import {bundle} from '@remotion/bundler';
import {ensureBrowser, getCompositions, renderStill, renderMedia} from '@remotion/renderer';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const root=fileURLToPath(new URL('..',import.meta.url));
const output=process.env.MOTION_OUTPUT ? path.resolve(process.env.MOTION_OUTPUT) : path.join(root,'renders');
const stillsOnly=process.argv.includes('--stills');
const onlyIndex=process.argv.indexOf('--only');
const only=onlyIndex>=0 ? process.argv[onlyIndex+1] : null;
const content=JSON.parse(await readFile(path.join(root,'src/content.json'),'utf8'));
const chromiumOptions={gl:'swangle'};
const assets=[
  {id:'Title',file:'01-title.mp4',seconds:6,at:'00:09',frames:[0,30,90,179]},
  {id:'Results',file:'02-results-54-vs-193.mp4',seconds:17,at:'01:12',frames:[0,45,105,180,509]},
  {id:'Architecture',file:'03-architecture-full.mp4',seconds:32,at:'01:42',frames:[0,90,210,390,465,570,750,959]},
  {id:'GPUPivot',file:'04-gpu-pivot.mp4',seconds:17,at:'02:29',frames:[0,60,180,360,509]},
  {id:'EndCard',file:'05-end-card.mp4',seconds:3,at:'02:57',frames:[0,30,89]},
];
await mkdir(path.join(output,'stills'),{recursive:true});
console.log('Preparing local renderer and bundled fonts…');
await ensureBrowser({logLevel:'warn'});
const serveUrl=await bundle({entryPoint:path.join(root,'src/index.tsx'),publicDir:path.join(root,'public')});
const compositions=await getCompositions(serveUrl,{inputProps:content,chromiumOptions,logLevel:'warn',onBrowserLog:log=>{if(log.type==='error')console.log('Browser:',log.text);}});
for(const asset of assets){
  if(only&&asset.id!==only)continue;
  const composition=compositions.find(c=>c.id===asset.id);
  if(!composition)throw new Error(`Missing composition ${asset.id}`);
  if(composition.durationInFrames!==asset.seconds*30)throw new Error(`Duration mismatch: ${asset.id}`);
  for(const frame of asset.frames){
    const name=`${asset.id}-${String(frame).padStart(4,'0')}.png`;
    await renderStill({serveUrl,composition,inputProps:content,chromiumOptions,frame,output:path.join(output,'stills',name),imageFormat:'png',logLevel:'warn'});
  }
  console.log(`${asset.id}: ${asset.frames.length} inspection frames rendered.`);
  if(stillsOnly)continue;
  let last=-1;
  await renderMedia({
    serveUrl,composition,inputProps:content,chromiumOptions,outputLocation:path.join(output,asset.file),
    codec:'h264',pixelFormat:'yuv420p',crf:18,x264Preset:'fast',concurrency:2,
    imageFormat:'png',muted:true,colorSpace:'bt709',logLevel:'warn',
    onProgress:({progress})=>{const step=Math.floor(progress*4);if(step!==last){last=step;console.log(`${asset.id}: ${Math.min(100,step*25)}%`);}},
  });
  console.log(`Saved ${asset.file}`);
}
await writeFile(path.join(output,'asset-manifest.json'),JSON.stringify({
  width:1920,height:1080,fps:30,codec:'h264',pixelFormat:'yuv420p',colorSpace:'bt709',audio:false,
  remotionVersion:'4.0.538',comparisonId:content.comparisonId,assets:assets.map(({frames,...asset})=>asset),
  note:'Opaque full-frame inserts. No alpha/keying or plug-in needed. Edit source props to change baked text.',
},null,2)+'\n');
console.log(stillsOnly?'Inspection stills ready.':'Main CapCut clips ready.');
