#!/usr/bin/env node
// Run from any directory: node scripts/verify-campus-building-labels.mjs
// Uses the installed frontend bundler and local map; no browser or model calls.
import assert from 'node:assert/strict'
import {spawnSync} from 'node:child_process'
import {fileURLToPath} from 'node:url'
import {test} from 'node:test'
import {build} from '../frontend/node_modules/esbuild/lib/main.js'

const root=fileURLToPath(new URL('../',import.meta.url))
const compiled=await build({
  entryPoints:[fileURLToPath(new URL('../frontend/src/pixel-world/CampusBuildings.ts',import.meta.url))],
  bundle:true,platform:'node',format:'esm',write:false,logLevel:'silent',
})
const {indexCampusBuildings,campusBuildingAt,campusBuildingLift}=await import(
  `data:text/javascript;base64,${Buffer.from(compiled.outputFiles[0].text).toString('base64')}`,
)
const rect=(left,top,right,bottom)=>[[left,top],[right,top],[right,bottom],[left,bottom],[left,top]]
const feature=(id,name,rings,extra={})=>({id,name,geometry:{type:'Polygon',coordinates:rings},...extra})
const city=(buildings,places=[])=>({campus_geometry:{buildings},places})

test('empty named buildings are identifiable without any occupant/place entry',()=>{
  const index=indexCampusBuildings(city([feature('empty-library','A Library',[rect(2,2,8,8)])]))
  assert.equal(index.length,1)
  assert.equal(index[0].named,true)
  assert.equal(campusBuildingAt(index,[4,4])?.name,'A Library')
  assert.equal(campusBuildingAt(index,[12,4]),null)
})

test('raised roof and visible facade hit the same building as its painted shape',()=>{
  const f=feature('raised','A Hall',[rect(2,2,8,8)])
  const index=indexCampusBuildings(city([f])),lift=campusBuildingLift(f)/64
  assert.equal(campusBuildingAt(index,[4,2-lift/2])?.id,'raised','roof overhang above ground footprint must be hittable')
  assert.equal(campusBuildingAt(index,[4,8-lift/2])?.id,'raised','front wall below roof must remain hittable')
  assert.equal(campusBuildingAt(index,[4,2-lift-.01]),null,'air above the roof is not a building')
})

test('open courtyard and the surrounding exterior remain unselectable',()=>{
  const hole=[[3,3],[3,7],[7,7],[7,3],[3,3]]
  const f=feature('courtyard','Courtyard Hall',[rect(0,0,10,10),hole])
  const index=indexCampusBuildings(city([f]))
  assert.equal(campusBuildingAt(index,[5,5]),null,'courtyard must not be filled by the outer-ring hit test')
  assert.equal(campusBuildingAt(index,[1,5])?.id,'courtyard')
  assert.equal(campusBuildingAt(index,[-1,5]),null)
})

test('overlapping geometry resolves in the same front-to-back order as scenery',()=>{
  const front=feature('front','Front Hall',[rect(4,4,12,12)])
  const back=feature('back','Back Hall',[rect(0,0,8,8)])
  for(const source of [[front,back],[back,front]]){
    const index=indexCampusBuildings(city(source))
    assert.equal(campusBuildingAt(index,[6,6])?.id,'front')
    assert.equal(campusBuildingAt(index,[2,2])?.id,'back')
  }
})

test('Orton clock tower remains selectable above the ordinary roof',()=>{
  const f=feature('orton','Orton Hall',[rect(2,2,8,8)])
  const index=indexCampusBuildings(city([f])),lift=campusBuildingLift(f)/64
  assert.equal(campusBuildingAt(index,[5,2-lift-15/64])?.id,'orton')
  assert.equal(campusBuildingAt(index,[5,2-lift-24/64]),null)
})

test('non-building lines are excluded and linked names/entrances are preserved',()=>{
  const valid=feature('residence',undefined,[rect(2,2,8,8)],{housing_type:'student_house'})
  const invalid={id:'path',name:'A path',geometry:{type:'LineString',coordinates:[[0,0],[1,1]]}}
  const index=indexCampusBuildings(city([valid,invalid],[{id:'residence',name:'Scholarship house',entrance:[3,8]}]))
  assert.equal(index.length,1)
  assert.equal(index[0].name,'Scholarship house')
  assert.equal(index[0].category,'Student house')
  assert.deepEqual(index[0].entrance,[3,8])
})

test('current serialized campus preserves all building identities and known landmarks',()=>{
  const result=spawnSync(fileURLToPath(new URL('../.venv/bin/python',import.meta.url)),['-c',[
    'import json',
    'from backend.app.simulation.campus_world import make_campus_city',
    'c=make_campus_city()',
    'print(json.dumps({"campus_geometry":{"buildings":c.geometry["buildings"]},"places":c.places}))',
  ].join(';')],{cwd:root,encoding:'utf8',maxBuffer:8*1024*1024,timeout:60000})
  assert.equal(result.status,0,result.stderr||String(result.error??'Campus serialization failed'))
  const current=JSON.parse(result.stdout),index=indexCampusBuildings(current)
  assert.equal(index.length,current.campus_geometry.buildings.length)
  assert.equal(new Set(index.map(b=>b.id)).size,index.length)
  for(const name of ['William Oxley Thompson Memorial Library','Orton Hall','Ohio Union']){
    const building=index.find(b=>b.name===name)
    assert.ok(building,`${name} must remain discoverable`)
    assert.ok(building.named)
    assert.ok(building.bounds.every(Number.isFinite))
  }
  const sourceNames=current.campus_geometry.buildings.filter(f=>f.name).map(f=>[f.id,f.name])
  for(const [id,name] of sourceNames)assert.equal(index.find(b=>b.id===id)?.name,name)
  console.log(`Campus geometry: ${index.length} buildings; ${sourceNames.length} source names preserved.`)
})
