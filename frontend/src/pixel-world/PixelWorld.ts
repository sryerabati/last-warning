import {Application,Container,Graphics,Sprite} from 'pixi.js'
import type {City,DisasterType,Frame,Point,ResidentProfile} from '../types'
import {ART_VERSION,CELL,loadArt,type TownArt} from './Art'
import {acquireTown} from './CityVisualAdapter'
import {HazardLayer} from './HazardLayer'
import {ResidentLayer} from './ResidentLayer'
import {VehicleLayer} from './VehicleLayer'
import {ReplayClock} from './ReplayClock'
import {TownAtmosphere} from './TownAtmosphere'
import {WeatherLayer} from './WeatherLayer'
import {WeatherSurfaces} from './WeatherSurfaces'
import {bounds} from './TownLifeTypes'
import {campusBuildingAt,indexCampusBuildings,type CampusBuilding} from './CampusBuildings'
import type {OpeningCamera,OpeningLanding,OpeningScreenBounds} from './OpeningCamera'

export interface CameraInsets {top?:number;right?:number;bottom?:number;left?:number}
export interface BuildingHint {id:string;name:string;category:string;venues:string[];residents:number[];pinned:boolean;x:number;y:number}
export interface PixelOptions {
  playing?:boolean;frameDurationMs?:number;selected?:number|null;hazardType?:DisasterType;
  followSelected?:boolean;placementMode?:boolean;hazardOrigin?:Point;cameraInsets?:CameraInsets;
  profiles?:ResidentProfile[];selectedRoute?:Point[]|null;routeAccessible?:boolean|null;
}
interface View {clip:Container;mask:Graphics;root:Container;water:Graphics;route:Graphics;people:ResidentLayer;vehicles:VehicleLayer;hazard:HazardLayer;atmosphere:TownAtmosphere;weather:WeatherLayer;surfaces:WeatherSurfaces;
  markers:Graphics;origin:Graphics;location:Graphics;base:ReturnType<typeof acquireTown>;frame:Frame|null}

/** One app/context, one visual clock, one camera, and one or two clipped world roots. */
export class PixelWorld {
  private app=new Application()
  private views:View[]=[]
  private clock=new ReplayClock()
  private options:PixelOptions={}
  private center:Point=[20,15]
  private initialCenter:Point=[20,15]
  private scale=.5
  private width=0
  private height=0
  private observer:ResizeObserver|null=null
  private raf=0
  private disposed=false
  private contextLost=false
  private dragging=false
  private moved=false
  private pointer:Point=[0,0]
  private pointerOrigin:Point=[0,0]
  private pointers=new Map<number,Point>()
  private pinchDistance=0
  private lastPick={x:0,y:0,index:-1,ids:''}
  private follow=false
  private focusedLocation:{point:Point;footprint?:Point[]}|null=null
  private buildings:CampusBuilding[]=[]
  private buildingFocus:{building:CampusBuilding;view:View;pinned:boolean;pointer?:Point}|null=null
  private buildingHintKey=''
  private hoverTimer:ReturnType<typeof setTimeout>|null=null
  private hoverId=''
  private wheelAt=0
  private openingFlight:{
    saved:{center:Point;scale:number;follow:boolean;location:PixelWorld['focusedLocation'];building:PixelWorld['buildingFocus']}
    landing:OpeningLanding;finalCenter:Point;finalScale:number;scale:number;anchor:Point;layoutKey:string
  }|null=null
  readonly openingCamera:OpeningCamera={begin:()=>this.beginOpening(),pose:(metres,anchor)=>this.poseOpening(metres,anchor),end:completed=>this.endOpening(completed)}
  private roads:Set<string>
  private reduced=matchMedia('(prefers-reduced-motion: reduce)')
  private mediaListener=()=>{this.clock.reduced=this.reduced.matches;this.render();this.schedule()}
  private loseContext=(event:Event)=> {
    event.preventDefault();this.contextLost=true;this.canvas.dataset.context='lost'
    if(this.raf)cancelAnimationFrame(this.raf)
    this.raf=0;this.canvas.dataset.animating='false'
  }
  private restoreContext=()=> {
    this.contextLost=false;this.canvas.dataset.context='ready';this.render();this.schedule()
  }
  private constructor(private canvas:HTMLCanvasElement,private city:City,
    private select:(id:number)=>void,private place:(point:Point)=>void,
    private followChanged:((enabled:boolean)=>void)|undefined,private buildingChanged?:((hint:BuildingHint|null)=>void)) {
      this.roads=new Set(city.roads.map(([x,y])=>`${x},${y}`))
      this.buildings=indexCampusBuildings(city)
      if(city.layout==='campus'){this.initialCenter=(city as City&{camera_focus?:Point}).camera_focus??[19,20.5];this.center=[...this.initialCenter]}
      if(city.layout==='organic') {
        const hub=city.places?.find(p=>p.kind==='shop')??city.places?.find(p=>p.kind==='civic')
        if(hub) {
          const b=bounds(hub),hx=b.x+b.w/2,hy=b.y+b.h/2
          const bridge=(city.road_styles??[]).filter(s=>s.kind==='bridge').sort((a,b)=>
            Math.hypot(a.position[0]-hx,a.position[1]-hy)-Math.hypot(b.position[0]-hx,b.position[1]-hy))[0]
          this.initialCenter=bridge?[(hx+bridge.position[0]+.5)/2,(hy+bridge.position[1]+.5)/2]:[hx,hy]
          this.center=[...this.initialCenter]
        }
      }
    }

