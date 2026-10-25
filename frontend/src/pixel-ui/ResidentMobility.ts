import type {AgentActivity,ResidentProfile} from '../types'

const responses:Record<string,string>={
  snow_caution:'Slower travel on snow',storm_caution:'Slower travel in the storm',
  wind_impact:'Stopped by wind impact',recovering:'Recovering from wind impact',
  urgent_shelter:'Hurrying to shelter',seeking_shelter:'Heading to shelter',
}
/** These readouts describe saved movement, not the resident's usual walking pace. */
export function residentMobility(activity:AgentActivity|undefined,profile:Pick<ResidentProfile,'appearance'>){
  if(!activity)return null
  const wheelchair=profile.appearance?.mobility==='wheelchair',mode=activity.mode??''
  const riding=mode==='riding'||mode==='driving'
  const style=activity.movement_style
  const label=activity.inside?'Inside':riding?(mode==='driving'?'Driving':'Riding'):
    style==='brace'?'Bracing':style==='recover'?'Recovering':style==='careful'?(wheelchair?'Moving carefully':'Careful steps'):
    style==='run'?(wheelchair?'Moving to shelter':'Running'):mode==='walking'?(activity.speed_mps===0?'Waiting':wheelchair?'Rolling':'Walking'):mode.replaceAll('_',' ')
  const speed=activity.speed_mps
  return {label,speed:typeof speed==='number'&&Number.isFinite(speed)&&speed>=0?`${speed.toFixed(1)} m/s`:null,
    response:!activity.inside&&activity.weather_response?responses[activity.weather_response]??null:null}
}
