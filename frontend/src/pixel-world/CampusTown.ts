import type {City,CampusFeature,Point} from '../types'
import {CELL,drawArt,hash,type TownArt} from './Art'
import {paintCampusSurfaces} from './CampusSurfaces'
import {campusBuildingHome,campusBuildingLift,campusBuildingRings} from './CampusBuildings'
import {pixelateCanvas} from './PixelCanvas'

export interface CampusDecoration {canvas:HTMLCanvasElement;x:number;y:number;depth:number}
const pixel=(n:number)=>Math.round(n/2)*2
const rings=(f:CampusFeature):Point[][]=>f.geometry.type==='Polygon'?f.geometry.coordinates as Point[][]:[f.geometry.coordinates as Point[]]
const ring=(f:CampusFeature)=>rings(f)[0]
const inside=(p:Point,r:Point[])=>{let yes=false;for(let i=0,j=r.length-1;i<r.length;j=i++){const a=r[i],b=r[j];if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])yes=!yes}return yes}
const inFeature=(p:Point,f:CampusFeature)=>inside(p,ring(f))&&!rings(f).slice(1).some(r=>inside(p,r))
const distance=(p:Point,a:Point,b:Point)=>{const dx=b[0]-a[0],dy=b[1]-a[1],t=Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy||1)));return Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)}
const stableHash=(value:string)=>[...value].reduce((n,c)=>Math.imul(n^c.charCodeAt(0),16777619)>>>0,2166136261)

/** Footprints and route geometry stay unchanged. Scenery is individually depth
 * sorted with residents; a courtyard remains open through every roof layer. */
