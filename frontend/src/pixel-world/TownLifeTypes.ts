import type {City,Frame,TownPlace} from '../types'

// Additive recording fields. The old grid recordings deliberately lack these.
export type {TownPlace,TownInteraction,AgentActivity as TownActivity} from '../types'
export type LivingCity=City
export type LivingFrame=Frame

export function bounds(place:TownPlace) {
  const points=place.footprint.length?place.footprint:[place.position]
  const minX=Math.min(...points.map(p=>p[0])),minY=Math.min(...points.map(p=>p[1]))
  return {x:minX,y:minY,w:Math.max(...points.map(p=>p[0]))-minX+1,h:Math.max(...points.map(p=>p[1]))-minY+1}
}
