import {useEffect,useRef,type CSSProperties} from 'react'
import {characterAppearance,drawCharacter,type CharacterAppearance} from '../pixel-world/CharacterDesign'

export type PixelIconName = 'beacon'|'flood'|'fire'|'tornado'|'snow'|'hail'|'storm'|'zone'|'warning'|'compare'|'runs'|'advanced'|'brain'|'people'|'shelter'|'danger'|'play'|'pause'|'back'|'step-back'|'step-next'|'close'|'check'|'settings'|'edit'|'follow'|'download'|'arrow'|'add'|'reset'|'chart'|'book'|'volume-on'|'volume-off'|'loading'|'route'|'pin'|'chevron-left'|'chevron-right'|'town'|'search'|'zoom-in'|'zoom-out'|'focus'|'fit'|'upload'|'trash'|'restart'|'menu'|'globe'|'replay'|'bus'

const paths:Record<PixelIconName,string>={
  bus:'M3 1h10v1h1v11h-1v2h-2v-2H5v2H3v-2H2V2h1zM4 3v5h8V3zM4 10v2h2v-2zM10 10v2h2v-2zM6 2v1h4V2z',
  beacon:'M7 2h2v2H7zM4 4h2v2H4zM10 4h2v2h-2zM2 7h2v3H2zM12 7h2v3h-2zM6 6h4v5H6zM5 11h6v2H5zM4 13h8v1H4z',
  flood:'M1 4h3v1h3V4h3v1h3V4h2v3h-2v1h-3V7H7v1H4V7H1zM1 10h3v1h3v-1h3v1h3v-1h2v3h-2v1h-3v-1H7v1H4v-1H1z',
  fire:'M8 1h2v3h2v3h2v5h-2v2H4v-2H2V8h2V5h2v3h2zM6 10v3h4v-3H9V8H7v2z',
  tornado:'M2 2h12v2H2zM4 5h10v2H4zM2 8h10v2H2zM4 11h6v2H4zM6 14h2v1H6z',
  snow:'M7 0h2v3h2V2h2v2h-2v2H9v1h3V5h2v2h2v2h-2v2h-2V9H9v1h2v2h2v2h-2v-1H9v3H7v-3H5v1H3v-2h2v-2h2V9H4v2H2V9H0V7h2V5h2v2h3V6H5V4H3V2h2v1h2z',
  hail:'M5 1h6v2h3v2h1v4H1V5h2V3h2zM2 11h3v3H2zM7 12h3v3H7zM12 10h3v3h-3z',
  storm:'M5 1h6v2h3v2h1v4h-4V7H8v2H1V5h2V3h2zM8 7h4l-3 4h3l-6 5 1-5H5zM1 11h2v4H1zM13 12h2v3h-2z',
  zone:'M1 1h5v2H3v3H1zM10 1h5v5h-2V3h-3zM1 10h2v3h3v2H1zM13 10h2v5h-5v-2h3zM7 4h2v5H7zM7 11h2v2H7z',
  warning:'M7 1h2v2h2v3h2v3h2v5H1V9h2V6h2V3h2zM7 5v5h2V5zM7 11v2h2v-2z',
  compare:'M3 2h2v2h7v2H5v2H3V6H1V4h2zM11 8h2v2h2v2h-2v2h-2v-2H4v-2h7z',
  runs:'M3 1h9v2h2v11H3zM5 4v1h7V4zM5 7v1h7V7zM5 10v1h5v-1zM1 4h1v11h10v1H1z',
  advanced:'M2 1h2v4h3v2H4v8H2V7H0V5h2zM10 1h2v8h3v2h-3v4h-2v-4H7V9h3z',
  brain:'M4 2h3v2h2V2h3v2h2v7h-2v3H9v-3H7v3H4v-3H2V4h2zM4 5v3h2V5zM10 5v3h2V5z',
  people:'M6 1h4v4H6zM4 6h8v5h-2v4H8v-4H7v4H5v-4H3V7h1zM0 4h3v3H0zM13 4h3v3h-3zM0 8h2v5H0zM14 8h2v5h-2z',
  shelter:'M7 1h2v2h2v2h2v2h2v2h-2v6H3V9H1V7h2V5h2V3h2zM7 9v5h3V9zM4 8v3h2V8z',
  danger:'M3 1h10v2h2v10h-2v2H3v-2H1V3h2zM7 4v5h2V4zM7 11v2h2v-2z',
  play:'M4 2h2v1h2v2h2v1h2v2h2v1h-2v2h-2v1H8v2H6v1H4z',
  pause:'M3 2h4v12H3zM9 2h4v12H9z',
  back:'M2 2h2v12H2zM12 2h2v12h-2v-2h-2v-2H8V8H6V6h2V4h2V3h2z',
  'step-back':'M2 3h2v10H2zM11 3h2v10h-2v-2H8V9H6V7h2V5h3z',
  'step-next':'M12 3h2v10h-2zM3 3h2v2h3v2h2v2H8v2H5v2H3z',
  close:'M2 2h3v2h2v2h2V4h2V2h3v3h-2v2h-2v2h2v2h2v3h-3v-2H9v-2H7v2H5v2H2v-3h2V9h2V7H4V5H2z',
  check:'M13 3h2v3h-2v2h-2v2H9v2H7v2H5v-2H3v-2H1V7h3v2h2v1h1V8h2V6h2V4h2z',
  settings:'M6 1h4v2h2v2h3v6h-3v2h-2v2H6v-2H4v-2H1V5h3V3h2zM6 6v4h4V6z',
  edit:'M11 1h2l2 2v2l-2 2-4-4zM8 4l4 4-7 7H1v-4zM3 11v2h2z',
  follow:'M7 0h2v3h4v4h3v2h-3v4H9v3H7v-3H3V9H0V7h3V3h4zM5 5v6h6V5zM7 7h2v2H7z',
  download:'M6 1h4v6h3v2h-2v2H9v2H7v-2H5V9H3V7h3zM1 11h2v3h10v-3h2v5H1z',
  arrow:'M8 2h2v2h2v2h2v4h-2v2h-2v2H8v-3H2V7h6V5h2V4H8z',
  add:'M6 1h4v5h5v4h-5v5H6v-5H1V6h5z',
  reset:'M3 1h2v3h7v2h2v6h-2v2H6v-2h6V6H5v3H3V7H1V5h2z',
  chart:'M1 1h2v12h12v2H1zM5 8h2v3H5zM9 5h2v6H9zM13 2h2v9h-2z',
  book:'M1 2h5v1h4V2h5v12h-5v1H6v-1H1zM3 4v8h3v1h1V5H6V4zM9 5v8h1v-1h3V4h-3v1z',
  'volume-on':'M6 2h2v12H6v-2H4v-2H1V6h3V4h2zM10 5h2v6h-2zM12 2h2v2h1v8h-1v2h-2v-2h1V4h-1z',
  'volume-off':'M6 2h2v12H6v-2H4v-2H1V6h3V4h2zM10 5h2v2h1V5h2v2h-1v2h1v2h-2V9h-1v2h-2V9h1V7h-1z',
  loading:'M3 1h10v2H3zM4 3h2v2h1v1h2V5h1V3h2v3h-2v1H9v2h1v1h2v3h-2v-2H9v-1H7v1H6v2H4v-3h2V9h1V7H6V6H4zM3 13h10v2H3z',
  route:'M1 1h4v4H1zM7 2h6v2H7zM12 4h2v4H8v3H6V6h6zM6 12h3v2H6zM11 11h4v4h-4z',
  pin:'M5 1h6v1h2v2h1v6h-2v2h-2v2H9v2H7v-2H6v-2H4v-2H2V4h1V2h2zM6 4v5h4V4z',
  'chevron-left':'M9 2h3v2h-2v2H8v4h2v2h2v2H9v-2H7v-2H5V6h2V4h2z',
  'chevron-right':'M4 2h3v2h2v2h2v4H9v2H7v2H4v-2h2v-2h2V6H6V4H4z',
  town:'M2 3h6v12H1V6h1zM3 5v2h2V5zM3 9v2h2V9zM6 12v3H4v-3zM11 5h2v2h2v8H9V7h2zM11 9v2h2V9z',
  search:'M3 1h6v1h2v2h1v5h-1v2H9v1H4v-1H2V9H1V4h1V2h1zM4 3v1H3v5h1v1h5V9h1V4H9V3zM11 11h2v1h1v1h1v2h-2v-1h-1v-1h-1z',
  'zoom-in':'M3 1h6v1h2v2h1v5h-1v2H9v1H4v-1H2V9H1V4h1V2h1zM4 3v1H3v5h1v1h5V9h1V4H9V3zM6 4h1v2h2v1H7v2H6V7H4V6h2zM11 11h2v1h1v1h1v2h-2v-1h-1v-1h-1z',
  'zoom-out':'M3 1h6v1h2v2h1v5h-1v2H9v1H4v-1H2V9H1V4h1V2h1zM4 3v1H3v5h1v1h5V9h1V4H9V3zM4 6h5v1H4zM11 11h2v1h1v1h1v2h-2v-1h-1v-1h-1z',
  focus:'M1 1h5v2H3v3H1zM10 1h5v5h-2V3h-3zM1 10h2v3h3v2H1zM13 10h2v5h-5v-2h3zM6 6h4v4H6z',
  fit:'M1 1h5v2H3v3H1zM10 1h5v5h-2V3h-3zM1 10h2v3h3v2H1zM13 10h2v5h-5v-2h3zM5 5h6v6H5zM6 6v4h4V6z',
  upload:'M7 1h2v2h2v2h2v2h-3v5H6V7H3V5h2V3h2zM1 11h2v3h10v-3h2v5H1z',
  trash:'M6 1h4v2h4v2H2V3h4zM3 6h10v9H3zM5 8v5h1V8zM10 8v5h1V8z',
  restart:'M3 1h2v3h7v2h2v6h-2v2H6v-2h6V6H5v3H3V7H1V5h2z',
  menu:'M2 3h12v2H2zM2 7h12v2H2zM2 11h12v2H2z',
  globe:'M5 1h6v1h2v2h1v2h1v4h-1v2h-1v2h-2v1H5v-1H3v-2H2v-2H1V6h1V4h1V2h2zM6 3v3h4V3zM3 6v4h1V6zM6 8v3h4V8zM12 6v4h1V6zM7 13h2v-1H7z',
  replay:'M5 1h6v1h2v2h1v2h1v5h-1v2h-2v1H6v-2h5v-1h1V6h-1V4H6v1H4V3H2V1h2v1h1zM5 6h2v1h2v1h2v1H9v1H7v1H5z',
}

