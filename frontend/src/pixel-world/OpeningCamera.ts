/** Geographic registration for a continuous flight into the live campus canvas.
 * Distances and bounds use CSS pixels, independent of renderer/device resolution. */
export interface OpeningLanding {
  target:[longitude:number,latitude:number]
  metersPerPixel:number
  metersPerDegree:[longitude:number,latitude:number]
  anchor:[normalizedX:number,normalizedY:number]
  viewport:[width:number,height:number]
  geographicBounds:[west:number,south:number,east:number,north:number]
}

export type OpeningScreenBounds=[left:number,top:number,right:number,bottom:number]

export interface OpeningCamera {
  /** Repeated calls preserve the saved view and refresh resized landing geometry. */
  begin():OpeningLanding|null
  /** Keep the Oval at a normalized viewport anchor without ordinary zoom snapping. */
  pose(metersPerPixel:number,anchorNormalized:[number,number]):OpeningScreenBounds
  /** Complete at the prepared normal camera, or restore the pre-flight view. */
  end(completed:boolean):void
}
