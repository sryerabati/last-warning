#!/usr/bin/env node
import assert from 'node:assert/strict'
import {test} from 'node:test'
import {build} from '../frontend/node_modules/esbuild/lib/main.js'

const compiled=await build({entryPoints:['frontend/src/audio/useWorldAudio.ts'],bundle:true,platform:'node',format:'esm',write:false,logLevel:'silent'})
const {readSoundPreference}=await import(`data:text/javascript;base64,${Buffer.from(compiled.outputFiles[0].text).toString('base64')}`)

test('sound defaults on while preserving an explicit mute preference',()=>{
  const original=Object.getOwnPropertyDescriptor(globalThis,'localStorage')
  try{
    for(const [saved,expected] of [[null,true],['on',true],['off',false],['unrecognized',true]]){
      Object.defineProperty(globalThis,'localStorage',{configurable:true,value:{getItem:key=>{assert.equal(key,'last-warning-sound/v1');return saved}}})
      assert.equal(readSoundPreference(),expected,`saved preference ${saved}`)
    }
  }finally{
    if(original)Object.defineProperty(globalThis,'localStorage',original)
    else delete globalThis.localStorage
  }
})

test('blocked browser storage does not turn off the sound default',()=>{
  const original=Object.getOwnPropertyDescriptor(globalThis,'localStorage')
  try{
    Object.defineProperty(globalThis,'localStorage',{configurable:true,get(){throw Error('Storage unavailable')}})
    assert.equal(readSoundPreference(),true)
  }finally{
    if(original)Object.defineProperty(globalThis,'localStorage',original)
    else delete globalThis.localStorage
  }
})
