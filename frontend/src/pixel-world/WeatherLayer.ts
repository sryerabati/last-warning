import {Container,Graphics} from 'pixi.js'
import type {City,Frame,Point} from '../types'
import {CELL,hash} from './Art'
import {weatherAt,LightningCue,type WeatherState} from './WeatherPresentation'
import {pixelEllipse,pixelLine} from './PixelEffectsGeometry'

export interface WeatherViewport {x:number;y:number;width:number;height:number;worldX:number;worldY:number;scale:number}
const mod=(n:number,m:number)=>((n%m)+m)%m
const pixel=(n:number)=>Math.round(n/2)*2

/** Screen-density precipitation keeps weather legible at every camera scale.
 * Surface ripples use mapped roads; sky effects never change hazard outcomes. */
export class WeatherLayer {
  readonly screen=new Container()
  readonly ground=new Graphics()
  private sky=new Graphics()
  private particles=new Graphics()
  private lightning=new Graphics()
  private frame:Frame|null=null
  private previous:Frame|null=null
  private cue=new LightningCue()
  private puddles:Point[]=[]
  private sample:WeatherState|null=null
  constructor(city:City){
    this.screen.eventMode='none';this.ground.eventMode='none'
    this.screen.addChild(this.sky,this.particles,this.lightning)
    if(city.campus_geometry){
      for(const road of city.campus_geometry.roads){
        if(road.geometry.type!=='LineString')continue
        const points=road.geometry.coordinates as Point[]
        for(let i=1;i<points.length;i++){
          const a=points[i-1],b=points[i],distance=Math.hypot(b[0]-a[0],b[1]-a[1])*CELL
          for(let k=0;k<Math.min(12,Math.floor(distance/90));k++){
            const t=(k+.5)/Math.max(1,Math.floor(distance/90))
            this.puddles.push([(a[0]+(b[0]-a[0])*t)*CELL,(a[1]+(b[1]-a[1])*t)*CELL])
          }
        }
      }
    }else this.puddles=city.roads.filter((_,i)=>i%3===0).map(([x,y])=>[(x+.5)*CELL,(y+.5)*CELL])
  }
  setFrame(frame:Frame,playing=false){
    if(frame===this.frame)return
    this.previous=this.frame&&frame.tick===this.frame.tick+1?this.frame:null
    if(!this.previous||!playing)this.cue.reset(typeof frame.hazard?.last_thunder_seconds==='number'?frame.hazard.last_thunder_seconds:-1)
    this.frame=frame
  }
  state(fraction:number){return this.frame?weatherAt(this.frame,this.previous,fraction):null}
  draw(time:number,fraction:number,animate:boolean,reduced:boolean,view:WeatherViewport){
    this.sky.clear();this.particles.clear();this.lightning.clear();this.ground.clear()
    if(!this.frame)return
    const state=this.sample=this.state(fraction)!,{width:w,height:h,scale,worldX,worldY}=view
    this.screen.position.set(view.x,view.y)
    if(!state.kind||!['thunderstorm','hailstorm','blizzard','tornado','wildfire','flood'].includes(state.kind))return
    const snow=state.kind==='blizzard',storm=state.kind==='thunderstorm'||state.kind==='hailstorm'
    const tornado=state.kind==='tornado',fire=state.kind==='wildfire'
    const windLength=Math.hypot(...state.direction)||1,wx=state.direction[0]/windLength,wy=state.direction[1]/windLength
    // Clouds and low visibility have a calm base exposure, never a strobing filter.
    const tint=snow?0xdbe6e8:fire?0x745243:0x233843
    const shade=snow?(state.active?.11:.025):storm?state.cloud*.27:tornado&&state.active?.18:fire&&state.active?.07:0
    if(shade)this.sky.rect(0,0,w,h).fill({color:tint,alpha:shade})
    if(state.cloud||state.visibility||tornado&&state.active){
      const amount=snow?state.visibility:storm?state.cloud:.7
      for(let band=0;band<4;band++){
        const y=-45+band*16,alpha=(snow?.05:.045)*amount
        this.sky.rect(0,y,w,34).fill({color:snow?0xf1f3e9:0x263843,alpha})
        this.sky.rect(0,h-y-34,w,34).fill({color:snow?0xf1f3e9:0x263843,alpha:alpha*.55})
      }
    }
    if(state.wetness>.01){
      const xmin=-worldX/scale,xmax=(w-worldX)/scale,ymin=-worldY/scale,ymax=(h-worldY)/scale
      for(let i=0;i<this.puddles.length;i++){
        const [x,y]=this.puddles[i];if(x<xmin-20||x>xmax+20||y<ymin-20||y>ymax+20)continue
        const n=hash(i,72),phase=mod(time*1.2+n/1000,1),size=5+n%10
        pixelEllipse(this.ground,x,y,size,2.2,0x8caeb1,state.wetness*.35)
        if(state.rain&&n%3===0)pixelEllipse(this.ground,x,y,2+phase*6,1+phase*2,0xccdddd,(1-phase)*.45,1,1)
      }
    }
    const count=state.snowfall?Math.min(640,Math.ceil(w*h/2100)):state.rain?Math.min(760,Math.ceil(w*h/1500)):0
    // Separate near/far sizes form depth without overwhelming people or labels.
    for(let i=0;i<count;i++){
      const n=hash(i,84),near=i%4===0,depth=near?1:.65
      const speed=snow?(near?68:42):(near?570:370),drift=snow?112:185
      const x=pixel(mod(n%100003/100003*(w+100)+time*drift*depth*wx+(snow?Math.sin(time*.7+i)*12:0),w+100)-50)
      const y=pixel(mod(hash(i,91)%100003/100003*(h+80)+time*(speed+drift*depth*wy),h+80)-40)
      if(snow){
        this.particles.rect(x,y,near?4:2,near?4:2).fill({color:near?0xfff9ed:0xd9e6e5,alpha:near?.85:.65})
        if(near&&i%8===0)this.particles.rect(x-2,y+2,8,2).fill({color:0xf6f7eb,alpha:.4})
      }else{
        const length=near?20:12,dx=(near?7:4)*wx
        for(let k=0;k<4;k++)this.particles.rect(x+Math.round(dx*k/4),y+Math.round(length*k/4),near?2:1,Math.ceil(length/4)+1).fill({color:near?0xc4dce0:0x97b6c1,alpha:near?.58:.35})
      }
    }
    if(state.hail){
      for(let i=0;i<Math.min(100,Math.ceil(w*h/13000));i++){
        const n=hash(i,49),phase=mod(time*1.7+(n%1000)/1000,1)
        const x=pixel(mod(n%100003/100003*(w+80)+time*94*wx,w+80)-40)
        const y=pixel(mod(hash(i,18)%100003/100003*(h+60)+time*(400+94*wy),h+60)-30)
        const r=state.kind==='hailstorm'?4:3
        this.particles.rect(x,y,r,r).fill({color:0xf5f3e7,alpha:.9}).rect(x+r-1,y+1,2,r).fill({color:0x8faeb9,alpha:.8})
        if(phase<.2)this.particles.rect(x-3,y+r+3,2,2).rect(x+r+3,y+r+2,2,2).fill({color:0xe4ecdf,alpha:.5})
      }
    }
    if(state.wind){
      const color=snow?0xf7f7ef:tornado?0xc9cdb6:0xb7cacc
      for(let i=0;i<(tornado?34:snow?30:18);i++){
        const n=hash(i,41),phase=mod(time*.35+i*.173,1)
        const speed=snow?210:290
        const x=pixel(mod(n%100003/100003*(w+260)+time*speed*wx,w+260)-130)
        const y=pixel(mod(hash(i,16)%100003/100003*(h+160)+time*speed*wy+Math.sin(time+i)*5,h+160)-80)
        const length=45+n%60,opacity=Math.sin(phase*Math.PI)*(tornado?.28:snow?.25:.18)
        // Four short, pixel-stepped segments follow the recorded wind bearing.
        this.particles.moveTo(x,y)
        for(let k=1;k<=4;k++)this.particles.lineTo(pixel(x+length*wx*k/4),pixel(y+length*wy*(k-1)/4)).lineTo(pixel(x+length*wx*k/4),pixel(y+length*wy*k/4))
        this.particles.stroke({color,width:2,alpha:opacity})
        if(tornado&&i%2===0)this.particles.rect(pixel(x+length*wx),pixel(y+length*wy-3),4,3).fill({color:i%4?0xd0bc7c:0x496450,alpha:.8})
      }
    }
    const cue=this.cue.sample(state.thunder,time,animate,reduced)
    if(storm&&state.active&&cue.amount>.01){
      // Distant cloud-to-cloud lightning: no invented strike at a campus person/building.
      const x=w*(.23+(hash(cue.event,7)%50)/100),y=h*.08
      const pts:Point[]=[[x,y],[x+14,y+24],[x-4,y+38],[x+28,y+61],[x+11,y+78],[x+40,y+105]]
      for(let i=1;i<pts.length;i++)pixelLine(this.lightning,...pts[i-1],...pts[i],0xb4d7e4,cue.amount*.16,6)
      for(let i=1;i<pts.length;i++)pixelLine(this.lightning,...pts[i-1],...pts[i],0xf7f2d5,cue.amount*.9,2)
      pixelLine(this.lightning,x+28,y+61,x+54,y+55,0xe8eff0,cue.amount*.55,2)
      pixelLine(this.lightning,x+54,y+55,x+64,y+69,0xe8eff0,cue.amount*.55,2)
      this.lightning.rect(0,0,w,h).fill({color:0xcbdde0,alpha:cue.amount*.035})
    }
  }
  get diagnostics(){return this.sample?{kind:this.sample.kind,active:this.sample.active,snowCover:this.sample.snowCover,rain:this.sample.rain}:null}
  destroy(){this.screen.destroy({children:true});this.ground.destroy()}
}
