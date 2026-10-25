export interface VehicleVisibility {id:string;fraction:number;visible:boolean}

/** Depot departures/returns are recorded events, independent of whether the
 * bus has resident passengers. Empty scheduled inventory stays off the map. */
export function busVisibleAt(finalActive:boolean,transitions:VehicleVisibility[],fraction:number):boolean {
  if(fraction>=1)return finalActive
  let visible=finalActive
  for(const row of transitions) {
    if(row.fraction>fraction)break
    visible=row.visible
  }
  return visible
}
