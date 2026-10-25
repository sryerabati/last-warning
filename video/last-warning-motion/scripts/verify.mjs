import {spawnSync} from 'node:child_process';
import {readFile,writeFile,stat} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const root=fileURLToPath(new URL('..',import.meta.url));
const output=process.env.MOTION_OUTPUT ? path.resolve(process.env.MOTION_OUTPUT) : path.join(root,'renders');
const cli=path.join(root,'node_modules/@remotion/cli/remotion-cli.js');
const run=(command,args)=>{
  const result=spawnSync(process.execPath,[cli,command,...args],{encoding:'utf8',maxBuffer:20*1024*1024});
  if(result.status!==0)throw new Error(`${command}: ${result.stderr||result.stdout}`);
  return result.stdout;
};
const manifest=JSON.parse(await readFile(path.join(output,'asset-manifest.json'),'utf8'));
const report=[];
for(const asset of manifest.assets){
  const file=path.join(output,asset.file);
  const metadata=JSON.parse(run('ffprobe',['-v','error','-count_frames','-show_streams','-show_format','-of','json',file]));
  const video=metadata.streams.find(s=>s.codec_type==='video');
  if(!video)throw new Error(`No video: ${asset.file}`);
  const actual={width:video.width,height:video.height,codec:video.codec_name,pixelFormat:video.pix_fmt,
    fps:video.r_frame_rate,duration:Number(metadata.format.duration),frames:Number(video.nb_read_frames),
    audioStreams:metadata.streams.filter(s=>s.codec_type==='audio').length,colorSpace:video.color_space};
  if(actual.width!==1920||actual.height!==1080||actual.fps!=='30/1'||actual.codec!=='h264'||actual.pixelFormat!=='yuv420p')throw new Error(`Wrong export format ${asset.file}: ${JSON.stringify(actual)}`);
  if(actual.frames!==asset.seconds*30||Math.abs(actual.duration-asset.seconds)>0.05)throw new Error(`Wrong duration ${asset.file}: ${JSON.stringify(actual)}`);
  if(actual.audioStreams!==0)throw new Error(`Unexpected audio ${asset.file}`);
  run('ffmpeg',['-v','error','-i',file,'-map','0:v:0','-c:v','rawvideo','-f','null','-']);
  const bytes=(await stat(file)).size;
  report.push({file:asset.file,...actual,bytes,decodedWithoutErrors:true});
  console.log(`PASS ${asset.file}: ${actual.duration}s / ${actual.frames} frames / ${(bytes/1048576).toFixed(2)} MiB`);
}
await writeFile(path.join(output,'verification.json'),JSON.stringify({verified:true,assets:report},null,2)+'\n');
console.log('All exported clips have the expected format, duration, frame count and clean video decoding.');
