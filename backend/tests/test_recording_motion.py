import hashlib
import json

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.schemas import ACTIONABLE, GENERIC, ScenarioConfig
from backend.app.simulation import Simulation, simulate


def test_motion_records_two_actual_edges_instead_of_cutting_a_corner():
    model = Simulation(ScenarioConfig(population=10, duration_ticks=12), GENERIC)
    resident = model.people[0]
    resident.position = (4, 9)
    resident.state = "EVACUATING"
    resident.progress, resident.movement_speed = 0.9, 1.3
    model.step()
    motion = next(m for m in model.frames[0]["agent_motion"] if m["id"] == resident.resident_id)
    assert motion["path"] == [[4, 9], [3, 9], [3, 8]]
    assert motion["fractions"] == [0, 0.5, 1]
    assert resident.position == (3, 8)


def test_motion_and_route_metadata_do_not_change_initial_conditions_or_outcomes():
    config = ScenarioConfig()
    model = Simulation(config, GENERIC)
    expected = hashlib.sha256(json.dumps(model.initial_conditions, sort_keys=True).encode()).hexdigest()
    assert model.initial_hash == expected
    baseline = model.run()
    alternative = simulate(config, ACTIONABLE)
    assert baseline["initial_conditions_hash"] == alternative["initial_conditions_hash"] == expected
    assert baseline["metrics"]["evacuated"] == 188
    assert alternative["metrics"]["evacuated"] == 235
    assert baseline["art_seed"] == alternative["art_seed"] == 42
    assert baseline["recording_version"] == "last-warning-recording/2"
    assert baseline["art_manifest_version"] == "last-warning-pixel/1"
    graph = model.city.graph
    for previous, frame in zip(baseline["frames"], baseline["frames"][1:]):
        before = {p[0]: p[1:3] for p in previous["agents"]}
        after = {p[0]: p[1:3] for p in frame["agents"]}
        motions = {m["id"]: m for m in frame["agent_motion"]}
        for resident_id, initial in before.items():
            if initial == after[resident_id]:
                assert resident_id not in motions
                continue
            motion = motions[resident_id]
            assert motion["path"][0] == initial
            assert motion["path"][-1] == after[resident_id]
            assert motion["fractions"][0] == 0 and motion["fractions"][-1] == 1
            assert all(graph.has_edge(tuple(a), tuple(b)) for a, b in zip(motion["path"], motion["path"][1:]))


def test_resident_inspector_reads_saved_traits_plans_and_legacy_defaults(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as client:
        scenario = client.post("/api/scenarios", json={"population": 20, "duration_ticks": 50}).json()
        run = client.post("/api/runs", json={"scenario_id": scenario["id"], "warning_id": "actionable"}).json()
        saved = app.state.store.recording(run["id"])
        resident = saved["initial_conditions"]["agents"][0]
        detail = client.get(f"/api/runs/{run['id']}/residents/0?tick=20")
        assert detail.status_code == 200
        value = detail.json()
        assert value["goal"] == resident["goal"]
        assert value["trust"] == resident["trust"]
        assert value["movement_speed_cells_per_tick"] == resident["movement_speed"]
        assert value["social_connections"] == resident["social_connections"]
        assert value["position"] == saved["frames"][20]["agents"][0][1:3]
        assert value["route_source"] in {None, "recorded_plan"}
        if value["route"]:
            assert value["route"][0] == value["position"]
        assert client.get(f"/api/runs/{run['id']}/residents/999").status_code == 404
        assert client.get(f"/api/runs/{run['id']}/residents/0?tick=999").status_code == 422
        original_hash, metrics = saved["initial_conditions_hash"], saved["metrics"]
        for field in ("art_seed", "art_manifest_version", "recording_version"):
            saved.pop(field, None)
            saved["city"].pop(field, None)
        for frame in saved["frames"]:
            frame.pop("agent_motion", None)
            frame.pop("route_changes", None)
        app.state.store.write_recording(run["id"], saved)
        legacy = client.get(f"/api/runs/{run['id']}/frames").json()
        assert legacy["art_seed"] == legacy["city"]["art_seed"] == run["seed"]
        assert legacy["recording_version"] is None
        assert "agent_motion" not in legacy["frames"][0]
        assert client.get(f"/api/runs/{run['id']}/residents/0").json()["route"] is None
        reread = app.state.store.recording(run["id"])
        assert reread["initial_conditions_hash"] == original_hash and reread["metrics"] == metrics
        assert "art_seed" not in reread
