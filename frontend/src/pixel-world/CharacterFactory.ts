import {Rectangle,Texture} from 'pixi.js'
import {appearanceKey,drawCharacter,CHARACTER_HEIGHT,CHARACTER_WIDTH,type CharacterAppearance,type CharacterMotionStyle} from './CharacterDesign'
export {characterAppearance,drawCharacter,CHARACTER_FOOT,CHARACTER_HEIGHT,CHARACTER_WIDTH} from './CharacterDesign'
export type {CharacterAppearance} from './CharacterDesign'

interface Page {canvas:HTMLCanvasElement;ctx:CanvasRenderingContext2D;texture:Texture;count:number;dirty:boolean}
/** Eight poses × four directions packed into shared pages, generated once per
 * persistent recipe. At 300 residents this uses four 2048² pages, not 300 textures. */
export class CharacterFactory {
  private pages:Page[]=[]
  private appearances=new Map<string,Texture[]>()
  texture(appearance:CharacterAppearance,direction:number,pose:number,motion:CharacterMotionStyle='walk'):Texture {
    const key=appearanceKey(appearance)+':'+motion
    let frames=this.appearances.get(key)
    if(!frames) {
      let page=this.pages.at(-1)
      if(!page||page.count===80){const canvas=document.createElement('canvas');canvas.width=canvas.height=2048
        const ctx=canvas.getContext('2d')!;ctx.imageSmoothingEnabled=false
        const texture=Texture.from(canvas);texture.source.scaleMode='nearest'
        page={canvas,ctx,texture,count:0,dirty:false};this.pages.push(page)}
      const column=page.count%8,row=Math.floor(page.count/8),x=column*256,y=row*192
      frames=[]
      for(let facing=0;facing<4;facing++)for(let frame=0;frame<8;frame++) {
        const fx=x+frame*CHARACTER_WIDTH,fy=y+facing*CHARACTER_HEIGHT
        page.ctx.save();page.ctx.translate(fx,fy);drawCharacter(page.ctx,appearance,facing,frame,motion);page.ctx.restore()
        frames.push(new Texture({source:page.texture.source,frame:new Rectangle(fx,fy,CHARACTER_WIDTH,CHARACTER_HEIGHT)}))
      }
      page.count++;page.dirty=true;this.appearances.set(key,frames)
    }
    return frames[Math.max(0,Math.min(3,direction))*8+Math.max(0,Math.min(7,pose))]
  }
  flush(){for(const page of this.pages)if(page.dirty){page.texture.source.update();page.dirty=false}}
  destroy(){for(const frames of this.appearances.values())for(const texture of frames)texture.destroy(false)
    for(const page of this.pages){page.texture.destroy(true);page.canvas.width=page.canvas.height=1}
    this.appearances.clear();this.pages=[]}
  diagnostics(){return{recipes:this.appearances.size,pages:this.pages.length,frameSize:[32,48],poses:8,facings:4}}
}
