import type {CampusFeature,City,Point} from '../types'
import {CELL} from './Art'

export const campusBuildingRings=(feature:CampusFeature):Point[][]=>feature.geometry.type==='Polygon'?feature.geometry.coordinates as Point[][]:[]
const stableHash=(value:string)=>[...value].reduce((n,c)=>Math.imul(n^c.charCodeAt(0),16777619)>>>0,2166136261)
export function campusBuildingHome(feature:CampusFeature) {
  const housing=String(feature.housing_type??''),kind=String(feature.building_type??feature.kind??'')
  return housing&&housing!=='null'?['house','student_house'].includes(housing):['house','detached','semidetached_house','terrace','residential'].includes(kind)
}
/** Shared by the scenery painter and pointer picking: displayed roofs rise above the footprint. */
export function campusBuildingLift(feature:CampusFeature) {
  return campusBuildingHome(feature)?16:/Thompson|Orton Hall/i.test(feature.name??'')||feature.name==='Ohio Union'?34:22+stableHash(String(feature.id))%3*4
}
export function pointInRing(point:Point,ring:Point[]) {
  let inside=false
  for(let i=0,j=ring.length-1;i<ring.length;j=i++){
    const a=ring[i],b=ring[j]
    if((a[1]>point[1])!==(b[1]>point[1])&&point[0]<(b[0]-a[0])*(point[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside
  }
  return inside
}
export interface CampusBuilding {
  id:string;name:string;named:boolean;category:string;venues:string[];rings:Point[][];roof:Point[][];facades:Point[][];
  anchor:Point;entrance:Point;depth:number;bounds:[number,number,number,number]
}
const category=(feature:CampusFeature)=>{
  const kind=String(feature.building_type??feature.kind??''),housing=String(feature.housing_type??'')
  if(housing==='student_house')return 'Student house'
  if(housing==='dormitory'||kind==='dormitory')return 'Residence hall'
  if(housing==='house'||campusBuildingHome(feature))return 'Neighborhood house'
  if(housing==='apartment'||['apartments','residential','terrace'].includes(kind))return 'Apartments'
  if(kind==='parking')return 'Parking garage'
  if(kind==='university'||feature.kind==='school')return 'University building'
  if(['commercial','retail'].includes(kind)||feature.kind==='shop')return 'Shops & services'
  if(['church','chapel','religious'].includes(kind))return 'Place of worship'
  return 'Campus & neighborhood'
}
export function indexCampusBuildings(city:City):CampusBuilding[] {
  const places=new Map(city.places?.filter(place=>!place.is_portal).map(place=>[place.id,place]))
  return (city.campus_geometry?.buildings??[]).flatMap(feature=>{
    const rings=campusBuildingRings(feature),outer=rings[0]
    if(!outer||outer.length<3)return []
    const lift=campusBuildingLift(feature)/CELL,roof=rings.map(ring=>ring.map(([x,y]):Point=>[x,y-lift]))
    const winding=outer.reduce((sum,a,i)=>{const b=outer[(i+1)%outer.length];return sum+a[0]*b[1]-b[0]*a[1]},0)
    const facades:Point[][]=[]
    for(const ring of rings)for(let i=0;i<ring.length-1;i++){
      const a=ring[i],b=ring[i+1]
      if((b[0]-a[0])*winding<0)facades.push([a,b,[b[0],b[1]-lift],[a[0],a[1]-lift]])
    }
    const xs=outer.map(p=>p[0]),ys=outer.map(p=>p[1]),left=Math.min(...xs),right=Math.max(...xs),top=Math.min(...ys),bottom=Math.max(...ys)
    // Orton's illustrative clock tower is painted above the ordinary roof plane.
    if(/Orton Hall/i.test(feature.name??'')){
      const x=(left+right)/2,y=top-lift+16/CELL
      facades.push([[x-14/CELL,y-39/CELL],[x+14/CELL,y-39/CELL],[x+14/CELL,y+11/CELL],[x-14/CELL,y+11/CELL]])
    }
    const place=places.get(feature.id),kind=category(feature)
    const name=String(feature.name||place?.name||(kind==='Campus & neighborhood'?'Building':kind))
    return [{id:feature.id,name,named:!!feature.name,category:kind,venues:Array.isArray(feature.food_venues)?feature.food_venues.filter((v):v is string=>typeof v==='string'):[],
      rings,roof,facades,anchor:[(left+right)/2,(top+bottom)/2-lift] as Point,entrance:place?.entrance??[(left+right)/2,bottom] as Point,
      depth:bottom,bounds:[left,Math.min(...roof[0].map(p=>p[1]),...facades.flat().map(p=>p[1])),right,bottom] as [number,number,number,number]}]
  }).sort((a,b)=>b.depth-a.depth)
}
export function campusBuildingAt(buildings:CampusBuilding[],point:Point) {
  return buildings.find(building=>{
    const [left,top,right,bottom]=building.bounds
    if(point[0]<left||point[0]>right||point[1]<top||point[1]>bottom)return false
    return (pointInRing(point,building.roof[0])&&!building.roof.slice(1).some(hole=>pointInRing(point,hole)))||building.facades.some(face=>pointInRing(point,face))
  })??null
}
