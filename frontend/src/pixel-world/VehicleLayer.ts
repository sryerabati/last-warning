import {Container,Graphics,Rectangle,Sprite,Texture} from 'pixi.js'
import type {AgentImpact,BusStop,Frame,Point} from '../types'
import {CELL} from './Art'
import {paintBusPlates} from './BusArt'
import {busVisibleAt,type VehicleVisibility} from './VehiclePresentation'
import {weatherAt} from './WeatherPresentation'
import {pixelEllipse,pixelLine} from './PixelEffectsGeometry'
import {vehicleConditionAt,vehicleImpactAt,vehicleMotionAt,vehicleWeatherPose,type VehicleCondition,type VehicleImpact,type VehicleStateChange} from './VehicleWeatherPresentation'

interface Vehicle extends VehicleCondition {id:string;x:number;y:number;type:string;color:number|string;state:string;occupant_ids:number[];driver_id:number|null;capacity:number;heading?:number;lane_offset_m?:number;service_active?:boolean;route_name?:string;next_stop_name?:string}
interface Motion {id:string;path:Point[];fractions:number[]}
interface Activity {id:number;mode?:string;vehicle_id?:string|null;fraction?:number}
interface Car {sprite:Sprite;effects:Graphics;ground:Graphics;data:Vehicle;x:number;y:number;direction:number;occupants:number[]}
const riding=(a:Activity)=>a.mode==='riding'||a.mode==='driving'
const near=(a:Point,b:Point)=>Math.hypot(a[0]-b[0],a[1]-b[1])<.00001
const COLORS=['#b0584d','#d6c8a1','#63869a','#6e856b','#4e595e','#b69a60','#84718e','#5f9793']
const shade=(color:string,delta:number)=>'#'+[16,8,0].map(s=>Math.max(0,Math.min(255,((parseInt(color.slice(1),16)>>s)&255)+delta)).toString(16).padStart(2,'0')).join('')

/** Original four-facing vehicle plates. The visible car carries the occupants
 * recorded by the simulation; no decorative cars travel independently. */
