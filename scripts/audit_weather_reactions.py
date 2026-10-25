"""Offline full-population weather checks and real-engine renderer fixtures.

Explicit rules baseline; this never invokes Bedrock or writes production runs.
"""
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.schemas import ScenarioConfig, WarningConfig
from backend.app.simulation.campus_engine import CampusSimulation


def point_at(motion, fraction):
    for i in range(1, len(motion['fractions'])):
        if fraction <= motion['fractions'][i]:
            a, b = motion['path'][i-1:i+1]
            start, end = motion['fractions'][i-1:i+1]
            t = (fraction-start)/(end-start)
            return [a[j]+(b[j]-a[j])*t for j in range(2)]
    return motion['path'][-1]


def activity_at(frame, resident, fraction):
    activity = next(a for a in frame['agent_activities'] if a['id'] == resident)
    for change in frame.get('agent_activity_transitions', []):
        if change['id'] == resident and change['fraction'] <= fraction:
            activity = {**activity, **change}
    return activity


def sample_case(record, kind, style=None, vehicle=False):
    for index, frame in enumerate(record['frames'][1:], 1):
        for motion in frame.get('vehicle_motion' if vehicle else 'agent_motion', []):
            for segment in range(1, len(motion['fractions'])):
                if math.dist(*motion['path'][segment-1:segment+1]) < .01:
                    continue
                fraction = sum(motion['fractions'][segment-1:segment+1])/2
                if vehicle:
                    state = next(v for v in frame['vehicles'] if v['id'] == motion['id'])
                    for change in frame.get('vehicle_state_transitions', []):
                        if change['id'] == motion['id'] and change['fraction'] <= fraction:
                            state = {**state, **change}
                    match = state.get('weather_response') == 'snow_caution' and state['type'] == 'car'
                else:
                    state = activity_at(frame, motion['id'], fraction)
                    match = state.get('movement_style') == style and not state.get('inside') and state.get('mode') == 'walking'
                if match:
                    return {'id':kind,'type':record['configuration']['disaster_type'],
                            'previous':record['frames'][index-1], 'frame':frame,'fraction':fraction,
                            'camera':point_at(motion, fraction),'resident_id':None if vehicle else motion['id'],
                            'vehicle_id':motion['id'] if vehicle else None}
    return None


def main():
    output = ROOT/'output'
    output.mkdir(exist_ok=True)
    report = {'test_fixture':True,'provider':'rules','note':'Offline engine audit; no new model decisions or measured human behavior.','runs':[]}
    fixture = {'test_fixture':True,'note':report['note'],'cases':[]}
    for kind in ('thunderstorm', 'blizzard', 'tornado'):
        start = time.monotonic()
        config = ScenarioConfig(name=f'Offline weather behavior audit · {kind}',layout='campus',town_life=True,
                                population=300,seed=42,town_start_minutes=770,disaster_type=kind,
                                decision_mode='rules',hazard_origin=(22,33))
        warning = WarningConfig(name='Offline shelter test',text='SIMULATION: seek a suitable substantial building. Stay inside until the all-clear.',
                                delivery_reach_probability=1,notice_probability=1,action_probability=1,
                                preparation_seconds=0,channels=['mobile','siren'])
        record = CampusSimulation(config, warning).run()
        profiles = {p['id']:p for p in record['profiles']}
        runners,careful,vehicles,contacts = set(),set(),set(),set()
        for frame in record['frames']:
            occupants = []
            inventory = {v['id']:v for v in frame.get('vehicles',[])}
            for v in inventory.values():
                occupants.extend(v['occupant_ids'])
                assert len(v['occupant_ids']) <= v['capacity']
                assert math.isfinite(v.get('speed_mps',0)) and v.get('speed_mps',0) >= 0
                if v.get('state') in {'parked','waiting','yielding','dwelling','scheduled','boarding','alighting'}:
                    assert v.get('speed_mps',0) == 0, (kind,frame['time'],v['id'],v['state'],v['speed_mps'])
                if v.get('weather_response') == 'snow_caution': vehicles.add(v['id'])
            assert len(occupants) == len(set(occupants)), 'A resident occupies multiple vehicles'
            for activity in [*frame['agent_activities'],*frame.get('agent_activity_transitions',[])]:
                style = activity.get('movement_style')
                assert math.isfinite(activity.get('speed_mps',0)) and activity.get('speed_mps',0) >= 0
                if style == 'run':
                    runners.add(activity['id'])
                    profile = profiles[activity['id']]
                    assert profile['appearance'].get('mobility') != 'wheelchair'
                    assert profile['appearance'].get('age') not in {'child','older'}
                if style == 'careful': careful.add(activity['id'])
            for row in frame['agent_activities']:
                if row.get('mode') in {'riding','driving'}:
                    v = inventory[row['vehicle_id']]
                    assert row['id'] in v['occupant_ids']
                    p = next(p for p in frame['agents'] if p[0] == row['id'])
                    assert math.dist(p[1:3], [v['x'],v['y']]) < 1e-5
            for impact in frame.get('agent_impacts',[]): contacts.add(impact.get('event_id',(impact['id'],impact['started_at'])))
        assert not runners if kind == 'blizzard' else True, 'No running on snow'
        report['runs'].append({'kind':kind,'engine':record['simulation_version'],'frames':len(record['frames']),
                               'population':300,'running_residents':len(runners),'careful_residents':len(careful),
                               'snow_vehicles':len(vehicles),'contact_events':len(contacts),
                               'seconds':round(time.monotonic()-start,2),'metrics':record['metrics']})
        if not fixture.get('city'):
            fixture.update(city=record['city'],profiles=record['profiles'],art_seed=42)
        if kind == 'thunderstorm':
            case = sample_case(record,'running-to-shelter',style='run')
            assert case, 'No actual running shelter trip was recorded'
            fixture['cases'].append(case)
        if kind == 'blizzard':
            for case in (sample_case(record,'careful-snow-walking',style='careful'),sample_case(record,'snow-driving',vehicle=True)):
                assert case, 'Missing actual snow movement'
                fixture['cases'].append(case)
        print(json.dumps(report['runs'][-1]),flush=True)
    (output/'weather-behavior-e2e.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    (output/'weather-behavior-render-fixtures.json').write_text(json.dumps(fixture,separators=(',',':'),allow_nan=False))


if __name__ == '__main__':
    main()
