/** Quantize a cached art surface, never the map coordinates underneath it.
 * Sampling keeps the original palette and transparency; nearest enlargement
 * gives each authored pixel the same two-world-pixel footprint. */
export function pixelateCanvas(canvas:HTMLCanvasElement,grid=2) {
  if(grid<=1)return
  const sample=document.createElement('canvas')
  sample.width=Math.ceil(canvas.width/grid);sample.height=Math.ceil(canvas.height/grid)
  const small=sample.getContext('2d')!,target=canvas.getContext('2d')!
  small.imageSmoothingEnabled=false
  small.drawImage(canvas,0,0,canvas.width/grid,canvas.height/grid)
  target.save();target.setTransform(1,0,0,1,0,0);target.clearRect(0,0,canvas.width,canvas.height)
  target.imageSmoothingEnabled=false;target.drawImage(sample,0,0,sample.width*grid,sample.height*grid);target.restore()
  sample.width=sample.height=1
}

/** Surface masks use binary coverage so a paved edge never becomes a soft
 * translucent fringe. Threshold after the union, preserving shared junctions. */
export function hardenMask(ctx:CanvasRenderingContext2D) {
  const image=ctx.getImageData(0,0,ctx.canvas.width,ctx.canvas.height),pixels=image.data
  for(let i=3;i<pixels.length;i+=4)pixels[i]=pixels[i]>=128?255:0
  ctx.putImageData(image,0,0)
}
