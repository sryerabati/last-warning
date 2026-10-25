from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_campus_pair_survives_api_storage_and_comparison(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        config = {"name": "Campus contract", "layout": "campus", "town_life": True,
                  "town_start_minutes": 700, "population": 20, "seed": 42,
                  "disaster_type": "thunderstorm", "decision_mode": "rules",
                  "campus_day_type": "class_break", "transit_enabled": False}
        scenario = client.post('/api/scenarios', json=config).json()
        assert scenario["campus_day_type"] == "class_break"
        assert scenario["transit_enabled"] is False
        preview = client.post('/api/scenarios/preview', json=config)
        assert preview.status_code == 200
        frozen = preview.json()['frame']
        runs = []
        for mode in ('generic', 'actionable'):
            response = client.post('/api/runs', json={
                'scenario_id': scenario['id'], 'warning_id': f'campus-{mode}-thunderstorm',
                'baseline_run_id': runs[0]['id'] if runs else None,
            })
            assert response.status_code == 201, response.text
            run = response.json()
            record = client.get(f"/api/runs/{run['id']}/frames").json()
            assert [p[:3] for p in record['frames'][0]['agents']] == [p[:3] for p in frozen['agents']]
            assert record['frames'][0]['vehicles'] == frozen['vehicles']
            assert len(record['profiles']) == 20
            assert run['configuration']['campus_day_type'] == 'class_break'
            assert run['configuration']['transit_enabled'] is False
            assert not any(v['type'] == 'bus' for v in record['frames'][0]['vehicles'])
            assert all(p['appearance'] for p in record['profiles'])
            assert record['frames'][-1]['hazard']['all_clear']
            details = client.get(f"/api/runs/{run['id']}/residents/0?tick=30")
            assert details.status_code == 200
            assert details.json()["response_timing_seconds"]["attention"] >= 5
            assert details.json()["reaction_delay_ticks"] is None
            activity = next(a for a in record['frames'][30]['agent_activities'] if a['id'] == 0)
            assert details.json()['current_speed_mps'] == activity.get('speed_mps')
            assert details.json()['movement_style'] == activity.get('movement_style')
            assert details.json()['weather_response'] == activity.get('weather_response')
            runs.append(run)
        comparison = client.post('/api/comparisons', json={
            'baseline_run_id': runs[0]['id'], 'alternative_run_id': runs[1]['id'],
        })
        assert comparison.status_code == 201, comparison.text
        # Descriptive and boolean metrics are not numeric deltas.
        assert 'exposure_method' not in comparison.json()['deltas']
        assert 'all_clear' not in comparison.json()['deltas']
        assert runs[0]['initial_conditions_hash'] == runs[1]['initial_conditions_hash']
        assert client.get('/api/health').json()['campus_simulation_version'] == runs[0]['simulation_version']


def test_historical_campus_route_uses_its_saved_map(tmp_path, monkeypatch):
    from backend.app.simulation import campus_world

    def no_current_map():
        raise AssertionError("A historical resident lookup must not rebuild today's map")

    monkeypatch.setattr(campus_world, 'make_campus_city', no_current_map)
    app = create_app(tmp_path)
    app.state.store.put('runs', {'simulation_version': 'last-warning-campus/1.0.0'}, 'historical-campus')
    app.state.store.write_recording('historical-campus', {
        'city': {'layout': 'campus', 'size': 40, 'map_bounds': [1, 6, 39, 34],
                 'world_version': 'osu-academic-core/1'},
        'configuration': {'layout': 'campus', 'population': 10, 'disaster_type': 'flood',
                          'hazard_origin': [13, 27]},
        'states': ['UNAWARE'],
        'initial_conditions': {'agents': [{'id': 0, 'position': [20, 20]}]},
        'frames': [{'tick': 0, 'time': 0, 'agents': [[0, 20, 20, 0, 0]],
                    'blocked_roads': [], 'agent_activities': [],
                    'route_changes': [{'id': 0, 'path': [[20, 20], [21, 20]], 'destination': [21, 20]}]}],
    })
    with TestClient(app) as client:
        response = client.get('/api/runs/historical-campus/residents/0?tick=0')
        assert response.status_code == 200, response.text
        assert response.json()['route_accessible'] is True
        assert response.json()['route'] == [[20, 20], [21, 20]]
        recording = app.state.store.recording('historical-campus')
        recording['configuration'].update(disaster_type='public_safety', hazard_origin=[20, 20])
        recording['frames'][0].update(time=120, blocked_roads=[[20, 20]])
        recording['frames'][0]['route_changes'][0].update(path=[[20, 20], [26, 20]], destination=[26, 20])
        app.state.store.write_recording('historical-campus', recording)
        outward = client.get('/api/runs/historical-campus/residents/0?tick=0').json()
        assert outward['route_accessible'] is True
        # Reverse motion from the boundary toward danger is still forbidden.
        recording['frames'][0]['agents'][0][1:3] = [26, 20]
        recording['frames'][0]['route_changes'][0].update(path=[[26, 20], [20, 20]], destination=[20, 20])
        app.state.store.write_recording('historical-campus', recording)
        inward = client.get('/api/runs/historical-campus/residents/0?tick=0').json()
        assert inward['route_accessible'] is False