export function paintCampusTown(ground:CanvasRenderingContext2D,city:City,art:TownArt):CampusDecoration[] {
  const g=city.campus_geometry!,size=city.size*CELL,objects:CampusDecoration[]=[]
  const [west,north,east,south]=city.map_bounds??[0,0,city.size,city.size]
  let ctx=ground
  const path=(pts:Point[],dy=0,dx=0,begin=true)=>{if(begin)ctx.beginPath();pts.forEach(([x,y],i)=>{const p:Point=[pixel(x*CELL+dx),pixel(y*CELL+dy)];if(i)ctx.lineTo(...p);else ctx.moveTo(...p)})}
  const shape=(rs:Point[][],dy=0,dx=0)=>{ctx.beginPath();for(const r of rs){path(r,dy,dx,false);ctx.closePath()}}
  const polygon=(rs:Point[][],fill:string,dy=0,dx=0)=>{shape(rs,dy,dx);ctx.fillStyle=fill;ctx.fill('evenodd')}
  const stroke=(pts:Point[],width:number,color:string)=>{path(pts);ctx.lineJoin='round';ctx.lineCap='round';ctx.lineWidth=width;ctx.strokeStyle=color;ctx.stroke()}
  const object=(x:number,y:number,w:number,h:number,depth:number,paint:()=>void,grid=2)=>{
    const left=Math.floor(x/grid)*grid,top=Math.floor(y/grid)*grid
    w+=x-left;h+=y-top;x=left;y=top
    const canvas=document.createElement('canvas');canvas.width=Math.ceil(w);canvas.height=Math.ceil(h)
    ctx=canvas.getContext('2d')!;ctx.imageSmoothingEnabled=false;ctx.translate(-x,-y);paint();pixelateCanvas(canvas,grid);ctx=ground
    objects.push({canvas,x,y,depth})
  }
  // Quiet ground and irregular grass tufts keep the silhouettes readable.
  ctx.fillStyle='#324f43';ctx.fillRect(0,0,size,size)
  ctx.fillStyle='#718963';ctx.fillRect(west*CELL,north*CELL,(east-west)*CELL,(south-north)*CELL)
  for(let y=north*CELL;y<south*CELL-12;y+=12)for(let x=west*CELL;x<east*CELL-12;x+=12){const n=hash(Math.round(x),Math.round(y));if(n%7<2){ctx.fillStyle=n%2?'#748c66':'#6f875f';ctx.fillRect(x,y,12,12)}if(n%29===0){ctx.fillStyle='#83986e';ctx.fillRect(x+2,y+4,4,2)}}
  for(const f of g.greens)if(f.geometry.type==='Polygon'){
    polygon(rings(f),'#7f986b');ctx.save();shape(rings(f));ctx.clip('evenodd')
    const r=ring(f),xs=r.map(p=>p[0]*CELL),ys=r.map(p=>p[1]*CELL)
    for(let y=Math.min(...ys);y<Math.max(...ys);y+=15)for(let x=Math.min(...xs);x<Math.max(...xs);x+=17){const n=hash(Math.round(x),Math.round(y));if(n%5===0){ctx.fillStyle=n%3?'#849c70':'#789263';ctx.fillRect(pixel(x),pixel(y),4,2)}}ctx.restore()
  }
  for(const f of g.water)if(f.geometry.type==='Polygon'){
    polygon(rings(f),'#b2b093');for(const r of rings(f))stroke(r,12,'#b0af8c');polygon(rings(f),'#537f83');for(const r of rings(f))stroke(r,3,'#3f6970')
    const r=ring(f),xs=r.map(p=>p[0]),ys=r.map(p=>p[1]);for(let y=Math.min(...ys);y<Math.max(...ys);y+=.28)for(let x=Math.min(...xs);x<Math.max(...xs);x+=.5)if(inFeature([x,y],f)&&hash(Math.round(x*100),Math.round(y*100))%3===0){ctx.fillStyle='#83a6a3';ctx.fillRect(pixel(x*CELL),pixel(y*CELL),8,2)}
  }
  paintCampusSurfaces(ctx,city)

  const buildings=[...g.buildings].sort((a,b)=>Math.max(...ring(a).map(p=>p[1]))-Math.max(...ring(b).map(p=>p[1])))
  for(const f of buildings){
    const rs=campusBuildingRings(f),r=rs[0],n=stableHash(String(f.id)),home=campusBuildingHome(f),lift=campusBuildingLift(f)
    const xs=r.map(p=>p[0]*CELL),ys=r.map(p=>p[1]*CELL),left=Math.min(...xs),right=Math.max(...xs),top=Math.min(...ys),bottom=Math.max(...ys)
    // Shadows belong on the ground; the facade/roof itself joins the depth layer.
    polygon(rs,'#586d51',8,6)
    const roof=rs.map(part=>part.map(([x,y]):Point=>[x,y-lift/CELL]))
    object(Math.floor(left)-4,Math.floor(top)-lift-50,right-left+12,bottom-top+lift+60,bottom,()=>{
      const brick=home?['#ac8a6d','#b59b7b','#99775d'][n%3]:['#a57961','#ae9474','#967862'][n%3]
      polygon(rs,brick)
      const winding=r.reduce((sum,a,i)=>{const b=r[(i+1)%r.length];return sum+a[0]*b[1]-b[0]*a[1]},0)
      for(const part of rs)for(let j=0;j<part.length-1;j++){const a=part[j],b=part[j+1];if((b[0]-a[0])*winding<0){
        const ar:Point=[a[0],a[1]-lift/CELL],br:Point=[b[0],b[1]-lift/CELL]
        polygon([[a,b,br,ar]],brick)
        // A low stone sill and masonry band articulate the visible facade.
        stroke([a,b],2,'#c4b391');stroke([ar,br],3,'#665f50')
        const length=Math.hypot((b[0]-a[0])*CELL,(b[1]-a[1])*CELL)
        for(let k=9;k<length-6;k+=home?14:16){const t=k/length,x=(a[0]+(b[0]-a[0])*t)*CELL,y=(a[1]+(b[1]-a[1])*t)*CELL
          ctx.fillStyle='#566a65';ctx.fillRect(pixel(x)-2,pixel(y)-lift+5,4,home?5:8);ctx.fillStyle='#d8c8a2';ctx.fillRect(pixel(x)-2,pixel(y)-lift+(home?10:13),4,2)
          if(lift>=30){ctx.fillStyle='#4a625d';ctx.fillRect(pixel(x)-2,pixel(y)-12,4,7);ctx.fillStyle='#ceb994';ctx.fillRect(pixel(x)-2,pixel(y)-5,4,2)}
        }
      }}
      polygon(roof,home?['#706d60','#817561','#777e71','#8b6e5c'][n%4]:['#b3b39b','#aaa990','#a8b09d','#96a497'][n%4])
      shape(roof);ctx.strokeStyle=home?'#525d52':'#747c68';ctx.lineWidth=3;ctx.stroke()
      ctx.save();shape(roof);ctx.clip('evenodd')
      if(home){
        const mid=(top+bottom)/2-lift
        ctx.fillStyle='#a2987c';ctx.fillRect(left,mid, right-left,2)
        ctx.fillStyle='#45584922';ctx.fillRect(left,mid+2,right-left,bottom-mid)
        for(let y=top-lift+5;y<bottom-lift;y+=9){ctx.fillStyle='#c2b69325';ctx.fillRect(left,y,right-left,1)}
        if(right-left>30){ctx.fillStyle='#735b49';ctx.fillRect(left+8,top-lift+7,6,10);ctx.fillStyle='#a99073';ctx.fillRect(left+7,top-lift+6,8,3)}
      } else {
        // Broad quiet roof planes replace dozens of bright horizontal stripes.
        ctx.fillStyle='#c6c3a6';ctx.fillRect(left+4,top-lift+4,right-left-8,2)
        ctx.fillStyle='#77867133';ctx.fillRect(left+7,bottom-lift-7,right-left-14,3)
        if(right-left>60&&bottom-top>40){const x=pixel(left+14),y=pixel(top-lift+14);ctx.fillStyle='#7e8b7c';ctx.fillRect(x+2,y+3,20,12);ctx.fillStyle='#c4c5ad';ctx.fillRect(x,y,18,11);ctx.fillStyle='#89968b';ctx.fillRect(x+4,y+3,10,5)}
        if(right-left>130&&bottom-top>80){ctx.fillStyle='#7d8d81';ctx.fillRect(right-36,bottom-lift-28,20,12);ctx.fillStyle='#bac4b4';ctx.fillRect(right-35,bottom-lift-29,18,4)}
      }
      ctx.restore()
      if(/Orton Hall/i.test(f.name??'')){
        const x=pixel((left+right)/2),y=pixel(top-lift+16)
        ctx.fillStyle='#6d6250';ctx.fillRect(x-13,y-35,26,46);ctx.fillStyle='#b39a76';ctx.fillRect(x-11,y-35,22,43)
        ctx.fillStyle='#c7b58d';ctx.fillRect(x-14,y-39,28,5);ctx.fillStyle='#47534d';ctx.fillRect(x-8,y-30,5,9);ctx.fillRect(x+3,y-30,5,9)
        ctx.fillStyle='#e0d5af';ctx.fillRect(x-5,y-15,10,10);ctx.fillStyle='#4e5b50';ctx.fillRect(x,y-14,1,5);ctx.fillRect(x,y-10,4,1)
      }
    })
  }
  // Entrances are ground-level route endpoints, never extra invented buildings.
  for(const p of city.places??[]){if(p.kind==='park'||(p as typeof p&{is_portal?:boolean}).is_portal)continue;const [x,y]=p.entrance;ctx.fillStyle='#acac8d';ctx.fillRect(pixel(x*CELL)-5,pixel(y*CELL)-2,10,4)}
  const obstacles=[...g.buildings,...g.water].filter(f=>f.geometry.type==='Polygon'),lines=[...g.roads,...g.paths].filter(f=>f.geometry.type!=='Polygon').map(ring)
  const clear=(p:Point)=>!obstacles.some(f=>inFeature(p,f))&&!g.paths.some(f=>f.geometry.type==='Polygon'&&inFeature(p,f))&&!lines.some(r=>r.some((a,i)=>i&&distance(p,r[i-1],a)<.3))
  const mappedTrees=(g as unknown as {trees?:{geometry:{coordinates:Point}}[]}).trees
  const trees:Point[]=mappedTrees?mappedTrees.map(f=>f.geometry.coordinates).filter(p=>!obstacles.some(f=>inFeature(p,f))):[]
  // Archived maps without point data retain a sparse authored fallback. New
  // snapshots use the pinned OSM tree positions rather than invented forests.
  if(!mappedTrees)for(let y=north+.6;y<south-.6;y+=.75)for(let x=west+.6;x<east-.6;x+=.78){const n=hash(Math.round(x*100),Math.round(y*100));if(n%4!==0)continue;const p:Point=[x+(n%17)/60,y+(n%11)/55];if(clear(p))trees.push(p)}
  for(const [x,y] of trees){const n=hash(Math.round(x*100),Math.round(y*100)),scale=.7+n%4*.09,px=x*CELL,py=y*CELL
    object(Math.floor(px-24),Math.floor(py-50),50,54,py,()=>{drawArt(ctx,art,n%13===0?'pine':n%3===0?'oak':`oak${n%3}`,px-20*scale,py-45*scale,scale)
      ctx.save();ctx.globalCompositeOperation='source-atop';ctx.fillStyle=['#b5b76b18','#386c541a','#8fa56320','#d2c27a14'][n%4];ctx.fillRect(px-24,py-50,50,54);ctx.restore()})
  }
  for(const p of city.places??[])if(p.kind==='park'){
    const x=p.entrance[0]*CELL,y=p.entrance[1]*CELL
    object(x-17,y-13,38,24,y,()=>drawArt(ctx,art,'bench',x-16,y-10,.65))
  }
  // Labels have their own quiet foreground plane, rather than being cut by roofs.
  const label=(name:string,x:number,y:number,large=false)=>{
    ctx.font=`600 ${large?20:17}px 'Pixelify Sans'`;const width=Math.ceil(ctx.measureText(name).width)+12
    object(x-width/2,y-12,width,26,99990,()=>{ctx.textAlign='center';ctx.textBaseline='middle';ctx.font=`600 ${large?20:17}px 'Pixelify Sans'`;ctx.lineWidth=4;ctx.strokeStyle='#536c55';ctx.strokeText(name,x,y);ctx.fillStyle=large?'#e0dfbc':'#eee6c6';ctx.fillText(name,x,y)},1)
  }
  for(const f of buildings){if(!f.name||(!/Thompson|Pomerene|Orton Hall/i.test(f.name)&&f.name!=='Ohio Union'))continue;const r=ring(f),x=r.reduce((s,p)=>s+p[0],0)/r.length*CELL,y=Math.min(...r.map(p=>p[1]))*CELL-48;label(/Thompson/.test(f.name)?'Thompson Library':f.name,x,y)}
  for(const n of city.neighborhoods)label(n.name,n.position[0]*CELL,n.position[1]*CELL,true)
  return objects
}
