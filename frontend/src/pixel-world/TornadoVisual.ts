import type {Graphics} from 'pixi.js'
import type {Point} from '../types'
import {pixelEllipse as drawPixelEllipse,pixelLine} from './PixelEffectsGeometry'

export interface TornadoVisualOptions {
  /** Recorded center and contact radius, expressed in world pixels. */
  center:Point
  radius:number
  /** Sampled replay seconds. No wall-clock or random state is retained. */
  seconds:number
  scale:number
  active:boolean
  reducedMotion:boolean
}

const clamp=(n:number,lo:number,hi:number)=>Math.max(lo,Math.min(hi,n))
const snap=(n:number,pixel=3)=>Math.round(n/pixel)*pixel
const tone={edge:0x34484e,shadow:0x486068,body:0x667f83,light:0xa3b6b0,rim:0xc5cdbb,dust:0xb6ae8a,earth:0x736a4f}
const mod=(n:number,m:number)=>((n%m)+m)%m
const pixelEllipse=(g:Graphics,x:number,y:number,rx:number,ry:number,color:number,alpha:number,unit=4,outline=0)=>drawPixelEllipse(g,x,y,rx,ry,color,alpha,unit,outline)

/** Broad connected pixel silhouette. The funnel is elevated scenery; only the
 * caller's recorded ground circle is a physical contact footprint. */
export function tornadoShape(radius:number,seconds:number,reducedMotion=false){
  const r=clamp(Number.isFinite(radius)?radius:115,20,220)
  const time=reducedMotion?0:Number.isFinite(seconds)?seconds:0
  const height=snap(clamp(240+r*.48,250,330))
  const crown=clamp(r*.69,65,91)
  const rows:Array<{y:number;left:number;right:number;u:number}>=[]
  for(let y=0;y<=height;y+=3){
    const u=y/height
    const sway=Math.sin(time*.52+u*4.1)*7*u+Math.sin(u*2.5)*12*u
    const width=8+crown*Math.pow(u,.84)+(Math.sin(u*15-time*.34)+Math.sin(u*9+time*.24))*2.2*u
    rows.push({y:-y,left:snap(sway-width),right:snap(sway+width),u})
  }
  return {height,crown,rows}
}

function steppedRibbon(g:Graphics,points:Point[],color:number,alpha:number,width:number){
  if(points.length<2)return
  for(let i=1;i<points.length;i++)pixelLine(g,...points[i-1],...points[i],color,alpha,width)
}

