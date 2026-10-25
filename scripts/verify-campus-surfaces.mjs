#!/usr/bin/env node
// Render-only trace reconstruction must never invent routes across clipped gaps.
import assert from 'node:assert/strict'
import {spawnSync} from 'node:child_process'
import {fileURLToPath} from 'node:url'
import {test} from 'node:test'
import {build} from '../frontend/node_modules/esbuild/lib/main.js'

const root=fileURLToPath(new URL('../',import.meta.url))
const compiled=await build({entryPoints:[fileURLToPath(new URL('../frontend/src/pixel-world/CampusSurfaces.ts',import.meta.url))],bundle:true,platform:'node',format:'esm',write:false,logLevel:'silent'})
const {campusTraces}=await import(`data:text/javascript;base64,${Buffer.from(compiled.outputFiles[0].text).toString('base64')}`)
const line=(id,points,kind='footway')=>({id,kind,geometry:{type:'LineString',coordinates:points}})
const segments=traces=>new Set(traces.flatMap(trace=>trace.points.slice(1).map((end,i)=>{
  const endpoints=[trace.points[i],end].map(point=>point.map(n=>n.toFixed(6)).join(',')).sort()
  return `${trace.kind}:${endpoints.join(';')}`
})))

test('continuous source fragments share one stroke without introducing connecting geometry',()=>{
  const input=[line('way/1/0',[[0,0],[1,1]]),line('way/1/1',[[1,1],[2,1]])]
  const output=campusTraces(input)
  assert.equal(output.length,1)
  assert.deepEqual(output[0].points,[[0,0],[1,1],[2,1]])
})

test('clipped gaps and unrelated ways remain separate even at nearby endpoints',()=>{
  const input=[line('way/1/0',[[0,0],[1,1]]),line('way/1/2',[[1,1],[2,1]]),line('way/2/0',[[2.00001,1],[3,1]])]
  assert.equal(campusTraces(input).length,3)
})

test('reversed duplicate traces do not darken the same path twice',()=>{
  const input=[line('way/1/0',[[0,0],[1,1]]),line('way/2/0',[[1,1],[0,0]])]
  assert.equal(campusTraces(input).length,1)
})

test('real campus road and pedestrian geometry is conserved exactly',()=>{
  const result=spawnSync(fileURLToPath(new URL('../.venv/bin/python',import.meta.url)),['-c','import json; from backend.app.simulation.campus_world import make_campus_city; c=make_campus_city(); print(json.dumps({k:c.geometry[k] for k in ("roads","paths")}))'],{cwd:root,encoding:'utf8',maxBuffer:16*1024*1024,timeout:60000})
  assert.equal(result.status,0,result.stderr||String(result.error??'Campus serialization failed'))
  const source=JSON.parse(result.stdout)
  for(const type of ['roads','paths']){
    const input=source[type].filter(f=>f.geometry.type==='LineString'&&f.kind!=='construction')
    const before=segments(input.map(f=>({kind:f.kind??'footway',points:f.geometry.coordinates}))),after=segments(campusTraces(input))
    assert.deepEqual(after,before,`${type} must not acquire new links or lose mapped segments`)
    console.log(`${type}: ${after.size} unique source segments preserved`)
  }
})
