/** Geographic detail for the introductory camera only; never simulation data. */
import type {City,Point} from '../types'
import {CELL,drawArt,hash,loadArt,type TownArt} from '../pixel-world/Art'
import {campusBuildingHome,campusBuildingLift,campusBuildingRings,pointInRing} from '../pixel-world/CampusBuildings'
import {campusTraces} from '../pixel-world/CampusSurfaces'

export type LonLat=[number,number]
export type RegionFeature={properties:{layer:string;name?:string;class?:string};geometry:{type:string;coordinates:unknown}}
export type LocalPolygon={layer:string;rings:LonLat[][];bounds:[number,number,number,number];id?:string;name?:string;home?:boolean;lift?:number;campus?:boolean}
type LocalLine={points:LonLat[];bounds:[number,number,number,number];kind:string;layer:'road'|'path'}
type LocalTree={position:LonLat;variant:number;scale:number}
export type OpeningGeography={land:Uint8ClampedArray;features:RegionFeature[];local:LocalPolygon[];art?:TownArt;campusLines?:LocalLine[];trees?:LocalTree[];networkLines?:LocalLine[];networkTrees?:LocalTree[];campusBounds?:[number,number,number,number];nativePixelMeters?:number}
export const OVAL:LonLat=[-83.0123,39.9994]
export const EARTH_RADIUS=6371008.8
export const radians=Math.PI/180
export const clamp=(n:number)=>Math.max(0,Math.min(1,n))
export const ease=(n:number)=>{n=clamp(n);return n*n*(3-2*n)}
let pending:Promise<OpeningGeography>|undefined
const localSurfaces=new WeakMap<CanvasRenderingContext2D,HTMLCanvasElement>()
const stableHash=(value:string)=>[...value].reduce((n,c)=>Math.imul(n^c.charCodeAt(0),16777619)>>>0,2166136261)
const boundsFor=(points:LonLat[]):[number,number,number,number]=>{let west=Infinity,south=Infinity,east=-Infinity,north=-Infinity;for(const [x,y] of points){west=Math.min(west,x);south=Math.min(south,y);east=Math.max(east,x);north=Math.max(north,y)}return [west,south,east,north]}
const roadWidth=(kind:string)=>kind==='primary'?28:kind==='secondary'?26:kind==='tertiary'?24:kind==='service'?8:kind==='motorway'||kind==='trunk'?42:18
const pathWidth=(kind:string)=>kind==='entrance_connector'?4:kind==='steps'?6:kind==='pedestrian'?10:kind==='cycleway'?7:kind==='living_street'?12:7
const mixColor=(a:string,b:string,t:number)=>'#'+[1,3,5].map(i=>Math.round(parseInt(a.slice(i,i+2),16)*(1-t)+parseInt(b.slice(i,i+2),16)*t).toString(16).padStart(2,'0')).join('')

/** Add the exact campus geometry underneath the native-detail reveal. The
 * surrounding footprint asset was clipped around this survey, so leaving this
 * layer empty would turn every feathered edge into a visible rectangular seam.
 * Roof heights are illustrative art offsets in native pixels, not building data. */
