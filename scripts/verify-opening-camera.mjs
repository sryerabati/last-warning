#!/usr/bin/env node
// Exercise the real PixelWorld camera methods against fake drawing surfaces.
// Geographic values come from the actual serialized campus. No browser/cloud calls.
import assert from 'node:assert/strict'
import {spawnSync} from 'node:child_process'
import {fileURLToPath} from 'node:url'
import {test} from 'node:test'
import {build} from '../frontend/node_modules/esbuild/lib/main.js'

const root=fileURLToPath(new URL('../',import.meta.url))
const mocks={
  'pixi.js':`export class Application {renderer={resolution:2,background:{},resize(){}};renderCount=0;render(){this.renderCount++}destroy(){}};export class Container{};export class Graphics{};export class Sprite{}`,
  './Art':`export const CELL=64,ART_VERSION='test-pixel-art';export function loadArt(){throw Error('No asset loading in camera checks')}`,
  './CityVisualAdapter':`export function acquireTown(){throw Error('No asset loading in camera checks')}`,
  './HazardLayer':`export class HazardLayer{}`,
  './ResidentLayer':`export class ResidentLayer{}`,
  './VehicleLayer':`export class VehicleLayer{}`,
  './ReplayClock':`export class ReplayClock{playing=false;reduced=false;fraction=1;time=0;animationTime=0;set(_tick,playing){this.playing=playing}}`,
  './TownAtmosphere':`export class TownAtmosphere{}`,
  './WeatherLayer':`export class WeatherLayer{}`,
  './WeatherSurfaces':`export class WeatherSurfaces{}`,
  './TownLifeTypes':`export function bounds(){throw Error('Noncampus generation is outside these checks')}`,
  './CampusBuildings':`export function indexCampusBuildings(){return []};export function campusBuildingAt(){return null}`,
}
const compiled=await build({
  entryPoints:[fileURLToPath(new URL('../frontend/src/pixel-world/PixelWorld.ts',import.meta.url))],
  bundle:true,platform:'node',format:'esm',write:false,logLevel:'silent',
  plugins:[{name:'drawing-surfaces',setup(build){
    build.onResolve({filter:/.*/},args=>mocks[args.path]?{path:args.path,namespace:'drawing-surfaces'}:undefined)
    build.onLoad({filter:/.*/,namespace:'drawing-surfaces'},args=>({contents:mocks[args.path],loader:'js'}))
  }}],
})
globalThis.matchMedia=()=>({matches:false,addEventListener(){},removeEventListener(){}})
const {PixelWorld}=await import(`data:text/javascript;base64,${Buffer.from(compiled.outputFiles[0].text).toString('base64')}`)
const result=spawnSync(fileURLToPath(new URL('../.venv/bin/python',import.meta.url)),['-c',[
  'import json',
  'from backend.app.simulation.campus_world import make_campus_city',
  'c=make_campus_city().serialize()',
  'print(json.dumps({k:c[k] for k in ("layout","size","camera_focus","map_bounds","meters_per_unit","geography_provenance")}))',
].join(';')],{cwd:root,encoding:'utf8',timeout:60000})
assert.equal(result.status,0,result.stderr||String(result.error??'Campus serialization failed'))
const campus={...JSON.parse(result.stdout),roads:[],river:[],places:[]}
const graphic=()=>({clear(){return this},rect(){return this},fill(){return this},stroke(){return this}})
function fixture(width=1440,height=900,extra={}){
  const box={width,height},canvas={dataset:{},parentElement:{getBoundingClientRect:()=>box},removeEventListener(){}}
  const world=new PixelWorld(canvas,{...campus,...extra},()=>{},()=>{},()=>{}),noop=()=>{}
  const r={x:0,y:0,scale:{value:1,set(value){this.value=value}}};r.position={set(x,y){r.x=x;r.y=y}}
  const view={root:r,mask:graphic(),route:graphic(),water:graphic(),location:graphic(),origin:graphic(),
    people:{root:{visible:true},draw:noop,setFrame:noop,setProfiles:noop,destroy:noop,occupiedPlaces:()=>[],position:()=>null},
    vehicles:{draw:noop,setFrame:noop,destroy:noop,positionForResident:()=>null},
    weather:{screen:{visible:true},state:()=>null,draw:noop,setFrame:noop,destroy:noop,diagnostics:null},surfaces:{setSnow:noop,destroy:noop},
    atmosphere:{night:0,draw:noop,setFrame:noop},hazard:{draw:noop,setFrame:noop},base:{release:noop},frame:null}
  world.views=[view];world.width=width;world.height=height;world.scale=1;world.render()
  return {world,camera:world.openingCamera,canvas,view,box}
}
const transform=f=>[f.view.root.x,f.view.root.y,f.view.root.scale.value]
const close=(actual,expected,tolerance=1e-8)=>assert.ok(Math.abs(actual-expected)<=tolerance,`${actual} != ${expected}`)
const frame={tick:0,time:0,agents:[],agent_activities:[],vehicles:[],blocked_roads:[],metrics:{}}

test('actual campus registers the Oval and metric axes in the serialized geographic extent',()=>{
  const f=fixture(),landing=f.camera.begin()
  assert.ok(landing)
  close(landing.target[0],-83.0123,1e-8);close(landing.target[1],39.9994,1e-8)
  const [west,south,east,north]=landing.geographicBounds,[left,top,right,bottom]=campus.map_bounds
  close((east-west)*landing.metersPerDegree[0],(right-left)*campus.meters_per_unit)
  close((north-south)*landing.metersPerDegree[1],(bottom-top)*campus.meters_per_unit)
  assert.equal(landing.metersPerPixel,24.25/64)
})

