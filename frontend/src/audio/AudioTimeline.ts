import type {DisasterType} from '../types'

export interface AudioFrame {
  runId?:string;tick?:number;time:number;playing:boolean
}
export function adjacentAudioAdvance(before:AudioFrame,after:AudioFrame){
  return !!after.runId&&before.runId===after.runId&&before.playing&&after.playing&&
    Number.isFinite(before.tick)&&Number.isFinite(after.tick)&&after.tick===before.tick!+1&&after.time>before.time
}
export function eventDelayMs(seconds:number,before:AudioFrame,after:AudioFrame,frameDurationMs:number){
  const fraction=Math.max(0,Math.min(1,(seconds-before.time)/(after.time-before.time||1)))
  // Leave one browser frame before the next state update cancels the timer.
  return Math.max(0,fraction*Math.max(16,frameDurationMs)-16)
}
export function weatherAudioEvent(before:AudioFrame,after:AudioFrame,type:DisasterType,active:boolean,lastThunderSeconds:number|null|undefined,frameDurationMs:number){
  if(!adjacentAudioAdvance(before,after))return null
  if((type==='thunderstorm'||type==='hailstorm')&&lastThunderSeconds!=null&&Number.isFinite(lastThunderSeconds)&&lastThunderSeconds>before.time&&lastThunderSeconds<=after.time){
    return {key:`${after.runId}:thunder:${lastThunderSeconds}`,sound:'thunderstorm' as DisasterType,
      delayMs:eventDelayMs(lastThunderSeconds,before,after,frameDurationMs)}
  }
  // New storm recordings only thunder on a saved thunder event. Legacy storms
  // without this field keep their sparse accent; ambient rain remains separate.
  if(type==='thunderstorm'&&lastThunderSeconds!==undefined)return null
  if(!active||type==='public_safety'||type==='flood')return null
  return {key:`${after.runId}:weather:${Math.floor(after.time/35)}`,sound:type,delayMs:0}
}