export function withCampusContext(geography:OpeningGeography,city:City):OpeningGeography {
  const g=city.campus_geometry,bounds=city.map_bounds
  const box=(city.geography_provenance as (City['geography_provenance']&{selection_bbox?:number[]})|undefined)?.selection_bbox
  if(!g||!bounds||bounds.length!==4||!box||box.length!==4)return geography
  const [west,north,east,south]=bounds,[minLon,minLat,maxLon,maxLat]=box
  if(!(east>west&&south>north&&maxLon>minLon&&maxLat>minLat))return geography
  const geographic=([x,y]:Point):LonLat=>[minLon+(x-west)/(east-west)*(maxLon-minLon),maxLat-(y-north)/(south-north)*(maxLat-minLat)]
  const local=geography.local.filter(polygon=>!polygon.campus)
  for(const [layer,features] of [['green',g.greens],['water',g.water],['path',g.paths],['building',g.buildings]] as const){
    for(const feature of features){
      if(feature.geometry.type!=='Polygon')continue
      const rings=(feature.geometry.coordinates as Point[][]).map(ring=>ring.map(geographic))
      if(!rings[0]?.length)continue
      local.push({layer,rings,bounds:boundsFor(rings[0]),id:feature.id,name:feature.name,campus:true,
        ...(layer==='building'?{home:!!campusBuildingHome(feature),lift:campusBuildingLift(feature)}:{})})
    }
  }
  const campusLines:LocalLine[]=[...(geography.networkLines??[])]
  for(const [layer,features] of [['path',g.paths],['road',g.roads]] as const)for(const line of campusTraces(features)){
    const points=line.points.map(geographic)
    campusLines.push({points,bounds:boundsFor(points),kind:line.kind,layer})
  }
  // Use only mapped tree points. No inferred forest fills the surrounding city.
  // Match the live renderer's obstacle filter and deterministic atlas variants.
  const obstacles=[...g.buildings,...g.water].filter(f=>f.geometry.type==='Polygon').map(f=>{
    const rings=campusBuildingRings(f);return {rings,bounds:boundsFor(rings[0])}
  })
  const trees:LocalTree[]=[...(geography.networkTrees??[])]
  const mapped=(g as typeof g&{trees?:{geometry:{type:string;coordinates:Point}}[]}).trees??[]
  for(const feature of mapped){
    if(feature.geometry.type!=='Point')continue
    const point=feature.geometry.coordinates,[x,y]=point
    if(obstacles.some(o=>x>=o.bounds[0]&&x<=o.bounds[2]&&y>=o.bounds[1]&&y<=o.bounds[3]&&pointInRing(point,o.rings[0])&&!o.rings.slice(1).some(r=>pointInRing(point,r))))continue
    const variant=hash(Math.round(x*100),Math.round(y*100))
    trees.push({position:geographic(point),variant,scale:.7+variant%4*.09})
  }
  return {...geography,local,campusLines,trees,campusBounds:[minLon,minLat,maxLon,maxLat],nativePixelMeters:(city.meters_per_unit??24.25)/CELL}
}

export function loadOpeningGeography(){
  if(!pending)pending=Promise.all([
    fetch('/assets/geography/natural-earth-land-110m.geojson',{signal:AbortSignal.timeout(12000)}),
    fetch('/assets/geography/opening-region.geojson',{signal:AbortSignal.timeout(12000)}),
    fetch('/assets/geography/opening-local.geojson',{signal:AbortSignal.timeout(12000)}),
    loadArt().catch(()=>undefined),
    fetch('/assets/geography/opening-local-network.geojson',{signal:AbortSignal.timeout(12000)}).then(response=>response.ok?response.json():null).catch(()=>null),
  ]).then(async ([landResponse,regionResponse,nearbyResponse,art,network])=>{
    const responses=[landResponse,regionResponse,nearbyResponse]
    if(responses.some(response=>!response.ok))throw new Error('Opening geography unavailable')
    const [land,region,nearby]=await Promise.all(responses.map(response=>response.json()))
    const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=512
    const ctx=canvas.getContext('2d')!;ctx.fillStyle='#fff'
    for(const feature of land.features){
      const polygons=feature.geometry.type==='MultiPolygon'?feature.geometry.coordinates:[feature.geometry.coordinates]
      for(const polygon of polygons){ctx.beginPath();for(const ring of polygon){ring.forEach(([lon,lat]:LonLat,i:number)=>{const x=(lon+180)/360*1024,y=(90-lat)/180*512;if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y)});ctx.closePath()}ctx.fill('evenodd')}
    }
    const texture=ctx.getImageData(0,0,1024,512).data
    // Bake the illustrative terrain palette once, not millions of times during
    // the flight. Alpha remains the land mask.
    for(let y=0;y<512;y++)for(let x=0;x<1024;x++){
      const i=(y*1024+x)*4,high=Math.sin(x*.11)*Math.cos(y*.19)+Math.sin(x*.03+y*.07)>.45
      texture[i]=high?145:119;texture[i+1]=high?165:151;texture[i+2]=high?111:108
    }
    const local:LocalPolygon[]=[]
    for(const feature of nearby.features){
      const polygons=feature.geometry.type==='MultiPolygon'?feature.geometry.coordinates:[feature.geometry.coordinates]
      for(const rings of polygons as LonLat[][][]){
        const bounds=boundsFor(rings[0]),home=feature.properties.class==='house'
        local.push({layer:feature.properties.layer,rings,bounds,id:`context/${bounds.join('/')}`,name:feature.properties.name,home,lift:home?16:26})
      }
    }
    const networkLines:LocalLine[]=[],networkTrees:LocalTree[]=[]
    for(const feature of network?.features??[]){
      const layer=feature.properties?.layer,coordinates=feature.geometry?.coordinates
      if(feature.geometry?.type==='LineString'&&['road','path'].includes(layer)&&Array.isArray(coordinates)&&coordinates.length>1){
        networkLines.push({points:coordinates,bounds:boundsFor(coordinates),kind:feature.properties?.class??'footway',layer})
      }else if(feature.geometry?.type==='Point'&&layer==='tree'&&Array.isArray(coordinates)&&coordinates.length===2){
        const variant=stableHash(String(feature.id??feature.properties?.id??coordinates.join('/')))
        networkTrees.push({position:coordinates as LonLat,variant,scale:.7+variant%4*.09})
      }
    }
    return {land:texture,features:region.features as RegionFeature[],local,art,networkLines,networkTrees,campusLines:networkLines,trees:networkTrees}
  }).catch(error=>{pending=undefined;throw error})
  return pending
}

