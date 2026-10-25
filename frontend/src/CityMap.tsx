import {useEffect,useMemo,useRef,useState} from 'react'
import {PixelIcon} from './pixel-ui/PixelIcon'
import type {City,DisasterType,Frame,Point,ResidentProfile} from './types'
import {PixelWorld,type BuildingHint,type CameraInsets} from './pixel-world/PixelWorld'
import {ART_VERSION} from './pixel-world/Art'
import type {OpeningCamera} from './pixel-world/OpeningCamera'
import {indexCampusBuildings} from './pixel-world/CampusBuildings'
import {stateColors,stateNames} from './city/CityPalette'
import './pixel-world/PixelWorld.css'

export {stateColors,stateNames} from './city/CityPalette'
export {residentAppearance} from './pixel-world/Art'

export interface CityMapProps {
  onReady?:()=>void;
  onOpeningCamera?:(camera:OpeningCamera|null)=>void;
  city:City;frame:Frame;onSelect?:(id:number)=>void;selected?:number|null;hazardType?:DisasterType;
  playing?:boolean;frameDurationMs?:number;followSelected?:boolean;artSeed?:number;
  placementMode?:boolean;onPlaceOrigin?:(point:Point)=>void;hazardOrigin?:Point;cameraInsets?:CameraInsets;
  onFollowChange?:(enabled:boolean)=>void;
  cameraTarget?:{position:Point;serial:number}|null;
  profiles?:ResidentProfile[];selectedRoute?:Point[]|null;routeAccessible?:boolean|null;
}
export interface PixelComparisonProps extends CityMapProps {
  comparisonFrame:Frame;comparisonArtSeed?:number;labels?:[string,string]
}

