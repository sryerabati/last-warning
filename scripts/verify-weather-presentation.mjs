#!/usr/bin/env node
import assert from 'node:assert/strict'
import {test} from 'node:test'
import {build} from '../frontend/node_modules/esbuild/lib/main.js'
const built=await build({entryPoints:['frontend/src/pixel-world/WeatherPresentation.ts'],bundle:true,platform:'node',format:'esm',write:false})
const {weatherAt,LightningCue}=await import(`data:text/javascript;base64,${Buffer.from(built.outputFiles[0].text).toString('base64')}`)
const frame=(type,time,hazard={},extra={})=>({tick:time/30,time,interval_seconds:30,hazard_cells:[],active_hazard_cells:[],hazard:{type,active:false,...hazard},...extra})
test('blizzard begins at zero even when the generic started flag is false',()=>{
  const state=weatherAt(frame('blizzard',0,{active:true,started:false,snowing:true,qualifying_blizzard_seconds:0},{interval_seconds:0}),null)
  assert.equal(state.snowfall,1);assert.equal(state.snowCover,0)
})
test('snow accumulates from recorded duration and persists after all-clear',()=>{
  const start=weatherAt(frame('blizzard',600,{active:true,qualifying_blizzard_seconds:600}),null)
  const later=weatherAt(frame('blizzard',3600,{active:true,qualifying_blizzard_seconds:3600}),null)
  const clear=weatherAt(frame('blizzard',14400,{active:false,all_clear:true,qualifying_blizzard_seconds:12600}),null)
  assert.ok(start.snowCover>0&&later.snowCover>start.snowCover)
  assert.equal(clear.snowCover,1);assert.equal(clear.snowfall,0)
  assert.deepEqual(weatherAt(frame('blizzard',600,{active:true,qualifying_blizzard_seconds:600}),null),start)
})
test('a coarse frame retains precipitation in its recorded active interval',()=>{
  const f=frame('thunderstorm',3600,{active:false,all_clear:true,last_thunder_seconds:1800},{interval_seconds:3600,hazard_motion:{path:[[0,0],[0,0]],fractions:[0,1],active_from:120/3600,active_until:.5}})
  assert.equal(weatherAt(f,null,.25).rain,1);assert.equal(weatherAt(f,null,.8).rain,0)
})
test('exact endpoints use the saved state for hazard onset and cessation',()=>{
  for(const [kind,seconds] of [['tornado',30],['thunderstorm',120],['hailstorm',120]]){
    const f=frame(kind,seconds,{active:true},{hazard_motion:{active_from:null,active_until:null}})
    assert.equal(weatherAt(f,null,.99).active,false)
    assert.equal(weatherAt(f,null,1).active,true)
  }
  const end=frame('blizzard',12600,{active:false,qualifying_blizzard_seconds:12600},{hazard_motion:{active_from:0,active_until:1}})
  assert.equal(weatherAt(end,null,.99).snowfall,1)
  assert.equal(weatherAt(end,null,1).snowfall,0)
  assert.equal(weatherAt(end,null,1).snowCover,1)
})
test('shelter hold is wet aftermath, not active rain or hail',()=>{
  const state=weatherAt(frame('thunderstorm',2100,{phase:'shelter_hold',last_thunder_seconds:1800,hail_inches:0}),null)
  assert.equal(state.rain,0);assert.equal(state.hail,false);assert.ok(state.wetness>0)
})
test('hail and low visibility last through the active part of an ending interval',()=>{
  const motion={active_from:0,active_until:.5}
  const snowBefore=frame('blizzard',12540,{active:true,visibility_miles:.2})
  const snowAfter=frame('blizzard',12660,{active:false,visibility_miles:10},{interval_seconds:120,hazard_motion:motion})
  assert.ok(weatherAt(snowAfter,snowBefore,.25).visibility>.5)
  assert.equal(weatherAt(snowAfter,snowBefore,.75).visibility,0)
  const stormBefore=frame('thunderstorm',1790,{active:true,hail_inches:1})
  const stormAfter=frame('thunderstorm',1810,{active:false,hail_inches:0},{interval_seconds:20,hazard_motion:motion})
  assert.equal(weatherAt(stormAfter,stormBefore,.25).hail,true)
  assert.equal(weatherAt(stormAfter,stormBefore,.75).hail,false)
})
test('a future endpoint thunder timestamp is not revealed before it occurs',()=>{
  const before=frame('thunderstorm',210,{active:true,last_thunder_seconds:120})
  const after=frame('thunderstorm',240,{active:true,last_thunder_seconds:240})
  assert.equal(weatherAt(after,before,.5).thunder,120);assert.equal(weatherAt(after,before,1).thunder,240)
})
test('accelerated playback can never trigger bright accents more than once per five presentation seconds',()=>{
  const cue=new LightningCue();cue.reset(0)
  assert.equal(cue.sample(120,1,true,false).amount,1)
  assert.equal(cue.sample(240,2,true,false).amount,0)
  assert.equal(cue.sample(360,3,true,false).amount,0)
  assert.equal(cue.sample(480,6,true,false).amount,1)
})
test('pause freezes the accent; seeking and reduced motion never replay a flash',()=>{
  const cue=new LightningCue();cue.reset(0);cue.sample(120,1,true,false)
  const frozen=cue.sample(120,1.3,false,false)
  assert.deepEqual(cue.sample(120,1.3,false,false),frozen)
  cue.reset(600);assert.equal(cue.sample(600,10,true,false).amount,0)
  assert.equal(cue.sample(720,20,true,true).amount,0)
})
