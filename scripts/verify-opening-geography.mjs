#!/usr/bin/env node
// Geographic registration and renderer contracts; no browser/cloud calls.
import assert from 'node:assert/strict'
import {spawnSync} from 'node:child_process'
import {fileURLToPath} from 'node:url'
import {test} from 'node:test'
import {build} from '../frontend/node_modules/esbuild/lib/main.js'

const root=fileURLToPath(new URL('../',import.meta.url))
const compiled=await build({entryPoints:[fileURLToPath(new URL('../frontend/src/pixel-ui/OpeningGeography.ts',import.meta.url))],bundle:true,platform:'node',format:'esm',write:false,logLevel:'silent',plugins:[{
  name:'no-gpu',setup(build){
    build.onResolve({filter:/^pixi\.js$/},()=>({path:'pixi',namespace:'no-gpu'}))
    build.onLoad({filter:/.*/,namespace:'no-gpu'},()=>({contents:'export const Assets={};export class Rectangle{};export class Texture{};',loader:'js'}))
  },
}]})
const {withCampusContext,paintRegion,geographicProjector}=await import(`data:text/javascript;base64,${Buffer.from(compiled.outputFiles[0].text).toString('base64')}`)
const result=spawnSync(fileURLToPath(new URL('../.venv/bin/python',import.meta.url)),['-c','import json;from backend.app.simulation.campus_world import make_campus_city;print(json.dumps(make_campus_city().serialize()))'],{cwd:root,encoding:'utf8',timeout:60000,maxBuffer:32*1024*1024})
assert.equal(result.status,0,result.stderr||String(result.error??'Campus serialization failed'))
const city=JSON.parse(result.stdout),outside={layer:'building',id:'outside',home:true,lift:16,bounds:[-83.04,40.01,-83.039,40.011],rings:[[[-83.04,40.01],[-83.039,40.01],[-83.039,40.011],[-83.04,40.01]]]}
const base={land:new Uint8ClampedArray(),features:[],local:[outside]}
const context=withCampusContext(base,city)
const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-8,`${a} != ${b}`)

test('campus geometry fills the survey while retaining real surrounding footprints',()=>{
  assert.equal(context.local.filter(p=>p.campus&&p.layer==='building').length,city.campus_geometry.buildings.length)
  for(const layer of ['green','water','path'])assert.ok(context.local.some(p=>p.campus&&p.layer===layer),`${layer} must be present below reveal`)
  assert.equal(context.local[0],outside)
  assert.deepEqual(base.local,[outside],'caller data must not be mutated')
  assert.ok(context.campusLines.some(p=>p.layer==='road'))
  assert.ok(context.campusLines.some(p=>p.layer==='path'))
  assert.ok(context.trees.length>1000&&context.trees.length<=city.campus_geometry.trees.length)
  assert.equal(context.nativePixelMeters,city.meters_per_unit/64)
})

test('converted vertices register exactly to native world coordinates and preserve courtyard holes',()=>{
  const [west,north,east,south]=city.map_bounds,[minLon,minLat,maxLon,maxLat]=city.geography_provenance.selection_bbox
  const coefficients=[(east-west)*city.meters_per_unit/(maxLon-minLon),(south-north)*city.meters_per_unit/(maxLat-minLat)]
  const project=geographicProjector([minLon,maxLat],coefficients,city.meters_per_unit/64,[0,0],1)
  const features=new Map(city.campus_geometry.buildings.map(f=>[f.id,f]))
  for(const mapped of context.local.filter(p=>p.campus&&p.layer==='building')){
    const source=features.get(mapped.id);assert.ok(source)
    assert.equal(mapped.rings.length,source.geometry.coordinates.length)
    for(let r=0;r<mapped.rings.length;r++)for(let i=0;i<mapped.rings[r].length;i++){
      const [x,y]=project(mapped.rings[r][i]),[wx,wy]=source.geometry.coordinates[r][i]
      close(x,(wx-west)*64);close(y,(wy-north)*64)
    }
  }
})

test('campus roof identity matches the native helper rules and context merging is idempotent',()=>{
  const hash=value=>[...value].reduce((n,c)=>Math.imul(n^c.charCodeAt(0),16777619)>>>0,2166136261)
  const features=new Map(city.campus_geometry.buildings.map(f=>[f.id,f]))
  for(const mapped of context.local.filter(p=>p.campus&&p.layer==='building')){
    const f=features.get(mapped.id),housing=String(f.housing_type??''),kind=String(f.building_type??f.kind??'')
    const home=!!(housing&&housing!=='null'?['house','student_house'].includes(housing):['house','detached','semidetached_house','terrace','residential'].includes(kind))
    assert.equal(mapped.home,home)
    assert.equal(mapped.lift,home?16:/Thompson|Orton Hall/i.test(f.name??'')||f.name==='Ohio Union'?34:22+hash(String(f.id))%3*4)
  }
  const again=withCampusContext(context,city)
  assert.deepEqual(again.local,context.local)
  assert.deepEqual(again.campusLines,context.campusLines)
  assert.deepEqual(again.trees,context.trees)
  assert.equal(withCampusContext(base,{...city,geography_provenance:{}}),base)
})

