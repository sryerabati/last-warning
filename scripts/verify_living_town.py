#!/usr/bin/env python3
"""Verify canonical town life and optionally run isolated warning comparisons.

The default checks local daily life only. --run-disasters creates experiments;
--decision-mode bedrock explicitly selects real paid decisions under app caps.
"""
import argparse
import hashlib
import json
import sys
import time
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.scripts.verify_disasters_demo import DISASTERS, LocalDemo, require, verify_artifact


def validate_day(day):
    city, frames, profiles = day['city'], day['frames'], day['profiles']
    require(city['layout'] == 'organic' and city['world_version'], 'Missing canonical organic world')
    require(len(frames) == day['total'] == 288, 'Expected a complete five-minute day')
    require(day['clock_start_minutes'] == 0 and day['minutes_per_tick'] == 5, 'Unexpected daily clock')
    roads, water = {tuple(p) for p in city['roads']}, {tuple(p) for p in city['river']}
    graph = nx.Graph()
    graph.add_nodes_from(roads)
    for x, y in roads:
        for other in [(x + 1, y), (x, y + 1)]:
            if other in roads:
                graph.add_edge((x, y), other)
    require(nx.is_connected(graph), 'Disconnected town roads')
    require(all(tuple(p) in roads for p in city['safe_zones']), 'Shelter is not reachable by road')
    centers = [sum(x for x, row in water if row == y) / sum(row == y for _, row in water)
               for y in range(city['size'])]
    require(max(centers) - min(centers) >= 3, 'River is still straight')
    places = {p['id']: p for p in city['places']}
    occupied = set()
    for place in places.values():
        cells = {tuple(p) for p in place['footprint']}
        require(bool(cells) and not cells.intersection(water | roads | occupied), 'Invalid building/park footprint')
        require(tuple(place['entrance']) in roads, 'Place has no reachable entrance')
        require(any(abs(x - place['entrance'][0]) + abs(y - place['entrance'][1]) == 1 for x, y in cells),
                'Entrance is detached from its place')
        occupied.update(cells)
    by_id = {p['id']: p for p in profiles}
    require(len(by_id) == len(profiles) > 0, 'Missing or duplicate residents')
    homes = defaultdict(set)
    for person in profiles:
        require(places[person['home_place_id']]['kind'] == 'home', 'Resident has no actual home')
        require(person['routine'] and person['household_id'], 'Missing household or itinerary')
        if person['work_place_id']:
            require(person['work_place_id'] in places, 'Unknown workplace')
        homes[person['household_id']].add(person['home_place_id'])
    require(all(len(value) == 1 for value in homes.values()), 'Household members have different homes')
    activity_counts = Counter()
    interactions, motion_count, turns, inside_samples = set(), 0, 0, 0
    previous = None
    snapshots = []
    for index, frame in enumerate(frames):
        require(frame['tick'] == index and frame['world_clock_minutes'] == index * 5, 'Daily clock is inconsistent')
        require(not frame['hazard_cells'] and not frame['blocked_roads'], 'Ambient day contains a disaster')
        people = {p[0]: p[1:3] for p in frame['agents']}
        activities = {p['id']: p for p in frame['agent_activities']}
        require(set(people) == set(activities) == set(by_id), 'Daily frame lost a resident/activity')
        require(all(tuple(p) in roads for p in people.values()), 'A resident left the walkable graph')
        indoors = 0
        for key, activity in activities.items():
            activity_counts[activity['activity']] += 1
            if activity['inside']:
                indoors += 1
                place = places[activity['place_id']]
                require(people[key] == place['entrance'], 'Indoor occupancy is not anchored at its entrance')
                require(place['kind'] in {'home', 'work', 'school', 'civic', 'shelter'}, 'Open-air place marked indoors')
        inside_samples += indoors
        for movement in frame.get('agent_motion', []):
            require(previous is not None, 'Initial midnight frame contains unexplained motion')
            path, fractions = movement['path'], movement['fractions']
            require(path[0] == previous[movement['id']] and path[-1] == people[movement['id']], 'Wrong motion endpoints')
            require(len(path) == len(fractions) and fractions[0] == 0 and fractions[-1] == 1, 'Invalid motion fractions')
            require(all(graph.has_edge(tuple(a), tuple(b)) for a, b in pairwise(path)), 'Movement skipped a road edge')
            require(all(a < b for a, b in pairwise(fractions)), 'Unordered motion fractions')
            motion_count += 1
            turns += int(len(path) > 2 and path[0][0] != path[-1][0] and path[0][1] != path[-1][1])
        for interaction in frame.get('interactions', []):
            keys = interaction['agent_ids']
            require(len(set(keys)) == len(keys) >= 2, 'Interaction needs actual distinct participants')
            require(all(people[key] == interaction['position'] for key in keys), 'Interaction participants are not together')
            require(interaction['tick'] <= index <= interaction['expires_tick'], 'Expired interaction was displayed')
            require(all(set(keys) - {key} <= set(activities[key]['partner_ids']) for key in keys),
                    'Interaction partners disagree with actual activity')
            interactions.add(interaction['id'])
        if index in [0, 96, 144, 216, 276]:
            snapshots.append({'tick': index, 'clock_minutes': frame['world_clock_minutes'], 'indoors': indoors,
                              'outdoors': len(people) - indoors, 'interactions': len(frame.get('interactions', []))})
        previous = people
    require(motion_count > 0 and turns > 0 and interactions and inside_samples, 'Missing actual life behavior')
    first = {p[0]: p[1:3] for p in frames[0]['agents']}
    require(previous == first, 'Midnight loop would teleport a resident')
    return {'world_version': city['world_version'], 'town_day_version': day['town_day_version'],
            'canonical_geometry_sha256': hashlib.sha256(json.dumps(city, sort_keys=True).encode()).hexdigest(),
            'residents': len(profiles), 'households': len(homes), 'places': dict(Counter(p['kind'] for p in places.values())),
            'roads': len(roads), 'river_cells': len(water), 'river_center_range': [min(centers), max(centers)],
            'frames': len(frames), 'motion_paths': motion_count, 'turning_paths': turns,
            'unique_interactions': len(interactions), 'activity_counts': dict(activity_counts),
            'samples': snapshots, 'loop_positions_match': True}


