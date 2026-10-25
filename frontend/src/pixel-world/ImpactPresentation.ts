import type {AgentImpact,Frame,Point} from '../types'

const unit=(n:number)=>Math.max(0,Math.min(1,n))
const ease=(n:number)=>{const t=unit(n);return t*t*(3-2*t)}

/** Presentation follows saved contact seconds; paused frames and seeking never
 * replay a wall-clock effect or invent a new physical position. */
export function impactAt(impacts:AgentImpact[],seconds:number){
  return impacts.filter(e=>Number.isFinite(e.started_at)&&seconds>=e.started_at&&seconds<e.recover_until)
    .sort((a,b)=>b.started_at-a.started_at)[0]
}
export function impactPose(event:AgentImpact,seconds:number,wheelchair=false){
  const age=Math.max(0,seconds-event.started_at),end=event.contact_ended_at
  const recovery=end===null?0:unit((seconds-end)/Math.max(.001,event.recover_until-end))
  const settle=ease(age/.65),rise=1-ease((recovery-.55)/.45),amount=settle*rise
  const side=event.id%2?1:-1,down=event.kind==='knockdown'&&!wheelchair
  return {rotation:wheelchair?0:side*(down?1.22:.16)*amount,scaleY:wheelchair?1:1-(down?.13:.18)*amount,
    offsetY:wheelchair?0:(down?2:3)*amount,dust:unit(1-age/1.7),amount,
    stage:recovery>.55?'recovering':down?'knocked down':'bracing'}
}

export function pointAlong(path:Point[],fractions:number[],fraction:number):Point|undefined{
  if(path.length<2||path.length!==fractions.length||fractions[0]!==0||fractions.at(-1)!==1||
    !path.every((p,i)=>p.length===2&&p.every(Number.isFinite)&&Number.isFinite(fractions[i])&&(!i||fractions[i]>fractions[i-1])))return
  let i=1;while(i<fractions.length-1&&fractions[i]<fraction)i++
  const t=unit((fraction-fractions[i-1])/(fractions[i]-fractions[i-1])),a=path[i-1],b=path[i]
  return [a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t]
}

export function hazardAt(frame:Frame,previousCenter:Point|null,fraction:number){
  const center=frame.hazard?.center
  if(!center)return {active:false,center:[0,0] as Point}
  const motion=frame.hazard_motion,point=motion?pointAlong(motion.path,motion.fractions,fraction):undefined
  const active=fraction>=1&&typeof frame.hazard?.active==='boolean'?frame.hazard.active:motion&&'active_from' in motion?motion.active_from!=null&&motion.active_until!=null&&fraction>=motion.active_from&&fraction<=motion.active_until:typeof frame.hazard?.active==='boolean'?frame.hazard.active:frame.hazard?.started!==false&&(frame.active_hazard_cells??frame.hazard_cells).length>0
  return {active,center:point??(previousCenter?[previousCenter[0]+(center[0]-previousCenter[0])*fraction,previousCenter[1]+(center[1]-previousCenter[1])*fraction] as Point:center)}
}
