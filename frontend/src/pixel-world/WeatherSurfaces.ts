import {Container,Sprite,Texture} from 'pixi.js'
import type {CampusFeature,City,Point} from '../types'
import {CELL,hash} from './Art'
import {campusBuildingLift,campusBuildingRings,pointInRing} from './CampusBuildings'
import {campusTraces} from './CampusSurfaces'
import {packCampusScenery} from './CampusScenery'
import type {CampusDecoration} from './CampusTown'
import {pixelateCanvas,hardenMask} from './PixelCanvas'

const pixel=(n:number)=>Math.round(n/2)*2
const clamp=(n:number)=>Math.max(0,Math.min(1,Number.isFinite(n)?n:0))
/** Twelve stable accumulation stages; seeking changes appearance, never terrain. */
export const snowLevel=(amount:number)=>Math.round(clamp(amount)*12)/12
export function snowRoof(feature:CampusFeature):Point[][] {
  const lift=campusBuildingLift(feature)/CELL
  return campusBuildingRings(feature).map(ring=>ring.map(([x,y]):Point=>[x,y-lift]))
}
const path=(ctx:CanvasRenderingContext2D,points:Point[],snap=false)=>{
  points.forEach(([x,y],i)=>{const px=snap?pixel(x*CELL):x*CELL,py=snap?pixel(y*CELL):y*CELL;i?ctx.lineTo(px,py):ctx.moveTo(px,py)})
}
const polygon=(ctx:CanvasRenderingContext2D,rings:Point[][],snap=false)=>{
  ctx.beginPath();for(const ring of rings){path(ctx,ring,snap);ctx.closePath()}
}
const roadWidth=(kind:string)=>kind==='primary'?28:kind==='secondary'?26:kind==='tertiary'?24:kind==='service'?8:18
const pathWidth=(kind:string)=>kind==='entrance_connector'?4:kind==='steps'?6:kind==='pedestrian'?10:kind==='cycleway'?7:kind==='living_street'?12:7

/** Persistent snow belongs to physical surfaces, below people and vehicles.
 * It is a visual accumulation amount, not a claim of measured snow depth or
 * plowed roads. Geometry is painted once; subsequent frames alter opacity only.
 */
