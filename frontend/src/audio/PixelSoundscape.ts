import type {DisasterType} from '../types'

export type SoundCue='select'|'confirm'|'error'|'broadcast'|'arrival'
export type WorldSoundState={playing:boolean;hazardActive:boolean;disasterType:DisasterType}
type Voice={source:AudioScheduledSourceNode;nodes:AudioNode[];end:number}
const MASTER=.09,MAX_VOICES=12

/** Original, quiet Web Audio synthesis. No samples, network requests or sirens. */
export class PixelSoundscape {
  readonly context:AudioContext
  private master:GainNode
  private ambience:GainNode
  private ambienceFilter:BiquadFilterNode
  private rumble:GainNode
  private flightWind:GainNode
  private flightFilter:BiquadFilterNode
  private flightTone:OscillatorNode
  private flightToneGain:GainNode
  private noiseBuffer:AudioBuffer
  private loops:AudioScheduledSourceNode[]=[]
  private nodes:AudioNode[]=[]
  private voices=new Set<Voice>()
  private cooldowns=new Map<string,number>()
  private world:WorldSoundState={playing:false,hazardActive:false,disasterType:'flood'}
  private flightProgress:number|null=null
  private visible=true
  private muted=true
  private disposed=false
  private idle:ReturnType<typeof setTimeout>|undefined
  private lastFlightUpdate=-Infinity

  constructor(context:AudioContext=new AudioContext(),private wallClock:()=>number=()=>performance.now()/1000) {
    this.context=context
    this.master=context.createGain();this.master.gain.value=0;this.master.connect(context.destination)
    this.noiseBuffer=context.createBuffer(1,Math.round(context.sampleRate*4),context.sampleRate)
    const samples=this.noiseBuffer.getChannelData(0)
    let seed=85471,smooth=0
    for(let i=0;i<samples.length;i++){
      seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5
      smooth=.93*smooth+.07*((seed>>>0)/2147483648-1);samples[i]=smooth
    }
    const noise=context.createBufferSource();noise.buffer=this.noiseBuffer;noise.loop=true
    this.ambienceFilter=context.createBiquadFilter();this.ambienceFilter.type='lowpass';this.ambienceFilter.frequency.value=600
    this.ambience=context.createGain();this.ambience.gain.value=0
    noise.connect(this.ambienceFilter).connect(this.ambience).connect(this.master)
    const bass=context.createOscillator();bass.type='sine';bass.frequency.value=47
    this.rumble=context.createGain();this.rumble.gain.value=0;bass.connect(this.rumble).connect(this.master)
    this.flightFilter=context.createBiquadFilter();this.flightFilter.type='bandpass';this.flightFilter.Q.value=.6
    this.flightWind=context.createGain();this.flightWind.gain.value=0
    noise.connect(this.flightFilter).connect(this.flightWind).connect(this.master)
    this.flightTone=context.createOscillator();this.flightTone.type='triangle';this.flightTone.frequency.value=72
    this.flightToneGain=context.createGain();this.flightToneGain.gain.value=0
    this.flightTone.connect(this.flightToneGain).connect(this.master)
    this.loops=[noise,bass,this.flightTone]
    this.nodes=[noise,bass,this.flightTone,this.master,this.ambienceFilter,this.ambience,this.rumble,this.flightFilter,this.flightWind,this.flightToneGain]
    this.loops.forEach(source=>source.start())
  }

