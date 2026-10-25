"""Canonical geography, daily life, and an unchanged handoff into an emergency."""
import copy
from itertools import pairwise

import networkx as nx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.bedrock import Decision
from backend.app.main import create_app
from backend.app.schemas import ACTIONABLE, GENERIC, ScenarioConfig
from backend.app.simulation import Simulation, simulate
from backend.app.simulation.life import town_day
from backend.app.simulation.world import STORM_SHELTERS, make_city


def config(**updates):
    return ScenarioConfig(**{"layout": "organic", "town_life": True, "population": 30,
                             "duration_ticks": 24, "town_start_tick": 96, **updates})


@pytest.fixture(scope="module")
def day():
    return town_day(80, 42, "flood")


def test_canonical_places_and_refuges_are_real_connected_land_footprints():
    city = make_city(config())
    assert nx.is_connected(city.graph)
    assert {tuple(p["entrance"]) for p in city.places if p["kind"] == "shelter"} == set(STORM_SHELTERS)
    footprints = set()
    for place in city.places:
        cells = {tuple(p) for p in place["footprint"]}
        entrance = tuple(place["entrance"])
        assert not cells.intersection(city.graph) and not cells.intersection(city.river)
        assert not cells.intersection(footprints)
        assert entrance in city.graph
        assert min(abs(x-entrance[0]) + abs(y-entrance[1]) for x, y in cells) == 1
        assert all(nx.has_path(city.graph, entrance, refuge) for refuge in city.safe_zones)
        for point in place.get("activity_spots", []):
            assert tuple(point) in city.graph and tuple(point) not in city.river
            assert nx.shortest_path_length(city.graph, entrance, tuple(point)) <= 2
        footprints.update(cells)
    assert len([p for p in city.places if p["kind"] == "home"]) == 64
    assert {p["kind"] for p in city.road_styles} == {"road", "path", "bridge"}
    assert {tuple(p["position"]) for p in city.road_styles if p["kind"] == "bridge"} == set(city.roads).intersection(city.river)
    river_centers = [sum(x for x, row in city.river if row == y) / 3 for y in range(40)]
    assert max(river_centers) - min(river_centers) >= 6


def test_households_names_and_itineraries_are_seeded_and_grounded(day):
    places = {p["id"]: p for p in day["city"]["places"]}
    assert len(day["profiles"]) == 80
    other = town_day(80, 99, "flood")
    assert [p["name"] for p in day["profiles"]] != [p["name"] for p in other["profiles"]]
    for profile in day["profiles"]:
        assert places[profile["home_place_id"]]["kind"] == "home"
        household = [p for p in day["profiles"] if p["household_id"] == profile["household_id"]]
        assert {p["home_place_id"] for p in household} == {profile["home_place_id"]}
        assert len({p["name"].split()[-1] for p in household}) == 1
        assert all(p["id"] in profile["social_connections"] for p in household if p["id"] != profile["id"])
        assert profile["routine"][0]["start_minute"] == 0
        for visit in profile["routine"]:
            assert visit["place_id"] in places
            assert tuple(visit["destination"]) in {tuple(p) for p in day["city"]["roads"]}
        if profile["role"] == "student":
            assert places[profile["work_place_id"]]["kind"] == "school"


