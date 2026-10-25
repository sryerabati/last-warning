import type {AgentImpact,MovementStyle,Point} from '../types'
import type {CharacterAppearance,CharacterMotionStyle} from './CharacterDesign'
import type {WeatherState} from './WeatherPresentation'

export interface ResidentActivityState {
  id?:number;activity?:string;mode?:string;inside?:boolean;place_id?:string|null;destination_place_id?:string|null;
  vehicle_id?:string|null;partner_ids?:number[];group_id?:string|null;walked_m?:number;
  movement_style?:MovementStyle;speed_mps?:number;weather_response?:string
}
export interface ResidentActivityChange extends ResidentActivityState {fraction:number}
export interface ResidentMotion {path:Point[];fractions:number[]}
const unit=(n:number)=>Math.max(0,Math.min(1,n))
export function endpointFacing(path:Point[]){
  for(let i=path.length-1;i>0;i--){const a=path[i-1],b=path[i]
    if(!a?.every(Number.isFinite)||!b?.every(Number.isFinite))return undefined
    const dx=b[0]-a[0],dy=b[1]-a[1]
    if(Math.hypot(dx,dy)>.00001)return Math.abs(dx)>Math.abs(dy)?dx>0?1:3:dy>0?2:0
  }
}

/** A later arrival/boarding state must never hide the person earlier in the
 * interval. Full transition snapshots replace the baseline in recorded order. */
export function activityDuring(endpoint:ResidentActivityState|undefined,previous:ResidentActivityState|undefined,changes:ResidentActivityChange[],fraction:number){
  if(fraction>=1)return endpoint
  let current=previous??endpoint
  for(const change of changes){if(change.fraction>fraction)break;current={...current,...change}}
  return current
}

/** The segment clock, not the screen-space sprite displacement, determines
 * gait speed. Stops and early arrivals therefore have zero gait immediately. */
export function residentSegment(motion:ResidentMotion|undefined,fraction:number,seconds:number,metresPerUnit:number){
  if(!motion||seconds<=0||motion.path.length<2||motion.path.length!==motion.fractions.length)return {moving:false,speed:0}
  const f=unit(fraction)
  let i=1;while(i<motion.fractions.length-1&&motion.fractions[i]<=f)i++
  const duration=(motion.fractions[i]-motion.fractions[i-1])*seconds
  const a=motion.path[i-1],b=motion.path[i],length=Math.hypot(b[0]-a[0],b[1]-a[1])*metresPerUnit
  const speed=duration>0&&Number.isFinite(length)?length/duration:0
  return {moving:speed>.015,speed:Number.isFinite(speed)?speed:0}
}

export function residentWeatherPose(input:{activity?:ResidentActivityState;appearance:Pick<CharacterAppearance,'age'|'mobility'>;moving:boolean;speed:number;weather:WeatherState|null;impact?:AgentImpact;time:number;phase:number;direction:number}){
  const {activity:a,appearance,moving,weather,impact,time,phase,direction}=input
  const wheel=appearance.mobility==='wheelchair',hidden=!!a?.inside||a?.mode==='riding'||a?.mode==='driving'
  const speed=moving?Math.max(0,input.speed):0,recorded=a?.movement_style
  const snow=weather?.active&&weather.kind==='blizzard'
  const wet=weather?.active&&(weather.kind==='thunderstorm'||weather.kind==='hailstorm')
  const urgent=recorded==='run'||a?.weather_response==='seeking_shelter'||a?.activity==='seeking shelter'
  let style:CharacterMotionStyle='walk',response='none'
  if(!hidden){
    const stoppingImpact=impact&&(impact.hazard==='tornado'||impact.kind==='knockdown')
    if(stoppingImpact||recorded==='brace'||recorded==='recover'){
      style='brace';response=stoppingImpact?'wind_impact':recorded==='recover'?'recovering':'wind_impact'
    }else if(impact&&!moving&&weather?.active){
      style='brace';response=impact.hazard==='blizzard'?'snow_caution':'storm_caution'
    }else if(recorded==='careful'||snow){style='careful';response=snow||a?.weather_response==='snow_caution'?'snow_caution':'storm_caution'}
    else if(moving&&urgent&&!wheel&&appearance.age==='adult'&&speed>=1.55){style='run';response='seeking_shelter'}
    else if(wet){style=moving?'careful':'brace';response='storm_caution'}
    else if(urgent){response='seeking_shelter'}
  }
  const pace=style==='run'?Math.min(13,Math.max(9,speed*5.4)):style==='careful'?Math.min(6,Math.max(3,speed*5)):Math.min(10,Math.max(5,speed*6))
  const gait=moving&&!hidden&&style!=='brace'
  const pose=gait?1+Math.floor(time*pace+phase*6)%6:0
  const lean=!hidden&&!wheel&&(direction===1||direction===3)?(direction===1?1:-1)*(style==='run'?.08:style==='careful'?.035:0):0
  return {style,pose,lean,response,moving:gait,speed}
}