  async unlock(){
    if(this.disposed)return false
    await this.context.resume()
    return !this.disposed&&this.context.state==='running'
  }
  private target(param:AudioParam,value:number,smoothing=.08){
    const now=this.context.currentTime
    param.cancelScheduledValues(now);param.setTargetAtTime(value,now,smoothing)
  }
  private wake(){
    clearTimeout(this.idle);this.idle=undefined
    if(this.context.state==='suspended')void this.context.resume().catch(()=>{})
  }
  private scheduleIdle(){
    clearTimeout(this.idle)
    if(this.disposed||(!this.muted&&this.visible&&(this.world.playing||this.flightProgress!==null)))return
    const remaining=Math.max(0,...[...this.voices].map(v=>v.end-this.context.currentTime))
    this.idle=setTimeout(()=>{if(!this.disposed)void this.context.suspend().catch(()=>{})},Math.max(350,remaining*1000+150))
  }
  private updateMix(){
    if(this.disposed)return
    const audible=!this.muted&&this.visible,ambient=audible&&this.world.playing&&this.flightProgress===null
    this.target(this.master.gain,audible?MASTER:0,.035)
    const storm=this.world.hazardActive
    const filters:Record<DisasterType,number>={flood:580,wildfire:1450,tornado:260,blizzard:380,hailstorm:1250,thunderstorm:850,public_safety:500}
    this.target(this.ambienceFilter.frequency,filters[this.world.disasterType],.18)
    this.target(this.ambience.gain,ambient?(storm?.38:.13):0,.16)
    this.target(this.rumble.gain,ambient&&storm&&(this.world.disasterType==='tornado'||this.world.disasterType==='thunderstorm')?.035:0,.2)
    const progress=this.flightProgress,envelope=audible&&progress!==null&&progress>0&&progress<1?Math.sin(Math.PI*progress):0
    this.target(this.flightWind.gain,envelope*.62,.07)
    this.target(this.flightToneGain.gain,envelope*.025,.07)
    if(progress!==null){this.target(this.flightFilter.frequency,180+2500*progress,.06);this.target(this.flightTone.frequency,72*Math.pow(2,progress*2),.06)}
    if(audible&&(this.world.playing||progress!==null))this.wake();else this.scheduleIdle()
  }
  setWorld(state:WorldSoundState){this.world=state;this.updateMix()}
  setFlight(progress:number|null){
    if(this.disposed)return
    const next=progress===null?null:Math.max(0,Math.min(1,Number.isFinite(progress)?progress:0))
    // Frequent animation updates need only a small number of audio automation events.
    const now=this.context.currentTime
    if(next!==null&&this.flightProgress!==null&&now-this.lastFlightUpdate<.03)return
    this.flightProgress=next;this.lastFlightUpdate=now;this.updateMix()
  }
  setMuted(value:boolean){
    this.muted=value
    if(value){this.stopVoices();this.cooldowns.clear()}
    this.updateMix()
  }
  setVisible(value:boolean){
    this.visible=value
    if(!value)this.stopVoices()
    this.updateMix()
  }
  private allowed(key:string,interval:number){
    if(this.disposed||this.muted||!this.visible)return false
    // AudioContext time freezes during idle suspension; use wall time so a
    // later click can wake a paused world instead of remaining rate-limited.
    const now=this.wallClock(),previous=this.cooldowns.get(key)??-Infinity
    if(now-previous<interval)return false
    this.cooldowns.set(key,now);this.wake();return true
  }
  private track(source:AudioScheduledSourceNode,nodes:AudioNode[],end:number){
    while(this.voices.size>=MAX_VOICES)this.release(this.voices.values().next().value!,true)
    const voice={source,nodes,end};this.voices.add(voice)
    source.onended=()=>this.release(voice,false)
    return voice
  }
  private release(voice:Voice,stop:boolean){
    if(!this.voices.delete(voice))return
    voice.source.onended=null
    if(stop){try{voice.source.stop()}catch{/* Already ended. */}}
    voice.nodes.forEach(node=>node.disconnect())
  }
  private stopVoices(){for(const voice of [...this.voices])this.release(voice,true)}
  private tone(frequency:number,offset:number,duration:number,level:number,type:OscillatorType='sine'){
    const context=this.context,start=context.currentTime+offset,tone=context.createOscillator(),gain=context.createGain()
    tone.type=type;tone.frequency.value=frequency
    gain.gain.setValueAtTime(0,start);gain.gain.linearRampToValueAtTime(level,start+.012);gain.gain.exponentialRampToValueAtTime(.0001,start+duration)
    tone.connect(gain).connect(this.master);this.track(tone,[tone,gain],start+duration+.03)
    tone.start(start);tone.stop(start+duration+.03)
  }
  private noiseBurst(offset:number,duration:number,frequency:number,level:number,type:BiquadFilterType='lowpass'){
    const c=this.context,start=c.currentTime+offset,source=c.createBufferSource(),filter=c.createBiquadFilter(),gain=c.createGain()
    source.buffer=this.noiseBuffer;filter.type=type;filter.frequency.value=frequency;filter.Q.value=.5
    gain.gain.setValueAtTime(0,start);gain.gain.linearRampToValueAtTime(level,start+Math.min(.05,duration/5));gain.gain.exponentialRampToValueAtTime(.0001,start+duration)
    source.connect(filter).connect(gain).connect(this.master);this.track(source,[source,filter,gain],start+duration+.03)
    source.start(start,1);source.stop(start+duration+.03)
  }
  cue(cue:SoundCue){
    if(!this.allowed(cue,cue==='select'?.10:cue==='error'?.7:.35))return
    switch(cue){
      case 'select':this.tone(740,0,.06,.10,'triangle');break
      case 'confirm':this.tone(523.25,0,.12,.12);this.tone(783.99,.07,.16,.10);break
      case 'error':this.tone(293.66,0,.14,.11,'triangle');this.tone(261.63,.10,.2,.08,'triangle');break
      case 'broadcast':this.tone(523.25,0,.25,.16);this.tone(659.25,.16,.3,.14);break
      case 'arrival':this.tone(392,0,.34,.10);this.tone(523.25,.09,.42,.12);this.tone(659.25,.18,.48,.08);break
    }
    this.scheduleIdle()
  }
  weather(type:DisasterType){
    if(!this.allowed('weather',2.8))return
    if(type==='thunderstorm'){this.noiseBurst(0,1.35,180,.46);this.tone(56,.08,.85,.045)}
    else if(type==='hailstorm'){for(let i=0;i<3;i++)this.noiseBurst(i*.105,.07,1900,.18,'highpass')}
    else if(type==='blizzard'||type==='tornado')this.noiseBurst(0,1.1,type==='blizzard'?650:320,.25,'bandpass')
    else if(type==='wildfire'){this.noiseBurst(0,.055,1400,.12,'highpass');this.noiseBurst(.17,.04,1900,.09,'highpass')}
    // Flood uses the continuous water texture; restricted-area scenarios never
    // synthesize weapons, crowds in distress, or an operational alarm.
    this.scheduleIdle()
  }
  dispose(){
    if(this.disposed)return;this.disposed=true;clearTimeout(this.idle);this.stopVoices()
    this.loops.forEach(source=>{try{source.stop()}catch{/* Already stopped. */}})
    this.nodes.forEach(node=>node.disconnect());void this.context.close().catch(()=>{})
  }
}