def test_full_day_paths_indoor_occupancy_meetings_and_midnight_loop_are_actual(day):
    graph = make_city(config(population=80)).graph
    places = {p["id"]: p for p in day["city"]["places"]}
    assert len(day["frames"]) == 288
    assert day["frames"][96]["world_clock_minutes"] == 480
    turns, meetings, motion_count = 0, 0, 0
    previous = None
    seen_activities = set()
    for frame in day["frames"]:
        positions = {p[0]: p[1:3] for p in frame["agents"]}
        activities = {p["id"]: p for p in frame["agent_activities"]}
        assert set(positions) == set(activities) == set(range(80))
        assert all(tuple(p) in graph for p in positions.values())
        for motion in frame["agent_motion"]:
            path = motion["path"]
            assert previous is not None
            assert path[0] == previous[motion["id"]] and path[-1] == positions[motion["id"]]
            assert motion["fractions"][0] == 0 and motion["fractions"][-1] == 1
            assert all(a < b for a, b in pairwise(motion["fractions"]))
            assert all(graph.has_edge(tuple(a), tuple(b)) for a, b in pairwise(path))
            turns += len(path) > 2 and path[0][0] != path[-1][0] and path[0][1] != path[-1][1]
            motion_count += 1
        for key, activity in activities.items():
            seen_activities.add(activity["activity"])
            if activity["inside"]:
                place = places[activity["place_id"]]
                assert place["kind"] in {"home", "work", "school", "civic"}
                assert positions[key] == place["entrance"]
            for partner in activity["partner_ids"]:
                assert not activity["inside"] and not activities[partner]["inside"]
                assert positions[key] == positions[partner]
                assert key in activities[partner]["partner_ids"]
        for interaction in frame["interactions"]:
            assert interaction["tick"] == frame["tick"] < interaction["expires_tick"]
            assert len(interaction["agent_ids"]) == 2
            assert all(positions[key] == interaction["position"] for key in interaction["agent_ids"])
            meetings += 1
        previous = positions
    assert turns > 0 and motion_count > 500 and meetings > 10
    assert {"working", "studying", "shopping", "relaxing", "sleeping", "commuting"} <= seen_activities
    assert day["frames"][0]["agents"] == day["frames"][-1]["agents"]
    assert all(a["inside"] and a["activity"] == "sleeping" for a in day["frames"][-1]["agent_activities"])


@pytest.mark.parametrize("tick", [0, 96, 150, 287])
def test_emergency_starts_at_exact_visible_day_snapshot(tick):
    settings = config(town_start_tick=tick)
    model = Simulation(settings, GENERIC)
    model.step()
    source = town_day(30, 42, "flood")["frames"][tick]
    assert model.frames[0]["agents"] == source["agents"]
    assert model.frames[0]["agent_activities"] == source["agent_activities"]
    assert model.frames[0]["world_clock_minutes"] == tick * 5
    assert model.frames[0]["agent_motion"] == []
    model.step()
    assert model.frames[1]["world_clock_minutes"] == pytest.approx((tick * 5 + 5 / 60) % 1440)


@pytest.mark.parametrize("kind", ["flood", "wildfire", "tornado"])
def test_new_world_counterfactuals_keep_common_initial_conditions_and_physical_hazards(kind):
    settings = config(disaster_type=kind, population=20)
    first, second = simulate(settings, GENERIC), simulate(settings, ACTIONABLE)
    assert first["initial_conditions_hash"] == second["initial_conditions_hash"]
    assert first["profiles"] == second["profiles"]
    assert [f["hazard_cells"] for f in first["frames"]] == [f["hazard_cells"] for f in second["frames"]]
    assert first["city"]["layout"] == "organic"


class LifePolicy:
    """A test-only provider boundary; the actual application still invokes Bedrock."""
    def __init__(self, action):
        self.action = action
        self.calls = []
        self.usage = {"provider": "test-only", "model_id": "test-life", "calls": 0}

    def decide(self, residents, warning, scenario, tick):
        self.calls.append(copy.deepcopy(residents))
        self.usage["calls"] += 1
        return {r["id"]: Decision(self.action, "Test boundary choice") for r in residents}


