#!/usr/bin/env node
import assert from 'node:assert/strict'
import {test} from 'node:test'
import {build} from '../frontend/node_modules/esbuild/lib/main.js'
const compiled=await build({entryPoints:['frontend/src/pixel-ui/OpeningBlend.ts'],bundle:true,platform:'node',format:'esm',write:false})
const {detailCoverage}=await import(`data:text/javascript;base64,${Buffer.from(compiled.outputFiles[0].text).toString('base64')}`)
test('detail coverage remains inside the surveyed live world',()=>{
  for(const progress of [0,.5,.95,1])for(const [x,y] of [[-1,400],[1601,400],[800,-1],[800,1201]])assert.equal(detailCoverage(x,y,1600,1200,progress),0)
})
test('edges are feathered and geographically irregular, with opaque interior',()=>{
  const values=[120,200,300,500,700,900].map(y=>detailCoverage(100,y,1600,1200,.8))
  assert.ok(values.every(n=>n>0&&n<1))
  assert.ok(Math.max(...values)-Math.min(...values)>.1)
  assert.equal(detailCoverage(800,600,1600,1200,.8),1)
  for(let x=1;x<250;x++)assert.ok(Math.abs(detailCoverage(x,600,1600,1200,.8)-detailCoverage(x-1,600,1600,1200,.8))<.04)
})
test('last approach resolves all visible detail before exact native handoff',()=>{
  for(const [x,y] of [[0,0],[10,100],[800,600],[1599,1199]]){
    let previous=0
    for(const p of [.9,.92,.94,.96,.98,1]){const n=detailCoverage(x,y,1600,1200,p);assert.ok(n>=previous);previous=n}
    assert.equal(previous,1)
  }
})
