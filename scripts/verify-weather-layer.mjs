#!/usr/bin/env node
import assert from 'node:assert/strict'
import {test} from 'node:test'
import {build} from '../frontend/node_modules/esbuild/lib/main.js'

// Exercise real Pixi Graphics without allocating a browser renderer or cloud run.
const built=await build({entryPoints:['frontend/src/pixel-world/WeatherLayer.ts'],bundle:true,platform:'node',format:'esm',write:false})
const {WeatherLayer}=await import(`data:text/javascript;base64,${Buffer.from(built.outputFiles[0].text).toString('base64')}`)
const view={x:0,y:0,width:300,height:200,worldX:0,worldY:0,scale:1}
const frame=(tick,time,lastThunderSeconds,hazard={},extra={})=>({tick,time,interval_seconds:30,hazard_cells:[],active_hazard_cells:[],hazard:{type:'thunderstorm',active:true,last_thunder_seconds:lastThunderSeconds,...hazard},...extra})
const flashes=layer=>layer.screen.children[2].context.instructions.length
const particles=layer=>layer.screen.children[1].context.instructions.length
const beginFlash=()=>{
  const layer=new WeatherLayer({roads:[]})
  layer.setFrame(frame(3,90,null),true);layer.draw(0,1,true,false,view)
  layer.setFrame(frame(4,120,120),true);layer.draw(1,1,true,false,view)
  assert.ok(flashes(layer)>0,'recorded adjacent thunder should draw lightning')
  return layer
}

test('same-frame pause freezes a visible accent, while a paused adjacent seek clears it',()=>{
  const layer=beginFlash()
  layer.draw(1.3,1,false,false,view)
  assert.ok(flashes(layer)>0,'pausing the current instant preserves its frozen appearance')
  layer.setFrame(frame(5,150,120),false);layer.draw(1.3,1,false,false,view)
  assert.equal(flashes(layer),0,'an adjacent paused seek must not carry lightning into another instant')
  layer.draw(1.4,1,true,false,view)
  assert.equal(flashes(layer),0,'resume must not replay the skipped event')
  layer.destroy()
})

test('nonadjacent and backward seeks never create a historical flash',()=>{
  const layer=beginFlash()
  layer.setFrame(frame(10,300,240),true);layer.draw(2,1,true,false,view)
  assert.equal(flashes(layer),0)
  layer.setFrame(frame(2,60,null),false);layer.draw(2,1,false,false,view)
  assert.equal(flashes(layer),0)
  layer.destroy()
})

test('recorded thunder inside a coarse interval appears only at its physical event time',()=>{
  const layer=new WeatherLayer({roads:[]})
  layer.setFrame(frame(10,210,120),true);layer.draw(0,1,true,false,view)
  layer.setFrame(frame(11,270,240,{}, {interval_seconds:60}),true)
  layer.draw(.2,.49,true,false,view);assert.equal(flashes(layer),0)
  layer.draw(.3,.5,true,false,view);assert.ok(flashes(layer)>0)
  layer.draw(.6,.8,true,false,view);assert.ok(flashes(layer)>0)
  layer.draw(1.2,1,true,false,view);assert.equal(flashes(layer),0)
  layer.destroy()
})

test('reduced motion retains precipitation and suppresses lightning',()=>{
  const layer=beginFlash()
  layer.draw(1.3,1,false,true,view)
  assert.equal(flashes(layer),0)
  assert.ok(particles(layer)>0,'rain remains legible as a still weather layer')
  layer.destroy()
})

test('screen-density weather remains inside each comparison viewport and ends on the exact snow endpoint',()=>{
  const layer=new WeatherLayer({roads:[]})
  layer.setFrame(frame(105,12600,null,{type:'blizzard',active:false,qualifying_blizzard_seconds:12600},
    {interval_seconds:120,hazard_motion:{path:[[0,0],[0,0]],fractions:[0,1],active_from:0,active_until:1}}),false)
  layer.draw(0,.5,false,false,{...view,x:304})
  assert.equal(layer.screen.x,304);assert.ok(particles(layer)>0)
  layer.draw(0,1,false,false,{...view,x:304})
  assert.equal(particles(layer),0);assert.equal(layer.diagnostics.snowCover,1)
  layer.destroy()
})
