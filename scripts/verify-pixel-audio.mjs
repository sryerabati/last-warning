#!/usr/bin/env node
// Exercise the actual synthesizer's gesture gating, envelopes, limits and lifecycle.
import assert from 'node:assert/strict'
import {test} from 'node:test'
import {fileURLToPath} from 'node:url'
import {build} from '../frontend/node_modules/esbuild/lib/main.js'
const compiled=await build({entryPoints:[fileURLToPath(new URL('../frontend/src/audio/PixelSoundscape.ts',import.meta.url))],bundle:true,platform:'node',format:'esm',write:false,logLevel:'silent'})
const {PixelSoundscape}=await import(`data:text/javascript;base64,${Buffer.from(compiled.outputFiles[0].text).toString('base64')}`)
class Param {
  value=0;events=[]
  cancelScheduledValues(time){this.events.push(['cancel',time])}
  setValueAtTime(value,time){this.value=value;this.events.push(['value',value,time])}
  setTargetAtTime(value,time,smoothing){this.value=value;this.events.push(['target',value,time,smoothing])}
  linearRampToValueAtTime(value,time){this.events.push(['linear',value,time])}
  exponentialRampToValueAtTime(value,time){this.events.push(['exponential',value,time])}
}
class Node {
  connections=[];disconnected=false
  connect(other){this.connections.push(other);return other}
  disconnect(){this.connections=[];this.disconnected=true}
}
class Source extends Node {
  starts=[];stops=[];onended=null;frequency=new Param()
  start(...args){this.starts.push(args)}
  stop(...args){this.stops.push(args)}
}
class Context {
  currentTime=0;sampleRate=8000;state='suspended';destination=new Node();nodes=[];resumes=0
  add(node){this.nodes.push(node);return node}
  createGain(){return this.add(Object.assign(new Node(),{gain:new Param()}))}
  createBiquadFilter(){return this.add(Object.assign(new Node(),{frequency:new Param(),Q:new Param()}))}
  createOscillator(){return this.add(new Source())}
  createBufferSource(){return this.add(new Source())}
  createBuffer(_channels,length){const data=new Float32Array(length);return {getChannelData:()=>data}}
  async resume(){this.resumes++;this.state='running'}
  async suspend(){this.state='suspended'}
  async close(){this.state='closed'}
}
function fixture(){const context=new Context(),engine=new PixelSoundscape(context,()=>context.currentTime);return {context,engine}}
function audible(f){f.engine.setMuted(false);f.context.state='running'}

test('new sound engine is silent and does not resume itself before gesture activation',()=>{
  const f=fixture();assert.equal(f.engine.master.gain.value,0);assert.equal(f.context.resumes,0)
  f.engine.cue('broadcast');f.engine.setFlight(.5)
  assert.equal(f.engine.voices.size,0);assert.equal(f.engine.flightWind.gain.value,0)
  f.engine.dispose()
})
test('paused simulation can play UI cues, with a quiet bounded master envelope',async()=>{
  const f=fixture();audible(f);await f.engine.unlock()
  f.engine.setWorld({playing:false,hazardActive:false,disasterType:'flood'});f.engine.cue('select')
  assert.equal(f.engine.voices.size,1);assert.equal(f.engine.ambience.gain.value,0)
  assert.ok(f.engine.master.gain.value>0&&f.engine.master.gain.value<=.1)
  const voice=[...f.engine.voices][0]
  assert.equal(voice.source.starts.length,1);assert.equal(voice.source.stops.length,1)
  assert.ok(voice.end-f.context.currentTime<.2);f.engine.dispose()
})
test('UI repeats are throttled, all transient voices have scheduled stops and clean up',()=>{
  const f=fixture();audible(f)
  for(let i=0;i<100;i++)f.engine.cue('select')
  assert.equal(f.engine.voices.size,1)
  for(let i=0;i<25;i++){f.context.currentTime+=.4;f.engine.cue('arrival')}
  assert.ok(f.engine.voices.size<=12)
  for(const voice of [...f.engine.voices]){
    assert.ok(voice.source.stops.length>0);const nodes=[...voice.nodes];voice.source.onended()
    assert.ok(nodes.every(node=>node.disconnected))
  }
  assert.equal(f.engine.voices.size,0);f.engine.dispose()
})
test('flight wind is separate from paused ambience and clamps all progress inputs',()=>{
  const f=fixture();audible(f);f.engine.setFlight(.5)
  assert.ok(f.engine.flightWind.gain.value>0);assert.equal(f.engine.ambience.gain.value,0)
  for(const value of [1,NaN,-10,100]){
    f.context.currentTime+=.1;f.engine.setFlight(value)
    assert.equal(f.engine.flightWind.gain.value,0)
  }
  f.context.currentTime+=.1;f.engine.setFlight(.5);f.engine.setFlight(null)
  assert.equal(f.engine.flightWind.gain.value,0);assert.equal(f.engine.flightToneGain.gain.value,0)
  f.engine.dispose()
})
test('mute and hidden-page transitions immediately reject cues and stop existing voices',()=>{
  const f=fixture();audible(f);f.engine.cue('broadcast');assert.equal(f.engine.voices.size,2)
  f.engine.setMuted(true);assert.equal(f.engine.voices.size,0);assert.equal(f.engine.master.gain.value,0)
  f.engine.cue('arrival');assert.equal(f.engine.voices.size,0)
  f.engine.setMuted(false);f.context.currentTime+=1;f.engine.cue('arrival');assert.equal(f.engine.voices.size,3)
  f.engine.setVisible(false);assert.equal(f.engine.voices.size,0);assert.equal(f.engine.master.gain.value,0)
  f.engine.cue('select');assert.equal(f.engine.voices.size,0);f.engine.dispose()
})
test('weather accents are sparse and abstract safety scenarios emit no threat sound',()=>{
  const f=fixture();audible(f);f.engine.weather('thunderstorm');assert.equal(f.engine.voices.size,2)
  for(let i=0;i<20;i++)f.engine.weather('thunderstorm')
  assert.equal(f.engine.voices.size,2)
  f.context.currentTime+=3;f.engine.weather('public_safety');assert.equal(f.engine.voices.size,2)
  f.context.currentTime+=3;f.engine.weather('hailstorm');assert.equal(f.engine.voices.size,5)
  f.engine.dispose()
})
test('a later cue can wake an idle context even when audio time has stopped',()=>{
  const context=new Context();let wallTime=0
  const engine=new PixelSoundscape(context,()=>wallTime);engine.setMuted(false);engine.cue('error')
  assert.equal(engine.voices.size,2)
  context.state='suspended';wallTime=5;engine.cue('error')
  assert.equal(engine.voices.size,4);assert.equal(context.state,'running');engine.dispose()
})
test('dispose closes the context and disconnects loops plus scheduled transient voices',()=>{
  const f=fixture();audible(f);f.engine.cue('arrival');f.engine.setFlight(.5);f.engine.dispose()
  assert.equal(f.context.state,'closed');assert.equal(f.engine.voices.size,0)
  assert.ok(f.context.nodes.every(node=>node.disconnected))
  assert.ok(f.engine.loops.every(source=>source.stops.length===1))
  const count=f.context.nodes.length;f.engine.dispose();f.engine.cue('confirm');f.engine.setFlight(.5)
  assert.equal(f.context.nodes.length,count)
})
