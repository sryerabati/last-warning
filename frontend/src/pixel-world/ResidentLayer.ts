import {Container,Graphics,Sprite} from 'pixi.js'
import type {AgentImpact,City,Frame,Point} from '../types'
import {impactAt,impactPose} from './ImpactPresentation'
import {activityDuring,endpointFacing,residentSegment,residentWeatherPose,type ResidentActivityState} from './ResidentWeatherPresentation'
import {weatherAt} from './WeatherPresentation'
import {pixelEllipse} from './PixelEffectsGeometry'
import {CELL,hash,type TownArt} from './Art'
import {bounds,type TownActivity,type TownPlace} from './TownLifeTypes'
import {CharacterFactory,characterAppearance,CHARACTER_FOOT,CHARACTER_HEIGHT,type CharacterAppearance} from './CharacterFactory'

interface Motion {id:number;path:Point[];fractions:number[]}
interface Activity extends TownActivity {mode?:string;vehicle_id?:string|null;group_id?:string|null;walked_m?:number}
interface Transition extends Partial<Activity> {id:number;fraction:number}
type MotionFrame=Frame&{agent_motion?:Motion[];agent_activity_transitions?:Transition[]}
interface Person {sprite:Sprite;id:number;direction:number;x:number;y:number;renderX:number;renderY:number;row:number[];appearance:CharacterAppearance}
interface Profile {id:number;appearance?:Partial<CharacterAppearance>}
const riding=(activity?:Partial<Activity>)=>activity?.mode==='riding'||activity?.mode==='driving'
const distance=(a:Point,b:Point)=>Math.hypot(a[0]-b[0],a[1]-b[1])
const matches=(a:Point,b:Point)=>distance(a,b)<.00001
const isPortal=(place?:TownPlace)=>!!(place as TownPlace&{is_portal?:boolean}|undefined)?.is_portal

function contains(polygon:Point[],x:number,y:number) {
  let inside=false
  for(let i=0,j=polygon.length-1;i<polygon.length;j=i++) {const a=polygon[i],b=polygon[j]
    if((a[1]>y)!==(b[1]>y)&&x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0])inside=!inside}
  return inside
}