/** Orthographic Earth becomes a north-up local metric view as altitude falls.
 * All regional layers use the SAME projection. At street level the coefficients
 * come from the live campus model, so its roads cannot drift at the join. */
export function geographicProjector(target:LonLat,metersPerDegree:LonLat,metersPerPixel:number,anchor:LonLat,pixelStep:number){
  const lon=target[0]*radians,lat=target[1]*radians,local=ease(Math.log(5000/metersPerPixel)/Math.log(10))
  return ([x,y]:LonLat):LonLat=>{
    if(local===1)return [anchor[0]+(x-target[0])*metersPerDegree[0]/metersPerPixel/pixelStep,anchor[1]+(target[1]-y)*metersPerDegree[1]/metersPerPixel/pixelStep]
    const dl=x*radians-lon,p=y*radians
    const globeX=EARTH_RADIUS*Math.cos(p)*Math.sin(dl),globeY=-EARTH_RADIUS*(Math.cos(lat)*Math.sin(p)-Math.sin(lat)*Math.cos(p)*Math.cos(dl))
    const flatX=(x-target[0])*metersPerDegree[0],flatY=(target[1]-y)*metersPerDegree[1]
    return [anchor[0]+(globeX+(flatX-globeX)*local)/metersPerPixel/pixelStep,anchor[1]+(globeY+(flatY-globeY)*local)/metersPerPixel/pixelStep]
  }
}

