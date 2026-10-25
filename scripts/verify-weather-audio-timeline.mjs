#!/usr/bin/env node
import assert from 'node:assert/strict'
import {test} from 'node:test'
import {build} from '../frontend/node_modules/esbuild/lib/main.js'
const compiled=await build({entryPoints:['frontend/src/audio/AudioTimeline.ts'],bundle:true,platform:'node',format:'esm',write:false})
const {adjacentAudioAdvance,eventDelayMs,weatherAudioEvent}=await import(`data:text/javascript;base64,${Buffer.from(compiled.outputFiles[0].text).toString('base64')}`)
const point=(tick,time,playing=true,runId='run-a')=>({tick,time,playing,runId})
test('adjacent 30-second storm and 120-second blizzard frames can produce weather sounds',()=>{
  assert.equal(adjacentAudioAdvance(point(3,90),point(4,120)),true)
  assert.equal(adjacentAudioAdvance(point(3,360),point(4,480)),true)
  assert.equal(weatherAudioEvent(point(3,360),point(4,480),'blizzard',true,null,250).sound,'blizzard')
})
test('thunder uses the recorded event, including an event inside a coarse frame',()=>{
  const atEnd=weatherAudioEvent(point(3,90),point(4,120),'thunderstorm',true,120,1000)
  assert.deepEqual(atEnd,{key:'run-a:thunder:120',sound:'thunderstorm',delayMs:984})
  const inside=weatherAudioEvent(point(8,220),point(9,250),'hailstorm',true,240,1000)
  assert.equal(inside.sound,'thunderstorm');assert.ok(Math.abs(inside.delayMs-650.6666666667)<.001)
  assert.equal(weatherAudioEvent(point(4,120),point(5,150),'thunderstorm',true,120,1000),null)
})
test('pause, resume, loading a new run and nonadjacent seeking never replay historical thunder',()=>{
  for(const [before,after] of [[point(3,90),point(4,120,false)],[point(3,90,false),point(4,120)],
    [point(3,90),point(4,120,true,'run-b')],[point(3,90),point(8,240)],[point(8,240),point(3,90)]]){
    assert.equal(weatherAudioEvent(before,after,'thunderstorm',true,120,1000),null)
  }
})
test('quiet or abstract scenes do not invent weather cues; legacy weather still has bounded accents',()=>{
  assert.equal(weatherAudioEvent(point(4,120),point(5,150),'thunderstorm',false,120,1000),null)
  assert.equal(weatherAudioEvent(point(4,120),point(5,150),'public_safety',true,null,1000),null)
  assert.equal(weatherAudioEvent(point(4,120),point(5,150),'flood',true,null,1000),null)
  assert.equal(weatherAudioEvent(point(4,120),point(5,150),'thunderstorm',true,undefined,1000).sound,'thunderstorm')
  assert.equal(eventDelayMs(130,point(4,120),point(5,150),1000),1000/3-16)
})
