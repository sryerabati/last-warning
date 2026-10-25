"""Expanded scene evidence, housing semantics, and pedestrian access regression tests."""
import json
from collections import Counter, defaultdict

import networkx as nx
import pytest

from backend.app.simulation.campus_world import (
    CAMERA_FOCUS,
    CAMPUS_SIZE,
    DATA,
    DEFAULT_ORIGINS,
    OFFICIAL_RESIDENCE_NAMES,
    _cells,
    _crosses_building,
    _exterior_segments,
    _food_source,
    distance,
    inside_polygon,
    make_campus_city,
    project,
)


@pytest.fixture(scope="module")
def city():
    return make_campus_city()


def test_expansion_preserves_metric_scale_and_actual_campus_relationships(city):
    assert city.size == CAMPUS_SIZE == 68
    assert city.meters_per_unit == 24.25
    assert city.map_bounds[2]-city.map_bounds[0] > 60
    assert city.map_bounds[3]-city.map_bounds[1] > 45
    assert city.serialize()["camera_focus"] == CAMERA_FOCUS
    assert CAMERA_FOCUS == list(project((-83.0123,39.9994)))
    assert all(0 < value < city.size for point in DEFAULT_ORIGINS.values() for value in point)
    names = {p["name"]:p for p in city.places}
    for dorm in ("Baker Hall","Bradley Hall","Paterson Hall","German House","Park-Stradley Hall"):
        assert names[dorm]["housing_type"] == "dormitory"
    assert names["Thompson Library"]["entrance"][0] < names["Ohio Union"]["entrance"][0]
    assert len(city.geometry["trees"]) > 3000


def test_households_have_actual_distinct_complete_house_footprints(city):
    houses = [p for p in city.places if p.get("family_home_eligible")]
    assert len(houses) > 100
    assert len({tuple(p["entrance"]) for p in houses}) == len(houses)
    for house in houses:
        assert house["kind"] == "home"
        assert house["household_capacity"] == 1
        assert house["capacity"] <= 6
        assert house["housing_type"] == "house"
        assert house["osm_building_type"] in {"house","detached","semidetached_house"}
        assert tuple(house["entrance"]) in city.graph
        assert all(city.map_bounds[0] < p[0] < city.map_bounds[2] and city.map_bounds[1] < p[1] < city.map_bounds[3] for p in house["footprint"])
    names = {p["name"]:p for p in city.places}
    assert names["Alpha Gamma Rho"]["housing_type"] == "student_house"
    assert names["North Columbus Friends Meeting"]["kind"] != "home"
    assert names["Schottenstein Chabad Student Jewish Center"]["kind"] != "home"
    assert names["Kuhn Honors and Scholars House"]["kind"] != "home"
    assert names["Scholars House West"]["housing_type"] == "dormitory"
    for name in ("Fechko Alumnae Scholarship House","Hanley House","Pomerene House"):
        assert names[name]["kind"] == "home"
        assert names[name]["housing_type"] == "dormitory"
        assert names[name]["housing_classification_source"].startswith("https://housing.osu.edu/")
    assert "Worthington Building" in OFFICIAL_RESIDENCE_NAMES  # Catalogued, but outside the playable destination set.


def test_authored_entry_connectors_do_not_cut_through_walls(city):
    buildings = [f["geometry"]["coordinates"] for f in city.geometry["buildings"]+city.geometry["water"]]
    for a,b,edge in city.graph.edges(data=True):
        if edge.get("kind") not in {"entrance_connector","parking_connector"}:
            continue
        assert edge["weight"] <= 32.001
        assert edge["weight"] == pytest.approx(distance(a,b)*city.meters_per_unit)
        for rings in buildings:
            ring = rings[0]
            if max(a[0],b[0]) < min(p[0] for p in ring) or min(a[0],b[0]) > max(p[0] for p in ring):
                continue
            if max(a[1],b[1]) < min(p[1] for p in ring) or min(a[1],b[1]) > max(p[1] for p in ring):
                continue
            assert not _crosses_building(a,b,rings)
    assert nx.is_connected(city.graph)


