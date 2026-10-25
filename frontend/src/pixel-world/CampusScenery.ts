import {Rectangle,Texture} from 'pixi.js'
import type {CampusDecoration} from './CampusTown'

export interface ScenerySprite {texture:Texture;x:number;y:number;depth:number}
/** Shelf-packed scenery shares a handful of sources across every comparison
 * view. Source canvases are discarded after packing; texture ownership is here. */
export function packCampusScenery(objects:CampusDecoration[]) {
  const sprites:ScenerySprite[]=[],pages:{canvas:HTMLCanvasElement;ctx:CanvasRenderingContext2D;texture:Texture;x:number;y:number;row:number}[]=[]
  for(const object of [...objects].sort((a,b)=>b.canvas.height-a.canvas.height)) {
    const w=object.canvas.width+2,h=object.canvas.height+2
    let page=pages.at(-1)
    if(page&&page.x+w>page.canvas.width){page.x=0;page.y+=page.row;page.row=0}
    if(!page||page.y+h>page.canvas.height||w>page.canvas.width){
      const size=Math.max(2048,2**Math.ceil(Math.log2(Math.max(w,h))))
      const canvas=document.createElement('canvas');canvas.width=canvas.height=size
      const ctx=canvas.getContext('2d')!;ctx.imageSmoothingEnabled=false
      const texture=Texture.from(canvas);texture.source.scaleMode='nearest'
      page={canvas,ctx,texture,x:0,y:0,row:0};pages.push(page)
    }
    const x=page.x+1,y=page.y+1;page.ctx.drawImage(object.canvas,x,y)
    sprites.push({texture:new Texture({source:page.texture.source,frame:new Rectangle(x,y,object.canvas.width,object.canvas.height)}),x:object.x,y:object.y,depth:object.depth})
    page.x+=w;page.row=Math.max(page.row,h);object.canvas.width=object.canvas.height=1
  }
  for(const page of pages)page.texture.source.update()
  return {sprites,destroy(){for(const sprite of sprites)sprite.texture.destroy(false);for(const page of pages){page.texture.destroy(true);page.canvas.width=page.canvas.height=1}}}
}
