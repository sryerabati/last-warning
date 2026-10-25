import type {AgentImpact,Point} from '../types'
import type {WeatherState} from './WeatherPresentation'

export interface VehicleCondition {
  state?:string
  speed_mps?:number
  weather_response?:string
  occupant_ids?:number[]
  heading?:number
}
export interface VehicleStateChange extends VehicleCondition {id:string;fraction:number}
export interface VehicleImpact {
  id:string;hazard:string;kind:string;started_at:number;contact_ended_at:number|null;
  recover_until:number;position:Point;intensity:number;event_id?:number
}
export interface VehiclePath {path:Point[];fractions:number[]}

const unit=(n:number)=>Math.max(0,Math.min(1,n))

/** Endpoint state must not leak into the preceding trip. New recordings supply
 * exact subframe changes; older ones keep their known prior state until arrival. */
export function vehicleConditionAt(final:VehicleCondition,previous:VehicleCondition|undefined,changes:VehicleStateChange[],fraction:number):VehicleCondition {
  if(fraction>=1)return final
  let current:VehicleCondition=previous??final
  for(const change of changes){
    if(!Number.isFinite(change.fraction)||change.fraction<0||change.fraction>1)continue
    if(change.fraction>fraction)break
    current={...current,...change}
  }
  return current
}

/** The path, including repeated positions while yielding, is the speed source.
 * Never slow the renderer independently of the recorded physical simulation. */
export function vehicleMotionAt(motion:VehiclePath|undefined,fraction:number,intervalSeconds:number,metersPerUnit:number){
  if(!motion||motion.path.length<2||motion.path.length!==motion.fractions.length||
    motion.fractions[0]!==0||motion.fractions.at(-1)!==1||
    !motion.path.every((p,i)=>p.length===2&&p.every(Number.isFinite)&&Number.isFinite(motion.fractions[i])&&(!i||motion.fractions[i]>motion.fractions[i-1])))return null
  let i=1;while(i<motion.fractions.length-1&&motion.fractions[i]<=fraction)i++
  const a=motion.path[i-1],b=motion.path[i],portion=unit((fraction-motion.fractions[i-1])/(motion.fractions[i]-motion.fractions[i-1]))
  const dx=b[0]-a[0],dy=b[1]-a[1],distance=Math.hypot(dx,dy)
  const seconds=intervalSeconds*(motion.fractions[i]-motion.fractions[i-1])
  let heading:number|null=distance>.00001?Math.atan2(dy,dx):null
  if(heading===null)for(let k=i-1;k>0;k--){const before=motion.path[k-1],after=motion.path[k];if(Math.hypot(after[0]-before[0],after[1]-before[1])>.00001){heading=Math.atan2(after[1]-before[1],after[0]-before[0]);break}}
  return {point:[a[0]+dx*portion,a[1]+dy*portion] as Point,heading,
    moving:distance>.00001,speed:seconds>0?distance*metersPerUnit/seconds:0,
    traversed:distance*portion,start:a}
}

/** Prefer vehicle contact records, including empty operating buses. Legacy
 * occupant contacts are accepted only while they belong to this vehicle. */
export function vehicleImpactAt(events:VehicleImpact[],legacy:AgentImpact[],id:string,occupants:number[],seconds:number){
  const visible=(event:{started_at:number;recover_until:number})=>Number.isFinite(event.started_at)&&seconds>=event.started_at&&seconds<event.recover_until
  const direct=events.filter(event=>event.id===id&&visible(event)).sort((a,b)=>b.started_at-a.started_at)[0]
  if(direct)return direct
  const fallback=legacy.filter(event=>{
    const vehicleId=(event as AgentImpact&{vehicle_id?:string|null}).vehicle_id
    return event.hazard==='tornado'&&event.kind==='brace'&&visible(event)&&
      (vehicleId!=null?vehicleId===id:occupants.includes(event.id))
  }).sort((a,b)=>b.started_at-a.started_at)[0]
  return fallback?{...fallback,id}:undefined
}

export function vehicleWeatherPose(weather:WeatherState|null,condition:VehicleCondition,speed:number,moving:boolean,seconds:number,animationTime:number,reduced:boolean,night:number,impact?:VehicleImpact){
  const active=!!weather?.active,snow=weather?.kind==='blizzard',storm=weather?.kind==='thunderstorm'||weather?.kind==='hailstorm'
  const exposedWeather=active&&(snow||storm),snowCover=snow?(weather?.snowCover??0):0
  const age=impact?Math.max(0,seconds-impact.started_at):0
  const contactEnd=impact?.contact_ended_at
  const recovery=impact&&contactEnd!=null?unit((seconds-contactEnd)/Math.max(.001,impact.recover_until-contactEnd)):0
  const impactAmount=impact?unit(age/.3)*(1-recovery):0
  const rotation=impactAmount*(reduced?.018:Math.sin(age*7.5)*.055)
  const braking=!!impact||condition.state==='yielding'||(!moving&&speed<.1&&condition.state==='driving')
  const hazardLights=!!impact&&(reduced||Math.floor(animationTime*2)%2===0)
  return {headlights:night>.15||exposedWeather||!!impact,braking,hazardLights,rotation,impactAmount,
    dust:impact?unit(1-age/1.2):0,wipers:exposedWeather,
    wiperPhase:reduced?.5:(Math.sin(animationTime*5)+1)/2,
    snowCover,snowTracks:snowCover>.04&&moving,
    spray:active&&storm&&moving&&speed>.1}
}
