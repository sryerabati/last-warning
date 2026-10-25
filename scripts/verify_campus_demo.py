#!/usr/bin/env python3
"""Resume-safe campus integration check. --bedrock explicitly permits paid calls.

Exercises API persistence, matched warnings, exact frozen life, passenger
conservation, replay and genuine local Mini artifacts. Default mode is offline
rules; neither mode silently falls back from Bedrock.
"""
import argparse
import json
import math
import sys
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.scripts.verify_disasters_demo import LocalDemo, require, verify_artifact
from scripts.verify_living_town import submit


def validate_record(record, population):
    require(record['city']['layout'] == 'campus', 'Wrong world')
    require(len(record['profiles']) == population, 'Profiles were lost in the API')
    frames = record['frames']
    modes, actions = set(), set()
    for frame in frames:
        people = {p[0]: p for p in frame['agents']}
        activities = {a['id']: a for a in frame['agent_activities']}
        require(len(people) == len(activities) == population, 'A frame lost a resident')
        occupants = []
        for car in frame['vehicles']:
            require(len(car['occupant_ids']) <= car['capacity'], 'Vehicle over capacity')
            occupants.extend(car['occupant_ids'])
            for i in car['occupant_ids']:
                require(activities[i]['vehicle_id'] == car['id'], 'Passenger is bound to the wrong car')
                require(activities[i]['mode'] in {'riding', 'driving', 'alighting'}, 'Passenger has an unrelated walking mode')
                if activities[i]['mode'] == 'alighting':
                    require(car['state'] in ({'dwelling'} if car['type'] == 'bus' else {'alighting'}), 'Exit transition disagrees with the vehicle')
                require(math.dist(people[i][1:3], [car['x'], car['y']]) < 1e-5, 'Passenger left the vehicle')
        require(len(occupants) == len(set(occupants)), 'Resident was duplicated in cars')
        require({a['id'] for a in activities.values() if a['mode'] in {'riding', 'driving'}} <= set(occupants), 'Rider has no car')
        modes.update(a['mode'] for a in activities.values())
        actions.update(d['action'] for d in frame.get('agent_decisions', []))
        for motion in frame.get('agent_motion', []) + frame.get('vehicle_motion', []):
            fractions = motion['fractions']
            require(len(fractions) == len(motion['path']) and fractions[0] == 0 and fractions[-1] == 1, 'Invalid replay trajectory')
            require(all(a < b for a, b in pairwise(fractions)), 'Non-monotonic replay fractions')
    return {'frames': len(frames), 'population': population, 'vehicles': len(frames[0]['vehicles']),
            'modes': sorted(modes), 'recorded_actions': sorted(actions), 'passenger_conservation': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bedrock', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--population', type=int, default=40)
    parser.add_argument('--hazard', default='thunderstorm', choices=['flood','wildfire','tornado','blizzard','hailstorm','thunderstorm','public_safety'])
    parser.add_argument('--output', type=Path, default=ROOT/'output'/'campus-demo-e2e.json')
    args = parser.parse_args()
    demo = LocalDemo('http://127.0.0.1:8000')
    settings = {'mode': 'bedrock' if args.bedrock else 'rules', 'population': args.population, 'hazard': args.hazard, 'start_minute': 700}
    if args.resume:
        report = json.loads(args.output.read_text())
        require(report['settings'] == settings, 'Resume settings differ')
    else:
        require(not args.output.exists(), 'Evidence already exists: use --resume to reconnect without buying replacement jobs')
        report = {'settings': settings, 'started_at': datetime.now(UTC).isoformat(), 'verified': False, 'runs': []}
    def save():
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    save()
    try:
        report.setdefault('budget_before', demo.json('/api/agents/status')['budget'])
        config = {'name': f'Campus {args.hazard} paired demo', 'layout': 'campus', 'town_life': True,
                  'population': args.population, 'seed': 42, 'town_start_tick': 140, 'town_start_minutes': 700,
                  'disaster_type': args.hazard, 'decision_mode': settings['mode']}
        if 'scenario_id' not in report:
            report['scenario_id'] = demo.json('/api/scenarios', config)['id'];save()
        config = demo.json(f"/api/scenarios/{report['scenario_id']}")
        preview = demo.json('/api/scenarios/preview', {k:v for k,v in config.items() if k not in {'id','created_at'}})
        initial = preview['frame']
        warnings = {w['id']: w for w in demo.json('/api/warnings')}
        first = None
        for mode in ('generic', 'actionable'):
            warning_id = f'campus-{mode}-{args.hazard}'
            evidence = next((r for r in report['runs'] if r['warning_id'] == warning_id), None)
            if evidence is None:
                evidence = {'warning_id': warning_id};report['runs'].append(evidence);save()
            evidence['mini'] = verify_artifact(demo, warnings[warning_id]);save()
            run = submit(demo, {'scenario_id': report['scenario_id'], 'warning_id': warning_id,
                               'baseline_run_id': first, 'neural_analysis_id': evidence['mini']['analysis_id']}, evidence, save)
            first = first or run['id']
            record = demo.json(f"/api/runs/{run['id']}/frames")
            require([a[:3] for a in record['frames'][0]['agents']] == [a[:3] for a in initial['agents']], 'Warning changed the frozen people')
            require(record['frames'][0]['vehicles'] == initial['vehicles'], 'Warning changed the frozen cars')
            evidence['checks'] = validate_record(record, args.population)
            require(run['decision_mode'] == settings['mode'], 'Decision provider mismatch')
            if args.bedrock:
                usage = run['agent_policy']['usage']
                require(usage['calls'] > 0 and usage['decision_count'] > 0, 'No real model decisions recorded')
                require(usage['accounted_cost_usd'] <= .3, 'Per-run cost guard exceeded')
                evidence['usage'] = usage
            evidence['metrics'] = run['metrics'];save()
        report['comparison'] = demo.json('/api/comparisons', {'baseline_run_id': report['runs'][0]['run_id'], 'alternative_run_id': report['runs'][1]['run_id']})
        report['budget_after'] = demo.json('/api/agents/status')['budget']
        require(report['budget_after']['project_accounted_cost_usd'] <= 30, 'Project spending guard exceeded')
        report.update(verified=True, finished_at=datetime.now(UTC).isoformat());report.pop('error', None);save()
        print(json.dumps({'verified': True, 'comparison_id': report['comparison']['id'], 'runs':[r['run_id'] for r in report['runs']], 'project_accounted_usd':report['budget_after']['project_accounted_cost_usd']}), flush=True)
    except Exception as error:
        report.update(error=str(error), verified=False);save();raise

if __name__ == '__main__':
    main()