export function paintRegion(ctx:CanvasRenderingContext2D,features:RegionFeature[],project:(p:LonLat)=>LonLat,mpp:number,step:number,local:LocalPolygon[]=[],geography?:OpeningGeography){
  const trace=(points:LonLat[],close=false)=>{points.forEach((p,i)=>{const [x,y]=project(p);if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y)});if(close)ctx.closePath()}
  const paths=(f:RegionFeature):LonLat[][]=>f.geometry.type==='LineString'?[f.geometry.coordinates as LonLat[]]:f.geometry.type==='MultiLineString'?f.geometry.coordinates as LonLat[][]:[]
  const polygon=(f:RegionFeature)=>{const polygons=f.geometry.type==='MultiPolygon'?f.geometry.coordinates as LonLat[][][]:[f.geometry.coordinates as LonLat[][]];ctx.beginPath();for(const p of polygons)for(const r of p)trace(r,true)}
  ctx.save();ctx.lineJoin='round';ctx.lineCap='round'
  // A geographic outline persists while new detail resolves beneath the camera.
  if(mpp<6000){
    ctx.globalAlpha=ease(Math.log(6000/mpp)/Math.log(3))
    for(const f of features.filter(f=>f.properties.layer==='state')){polygon(f);ctx.fillStyle='#718963';ctx.fill('evenodd');ctx.strokeStyle=f.properties.name==='Ohio'?'#d2c28b':'#92a27b';ctx.lineWidth=f.properties.name==='Ohio'?1.25:.6;ctx.stroke()}
    ctx.globalAlpha=1
  }
  for(const f of features.filter(f=>f.properties.layer==='lake')){polygon(f);ctx.fillStyle='#477b88';ctx.fill('evenodd');ctx.strokeStyle='#789b91';ctx.lineWidth=.6;ctx.stroke()}
  const nativeScale=(geography?.nativePixelMeters??24.25/CELL)/mpp/step
  for(const f of features.filter(f=>f.properties.layer==='river')){
    const local=f.properties.name==='Scioto River'||f.properties.name==='Olentangy River'
    if(mpp>(local?400:3500)||(!local&&mpp<90))continue
    ctx.beginPath();for(const p of paths(f))trace(p)
    ctx.lineWidth=Math.max(.7,(f.properties.name==='Scioto River'?65:35)/mpp/step);ctx.strokeStyle='#4b7e84';ctx.stroke()
  }
  const roads=features.filter(f=>f.properties.layer==='road'&&mpp<(f.properties.class?.includes('motorway')?900:f.properties.class?.includes('trunk')?500:f.properties.class?.includes('primary')?180:65))
  // Broad city corridors are a restrained illustrative land-use treatment.
  if(mpp<180&&mpp>4){
    ctx.save();ctx.globalAlpha=ease((mpp-4)/6);ctx.strokeStyle='#87957b';ctx.lineWidth=Math.max(1,150/mpp/step)
    for(const f of roads){ctx.beginPath();for(const p of paths(f))trace(p);ctx.stroke()}ctx.restore()
  }
  const paintRoads=()=>{
    const close=ease((28-mpp)/16)
    if(nativeScale<.2){
      for(const f of roads){
        ctx.beginPath();for(const p of paths(f))trace(p)
        const major=f.properties.class?.includes('motorway')||f.properties.class?.includes('trunk')
        const distantWidth=Math.max(major?.8:.5,(major?25:13)/mpp/step),nearWidth=Math.max(.7,roadWidth(f.properties.class??'')*nativeScale)
        ctx.lineWidth=distantWidth+(nearWidth-distantWidth)*close
        ctx.strokeStyle=mixColor(major?'#d2c59b':'#b9bba0','#697771',close);ctx.stroke()
      }
    }else{
      for(const [color,extra] of [['#667463',4],['#bab69d',2],['#697771',0]] as const){
        ctx.strokeStyle=color
        for(const f of roads){ctx.beginPath();for(const p of paths(f))trace(p);ctx.lineWidth=Math.max(.7,(roadWidth(f.properties.class??'')+extra)*nativeScale);ctx.stroke()}
      }
      ctx.strokeStyle='#c9bd91';ctx.lineWidth=Math.max(.35,2*nativeScale);ctx.setLineDash([11*nativeScale,19*nativeScale]);ctx.lineCap='butt'
      for(const f of roads){ctx.beginPath();for(const p of paths(f))trace(p);ctx.stroke()}
    }
  }
  if(mpp<12&&geography?.campusBounds){
    // Generalized roads retire continuously inside the exact survey while the
    // shared street layer resolves. Outside, their geographic context persists.
    const [west,south,east,north]=geography.campusBounds,[x,y]=project([west,north]),[r,b]=project([east,south])
    ctx.save();ctx.beginPath();ctx.rect(0,0,ctx.canvas.width,ctx.canvas.height);ctx.rect(x,y,r-x,b-y);ctx.clip('evenodd');paintRoads();ctx.restore()
    if(mpp>8){
      ctx.save();ctx.beginPath();ctx.rect(x,y,r-x,b-y);ctx.clip();ctx.globalAlpha=ease((mpp-8)/4);paintRoads();ctx.restore()
    }
  }else{ctx.save();paintRoads();ctx.restore()}
  paintLocalDetail(ctx,local,geography,project,mpp,step,nativeScale)
  ctx.restore()
}

/** Street-level detail resolves around the camera's destination, rather than
 * exposing the rectangular edges of a bounded data extract from high altitude.
 * This is visual level-of-detail only; geographic coordinates remain unchanged. */