function drawingSurface(){
  const calls=[],stack=[]
  const ctx={canvas:{width:1200,height:900},fillStyle:'',strokeStyle:'',lineWidth:1,globalAlpha:1,
    save(){stack.push([this.fillStyle,this.strokeStyle,this.lineWidth,this.globalAlpha])},restore(){[this.fillStyle,this.strokeStyle,this.lineWidth,this.globalAlpha]=stack.pop()},
    beginPath(){},moveTo(){},lineTo(){},closePath(){},rect(){},clip(){},setLineDash(){},clearRect(){calls.length=0},createRadialGradient(){return {addColorStop(){}}},
    stroke(){calls.push(['stroke',this.strokeStyle,this.lineWidth,this.globalAlpha])},fill(){calls.push(['fill',this.fillStyle])},
    fillRect(){calls.push(['rect',this.fillStyle])},drawImage(source){calls.push(...(source.commands??[['tree']]))},
  }
  ctx.canvas.getContext=()=>ctx;ctx.canvas.commands=calls
  return {ctx,calls}
}
globalThis.document={createElement(){return drawingSurface().ctx.canvas}}

test('nearby scenery uses campus roof and surface colors and mapped atlas trees',()=>{
  const fixture={...context,art:{image:{},frames:{oak:{x:0,y:0,w:40,h:50},pine:{x:40,y:0,w:40,h:50}}}}
  const {ctx,calls}=drawingSurface(),[west,north,east,south]=city.map_bounds,[minLon,minLat,maxLon,maxLat]=city.geography_provenance.selection_bbox
  const coefficients=[(east-west)*city.meters_per_unit/(maxLon-minLon),(south-north)*city.meters_per_unit/(maxLat-minLat)]
  // Context remains fully rendered even when no native campus is underneath it.
  const project=geographicProjector([-83.0123,39.9994],coefficients,1,[600,450],1)
  paintRegion(ctx,fixture.features,project,1,1,fixture.local,fixture)
  assert.ok(calls.some(c=>c[0]==='tree'))
  for(const color of ['#7f986b','#c7c1a6','#697771','#586d51','#b3b39b'])assert.ok(calls.some(c=>c[1]===color),`${color} must be present`)
  assert.ok(calls.some(c=>['#706d60','#817561','#777e71','#8b6e5c'].includes(c[1])),'neighborhood homes must retain their muted roof palettes')
})

test('high-altitude detail does not expose the rectangular source extent',()=>{
  const {ctx,calls}=drawingSurface()
  paintRegion(ctx,[],p=>p,18,1,context.local,context)
  assert.equal(calls.length,0,'local roofs, trees and paths must not render as a dense island at district altitude')
})

test('subpixel road surfacing uses one clean stroke without curb and centerline noise',()=>{
  const {ctx,calls}=drawingSurface(),road={properties:{layer:'road',class:'primary'},geometry:{type:'LineString',coordinates:[[0,0],[30,30]]}}
  paintRegion(ctx,[road],p=>p,5,1,[],undefined)
  assert.ok(calls.some(c=>c[0]==='stroke'&&c[1]==='#697771'))
  assert.ok(!calls.some(c=>c[0]==='stroke'&&['#667463','#bab69d','#c9bd91'].includes(c[1])))
})

test('regional street width and palette do not jump at the former 22m/px cutoff',()=>{
  const road={properties:{layer:'road',class:'primary'},geometry:{type:'LineString',coordinates:[[0,0],[30,30]]}}
  const samples=[22.01,21.99].map(mpp=>{const {ctx,calls}=drawingSurface();paintRegion(ctx,[road],p=>p,mpp,1);return calls.filter(c=>c[0]==='stroke').at(-1)})
  assert.ok(Math.abs(samples[0][2]-samples[1][2])<.01)
  for(const index of [1,3,5])assert.ok(Math.abs(parseInt(samples[0][1].slice(index,index+2),16)-parseInt(samples[1][1].slice(index,index+2),16))<=1)
})

test('broad illustrative road corridors fade away before the campus landing',()=>{
  const road={properties:{layer:'road',class:'primary'},geometry:{type:'LineString',coordinates:[[0,0],[30,30]]}}
  for(const mpp of [5,4,1]){
    const {ctx,calls}=drawingSurface();paintRegion(ctx,[road],p=>p,mpp,1)
    const corridor=calls.find(c=>c[0]==='stroke'&&c[1]==='#87957b')
    if(mpp===5)assert.ok(corridor&&corridor[3]<.1)
    else assert.equal(corridor,undefined)
  }
})