export class VehicleLayer {
  readonly root=new Container()
  private cars=new Map<string,Car>()
  private motions=new Map<string,Motion>()
  private transitions=new Map<number,Activity[]>()
  private visibility=new Map<string,VehicleVisibility[]>()
  private activities:Activity[]=[]
  private priorActivities=new Map<number,Activity>()
  private priorConditions=new Map<string,VehicleCondition>()
  private conditions=new Map<string,VehicleStateChange[]>()
  private frame:Frame|null=null
  private previous:Frame|null=null
  private impacts:VehicleImpact[]=[]
  private legacyImpacts:AgentImpact[]=[]
  private plates:Texture[]=[]
  private atlas:Texture
  private busAtlas:Texture
  private busPlates:Texture[]=[]
  private stops:BusStop[]=[]
  private stopSigns=new Graphics()
  private doors=new Graphics()
  private ring=new Graphics()
  private tick=-1
  private active=new Set<string>()
  private selected:number|null=null
  constructor(_seed=42,private depthRoot?:Container,private metersPerUnit=24.25) {
    const canvas=document.createElement('canvas');canvas.width=256;canvas.height=512
    const ctx=canvas.getContext('2d')!;ctx.imageSmoothingEnabled=false
    for(let color=0;color<8;color++)for(let facing=0;facing<4;facing++) {
      ctx.save();ctx.translate(facing*64,color*64)
      const r=(x:number,y:number,w:number,h:number,c:string)=>{ctx.fillStyle=c;ctx.fillRect(x,y,w,h)}
      const paint=COLORS[color],dark=shade(paint,-30),light=shade(paint,28),ink='#273335'
      if(facing===1||facing===3) {
        if(facing===3){ctx.translate(64,0);ctx.scale(-1,1)}
        r(4,40,55,9,'#20332b48');r(8,38,10,10,ink);r(44,38,10,10,ink)
        r(10,40,6,5,'#758489');r(46,40,6,5,'#758489');r(3,25,58,15,ink);r(7,20,49,22,ink)
        r(10,16,31,8,ink);r(12,15,23,3,ink);r(6,27,52,11,dark);r(8,23,45,12,paint)
        r(12,18,24,7,light);r(11,25,31,11,light);r(12,27,29,7,'#35525b')
        r(14,27,10,6,'#789ba1');r(26,27,12,6,'#6b8c92');r(24,26,2,9,ink)
        r(42,25,11,4,light);r(9,35,44,2,paint);r(27,35,4,1,'#d0c6ab')
        r(56,28,3,5,'#e8dfb8');r(5,30,2,5,'#bf6950');r(2,36,3,4,'#939f9a');r(58,36,3,4,'#939f9a')
      } else {
        if(facing===0){ctx.translate(64,64);ctx.rotate(Math.PI)}
        r(14,8,37,51,'#20332b48');r(14,14,5,11,ink);r(45,14,5,11,ink);r(14,42,5,11,ink);r(45,42,5,11,ink)
        r(17,7,30,49,ink);r(21,4,22,55,ink);r(19,9,26,45,paint);r(23,6,18,50,light)
        r(21,14,22,28,dark);r(23,15,18,25,paint);r(21,14,22,8,'#304d58');r(23,15,18,5,'#789ba1')
        r(21,34,22,9,'#304d58');r(23,35,18,6,'#789ba1');r(23,23,18,10,light)
        r(19,22,2,13,dark);r(43,22,2,13,dark);r(15,30,3,4,ink);r(46,30,3,4,ink)
        r(20,48,6,4,'#efe2b8');r(39,48,6,4,'#efe2b8');r(20,8,5,3,'#b85a4b');r(40,8,5,3,'#b85a4b')
        r(23,54,18,2,'#a6b0a8');r(29,54,7,2,'#e6dfbf')
      }
      ctx.restore()
    }
    this.atlas=Texture.from(canvas);this.atlas.source.scaleMode='nearest'
    for(let color=0;color<8;color++)for(let facing=0;facing<4;facing++)this.plates.push(new Texture({source:this.atlas.source,frame:new Rectangle(facing*64,color*64,64,64)}))
    const busCanvas=document.createElement('canvas');paintBusPlates(busCanvas)
    this.busAtlas=Texture.from(busCanvas);this.busAtlas.source.scaleMode='nearest'
    for(let facing=0;facing<4;facing++)this.busPlates.push(new Texture({source:this.busAtlas.source,frame:new Rectangle(facing*128,0,128,128)}))
    this.root.addChild(this.stopSigns,this.doors)
    this.root.sortableChildren=true;this.ring.zIndex=100000;this.root.addChild(this.ring)
  }
  setFrame(frame:Frame,selectedResidentId:number|null=null) {
    const vehicles=frame.vehicles as Vehicle[]|undefined,adjacent=frame.tick===this.tick+1&&frame!==this.frame
    if(frame!==this.frame) {
      this.previous=adjacent?this.frame:null
      this.priorConditions=adjacent?new Map([...this.cars].map(([id,car])=>[id,car.data])):new Map()
      this.priorActivities=adjacent?new Map(this.activities.map(a=>[a.id,a])):new Map()
      this.motions.clear();this.transitions.clear();this.visibility.clear();this.conditions.clear()
      if(adjacent)for(const motion of (frame.vehicle_motion??[]) as Motion[]) {
        const old=this.cars.get(motion.id),end=vehicles?.find(v=>v.id===motion.id)
        if(old&&end&&motion.path.length>=2&&motion.path.length===motion.fractions.length&&motion.fractions[0]===0&&motion.fractions.at(-1)===1&&
          motion.path.every((p,i)=>p.every(Number.isFinite)&&Number.isFinite(motion.fractions[i])&&(!i||motion.fractions[i]>motion.fractions[i-1]))&&
          near(motion.path[0],[old.data.x,old.data.y])&&near(motion.path.at(-1)!,[end.x,end.y]))this.motions.set(motion.id,motion)
      }
      if(adjacent)for(const transition of frame.agent_activity_transitions??[]) {
        if(!Number.isFinite(transition.fraction)||transition.fraction<0||transition.fraction>1)continue
        const list=this.transitions.get(transition.id)??[];list.push(transition);this.transitions.set(transition.id,list)
      }
      for(const list of this.transitions.values())list.sort((a,b)=>(a.fraction??0)-(b.fraction??0))
      if(adjacent)for(const transition of (frame as Frame&{vehicle_visibility_transitions?:VehicleVisibility[]}).vehicle_visibility_transitions??[]) {
        if(!Number.isFinite(transition.fraction)||transition.fraction<0||transition.fraction>1||typeof transition.visible!=='boolean')continue
        const list=this.visibility.get(transition.id)??[];list.push(transition);this.visibility.set(transition.id,list)
      }
      for(const list of this.visibility.values())list.sort((a,b)=>a.fraction-b.fraction)
      if(adjacent)for(const change of (frame as Frame&{vehicle_state_transitions?:VehicleStateChange[]}).vehicle_state_transitions??[]){
        if(!Number.isFinite(change.fraction)||change.fraction<0||change.fraction>1)continue
        const list=this.conditions.get(change.id)??[];list.push(change);this.conditions.set(change.id,list)
      }
      for(const list of this.conditions.values())list.sort((a,b)=>a.fraction-b.fraction)
      this.tick=frame.tick
      this.frame=frame
    }
    this.impacts=(frame as Frame&{vehicle_impacts?:VehicleImpact[]}).vehicle_impacts??[]
    this.legacyImpacts=frame.agent_impacts??[]
    this.stops=frame.bus_stops??[]
    this.selected=selectedResidentId;this.activities=frame.agent_activities??[]
    const seen=new Set<string>()
    for(const data of vehicles??[]) {
      seen.add(data.id);let car=this.cars.get(data.id)
      if(!car){const sprite=new Sprite(this.plates[2]);sprite.anchor.set(.5,.5);sprite.scale.set(.85)
        const effects=new Graphics(),ground=new Graphics();effects.eventMode=ground.eventMode='none'
        car={sprite,effects,ground,data,x:data.x,y:data.y,direction:2,occupants:data.occupant_ids??[]};this.cars.set(data.id,car);(this.depthRoot??this.root).addChild(ground,sprite,effects)}
      car.data=data;car.sprite.visible=true
    }
    for(const [id,car] of this.cars)if(!seen.has(id))car.sprite.visible=car.effects.visible=car.ground.visible=false
    this.active=seen
  }
  draw(fraction:number,animationTime:number,_animate:boolean,night=0,reduced=false) {
    this.ring.clear();this.stopSigns.clear();this.doors.clear()
    const weather=this.frame?weatherAt(this.frame,this.previous,fraction):null
    const seconds=weather?.seconds??this.frame?.time??0
    const interval=this.frame?.interval_seconds??(this.previous?Math.max(0,(this.frame?.time??0)-this.previous.time):0)
    for(const stop of this.stops){const [sx,sy]=stop.position,x=Math.round(sx*CELL),y=Math.round(sy*CELL)
      this.stopSigns.rect(x-1,y-14,2,17).fill(0x64766b).rect(x-6,y-21,12,11).fill(0xe2d9bb).stroke({color:0x354e46,width:1})
      this.stopSigns.rect(x-4,y-18,8,4).fill(0x9f5148).rect(x-3,y-13,2,2).rect(x+2,y-13,2,2).fill(0x354e46)
      if(stop.waiting_count)pixelEllipse(this.stopSigns,x,y+4,8,3,0xdfba68,.45)
    }
    const occupants=new Map<string,number[]>(),transfers=new Set<string>()
    for(const final of this.activities) {
      let current=fraction<1?this.priorActivities.get(final.id)??final:final
      if(fraction<1)for(const transition of this.transitions.get(final.id)??[]){if((transition.fraction??0)<=fraction)current={...current,...transition};else break}
      if(riding(current)&&current.vehicle_id){const ids=occupants.get(current.vehicle_id)??[];ids.push(current.id);occupants.set(current.vehicle_id,ids)}
      if(current.vehicle_id&&['boarding','alighting'].includes(current.mode??''))transfers.add(current.vehicle_id)
    }
    for(const car of this.cars.values()) {
      if(!this.active.has(car.data.id))continue
      car.effects.clear();car.ground.clear()
      const condition=vehicleConditionAt(car.data,this.priorConditions.get(car.data.id),this.conditions.get(car.data.id)??[],fraction)
      // All cars in a parking facility share its transfer node, not a parking
      // stall. Stored empty inventory must not render as a stack of vehicles.
      const active=this.activities.length?occupants.get(car.data.id)??[]:car.data.occupant_ids??[]
      car.sprite.visible=car.data.type==='bus'?busVisibleAt(car.data.service_active!==false&&['driving','dwelling','yielding','boarding','alighting'].includes(car.data.state),this.visibility.get(car.data.id)??[],fraction):this.activities.length?active.length>0||transfers.has(car.data.id):active.length>0||['driving','boarding','alighting'].includes(car.data.state)
      car.effects.visible=car.ground.visible=car.sprite.visible
      if(!car.sprite.visible)continue
      let x=car.data.x,y=car.data.y,heading=condition.heading??car.data.heading??Math.PI/2,moving=false,speed=Number(condition.speed_mps??0)
      const movement=fraction<1?vehicleMotionAt(this.motions.get(car.data.id),fraction,interval,this.metersPerUnit):null
      if(movement){[x,y]=movement.point;moving=movement.moving;speed=movement.speed;if(movement.heading!==null)heading=movement.heading}
      const hx=Math.cos(heading),hy=Math.sin(heading);car.direction=Math.abs(hx)>Math.abs(hy)?hx>0?1:3:hy>0?2:0
      const offset=Number(car.data.lane_offset_m??0)/this.metersPerUnit
      // Geographic routing uses road centerlines; sprites occupy their right lane.
      x-=Math.sin(heading)*offset;y+=Math.cos(heading)*offset
      car.x=x;car.y=y;car.occupants=this.activities.length?occupants.get(car.data.id)??[]:car.data.occupant_ids??[]
      const color=typeof car.data.color==='number'?Math.abs(Math.trunc(car.data.color))%8:Math.max(0,COLORS.indexOf(car.data.color))
      const bus=car.data.type==='bus'
      car.sprite.texture=bus?this.busPlates[car.direction]:this.plates[color*4+car.direction];car.sprite.scale.set(bus?.70:.85)
      if(bus&&!moving&&(condition.state==='dwelling'||transfers.has(car.data.id))){const bx=x*CELL,by=y*CELL
        const dx=[-9,23,9,-29][car.direction],dy=[-22,6,14,6][car.direction]
        this.doors.rect(Math.round(bx+dx),Math.round(by+dy),6,9).fill(0xf1d995).rect(Math.round(bx+dx),Math.round(by+dy+8),8,2).fill(0xadb39a)
      }
      car.sprite.position.set(Math.round(x*CELL),Math.round(y*CELL));car.sprite.zIndex=y*CELL+17
      car.sprite.tint=night>.15?0xcdd8d2:0xffffff
      const impact=vehicleImpactAt(this.impacts,this.legacyImpacts,car.data.id,car.occupants,seconds)
      const pose=vehicleWeatherPose(weather,condition,speed,moving,seconds,animationTime,reduced,night,impact)
      car.sprite.rotation=pose.rotation
      car.effects.position.copyFrom(car.sprite.position);car.effects.rotation=pose.rotation;car.effects.scale.set(bus?.70:.85);car.effects.zIndex=car.sprite.zIndex+.01
      car.ground.position.copyFrom(car.sprite.position);car.ground.zIndex=car.sprite.zIndex-.01
      this.drawWeatherDetails(car,pose,bus)
      if(pose.snowTracks&&movement){
        // Only the traversed part of this recorded segment receives tire marks.
        // They cannot extend across a corner or invent a route behind a car.
        const length=Math.min(bus?38:25,movement.traversed*CELL),rear=bus?33:21
        if(length>rear)for(const side of [-1,1]){
          const ox=-hy*side*(bus?10:8),oy=hx*side*(bus?10:8)
          pixelLine(car.ground,ox-hx*rear,oy-hy*rear,ox-hx*length,oy-hy*length,0x82918d,.45,2)
        }
      }
      if(pose.spray){
        const phase=reduced?.5:(animationTime*3+car.direction)%1
        for(const side of [-1,1])car.ground.rect(Math.round(-hx*20-hy*side*(10+phase*4)),Math.round(-hy*20+hx*side*(10+phase*4)),3,2).fill({color:0xd6e1dc,alpha:(1-phase)*.45})
      }
      if(pose.dust>0)for(let k=0;k<5;k++){
        const phase=1-pose.dust,a=k*Math.PI*.4,r=13+phase*16
        car.ground.rect(Math.round(Math.cos(a)*r),Math.round(Math.sin(a)*r*.5+11),3,2).fill({color:k%2?0xcabf96:0x8f947c,alpha:pose.dust*.65})
      }
      if(this.selected!=null&&car.occupants.includes(this.selected))pixelEllipse(this.ring,x*CELL,y*CELL+12,32,17,0xf4e7ad,1,2,2)
    }
  }
  private drawWeatherDetails(car:Car,pose:ReturnType<typeof vehicleWeatherPose>,bus:boolean){
    const g=car.effects,size=bus?128:64,half=size/2,side=car.direction===1||car.direction===3
    const point=(x:number,y:number):Point=>car.direction===3?[size-x-half,y-half]:car.direction===0?[size-x-half,size-y-half]:[x-half,y-half]
    const r=(x:number,y:number,w:number,h:number,color:number,alpha=1)=>{
      if(car.direction===3)x=size-x-w
      if(car.direction===0){x=size-x-w;y=size-y-h}
      g.rect(x-half,y-half,w,h).fill({color,alpha})
    }
    const lamp=(x:number,y:number,w:number,h:number,front:boolean)=>{
      if(pose.hazardLights){r(x-1,y-1,w+2,h+2,0xe2b166,.28);r(x,y,w,h,0xffd685)}
      else if(front&&pose.headlights){r(x-1,y-1,w+2,h+2,0xece2ac,.2);r(x,y,w,h,0xfff0c8)}
      else if(!front&&pose.braking){r(x-2,y-1,w+4,h+2,0xc66548,.22);r(x,y,w,h,0xf3875a)}
    }
    if(side){
      if(bus){lamp(114,64,3,5,true);lamp(10,65,3,5,false)}
      else {lamp(56,28,3,5,true);lamp(5,30,2,5,false)}
    }else if(bus){lamp(50,111,6,4,true);lamp(71,111,6,4,true);lamp(50,12,5,3,false);lamp(72,12,5,3,false)}
    else {lamp(20,48,6,4,true);lamp(39,48,6,4,true);lamp(20,8,5,3,false);lamp(40,8,5,3,false)}
    if(pose.snowCover>.02){
      const alpha=Math.min(.85,pose.snowCover)
      if(side)bus?r(17,39,76,2,0xe5eade,alpha):r(12,16,23,2,0xe5eade,alpha)
      else bus?r(54,49,19,3,0xe5eade,alpha):r(24,24,16,3,0xe5eade,alpha)
    }
    if(pose.wipers){
      const a=side?(bus?[109,63]:[35,33]):bus?[64,100]:[32,41]
      const b=side?(bus?[102+pose.wiperPhase*9,52]:[31+pose.wiperPhase*7,27]):bus?[54+pose.wiperPhase*20,92]:[26+pose.wiperPhase*12,35]
      const from=point(a[0],a[1]),to=point(Math.round(b[0]),b[1])
      pixelLine(g,...from,...to,0xd5ded0,.9,1)
    }
  }
  positionForResident(id:number):Point|undefined {const car=[...this.cars.values()].find(c=>c.sprite.visible&&c.occupants.includes(id));return car?[car.x,car.y]:undefined}
  pick(x:number,y:number,worldRadius:number):number[] {return[...this.cars.values()].filter(c=>c.sprite.visible&&Math.hypot(c.x*CELL-x,c.y*CELL-y)<worldRadius+15).sort((a,b)=>Math.hypot(a.x*CELL-x,a.y*CELL-y)-Math.hypot(b.x*CELL-x,b.y*CELL-y)).flatMap(c=>c.occupants)}
  destroy(){for(const texture of this.busPlates)texture.destroy(false);this.busAtlas.destroy(true);for(const texture of this.plates)texture.destroy(false);this.atlas.destroy(true)}
}