test('flight scales are continuous and preserve a chosen Oval anchor to pixel-rounding precision',()=>{
  const f=fixture(),landing=f.camera.begin(),anchor=[.58,.43]
  const scales=[]
  for(const metres of [31.73,31.72,31.71]){
    const bounds=f.camera.pose(metres,anchor);scales.push(f.view.root.scale.value)
    assert.ok(bounds.every(Number.isFinite));assert.ok(bounds[2]>bounds[0]&&bounds[3]>bounds[1])
    const point=campus.camera_focus.map((n,i)=>n*64*f.view.root.scale.value+(i?f.view.root.y:f.view.root.x))
    close(point[0],anchor[0]*landing.viewport[0],.5);close(point[1],anchor[1]*landing.viewport[1],.5)
  }
  assert.ok(scales[0]<scales[1]&&scales[1]<scales[2],'adjacent flight poses must not snap to the same zoom level')
  assert.ok(f.world.app.renderCount>=4,'poses must render the actual world')
})

test('final flight frame and ordinary Oval camera have identical transforms, including clamped wide screens',()=>{
  for(const [width,height] of [[1440,900],[390,844],[5000,2000]]){
    const f=fixture(width,height),landing=f.camera.begin()
    f.camera.pose(50,[.5,.5]);f.camera.pose(landing.metersPerPixel,landing.anchor)
    const before=transform(f);f.camera.end(true)
    assert.deepEqual(transform(f),before,`${width}×${height} must not jump at handoff`)
    assert.equal(f.canvas.dataset.openingActive,'false')
  }
})

test('Skip restores the original view even after repeated begin calls and several flight poses',()=>{
  const f=fixture();f.world.center=[35,30];f.world.scale=.375;f.world.render()
  const original=transform(f),center=[...f.world.center],landing=f.camera.begin()
  f.camera.pose(80,[.3,.4]);assert.equal(f.camera.begin(),landing);f.camera.pose(2,[.6,.5]);f.camera.end(false)
  assert.deepEqual(transform(f),original);assert.deepEqual(f.world.center,center)
  f.camera.end(false);assert.deepEqual(transform(f),original,'ending twice must be harmless')
})

test('resize refreshes the final landing without replacing the saved view',()=>{
  const f=fixture(),originalScale=f.world.scale,first=f.camera.begin()
  f.camera.pose(10,[.5,.5]);f.box.width=390;f.box.height=844;f.world.resize()
  const resized=f.camera.begin();assert.deepEqual(resized.viewport,[390,844]);assert.deepEqual(resized.target,first.target)
  f.camera.pose(resized.metersPerPixel,resized.anchor);const final=transform(f);f.camera.end(true)
  assert.deepEqual(transform(f),final);assert.equal(f.world.scale,originalScale)
})

test('setFrames cannot re-clamp or snap a flight while App updates paused frame options',()=>{
  const f=fixture();f.camera.begin();const bounds=f.camera.pose(42.37,[.18,.71]),before=transform(f)
  f.world.setFrames([frame],{playing:false,profiles:[],selected:null,followSelected:false})
  assert.deepEqual(transform(f),before);assert.deepEqual(JSON.parse(f.canvas.dataset.mapScreenBounds),bounds)
})

test('paused follow-state updates during a flight still restore following on Skip',()=>{
  const f=fixture(),changes=[],position=[30,30]
  f.world.followChanged=value=>changes.push(value);f.world.follow=true
  f.world.options={selected:7,followSelected:true};f.view.people.position=()=>position;f.world.render()
  const original=transform(f)
  f.camera.begin();f.world.setFrames([frame],{playing:false,selected:7,followSelected:false})
  f.camera.pose(30,[.5,.5]);f.camera.end(false)
  f.world.setFrames([frame],{playing:false,selected:7,followSelected:true})
  assert.deepEqual(changes,[false,true]);assert.deepEqual(transform(f),original)
})

test('inspector inset changes refresh the landing while the current geographic pose stays fixed',()=>{
  const f=fixture(),first=f.camera.begin();f.camera.pose(30,[.5,.5]);const before=transform(f)
  f.world.setFrames([frame],{playing:false,cameraInsets:{right:360}})
  assert.deepEqual(transform(f),before)
  const next=f.camera.begin();assert.ok(next.anchor[0]<first.anchor[0])
  f.camera.pose(next.metersPerPixel,next.anchor);const landing=transform(f);f.camera.end(true)
  assert.deepEqual(transform(f),landing)
})

test('far-flight fixed-size resident markers hide, then restore at normal campus scale',()=>{
  const f=fixture(),landing=f.camera.begin();f.camera.pose(50,[.5,.5])
  assert.equal(f.view.people.root.visible,false)
  f.camera.pose(landing.metersPerPixel,landing.anchor);assert.equal(f.view.people.root.visible,true)
  f.camera.pose(50,[.5,.5]);f.camera.end(false);assert.equal(f.view.people.root.visible,true)
})

test('unsupported, invalid and disposed camera states fail without corrupting a view',()=>{
  const f=fixture();f.camera.begin();const valid=f.camera.pose(10,[.5,.5]),before=transform(f)
  for(const metres of [0,-1,NaN,Infinity])assert.deepEqual(f.camera.pose(metres,[.5,.5]),valid)
  assert.deepEqual(transform(f),before)
  const paired=fixture();paired.world.views.push(paired.view);assert.equal(paired.camera.begin(),null)
  const absent=fixture(1440,900,{geography_provenance:{}});assert.equal(absent.camera.begin(),null)
  f.world.dispose();assert.equal(f.camera.begin(),null);assert.deepEqual(f.camera.pose(1,[.5,.5]),[0,0,0,0]);assert.doesNotThrow(()=>f.camera.end(true))
})
