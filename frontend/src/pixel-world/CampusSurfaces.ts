import type {CampusFeature,City,Point} from '../types'
import {CELL} from './Art'
import {hardenMask} from './PixelCanvas'

interface Trace {points:Point[];kind:string;source:string}
const same=(a:Point,b:Point)=>Math.abs(a[0]-b[0])+Math.abs(a[1]-b[1])<.000002
const key=(p:Point)=>`${p[0].toFixed(6)},${p[1].toFixed(6)}`

/** Reassemble the original OSM way fragments for drawing only. Never bridge a
 * clipped gap or join unrelated paths just because their endpoints are close. */
export function campusTraces(features:CampusFeature[]):Trace[] {
  const groups=new Map<string,{index:number;points:Point[];kind:string}[]>(),seen=new Set<string>()
  for(const f of features){
    if(f.geometry.type!=='LineString'||f.kind==='construction')continue
    const points=f.geometry.coordinates as Point[]
    if(points.length<2)continue
    const forwards=points.map(key).join(';'),backwards=[...points].reverse().map(key).join(';')
    const identity=`${f.kind}:${forwards<backwards?forwards:backwards}`
    if(seen.has(identity))continue
    seen.add(identity)
    const match=/^((?:way|relation)\/\d+)\/(\d+)$/.exec(f.id)
    const source=match?.[1]??f.id,groupKey=`${source}:${f.kind}`
    const list=groups.get(groupKey)??[]
    list.push({index:match?Number(match[2]):0,points,kind:f.kind??'footway'});groups.set(groupKey,list)
  }
  const traces:Trace[]=[]
  for(const [source,parts] of groups){
    let current:Trace|null=null,previous=-2
    for(const part of parts.sort((a,b)=>a.index-b.index)){
      if(current&&part.index===previous+1&&same(current.points.at(-1)!,part.points[0]))current.points.push(...part.points.slice(1))
      else{current={points:[...part.points],kind:part.kind,source};traces.push(current)}
      previous=part.index
    }
  }
  return traces
}

const roadWidth=(kind:string)=>kind==='primary'?28:kind==='secondary'?26:kind==='tertiary'?24:kind==='service'?8:18
const pathWidth=(kind:string)=>kind==='entrance_connector'?4:kind==='steps'?6:kind==='pedestrian'?10:kind==='cycleway'?7:kind==='living_street'?12:7

/** Draw physical surfaces as unions on the shared two-pixel art grid. The geometry is
 * not snapped before rasterization: rounding each curve vertex independently
 * changes its tangent and makes the road's inner/outer edges visibly lumpy. */
export function paintCampusSurfaces(ground:CanvasRenderingContext2D,city:City) {
  const g=city.campus_geometry!,roads=campusTraces(g.roads),paths=campusTraces(g.paths)
  const areas=g.paths.filter(f=>f.geometry.type==='Polygon'),size=city.size*CELL
  const grid=2,mask=document.createElement('canvas');mask.width=mask.height=Math.ceil(size/grid)
  const ctx=mask.getContext('2d',{willReadFrequently:true})!
  const trace=(points:Point[])=>{ctx.beginPath();points.forEach(([x,y],i)=>{if(i)ctx.lineTo(x*CELL,y*CELL);else ctx.moveTo(x*CELL,y*CELL)})}
  const surface=(color:string,paint:()=>void)=>{
    ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,mask.width,mask.height);ctx.scale(1/grid,1/grid)
    ctx.globalCompositeOperation='source-over';ctx.fillStyle=ctx.strokeStyle='#fff';ctx.lineJoin='round';ctx.lineCap='round';ctx.setLineDash([])
    paint()
    hardenMask(ctx)
    ctx.globalCompositeOperation='source-in';ctx.fillStyle=color;ctx.fillRect(0,0,size,size)
    ground.save();ground.imageSmoothingEnabled=false;ground.drawImage(mask,0,0,size,size);ground.restore()
  }
  const pedestrian=(edge:number)=>{
    for(const f of areas){ctx.beginPath();for(const points of f.geometry.coordinates as Point[][]){points.forEach(([x,y],i)=>{if(i)ctx.lineTo(x*CELL,y*CELL);else ctx.moveTo(x*CELL,y*CELL)});ctx.closePath()}ctx.fill('evenodd');if(edge){ctx.lineWidth=edge*2;ctx.stroke()}}
    for(const t of paths){trace(t.points);ctx.lineWidth=pathWidth(t.kind)+edge*2;ctx.stroke()}
  }
  // Plaza polygons and the route lines within them are one paved surface. This
  // prevents dark phantom outlines from tracing routes through a filled plaza.
  surface('#8a9478',()=>pedestrian(1))
  surface('#c7c1a6',()=>pedestrian(0))
  surface('#999b82',()=>{ctx.setLineDash([1,4]);for(const t of paths)if(t.kind==='steps'){trace(t.points);ctx.lineWidth=pathWidth(t.kind);ctx.stroke()}})

  // Local access lanes are genuinely narrower than streets. Mapped sidewalks
  // supply their own surface; do not invent a second wide sidewalk at every road.
  // Road surfacing sits above footpaths at crossings, avoiding cream stripes
  // through intersections when no mapped crossing markings are available.
  for(const [color,extra] of [['#667463',4],['#bab69d',2],['#697771',0]] as const)
    surface(color,()=>{for(const t of roads){trace(t.points);ctx.lineWidth=roadWidth(t.kind)+extra;ctx.stroke()}})

  const neighbors=new Map<string,{point:Point;links:Set<string>}>()
  for(const t of roads)for(let i=1;i<t.points.length;i++)for(const [p,q] of [[t.points[i-1],t.points[i]],[t.points[i],t.points[i-1]]]){
    const id=key(p),node=neighbors.get(id)??{point:p,links:new Set<string>()};node.links.add(key(q));neighbors.set(id,node)
  }
  surface('#c9bd91',()=>{
    ctx.setLineDash([11,19]);ctx.lineCap='butt';ctx.lineWidth=2
    for(const t of roads)if(['primary','secondary','tertiary'].includes(t.kind)){trace(t.points);ctx.stroke()}
    // Keep junction centers clear instead of crossing several dashed centerlines.
    ctx.globalCompositeOperation='destination-out';ctx.setLineDash([])
    for(const {point,links} of neighbors.values())if(links.size>2){ctx.beginPath();ctx.arc(point[0]*CELL,point[1]*CELL,18,0,Math.PI*2);ctx.fill()}
    ctx.globalCompositeOperation='source-over'
  })
  mask.width=mask.height=1
}
