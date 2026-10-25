"""Mechanism checks for hazards that change the actual accessible road network."""
import networkx as nx
import pytest

from backend.app.schemas import ACTIONABLE, GENERIC, ScenarioConfig
from backend.app.simulation import Simulation, simulate
from backend.app.simulation.engine import STATES
from backend.app.simulation.hazards import Tornado, Wildfire, make_hazard
from backend.app.simulation.world import SAFE_ZONES, STORM_SHELTERS, make_city


@pytest.fixture(scope="module", params=["wildfire", "tornado"])
def disaster_pair(request):
    config = ScenarioConfig(disaster_type=request.param)
    return config, simulate(config, GENERIC), simulate(config, ACTIONABLE)


def test_new_hazards_are_deterministic_and_warning_independent(disaster_pair):
    config, baseline, alternative = disaster_pair
    assert simulate(config, GENERIC) == baseline
    assert baseline["initial_conditions"] == alternative["initial_conditions"]
    assert baseline["initial_conditions_hash"] == alternative["initial_conditions_hash"]
    for a, b in zip(baseline["frames"], alternative["frames"], strict=True):
        assert a["hazard_cells"] == b["hazard_cells"]
        assert a["active_hazard_cells"] == b["active_hazard_cells"]
        assert a["blocked_roads"] == b["blocked_roads"]
        assert a["hazard"] == b["hazard"]


def test_new_hazards_change_exposure_and_routes(disaster_pair):
    config, baseline, alternative = disaster_pair
    city = make_city(config)
    assert baseline["metrics"]["evacuated"] != alternative["metrics"]["evacuated"]
    for run in (baseline, alternative):
        assert run["metrics"]["exposed"] > 0
        assert run["metrics"]["road_closures"] > 0
        assert run["metrics"]["route_replans"] > 0
        for old, frame in zip(run["frames"], run["frames"][1:]):
            closed = {tuple(p) for p in frame["blocked_roads"]}
            graph = nx.subgraph_view(city.graph, filter_node=lambda n, closed=closed: n not in closed)
            assert not closed.intersection(city.safe_zones)
            assert sum(frame["metrics"]["state_counts"].values()) == config.population
            for before, after in zip(old["agents"], frame["agents"], strict=True):
                start, end = tuple(before[1:3]), tuple(after[1:3])
                if start != end:
                    assert start not in closed and end not in closed
                    assert nx.shortest_path_length(graph, start, end) <= 2
                if STATES[after[3]] == "SHELTERED":
                    assert end in city.safe_zones
                if STATES[before[3]] == "SHELTERED":
                    assert before == after


def test_legacy_scenarios_still_default_to_the_original_flood():
    old = {"name": "Riverside", "population": 300, "seed": 42,
           "duration_ticks": 120, "tick_seconds": 5,
           "hazard_origin": [19, 4], "hazard_spread": 1}
    assert ScenarioConfig(**old) == ScenarioConfig()
    # These outcomes protect the established demo while hazard handling evolves.
    assert simulate(ScenarioConfig(), GENERIC)["metrics"]["evacuated"] == 188
    assert simulate(ScenarioConfig(), ACTIONABLE)["metrics"]["evacuated"] == 235


@pytest.mark.parametrize("kind,origin", [
    ("flood", (19, 4)), ("wildfire", (6, 12)), ("tornado", (3, 35)),
])
def test_disaster_default_origin(kind, origin):
    assert ScenarioConfig(disaster_type=kind).hazard_origin == origin


@pytest.mark.parametrize("kind,origin", [
    ("wildfire", (19, 4)), ("wildfire", (3, 3)),
    ("tornado", (9, 9)), ("tornado", (33, 21)),
])
def test_invalid_disaster_origins(kind, origin):
    with pytest.raises(ValueError):
        ScenarioConfig(disaster_type=kind, hazard_origin=origin)


def test_unknown_disaster_is_rejected():
    with pytest.raises(ValueError):
        ScenarioConfig(disaster_type="earthquake")


def test_wildfire_has_a_finite_front_and_a_river_fuel_break():
    config = ScenarioConfig(disaster_type="wildfire")
    city = make_city(config)
    fire = Wildfire(city, config)
    burned, closed = set(), set()
    for tick in range(361):
        fire.step(tick)
        assert burned <= fire.cells
        assert closed <= fire.blocked
        assert fire.active_cells <= fire.cells
        assert not fire.cells.intersection(city.river)
        assert not fire.cells.intersection(city.safe_zones)
        burned, closed = set(fire.cells), set(fire.blocked)
    assert len(burned) > 500
    assert fire.active_cells == set()
    assert len(fire.blocked) > 100
    assert all(x < 18 for x, _ in burned)
    # Equal-distance neighbors should ignite sooner downwind.
    assert fire.arrival[12, 7] < fire.arrival[12, 5]


def test_wildfire_can_start_on_either_river_bank():
    config = ScenarioConfig(disaster_type="wildfire", hazard_origin=(30, 12))
    fire = make_hazard(make_city(config), config)
    fire.step(120)
    assert len(fire.cells) > 100
    assert all(x > 20 for x, _ in fire.cells)


def test_tornado_moves_then_exits_and_leaves_persistent_debris():
    config = ScenarioConfig(disaster_type="tornado")
    city = make_city(config)
    storm = Tornado(city, config)
    storm.step(storm.start_tick - 1)
    assert not storm.active_cells and not storm.started
    storm.step(storm.start_tick)
    first_center = storm.center
    first_active = set(storm.active_cells)
    first_closed = set(storm.blocked)
    for tick in range(storm.start_tick + 1, 70):
        storm.step(tick)
    assert storm.center[0] > first_center[0] and storm.center[1] < first_center[1]
    assert storm.active_cells != first_active
    assert first_closed <= storm.blocked
    for tick in range(70, 361):
        storm.step(tick)
    assert not storm.active_cells
    assert len(storm.blocked) > 50
    assert not storm.blocked.intersection(city.safe_zones)
    assert first_active <= storm.cells


def test_tornado_uses_local_designated_storm_shelters():
    model = Simulation(ScenarioConfig(disaster_type="tornado"), ACTIONABLE)
    assert model.city.safe_zones == STORM_SHELTERS
    assert set(SAFE_ZONES) < set(model.city.safe_zones)
    assert all(p in model.city.graph for p in model.safe_zones)
    model.step()
    assert all(route[0] in model.safe_zones for route in model.paths.values())


@pytest.mark.parametrize("kind", ["wildfire", "tornado"])
def test_intensity_changes_the_hazard_not_the_population(kind):
    a = Simulation(ScenarioConfig(disaster_type=kind, population=20, hazard_spread=0.5), GENERIC)
    b = Simulation(ScenarioConfig(disaster_type=kind, population=20, hazard_spread=2), GENERIC)
    assert a.initial_conditions["agents"] == b.initial_conditions["agents"]
    for tick in range(61):
        a.hazard.step(tick)
        b.hazard.step(tick)
    assert a.hazard.cells != b.hazard.cells


def test_frames_describe_the_current_and_affected_hazard_separately():
    run = simulate(ScenarioConfig(disaster_type="wildfire", population=20), GENERIC)
    frame = run["frames"][-1]
    assert frame["hazard"]["type"] == "wildfire"
    assert frame["hazard"]["wind"] == [0.8, 0.6]
    assert len(frame["active_hazard_cells"]) < len(frame["hazard_cells"])