export function drawTornado(ground:Graphics,funnel:Graphics,options:TornadoVisualOptions){
  const {center,active,reducedMotion}=options
  if(!active||center.length!==2||!center.every(Number.isFinite)||!Number.isFinite(options.radius)||options.radius<=0)return
  const [x,y]=center.map(value=>snap(value)),r=options.radius,scale=clamp(Number.isFinite(options.scale)?options.scale:1,.125,4)
  const time=reducedMotion?0:Number.isFinite(options.seconds)?options.seconds:0
  const {height,crown,rows}=tornadoShape(r,time,reducedMotion)
  // A rasterized boundary distinguishes actual ground contact from the larger
  // cloud. Its radius remains faithful to the recorded footprint.
  pixelEllipse(ground,x,y,r,r,0x43524b,.13,3)
  pixelEllipse(ground,x,y,r,r,0xc8c49f,.46,3,Math.max(3,3/scale))
  pixelEllipse(ground,x+8,y+7,r*.82,r*.30,0x263c3c,.26)
  pixelEllipse(ground,x-2,y+3,r*.57,r*.19,tone.dust,.16)
  // Long, sparse bent wind ribbons convey rotation without hiding the map.
  for(let i=0;i<9;i++){
    const phase=time*.62+i*2.3999,rad=r*(.75+(i%3)*.18),arc:Point[]=[]
    for(let k=0;k<9;k++){
      const a=phase+k*.055
      arc.push([x+Math.cos(a)*rad,y+Math.sin(a)*rad*.38-(i%3)*5])
    }
    steppedRibbon(ground,arc,i%2?tone.rim:tone.dust,.22+(i%3)*.055,2)
  }
  // Wide rolling cloud base feeds directly into the funnel crown. Connected
  // stepped lobes avoid the old disconnected stack-of-bars silhouette.
  const capY=y-height+7,capShift=rows.at(-1)!.left+rows.at(-1)!.right
  pixelEllipse(funnel,x+capShift/2,capY,crown*1.55,25,tone.edge,.94)
  // Deliberately unequal lobes form a rolling cloud base rather than a flat
  // saucer. Their centers remain within the existing broad crown envelope.
  const lobes=[[-1,31,25,9],[-.55,42,33,16],[.02,47,39,24],[.55,38,30,12],[.98,30,25,8]]
  for(let i=0;i<lobes.length;i++){
    const [offset,w,h,lift]=lobes[i],shift=offset*crown
    const cy=capY-lift+Math.sin(i*1.7+time*.16)*3
    pixelEllipse(funnel,x+capShift/2+shift,cy,w,h,i%2?tone.shadow:tone.body,.97)
    pixelEllipse(funnel,x+capShift/2+shift-7,cy-h*.43,w*.67,h*.32,tone.light,.25)
    pixelEllipse(funnel,x+capShift/2+shift-9,cy-h*.62,w*.38,4,tone.rim,.15)
  }
  // Connected horizontal strips keep every silhouette edge on the same pixel
  // grid; a smooth polygon stroke would reintroduce vector-looking curves.
  for(const row of rows)funnel.rect(x+row.left-3,y+row.y-3,row.right-row.left+6,9)
  funnel.fill({color:tone.edge,alpha:.95})
  for(const row of rows)funnel.rect(x+row.left,y+row.y,row.right-row.left,3)
  funnel.fill({color:tone.body,alpha:.97})
  // The side shading and moving highlights never cut gaps in the solid body.
  for(const row of rows){
    const width=row.right-row.left,phase=row.u*23-time*.85
    const front=(Math.sin(phase)+1)*.5
    funnel.rect(x+row.left+2,y+row.y,Math.max(3,snap(width*(.18+.07*front))),3).fill({color:tone.shadow,alpha:.72})
    funnel.rect(x+row.right-Math.max(3,snap(width*.18)),y+row.y,Math.max(3,snap(width*.18)),3).fill({color:tone.edge,alpha:.46})
    // Helical light bands with a sloped, continuous pixel edge.
    const ribbon=mod(row.u*height*.075-time*.45,1)
    if(ribbon<.24){
      const start=row.left+width*(.19+.13*front),length=width*(.47+.12*front)
      funnel.rect(snap(x+start),y+row.y,Math.max(3,snap(length)),3).fill({color:tone.light,alpha:.37+.16*row.u})
      if(ribbon<.07)funnel.rect(snap(x+start+length*.12),y+row.y,Math.max(3,snap(length*.66)),3).fill({color:tone.rim,alpha:.35})
    }
  }
  // Debris travels on the same deterministic vortex. Higher chips are airborne
  // decoration, not damage markers; the physical contact ring is unchanged.
  for(let i=0;i<27;i++){
    const age=mod(time*.17+i*.618034,1),a=time*(1.1+(i%3)*.08)+i*2.3999
    const elevation=(i%4===0?height*.64:height*.28)*age,rad=(18+r*.60*age)
    const px=snap(x+Math.cos(a)*rad),py=snap(y+Math.sin(a)*rad*.26-elevation)
    const w=i%4===0?7:4,h=i%3===0?4:3
    funnel.rect(px,py,w,h).fill({color:i%3===0?tone.rim:i%3===1?tone.earth:0x556a50,alpha:.75})
    if(i%4===0)funnel.rect(px-3,py+2,3,2).fill({color:tone.dust,alpha:.35})
  }
  // Low opaque dust does not cover the resident layer: the caller sorts this
  // scenery behind people at the same contact center.
  for(let i=0;i<7;i++){
    const a=time*.68+i*.90,dx=Math.cos(a)*r*.36,dy=Math.sin(a)*r*.12
    pixelEllipse(funnel,x+dx,y+dy-3,14+(i%3)*4,6+(i%2)*3,i%2?tone.dust:tone.earth,.24,3)
  }
}
