#!/usr/bin/env node
import assert from 'node:assert/strict'
import {test} from 'node:test'
import {build} from '../frontend/node_modules/esbuild/lib/main.js'
const built=await build({entryPoints:['frontend/src/pixel-world/PixelEffectsGeometry.ts'],bundle:true,platform:'node',format:'esm',write:false})
const {ellipsePixels,linePixels}=await import(`data:text/javascript;base64,${Buffer.from(built.outputFiles[0].text).toString('base64')}`)

test('pixel outlines retain empty centers and bilateral, integer-grid symmetry',()=>{
  const shape=ellipsePixels(100,100,18,8,2,2)
  assert.ok(shape.length>4)
  for(const [x,y,w,h] of shape){
    assert.ok([x,y,w,h].every(n=>Number.isInteger(n)&&n%2===0));assert.ok(w>0&&h>0)
    assert.ok(!(x<100&&x+w>100&&y<=100&&y+h>100),'selection ring must not fill the resident center')
    assert.ok(shape.some(([a,b,c,d])=>a===200-x-w&&b===y&&c===w&&d===h),'outline mirrors across the center')
  }
})
test('pixel lines have connected steps and exactly preserve quantized endpoints',()=>{
  for(const end of [[24,9],[-13,29],[0,-18]]){
    const line=linePixels(0,0,...end,2)
    assert.deepEqual(line[0],[0,0,2,2]);assert.deepEqual(line.at(-1),[Math.round(end[0]/2)*2,Math.round(end[1]/2)*2,2,2])
    for(let i=1;i<line.length;i++){assert.ok(Math.abs(line[i][0]-line[i-1][0])<=2);assert.ok(Math.abs(line[i][1]-line[i-1][1])<=2)}
  }
})
test('invalid geometry cannot create phantom effects or unbounded loops',()=>{
  assert.deepEqual(linePixels(NaN,0,1,1),[]);assert.deepEqual(linePixels(0,0,1,1,0),[])
  assert.deepEqual(ellipsePixels(0,0,-1,2),[]);assert.deepEqual(ellipsePixels(0,0,1,Infinity),[])
})
