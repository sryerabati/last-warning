import {spawnSync} from 'node:child_process';
import {copyFile,mkdir,readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const root=fileURLToPath(new URL('..',import.meta.url));
const output=process.env.MOTION_OUTPUT ? path.resolve(process.env.MOTION_OUTPUT) : path.join(root,'renders');
const cli=path.join(root,'node_modules/@remotion/cli/remotion-cli.js');
const run=(args)=>{
  const r=spawnSync(process.execPath,[cli,'ffmpeg',...args],{encoding:'utf8',maxBuffer:20*1024*1024});
  if(r.status!==0)throw new Error(r.stderr||r.stdout);
};
const encode=(source,start,seconds,destination)=>run([
  '-v','error','-y','-ss',String(start),'-i',source,'-t',String(seconds),'-map','0:v:0','-an',
  '-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',
  '-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-movflags','+faststart',destination,
]);
const architecture=path.join(output,'03-architecture-full.mp4');
encode(architecture,0,14,path.join(output,'03a-architecture-core.mp4'));
encode(architecture,14,18,path.join(output,'03b-architecture-neural.mp4'));
console.log('Split architecture clips exported: 14 seconds + 18 seconds.');

const holds=path.join(output,'hold-frames');
await mkdir(holds,{recursive:true});
for(const [from,to] of [
  ['Title-0179.png','01-title.png'],['Results-0509.png','02-results-54-vs-193.png'],
  ['Architecture-0959.png','03-architecture-full.png'],['Architecture-0390.png','03a-architecture-core.png'],
  ['Architecture-0959.png','03b-architecture-neural.png'],['GPUPivot-0509.png','04-gpu-pivot.png'],['EndCard-0089.png','05-end-card.png'],
])await copyFile(path.join(output,'stills',from),path.join(holds,to));

const previewDir=path.join(output,'preview');
await mkdir(previewDir,{recursive:true});
const previewParts=[['01-title.mp4',0,5],['02-results-54-vs-193.mp4',0,6],['03-architecture-full.mp4',14,7],['04-gpu-pivot.mp4',9,6],['05-end-card.mp4',0,3]];
for(let i=0;i<previewParts.length;i++){
  const [file,start,seconds]=previewParts[i];
  encode(path.join(output,file),start,seconds,path.join(previewDir,`part-${i}.mp4`));
}
const concatList=path.join(previewDir,'parts.txt');
await writeFile(concatList,previewParts.map((_,i)=>`file 'part-${i}.mp4'`).join('\n')+'\n');
run(['-v','error','-y','-f','concat','-safe','0','-i',concatList,'-an','-c:v','copy','-movflags','+faststart',path.join(output,'animation-preview.mp4')]);

const manifestPath=path.join(output,'asset-manifest.json');
const manifest=JSON.parse(await readFile(manifestPath,'utf8'));
manifest.assets=manifest.assets.filter(a=>!a.id.startsWith('Architecture-'));
manifest.assets.push(
  {id:'Architecture-Core',file:'03a-architecture-core.mp4',seconds:14,at:'01:42',use:'Alternative to first 14 seconds of full architecture'},
  {id:'Architecture-Neural',file:'03b-architecture-neural.mp4',seconds:18,at:'01:56',use:'Alternative to last 18 seconds of full architecture'},
);
manifest.preview={file:'animation-preview.mp4',seconds:27,note:'Asset preview only; not the three-minute demo.'};
await writeFile(manifestPath,JSON.stringify(manifest,null,2)+'\n');
console.log('Hold frames and 27-second preview created.');