def submit(demo, body, evidence, save):
    # Persist identity before sending a paid request. Resuming reconnects to that
    # exact job; it cannot accidentally purchase a replacement experiment.
    request = {**body, 'idempotency_key': evidence.setdefault('idempotency_key', str(uuid.uuid4())),
               'analyze_warning': True}
    save()
    job = demo.json('/api/run-jobs', request)
    require(demo.json('/api/run-jobs', request)['id'] == job['id'], 'Duplicate request created another job')
    evidence.update(job_id=job['id'], idempotent=True)
    save()
    print(f"Started job {job['id']}", flush=True)
    deadline = time.monotonic() + 700
    while job['status'] in {'running', 'queued'}:
        require(time.monotonic() < deadline, 'Job exceeded verification deadline')
        time.sleep(.6)
        job = demo.json(f"/api/run-jobs/{job['id']}")
    evidence.update(status=job['status'], run_id=job.get('run_id'), progress=job['progress'])
    save()
    require(job['status'] == 'completed', f"Job did not complete: {job.get('error')}")
    return demo.json(f"/api/runs/{job['run_id']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--decision-mode', choices=['rules', 'bedrock'], default='rules')
    parser.add_argument('--run-disasters', nargs='*', choices=list(DISASTERS), default=[])
    parser.add_argument('--population', type=int, default=300)
    parser.add_argument('--start-tick', type=int, default=96)
    parser.add_argument('--output', type=Path, default=ROOT / 'output' / 'living-town-e2e.json')
    parser.add_argument('--resume', action='store_true', help='Reconnect to jobs saved in --output; never replace failed jobs')
    args = parser.parse_args()
    demo = LocalDemo(args.base_url)
    settings = {'decision_mode': args.decision_mode, 'population': args.population,
                'start_tick': args.start_tick, 'run_disasters': args.run_disasters}
    if args.resume:
        report = json.loads(args.output.read_text())
        require(report.get('settings') == settings, 'Resume settings must exactly match the saved report')
        report.pop('error', None)
        report['verified'] = False
    else:
        require(not args.output.exists() or args.decision_mode != 'bedrock' or not args.run_disasters,
                'Paid verification report already exists; use --resume or a new output path')
        report = {'verified': False, 'started_at': datetime.now(UTC).isoformat(), 'decision_mode': args.decision_mode,
                  'settings': settings, 'disasters': []}

    def save():
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')

    try:
        report.setdefault('budget_before', demo.json('/api/agents/status')['budget'])
        base = {'name': 'Living Riverside verification', 'population': args.population, 'seed': 42,
                'layout': 'organic', 'town_life': True, 'town_start_tick': args.start_tick,
                'decision_mode': args.decision_mode, 'duration_ticks': 120, 'tick_seconds': 5}
        started = time.monotonic()
        day = demo.json('/api/town-life/preview', base)
        report['day'] = validate_day(day)
        report['preview_seconds'] = time.monotonic() - started
        require(day == demo.json('/api/town-life/preview', base), 'Same seeded daily preview changed')
        report['deterministic_preview'] = True
        warnings = {w['id']: w for w in demo.json('/api/warnings')}
        for kind in args.run_disasters:
            result = next((row for row in report['disasters'] if row['disaster'] == kind), None)
            if result is None:
                scenario = demo.json('/api/scenarios', {**base, 'disaster_type': kind})
                result = {'disaster': kind, 'scenario_id': scenario['id'], 'runs': []}
                report['disasters'].append(result)
                save()
            records = []
            first_id = None
            for warning_id in DISASTERS[kind]['warnings']:
                evidence = next((row for row in result['runs'] if row['warning_id'] == warning_id), None)
                if evidence is None:
                    artifact = verify_artifact(demo, warnings[warning_id])
                    evidence = {'warning_id': warning_id, 'mini': artifact}
                    result['runs'].append(evidence)
                run = submit(demo, {'scenario_id': result['scenario_id'], 'warning_id': warning_id,
                                   'baseline_run_id': first_id, 'neural_analysis_id': evidence['mini']['analysis_id']},
                             evidence, save)
                first_id = first_id or run['id']
                record = demo.json(f"/api/runs/{run['id']}/frames")
                records.append(record)
                expected = {p[0]: p[1:3] for p in day['frames'][args.start_tick]['agents']}
                actual = {p[0]: p[1:3] for p in record['frames'][0]['agents']}
                require(actual == expected, 'Warning reset the visible town positions')
                require(record['city']['world_version'] == day['city']['world_version'], 'Warning changed worlds')
                require(record['frames'][0]['world_clock_minutes'] == args.start_tick * 5, 'Warning reset the daily clock')
                usage = (run.get('agent_policy') or {}).get('usage')
                if args.decision_mode == 'bedrock':
                    require(usage and usage['calls'] > 0 and usage['decision_protocol'] == 'nova_resident_json_life_v1',
                            'Missing actual living-town Bedrock protocol')
                evidence.update(metrics=run['metrics'], initial_conditions_hash=run['initial_conditions_hash'],
                                exact_visible_start=True, protocol=usage.get('decision_protocol') if usage else None,
                                model_calls=usage.get('calls') if usage else 0,
                                model_cost_usd=usage.get('accounted_cost_usd') if usage else 0,
                                actions=dict(Counter(e['action'] for f in record['frames'] for e in f.get('agent_decisions', [])
                                                     if e['tick'] == f['tick'])))
                save()
            require(result['runs'][0]['initial_conditions_hash'] == result['runs'][1]['initial_conditions_hash'],
                    'Warnings did not share the same initial population')
            for first, second in zip(records[0]['frames'], records[1]['frames'], strict=True):
                require(all(first.get(k) == second.get(k) for k in ['hazard_cells', 'active_hazard_cells', 'blocked_roads', 'hazard']),
                        'Warning wording changed physical hazards')
            result['comparison'] = demo.json('/api/comparisons', {'baseline_run_id': result['runs'][0]['run_id'],
                                                               'alternative_run_id': result['runs'][1]['run_id']})
            result['matched_hazards'] = True
            save()
        require(day == demo.json('/api/town-life/preview', base), 'An emergency mutated the cached daily world')
        report['day_unchanged_after_experiments'] = True
        report['budget_after'] = demo.json('/api/agents/status')['budget']
        require(report['budget_after']['project_accounted_cost_usd'] < 30, 'Project cap exceeded')
        report.update(verified=True, finished_at=datetime.now(UTC).isoformat())
        save()
        print(f'LIVING_TOWN_VERIFIED: {args.output}', flush=True)
    except Exception as error:
        report.update(error=f'{type(error).__name__}: {error}', finished_at=datetime.now(UTC).isoformat())
        save()
        raise


if __name__ == '__main__':
    main()
