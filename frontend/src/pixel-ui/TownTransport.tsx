import type {CampusDayType} from '../types'
import {PixelIcon} from './PixelIcon'

export function townClock(minutes:number) {
  const value=((Math.floor(minutes)%1440)+1440)%1440
  return `${Math.floor(value/60).toString().padStart(2,'0')}:${(value%60).toString().padStart(2,'0')}`
}

export function TownTransport({day,dayType,minutes,playing,speed,disabled,onPlaying,onSpeed,onTime}: {
  day:number;dayType?:CampusDayType;minutes:number;playing:boolean;speed:number;disabled:boolean;
  onPlaying:(playing:boolean)=>void;onSpeed:(speed:number)=>void;onTime:(minutes:number)=>void
}) {
  return <div className="town-transport-row">
    <div className="town-clock"><strong title={`Day ${day}`}>{dayType?({teaching:'Teaching day',weekend:'Weekend',class_break:'Class break',closed:'Campus closed'}[dayType]):`Day ${day}`}</strong><span>{townClock(minutes)}</span></div>
    <div className="town-transport-controls">
      <button className="town-play" aria-label={playing?'Pause town':'Play town'} title="Play / pause · Space" disabled={disabled} onClick={()=>onPlaying(!playing)}><PixelIcon name={playing?'pause':'play'} size={17}/></button>
      <select aria-label="Town speed" value={speed} disabled={disabled} onChange={event=>onSpeed(Number(event.target.value))}>{[1,2,4,8].map(value=><option key={value} value={value}>{value}×</option>)}</select>
      <select aria-label="Jump to time of day" value="" disabled={disabled} onChange={event=>onTime(Number(event.target.value))}>
        <option value="" disabled>Time of day</option><option value={480}>Morning · 08:00</option><option value={720}>Noon · 12:00</option><option value={1080}>Evening · 18:00</option><option value={1320}>Night · 22:00</option>
      </select>
    </div>
  </div>
}
