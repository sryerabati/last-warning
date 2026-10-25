#!/usr/bin/env node
import assert from 'node:assert/strict'
import {test} from 'node:test'
import {build} from '../frontend/node_modules/esbuild/lib/main.js'
const compiled=await build({entryPoints:['frontend/src/pixel-world/ImpactPresentation.ts'],bundle:true,platform:'node',format:'esm',write:false})
const {impactAt,impactPose,pointAlong,hazardAt}=await import(`data:text/javascript;base64,${Buffer.from(compiled.outputFiles[0].text).toString('base64')}`)
const event={id:1,hazard:'tornado',kind:'knockdown',started_at:31,contact_ended_at:35,recover_until:43,position:[20,20],intensity:1}
test('saved impact appears only in its exact contact/recovery window, including seek',()=>{
  assert.equal(impactAt([event],30.99),undefined);assert.equal(impactAt([event],31),event)
  assert.equal(impactAt([event],42.99),event);assert.equal(impactAt([event],43),undefined)
  assert.equal(impactAt([event],33),event,'seeking backward recovers the exact recorded state')
})
test('contact has a readable fall, sustained hold and gradual recovery, with no coordinate displacement',()=>{
  const before=impactPose(event,31),fall=impactPose(event,31.3),held=impactPose(event,36),rise=impactPose(event,42.5),end=impactPose(event,43)
  assert.equal(before.rotation,0);assert.ok(fall.rotation>0&&fall.rotation<held.rotation)
  assert.ok(held.rotation>1);assert.ok(rise.rotation<held.rotation);assert.equal(end.rotation,0)
  assert.equal(impactPose(event,36).stage,'knocked down');assert.equal(rise.stage,'recovering')
  assert.deepEqual(impactPose(event,36),held,'paused animation is deterministic')
})
test('wheelchair and bracing poses avoid tipping a chair onto the ground',()=>{
  assert.ok(Math.abs(impactPose(event,33,true).rotation)<=.16)
  assert.equal(impactPose(event,33,true).stage,'bracing')
  assert.ok(Math.abs(impactPose({...event,kind:'brace'},33).rotation)<=.16)
})
test('newer contact wins only once it actually starts',()=>{
  const later={...event,started_at:38,recover_until:50}
  assert.equal(impactAt([event,later],36),event);assert.equal(impactAt([event,later],40),later)
})
test('tornado center follows recorded breakpoints while the end snapshot is inactive',()=>{
  const frame={hazard:{center:[30,10],started:false},hazard_cells:[],active_hazard_cells:[],hazard_motion:{path:[[10,20],[10,20],[30,10],[30,10]],fractions:[0,.125,.75,1],active_from:.125,active_until:.75}}
  assert.equal(hazardAt(frame,null,.1).active,false)
  assert.deepEqual(hazardAt(frame,null,.4375),{active:true,center:[20,15]})
  assert.equal(hazardAt(frame,null,.9).active,false)
})
test('motion sampling rejects corrupt trajectories and never overshoots',()=>{
  assert.equal(pointAlong([[0,0],[1,1]],[0,0],.5),undefined)
  assert.equal(pointAlong([[0,0],[NaN,1]],[0,1],.5),undefined)
  assert.deepEqual(pointAlong([[0,0],[10,5]],[0,1],2),[10,5])
})
test('exact recorded tornado endpoints take precedence over the preceding motion window',()=>{
  const base={hazard:{center:[20,20],active:true,started:true},hazard_cells:[],hazard_motion:{path:[[20,20],[20,20]],fractions:[0,1],active_from:null,active_until:null}}
  assert.equal(hazardAt(base,null,.99).active,false)
  assert.equal(hazardAt(base,null,1).active,true)
  assert.equal(hazardAt({...base,hazard:{...base.hazard,active:false},hazard_motion:{...base.hazard_motion,active_from:0,active_until:1}},null,1).active,false)
})
