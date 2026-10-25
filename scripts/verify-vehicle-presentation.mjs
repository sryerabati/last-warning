#!/usr/bin/env node
import assert from 'node:assert/strict'
import {test} from 'node:test'
import {build} from '../frontend/node_modules/esbuild/lib/main.js'
const compiled=await build({entryPoints:['frontend/src/pixel-world/VehiclePresentation.ts'],bundle:true,platform:'node',format:'esm',write:false})
const {busVisibleAt}=await import(`data:text/javascript;base64,${Buffer.from(compiled.outputFiles[0].text).toString('base64')}`)
const row=(fraction,visible)=>({id:'bus-campus-1',fraction,visible})
test('returning bus remains visible during its trip even when final inventory is scheduled',()=>{
  const events=[row(0,true),row(.8,false)]
  assert.equal(busVisibleAt(false,events,.3),true)
  assert.equal(busVisibleAt(false,events,.799),true)
  assert.equal(busVisibleAt(false,events,.8),false)
  assert.equal(busVisibleAt(false,events,1),false)
})
test('late departure does not expose empty scheduled inventory before dispatch',()=>{
  const events=[row(0,false),row(.6,true)]
  assert.equal(busVisibleAt(true,events,0),false)
  assert.equal(busVisibleAt(true,events,.599),false)
  assert.equal(busVisibleAt(true,events,.6),true)
  assert.equal(busVisibleAt(true,events,1),true)
})
test('a complete trip within one frame replays only its recorded visibility interval',()=>{
  const events=[row(0,false),row(.1,true),row(.9,false)]
  assert.equal(busVisibleAt(false,events,.05),false)
  assert.equal(busVisibleAt(false,events,.5),true)
  assert.equal(busVisibleAt(false,events,.95),false)
  assert.equal(busVisibleAt(false,events,.5),true,'backward seeking is deterministic')
})
test('direct seeks and legacy frames use the actual endpoint state',()=>{
  assert.equal(busVisibleAt(false,[],.4),false)
  assert.equal(busVisibleAt(true,[],.4),true)
  assert.equal(busVisibleAt(false,[row(0,true)],1),false)
})