function paintLocalDetail(ctx:CanvasRenderingContext2D,local:LocalPolygon[],geography:OpeningGeography|undefined,project:(p:LonLat)=>LonLat,mpp:number,step:number,scale:number){
  const opacity=ease((12-mpp)/9)
  if(!opacity)return
  let surface=localSurfaces.get(ctx)
  if(!surface){surface=document.createElement('canvas');localSurfaces.set(ctx,surface)}
  const width=ctx.canvas.width,height=ctx.canvas.height
  if(surface.width!==width||surface.height!==height){surface.width=width;surface.height=height}
  const paint=surface.getContext('2d')!
  paint.save();paint.clearRect(0,0,width,height);paint.imageSmoothingEnabled=false;paint.lineJoin='round';paint.lineCap='round'
  paintLocalGround(paint,local,project,mpp,scale)
  paintCampusContextSurfaces(paint,local,geography?.campusLines??[],project,scale)
  paintLocalObjects(paint,local,geography?.trees??[],geography?.art,project,mpp,scale)
  // The circular focus lies safely inside the source extent. It becomes larger
  // than the viewport before the native campus handoff, leaving no crop seam.
  const [x,y]=project(OVAL),radius=1400/mpp/step,mask=paint.createRadialGradient(x,y,radius*.35,x,y,radius)
  mask.addColorStop(0,'#fff');mask.addColorStop(.55,'#ffffffe6');mask.addColorStop(1,'#ffffff00')
  paint.globalCompositeOperation='destination-in';paint.fillStyle=mask;paint.fillRect(0,0,width,height);paint.restore()
  ctx.save();ctx.globalAlpha=opacity;ctx.imageSmoothingEnabled=false;ctx.drawImage(surface,0,0);ctx.restore()
}

function visibleBounds(ctx:CanvasRenderingContext2D,bounds:[number,number,number,number],project:(p:LonLat)=>LonLat,margin=20){
  const [west,south,east,north]=bounds,[left,top]=project([west,north]),[right,bottom]=project([east,south])
  return right>=-margin&&left<=ctx.canvas.width+margin&&bottom>=-margin&&top<=ctx.canvas.height+margin
}
function traceRings(ctx:CanvasRenderingContext2D,rings:LonLat[][],project:(p:LonLat)=>LonLat,dx=0,dy=0){
  ctx.beginPath()
  for(const ring of rings){ring.forEach((point,i)=>{const [x,y]=project(point);if(i)ctx.lineTo(x+dx,y+dy);else ctx.moveTo(x+dx,y+dy)});ctx.closePath()}
}
function paintLocalGround(ctx:CanvasRenderingContext2D,polygons:LocalPolygon[],project:(p:LonLat)=>LonLat,mpp:number,scale:number){
  if(mpp>=22)return
  ctx.save()
  for(const polygon of polygons){
    if(!['green','water'].includes(polygon.layer)||!visibleBounds(ctx,polygon.bounds,project))continue
    traceRings(ctx,polygon.rings,project)
    if(polygon.layer==='water'){ctx.strokeStyle='#b0af8c';ctx.lineWidth=Math.max(.5,12*scale);ctx.stroke()}
    ctx.fillStyle=polygon.layer==='water'?'#537f83':'#7f986b';ctx.fill('evenodd')
    if(polygon.layer==='water'){ctx.strokeStyle='#3f6970';ctx.lineWidth=Math.max(.25,3*scale);ctx.stroke()}
  }
  ctx.restore()
}

/** The same union order, widths and colors as CampusSurfaces: pedestrian areas
 * first, asphalt above crossings, then restrained centerlines. No vertex snaps
 * on curves, and no border is drawn between plaza polygons and their paths. */
