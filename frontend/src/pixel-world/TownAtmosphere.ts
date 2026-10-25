import {Graphics} from 'pixi.js'
import type {City,Frame} from '../types'
import {CELL,hash} from './Art'
import type {ResidentLayer} from './ResidentLayer'

export class TownAtmosphere {
  readonly shade=new Graphics()
  readonly lights=new Graphics()
  readonly interactions=new Graphics()
  private frame:Frame|null=null
  private priorMinutes:number|null=null
  private lamps:{x:number;y:number}[]
  night=0
  constructor(private city:City) {
    this.lamps=(city.road_styles??[]).filter(s=>s.kind==='road'&&hash(...s.position)%9===0)
      .map(({position:[x,y]})=>({x:x*CELL+52,y:y*CELL+3}))
    if(city.layout==='campus')this.lamps=(city.places??[]).filter(p=>p.kind!=='park'&&!(p as typeof p&{is_portal?:boolean}).is_portal).map(p=>({x:p.entrance[0]*CELL,y:p.entrance[1]*CELL-10}))
  }
  setFrame(frame:Frame) {
    if(frame!==this.frame) {
      this.priorMinutes=this.frame&&frame.tick===this.frame.tick+1?this.frame.world_clock_minutes??null:null
      this.frame=frame
    }
  }
  draw(fraction:number,time:number,animate:boolean,people:ResidentLayer,selected:number|null,scale:number) {
    this.shade.clear();this.lights.clear();this.interactions.clear()
    const frame=this.frame
    if(!frame||frame.world_clock_minutes==null) {this.night=0;return}
    let minutes=frame.world_clock_minutes
    if(this.priorMinutes!=null) {
      const delta=(minutes-this.priorMinutes+1440)%1440
      if(delta<30)minutes=this.priorMinutes+delta*fraction
    }
    minutes=(minutes%1440+1440)%1440
    const sun=Math.sin((minutes/1440-.25)*Math.PI*2)
    this.night=1-Math.max(0,Math.min(1,(sun+.15)/.75))
    const size=this.city.size*CELL
    if(this.night>0)this.shade.rect(0,0,size,size).fill({color:0x122b48,alpha:this.night*.50})
    const dusk=Math.max(0,1-Math.abs(minutes-1080)/95)*.11
    if(dusk>0)this.shade.rect(0,0,size,size).fill({color:0xb97840,alpha:dusk})
    people.drawOccupancy(this.lights,this.night,scale)
    if(this.night>.1)for(const p of this.lamps) {
      this.lights.rect(p.x-13,p.y-11,26,22).fill({color:0xdcbd70,alpha:this.night*.06})
      this.lights.rect(p.x-7,p.y-6,14,12).fill({color:0xe8ca84,alpha:this.night*.1})
      this.lights.rect(p.x-2,p.y-2,4,4).fill({color:0xf5d99a,alpha:this.night*.9})
    }
    const events=(frame.interactions??[]).filter(event=>event.tick<=frame.tick&&event.expires_tick>=frame.tick)
      .filter(event=>event.agent_ids.some(id=>people.visiblePosition(id)))
      .sort((a,b)=>Number(b.agent_ids.includes(selected??-1))-Number(a.agent_ids.includes(selected??-1))||a.id.localeCompare(b.id)).slice(0,12)
    for(const event of events) {
      const selectedEvent=event.agent_ids.includes(selected??-1)
      if(this.city.layout==='campus'&&!selectedEvent&&(scale<.5||(time+event.agent_ids[0]*.71)%6>2))continue
      const positions=event.agent_ids.map(id=>people.visiblePosition(id)).filter((p):p is [number,number]=>!!p)
      const [x,y]=positions.length?positions.reduce(([x,y],[px,py])=>[x+px/positions.length,y+py/positions.length],[0,0]):event.position
      const px=x*CELL,py=y*CELL-(this.city.layout==='campus'?49:29)+(animate?Math.floor(Math.sin(time*2+event.agent_ids[0])*.9):0)
      const g=this.interactions
      if(event.kind==='warning_shared') {
        g.rect(px-7,py-7,14,11).fill(0xe8ce89).stroke({color:0x273d40,width:1})
        g.rect(px-1,py-5,2,5).rect(px-1,py+1,2,1).fill(0x7f5a43)
      } else {
        g.rect(px-8,py-7,16,10).fill(0xe8dfbb).stroke({color:0x324e43,width:1})
        g.poly([px-5,py+3,px-5,py+6,px-1,py+3]).fill(0xe8dfbb)
        g.rect(px-5,py-3,2,2).rect(px-1,py-3,2,2).rect(px+3,py-3,2,2).fill(0x57735c)
      }
    }
  }
}
