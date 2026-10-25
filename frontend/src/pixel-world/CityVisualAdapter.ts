import {Texture} from 'pixi.js'
import type {City} from '../types'
import {ART_VERSION,CELL,drawArt,hash,type TownArt} from './Art'
import {paintCampusTown} from './CampusTown'
import {packCampusScenery} from './CampusScenery'
import {paintOrganicTown} from './OrganicTown'
import type {LivingCity} from './TownLifeTypes'
import {pixelateCanvas} from './PixelCanvas'

const cache=new Map<string,{texture:Texture;scenery:ReturnType<typeof packCampusScenery>|null;users:number}>()
const key=(x:number,y:number)=>`${x},${y}`

/** Authored decorative placement consumes the real road/river mask. Never routing data. */
export function acquireTown(city:City,art:TownArt) {
  const living=city as LivingCity
  const identity=JSON.stringify([ART_VERSION,city.size,city.roads,city.river,city.buildings,living.world_version,city.campus_geometry,living.places,living.road_styles])
  let cached=cache.get(identity)
  if (!cached) {
    const canvas=document.createElement('canvas')
    canvas.width=canvas.height=city.size*CELL
    const ctx=canvas.getContext('2d')!
    ctx.imageSmoothingEnabled=false
    let scenery:ReturnType<typeof packCampusScenery>|null=null
    if(city.layout==='campus'&&city.campus_geometry)scenery=packCampusScenery(paintCampusTown(ctx,city,art))
    else if(living.layout==='organic'&&living.places)paintOrganicTown(ctx,living,art)
    else {
    const roads=new Set(city.roads.map(([x,y])=>key(x,y)))
    const river=new Set(city.river.map(([x,y])=>key(x,y)))
    const isRoad=(x:number,y:number)=>roads.has(key(x,y))
    const isWater=(x:number,y:number)=>river.has(key(x,y))
    const rect=(x:number,y:number,w:number,h:number,c:string)=>{ctx.fillStyle=c;ctx.fillRect(x,y,w,h)}
    // Ground is four 16-pixel tiles along each logic-cell edge: 25,600 placements.
    for(let y=0;y<city.size*4;y++)for(let x=0;x<city.size*4;x++) {
      const water=isWater(Math.floor(x/4),Math.floor(y/4))
      drawArt(ctx,art,`${water?'water':'grass'}${hash(x,y)%4}`,x*16,y*16)
    }
    // Real orthogonal graph roads, expressed as streets with curbs and sidewalks.
    for(const [x,y] of city.roads) {
      const px=x*CELL,py=y*CELL
      const horizontal=isRoad(x-1,y)||isRoad(x+1,y)
      const vertical=isRoad(x,y-1)||isRoad(x,y+1)
      if(horizontal) {rect(px,py+5,64,54,'#5c6b58');rect(px,py+7,64,50,'#b0b39b');rect(px,py+13,64,38,'#606e6a')}
      if(vertical) {rect(px+5,py,54,64,'#5c6b58');rect(px+7,py,50,64,'#b0b39b');rect(px+13,py,38,64,'#606e6a')}
      if(horizontal&&!vertical) {rect(px+10,py+30,17,2,'#b9b48e');rect(px+44,py+30,17,2,'#b9b48e')}
      if(vertical&&!horizontal) {rect(px+30,py+10,2,17,'#b9b48e');rect(px+30,py+44,2,17,'#b9b48e')}
      if(horizontal&&vertical) {
        // Pedestrian crossings do not introduce new path nodes.
        for(let j=0;j<5;j++) {rect(px+7+j*10,py+7,6,5,'#d5d0ae');rect(px+7+j*10,py+52,6,5,'#d5d0ae');rect(px+7,py+8+j*10,5,6,'#d5d0ae');rect(px+52,py+8+j*10,5,6,'#d5d0ae')}
      }
      if(isWater(x,y)) {
        rect(px,py+2,64,7,'#324d50');rect(px,py+5,64,3,'#c0b790')
        rect(px,py+56,64,7,'#324d50');rect(px,py+56,64,3,'#c0b790')
        for(let j=4;j<64;j+=16) {rect(px+j,py+1,4,9,'#e4d6ad');rect(px+j,py+55,4,9,'#e4d6ad')}
      }
    }
    // Waterfront embankment stays at the actual river boundary, bridges unobstructed.
    for(let y=0;y<city.size;y++)for(let x=0;x<city.size;x++)if(isWater(x,y)&&!isRoad(x,y)) {
      if(!isWater(x-1,y)) {rect(x*CELL,y*CELL,8,64,'#365e5b');rect(x*CELL,y*CELL,3,64,'#bcb48f')}
      if(!isWater(x+1,y)) {rect((x+1)*CELL-8,y*CELL,8,64,'#365e5b');rect((x+1)*CELL-3,y*CELL,3,64,'#bcb48f')}
    }
    const streets=[...new Set(city.roads.filter(([,y])=>y===1).map(([x])=>x))].sort((a,b)=>a-b)
    const bounds=[-1,...streets,city.size]
    const drawTree=(x:number,y:number,pine=false)=>drawArt(ctx,art,pine?'pine':'oak',x-20,y-45)
    // Coherent blocks: residential gardens, town squares, an orchard, school/civic district.
    for(let by=0;by<bounds.length-1;by++)for(let bx=0;bx<bounds.length-1;bx++) {
      const left=(bounds[bx]+1)*CELL,top=(bounds[by]+1)*CELL
      const w=(bounds[bx+1]-bounds[bx]-1)*CELL,h=(bounds[by+1]-bounds[by]-1)*CELL
      if(w<90||h<90||isWater(Math.floor((left+w/2)/CELL),Math.floor((top+h/2)/CELL)))continue
      const block=hash(bx,by),park=(bx===1&&by===2)||(bx===5&&by===4)||(bx===1&&by===5)
      // All placements must fit within the non-road/non-river block.
      const minX=left+12,maxX=left+w-12,minY=top+12,maxY=top+h-12
      if(park) {
        rect(left+12,top+12,w-24,h-24,'#708c59')
        rect(left+w/2-8,top+12,16,h-24,'#b8b18a');rect(left+12,top+h/2-7,w-24,14,'#b8b18a')
        drawArt(ctx,art,'fountain',left+w/2-24,top+h/2-24,1.3)
        for(let ty=top+45;ty<maxY;ty+=62)for(let tx=left+40;tx<maxX;tx+=64)if(Math.abs(tx-(left+w/2))>26&&Math.abs(ty-(top+h/2))>24)drawTree(tx,ty)
        for(const [tx,ty] of [[left+24,top+h/2+18],[left+w-62,top+h/2+18]])drawArt(ctx,art,'bench',tx,ty)
        continue
      }
      const landmark=bx===1&&by===1?'school':bx===5&&by===2?'townhall':bx===2&&by===2?'market':null
      if(landmark&&w>=300&&h>=300) {
        rect(left+18,top+18,w-36,h-36,'#a5aa85')
        for(let ty=top+20;ty<top+h-20;ty+=16)for(let tx=left+20;tx<left+w-20;tx+=16)drawArt(ctx,art,'stone0',tx,ty)
        drawArt(ctx,art,landmark,left+(w-192)/2,top+25)
        if(landmark==='school') {
          rect(left+60,top+207,200,76,'#7d9583');rect(left+62,top+209,196,72,'#628579')
          ctx.strokeStyle='#c7c9a3';ctx.lineWidth=2;ctx.strokeRect(left+72,top+218,176,53)
          ctx.beginPath();ctx.moveTo(left+w/2,top+218);ctx.lineTo(left+w/2,top+271);ctx.stroke()
          ctx.beginPath();ctx.arc(left+w/2,top+244,15,0,Math.PI*2);ctx.stroke()
        } else if(landmark==='market') {
          for(const tx of [left+36,left+104,left+172,left+240])drawArt(ctx,art,'stall',tx,top+215)
        } else {
          drawArt(ctx,art,'fountain',left+w/2-24,top+216)
          drawArt(ctx,art,'bench',left+55,top+220);drawArt(ctx,art,'bench',left+w-101,top+220)
        }
        for(const [tx,ty] of [[left+30,top+65],[left+w-26,top+65],[left+28,top+h-25],[left+w-28,top+h-25]])drawTree(tx,ty)
        continue
      }
      // Narrow river-adjacent blocks are gardens/quays, never half buildings in water.
      const slots:Array<{x:number;y:number;name:string}>=[]
      for(let sy=top+10;sy+112<maxY;sy+=136)for(let sx=left+10;sx+112<maxX;sx+=136) {
        const cx=Math.floor((sx+56)/CELL),cy=Math.floor((sy+56)/CELL)
        if(isWater(cx,cy)||isWater(Math.floor((sx+110)/CELL),cy))continue
        let name=`house${hash(cx,cy)%4}`
        if(by>=4)name=`cottage${hash(cx,cy)%4}`
        if((bx===2||bx===4)&&by===2)name=`shop${(cx+cy)%2}`
        if(bx===5&&by===1)name='warehouse'
        if(bx===1&&by===1&&slots.length===0)name='civic'
        slots.push({x:sx,y:sy,name})
      }
      for(const slot of slots) {
        // Stone footpath, low garden fence, flowers and shrubs before each facade.
        rect(slot.x+47,slot.y+93,18,26,'#b8b18a')
        rect(slot.x+3,slot.y+108,35,2,'#a3b08a');rect(slot.x+76,slot.y+108,31,2,'#a3b08a')
        for(let f=slot.x+3;f<slot.x+108;f+=8)if(f<slot.x+40||f>slot.x+75)rect(f,slot.y+104,2,8,'#c6c5a3')
        drawArt(ctx,art,slot.name,slot.x,slot.y)
        drawArt(ctx,art,'flowers',slot.x+72,slot.y+88,.7)
        if(hash(slot.x,slot.y)%3===0)drawTree(slot.x+104,slot.y+64)
      }
      // Block edge vegetation, with deliberate gaps at paths and doors.
      for(let tx=minX+20;tx<maxX;tx+=55)if(hash(tx,top)%3===0)drawTree(tx,top+28,by===0)
      for(let ty=minY+70;ty<maxY;ty+=81)if(hash(left,ty)%2===0)drawTree(left+15,ty)
      if(block%3===0)drawArt(ctx,art,'bench',left+w/2-24,top+h-48)
    }
    // Street furniture and parked cars use curb space, never decorative traffic.
    for(const [x,y] of city.roads) {
      if(isWater(x,y))continue
      const horizontal=isRoad(x-1,y)&&isRoad(x+1,y),vertical=isRoad(x,y-1)&&isRoad(x,y+1)
      if(horizontal&&!vertical&&x%3===1)drawArt(ctx,art,'lamp',x*CELL+6,y*CELL-15,.8)
      if(vertical&&!horizontal&&y%5===2)drawArt(ctx,art,`car${hash(x,y)%2}`,x*CELL+31,y*CELL+6,.65)
    }
    // Quays, moorings and riparian trees remain decoration outside the graph.
    for(const x of [17,21])for(let y=1;y<city.size-1;y++)if(!isRoad(x,y)) {
      rect(x*CELL+17,y*CELL,30,64,'#b6b08a')
      if(y%3===1) {drawArt(ctx,art,'lamp',x*CELL+8,y*CELL+6);drawArt(ctx,art,'bench',x*CELL+5,y*CELL+30)}
      if(y%4===2)drawTree(x*CELL+10,y*CELL+35)
    }
    for(const [x,y] of [[18,12],[20,22],[18,31]])drawArt(ctx,art,'boat',x*CELL+8,y*CELL+12)
    // Parkland beyond the outer ring roads keeps the composition inhabited to its edge.
    for(let y=0;y<city.size;y++)for(let x=0;x<city.size;x++)if((x<2||x>37||y<2||y>37)&&!isRoad(x,y)&&!isWater(x,y)&&hash(x,y)%3!==0)drawTree(x*CELL+25,y*CELL+43,(x+y)%2===0)
    }
    if(city.layout==='campus')pixelateCanvas(canvas)
    const texture=Texture.from(canvas)
    texture.source.scaleMode='nearest'
    cached={texture,scenery,users:0};cache.set(identity,cached)
  }
  cached.users++
  return {texture:cached.texture,scenery:cached.scenery?.sprites??[],release() {
    const current=cache.get(identity)
    if(current&&--current.users===0) {current.texture.destroy(true);current.scenery?.destroy();cache.delete(identity)}
  }}
}