function paintCampusContextSurfaces(ctx:CanvasRenderingContext2D,polygons:LocalPolygon[],lines:LocalLine[],project:(p:LonLat)=>LonLat,scale:number){
  const areas=polygons.filter(p=>p.layer==='path'&&visibleBounds(ctx,p.bounds,project))
  const visible=lines.filter(line=>visibleBounds(ctx,line.bounds,project,30*scale))
  const trace=(points:LonLat[])=>{ctx.beginPath();points.forEach((p,i)=>{const [x,y]=project(p);if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y)})}
  ctx.save();ctx.lineJoin='round';ctx.lineCap='round';ctx.setLineDash([])
  const pathPasses:readonly (readonly [string,number])[]=scale>=.2?[['#8a9478',1],['#c7c1a6',0]]:[['#c7c1a6',0]]
  for(const [color,edge] of pathPasses){
    ctx.fillStyle=ctx.strokeStyle=color
    for(const area of areas){traceRings(ctx,area.rings,project);ctx.fill('evenodd');if(edge){ctx.lineWidth=edge*2*scale;ctx.stroke()}}
    for(const line of visible)if(line.layer==='path'){trace(line.points);ctx.lineWidth=Math.max(.3,(pathWidth(line.kind)+edge*2)*scale);ctx.stroke()}
  }
  if(scale>=.2){ctx.strokeStyle='#999b82';ctx.setLineDash([scale,4*scale]);for(const line of visible)if(line.kind==='steps'){trace(line.points);ctx.lineWidth=pathWidth(line.kind)*scale;ctx.stroke()}ctx.setLineDash([])}
  const roadPasses:readonly (readonly [string,number])[]=scale>=.2?[['#667463',4],['#bab69d',2],['#697771',0]]:[['#697771',0]]
  for(const [color,extra] of roadPasses){
    ctx.strokeStyle=color
    for(const line of visible)if(line.layer==='road'){trace(line.points);ctx.lineWidth=Math.max(.3,(roadWidth(line.kind)+extra)*scale);ctx.stroke()}
  }
  if(scale>=.2){
    ctx.strokeStyle='#c9bd91';ctx.lineWidth=Math.max(.3,2*scale);ctx.setLineDash([11*scale,19*scale]);ctx.lineCap='butt'
    for(const line of visible)if(line.layer==='road'&&['primary','secondary','tertiary'].includes(line.kind)){trace(line.points);ctx.stroke()}
  }
  ctx.restore()
}

/** Real surrounding footprints and the surveyed campus share one depth-sorted
 * art vocabulary. The context remains scenery, not an expanded playable map. */
function paintLocalObjects(ctx:CanvasRenderingContext2D,polygons:LocalPolygon[],trees:LocalTree[],art:TownArt|undefined,project:(p:LonLat)=>LonLat,mpp:number,scale:number){
  if(mpp>=22)return
  const buildings=polygons.filter(p=>p.layer==='building'&&visibleBounds(ctx,p.bounds,project,60*scale))
  const objects:({depth:number;building:LocalPolygon}|{depth:number;tree:LocalTree})[]=buildings.map(building=>({depth:building.bounds[1],building}))
  if(art&&scale>.035)for(const tree of trees){const [x,y]=project(tree.position);if(x>=-30*scale&&x<=ctx.canvas.width+30*scale&&y>=-10*scale&&y<=ctx.canvas.height+55*scale)objects.push({depth:tree.position[1],tree})}
  objects.sort((a,b)=>b.depth-a.depth)
  ctx.save();ctx.imageSmoothingEnabled=false
  // Ground shadows are drawn before roofs and trees, as in the live map.
  ctx.fillStyle='#586d51'
  if(scale>=.15)for(const building of buildings){traceRings(ctx,building.rings,project,6*scale,8*scale);ctx.fill('evenodd')}
  for(const object of objects){
    if('building' in object)paintContextBuilding(ctx,object.building,project,scale)
    else if(art){const tree=object.tree,[x,y]=project(tree.position),s=tree.scale*scale;drawArt(ctx,art,tree.variant%13===0?'pine':'oak',x-20*s,y-45*s,s)}
  }
  ctx.restore()
}