function PixelViewport(props:CityMapProps&{comparisonFrame?:Frame;comparisonArtSeed?:number;labels?:[string,string]}) {
  const {city,frame,comparisonFrame,onSelect,onPlaceOrigin,selected,hazardType,playing=false,
    frameDurationMs=220,followSelected=false,placementMode=false,hazardOrigin,cameraInsets,
    artSeed=42,comparisonArtSeed=artSeed,labels,selectedRoute,routeAccessible,profiles}=props
  const canvas=useRef<HTMLCanvasElement>(null),world=useRef<PixelWorld|null>(null)
  const callbacks=useRef({onSelect,onPlaceOrigin,onFollowChange:props.onFollowChange});callbacks.current={onSelect,onPlaceOrigin,onFollowChange:props.onFollowChange}
  const latest=useRef(props);latest.current=props
  const [state,setState]=useState<'loading'|'ready'|'failed'>('loading')
  const [buildingHint,setBuildingHint]=useState<BuildingHint|null>(null),[finding,setFinding]=useState(false),[query,setQuery]=useState('')
  const buildings=useMemo(()=>indexCampusBuildings(city).filter(building=>building.named).sort((a,b)=>a.name.localeCompare(b.name)),[city])
  const terms=query.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean)
  const matches=buildings.filter(building=>terms.every(term=>`${building.name} ${building.venues.join(' ')}`.toLocaleLowerCase().includes(term))).slice(0,7)
  const findBuilding=(id:string)=>{setFinding(false);world.current?.focusBuilding(id);canvas.current?.focus()}
  useEffect(()=>{if(placementMode)setFinding(false)},[placementMode])
  const paired=!!comparisonFrame
  // Pixi destroys its WebGL context at teardown. A different world must receive
  // a fresh canvas; reusing the old DOM canvas can retain a lost context.
  const sceneKey=useMemo(()=>JSON.stringify([city,paired,artSeed,comparisonArtSeed]),[city,paired,artSeed,comparisonArtSeed])
  useEffect(()=> {
    if(!canvas.current)return
    let cancelled=false,created:PixelWorld|null=null
    const controller=new AbortController()
    setState('loading')
    setBuildingHint(null);setFinding(false)
    PixelWorld.create(canvas.current,city,id=>callbacks.current.onSelect?.(id),point=>callbacks.current.onPlaceOrigin?.(point),paired?[artSeed,comparisonArtSeed]:[artSeed],controller.signal,enabled=>callbacks.current.onFollowChange?.(enabled),hint=>{if(!cancelled)setBuildingHint(hint)})
      .then(view=> {
        created=view
        if(cancelled) {view.dispose();return}
        world.current=view
        const p=latest.current
        view.setFrames(p.comparisonFrame?[p.frame,p.comparisonFrame]:[p.frame],p)
        setState('ready')
        p.onOpeningCamera?.(view.openingCamera)
        p.onReady?.()
      }).catch(error=>{if(!cancelled){console.error('Pixel town could not initialize',error);setState('failed')}})
    return ()=>{cancelled=true;controller.abort();latest.current.onOpeningCamera?.(null);created?.dispose();world.current=null}
  },[sceneKey])
  useEffect(()=> {
    world.current?.setFrames(comparisonFrame?[frame,comparisonFrame]:[frame],{playing,frameDurationMs,selected,hazardType,followSelected,placementMode,hazardOrigin,cameraInsets,selectedRoute,routeAccessible,profiles})
  },[frame,comparisonFrame,playing,frameDurationMs,selected,hazardType,followSelected,placementMode,hazardOrigin,cameraInsets,selectedRoute,routeAccessible,profiles])
  useEffect(()=>{if(state==='ready'&&props.cameraTarget)world.current?.focusLocation(props.cameraTarget.position)},[props.cameraTarget,state])
  const clock=frame.world_clock_minutes!=null?`${String(Math.floor(frame.world_clock_minutes/60)%24).padStart(2,'0')}:${String(Math.floor(frame.world_clock_minutes)%60).padStart(2,'0')}`:null
  const indoors=(frame.agent_activities??[]).filter(a=>a.inside).length
  const description=comparisonFrame
    ? `Comparison at ${frame.time} seconds. ${labels?.[0]??'Warning A'}: ${frame.metrics.evacuated} residents sheltered, ${frame.metrics.exposed} ever exposed. ${labels?.[1]??'Warning B'}: ${comparisonFrame.metrics.evacuated} residents sheltered, ${comparisonFrame.metrics.exposed} ever exposed.`
    : clock?`Town at ${clock}. ${frame.agents.length} residents, ${indoors} indoors. ${frame.metrics.evacuated} residents sheltered. Hover or select a building to identify it. Use Find building to search by name.`
    : `Pixel city at ${frame.time} seconds. ${frame.metrics.evacuated} residents sheltered.`
  return <div className={`pixel-world${placementMode?' placing':''}${selected!=null?' has-selection':''}${buildingHint||finding?' discovering-building':''}`} data-art-version={ART_VERSION}>
    <canvas key={sceneKey} ref={canvas} className="pixel-world-canvas" tabIndex={0}
      aria-label={`${description} Drag to pan, scroll or pinch to zoom. Arrow keys pan, plus and minus zoom, Home shows the town, F follows selection.`}
      onKeyDown={event=>{if(world.current?.key(event.key))event.preventDefault()}}/>
    {state==='loading'&&<div className="pixel-world-loading" role="status">Drawing the town…</div>}
    {state==='failed'&&<div className="pixel-world-error" role="alert">The town could not load. Check that WebGL hardware acceleration is enabled, then reload.</div>}
    {paired&&labels&&<div className="pixel-comparison-labels"><span><strong>{labels[0]}</strong><small>{frame.metrics.evacuated} sheltered · <b>{frame.metrics.exposed} ever exposed</b></small></span><span><strong>{labels[1]}</strong><small>{comparisonFrame!.metrics.evacuated} sheltered · <b>{comparisonFrame!.metrics.exposed} ever exposed</b></small></span></div>}
    {city.geography_provenance&&<a className="map-attribution" href={city.geography_provenance.url} target="_blank" rel="noreferrer">© OpenStreetMap contributors</a>}
    {buildingHint&&!finding&&<aside className={`building-hint${buildingHint.pinned?' pinned':''}`} role={buildingHint.pinned?'region':'tooltip'} aria-label="Building information" style={{left:buildingHint.x,top:buildingHint.y}}>
      <div className="building-hint-heading"><strong>{buildingHint.name}</strong>{buildingHint.pinned&&<button type="button" aria-label="Close building information" onClick={()=>{world.current?.dismissBuilding();canvas.current?.focus()}}><PixelIcon name="close" size={14}/></button>}</div>
      {buildingHint.category!==buildingHint.name&&<span>{buildingHint.category}</span>}
      {buildingHint.venues.length>0&&<p>{buildingHint.venues.slice(0,2).join(' · ')}</p>}
      {buildingHint.pinned&&buildingHint.residents.length>0?<button type="button" className="building-residents" onClick={()=>{world.current?.dismissBuilding();callbacks.current.onSelect?.(buildingHint.residents[0])}}>View {buildingHint.residents.length} {buildingHint.residents.length===1?'resident':'residents'} inside <span aria-hidden="true">→</span></button>:<small>{buildingHint.residents.length} {buildingHint.residents.length===1?'resident':'residents'} inside</small>}
    </aside>}
    {finding&&<section className="building-finder" aria-label="Find a building" onKeyDown={event=>{if(event.key==='Escape'){setFinding(false);canvas.current?.focus();event.stopPropagation()}}}>
      <header><strong>Find a building</strong><button type="button" aria-label="Close building search" onClick={()=>{setFinding(false);canvas.current?.focus()}}><PixelIcon name="close" size={14}/></button></header>
      <input autoFocus type="search" aria-label="Building name" placeholder="Search campus buildings…" value={query} onChange={event=>setQuery(event.target.value)} onKeyDown={event=>{if(event.key==='Enter'&&matches.length&&terms.length){event.preventDefault();findBuilding(matches[0].id)}}}/>
      <div className="building-results">{matches.map(building=><button type="button" key={building.id} onClick={()=>findBuilding(building.id)}><strong>{building.name}</strong><small>{building.category}</small></button>)}{!matches.length&&<p role="status">No matching building.</p>}</div>
    </section>}
    {state==='ready'&&<div className="pixel-camera-controls" aria-label="World camera">
      {buildings.length>0&&<button type="button" aria-label="Find building" title="Find a building" disabled={placementMode} aria-expanded={finding} onClick={()=>{world.current?.dismissBuilding();setFinding(value=>!value)}}><PixelIcon name="search" size={16}/></button>}
      <button type="button" aria-label="Zoom in" title="Zoom in (+)" onClick={()=>world.current?.zoom(1.5)}><PixelIcon name="zoom-in" size={16}/></button>
      <button type="button" aria-label="Zoom out" title="Zoom out (−)" onClick={()=>world.current?.zoom(1/1.5)}><PixelIcon name="zoom-out" size={16}/></button>
      <button type="button" aria-label={selected!=null?'Focus selected resident':city.layout==='campus'?'Focus the Oval':'Focus river neighborhood'} title="Focus neighborhood or selected resident" onClick={()=>world.current?.focus()}><PixelIcon name="focus" size={16}/></button>
      <button type="button" aria-label="Show whole town" title="Show whole town (Home)" onClick={()=>world.current?.reset()}><PixelIcon name="fit" size={16}/></button>
    </div>}
  </div>
}

export function CityMap(props:CityMapProps) {return <PixelViewport {...props}/>}
export function PixelComparison(props:PixelComparisonProps) {return <PixelViewport {...props}/>}
export function Legend() {
  return <div className="legend">{[0,4,5,6,7].map(i=><span key={i}><i style={{background:stateColors[i]}}/>{stateNames[i]}</span>)}<span><i className="shelter-key"/>Shelter</span></div>
}