  static async create(canvas:HTMLCanvasElement,city:City,select:(id:number)=>void,
    place:(point:Point)=>void,seeds:number[],signal?:AbortSignal,followChanged?:(enabled:boolean)=>void,buildingChanged?:((hint:BuildingHint|null)=>void)) {
    const view=new PixelWorld(canvas,city,select,place,followChanged,buildingChanged)
    try {await view.initialize(seeds,signal);return view}
    catch(error) {view.dispose();throw error}
  }
  private async initialize(seeds:number[],signal?:AbortSignal) {
    const [art]=await Promise.all([loadArt(),document.fonts.load('600 17px "Pixelify Sans"').catch(()=>[]),document.fonts.load('600 20px "Pixelify Sans"').catch(()=>[])])
    signal?.throwIfAborted()
    await this.app.init({canvas:this.canvas,preference:'webgl',antialias:false,autoStart:false,
      width:Math.max(1,this.canvas.clientWidth),height:Math.max(1,this.canvas.clientHeight),
      backgroundColor:0x324f43,resolution:Math.min(devicePixelRatio||1,2),autoDensity:true,
      powerPreference:'high-performance',roundPixels:true})
    signal?.throwIfAborted()
    this.app.stop()
    this.canvas.dataset.renderer='pixi-webgl'
    this.canvas.dataset.worlds=String(seeds.length)
    this.canvas.dataset.context='ready'
    for(const seed of seeds)this.addView(art,seed)
    this.canvas.dataset.sceneryObjects=String(this.views[0]?.base.scenery.length??0)
    this.canvas.addEventListener('pointerdown',this.down)
    this.canvas.addEventListener('pointermove',this.move)
    this.canvas.addEventListener('pointerleave',this.leave)
    this.canvas.addEventListener('pointerup',this.up)
    this.canvas.addEventListener('pointercancel',this.cancel)
    this.canvas.addEventListener('wheel',this.wheel,{passive:false})
    this.canvas.addEventListener('webglcontextlost',this.loseContext)
    this.canvas.addEventListener('webglcontextrestored',this.restoreContext)
    this.reduced.addEventListener('change',this.mediaListener)
    this.observer=new ResizeObserver(()=>this.resize())
    this.observer.observe(this.canvas.parentElement!)
    this.resize(true)
  }
  private addView(art:TownArt,seed:number) {
    const clip=new Container(),mask=new Graphics(),root=new Container()
    const base=acquireTown(this.city,art),terrain=new Sprite(base.texture)
    const depth=this.city.layout==='campus'?new Container():undefined
    if(depth){depth.sortableChildren=true;for(const item of base.scenery){const sprite=new Sprite(item.texture);sprite.position.set(item.x,item.y);sprite.zIndex=item.depth;depth.addChild(sprite)}}
    const hazard=new HazardLayer(art,this.city.layout==='campus',depth),people=new ResidentLayer(art,seed,this.city,[],depth),atmosphere=new TownAtmosphere(this.city)
    const vehicles=new VehicleLayer(seed,depth,this.city.meters_per_unit??24.25)
    const weather=new WeatherLayer(this.city),surfaces=new WeatherSurfaces(this.city,depth)
    const water=new Graphics(),markers=new Graphics(),origin=new Graphics(),route=new Graphics(),location=new Graphics()
    if(depth)root.addChild(terrain,surfaces.ground,water,weather.ground,hazard.root,markers,hazard.closures,route,depth,atmosphere.shade,vehicles.root,people.root,atmosphere.lights,atmosphere.interactions,location,origin)
    else root.addChild(terrain,surfaces.ground,water,weather.ground,hazard.root,markers,hazard.closures,route,surfaces.roofs,atmosphere.shade,vehicles.root,people.root,atmosphere.lights,atmosphere.interactions,location,origin)
    clip.addChild(root,weather.screen);clip.mask=mask;this.app.stage.addChild(clip,mask)
    this.views.push({clip,mask,root,water,route,people,vehicles,hazard,atmosphere,weather,surfaces,markers,origin,location,base,frame:null})
    for(const [x,y] of this.city.safe_zones) {
      const px=(x+.5)*CELL,py=(y+.5)*CELL
      markers.rect(px-17,py-15,34,30).rect(px-15,py-17,30,34).fill(0xe8dfbb)
      markers.rect(px-15,py-13,30,26).rect(px-13,py-15,26,30).fill(0x2f594c)
      markers.rect(px-3,py-11,6,22).rect(px-11,py-3,22,6).fill(0xe8dfbb)
    }
  }
  setFrames(frames:Frame[],options:PixelOptions) {
    const prior=this.options;this.options=options
    if(options.placementMode||prior.selected!==options.selected)this.clearBuilding()
    if(prior.followSelected!==options.followSelected||prior.selected!==options.selected){this.follow=!!options.followSelected;if(this.follow||prior.selected!==options.selected)this.focusedLocation=null}
    if(this.focusedLocation&&prior.cameraInsets!==options.cameraInsets)this.center=[...this.focusedLocation.point]
    if(this.openingFlight&&prior.cameraInsets!==options.cameraInsets)this.refreshOpeningLanding()
    for(let i=0;i<this.views.length;i++) {
      const view=this.views[i],frame=frames[i]??frames[0]
      if(view.frame!==frame) {view.hazard.setFrame(frame,options.hazardType);view.atmosphere.setFrame(frame);view.weather.setFrame(frame,!!options.playing);view.frame=frame}
      if(prior.profiles!==options.profiles)view.people.setProfiles(options.profiles??[])
      view.people.setFrame(frame,options.selected??null)
      view.vehicles.setFrame(frame,options.selected??null)
    }
    this.clock.set(frames[0].tick,!!options.playing,options.frameDurationMs??220)
    this.canvas.dataset.residents=frames.map(frame=>frame.agents.length).join(',')
    this.canvas.dataset.tick=String(frames[0].tick)
    this.canvas.dataset.indoors=frames.map(frame=>(frame.agent_activities??[]).filter(a=>a.inside).length).join(',')
    this.canvas.dataset.vehicles=String(frames[0].vehicles?.length??0)
    this.canvas.dataset.clockMinutes=String(frames[0].world_clock_minutes??'')
    this.render();this.schedule()
  }
  private drawRoute() {
    for(const view of this.views)view.route.clear()
    this.canvas.dataset.routeVisible='false'
    const view=this.views.at(-1),path=this.options.selectedRoute
    if(!view?.frame||!path?.length||this.options.routeAccessible!==true||this.options.selected==null)return
    const resident=view.frame.agents.find(a=>a[0]===this.options.selected)
    if(!resident||path[0][0]!==resident[1]||path[0][1]!==resident[2])return
    const blocked=new Set(view.frame.blocked_roads.map(([x,y])=>`${x},${y}`))
    const valid=this.city.layout==='campus'?path.every(p=>p.length===2&&p.every(Number.isFinite)&&!blocked.has(`${p[0]},${p[1]}`)):path.every((p,i)=>p.length===2&&p.every(Number.isInteger)&&this.roads.has(`${p[0]},${p[1]}`)&&
      !blocked.has(`${p[0]},${p[1]}`)&&(!i||Math.abs(p[0]-path[i-1][0])+Math.abs(p[1]-path[i-1][1])===1))
    if(!valid)return
    this.canvas.dataset.routeVisible='true'
    const offset=this.city.layout==='campus'?0:.5
    const trace=(width:number,color:number)=> {
      view.route.moveTo((path[0][0]+offset)*CELL,(path[0][1]+offset)*CELL)
      for(const [x,y] of path.slice(1))view.route.lineTo((x+offset)*CELL,(y+offset)*CELL)
      view.route.stroke({color,width:width/this.scale,alpha:.95})
    }
    trace(4,0x273d40);trace(2,0xdcbd70)
    const end=path.at(-1)!,x=(end[0]+offset)*CELL,y=(end[1]+offset)*CELL
    const radius=7/this.scale
    view.route.poly([x,y-radius,x+radius,y,x,y+radius,x-radius,y,x,y-radius]).fill(0x273d40).stroke({color:0xf3e3a8,width:2/this.scale})
  }
  private schedule() {
    if(this.raf)cancelAnimationFrame(this.raf)
    this.raf=0
    this.canvas.dataset.animating=String(!this.disposed&&!this.contextLost&&this.clock.playing&&!this.clock.reduced)
    if(this.disposed||this.contextLost||!this.clock.playing||this.clock.reduced)return
    this.raf=requestAnimationFrame(()=>{this.raf=0;this.render();this.schedule()})
  }
  private resize(initial=false) {
    const box=this.canvas.parentElement!.getBoundingClientRect()
    this.width=Math.max(1,Math.round(box.width));this.height=Math.max(1,Math.round(box.height))
    this.app.renderer.resize(this.width,this.height)
    if(initial) {
      const usableHeight=Math.max(250,this.height-210)
      this.scale=this.width<600?(this.city.layout==='organic'?.625:.5):Math.max(this.width/(this.city.size*CELL),Math.min(this.city.layout==='organic'?1:.75,usableHeight/(CELL*(this.city.layout==='organic'?15:19))))
      if(this.city.layout==='campus')this.scale=this.width<600?.75:1
      this.scale=this.alignedScale(Math.ceil(this.scale*8)/8)
    }
    if(this.focusedLocation)this.center=[...this.focusedLocation.point]
    if(this.openingFlight)this.refreshOpeningLanding()
    this.render()
  }
  private layout(allowOpening=true) {
    const count=this.views.length,gap=count===2?4:0,vw=(this.width-gap)/count
    if(allowOpening&&this.openingFlight){
      const flight=this.openingFlight,view=this.views[0]
      this.scale=flight.scale
      view.mask.clear().rect(0,0,this.width,this.height).fill(0xffffff)
      view.root.scale.set(this.scale)
      view.root.position.set(Math.round(flight.anchor[0]*this.width-this.initialCenter[0]*CELL*this.scale),Math.round(flight.anchor[1]*this.height-this.initialCenter[1]*CELL*this.scale))
      this.canvas.dataset.mapScreenBounds=JSON.stringify(this.openingBounds())
      return
    }
    const insets=this.options.cameraInsets??{}
    const defaultBottom=this.city.layout==='campus'?(this.width<600?220:210):140
    const top=Math.max(0,Math.min(this.height-1,insets.top??82)),bottom=Math.max(0,Math.min(this.height-top-1,insets.bottom??defaultBottom))
    const left=Math.max(0,Math.min(vw-1,insets.left??0)),right=Math.max(0,Math.min(vw-left-1,insets.right??0))
    const map=this.city.layout==='campus'?this.city.map_bounds:undefined
    if(map?.length===4&&map.every(Number.isFinite)){
      // Clamp the unobstructed viewport to surveyed geography. At overview
      // scale, center a smaller map instead of oscillating between its edges.
      const clampAxis=(value:number,min:number,max:number,half:number)=>max-min<=half*2?(min+max)/2:Math.max(min+half,Math.min(max-half,value))
      const halfW=(vw-left-right)/(2*CELL*this.scale),halfH=(this.height-top-bottom)/(2*CELL*this.scale)
      this.center=[clampAxis(this.center[0],map[0],map[2],halfW),clampAxis(this.center[1],map[1],map[3],halfH)]
    }
    for(let i=0;i<count;i++) {
      const view=this.views[i],start=i*(vw+gap)
      view.mask.clear().rect(start,0,vw,this.height).fill(0xffffff)
      view.root.scale.set(this.scale)
      view.root.position.set(Math.round(start+(vw+left-right)/2-this.center[0]*CELL*this.scale),
        Math.round((this.height+top-bottom)/2-this.center[1]*CELL*this.scale))
      if(i===0&&map)this.canvas.dataset.mapScreenBounds=JSON.stringify([map[0]*CELL*this.scale+view.root.x,map[1]*CELL*this.scale+view.root.y,map[2]*CELL*this.scale+view.root.x,map[3]*CELL*this.scale+view.root.y].map(Math.round))
    }
  }
  private render() {
    if(this.disposed||this.contextLost||!this.app.renderer)return
    const fraction=this.clock.fraction,time=this.clock.time,animationTime=this.clock.animationTime
    this.drawRoute()
    for(const view of this.views) {
      const animate=this.clock.playing&&!this.clock.reduced
      view.surfaces.setSnow(view.weather.state(fraction)?.snowCover??0)
      // The ordinary overview marker has a fixed screen size. At continental
      // flight scales it would cover the entire campus with resident dots.
      view.people.root.visible=!this.openingFlight||this.scale>=.0625
      view.vehicles.draw(fraction,animationTime,animate,view.atmosphere.night,this.clock.reduced);view.people.draw(fraction,animationTime,animate,view.atmosphere.night,this.scale)
      view.atmosphere.draw(fraction,animationTime,animate,view.people,this.options.selected??null,this.scale);view.hazard.draw(animationTime,fraction,animate,this.scale,this.clock.reduced)
      view.location.clear()
      if(this.buildingFocus?.view===view){
        for(const ring of this.buildingFocus.building.roof){
          const outline=ring.map(([x,y])=>[x*CELL,y*CELL]).flat()
          view.location.poly(outline).stroke({color:0x263e32,width:4/this.scale,alpha:.8})
          view.location.poly(outline).stroke({color:0xf0d483,width:1.5/this.scale,alpha:.95})
        }
      }
      if(this.focusedLocation){
        const {point,footprint}=this.focusedLocation,unit=1/this.scale,px=point[0]*CELL,py=point[1]*CELL
        if(footprint?.length){const outline=footprint.map(([x,y])=>[x*CELL,y*CELL]).flat()
          view.location.poly(outline).fill({color:0xf0d483,alpha:.10}).stroke({color:0x334d3d,width:4*unit,alpha:.9})
          view.location.poly(outline).stroke({color:0xf2d88c,width:2*unit,alpha:.95})}
        // A small fixed-screen-size entrance pin stays legible when zooming.
        view.location.poly([px,py-3*unit,px-7*unit,py-13*unit,px-7*unit,py-23*unit,px+7*unit,py-23*unit,px+7*unit,py-13*unit]).fill(0xf0d483).stroke({color:0x334d3d,width:2*unit})
        view.location.rect(px-2*unit,py-20*unit,4*unit,5*unit).fill(0x405842)
      }
      view.water.clear()
      // The permanent river has a restrained replay-clock surface animation.
      for(let i=0;i<this.city.river.length;i+=4) {
        const [x,y]=this.city.river[i]
        if(this.roads.has(`${x},${y}`))continue
        const px=x*CELL+12+(i%3)*11,py=y*CELL+((time*4+i*9)%48)+8
        view.water.moveTo(Math.round(px),Math.round(py)).lineTo(Math.round(px+11),Math.round(py))
      }
      view.water.stroke({color:0xb1cec0,width:1,alpha:.38})
      view.origin.clear()
      const origin=this.options.hazardOrigin
      if(origin&&(!view.frame||view.frame.tick===0||this.options.placementMode)) {
        const offset=this.city.layout==='campus'?0:.5,px=(origin[0]+offset)*CELL,py=(origin[1]+offset)*CELL
        view.origin.rect(px-22,py-22,44,44).stroke({color:0xe8dfbb,width:2,alpha:.9})
        view.origin.moveTo(px-29,py).lineTo(px-15,py).moveTo(px+15,py).lineTo(px+29,py)
          .moveTo(px,py-29).lineTo(px,py-15).moveTo(px,py+15).lineTo(px,py+29).stroke({color:0xdcbd70,width:3})
      }
    }
    const night=this.views[0]?.atmosphere.night??0
    const mix=(day:number,dark:number)=>Math.round(day+(dark-day)*night)
    this.app.renderer.background.color=(mix(50,23)<<16)+(mix(79,37)<<8)+mix(67,51)
    if(!this.openingFlight&&this.follow&&this.options.selected!=null) {
      const p=this.views.at(-1)?.vehicles.positionForResident(this.options.selected)??this.views.at(-1)?.people.position(this.options.selected);if(p)this.center=p
    }
    this.canvas.dataset.locationFocus=this.focusedLocation?.point.join(',')??''
    this.layout()
    const gap=this.views.length===2?4:0,viewWidth=(this.width-gap)/this.views.length
    this.views.forEach((view,index)=>{
      view.weather.screen.visible=!this.openingFlight
      view.weather.draw(animationTime,fraction,this.clock.playing&&!this.clock.reduced,this.clock.reduced,
        {x:index*(viewWidth+gap),y:0,width:viewWidth,height:this.height,worldX:view.root.x-index*(viewWidth+gap),worldY:view.root.y,scale:this.scale})
    })
    this.canvas.dataset.weather=JSON.stringify(this.views.map(view=>view.weather.diagnostics))
    this.publishBuilding();this.app.render()
  }
  private openingLayoutKey(){const i=this.options.cameraInsets;return [this.width,this.height,i?.top,i?.right,i?.bottom,i?.left].join(',')}
  private openingPlan():{landing:OpeningLanding;finalCenter:Point;finalScale:number}|null {
    const map=this.city.map_bounds,provenance=this.city.geography_provenance as (City['geography_provenance']&{selection_bbox?:number[]})
    const geo=provenance?.selection_bbox,metres=this.city.meters_per_unit
    if(this.disposed||this.contextLost||this.city.layout!=='campus'||this.views.length!==1||!map||map.length!==4||!geo||geo.length!==4||!metres||metres<=0||!map.every(Number.isFinite)||!geo.every(Number.isFinite)||map[2]<=map[0]||map[3]<=map[1]||geo[2]<=geo[0]||geo[3]<=geo[1])return null
    const savedCenter=this.center,savedScale=this.scale
    // Obtain the destination from ordinary layout itself, including its map
    // clamps, HUD insets and pixel rounding. Do not approximate a second camera.
    this.center=[...this.initialCenter];this.scale=this.alignedScale(1);this.layout(false)
    const finalCenter:Point=[...this.center],finalScale=this.scale,root=this.views[0].root
    const landing:OpeningLanding={
      target:[geo[0]+(this.initialCenter[0]-map[0])/(map[2]-map[0])*(geo[2]-geo[0]),geo[3]-(this.initialCenter[1]-map[1])/(map[3]-map[1])*(geo[3]-geo[1])],
      metersPerPixel:metres/(CELL*finalScale),
      metersPerDegree:[(map[2]-map[0])*metres/(geo[2]-geo[0]),(map[3]-map[1])*metres/(geo[3]-geo[1])],
      anchor:[(this.initialCenter[0]*CELL*finalScale+root.x)/this.width,(this.initialCenter[1]*CELL*finalScale+root.y)/this.height],
      viewport:[this.width,this.height],geographicBounds:[geo[0],geo[1],geo[2],geo[3]],
    }
    this.center=savedCenter;this.scale=savedScale;this.layout()
    return {landing,finalCenter,finalScale}
  }
  private refreshOpeningLanding(){
    const flight=this.openingFlight;if(!flight)return
    const plan=this.openingPlan();if(!plan)return
    flight.landing=plan.landing;flight.finalCenter=plan.finalCenter;flight.finalScale=plan.finalScale;flight.layoutKey=this.openingLayoutKey()
  }
  private beginOpening():OpeningLanding|null {
    if(this.disposed||this.contextLost)return null
    if(this.openingFlight){if(this.openingFlight.layoutKey!==this.openingLayoutKey())this.refreshOpeningLanding();return this.openingFlight.landing}
    const plan=this.openingPlan();if(!plan)return null
    const saved={center:[...this.center] as Point,scale:this.scale,follow:this.follow,location:this.focusedLocation,building:this.buildingFocus}
    this.clearBuilding();this.setFollow(false);this.focusedLocation=null
    this.openingFlight={saved,...plan,scale:plan.finalScale,anchor:[...plan.landing.anchor],layoutKey:this.openingLayoutKey()}
    this.canvas.dataset.openingActive='true';this.canvas.dataset.openingTarget=plan.landing.target.join(',')
    this.render()
    return plan.landing
  }
  private openingBounds():OpeningScreenBounds {
    const map=this.city.map_bounds,root=this.views[0]?.root
    if(this.disposed||!map||!root)return [0,0,0,0]
    return [map[0]*CELL*this.scale+root.x,map[1]*CELL*this.scale+root.y,map[2]*CELL*this.scale+root.x,map[3]*CELL*this.scale+root.y]
  }
  private poseOpening(metres:number,anchor:Point):OpeningScreenBounds {
    const flight=this.openingFlight
    if(this.disposed||this.contextLost||!flight)return [0,0,0,0]
    if(!Number.isFinite(metres)||metres<=0||anchor.length!==2||!anchor.every(Number.isFinite))return this.openingBounds()
    flight.scale=this.city.meters_per_unit!/(CELL*metres);flight.anchor=[...anchor];this.scale=flight.scale
    this.canvas.dataset.openingMetersPerPixel=String(metres);this.canvas.dataset.openingAnchor=anchor.join(',')
    this.render()
    const bounds=this.openingBounds();this.canvas.dataset.openingBounds=JSON.stringify(bounds)
    return bounds
  }
  private endOpening(completed:boolean){
    const flight=this.openingFlight;if(this.disposed||!flight)return
    this.refreshOpeningLanding();this.openingFlight=null
    if(completed){this.center=[...flight.finalCenter];this.scale=flight.finalScale;this.setFollow(false);this.focusedLocation=null}
    else {this.center=[...flight.saved.center];this.scale=flight.saved.scale;this.setFollow(flight.saved.follow);this.focusedLocation=flight.saved.location;this.buildingFocus=flight.saved.building}
    this.canvas.dataset.openingActive='false'
    this.render();this.schedule()
  }
  private alignedScale(value:number) {const resolution=this.app.renderer?.resolution??1;return value>=.5?Math.max(.5,Math.round(value*resolution)/resolution):value}
  zoom(factor:number,at?:Point) {
    this.clearBuilding()
    const before=at?this.worldPoint(at):null,levels=[...new Set([.0625,.09375,.125,.1875,.25,.375,.5,.75,1,1.5,2,3,4].map(value=>this.alignedScale(value)))].sort((a,b)=>a-b)
    const next=factor>1?levels.find(z=>z>this.scale+.001):[...levels].reverse().find(z=>z<this.scale-.001)
    this.scale=next??this.scale
    if(before&&at) {
      this.layout();const after=this.worldPoint(at)
      this.center=[this.center[0]+(before[0]-after[0])/CELL,this.center[1]+(before[1]-after[1])/CELL]
    }
    this.render()
  }
  reset() {
    this.clearBuilding()
    const [left,top,right,bottom]=this.city.layout==='campus'&&this.city.map_bounds?this.city.map_bounds:[0,0,this.city.size,this.city.size]
    this.setFollow(false);this.focusedLocation=null;this.center=[(left+right)/2,(top+bottom)/2]
    const vw=this.width/this.views.length
    const insets=this.options.cameraInsets??{},defaultBottom=this.city.layout==='campus'?(this.width<600?220:210):140
    const usableWidth=Math.max(1,vw-(insets.left??0)-(insets.right??0)-24),usableHeight=Math.max(1,this.height-(insets.top??82)-(insets.bottom??defaultBottom)-24)
    this.scale=Math.max(.0625,Math.min(usableWidth/((right-left)*CELL),usableHeight/((bottom-top)*CELL)))
    this.render()
  }
  focus() {
    this.clearBuilding()
    this.focusedLocation=null
    const p=this.options.selected!=null?this.views.at(-1)?.vehicles.positionForResident(this.options.selected)??this.views.at(-1)?.people.position(this.options.selected):null
    this.center=p??[...this.initialCenter];this.scale=this.alignedScale(this.city.layout==='campus'?(p?1.5:1):this.width<600?1:.75);this.render()
  }
  focusLocation(point:Point) {
    if(point.length!==2||!point.every(Number.isFinite))return
    this.clearBuilding()
    const place=this.city.places?.find(place=>Math.hypot(place.entrance[0]-point[0],place.entrance[1]-point[1])<.0001)
    this.setFollow(false);this.focusedLocation={point:[...point],footprint:place?.footprint};this.center=[...point]
    this.scale=this.alignedScale(this.city.layout==='campus'?1:this.width<600?1:.75);this.render()
  }
  focusBuilding(id:string) {
    const building=this.buildings.find(value=>value.id===id)
    if(!building)return
    this.clearBuilding();this.setFollow(false);this.focusedLocation=null
    this.center=[...building.anchor];this.scale=this.alignedScale(1)
    this.buildingFocus={building,view:this.views.at(-1)!,pinned:true};this.render()
  }
  dismissBuilding(){this.clearBuilding();this.render()}
  private clearBuilding(){
    if(this.hoverTimer)clearTimeout(this.hoverTimer)
    this.hoverTimer=null;this.hoverId='';this.buildingFocus=null
    if(this.buildingHintKey){this.buildingHintKey='';this.canvas.dataset.building='';this.buildingChanged?.(null)}
  }
  private publishBuilding(){
    const focus=this.buildingFocus
    if(!focus)return
    const {building,view,pinned}=focus,point=focus.pointer??[building.anchor[0]*CELL*this.scale+view.root.x,building.anchor[1]*CELL*this.scale+view.root.y]
    const ids=view.people.occupiedPlaces().find(value=>value.place.id===building.id)?.ids??[]
    const width=Math.min(260,this.width-24),height=156,right=this.options.cameraInsets?.right??0
    const x=Math.max(12,Math.min(this.width-right-width-12,point[0]+18))
    const maxY=Math.max(100,this.height-(this.width<=700?230:210)-height-12)
    const y=Math.max(100,Math.min(maxY,point[1]+20>maxY?point[1]-height-18:point[1]+20))
    const hint:BuildingHint={id:building.id,name:building.name,category:building.category,venues:building.venues,residents:ids,pinned,x:Math.round(x),y:Math.round(y)}
    const key=JSON.stringify(hint)
    if(key!==this.buildingHintKey){this.buildingHintKey=key;this.canvas.dataset.building=building.id;this.buildingChanged?.(hint)}
  }
  key(key:string):boolean {
    if(key==='Escape'&&this.buildingFocus){this.dismissBuilding();return true}
    if(key==='+'||key==='=')this.zoom(1.5)
    else if(key==='-')this.zoom(1/1.5)
    else if(key==='Home'||key==='0')this.reset()
    else if(key.toLowerCase()==='f') {if(this.options.selected!=null)this.setFollow(!this.follow);this.focus()}
    else if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(key)) {
      this.clearBuilding()
      this.setFollow(false);this.focusedLocation=null;const step=64/(this.scale*CELL)
      this.center=[this.center[0]+(key==='ArrowLeft'?-step:key==='ArrowRight'?step:0),this.center[1]+(key==='ArrowUp'?-step:key==='ArrowDown'?step:0)];this.render()
    } else return false
    return true
  }
  private local(event:PointerEvent|WheelEvent):Point {
    const r=this.canvas.getBoundingClientRect();return [event.clientX-r.left,event.clientY-r.top]
  }
  private setFollow(enabled:boolean) {
    if(enabled)this.focusedLocation=null
    if(this.follow===enabled)return
    this.follow=enabled;this.followChanged?.(enabled)
  }
  private viewAt(point:Point) {return this.views[Math.min(this.views.length-1,Math.floor(point[0]/(this.width/this.views.length)))]}
  private worldPoint(point:Point):Point {
    const view=this.viewAt(point);return [(point[0]-view.root.x)/this.scale,(point[1]-view.root.y)/this.scale]
  }
  private down=(event:PointerEvent)=> {
    if(event.button!==0)return
    const p=this.local(event);this.pointers.set(event.pointerId,p);this.canvas.setPointerCapture(event.pointerId)
    this.pointer=p;this.pointerOrigin=p;this.dragging=true;this.moved=false
    this.canvas.focus({preventScroll:true})
    if(this.pointers.size===2) {const a=[...this.pointers.values()];this.pinchDistance=Math.hypot(a[0][0]-a[1][0],a[0][1]-a[1][1]);this.moved=true}
  }
  private move=(event:PointerEvent)=> {
    if(!this.dragging) {
      if(event.pointerType==='touch'||this.options.placementMode||this.buildingFocus?.pinned)return
      const p=this.local(event),point=this.worldPoint(p),view=this.viewAt(p),building=campusBuildingAt(this.buildings,[point[0]/CELL,point[1]/CELL])
      if(!building){if(this.hoverId||this.buildingFocus){this.clearBuilding();this.render()}return}
      if(this.hoverId===building.id)return
      this.clearBuilding();this.hoverId=building.id
      this.hoverTimer=setTimeout(()=>{this.hoverTimer=null;this.buildingFocus={building,view,pinned:false,pointer:p};this.render()},160)
      return
    }
    if(!this.pointers.has(event.pointerId))return
    const p=this.local(event);this.pointers.set(event.pointerId,p)
    if(this.pointers.size===2) {
      const a=[...this.pointers.values()],distance=Math.hypot(a[0][0]-a[1][0],a[0][1]-a[1][1])
      if(distance/this.pinchDistance>1.18||distance/this.pinchDistance<.84) {this.zoom(distance/this.pinchDistance,[(a[0][0]+a[1][0])/2,(a[0][1]+a[1][1])/2]);this.pinchDistance=distance}
      this.moved=true;return
    }
    const dx=p[0]-this.pointer[0],dy=p[1]-this.pointer[1]
    if(Math.hypot(p[0]-this.pointerOrigin[0],p[1]-this.pointerOrigin[1])>4)this.moved=true
    if(this.moved) {this.clearBuilding();this.setFollow(false);this.focusedLocation=null;this.center=[this.center[0]-dx/(CELL*this.scale),this.center[1]-dy/(CELL*this.scale)];this.render()}
    this.pointer=p
  }
  private up=(event:PointerEvent)=> {
    this.pointers.delete(event.pointerId)
    if(!this.moved&&this.dragging) {
      const p=this.local(event),point=this.worldPoint(p)
      if(this.options.placementMode) {
        const cell:Point=[Math.floor(point[0]/CELL),Math.floor(point[1]/CELL)]
        if(cell.every(c=>c>=0&&c<this.city.size))this.place(cell)
      } else {
        const view=this.viewAt(p),building=campusBuildingAt(this.buildings,[point[0]/CELL,point[1]/CELL])
        const people=view.people.pick(point[0],point[1],Math.max(11,22/this.scale)).filter(id=>!building||(view.people.visiblePosition(id)?.[1]??0)>=building.depth)
        const cars=view.vehicles.pick(point[0],point[1],Math.max(14,22/this.scale)).filter(id=>!building||(view.vehicles.positionForResident(id)?.[1]??0)>=building.depth)
        const ids=cars.length?cars:people.length?people:!this.buildings.length?view.people.buildingAt(...point)?.ids??[]:[]
        if(ids.length) {
          this.clearBuilding()
          const signature=ids.join(','),repeat=signature===this.lastPick.ids&&Math.hypot(p[0]-this.lastPick.x,p[1]-this.lastPick.y)<8
          const index=repeat?(this.lastPick.index+1)%ids.length:0
          this.lastPick={x:p[0],y:p[1],index,ids:signature};this.select(ids[index])
        }else{this.clearBuilding();if(building)this.buildingFocus={building,view,pinned:true};this.render()}
      }
    }
    this.dragging=this.pointers.size>0;if(this.pointers.size)this.pointer=[...this.pointers.values()][0]
  }
  private cancel=()=>{this.pointers.clear();this.dragging=false}
  private leave=()=>{if(!this.buildingFocus?.pinned){this.clearBuilding();this.render()}}
  private wheel=(event:WheelEvent)=> {
    event.preventDefault();if(performance.now()-this.wheelAt<80)return
    this.wheelAt=performance.now();this.setFollow(false);this.zoom(event.deltaY<0?1.5:1/1.5,this.local(event))
  }
  diagnostics() {return {renderer:'PixiJS WebGL',worlds:this.views.length,canvases:1,residents:this.views.map(v=>v.frame?.agents.length??0),indoors:this.views.map(v=>(v.frame?.agent_activities??[]).filter(a=>a.inside).length),occupiedPlaces:this.views.map(v=>v.people.occupiedPlaces().length),artVersion:ART_VERSION,scale:this.scale,animating:!!this.raf}}
  dispose() {
    this.disposed=true;this.openingFlight=null;if(this.raf)cancelAnimationFrame(this.raf)
    if(this.hoverTimer)clearTimeout(this.hoverTimer)
    this.observer?.disconnect();this.reduced.removeEventListener('change',this.mediaListener)
    this.canvas.removeEventListener('pointerdown',this.down);this.canvas.removeEventListener('pointermove',this.move)
    this.canvas.removeEventListener('pointerup',this.up);this.canvas.removeEventListener('pointercancel',this.cancel);this.canvas.removeEventListener('wheel',this.wheel)
    this.canvas.removeEventListener('pointerleave',this.leave)
    this.canvas.removeEventListener('webglcontextlost',this.loseContext);this.canvas.removeEventListener('webglcontextrestored',this.restoreContext)
    for(const view of this.views){view.people.destroy();view.vehicles.destroy();view.weather.destroy();view.surfaces.destroy();view.base.release()}
    if(this.app.renderer)this.app.destroy({removeView:false},{children:true,texture:false,textureSource:false})
  }
}
