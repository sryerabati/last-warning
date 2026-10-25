import type {Graphics} from 'pixi.js'

export type PixelRect=[x:number,y:number,width:number,height:number]
const snap=(n:number,unit:number)=>Math.round(n/unit)*unit

/** Raster geometry: every effect has hard, integer-aligned steps instead of a
 * smooth vector edge. Coordinates are presentation only, never physics. */
export function ellipsePixels(x:number,y:number,rx:number,ry:number,unit=2,outline=0):PixelRect[]{
  if(![x,y,rx,ry,unit,outline].every(Number.isFinite)||rx<=0||ry<=0||unit<1)return []
  unit=Math.max(1,Math.round(unit));const cx=snap(x,unit),cy=snap(y,unit)
  const rows=Math.max(1,Math.round(ry/unit)),cols=Math.max(1,Math.round(rx/unit)),rects:PixelRect[]=[]
  const inset=Math.max(1,Math.ceil(outline/unit)),innerY=rows-inset,innerX=cols-inset
  for(let row=-rows;row<rows;row++){
    const dy=row+.5,extent=Math.max(1,Math.round(cols*Math.sqrt(Math.max(0,1-(dy/rows)**2))))
    const inner=outline>0&&innerY>0&&Math.abs(dy)<innerY?Math.max(0,Math.round(innerX*Math.sqrt(Math.max(0,1-(dy/innerY)**2)))):0
    if(inner>0&&inner<extent){rects.push([cx-extent*unit,cy+row*unit,(extent-inner)*unit,unit],[cx+inner*unit,cy+row*unit,(extent-inner)*unit,unit])}
    else if(inner===0)rects.push([cx-extent*unit,cy+row*unit,extent*2*unit,unit])
  }
  return rects
}

export function linePixels(x0:number,y0:number,x1:number,y1:number,unit=2):PixelRect[]{
  if(![x0,y0,x1,y1,unit].every(Number.isFinite)||unit<1)return []
  unit=Math.max(1,Math.round(unit));let x=Math.round(x0/unit),y=Math.round(y0/unit)
  const tx=Math.round(x1/unit),ty=Math.round(y1/unit),dx=Math.abs(tx-x),dy=-Math.abs(ty-y),sx=x<tx?1:-1,sy=y<ty?1:-1
  let error=dx+dy;const rects:PixelRect[]=[]
  for(;;){rects.push([x*unit,y*unit,unit,unit]);if(x===tx&&y===ty)break
    const twice=error*2;if(twice>=dy){error+=dy;x+=sx}if(twice<=dx){error+=dx;y+=sy}}
  return rects
}

export function pixelEllipse(g:Graphics,x:number,y:number,rx:number,ry:number,color:number,alpha=1,unit=2,outline=0){
  const rects=ellipsePixels(x,y,rx,ry,unit,outline)
  for(const rect of rects)g.rect(...rect)
  if(rects.length)g.fill({color,alpha})
}
export function pixelLine(g:Graphics,x0:number,y0:number,x1:number,y1:number,color:number,alpha=1,unit=2){
  for(const rect of linePixels(x0,y0,x1,y1,unit))g.rect(...rect)
  g.fill({color,alpha})
}
