#!/usr/bin/env node
import assert from 'node:assert/strict'
import {test} from 'node:test'
import {build} from '../frontend/node_modules/esbuild/lib/main.js'
const compiled=await build({entryPoints:['frontend/src/pixel-world/VehicleWeatherPresentation.ts'],bundle:true,platform:'node',format:'esm',write:false})
const {vehicleConditionAt,vehicleImpactAt,vehicleMotionAt,vehicleWeatherPose}=await import(`data:text/javascript;base64,${Buffer.from(compiled.outputFiles[0].text).toString('base64')}`)

test('snow speed follows recorded distance and physical seconds without altering positions',()=>{
  const clear={path:[[0,0],[10,0]],fractions:[0,1]},snow={path:[[0,0],[5,0]],fractions:[0,1]}
  const clearAt=vehicleMotionAt(clear,.5,10,24),snowAt=vehicleMotionAt(snow,.5,10,24)
  assert.deepEqual(clearAt.point,[5,0]);assert.deepEqual(snowAt.point,[2.5,0])
  assert.equal(snowAt.speed,clearAt.speed/2)
  assert.deepEqual(vehicleMotionAt(snow,.5,10,24),snowAt,'pause and seek sample the same position')
})
test('recorded stops have zero speed and retain their prior heading at a turn',()=>{
  const motion={path:[[0,0],[0,3],[0,3],[2,3]],fractions:[0,.3,.7,1]}
  const stopped=vehicleMotionAt(motion,.5,10,1)
  assert.deepEqual(stopped.point,[0,3]);assert.equal(stopped.speed,0);assert.equal(stopped.moving,false)
  assert.equal(stopped.heading,Math.PI/2)
  assert.equal(vehicleMotionAt(motion,.3,10,1).moving,false,'the hold begins at the exact breakpoint')
})
test('invalid or corrupt vehicle trajectories cannot invent movement',()=>{
  assert.equal(vehicleMotionAt({path:[[0,0],[1,1]],fractions:[0,0]},.5,10,1),null)
  assert.equal(vehicleMotionAt({path:[[0,0],[NaN,1]],fractions:[0,1]},.5,10,1),null)
  assert.equal(vehicleMotionAt({path:[[0,0],[1]],fractions:[0,1]},.5,10,1),null)
})
test('bus dwell and impact yielding are sampled at recorded transitions, never from the future endpoint',()=>{
  const previous={state:'driving',speed_mps:4,weather_response:'snow_caution'},final={state:'dwelling',speed_mps:0,weather_response:'snow_caution'}
  const changes=[{id:'bus',fraction:0,...previous},{id:'bus',fraction:.4,state:'yielding',speed_mps:0,weather_response:'wind_impact'},{id:'bus',fraction:.8,...final}]
  assert.equal(vehicleConditionAt(final,previous,changes,.3).state,'driving')
  assert.equal(vehicleConditionAt(final,previous,changes,.4).state,'yielding')
  assert.equal(vehicleConditionAt(final,previous,changes,.9).state,'dwelling')
  assert.deepEqual(vehicleConditionAt(final,previous,changes,1),final)
  assert.equal(vehicleConditionAt(final,previous,[],.5).state,'driving','legacy frames retain their known prior state')
})
const impact={id:'car-1',hazard:'tornado',kind:'buffet',started_at:30,contact_ended_at:32,recover_until:40,position:[2,3],intensity:1}
test('vehicle contact survives alighting and includes empty active buses only when recorded',()=>{
  assert.equal(vehicleImpactAt([impact],[],'car-1',[],31),impact)
  assert.equal(vehicleImpactAt([impact],[],'car-1',[],29),undefined)
  assert.equal(vehicleImpactAt([impact],[],'car-1',[],40),undefined)
  assert.equal(vehicleImpactAt([impact],[],'bus-2',[],31),undefined)
  const bus={...impact,id:'bus-2'};assert.equal(vehicleImpactAt([bus],[],'bus-2',[],31),bus)
})
test('legacy contacts never attach a pedestrians fall or another vehicles occupant to this vehicle',()=>{
  const brace={...impact,id:7,kind:'brace',vehicle_id:'car-1'}
  assert.equal(vehicleImpactAt([], [brace], 'car-2',[7],31),undefined)
  assert.equal(vehicleImpactAt([], [brace], 'car-1',[],31).id,'car-1')
  assert.equal(vehicleImpactAt([], [{...brace,vehicle_id:undefined,kind:'knockdown'}], 'car-1',[7],31),undefined)
})
test('impact rocking stays bounded and grounded, with deterministic recovery and reduced motion',()=>{
  const pose=t=>vehicleWeatherPose({kind:'tornado',active:true}, {state:'yielding'},0,false,t,1,false,0,impact)
  for(let t=30;t<40;t+=.1){assert.ok(Math.abs(pose(t).rotation)<=.055);assert.equal(pose(t).braking,true)}
  assert.deepEqual(pose(31),pose(31))
  assert.ok(pose(39.9).impactAmount<pose(33).impactAmount)
  const quiet=vehicleWeatherPose({kind:'tornado',active:true},{state:'yielding'},0,false,31,20,true,0,impact)
  assert.equal(quiet.rotation,.018);assert.equal(quiet.hazardLights,true)
  assert.ok(!('x' in quiet)&&!('y' in quiet),'presentation never displaces recorded coordinates')
})
test('weather lights and wipers stop after rain while accumulated roof snow remains',()=>{
  const state={state:'driving'},active={kind:'blizzard',active:true,snowCover:.8},clear={...active,active:false}
  const snowy=vehicleWeatherPose(active,state,2,true,600,2,false,0)
  assert.equal(snowy.headlights,true);assert.equal(snowy.wipers,true);assert.equal(snowy.snowTracks,true)
  const after=vehicleWeatherPose(clear,state,2,true,14000,2,false,0)
  assert.equal(after.wipers,false);assert.equal(after.snowCover,.8)
  assert.equal(vehicleWeatherPose(active,state,0,false,600,2,true,0).wiperPhase,.5)
})
