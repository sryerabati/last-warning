#!/usr/bin/env node
import assert from 'node:assert/strict'
import {test} from 'node:test'
import {build} from '../frontend/node_modules/esbuild/lib/main.js'
const compiled=await build({entryPoints:['frontend/src/pixel-world/WeatherSurfaces.ts'],bundle:true,platform:'node',format:'esm',write:false})
const {snowLevel,snowRoof}=await import(`data:text/javascript;base64,${Buffer.from(compiled.outputFiles[0].text).toString('base64')}`)
test('snow stages clamp invalid inputs and are stable for rewind/replay',()=>{
  assert.equal(snowLevel(NaN),0);assert.equal(snowLevel(-1),0);assert.equal(snowLevel(2),1)
  assert.equal(snowLevel(.501),snowLevel(.52));assert.equal(snowLevel(.5),.5)
  assert.deepEqual([.7,.2,.7].map(snowLevel),[8/12,2/12,8/12])
})
test('snow roof uses the same raised plane as the rendered building and retains courtyards',()=>{
  const outer=[[0,0],[10,0],[10,10],[0,10],[0,0]],hole=[[2,2],[2,4],[4,4],[4,2],[2,2]]
  const feature={id:'house',housing_type:'house',geometry:{type:'Polygon',coordinates:[outer,hole]}}
  const roof=snowRoof(feature)
  assert.equal(roof.length,2);assert.deepEqual(roof[0][0],[0,-.25]);assert.deepEqual(roof[1][0],[2,1.75])
  assert.deepEqual(feature.geometry.coordinates,[outer,hole],'painting must not mutate routing geometry')
})
test('named landmark snow roof lift matches the existing campus roof plane',()=>{
  const feature={id:'landmark',name:'Orton Hall',geometry:{type:'Polygon',coordinates:[[[1,2],[3,2],[3,4],[1,2]]]}}
  assert.deepEqual(snowRoof(feature)[0][0],[1,2-34/64])
})
