import {Assets, Rectangle, Texture} from 'pixi.js'

export const CELL = 64
export const ART_VERSION = 'last-warning-pixel/3'
export interface AtlasFrame {x:number;y:number;w:number;h:number}
interface Manifest {revision:number;frames:Record<string,AtlasFrame>}
export interface TownArt {
  image:HTMLImageElement
  frames:Record<string,AtlasFrame>
  texture:(name:string)=>Texture
}

let pending:Promise<TownArt>|null=null
export function loadArt():Promise<TownArt> {
  if (!pending) pending = (async () => {
    const [manifest, source] = await Promise.all([
      fetch('/assets/art/last-warning/town-atlas.json').then(async response => {
        if (!response.ok) throw new Error('Town art manifest could not load')
        return response.json() as Promise<Manifest>
      }),
      Assets.load<Texture>('/assets/art/last-warning/town-atlas.png'),
    ])
    source.source.scaleMode='nearest'
    const image = new Image()
    image.src='/assets/art/last-warning/town-atlas.png'
    await image.decode()
    const textures = new Map<string,Texture>()
    return {image, frames:manifest.frames, texture(name:string) {
      let texture=textures.get(name)
      if (!texture) {
        const f=manifest.frames[name]
        if (!f) throw new Error(`Unknown town art: ${name}`)
        texture=new Texture({source:source.source,frame:new Rectangle(f.x,f.y,f.w,f.h)})
        textures.set(name,texture)
      }
      return texture
    }}
  })().catch(error=>{pending=null;throw error})
  return pending
}

export function hash(x:number,y=0):number {
  let n=Math.imul(x+9317,374761393)^Math.imul(y+1777,668265263)
  n=Math.imul(n^(n>>>13),1274126177)
  return (n^(n>>>16))>>>0
}

/** Palette matches generate_atlas.py; inspect the same person in either warning. */
export function residentAppearance(id:number,artSeed=42) {
  const variant=hash(id,artSeed)%12
  return {variant,
    skin:['#d5a67c','#aa7859','#e1bd91','#805a46'][variant%4],
    shirt:['#42616e','#a05b49','#d7ca9b','#dcbd70','#577b51','#507b85'][variant%6],
    hair:variant%3?'#705b40':'#273d40',
    hat:variant>7?'#dcbd70':null}
}

export function drawArt(ctx:CanvasRenderingContext2D, art:TownArt, name:string, x:number,y:number,scale=1) {
  const f=art.frames[name]
  ctx.drawImage(art.image,f.x,f.y,f.w,f.h,Math.round(x),Math.round(y),f.w*scale,f.h*scale)
}
