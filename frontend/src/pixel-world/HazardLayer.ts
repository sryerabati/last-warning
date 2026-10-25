import {Container,Graphics,Sprite,Texture} from 'pixi.js'
import type {DisasterType,Frame,Point} from '../types'
import {hazardAt} from './ImpactPresentation'
import {drawTornado} from './TornadoVisual'
import {pixelEllipse} from './PixelEffectsGeometry'
import {CELL,hash,type TownArt} from './Art'

export class HazardLayer {
  readonly root=new Container()
  readonly closures=new Container()
  private footprint=new Container()
  private fire=new Container()
  private wind=new Graphics()
  private highlights=new Graphics()
  private sprites:Sprite[]=[]
  private flames:Sprite[]=[]
  private barriers:Sprite[]=[]
  private frame:Frame|null=null
  private type:DisasterType='flood'
  private previousCenter:Point|null=null
  constructor(private art:TownArt,private campus=false,private depthRoot?:Container) {
    this.root.addChild(this.footprint,this.highlights,this.fire)
    ;(depthRoot??this.root).addChild(this.wind)
    this.root.eventMode='none';this.closures.eventMode='none'
  }
  setFrame(frame:Frame,fallback:DisasterType='flood') {
    this.previousCenter=this.frame&&frame.tick===this.frame.tick+1?this.frame.hazard?.center??null:null
    this.frame=frame;this.type=frame.hazard?.type??fallback
    const active=frame.active_hazard_cells??frame.hazard_cells
    const cells=this.type==='flood'?active:this.type==='wildfire'?frame.hazard_cells:[]
    for(let i=0;i<Math.max(cells.length,this.sprites.length);i++) {
      let s=this.sprites[i]
      if(!s) {s=new Sprite(Texture.WHITE);s.width=s.height=CELL;this.footprint.addChild(s);this.sprites.push(s)}
      s.visible=i<cells.length
      if(s.visible) {s.position.set(cells[i][0]*CELL,cells[i][1]*CELL);s.tint=this.type==='flood'?0x4594aa:this.type==='wildfire'?0x48483c:0x777466;s.alpha=this.type==='flood'?.53:this.type==='wildfire'?.40:.24}
    }
    const flameCells=this.type==='wildfire'?active:[]
    for(let i=0;i<Math.max(flameCells.length,this.flames.length);i++) {
      let s=this.flames[i]
      if(!s) {s=new Sprite(this.art.texture('fire0'));s.anchor.set(.5,1);this.fire.addChild(s);this.flames.push(s)}
      s.visible=i<flameCells.length
      if(s.visible) {s.position.set((flameCells[i][0]+.5)*CELL,(flameCells[i][1]+.8)*CELL);s.scale.set(1.1+(hash(...flameCells[i])%5)*.1)}
    }
    const closures=frame.blocked_roads.filter((_,i)=>!this.campus||i%6===0)
    for(let i=0;i<Math.max(closures.length,this.barriers.length);i++) {
      let s=this.barriers[i]
      if(!s) {s=new Sprite(this.art.texture('barrier'));s.anchor.set(.5,.5);s.scale.set(.5);this.closures.addChild(s);this.barriers.push(s)}
      s.visible=i<closures.length
      if(s.visible){const offset=.5;s.position.set((closures[i][0]+offset)*CELL,(closures[i][1]+offset)*CELL)}
    }
  }
  draw(time:number,fraction=1,_animate=true,scale=1,reducedMotion=false) {
    const frame=this.frame
    if(!frame)return
    this.highlights.clear();this.wind.clear();if(this.depthRoot)this.wind.zIndex=99998
    if(this.type==='flood') {
      const cells=frame.active_hazard_cells??frame.hazard_cells
      for(let i=0;i<cells.length;i+=2) {
        const [x,y]=cells[i],phase=(time*.75+(hash(x,y)%17)/17)%1
        const px=x*CELL+8+phase*14,py=y*CELL+14+(hash(y,x)%35)
        this.highlights.moveTo(px,py).lineTo(px+15,py).moveTo(px+4,py+3).lineTo(px+9,py+3)
      }
      this.highlights.stroke({color:0xb1cec0,width:1,alpha:.55})
    } else if(this.type==='wildfire') {
      for(let i=0;i<this.flames.length;i++)if(this.flames[i].visible) {
        const s=this.flames[i];s.texture=this.art.texture(`fire${Math.floor(time*3+i)%4}`)
        if(i%3===0) {
          const phase=(time*.4+i*.13)%1
          this.wind.rect(s.x-6+phase*13,s.y-43-phase*58,10+phase*15,8+phase*14).fill({color:0x4d5650,alpha:.24*(1-phase)})
        }
      }
    } else if(this.type==='tornado'&&frame.hazard?.center) {
      const {active,center}=hazardAt(frame,this.previousCenter,fraction)
      // Debris marks recorded affected cells after the wind has moved on.
      for(let i=0;i<frame.hazard_cells.length;i+=2){const [x,y]=frame.hazard_cells[i],n=hash(x,y)
        this.highlights.rect((x+.2+n%5*.1)*CELL,(y+.3+n%3*.1)*CELL,7,2).fill({color:0x77674c,alpha:.3})
      }
      if(!active)return
      const [cx,cy]=center,offset=this.campus?0:.5,px=(cx+offset)*CELL,py=(cy+offset)*CELL
      const radius=Number(frame.hazard.ground_radius??frame.hazard.radius??2.2)*CELL
      if(this.depthRoot)this.wind.zIndex=py+1
      drawTornado(this.highlights,this.wind,{center:[px,py],radius,seconds:time,scale,active,reducedMotion})
    } else if(this.type==='public_safety') {
      const active=frame.hazard?.active??(frame.active_hazard_cells??frame.hazard_cells).length>0
      if(!active)return
      const center=frame.hazard?.center??[20,20],r=(frame.hazard?.radius??3)*CELL,x=center[0]*CELL,y=center[1]*CELL
      pixelEllipse(this.wind,x,y,r,r,0xc58b47,.13,4)
      pixelEllipse(this.wind,x,y,r,r,0xe9bf6e,.9,4,4)
      for(let i=0;i<24;i++){const a=i*Math.PI/12,px=Math.round((x+Math.cos(a)*r)/2)*2,py=Math.round((y+Math.sin(a)*r)/2)*2;this.wind.rect(px-4,py-4,8,8).fill(i%2?0x354943:0xe9bf6e)}
      this.wind.rect(x-12,y-17,24,28).fill(0x344b43).stroke({color:0xe9bf6e,width:2})
      this.wind.rect(x-2,y-12,4,12).rect(x-2,y+4,4,4).fill(0xe9bf6e)
    }
  }
}
