import assert from 'node:assert/strict'
import {test} from 'node:test'
import {build} from '../frontend/node_modules/esbuild/lib/main.js'
const built=await build({entryPoints:['frontend/src/pixel-ui/ResidentMobility.ts'],bundle:true,platform:'node',format:'esm',write:false})
const {residentMobility}=await import(`data:text/javascript;base64,${Buffer.from(built.outputFiles[0].text).toString('base64')}`)
const person={appearance:{mobility:'walk'}},chair={appearance:{mobility:'wheelchair'}}
test('inspector distinguishes current running/careful movement from usual pace',()=>{
  assert.equal(residentMobility({mode:'walking',movement_style:'run',speed_mps:2.2},person).label,'Running')
  assert.deepEqual(residentMobility({mode:'walking',movement_style:'careful',speed_mps:.54,weather_response:'snow_caution'},person),{label:'Careful steps',speed:'0.5 m/s',response:'Slower travel on snow'})
})
test('wheelchair movement never becomes a running label and vehicle riders retain their mode',()=>{
  assert.equal(residentMobility({mode:'walking',movement_style:'run'},chair).label,'Moving to shelter')
  assert.equal(residentMobility({mode:'walking',movement_style:'careful'},chair).label,'Moving carefully')
  assert.equal(residentMobility({mode:'riding',movement_style:'careful'},person).label,'Riding')
})
test('stops retain explicit zero speed; missing legacy values never claim a current speed',()=>{
  assert.equal(residentMobility({mode:'waiting',speed_mps:0,weather_response:'wind_impact'},person).speed,'0.0 m/s')
  assert.equal(residentMobility({mode:'walking',movement_style:'still',speed_mps:0},person).label,'Waiting')
  for(const value of [undefined,NaN,Infinity,-1])assert.equal(residentMobility({mode:'walking',speed_mps:value},person).speed,null)
  assert.equal(residentMobility(undefined,person),null)
  assert.equal(residentMobility({inside:true,weather_response:'snow_caution'},person).response,null)
})