function paintContextBuilding(ctx:CanvasRenderingContext2D,building:LocalPolygon,project:(p:LonLat)=>LonLat,scale:number){
  const rings=building.rings.map(ring=>ring.map(project)),r=rings[0]
  if(!r?.length)return
  const xs=r.map(p=>p[0]),ys=r.map(p=>p[1]),left=Math.min(...xs),right=Math.max(...xs),top=Math.min(...ys),bottom=Math.max(...ys)
  if((right-left)*(bottom-top)<.45)return
  const home=building.home,n=stableHash(building.id??`${building.bounds}`),lift=(building.lift??(home?16:26))*scale
  const shape=(parts:LonLat[][],dy=0)=>{ctx.beginPath();for(const ring of parts){ring.forEach(([x,y],i)=>{if(i)ctx.lineTo(x,y+dy);else ctx.moveTo(x,y+dy)});ctx.closePath()}}
  const fill=(parts:LonLat[][],color:string,dy=0)=>{shape(parts,dy);ctx.fillStyle=color;ctx.fill('evenodd')}
  const rect=(x:number,y:number,w:number,h:number,color:string)=>{if(w<=0||h<=0)return;ctx.fillStyle=color;ctx.fillRect(Math.round(x),Math.round(y),Math.max(.5,w),Math.max(.5,h))}
  const brick=home?['#ac8a6d','#b59b7b','#99775d'][n%3]:['#a57961','#ae9474','#967862'][n%3]
  const roof=home?['#706d60','#817561','#777e71','#8b6e5c'][n%4]:['#b3b39b','#aaa990','#a8b09d','#96a497'][n%4]
  if(scale<.15){fill(rings,roof);return}
  fill(rings,brick)
  const winding=r.reduce((sum,a,i)=>{const b=r[(i+1)%r.length];return sum+a[0]*b[1]-b[0]*a[1]},0)
  for(const ring of rings)for(let j=0;j<ring.length-1;j++){
    const a=ring[j],b=ring[j+1];if((b[0]-a[0])*winding>=0)continue
    fill([[a,b,[b[0],b[1]-lift],[a[0],a[1]-lift]]],brick)
    if(scale>.16){
      ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.strokeStyle='#c4b391';ctx.lineWidth=Math.max(.4,2*scale);ctx.stroke()
      const length=Math.hypot(b[0]-a[0],b[1]-a[1])
      for(let k=9*scale;k<length-6*scale;k+=(home?14:16)*scale){const t=k/length,x=a[0]+(b[0]-a[0])*t,y=a[1]+(b[1]-a[1])*t
        rect(x-2*scale,y-lift+5*scale,4*scale,(home?5:8)*scale,'#566a65');rect(x-2*scale,y-lift+(home?10:13)*scale,4*scale,2*scale,'#d8c8a2')
        if(lift>=30*scale){rect(x-2*scale,y-12*scale,4*scale,7*scale,'#4a625d');rect(x-2*scale,y-5*scale,4*scale,2*scale,'#ceb994')}
      }
    }
  }
  fill(rings,roof,-lift)
  shape(rings,-lift);ctx.strokeStyle=home?'#525d52':'#747c68';ctx.lineWidth=Math.max(.3,3*scale);ctx.stroke()
  if(scale<.12)return
  ctx.save();shape(rings,-lift);ctx.clip('evenodd')
  if(home){
    const middle=(top+bottom)/2-lift
    rect(left,middle,right-left,2*scale,'#a2987c');rect(left,middle+2*scale,right-left,bottom-middle,'#45584922')
    if(scale>.35)for(let y=top-lift+5*scale;y<bottom-lift;y+=9*scale)rect(left,y,right-left,scale,'#c2b69325')
    if(right-left>30*scale){rect(left+8*scale,top-lift+7*scale,6*scale,10*scale,'#735b49');rect(left+7*scale,top-lift+6*scale,8*scale,3*scale,'#a99073')}
  }else{
    rect(left+4*scale,top-lift+4*scale,right-left-8*scale,2*scale,'#c6c3a6');rect(left+7*scale,bottom-lift-7*scale,right-left-14*scale,3*scale,'#77867133')
    if(right-left>60*scale&&bottom-top>40*scale){const x=left+14*scale,y=top-lift+14*scale;rect(x+2*scale,y+3*scale,20*scale,12*scale,'#7e8b7c');rect(x,y,18*scale,11*scale,'#c4c5ad');rect(x+4*scale,y+3*scale,10*scale,5*scale,'#89968b')}
    if(right-left>130*scale&&bottom-top>80*scale){rect(right-36*scale,bottom-lift-28*scale,20*scale,12*scale,'#7d8d81');rect(right-35*scale,bottom-lift-29*scale,18*scale,4*scale,'#bac4b4')}
  }
  ctx.restore()
  if(/Orton Hall/i.test(building.name??'')){
    const x=(left+right)/2,y=top-lift+16*scale
    rect(x-13*scale,y-35*scale,26*scale,46*scale,'#6d6250');rect(x-11*scale,y-35*scale,22*scale,43*scale,'#b39a76');rect(x-14*scale,y-39*scale,28*scale,5*scale,'#c7b58d')
    rect(x-8*scale,y-30*scale,5*scale,9*scale,'#47534d');rect(x+3*scale,y-30*scale,5*scale,9*scale,'#47534d');rect(x-5*scale,y-15*scale,10*scale,10*scale,'#e0d5af');rect(x,y-14*scale,scale,5*scale,'#4e5b50');rect(x,y-10*scale,4*scale,scale,'#4e5b50')
  }
}
