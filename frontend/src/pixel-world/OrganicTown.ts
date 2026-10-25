import {CELL,drawArt,hash,type TownArt} from './Art'
import {bounds,type LivingCity,type TownPlace} from './TownLifeTypes'

const key=(x:number,y:number)=>`${x},${y}`

/** Paint only the new canonical map. Art never creates buildings, paths or water cells. */
export function paintOrganicTown(ctx:CanvasRenderingContext2D,city:LivingCity,art:TownArt) {
  const water=new Set(city.river.map(([x,y])=>key(x,y)))
  const roads=new Set(city.roads.map(([x,y])=>key(x,y)))
  const style=new Map((city.road_styles??[]).map(s=>[key(...s.position),s.kind]))
  const places=city.places??[]
  const occupied=new Set(places.flatMap(p=>p.footprint.map(([x,y])=>key(x,y))))
  const solid=(x:number,y:number)=>water.has(key(x,y))||roads.has(key(x,y))||occupied.has(key(x,y))
  const rect=(x:number,y:number,w:number,h:number,color:string)=>{ctx.fillStyle=color;ctx.fillRect(Math.round(x),Math.round(y),Math.round(w),Math.round(h))}
  const tree=(x:number,y:number,name='oak',scale=1)=>drawArt(ctx,art,name,x-(name==='willow'?28:20)*scale,y-(name==='willow'?62:45)*scale,scale)
  // Crisp, low-noise meadow and an actual meandering river mask.
  for(let y=0;y<city.size*4;y++)for(let x=0;x<city.size*4;x++) {
    const wet=water.has(key(Math.floor(x/4),Math.floor(y/4)))
    drawArt(ctx,art,`${wet?'water':'grass'}${hash(x,y)%4}`,x*16,y*16)
    if(!wet&&hash(Math.floor(x/12),Math.floor(y/12))%7===0)rect(x*16,y*16,16,16,'#8d9e6819')
  }
  // Pixel-stepped banks remain inside the authoritative water footprint.
  for(const [x,y] of city.river) {
    const px=x*CELL,py=y*CELL
    const n=!water.has(key(x,y-1)),e=!water.has(key(x+1,y)),s=!water.has(key(x,y+1)),w=!water.has(key(x-1,y))
    if(n){rect(px,py,64,6,'#c4bb90');rect(px,py+6,64,3,'#648d7b')}
    if(s){rect(px,py+58,64,6,'#8c9d70');rect(px,py+55,64,3,'#648d7b')}
    if(w){rect(px,py,6,64,'#b4b48a');rect(px+6,py,3,64,'#648d7b')}
    if(e){rect(px+58,py,6,64,'#c4bb90');rect(px+55,py,3,64,'#648d7b')}
    for(const [horizontal,vertical,cx,cy] of [[w,n,px,py],[e,n,px+64,py],[w,s,px,py+64],[e,s,px+64,py+64]] as const)if(horizontal&&vertical) {
      const sx=cx===px?1:-1,sy=cy===py?1:-1
      for(let i=0;i<4;i++)rect(cx+(sx<0?-1:0)+sx*i*4-(sx<0?3:0),cy+(sy<0?-1:0)+sy*6-(sy<0?5:0),4,22-i*4,'#a9aa7b')
    }
  }
  // Each arm follows a real graph edge. End caps and bends never imply new links.
  for(const [x,y] of city.roads) {
    const px=(x+.5)*CELL,py=(y+.5)*CELL,kind=style.get(key(x,y))??'path'
    const width=kind==='path'?20:36,border=kind==='path'?4:8
    const neighbors=[[1,0],[-1,0],[0,1],[0,-1]].filter(([dx,dy])=>roads.has(key(x+dx,y+dy)))
    const stroke=(w:number,color:string)=> {
      rect(px-w/2,py-w/2,w,w,color)
      for(const [dx,dy] of neighbors) {
        if(dx)rect(dx>0?px:px-32,py-w/2,32,w,color)
        else rect(px-w/2,dy>0?py:py-32,w,32,color)
      }
    }
    stroke(width+border*2,kind==='path'?'#7d8b60':'#a4ac91')
    stroke(width,kind==='path'?'#b9b187':kind==='bridge'?'#a18c65':'#65736b')
    if(kind==='path') {
      const v=hash(x,y)
      rect(px-7+(v%6),py-5,3,2,'#d3c59b');rect(px+4,py+3,4,2,'#9b9e76')
    } else if(kind==='road') {
      if(neighbors.length===2&&neighbors[0][0]===-neighbors[1][0]&&neighbors[0][1]===-neighbors[1][1]) {
        if(neighbors[0][0])rect(px-8,py-1,16,2,'#c5b994');else rect(px-1,py-8,2,16,'#c5b994')
      }
    } else {
      const horizontal=neighbors.some(n=>n[0]!==0)
      for(let d=-28;d<32;d+=8)if(horizontal)rect(px+d,py-18,2,36,'#716a50');else rect(px-18,py+d,36,2,'#716a50')
      if(horizontal) {rect(px-32,py-26,64,4,'#e0ce9d');rect(px-32,py+22,64,4,'#e0ce9d')}
      else {rect(px-26,py-32,4,64,'#e0ce9d');rect(px+22,py-32,4,64,'#e0ce9d')}
    }
  }
  // Lots and entrance steps are grounded in explicit canonical footprints.
  for(const place of [...places].sort((a,b)=>a.position[1]-b.position[1])) {
    const b=bounds(place),x=b.x*CELL,y=b.y*CELL,w=b.w*CELL,h=b.h*CELL
    if(place.kind==='park') {
      for(const [cx,cy] of place.footprint)rect(cx*CELL+3,cy*CELL+3,58,58,'#7c975f')
      const midX=x+w/2,midY=y+h/2
      drawArt(ctx,art,'fountain',midX-24,midY-24)
      for(const [tx,ty] of [[x+22,y+40],[x+w-22,y+40],[x+22,y+h-15],[x+w-22,y+h-15]])tree(tx,ty,'oak')
      drawArt(ctx,art,'bench',x+12,y+h/2+8);drawArt(ctx,art,'bench',x+w-60,y+h/2+8)
      entranceSteps(place,x+w/2,y+h/2)
      continue
    }
    const farm=place.kind==='work'&&/farm|orchard|garden|mill/i.test(place.name)
    for(const [cx,cy] of place.footprint) {
      const paved=place.kind==='civic'||place.kind==='school'||place.kind==='shelter'
      if(paved)for(let ty=0;ty<4;ty++)for(let tx=0;tx<4;tx++)drawArt(ctx,art,'stone0',cx*CELL+tx*16,cy*CELL+ty*16)
      else if(farm)rect(cx*CELL+3,cy*CELL+3,58,58,'#96925e')
    }
    const asset=place.kind==='home'?`house${place.variant%4}`:place.kind==='shop'?'market':place.kind==='school'?'school':place.kind==='civic'||place.kind==='shelter'?'townhall':farm?'barn':'workshop'
    const f=art.frames[asset],fit=Math.min(1,(w-8)/f.w,(h-12)/f.h)
    const sx=x+(w-f.w*fit)/2,sy=y+(h-f.h*fit)/2
    // Pixel assets remain unclipped where footprints are rectangular, and never cover paths.
    ctx.save();ctx.beginPath();for(const [cx,cy] of place.footprint)ctx.rect(cx*CELL,cy*CELL,CELL,CELL);ctx.clip()
    // Facades stay upright: turning a quasi-top-down image makes windows sideways.
    // The canonical entrance may be at the rear/side; its real steps show that side.
    drawArt(ctx,art,asset,sx,sy,fit)
    ctx.restore()
    entranceSteps(place,x+w/2,y+h/2)
    if(place.kind==='home') {
      // A pair of real footprint-side garden details; never new house objects.
      drawArt(ctx,art,'flowers',x+w-43,y+h-35,.65)
      if(w>=128&&h>=128)drawArt(ctx,art,'bush',x+2,y+h-41,.7)
    }
    if(farm&&w>=128) {
      for(let fy=y+h-29;fy<y+h-6;fy+=7)for(let fx=x+12;fx<x+w-12;fx+=9) {
        rect(fx,fy,5,4,'#4e7350');rect(fx+1,fy-2,3,3,'#b6ac62')
      }
    }
    if(place.kind==='shop')for(let i=0;i<Math.floor(w/54);i++)drawArt(ctx,art,'stall',x+6+i*52,y+h-44,.8)
  }
  // Natural groves are decoration in unoccupied land, not fictitious settlements.
  for(let y=0;y<city.size;y++)for(let x=0;x<city.size;x++) {
    if(solid(x,y))continue
    const v=hash(x,y),nearRoad=[[-1,0],[1,0],[0,-1],[0,1]].some(([dx,dy])=>roads.has(key(x+dx,y+dy)))
    const nearWater=[[-1,0],[1,0],[0,-1],[0,1]].some(([dx,dy])=>water.has(key(x+dx,y+dy)))
    const patch=(Math.sin(x*.41)+Math.cos(y*.34)+Math.sin((x+y)*.19))
    if(nearRoad) {
      if(v%5===0)tree(x*CELL+27,y*CELL+45,nearWater?'willow':'oak')
      if(v%17===0)drawArt(ctx,art,'flowers',x*CELL+9,y*CELL+20,.8)
    } else if(patch>-.6&&v%5!==0) {
      const count=patch>.7?3:2
      for(let j=0;j<count;j++) {
        const tx=x*CELL+14+(hash(v,j)%35),ty=y*CELL+28+(hash(j,v)%31)
        tree(tx,ty,nearWater?'willow':v%3?'oak':'pine',.85+(v%3)*.1)
      }
    } else if(v%7===0)drawArt(ctx,art,'flowers',x*CELL+6,y*CELL+25,.65)
  }
  // Only a few stationary riverside moorings, always on actual water cells.
  for(const [x,y] of city.river)if(hash(x,y)%127===0&&!roads.has(key(x,y))&&[[-1,0],[1,0]].some(([dx,dy])=>!water.has(key(x+dx,y+dy))))drawArt(ctx,art,'boat',x*CELL+7,y*CELL+12,.9)
  for(const s of city.road_styles??[])if(s.kind==='road'&&hash(...s.position)%9===0)drawArt(ctx,art,'lamp',s.position[0]*CELL+37,s.position[1]*CELL-4,.65)

  function entranceSteps(place:TownPlace,cx:number,cy:number) {
    const ex=(place.entrance[0]+.5)*CELL,ey=(place.entrance[1]+.5)*CELL
    const b=bounds(place),left=b.x*CELL,top=b.y*CELL,right=(b.x+b.w)*CELL,bottom=(b.y+b.h)*CELL
    const dx=ex<left?left:ex>right?right:ex,dy=ey<top?top:ey>bottom?bottom:ey
    const color=place.kind==='home'?'#c4b68b':'#b4b398'
    // The visible steps end at the logical entrance; no resident is tweened through them.
    if(Math.abs(ex-dx)>Math.abs(ey-dy))rect(Math.min(ex,dx),ey-8,Math.abs(ex-dx),16,color)
    else rect(ex-8,Math.min(ey,dy),16,Math.abs(ey-dy),color)
    if(place.kind==='park') {
      if(Math.abs(ex-cx)>Math.abs(ey-cy))rect(Math.min(ex,cx),cy-7,Math.abs(ex-cx),14,color)
      else rect(cx-7,Math.min(ey,cy),14,Math.abs(ey-cy),color)
    }
  }
}