def test_continue_routine_moves_but_wait_holds_until_another_model_choice():
    settings = config(decision_mode="bedrock", duration_ticks=12)
    warning = GENERIC.model_copy(update={"channels": []})
    walking_policy, waiting_policy = LifePolicy("CONTINUE_ROUTINE"), LifePolicy("WAIT")
    walking = simulate(settings, warning, decision_policy=walking_policy)
    waiting = simulate(settings, warning, decision_policy=waiting_policy)
    assert walking["frames"][0]["agents"] == waiting["frames"][0]["agents"]
    assert waiting["frames"][4]["agents"] == waiting["frames"][12]["agents"]
    assert any(m["path"] for frame in walking["frames"][5:] for m in frame["agent_motion"])
    assert not any(frame["agent_motion"] for frame in waiting["frames"][4:])
    assert waiting["metrics"]["evacuation_started"] == 0
    for resident in walking_policy.calls[0]:
        assert "CONTINUE_ROUTINE" in resident["available_actions"]
        assert resident["perceived_warning"] is None
        assert resident["town_life"]["home"]["name"]
        assert resident["town_life"]["household_members"]
        if resident["town_life"]["role"] != "neighbor":
            assert resident["town_life"]["workplace"]["name"]
        if resident["town_life"]["inside"]:
            assert resident["hazard"]["visible_active_cells"] == []


def test_evacuate_exits_real_indoor_occupancy_and_uses_actual_paths():
    result = simulate(config(decision_mode="bedrock", town_start_tick=60, duration_ticks=12),
                      GENERIC, decision_policy=LifePolicy("EVACUATE"))
    assert all(a["inside"] for a in result["frames"][0]["agent_activities"])
    assert any(not a["inside"] and a["activity"] == "evacuating" for a in result["frames"][4]["agent_activities"])
    assert result["frames"][4]["agent_motion"]
    shelter_ids = {p["id"] for p in result["city"]["places"] if p["kind"] == "shelter"}
    assert all(a["destination_place_id"] in shelter_ids for a in result["frames"][4]["agent_activities"])


def test_stranded_resident_clears_previous_routine_destination():
    model = Simulation(config(), GENERIC)
    model.step()
    resident = model.people[0]
    model.paths = {}
    model.move_resident(resident)
    assert resident.state == "STRANDED" and resident.activity == "stranded"
    assert resident.destination_place_id is None and resident.destination is None


def test_town_day_api_is_free_cached_compressed_and_runs_export_real_profiles(tmp_path, monkeypatch):
    from backend.app import main

    monkeypatch.setattr(main, "BedrockPolicy", lambda *a, **k: pytest.fail("Daily preview must never call Bedrock"))
    app = create_app(tmp_path)
    with TestClient(app) as client:
        settings = config(population=20, duration_ticks=12).model_dump(mode="json")
        before = town_day.cache_info()
        response = client.post("/api/town-life/preview", json=settings)
        assert response.status_code == 200 and response.headers["content-encoding"] == "gzip"
        day = response.json()
        changed = client.post("/api/town-life/preview", json={**settings, "town_start_tick": 200}).json()
        assert changed == day
        assert town_day.cache_info().hits > before.hits
        scenario = client.post("/api/scenarios", json=settings).json()
        run = client.post("/api/runs", json={"scenario_id": scenario["id"], "warning_id": "generic"})
        assert run.status_code == 201
        result = run.json()
        assert "profiles" not in result
        recording = client.get(f"/api/runs/{result['id']}/frames").json()
        assert recording["profiles"] == day["profiles"]
        assert recording["frames"][0]["agents"] == day["frames"][96]["agents"]
        detail = client.get(f"/api/runs/{result['id']}/residents/0?tick=0").json()
        assert detail["name"] == day["profiles"][0]["name"]
        assert detail["home_place_id"] == day["profiles"][0]["home_place_id"]
        assert detail["inside"] == day["frames"][96]["agent_activities"][0]["inside"]
        assert client.post("/api/town-life/preview", json={"town_life": False}).status_code == 422


def test_town_life_rejects_missing_canonical_places_and_out_of_day_snapshots():
    with pytest.raises(ValidationError, match="organic"):
        ScenarioConfig(town_life=True)
    with pytest.raises(ValidationError):
        config(town_start_tick=288)


def test_legacy_initial_conditions_still_omit_new_default_fields():
    legacy = Simulation(ScenarioConfig(population=10), GENERIC)
    assert not {"layout", "town_life", "town_start_tick"}.intersection(legacy.initial_conditions["configuration"])
    assert all(a.profile is None for a in legacy.people)
    assert "places" not in legacy.city.serialize()
