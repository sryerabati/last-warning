#!/usr/bin/env node
import assert from 'node:assert/strict'
import {test} from 'node:test'
import {build} from '../frontend/node_modules/esbuild/lib/main.js'
const built=await build({entryPoints:['frontend/src/pixel-world/TornadoVisual.ts'],bundle:true,platform:'node',format:'esm',write:false})
const {drawTornado,tornadoShape}=await import(`data:text/javascript;base64,${Buffer.from(built.outputFiles[0].text).toString('base64')}`)
class RecordedGraphics{
  commands=[]
  rect(...args){this.commands.push(['rect',...args]);return this}
  circle(...args){this.commands.push(['circle',...args]);return this}
  moveTo(...args){this.commands.push(['moveTo',...args]);return this}
  lineTo(...args){this.commands.push(['lineTo',...args]);return this}
  poly(...args){this.commands.push(['poly',...args]);return this}
  fill(...args){this.commands.push(['fill',...args]);return this}
  stroke(...args){this.commands.push(['stroke',...args]);return this}
}
const options={center:[600,700],radius:115.2,seconds:35,scale:1,active:true,reducedMotion:false}
function record(overrides={}){const ground=new RecordedGraphics(),funnel=new RecordedGraphics();drawTornado(ground,funnel,{...options,...overrides});return {ground:ground.commands,funnel:funnel.commands}}
test('the tornado has one connected, tapered pixel silhouette at a readable bounded height',()=>{
  for(const radius of [30,115.2,220,1000]){
    const shape=tornadoShape(radius,35)
    assert.ok(shape.height>=250&&shape.height<=330)
    assert.ok(shape.rows.at(-1).right-shape.rows.at(-1).left>120)
    assert.ok(shape.rows[0].right-shape.rows[0].left<25)
    for(let i=0;i<shape.rows.length;i++){
      const row=shape.rows[i];assert.ok(row.left<row.right)
      assert.ok(row.left%3===0);assert.ok(row.right%3===0)
      if(i)assert.equal(shape.rows[i-1].y-row.y,3)
    }
  }
  assert.equal(record().funnel.filter(c=>['poly','circle','lineTo'].includes(c[0])).length,0,'funnel silhouette and ribbons are raster rectangles')
})
test('pixel contact boundary stays within one art pixel of the recorded center/radius at every camera scale',()=>{
  for(const scale of [.125,.5,1,4]){
    const commands=record({scale}).ground,firstFill=commands.findIndex(c=>c[0]==='fill'),rects=commands.slice(0,firstFill)
    assert.ok(rects.every(c=>c[0]==='rect'))
    const left=Math.min(...rects.map(c=>c[1])),right=Math.max(...rects.map(c=>c[1]+c[3]))
    const top=Math.min(...rects.map(c=>c[2])),bottom=Math.max(...rects.map(c=>c[2]+c[4]))
    assert.ok(Math.abs((left+right)/2-600)<=1.5);assert.ok(Math.abs((top+bottom)/2-700)<=1.5)
    assert.ok(Math.abs((right-left)/2-115.2)<=3);assert.ok(Math.abs((bottom-top)/2-115.2)<=3)
    assert.equal(commands.filter(c=>c[0]==='circle').length,0)
  }
})
test('seeking and paused frames reproduce the same drawing without retained animation state',()=>{
  const a=record();record({seconds:88});assert.deepEqual(record(),a)
  assert.notDeepEqual(record({seconds:36}).funnel,a.funnel)
})
test('reduced motion freezes the tornado sculpture while keeping it visible',()=>{
  const a=record({reducedMotion:true});assert.ok(a.funnel.length>100)
  assert.deepEqual(record({seconds:70,reducedMotion:true}),a)
})
test('inactive or invalid recorded hazards draw no phantom tornado',()=>{
  for(const o of [{active:false},{radius:0},{radius:NaN},{center:[NaN,1]}])assert.deepEqual(record(o),{ground:[],funnel:[]})
})
test('all generated coordinates and dimensions remain finite and bounded',()=>{
  for(const [key,commands] of Object.entries(record({seconds:1e8}))){
    assert.ok(commands.length<1200,key)
    for(const command of commands)for(const value of command.slice(1).flat(Infinity))if(typeof value==='number')assert.ok(Number.isFinite(value))
    for(const command of commands.filter(c=>c[0]==='rect'))assert.ok(command[3]>0&&command[4]>0)
  }
})

test('cloud cap has taller irregular lobes without expanding the broad horizontal envelope',()=>{
  const shape=tornadoShape(options.radius,options.seconds),rects=record().funnel.filter(c=>c[0]==='rect')
  const top=Math.min(...rects.map(c=>c[2]))
  assert.ok(top<options.center[1]-shape.height-40,'cloud should visibly rise above the funnel crown')
  assert.ok(top>options.center[1]-shape.height-75,'cloud cap height stays bounded')
  const crownRects=rects.filter(c=>c[2]<options.center[1]-shape.height)
  const left=Math.min(...crownRects.map(c=>c[1])),right=Math.max(...crownRects.map(c=>c[1]+c[3]))
  assert.ok(right-left<shape.crown*3.25,'cloud remains inside its existing broad envelope')
  const roofProfile=side=>[.5,.7,.9,1.1].map(offset=>{
    const x=options.center[0]+side*shape.crown*offset
    return Math.min(...crownRects.filter(c=>c[1]<=x&&c[1]+c[3]>=x).map(c=>c[2]))
  })
  assert.notDeepEqual(roofProfile(-1),roofProfile(1),'cloud should not be a mirrored, flat cap')
})
