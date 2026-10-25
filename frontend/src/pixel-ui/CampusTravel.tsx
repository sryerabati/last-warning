import type {Frame,Point} from '../types'
import {PixelIcon} from './PixelIcon'
import './CampusTravel.css'

export function CampusTravel({frame,onLocate,onResident,nameOf}:{frame?:Frame;onLocate:(point:Point)=>void;onResident:(id:number)=>void;nameOf:(id:number)=>string}){
  const transit=frame?.transit,buses=frame?.vehicles?.filter(v=>v.type==='bus')??[]
  if(!transit)return <p className="muted">This recording has no campus shuttle service. New campus days include scheduled travel.</p>
  return <div className="campus-travel">
    <h3>{transit.route_name??'Campus shuttle'}</h3>
    <p className="muted">{transit.service_active?'Service is running. Residents walk to a stop, wait for a seat, ride and continue on foot.':String(transit.suspended_reason??'No scheduled service at this time.')}</p>
    <dl className="metric-details"><div><dt>Waiting at stops</dt><dd>{Number(transit.waiting??0)}</dd></div><div><dt>Completed rides</dt><dd>{Number(transit.completed_trips??0)}</dd></div><div><dt>On board</dt><dd>{buses.reduce((n,b)=>n+(b.occupant_ids?.length??0),0)}</dd></div></dl>
    {buses.filter(b=>b.service_active).map(bus=><details className="travel-vehicle details-block" key={bus.id} open>
      <summary><PixelIcon name="bus" size={18}/>{`Shuttle ${String(bus.id).split('-').at(-1)}`} <span>{bus.occupant_ids?.length??0}/{bus.capacity??40}</span></summary>
      <p>{bus.state==='dwelling'?'At stop':bus.state==='yielding'?'Yielding':'Next stop'} · {String(bus.next_stop_name??'Campus route')}</p>
      <button className="text-button" onClick={()=>onLocate([bus.x,bus.y])}><PixelIcon name="pin" size={14}/>Find shuttle</button>
      {!!bus.occupant_ids?.length&&<div className="travel-passengers">{bus.occupant_ids.map(id=><button className="text-button" key={id} onClick={()=>onResident(id)}>{nameOf(id)}</button>)}</div>}
    </details>)}
    <h3>Stops</h3><div className="travel-stops">{(frame?.bus_stops??[]).map(stop=><button key={stop.id} onClick={()=>onLocate(stop.position)}><PixelIcon name="bus" size={17}/><span title={stop.name}>{stop.name.includes('Temporary Stop')?'12th Avenue · temporary westbound stop':stop.name}<small>{stop.waiting_count?`${stop.waiting_count} waiting`:'No queue'}</small></span><PixelIcon name="chevron-right" size={12}/></button>)}</div>
    {frame?.traffic&&<details className="details-block"><summary>Crossings & queues</summary><dl className="metric-details">{Object.entries({waiting_pedestrians:'People waiting to cross',yielding_vehicles:'Vehicles yielding',queued_vehicles:'Vehicles queued',crossing_count:'Mapped crossings',wait_events:'Recorded waits'}).map(([key,label])=>typeof frame.traffic?.[key]==='number'?<div key={key}><dt>{label}</dt><dd>{frame.traffic[key]}</dd></div>:null)}</dl></details>}
    <details className="details-block"><summary>About this service</summary><p className="muted">A bounded educational shuttle on the College Connector corridor, using mapped campus stops and roads. It is not the complete current CABS route. Capacity and traffic behavior are authored simulation settings.</p><a href="https://ttm.osu.edu/cabs" target="_blank" rel="noreferrer">Official CABS service information ↗</a></details>
  </div>
}
