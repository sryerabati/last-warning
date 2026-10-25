const smooth=(value:number)=>{const x=Math.max(0,Math.min(1,value));return x*x*(3-2*x)}

/** Geographically anchored detail transition, rather than a rectangular window.
 * Both sides already contain the same mapped streets and buildings. This mask
 * brings in the live world gradually across a broad, irregular edge. */
export function detailCoverage(x:number,y:number,width:number,height:number,progress:number){
  if(x<0||y<0||x>width||y>height)return 0
  const edge=Math.min(x,width-x,y,height-y)
  const variation=22*Math.sin(x/81+y/123)+15*Math.sin(x/43-y/69)
  const feather=130*(1-smooth((progress-.90)/.10))
  if(feather<.01)return 1
  return smooth((edge-40-variation)/feather)
}

export class CampusDetailMask {
  private canvas=document.createElement('canvas')
  private context=this.canvas.getContext('2d')!
  private image:ImageData
  private lastProgress=-1
  private lastSize=''
  constructor(){this.canvas.width=256;this.canvas.height=256;this.image=this.context.createImageData(256,256)}
  draw(ctx:CanvasRenderingContext2D,bounds:number[],mpp:number,step:number,progress:number){
    const [left,top,right,bottom]=bounds
    const width=(right-left)*mpp,height=(bottom-top)*mpp
    // Before the last approach the world-space mask is static and cached.
    const phase=progress<.9?0:Math.round(progress*120)/120,key=`${Math.round(width)}:${Math.round(height)}`
    if(phase!==this.lastProgress||key!==this.lastSize){
      const data=this.image.data
      for(let y=0;y<256;y++)for(let x=0;x<256;x++)data[(y*256+x)*4+3]=Math.round(255*detailCoverage(x/255*width,y/255*height,width,height,phase))
      this.context.putImageData(this.image,0,0);this.lastProgress=phase;this.lastSize=key
    }
    const strength=smooth(Math.log(9/mpp)/Math.log(6))
    if(!strength)return
    ctx.save();ctx.globalCompositeOperation='destination-out';ctx.globalAlpha=strength
    // Interpolation applies only to alpha, never to the pixel-art drawing.
    ctx.imageSmoothingEnabled=true
    ctx.drawImage(this.canvas,left/step,top/step,(right-left)/step,(bottom-top)/step)
    ctx.restore()
  }
}
