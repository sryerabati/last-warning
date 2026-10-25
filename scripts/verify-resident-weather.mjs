#!/usr/bin/env node
import assert from 'node:assert/strict'
import {test} from 'node:test'
import {build} from '../frontend/node_modules/esbuild/lib/main.js'
const load=async path=>{const result=await build({entryPoints:[path],bundle:true,platform:'node',format:'esm',write:false});return import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].text).toString('base64')}`)}
const {activityDuring,endpointFacing,residentSegment,residentWeatherPose}=await load('frontend/src/pixel-world/ResidentWeatherPresentation.ts')
const {impactAt,impactPose}=await load('frontend/src/pixel-world/ImpactPresentation.ts')
const {drawCharacter,characterAppearance}=await load('frontend/src/pixel-world/CharacterDesign.ts')
const adult={age:'adult',mobility:'walk'}
const input=(extra={})=>({activity:{mode:'walking',activity:'seeking shelter',movement_style:'run',weather_response:'seeking_shelter'},appearance:adult,moving:true,speed:2.2,weather:null,time:2.1,phase:.3,direction:1,...extra})

test('actual segment duration sets gait speed, independent of accelerated replay time',()=>{
  const motion={path:[[0,0],[2,0],[2,0],[3,0]],fractions:[0,.4,.8,1]}
  assert.equal(residentSegment(motion,.2,10,4).speed,2)
  assert.deepEqual(residentSegment(motion,.4,10,4),{moving:false,speed:0},'exact stop boundary must stop gait')
  assert.deepEqual(residentSegment(motion,.7,10,4),{moving:false,speed:0})
  assert.ok(Math.abs(residentSegment(motion,.9,10,4).speed-2)<1e-10)
  assert.deepEqual(residentSegment(motion,.2,0,4),{moving:false,speed:0})
})
test('future arrival, boarding and weather metadata do not leak backwards into an interval',()=>{
  const before={inside:false,mode:'walking',activity:'seeking shelter',movement_style:'run',speed_mps:2.1}
  const end={inside:true,mode:'indoors',activity:'sheltering indoors',movement_style:'still',speed_mps:0}
  const changes=[{...end,fraction:.7}]
  assert.deepEqual(activityDuring(end,before,changes,.2),before)
  assert.equal(activityDuring(end,before,changes,.7).inside,true)
  assert.deepEqual(activityDuring(end,before,changes,1),end)
})
test('full fraction-zero transition supports legacy recordings without previous activity state',()=>{
  const start={inside:false,mode:'walking',activity:'walking to class',fraction:0}
  const end={inside:true,mode:'indoors',activity:'in class'}
  assert.equal(activityDuring(end,undefined,[start,{...end,fraction:.8}],.1).inside,false)
  assert.equal(activityDuring(end,undefined,[start,{...end,fraction:.8}],.9).inside,true)
})
test('a real urgent adult walk uses a distinct running silhouette and fixed frozen pose',()=>{
  const run=residentWeatherPose(input()),ordinary=residentWeatherPose(input({activity:{mode:'walking',activity:'walking to class'}}))
  assert.equal(run.style,'run');assert.ok(run.lean>0);assert.notEqual(ordinary.style,'run')
  assert.deepEqual(residentWeatherPose(input()),run,'frozen replay clock must preserve gait')
  assert.notEqual(residentWeatherPose(input({time:2.25})).pose,run.pose)
})
test('a stopped resident cannot run in place because of stale shelter metadata',()=>{
  const stopped=residentWeatherPose(input({moving:false,speed:0}))
  assert.equal(stopped.moving,false);assert.equal(stopped.pose,0);assert.notEqual(stopped.style,'run')
})
test('snow overrides urgency and uses a cautious gait, including wheelchair and family members',()=>{
  for(const appearance of [adult,{age:'child',mobility:'walk'},{age:'older',mobility:'walk'},{age:'adult',mobility:'wheelchair'}]){
    const pose=residentWeatherPose(input({appearance,speed:.7,weather:{kind:'blizzard',active:true}}))
    assert.equal(pose.style,'careful');assert.equal(pose.response,'snow_caution')
    assert.ok(pose.pose>0)
  }
})
test('wheelchair, older adults and children never inherit the adult running recipe',()=>{
  for(const appearance of [{age:'adult',mobility:'wheelchair'},{age:'older',mobility:'walk'},{age:'child',mobility:'walk'}])assert.notEqual(residentWeatherPose(input({appearance})).style,'run')
  assert.equal(residentWeatherPose(input({appearance:{age:'adult',mobility:'wheelchair'}})).lean,0)
})
test('weather protection applies outdoors; sheltered and vehicle occupants do not gesture in the rain',()=>{
  const storm={kind:'thunderstorm',active:true}
  assert.equal(residentWeatherPose(input({moving:false,weather:storm})).style,'brace')
  for(const activity of [{inside:true,mode:'indoors'},{inside:false,mode:'riding'},{inside:false,mode:'driving'}]){
    const result=residentWeatherPose(input({activity,weather:storm}));assert.equal(result.style,'walk');assert.equal(result.response,'none');assert.equal(result.moving,false)
  }
})
test('tornado contact overrides gait, then ends exactly on the recorded recovery boundary',()=>{
  const event={id:2,hazard:'tornado',kind:'knockdown',started_at:30,contact_ended_at:34,recover_until:42,position:[0,0],intensity:1}
  const hit=impactAt([event],32),pose=residentWeatherPose(input({impact:hit}))
  assert.equal(pose.style,'brace');assert.equal(pose.pose,0);assert.equal(pose.moving,false)
  assert.equal(impactAt([event],42),undefined)
  const chair=impactPose(event,32,true);assert.equal(chair.rotation,0);assert.equal(chair.scaleY,1);assert.equal(chair.offsetY,0)
})
test('continuous snow or hail exposure does not immobilize a recorded moving pedestrian',()=>{
  const event={id:2,hazard:'blizzard',kind:'brace',started_at:0,contact_ended_at:null,recover_until:100,position:[0,0],intensity:1}
  const snow=residentWeatherPose(input({impact:event,speed:.7,weather:{kind:'blizzard',active:true}}))
  assert.equal(snow.style,'careful');assert.equal(snow.moving,true);assert.ok(snow.pose>0)
  const hail=residentWeatherPose(input({impact:{...event,hazard:'hailstorm'},weather:{kind:'hailstorm',active:true}}))
  assert.equal(hail.style,'run');assert.equal(hail.moving,true)
})
test('paused or direct-seek facing follows the last recorded motion, ignoring trailing holds',()=>{
  assert.equal(endpointFacing([[0,0],[1,0],[1,0]]),1)
  assert.equal(endpointFacing([[2,3],[2,1],[2,1]]),0)
  assert.equal(endpointFacing([[0,0],[0,0]]),undefined)
  assert.equal(endpointFacing([[0,0],[NaN,0]]),undefined)
})
test('generated run, careful and protective variants use distinct finite native pixel geometry',()=>{
  const recipes=[]
  for(const style of ['walk','run','careful','brace']){
    const calls=[],ctx={save(){},restore(){},beginPath(){},rect(){},clip(){},translate(){},scale(){},fillRect(x,y,w,h){assert.ok([x,y,w,h].every(Number.isFinite));assert.ok(w>=0&&h>0);if(w)calls.push([x,y,w,h,this.fillStyle])}}
    drawCharacter(ctx,characterAppearance(7,42,{headwear:0,accessory:0}),1,3,style)
    recipes.push(JSON.stringify(calls))
  }
  assert.equal(new Set(recipes).size,4)
})