export function PixelIcon({name,size=24,className='',style}: {name:PixelIconName;size?:number;className?:string;style?:CSSProperties}) {
  return <svg className={`pixel-icon ${className}`} width={size} height={size} viewBox="0 0 16 16" fill="currentColor" fillRule="evenodd" shapeRendering="crispEdges" aria-hidden="true" style={style}><path d={paths[name]}/></svg>
}

export function ResidentPortrait({id,appearance,character,seed=42}: {id:number;appearance?:{skin:string;shirt:string;hair:string;hat:string|null};character?:Partial<CharacterAppearance>;seed?:number}) {
  const canvas=useRef<HTMLCanvasElement>(null)
  useEffect(()=>{
    if(!character||!canvas.current)return
    const ctx=canvas.current.getContext('2d')!;ctx.clearRect(0,0,32,48);ctx.fillStyle='#263f39';ctx.fillRect(0,0,32,48)
    ctx.fillStyle='#375246';ctx.fillRect(0,40,32,8);drawCharacter(ctx,characterAppearance(id,seed,character),2,0)
  },[id,seed,character])
  const palettes=[['#815044','#b7613f'],['#b9855a','#406d82'],['#704b36','#d0a146'],['#c5956a','#69866b'],['#664333','#8a6686'],['#a67451','#4f7b83']]
  const [fallbackSkin,fallbackShirt]=palettes[id%palettes.length]
  const skin=appearance?.skin??fallbackSkin,shirt=appearance?.shirt??fallbackShirt
  if(character)return <canvas ref={canvas} className="resident-portrait" width={32} height={48} style={{imageRendering:'pixelated',objectFit:'contain',background:'#263f39'}} aria-hidden="true"/>
  return <svg className="resident-portrait" viewBox="0 0 24 28" shapeRendering="crispEdges" aria-hidden="true"><path fill="#263f39" d="M0 0h24v28H0z"/><path fill="#375246" d="M0 23h24v5H0z"/><path fill={appearance?.hair??'#342d29'} d="M8 3h8v2h2v7H6V5h2z"/><path fill={skin} d="M7 7h10v7H7zM9 14h6v3H9z"/>{appearance?.hat&&<path fill={appearance.hat} d="M7 2h10v3H7zM5 5h14v2H5z"/>}<path fill="#242c2b" d="M8 8h2v2H8zM14 8h2v2h-2z"/><path fill={shirt} d="M5 16h14v9H5z"/><path fill={skin} d="M3 18h3v7H3zM18 18h3v7h-3z"/><path fill="#c6b993" d="M6 25h5v3H6zM13 25h5v3h-5z"/></svg>
}
