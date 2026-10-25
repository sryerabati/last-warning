import type {DisasterType,Frame} from '../types'

export const clamp01=(n:number)=>Math.max(0,Math.min(1,n))
const finite=(value:unknown,fallback=0)=>typeof value==='number'&&Number.isFinite(value)?value:fallback

/** Physical weather state comes from the recording. Surface coverage is an
 * illustrative treatment, not a snow-depth or damage calculation. */
export function weatherAt(frame:Frame,previous:Frame|null,fraction=1){
  const h=frame.hazard,kind=h?.type
  const interval=Math.max(0,finite(frame.interval_seconds,previous?frame.time-previous.time:0))
  const seconds=Math.max(0,frame.time-interval*(1-clamp01(fraction)))
  const motion=frame.hazard_motion
  const active=fraction>=1&&typeof h?.active==='boolean'?h.active:motion&&'active_from' in motion
    ?motion.active_from!=null&&motion.active_until!=null&&fraction>=motion.active_from&&fraction<=motion.active_until
    :typeof h?.active==='boolean'?h.active:(frame.active_hazard_cells??frame.hazard_cells).length>0
  const storm=kind==='thunderstorm'||kind==='hailstorm',snow=kind==='blizzard',tornado=kind==='tornado'
  const conditions=active&&h?.active===false&&previous?.hazard?.active===true?previous.hazard:h
  const endThunder=finite(h?.last_thunder_seconds,-1),previousThunder=finite(previous?.hazard?.last_thunder_seconds,-1)
  const thunder=endThunder<=seconds?endThunder:previousThunder<=seconds?previousThunder:-1
  const qualifying=finite(h?.qualifying_blizzard_seconds,snow&&active?frame.time:0)
  const snowSeconds=Math.max(0,Math.min(seconds,qualifying))
  const snowCover=snow?Math.pow(clamp01(snowSeconds/5400),.68):0
  const approaching=h?.phase==='approaching'&&!active
  const stormCloud=storm?(active?1:approaching?clamp01(seconds/120)*.55:clamp01(1-(seconds-Math.max(0,thunder))/1800)*.45):0
  const wetness=storm?(active?1:thunder>=0?clamp01(1-(seconds-thunder)/1800)*.65:0):0
  return {kind:kind as DisasterType|undefined,seconds,active,snowCover,wetness,thunder,
    rain:storm&&active?1:0,hail:active&&(kind==='hailstorm'||finite(conditions?.hail_inches)>0),
    snowfall:snow&&active?1:0,cloud:stormCloud,
    wind:active&&(storm||snow||tornado)?1:0,
    visibility:snow&&active?clamp01(1-finite(conditions?.visibility_miles,10)/.5):0,
    direction:h?.wind??[1,-.25]}
}
export type WeatherState=ReturnType<typeof weatherAt>

/** Bright accents are limited by presentation time, even at 16× replay.
 * Direct seeks don't replay a thunderclap or flash; reduced motion never flashes. */
export class LightningCue {
  private seen=-1
  private started=-100
  private last=-100
  private event=-1
  reset(event:number){this.seen=event;this.started=-100;this.event=-1}
  sample(event:number,time:number,animate:boolean,reduced:boolean){
    if(event>=0&&event!==this.seen){
      this.seen=event
      if(animate&&!reduced&&time-this.last>=5){this.started=time;this.last=time;this.event=event}
    }
    const age=time-this.started,amount=!reduced&&age>=0&&age<.85?Math.pow(1-age/.85,2):0
    return {amount,event:this.event}
  }
}