export class WeatherSurfaces {
  readonly ground=new Container()
  readonly roofs=new Container()
  private level=-1
  private built=false
  private groundTexture:Texture|null=null
  private atlas:ReturnType<typeof packCampusScenery>|null=null
  private caps:Sprite[]=[]
  private disposed=false
  constructor(private city:City,private depthRoot?:Container){
    this.ground.eventMode='none';this.roofs.eventMode='none'
    this.ground.visible=this.roofs.visible=false
  }
  setSnow(amount:number){
    if(this.disposed)return
    const level=snowLevel(amount)
    if(level===this.level)return
    this.level=level
    if(level>0&&!this.built)this.build()
    this.ground.visible=this.roofs.visible=level>0
    // First flakes catch on raised surfaces; a broad ground blanket follows.
    this.ground.alpha=Math.pow(level,1.18)*.94
    const raised=Math.min(.97,Math.pow(level,.8)*.97)
    this.roofs.alpha=raised
    for(const cap of this.caps){cap.visible=level>0;cap.alpha=this.depthRoot?raised:1}
  }
  private build(){
    this.built=true
    const city=this.city,size=city.size*CELL,geometry=city.campus_geometry
    // Half-resolution snow uses a deliberate two-pixel material grain and
    // avoids another full-size terrain framebuffer per comparison root.
    const canvas=document.createElement('canvas');canvas.width=canvas.height=Math.ceil(size/2)
    const ctx=canvas.getContext('2d')!;ctx.scale(.5,.5);ctx.imageSmoothingEnabled=false
    const [west,north,east,south]=(city.map_bounds??[0,0,city.size,city.size]).map(v=>v*CELL)
    ctx.fillStyle='#d9e2de';ctx.fillRect(west,north,east-west,south-north)
    // Wind-packed flecks and low drifts give the blanket texture without tile
    // outlines. Stable jitter avoids a visible repeating logic-cell grid.
    for(let y=north;y<south;y+=20)for(let x=west;x<east;x+=22){
      const n=hash(Math.round(x),Math.round(y)),px=pixel(x+n%17),py=pixel(y+(n>>>5)%15)
      if(n%5===0){ctx.fillStyle='#edf1e8';ctx.fillRect(px,py,8+n%11,2);ctx.fillRect(px+2,py+2,6+n%7,2)}
      else if(n%7===0){ctx.fillStyle='#c6d5d4';ctx.fillRect(px,py,4+n%7,2)}
    }
    if(geometry){
      // Retain enough of the mapped surface beneath snow to read routes. The
      // broad ground blanket naturally leaves pale snowbanks along their edge.
      ctx.globalCompositeOperation='destination-out';ctx.strokeStyle=ctx.fillStyle='rgba(0,0,0,.65)';ctx.lineJoin='bevel';ctx.lineCap='butt'
      for(const f of geometry.paths)if(f.geometry.type==='Polygon'){polygon(ctx,f.geometry.coordinates as Point[][]);ctx.fill('evenodd')}
      for(const trace of campusTraces(geometry.paths)){ctx.beginPath();path(ctx,trace.points);ctx.lineWidth=pathWidth(trace.kind);ctx.stroke()}
      ctx.strokeStyle='rgba(0,0,0,.80)'
      for(const trace of campusTraces(geometry.roads)){ctx.beginPath();path(ctx,trace.points);ctx.lineWidth=roadWidth(trace.kind);ctx.stroke()}
      // Water never turns into an unexplained frozen white rectangle. This also
      // preserves polygon holes and irregular river banks in the survey.
      ctx.fillStyle='#000';ctx.strokeStyle='#000'
      for(const water of geometry.water)if(water.geometry.type==='Polygon'){polygon(ctx,water.geometry.coordinates as Point[][]);ctx.fill('evenodd');ctx.lineWidth=2;ctx.stroke()}
      ctx.globalCompositeOperation='source-over'
    }else{
      // Saved legacy worlds have a raster river rather than survey polygons.
      for(const [x,y] of city.river)ctx.clearRect(x*CELL,y*CELL,CELL,CELL)
      ctx.globalCompositeOperation='destination-out';ctx.fillStyle='rgba(0,0,0,.78)'
      for(const [x,y] of city.roads)ctx.fillRect(x*CELL+9,y*CELL+9,CELL-18,CELL-18)
      ctx.globalCompositeOperation='source-over'
    }
    this.groundTexture=Texture.from(canvas);this.groundTexture.source.scaleMode='nearest'
    const blanket=new Sprite(this.groundTexture);blanket.scale.set(2);this.ground.addChild(blanket)
    if(!geometry)return
    const objects:CampusDecoration[]=[]
    const object=(x:number,y:number,w:number,h:number,depth:number,paint:(ctx:CanvasRenderingContext2D)=>void)=>{
      const image=document.createElement('canvas');image.width=Math.max(1,Math.ceil(w));image.height=Math.max(1,Math.ceil(h))
      const brush=image.getContext('2d')!;brush.imageSmoothingEnabled=false;brush.translate(-x,-y);paint(brush)
      pixelateCanvas(image,2);hardenMask(brush)
      objects.push({canvas:image,x,y,depth})
    }
    for(const feature of geometry.buildings){
      const footprint=campusBuildingRings(feature),roof=snowRoof(feature),outer=roof[0]
      if(!outer?.length)continue
      const xs=outer.map(p=>p[0]*CELL),ys=outer.map(p=>p[1]*CELL),left=Math.floor(Math.min(...xs))-2,top=Math.floor(Math.min(...ys))-2,right=Math.ceil(Math.max(...xs))+2,bottom=Math.ceil(Math.max(...ys))+2
      const depth=Math.max(...footprint[0].map(p=>p[1]))*CELL+.2
      object(left,top,right-left,bottom-top,depth,brush=>{
        polygon(brush,roof,true);brush.fillStyle='#e3e9e2';brush.fill('evenodd')
        // Keep the original roof's dark silhouette and equipment faintly
        // legible. Courtyards remain open, never snow bridges over their holes.
        brush.save();polygon(brush,roof,true);brush.clip('evenodd')
        brush.strokeStyle='#bacbca';brush.lineWidth=3;brush.stroke()
        for(let y=top+5;y<bottom;y+=13)for(let x=left+4;x<right;x+=19){const n=hash(x,y);if(n%7===0){brush.fillStyle='#f2f3e9';brush.fillRect(pixel(x+n%7),pixel(y),8+n%11,2)}else if(n%13===0){brush.fillStyle='#cbd9d5';brush.fillRect(pixel(x),pixel(y),6,2)}}
        brush.restore()
        // Preserve Orton's small tower; its roof cap is above the normal plane.
        if(/Orton Hall/i.test(feature.name??'')){
          const raw=footprint[0],x=pixel((Math.min(...raw.map(p=>p[0]))+Math.max(...raw.map(p=>p[0])))*CELL/2),y=pixel(Math.min(...raw.map(p=>p[1]))*CELL-campusBuildingLift(feature)+16)
          brush.clearRect(x-14,y-39,28,50)
        }
      })
      if(/Orton Hall/i.test(feature.name??'')){
        const raw=footprint[0],x=pixel((Math.min(...raw.map(p=>p[0]))+Math.max(...raw.map(p=>p[0])))*CELL/2),y=pixel(Math.min(...raw.map(p=>p[1]))*CELL-campusBuildingLift(feature)+16)-40
        object(x-15,y,30,5,depth+.1,brush=>{brush.fillStyle='#e8eee5';brush.fillRect(x-14,y,28,3);brush.fillStyle='#f5f4e9';brush.fillRect(x-10,y-1,20,2)})
      }
    }
    const mappedTrees=(geometry as unknown as {trees?:{geometry:{coordinates:Point}}[]}).trees??[]
    const obstacles=[...geometry.buildings,...geometry.water].filter(f=>f.geometry.type==='Polygon').map(f=>{
      const rings=f.geometry.coordinates as Point[][],xs=rings[0].map(p=>p[0]),ys=rings[0].map(p=>p[1]);return {rings,bounds:[Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)]}
    })
    for(const tree of mappedTrees){const [x,y]=tree.geometry.coordinates
      if(obstacles.some(({rings,bounds:[a,b,c,d]})=>x>=a&&x<=c&&y>=b&&y<=d&&pointInRing([x,y],rings[0])&&!rings.slice(1).some(r=>pointInRing([x,y],r))))continue
      const n=hash(Math.round(x*100),Math.round(y*100)),scale=.7+n%4*.09,px=x*CELL,py=y*CELL,pine=n%13===0
      object(Math.floor(px-22),Math.floor(py-46),44,39,py+.2,brush=>{
        const cap=(dx:number,dy:number,w:number)=>{
          const sx=pixel(px+dx*scale),sy=pixel(py+dy*scale),width=pixel(w*scale)
          brush.fillStyle='#cbdad7';brush.fillRect(sx-2,sy+2,width+4,4)
          brush.fillStyle='#edf0e5';brush.fillRect(sx,sy,width,4);brush.fillRect(sx+2,sy-2,Math.max(2,width-4),2)
        }
        if(pine){cap(-4,-40,8);cap(-9,-30,18);cap(-13,-20,26)}
        else {cap(-6,-39,13);cap(-15,-29,16);cap(2,-24,13)}
      })
    }
    this.atlas=packCampusScenery(objects)
    for(const item of this.atlas.sprites){const sprite=new Sprite(item.texture);sprite.position.set(item.x,item.y);sprite.zIndex=item.depth;sprite.eventMode='none';(this.depthRoot??this.roofs).addChild(sprite);this.caps.push(sprite)}
  }
  destroy(){
    if(this.disposed)return
    this.disposed=true
    // The shared scene owns the depth container, so remove only our additions.
    for(const cap of this.caps){cap.removeFromParent();cap.destroy()}
    this.caps=[];this.atlas?.destroy();this.atlas=null
    this.ground.destroy({children:true});this.roofs.destroy({children:true})
    this.groundTexture?.destroy(true);this.groundTexture=null
  }
}
