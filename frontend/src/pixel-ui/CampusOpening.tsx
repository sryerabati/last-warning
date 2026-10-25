import {useEffect,useRef,useState} from 'react'
import {PixelIcon} from './PixelIcon'
import type {City} from '../types'
import {CampusDetailMask} from './OpeningBlend'
import type {OpeningCamera,OpeningLanding} from '../pixel-world/OpeningCamera'
import {EARTH_RADIUS,geographicProjector,loadOpeningGeography,OVAL,paintRegion,withCampusContext,type OpeningGeography,type LonLat} from './OpeningGeography'
import './CampusOpening.css'

const SEEN='last-warning-opening/v2',ORBIT=2400,FLIGHT=8400,DURATION=ORBIT+FLIGHT
const radians=Math.PI/180
const clamp=(n:number)=>Math.max(0,Math.min(1,n))
const ease=(n:number)=>{n=clamp(n);return n*n*(3-2*n)}
export function shouldShowOpening(){try{return !matchMedia('(prefers-reduced-motion: reduce)').matches&&!sessionStorage.getItem(SEEN)}catch{return !matchMedia('(prefers-reduced-motion: reduce)').matches}}
/** One geographic flight into the LIVE campus. No screenshot or opacity dissolve. */
export function CampusOpening({camera,city,failed,onComplete,onSoundFlight,onArrival}:{camera:OpeningCamera|null;city?:City;failed:boolean;onComplete:()=>void;onSoundFlight?:(progress:number|null)=>void;onArrival?:()=>void}){
  const canvas=useRef<HTMLCanvasElement>(null),root=useRef<HTMLElement>(null),skip=useRef<HTMLButtonElement>(null)
  const latest=useRef({camera,city,failed,onComplete,onSoundFlight,onArrival});latest.current={camera,city,failed,onComplete,onSoundFlight,onArrival}
  const activeCamera=useRef<OpeningCamera|null>(null)
  const [phase,setPhase]=useState('Earth'),[reduced,setReduced]=useState(()=>matchMedia('(prefers-reduced-motion: reduce)').matches)
  const done=useRef(false)
  const finish=(completed=false)=>{if(done.current)return;done.current=true;activeCamera.current?.end(completed);activeCamera.current=null;latest.current.onSoundFlight?.(null);if(completed)latest.current.onArrival?.();try{sessionStorage.setItem(SEEN,'seen')}catch{/* Storage can be unavailable in private contexts. */}latest.current.onComplete()}
  useEffect(()=>{
    const preference=matchMedia('(prefers-reduced-motion: reduce)'),change=()=>setReduced(preference.matches)
    preference.addEventListener('change',change)
    skip.current?.focus({preventScroll:true})
    const key=(event:KeyboardEvent)=>{if(event.key==='Escape'){event.preventDefault();finish()}else if(event.key==='Tab'){event.preventDefault();skip.current?.focus()}}
    window.addEventListener('keydown',key,true)
    return()=>{preference.removeEventListener('change',change);window.removeEventListener('keydown',key,true);activeCamera.current?.end(false);activeCamera.current=null}
  },[])
  useEffect(()=>{
    const el=canvas.current,container=root.current;if(!el||!container)return
    if(reduced){activeCamera.current?.end(false);activeCamera.current=null;latest.current.onSoundFlight?.(null)}
    const ctx=el.getContext('2d',{alpha:true})!,globe=document.createElement('canvas'),globeContext=globe.getContext('2d')!;let stopped=false,raf=0,baseGeography:OpeningGeography|undefined,geography:OpeningGeography|undefined,contextCity:City|undefined,start=performance.now(),last=0,travelAt:number|null=null,label=''
    
    const detailMask=new CampusDetailMask()
    let finePixels=false
    let width=0,height=0,cssWidth=0,cssHeight=0,step=1,pixels:ImageData,redrawStatic:(()=>void)|undefined,stars:{x:number;y:number;size:number;light:number}[]=[]
    const resize=()=>{
      const box=container.getBoundingClientRect(),factor=finePixels?1:Math.max(2,Math.ceil(box.width/640));cssWidth=box.width;cssHeight=box.height;step=factor
      const nextWidth=Math.max(1,Math.ceil(box.width/factor)),nextHeight=Math.max(1,Math.ceil(box.height/factor))
      if(nextWidth===width&&nextHeight===height)return
      width=nextWidth;height=nextHeight;el.width=globe.width=width;el.height=globe.height=height;pixels=ctx.createImageData(width,height);el.style.width=width*step+'px';el.style.height=height*step+'px';ctx.imageSmoothingEnabled=false
      stars=Array.from({length:110},(_,i)=>({x:((i*7919+1247)%10000)/10000*width,y:((i*3571+531)%10000)/10000*height,size:i%31===0?2:1,light:i%3}))
      if(reduced&&geography)redrawStatic?.()
    }
    const observer=new ResizeObserver(resize);observer.observe(container);resize()
    loadOpeningGeography().then(data=>{if(stopped)return;baseGeography=geography=data;start=performance.now()}).catch(()=>{if(!stopped)finish()})
    const draw=(now:number)=>{
      if(stopped||done.current)return
      raf=requestAnimationFrame(draw)
      if(now-last<1000/60-1)return
      last=now
      if(latest.current.failed&&!reduced){finish();return}
      if(baseGeography&&latest.current.city&&contextCity!==latest.current.city){contextCity=latest.current.city;geography=withCampusContext(baseGeography,contextCity)}
      const raw=geography?now-start:0
      let landing:OpeningLanding|null=null
      if(!reduced&&latest.current.camera){
        if(activeCamera.current&&activeCamera.current!==latest.current.camera){activeCamera.current.end(false);travelAt=null}
        activeCamera.current=latest.current.camera;landing=activeCamera.current.begin()
        if(!landing){finish();return}
      }
      if(!reduced&&!landing&&raw>ORBIT+15000){finish();return}
      if(raw>=ORBIT&&landing&&geography&&travelAt===null)travelAt=now
      const travel=reduced?0:travelAt===null?0:Math.max(0,now-travelAt),zoom=ease(travel/FLIGHT)
      const elapsed=Math.min(raw,ORBIT)+travel,t=clamp(elapsed/DURATION),rotation=reduced?.62:ease(Math.min(raw,ORBIT)/ORBIT)
      const target=landing?.target??OVAL,coefficients=landing?.metersPerDegree??[85395,111034]
      const lon=(30+(target[0]-30)*rotation)*radians,lat=(12+(target[1]-12)*rotation)*radians
      const base=Math.min(cssWidth*.31,cssHeight*.29),startMpp=EARTH_RADIUS/base
      const mpp=Math.exp(Math.log(startMpp)+(Math.log(landing?.metersPerPixel??.38)-Math.log(startMpp))*zoom)
      if(!reduced&&travelAt!==null)latest.current.onSoundFlight?.(clamp(travel/FLIGHT))
      if(!finePixels&&mpp<100){finePixels=true;resize()}
      const anchor:LonLat=[.5+((landing?.anchor[0]??.5)-.5)*zoom,.40+((landing?.anchor[1]??.40)-.40)*zoom]
      const radius=EARTH_RADIUS/mpp/step,cx=anchor[0]*cssWidth/step,cy=anchor[1]*cssHeight/step
      ctx.clearRect(0,0,width,height);ctx.fillStyle='#0b1e29';ctx.fillRect(0,0,width,height)
      for(const star of stars){ctx.fillStyle=['#324d59','#64808a','#a3b2aa'][star.light];ctx.fillRect(Math.round(star.x),Math.round(star.y),star.size,star.size)}
      // Two narrow, stepped atmosphere bands. Canvas is displayed at an integer
      // pixel scale; no full-resolution gradients or antialiased asset upscaling.
      if(radius<Math.hypot(width,height)){
        for(const [extra,color] of [[3,'#244452'],[1,'#497986']] as const){
          ctx.fillStyle=color;const r=radius+extra
          for(let y=Math.max(0,Math.ceil(cy-r));y<Math.min(height,Math.ceil(cy+r));y++){
            const half=Math.sqrt(Math.max(0,r*r-(y-cy)*(y-cy))),left=Math.max(0,Math.ceil(cx-half)),right=Math.min(width,Math.floor(cx+half)+1)
            if(right>left)ctx.fillRect(left,y,right-left,1)
          }
        }
      }
      const flatten=ease(Math.log(2500/mpp)/Math.log(8))
      if(flatten===1){ctx.fillStyle='#718963';ctx.fillRect(0,0,width,height)}else{
      const data=pixels.data;data.fill(0)
      const cosLon=Math.cos(lon),sinLon=Math.sin(lon),cosLat=Math.cos(lat),sinLat=Math.sin(lat)
      const minX=Math.max(0,Math.floor(cx-radius)),maxX=Math.min(width,Math.ceil(cx+radius)),minY=Math.max(0,Math.floor(cy-radius)),maxY=Math.min(height,Math.ceil(cy+radius))
      for(let y=minY;y<maxY;y++)for(let x=minX;x<maxX;x++){
        const u=(x-cx)/radius,v=(cy-y)/radius,square=u*u+v*v;if(square>1)continue
        const z=Math.sqrt(1-square),wx=-u*sinLon-v*sinLat*cosLon+z*cosLat*cosLon,wy=u*cosLon-v*sinLat*sinLon+z*cosLat*sinLon,wz=v*cosLat+z*sinLat
        const gx=((Math.floor((Math.atan2(wy,wx)/Math.PI+1)*512)%1024)+1024)%1024,gy=Math.max(0,Math.min(511,Math.floor((.5-Math.asin(Math.max(-1,Math.min(1,wz)))/Math.PI)*512)))
        const source=(gy*1024+gx)*4,texture=geography?.land,land=!!texture&&texture[source+3]>127
        const illumination=Math.max(.12,-u*.44+v*.31+z*.84),shade=Math.round(illumination*5)/5
        const i=(y*width+x)*4
        data[i]=Math.round((land?texture![source]:53)*(.32+shade*.68)*(1-flatten)+(land?113:71)*flatten)
        data[i+1]=Math.round((land?texture![source+1]:110)*(.38+shade*.62)*(1-flatten)+(land?137:123)*flatten)
        data[i+2]=Math.round((land?texture![source+2]:131)*(.44+shade*.56)*(1-flatten)+(land?99:136)*flatten);data[i+3]=255
      }
      // Composite the sphere without clearing the starfield outside its disc.
      globeContext.putImageData(pixels,0,0);ctx.drawImage(globe,0,0)}
      if(geography&&rotation===1){
        const project=geographicProjector(target,coefficients,mpp,[cx,cy],step)
        paintRegion(ctx,geography.features,project,mpp,step,geography.local,geography)
        // The same mapped geometry continues beneath the live world. Reveal its
        // finer detail through a broad geographic blend, never a cut-out rectangle.
        if(landing&&activeCamera.current&&mpp<70){
          const bounds=activeCamera.current.pose(mpp,anchor)
          detailMask.draw(ctx,bounds,mpp,step,clamp(travel/FLIGHT));el.dataset.campusBounds=JSON.stringify(bounds)
        }
        const mark=(point:LonLat,text:string)=>{
          const [x,y]=project(point);if(x<0||y<0||x>width||y>height)return
          ctx.font='600 9px "Pixelify Sans"';ctx.textAlign='center';ctx.textBaseline='middle';ctx.lineWidth=3;ctx.strokeStyle='#334e3d';ctx.fillStyle='#efe0b0';ctx.strokeText(text,Math.round(x),Math.round(y));ctx.fillText(text,Math.round(x),Math.round(y))
        }
        if(mpp<3000&&mpp>180)mark([-82.55,40.42],'OHIO')
        if(mpp<180&&mpp>8)mark([-82.9988,39.9623],'COLUMBUS')
        if(mpp>4){ctx.fillStyle='#eed18c';ctx.fillRect(Math.round(cx)-1,Math.round(cy)-1,3,3);ctx.strokeStyle='#eed18c';ctx.lineWidth=1;ctx.strokeRect(Math.round(cx)-4,Math.round(cy)-4,8,8)}
      }
      const next=reduced?'Earth':travelAt===null?(raw>ORBIT+1500?'Preparing campus':'Earth'):mpp>3000?'North America':mpp>180?'Ohio':mpp>8?'Columbus':mpp>1.5?'Ohio State campus':'The Oval'
      if(next!==label){label=next;setPhase(next)}
      container.style.setProperty('--opening-brand-opacity',String(1-ease(travel/950)))
      if(!reduced&&travel>=FLIGHT+350&&landing){finish(true);return}
      if(reduced&&geography){cancelAnimationFrame(raf);raf=0}
      el.dataset.metersPerPixel=mpp.toFixed(8);el.dataset.phase=label;el.dataset.progress=String(Math.floor(t*100))
    }
    redrawStatic=()=>{cancelAnimationFrame(raf);last=0;raf=requestAnimationFrame(draw)}
    raf=requestAnimationFrame(draw)
    return()=>{stopped=true;cancelAnimationFrame(raf);observer.disconnect();latest.current.onSoundFlight?.(null)}
  },[reduced])
  return <section ref={root} className="campus-opening" role="dialog" aria-modal="true" aria-label="Welcome to Last Warning">
    <canvas ref={canvas} aria-hidden="true"/>
    <button ref={skip} className="opening-skip" onClick={()=>finish()}>{reduced?'Enter campus':'Skip opening'}<PixelIcon name="chevron-right" size={14}/></button>
    <div className="opening-brand"><PixelIcon name="beacon" size={28}/><h1>Last Warning</h1><p>Ohio State · Columbus, Ohio</p></div>
    <div className="opening-location" role="status"><span/><p>{phase}</p></div>
    <span className="opening-attribution">Natural Earth · <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer" tabIndex={-1}>© OpenStreetMap contributors</a></span>
  </section>
}
