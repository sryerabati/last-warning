import {useCallback,useEffect,useRef,useState} from 'react'
import type {DisasterType} from '../types'
import {PixelSoundscape,type SoundCue} from './PixelSoundscape'
import {adjacentAudioAdvance,eventDelayMs,weatherAudioEvent} from './AudioTimeline'

type Options={playing:boolean;time:number;tick?:number;runId?:string;disasterType:DisasterType;hazardActive:boolean;warningTickSeconds?:number;lastThunderSeconds?:number|null;frameDurationMs?:number}
const PREFERENCE='last-warning-sound/v1'
export function readSoundPreference(){try{return localStorage.getItem(PREFERENCE)!=='off'}catch{return true}}
function save(value:boolean){try{localStorage.setItem(PREFERENCE,value?'on':'off')}catch{/* Storage can be unavailable. */}}

/** Sound defaults on unless explicitly muted. Audio still waits for a real user
 * gesture before creating/resuming AudioContext, including on the first opening. */
export function useWorldAudio({playing,time,tick,runId,disasterType,hazardActive,warningTickSeconds=0,lastThunderSeconds,frameDurationMs=250}:Options){
  const [enabled,setEnabled]=useState(readSoundPreference),[unavailable,setUnavailable]=useState(false)
  const enabledRef=useRef(enabled),mounted=useRef(true),mix=useRef<PixelSoundscape|null>(null),flightProgress=useRef<number|null>(null)
  const desired=useRef({playing,hazardActive,disasterType});desired.current={playing,hazardActive,disasterType}
  const previous=useRef({runId,time,tick,playing}),playedWarning=useRef<string|undefined>(undefined)
  const weatherSlot=useRef<string|undefined>(undefined)

  const activate=useCallback(async()=>{
    if(!enabledRef.current||!mounted.current)return
    try {
      mix.current??=new PixelSoundscape()
      const current=mix.current
      current.setVisible(!document.hidden);current.setMuted(false);current.setWorld(desired.current);current.setFlight(flightProgress.current)
      const running=await current.unlock()
      if(!mounted.current||!enabledRef.current||mix.current!==current)return
      if(!running){enabledRef.current=false;setEnabled(false);save(false);current.setMuted(true)}
      else setUnavailable(false)
    }catch{
      if(!mounted.current)return
      mix.current?.setMuted(true);enabledRef.current=false;setEnabled(false);save(false)
      setUnavailable(typeof AudioContext==='undefined')
    }
  },[])
  const toggle=useCallback(async()=>{
    if(enabledRef.current){enabledRef.current=false;setEnabled(false);save(false);mix.current?.setMuted(true);return}
    enabledRef.current=true;setEnabled(true);save(true)
    await activate()
    if(enabledRef.current)mix.current?.cue('confirm')
  },[activate])
  const cue=useCallback((value:SoundCue)=>{if(enabledRef.current)mix.current?.cue(value)},[])
  const flight=useCallback((progress:number|null)=>{
    flightProgress.current=progress
    if(enabledRef.current)mix.current?.setFlight(progress)
  },[])

  useEffect(()=>{
    mounted.current=true
    if(typeof AudioContext==='undefined')setUnavailable(true)
    const unlock=(event:Event)=>{
      if(event.isTrusted&&enabledRef.current&&!mix.current)void activate()
    }
    const visibility=()=>mix.current?.setVisible(!document.hidden)
    document.addEventListener('pointerdown',unlock,{capture:true})
    document.addEventListener('keydown',unlock,{capture:true})
    document.addEventListener('visibilitychange',visibility)
    return()=>{
      mounted.current=false
      document.removeEventListener('pointerdown',unlock,true);document.removeEventListener('keydown',unlock,true);document.removeEventListener('visibilitychange',visibility)
      mix.current?.dispose();mix.current=null
    }
  },[activate])
  useEffect(()=>{mix.current?.setWorld({playing,hazardActive,disasterType})},[playing,hazardActive,disasterType])
  useEffect(()=>{
    const before=previous.current,after={runId,time,tick,playing},changed=runId!==before.runId
    if(changed){playedWarning.current=undefined;weatherSlot.current=undefined}
    const timers:ReturnType<typeof setTimeout>[]=[]
    const schedule=(delay:number,play:()=>void)=>{
      if(delay===0)play()
      else timers.push(setTimeout(()=>{if(enabledRef.current&&desired.current.playing)play()},delay))
    }
    const beginning=(!before.playing||changed)&&time===0&&warningTickSeconds===0
    const adjacent=adjacentAudioAdvance(before,after)
    const crossing=adjacent&&before.time<warningTickSeconds&&time>=warningTickSeconds
    if(mix.current&&enabledRef.current&&playing&&runId&&(beginning||crossing)&&playedWarning.current!==runId){
      schedule(crossing?eventDelayMs(warningTickSeconds,before,after,frameDurationMs):0,()=>mix.current?.cue('broadcast'))
      playedWarning.current=runId
    }
    // Recorded frame adjacency works for 5s, 30s and 120s output alike. The
    // thunder cue follows saved event time within this interpolated interval;
    // loading, pausing or seeking never starts a historical storm sound.
    const weather=weatherAudioEvent(before,after,disasterType,hazardActive,lastThunderSeconds,frameDurationMs)
    if(mix.current&&enabledRef.current&&weather&&weather.key!==weatherSlot.current){
      schedule(weather.delayMs,()=>mix.current?.weather(weather.sound));weatherSlot.current=weather.key
    }
    previous.current=after
    return()=>timers.forEach(clearTimeout)
  },[time,tick,runId,playing,hazardActive,disasterType,warningTickSeconds,lastThunderSeconds,frameDurationMs])
  return {enabled,toggle,unavailable,cue,flight}
}