export class ResidentLayer {
  readonly root=new Container()
  private people=new Map<number,Person>()
  private active=new Set<number>()
  private profiles=new Map<number,Profile>()
  private motions=new Map<number,Motion>()
  private endpointDirections=new Map<number,number>()
  private transitions=new Map<number,Transition[]>()
  private tick=-1
  private selected:number|null=null
  private ring=new Graphics()
  private action=new Graphics()
  private overview=new Graphics()
  private impacts=new Map<number,AgentImpact[]>()
  private frameTime=0
  private intervalSeconds=0
  private contact=new Graphics()
  private decisions=new Map<number,string>()
  private activities=new Map<number,Activity>()
  private previousActivities=new Map<number,Activity>()
  private displayActivities=new Map<number,Partial<Activity>>()
  private frame:Frame|null=null
  private previousFrame:Frame|null=null
  private metresPerUnit:number
  private reactions=new Map<number,string>()
  private places:TownPlace[]
  private organic:boolean
  private campus:boolean
  private characters:CharacterFactory|null
  private offset:number
  constructor(private art:TownArt,private seed:number,city:City,profiles:Profile[]=[],private depthRoot?:Container) {
    this.metresPerUnit=city.meters_per_unit??24.25
    this.places=city.places??[];this.organic=city.layout==='organic';this.campus=(city.layout as string)==='campus'
    this.offset=this.campus?0:.5
    this.characters=this.campus?new CharacterFactory():null
    this.setProfiles(profiles)
    this.root.sortableChildren=true
    this.overview.zIndex=99999;this.ring.zIndex=100000;this.action.zIndex=100001
    this.contact.zIndex=99998;this.root.addChild(this.contact,this.overview,this.ring,this.action)
  }
  setProfiles(profiles:Profile[]) {this.profiles=new Map(profiles.map(p=>[p.id,p]));for(const p of this.people.values())p.appearance=characterAppearance(p.id,this.seed,this.profiles.get(p.id)?.appearance)}
  setFrame(frame:Frame,selected:number|null) {
    const adjacent=frame.tick===this.tick+1,arrivals=new Map(frame.agents.map(a=>[a[0],a]))
    if(frame!==this.frame) {
      this.previousActivities=adjacent?this.activities:new Map()
      this.previousFrame=adjacent?this.frame:null
      this.intervalSeconds=frame.interval_seconds??(adjacent?Math.max(0,frame.time-this.frameTime):frame.tick>0?frame.time/frame.tick:0)
      this.frameTime=frame.time
      this.motions.clear();this.transitions.clear()
      this.endpointDirections.clear()
      for(const motion of (frame as MotionFrame).agent_motion??[]){const direction=endpointFacing(motion.path);if(direction!==undefined)this.endpointDirections.set(motion.id,direction)}
      if(adjacent)for(const motion of (frame as MotionFrame).agent_motion??[]) {
        const old=this.people.get(motion.id),arriving=arrivals.get(motion.id)
        // Campus paths are authoritative continuous edge progress; legacy
        // recordings retain the strict cardinal-cell validation.
        const valid=motion.path.length>=2&&motion.path.length===motion.fractions.length&&
          motion.fractions[0]===0&&motion.fractions.at(-1)===1&&
          motion.path.every((p,i)=>p.length===2&&p.every(Number.isFinite)&&(!i||
            (motion.fractions[i]>motion.fractions[i-1]&&(this.campus||Math.abs(p[0]-motion.path[i-1][0])+Math.abs(p[1]-motion.path[i-1][1])===1))))&&
          old&&matches(motion.path[0],[old.row[1],old.row[2]])&&arriving&&matches(motion.path.at(-1)!,[arriving[1],arriving[2]])
        if(valid)this.motions.set(motion.id,motion)
      }
      if(adjacent)for(const transition of (frame as MotionFrame).agent_activity_transitions??[]) {
        if(!Number.isFinite(transition.fraction)||transition.fraction<0||transition.fraction>1)continue
        const list=this.transitions.get(transition.id)??[];list.push(transition);this.transitions.set(transition.id,list)
      }
      for(const list of this.transitions.values())list.sort((a,b)=>a.fraction-b.fraction)
      this.tick=frame.tick
      this.frame=frame
    }
    this.selected=selected
    this.impacts.clear()
    for(const impact of frame.agent_impacts??[]){const rows=this.impacts.get(impact.id)??[];rows.push(impact);this.impacts.set(impact.id,rows)}
    this.decisions=new Map((frame.agent_decisions??[]).map(d=>[d.id,d.action]))
    this.activities=new Map((frame.agent_activities??[]).map(a=>[a.id,a]))
    const seen=new Set<number>()
    for(const row of frame.agents) {
      const id=row[0];seen.add(id)
      let p=this.people.get(id)
      if(!p) {
        const appearance=characterAppearance(id,this.seed,this.profiles.get(id)?.appearance)
        const sprite=new Sprite(this.art.texture('person-'+hash(id,this.seed)%12+'-2-0'))
        sprite.anchor.set(.5,this.campus?CHARACTER_FOOT/CHARACTER_HEIGHT:.9)
        if(this.organic)sprite.scale.set(1.35)
        p={sprite,id,direction:2,x:row[1],y:row[2],renderX:row[1]+this.offset,renderY:row[2]+this.offset,row,appearance}
        ;(this.depthRoot??this.root).addChild(sprite);this.people.set(id,p)
      }
      p.row=row;p.sprite.visible=true
    }
    for(const [id,p] of this.people)if(!seen.has(id))p.sprite.visible=false
    this.active=seen
  }
  private activityAt(id:number,fraction:number):Partial<Activity>|undefined {
    return activityDuring(this.activities.get(id),this.previousActivities.get(id),this.transitions.get(id)??[],fraction)
  }
  private recordedPosition(p:Person,fraction:number):Point {
    const motion=this.motions.get(p.id)
    if(!motion||fraction>=1)return[p.row[1],p.row[2]]
    let i=1;while(i<motion.fractions.length-1&&motion.fractions[i]<=fraction)i++
    const a=motion.path[i-1],b=motion.path[i],f=Math.max(0,Math.min(1,(fraction-motion.fractions[i-1])/(motion.fractions[i]-motion.fractions[i-1])))
    return[a[0]+(b[0]-a[0])*f,a[1]+(b[1]-a[1])*f]
  }
  /** Preserve a compact trail perpendicular to each recorded group route.
   * Only overlapping members receive at most 14 display pixels of separation;
   * recorded coordinates, routes, timing and hazard calculations stay intact. */
  private groupOffsets(fraction:number) {
    const offsets=new Map<number,Point>(),groups=new Map<string,{id:number;point:Point}[]>()
    if(!this.campus)return offsets
    for(const p of this.people.values()) {
      if(!this.active.has(p.id))continue
      const a=this.activityAt(p.id,fraction)
      if(!a?.group_id||a.inside||riding(a))continue
      const members=groups.get(a.group_id)??[];members.push({id:p.id,point:this.recordedPosition(p,fraction)});groups.set(a.group_id,members)
    }
    for(const members of groups.values()) {
      const pending=new Set(members.map(m=>m.id))
      for(const member of members) {
        if(!pending.has(member.id))continue
        const nearby=members.filter(m=>pending.has(m.id)&&distance(member.point,m.point)*CELL<28).sort((a,b)=>a.id-b.id)
        for(const m of nearby)pending.delete(m.id)
        if(nearby.length<2)continue
        const motion=this.motions.get(member.id)
        let dx=0,dy=1
        if(motion){let i=1;while(i<motion.fractions.length-1&&motion.fractions[i]<=fraction)i++;const a=motion.path[i-1],b=motion.path[i],d=distance(a,b);if(d>.00001){dx=(b[0]-a[0])/d;dy=(b[1]-a[1])/d}}
        const gap=Math.min(20,28/(nearby.length-1))
        nearby.forEach((m,i)=>{const lateral=(i-(nearby.length-1)/2)*gap,trail=this.people.get(m.id)?.appearance.age==='child'?-7:(i%2)*3
          offsets.set(m.id,[-dy*lateral+dx*trail,dx*lateral+dy*trail])})
      }
    }
    return offsets
  }
  draw(fraction:number,time:number,animate:boolean,night=0,scale=1) {
    this.ring.clear();this.action.clear();this.overview.clear();this.contact.clear();this.displayActivities.clear();this.reactions.clear()
    const replaySeconds=this.frameTime-this.intervalSeconds*(1-fraction)
    const weather=this.frame?weatherAt(this.frame,this.previousFrame,fraction):null
    const offsets=this.groupOffsets(fraction)
    for(const p of this.people.values()) {
      if(!this.active.has(p.id))continue
      const row=p.row,motion=this.motions.get(p.id)
      const activity=this.activityAt(p.id,fraction)
      if(activity)this.displayActivities.set(p.id,activity)
      let x=row[1],y=row[2],moving=false
      if(motion&&fraction<1) {
        let i=1
        while(i<motion.fractions.length-1&&motion.fractions[i]<=fraction)i++
        const from=motion.path[i-1],to=motion.path[i]
        const f=Math.max(0,Math.min(1,(fraction-motion.fractions[i-1])/(motion.fractions[i]-motion.fractions[i-1])))
        x=from[0]+(to[0]-from[0])*f;y=from[1]+(to[1]-from[1])*f;moving=distance(from,to)>.00001
        if(moving){const dx=to[0]-from[0],dy=to[1]-from[1];p.direction=Math.abs(dx)>Math.abs(dy)?dx>0?1:3:dy>0?2:0}
      }
      if(!moving&&activity?.partner_ids?.length){
        const partner=this.people.get(activity.partner_ids[0])
        if(partner){const [px,py]=this.recordedPosition(partner,fraction),dx=px-x,dy=py-y;if(Math.hypot(dx,dy)>.001)p.direction=Math.abs(dx)>Math.abs(dy)?dx>0?1:3:dy>0?2:0}
      }
      if(fraction>=1&&!activity?.partner_ids?.length&&this.endpointDirections.has(p.id))p.direction=this.endpointDirections.get(p.id)!
      p.x=x;p.y=y
      const hidden=this.campus?!!activity?.inside||riding(activity):!!activity?.inside&&!moving,compact=this.campus&&scale<.5
      p.sprite.visible=!hidden&&!compact
      const offset=offsets.get(p.id)??[0,0],px=(x+this.offset)*CELL+offset[0],py=(y+this.offset)*CELL+offset[1]
      p.renderX=px/CELL;p.renderY=py/CELL
      p.sprite.position.set(Math.round(px),Math.round(py));p.sprite.zIndex=py+p.id*.00001
      const impact=impactAt(this.impacts.get(p.id)??[],replaySeconds)
      const segment=residentSegment(motion,fraction,this.intervalSeconds,this.metresPerUnit)
      const recordedSpeed=typeof activity?.speed_mps==='number'?activity.speed_mps:0
      // Direct seeks can use an explicitly recorded endpoint gait. Adjacent
      // playback always uses its current physical segment, including stops.
      if(fraction>=1)moving=activity?.mode==='walking'&&(typeof activity.speed_mps==='number'?recordedSpeed>.015:segment.moving)
      else if(motion)moving=segment.moving
      const phase=hash(p.id,this.seed)%113/113
      const reaction=residentWeatherPose({activity:activity as ResidentActivityState|undefined,appearance:p.appearance,moving,
        speed:motion?segment.speed:recordedSpeed,weather,impact,time,phase,direction:p.direction})
      if(!hidden)this.reactions.set(p.id,reaction.response)
      if(this.characters) {
        // Children have their own native-pixel proportions in the atlas. A second
        // fractional sprite scale made their faces and hands shimmer while moving.
        p.sprite.scale.set(1)
        if(p.sprite.visible){
          // World time runs up to 24× at normal playback. Limit the visible gait
          // to ten poses per second instead of aliasing 100+ distance poses/sec.
          const gesture=!moving&&activity?.partner_ids?.length&&(time+phase*4)%4<.65
          const pose=gesture&&reaction.style==='walk'?7:reaction.pose
          const texture=this.characters.texture(p.appearance,p.direction,pose,reaction.style)
          if(p.sprite.texture!==texture)p.sprite.texture=texture
        }
        if(compact&&!hidden){const radius=Math.max(3,3.2/scale);this.overview.rect(px-radius/2,py-radius,radius,radius).fill(p.id===this.selected?0xffdf8a:0xe9d9b5)}
      } else {
        const pose=moving&&animate?Math.floor(time*5+p.id%3)%4:0
        const texture=this.art.texture('person-'+hash(p.id,this.seed)%12+'-'+p.direction+'-'+pose)
        if(p.sprite.texture!==texture)p.sprite.texture=texture
      }
      p.sprite.rotation=reaction.lean
      if(reaction.moving&&!hidden&&!compact&&reaction.style==='careful'&&weather?.kind==='blizzard'){
        const foot=1+Math.floor(time*4+phase*6)%2
        this.contact.rect(Math.round(px+(foot===1?-7:5)),Math.round(py),3,2).fill({color:0x526c71,alpha:.5})
        this.contact.rect(Math.round(px+(foot===1?6:-9)),Math.round(py+1),5,2).fill({color:0xe9efe6,alpha:.7})
      }
      if(impact&&!hidden&&(impact.hazard==='tornado'||impact.kind==='knockdown')){
        const pose=impactPose(impact,replaySeconds,p.appearance.mobility==='wheelchair')
        p.sprite.rotation=pose.rotation;p.sprite.scale.set(1,pose.scaleY);p.sprite.y+=pose.offsetY
        pixelEllipse(this.contact,px,py+1,18,7,0x4d4939,.2*pose.amount)
        pixelEllipse(this.contact,px,py+1,22,10,0xdab676,.7*pose.amount,2,2)
        // Six deterministic dust chips; no screen shake, flashes or invented displacement.
        if(pose.dust>0)for(let k=0;k<6;k++){
          const phase=1-pose.dust,a=k*Math.PI/3+impact.id,r=8+phase*20
          this.contact.rect(Math.round(px+Math.cos(a)*r),Math.round(py+Math.sin(a)*r*.38-phase*8),3,2).fill({color:k%2?0xc8bd92:0x948c6d,alpha:pose.dust*.7})
        }
        if(compact){
          const u=1/scale
          this.overview.poly([px,py-10*u,px+5*u,py-5*u,px,py,px-5*u,py-5*u]).fill(0xe3af64).stroke({color:0x483b32,width:u})
          this.overview.rect(px-u,py-8*u,2*u,3*u).rect(px-u,py-4*u,2*u,u).fill(0x483b32)
        }
      }
      p.sprite.alpha=row[3]===5?.92:1
      p.sprite.tint=night>.15?0xcdd8d2:0xffffff
      if(p.id===this.selected&&!riding(activity)&&!isPortal(activity?.inside?this.places.find(place=>place.id===activity.place_id):undefined)) {
        const child=this.campus&&p.appearance.age==='child'
        pixelEllipse(this.ring,px,py-1,this.campus?(child?14:18):13,this.campus?(child?6:8):7,0xf4e7ad,1,2,2)
        const top=this.campus?(child?38:49):29
        this.ring.poly([px-4,py-top,px+4,py-top,px,py-top+5]).fill(0xf4e7ad)
        const action=this.decisions.get(p.id)
        if(activity?.inside) {
          this.action.poly([px-7,py-29,px,py-35,px+7,py-29]).fill(0xf4e7ad)
          this.action.rect(px-5,py-29,10,9).fill(0xf4e7ad).rect(px-1,py-25,3,5).fill(0x273d40)
        } else if(action==='SHARE'&&!this.campus) {
          this.action.rect(px+10,py-24,12,9).fill(0xe8dfbb).stroke({color:0x273d40,width:1})
          this.action.poly([px+11,py-16,px+11,py-12,px+15,py-16]).fill(0xe8dfbb)
        } else if(action==='PREPARE')this.action.rect(px+11,py-21,6,7).fill(0xdcbd70).stroke({color:0x273d40,width:1})
      }
    }
    this.characters?.flush()
  }
  position(id:number):Point|undefined {const p=this.people.get(id),a=this.displayActivities.get(id);return p&&this.active.has(id)&&!(a?.inside&&isPortal(this.places.find(place=>place.id===a.place_id)))?[p.renderX,p.renderY]:undefined}
  visiblePosition(id:number):Point|undefined {const a=this.displayActivities.get(id);return a?.inside||riding(a)?undefined:this.position(id)}
  pick(x:number,y:number,worldRadius:number):number[] {
    const hitDistance=(p:Person)=>{const px=p.renderX*CELL,py=p.renderY*CELL,height=this.campus?(p.appearance.age==='child'?32:43):22
      return Math.hypot(Math.max(0,Math.abs(px-x)-(this.campus?10:6)),y-Math.max(py-height,Math.min(py+2,y)))}
    return [...this.people.values()].filter(p=>this.active.has(p.id)&&!this.displayActivities.get(p.id)?.inside&&!riding(this.displayActivities.get(p.id))&&hitDistance(p)<worldRadius)
      .sort((a,b)=>hitDistance(a)-hitDistance(b)||Math.hypot(a.renderX*CELL-x,a.renderY*CELL-y)-Math.hypot(b.renderX*CELL-x,b.renderY*CELL-y)||a.id-b.id).map(p=>p.id)
  }
  occupiedPlaces():{place:TownPlace;ids:number[]}[] {
    const groups=new Map<string,number[]>(),current=this.displayActivities.size?this.displayActivities:this.activities
    for(const [id,a] of current)if(a.inside&&a.place_id&&this.people.has(id)) {
      const ids=groups.get(a.place_id)??[];ids.push(id);groups.set(a.place_id,ids)
    }
    return this.places.filter(p=>groups.has(p.id)&&!isPortal(p)).map(place=>({place,ids:groups.get(place.id)!.sort((a,b)=>a-b)}))
  }
  buildingAt(x:number,y:number) {
    if(this.campus)return this.occupiedPlaces().find(({place})=>contains(place.footprint,x/CELL,y/CELL))
    const cellX=Math.floor(x/CELL),cellY=Math.floor(y/CELL)
    return this.occupiedPlaces().find(({place})=>place.footprint.some(([px,py])=>px===cellX&&py===cellY))
  }
  selectedBuilding() {
    if(this.selected==null)return null
    const activity=this.displayActivities.get(this.selected)??this.activities.get(this.selected)
    return activity?.inside?this.places.find(p=>p.id===activity.place_id&&!isPortal(p))??null:null
  }
  drawOccupancy(graphics:Graphics,night:number,scale:number) {
    for(const {place,ids} of this.occupiedPlaces()) {
      const legacy=bounds(place),b=this.campus?{...legacy,w:Math.max(.1,legacy.w-1),h:Math.max(.1,legacy.h-1)}:legacy
      const px=(b.x+b.w/2)*CELL,py=(b.y+b.h*.72)*CELL,selected=ids.includes(this.selected??-1)
      if(selected)graphics.rect(b.x*CELL+2,b.y*CELL+2,Math.max(4,b.w*CELL-4),Math.max(4,b.h*CELL-4)).stroke({color:0xdcbd70,width:1.5/scale,alpha:.8})
      const count=Math.min(3,ids.length)
      for(let i=0;i<count;i++) {const x=px+(i-(count-1)/2)*10
        if(night>.1){graphics.rect(x-7,py-6,14,12).fill({color:0xdcbd70,alpha:night*.1});graphics.rect(x-5,py-4,10,8).fill({color:0xdcbd70,alpha:night*.17})}
        graphics.rect(x-3,py-2,6,4).fill({color:selected?0xffe2a0:0xe3c77e,alpha:.55+night*.4})
      }
    }
  }
  diagnostics(){return {...(this.characters?.diagnostics()??{recipes:12,pages:1,frameSize:[12,20],poses:4,facings:4}),weatherReactions:Object.fromEntries([...new Set(this.reactions.values())].map(key=>[key,[...this.reactions.values()].filter(value=>value===key).length]))}}
  destroy(){this.characters?.destroy()}
}