def test_exterior_routes_never_use_unsupported_interior_corridors(city):
    buildings = [f for f in city.geometry["buildings"] if f.get("kind") not in {"roof","roof;yes","bridge","no"}]
    grid = defaultdict(set)
    for i,building in enumerate(buildings):
        for cell in _cells(building["geometry"]["coordinates"][0]):
            grid[cell].add(i)
    for a,b,edge in city.graph.edges(data=True):
        if edge.get("authored"):
            continue
        for i in set().union(*(grid[cell] for cell in _cells((a,b)))):
            outside = _exterior_segments(a,b,buildings[i]["geometry"]["coordinates"],city.meters_per_unit)
            assert sum(distance(start,end) for start,end in outside) >= distance(a,b)-.0001


def test_commuter_homes_are_boundary_portals_not_false_houses(city):
    portals = [p for p in city.places if p.get("is_portal")]
    assert {p["id"] for p in portals} == {"commuter-north","commuter-south","commuter-east","commuter-west"}
    for portal in portals:
        assert portal["housing_type"] == "commuter"
        assert not portal["solid_building"]
        assert not portal["shelter_eligible"] and not portal["public_shelter"]
        assert tuple(portal["entrance"]) in city.graph
        assert tuple(portal["vehicle_position"]) in city.vehicle_graph
        x,y = portal["entrance"]
        l,t,r,b = city.map_bounds
        assert min(abs(x-l),abs(x-r),abs(y-t),abs(y-b))*city.meters_per_unit < 30
    assert all(not p["shelter_eligible"] and not p["storm_shelter"] for p in city.places if p.get("is_parking"))


def test_wall_crossing_detects_thin_obstacles_but_allows_exterior_approach():
    rings = [[[1,0],[1.01,0],[1.01,1],[1,1],[1,0]]]
    assert _crosses_building((0,.5),(3,.5),rings)
    assert not _crosses_building((0,.5),(1,.5),rings)


def test_food_service_requires_a_real_contained_venue_not_generic_retail(city):
    source = {f["id"]:f for f in json.loads((DATA/"osu-district.geojson").read_text())["features"]}
    names = {p["name"]:p for p in city.places}
    matched = Counter()
    for place in city.places:
        if place.get("food_service") or place.get("coffee_service"):
            assert place["kind"] != "home" and not place.get("is_parking")
            assert place["service_sources"]
            for service in place["service_sources"]:
                feature = source[service["source_id"]]
                assert feature["properties"]["amenity"] in {"restaurant","fast_food","food_court","cafe"}
                if feature["geometry"]["type"] == "Point":
                    assert inside_polygon(project(feature["geometry"]["coordinates"]),place["footprint"])
                    matched[feature["id"]] += 1
                else:
                    assert feature["id"] == place["id"]
    assert all(count == 1 for count in matched.values())
    assert names["Starbucks"]["coffee_service"]
    assert names["McDonald's"]["food_service"]
    assert not names["Chittenden Veterinary Clinic"]["food_service"]
    # Mixed-use source footprints can have an unrelated building name: the
    # actual contained business is retained for activity/inspector text.
    assert names["The View on High"]["food_venues"] == ["Yes Sushi"]
    assert names["Newport Music Hall"]["food_venues"] == ["Chipotle"]
    assert names["Thompson Library"]["coffee_venues"] == ["Berry Cafe"]
    assert "Traditions at Kennedy" in names["Kennedy Commons"]["food_venues"]


def test_beverage_only_cafe_is_not_assumed_to_offer_lunch_or_coffee():
    tea = _food_source("test",{"amenity":"cafe","cuisine":"bubble_tea"})
    assert not tea["food_service"] and not tea["coffee_service"]
    cafe = _food_source("test",{"amenity":"cafe","cuisine":"coffee_shop"})
    assert cafe["food_service"] and cafe["coffee_service"]
