import {useCallback, useEffect, useRef, useState} from 'react'
import {CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis} from 'recharts'
import {api, clock, payload} from './api'
import {CityMap, PixelComparison, Legend, residentAppearance, stateColors, stateNames} from './CityMap'
import NeuralPanel from './NeuralPanel'
import {PixelIcon, ResidentPortrait} from './pixel-ui/PixelIcon'
import {TownTransport, townClock} from './pixel-ui/TownTransport'
import {CampusTravel} from './pixel-ui/CampusTravel'
import {ResidentLife, activityLabel, roleLabel} from './pixel-ui/ResidentLife'
import {CampusOpening,shouldShowOpening} from './pixel-ui/CampusOpening'
import type {OpeningCamera} from './pixel-world/OpeningCamera'
import {SourcesPanel} from './pixel-ui/SourcesPanel'
import {useWorldAudio} from './audio/useWorldAudio'
import type {AgentStatus, Analysis, CampusDayType, City, Comparison, DecisionMode, DisasterType, Frame, Metrics, Recording, ResidentDetails, Run, RunJob, Scenario, Stimulus, TownDay, Warning} from './types'

type Drawer = 'scenario'|'warning'|'neural'|'history'|'method'|'outcomes'|'transit'
type Pair = {runs:[Run,Run]; recordings:[Recording,Recording]; comparison:Comparison}
const disasters = {
  flood:{name:'Flash flood',label:'Flood',icon:'flood' as const,origin:[19,4] as [number,number],description:'River overflow and rising water'},
  wildfire:{name:'Wildfire',label:'Fire',icon:'fire' as const,origin:[6,12] as [number,number],description:'Wind-driven fire and road closures'},
  tornado:{name:'Tornado',label:'Tornado',icon:'tornado' as const,origin:[3,35] as [number,number],description:'Moving storm and debris'},
  blizzard:{name:'Blizzard',label:'Blizzard',icon:'snow' as const,origin:[20,20] as [number,number],description:'Four hours of snow, wind and low visibility'},
  hailstorm:{name:'Hailstorm',label:'Hail',icon:'hail' as const,origin:[8,17] as [number,number],description:'Hail exposure and indoor shelter'},
  thunderstorm:{name:'Severe thunderstorm',label:'Storm',icon:'storm' as const,origin:[7,17] as [number,number],description:'Destructive winds, hail and lightning'},
  public_safety:{name:'Major public safety threat',label:'Safety',icon:'zone' as const,origin:[29,22] as [number,number],description:'An abstract restricted area and protective instructions'},
}
const presetId = (type:DisasterType, actionable:boolean, campus=false) => campus?`campus-${actionable?'actionable':'generic'}-${type}`:`${actionable?'actionable':'generic'}${type==='flood'?'':`-${type}`}`
const isPreset = (id:string) => id.startsWith('campus-')||['generic','actionable','generic-wildfire','actionable-wildfire','generic-tornado','actionable-tornado'].includes(id)
const assumptions = [['delivery_reach_probability','Delivery reach'],['notice_probability','Notice probability'],
  ['action_probability','Action probability'],['social_share_probability','Social sharing']] as const
const actionLabels = {WAIT:'Wait',PREPARE:'Prepare',SHARE:'Share the warning',EVACUATE:'Evacuate',CONTINUE_ROUTINE:'Continue routine',SHELTER:'Seek indoor shelter',SHELTER_IN_PLACE:'Shelter in place',AVOID_AREA:'Avoid the restricted area',REUNITE:'Stay with family',SEEK_INDOOR_SHELTER:'Seek indoor shelter',POSTPONE_TRAVEL:'Postpone travel',EVACUATE_AREA:'Leave the affected area',STAY_WITH_GROUP:'Stay with household'}

function OutcomeChart({recording,alternative,index}: {recording:Recording;alternative?:Recording;index:number}) {
  const data=recording.frames.map((f,i)=>({time:f.time,sheltered:f.metrics.evacuated,alternative:alternative?.frames[i]?.metrics.evacuated}))
  return <div className="outcome-chart"><div className="section-label"><h3>Residents sheltered</h3><span>{alternative?'Baseline / Alternative':'Over time'}</span></div>
    <ResponsiveContainer width="100%" height={145}><LineChart data={data} margin={{top:8,right:8,left:-24,bottom:0}}>
      <CartesianGrid stroke="#e8edef" vertical={false}/><XAxis dataKey="time" tickFormatter={clock} tick={{fill:'#596f7c',fontSize:10}} minTickGap={40} axisLine={false} tickLine={false}/>
      <YAxis tick={{fill:'#596f7c',fontSize:10}} allowDecimals={false} axisLine={false} tickLine={false}/>
      <Tooltip labelFormatter={v=>clock(Number(v))} contentStyle={{background:'#f1edda',border:'2px solid #697c59',borderRadius:0,fontSize:12}}/>
      <ReferenceLine x={recording.frames[index]?.time} stroke="#9cb2bd" strokeDasharray="3 4"/>
      <Line type="stepAfter" dataKey="sheltered" name={alternative?'Baseline':'Sheltered'} stroke="#48674b" strokeWidth={2} dot={false} activeDot={false} isAnimationActive={false}/>
      {alternative&&<Line type="stepAfter" dataKey="alternative" name="Alternative" stroke="#ad6748" strokeWidth={2} dot={false} activeDot={false} isAnimationActive={false}/>}
    </LineChart></ResponsiveContainer></div>
}

function OutcomeNumbers({metrics,baseline}: {metrics:Metrics;baseline?:Metrics}) {
  return <div className="outcome-numbers">{([['evacuated','Sheltered'],['exposed','Ever exposed'],['stranded','Stranded'],['warning_noticed','Alert noticed']] as const).map(([key,label])=>{
    const delta=baseline?metrics[key]-baseline[key]:null
    return <div key={key}><span>{label}</span><strong className={key==='exposed'?'number-danger':''}>{metrics[key].toLocaleString()}</strong>
      {delta!==null&&<small>{delta>0?'+':''}{delta} vs baseline</small>}</div>
  })}</div>
}

function Timeline({frame,length,index,setIndex,playing,setPlaying,speed,setSpeed,tickSeconds}: {
  frame?:Frame;length:number;index:number;setIndex:(n:number)=>void;playing:boolean;setPlaying:(b:boolean)=>void;
  speed:number;setSpeed:(n:number)=>void;tickSeconds:number}) {
  const active=length>0
  const seek=(n:number)=>{setPlaying(false);setIndex(Math.max(0,Math.min(length-1,n)))}
  return <div className="timeline-dock"><div className="transport">
    <button aria-label="Restart playback" title="Restart playback" disabled={!active} onClick={()=>seek(0)}><PixelIcon name="restart" size={16}/></button>
    <button aria-label="Step backward" title="Previous frame" disabled={!active||index===0} onClick={()=>seek(index-1)}><PixelIcon name="step-back" size={16}/></button>
    <button className="transport-play" aria-label={playing?'Pause playback':'Play playback'} title="Play / pause · Space" disabled={!active} onClick={()=>{if(index>=length-1)setIndex(0);setPlaying(!playing)}}><PixelIcon name={playing?'pause':'play'} size={18}/></button>
    <button aria-label="Step forward" title="Next frame" disabled={!active||index>=length-1} onClick={()=>seek(index+1)}><PixelIcon name="step-next" size={16}/></button>
  </div><span className="time-current">{clock(frame?.time??0)}</span><input aria-label="Timeline position" type="range" min={0} max={Math.max(0,length-1)} value={index} disabled={!active} onChange={e=>seek(Number(e.target.value))}/>
    <span className="time-end">{clock(Math.max(0,length-1)*tickSeconds)}</span><select aria-label="Playback speed" value={speed} onChange={e=>setSpeed(Number(e.target.value))}>{[1,2,4,8,16].map(n=><option key={n} value={n}>{n}×</option>)}</select></div>
}

export default function App() {
  const [opening,setOpening]=useState(shouldShowOpening),[openingCamera,setOpeningCamera]=useState<OpeningCamera|null>(null)
  const connectOpeningCamera=useCallback((camera:OpeningCamera|null)=>setOpeningCamera(camera),[])
  const finishOpening=useCallback(()=>{setOpening(false);requestAnimationFrame(()=>(document.querySelector<HTMLElement>('.pixel-world-canvas')??document.getElementById('simulator'))?.focus({preventScroll:true}))},[])
  const [scenario,setScenario]=useState<Scenario|null>(null)
  const [warnings,setWarnings]=useState<Warning[]>([]),[drafts,setDrafts]=useState<Record<string,Warning>>({}),[warningId,setWarningId]=useState('generic')
  const [recordedWarning,setRecordedWarning]=useState<Warning|null>(null)
  const [runs,setRuns]=useState<Run[]>([]),[comparisons,setComparisons]=useState<Comparison[]>([])
  const [analyses,setAnalyses]=useState<Analysis[]>([]),[stimuli,setStimuli]=useState<Stimulus[]>([])
  const [current,setCurrent]=useState<Run|null>(null),[recording,setRecording]=useState<Recording|null>(null)
  const [preview,setPreview]=useState<{city:City;frame:Frame}|null>(null)
  const [townResponse,setTownResponse]=useState<{key:string;day:TownDay}|null>(null),[townIndex,setTownIndex]=useState(96),[townCycles,setTownCycles]=useState(0)
  const [townPlaying,setTownPlaying]=useState(()=>!window.matchMedia('(prefers-reduced-motion: reduce)').matches),[townSpeed,setTownSpeed]=useState(1)
  const townScenario=useRef<Scenario|null>(null),townResumeWanted=useRef(!window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  const townIdentity=useRef(''),townWarningId=useRef('generic')
  const [baseline,setBaseline]=useState<Run|null>(null),[pair,setPair]=useState<Pair|null>(null),[showPair,setShowPair]=useState(false)
  const [index,setIndex]=useState(0),[playing,setPlaying]=useState(false),[speed,setSpeed]=useState(4)
  const [selectedAgent,setSelectedAgent]=useState<number|null>(null)
  const [cameraTarget,setCameraTarget]=useState<{position:[number,number];serial:number}|null>(null)
  const inspectorRef=useRef<HTMLElement>(null)
  const [cameraInsets,setCameraInsets]=useState<{right:number}|undefined>()
  useEffect(()=>{
    const element=inspectorRef.current
    if(!element){setCameraInsets(undefined);return}
    const measure=()=>setCameraInsets(window.innerWidth>700?{right:Math.ceil(window.innerWidth-element.getBoundingClientRect().left+16)}:undefined)
    const observer=new ResizeObserver(measure);observer.observe(element);window.addEventListener('resize',measure);measure()
    return()=>{observer.disconnect();window.removeEventListener('resize',measure)}
  },[selectedAgent])
  const [followSelected,setFollowSelected]=useState(false),[job,setJob]=useState<RunJob|null>(null)
  const [pendingRequest,setPendingRequest]=useState<string|null>(null)
  const [placingHazard,setPlacingHazard]=useState(false),[residentDetailsResponse,setResidentDetailsResponse]=useState<{runId:string;value:ResidentDetails}|null>(null)
  const [routeSelection,setRouteSelection]=useState<{runId:string;residentId:number}|null>(null)
  const [drawer,setDrawer]=useState<Drawer|null>(null),[deleteConfirm,setDeleteConfirm]=useState(false)
  const [includeNeural,setIncludeNeural]=useState(true),[coupling,setCoupling]=useState(false),[strength,setStrength]=useState(.2)
  const [agentStatus,setAgentStatus]=useState<AgentStatus|null>(null)
  const [simulationVersion,setSimulationVersion]=useState<string|null>(null),[campusSimulationVersion,setCampusSimulationVersion]=useState<string|null>(null)
  const [campusOrigins,setCampusOrigins]=useState<Partial<Record<DisasterType,[number,number]>>>({})
  const [fingerprint,setFingerprint]=useState<{text:string;hash:string}|null>(null),[busy,setBusy]=useState(''),[loading,setLoading]=useState(true)
  const [notice,setNotice]=useState<{message:string;error:boolean}|null>(null)
  const [loadError,setLoadError]=useState(false)
  const dialogRef=useRef<HTMLDialogElement>(null),menuRef=useRef<HTMLDetailsElement>(null),hazardMenuRef=useRef<HTMLDetailsElement>(null),loadSeq=useRef(0),resumedJob=useRef(false)
  const returnFocus=useRef<HTMLElement|null>(null)
  const initialized=useRef(false)
  const warning=recordedWarning??drafts[warningId]??warnings.find(w=>w.id===warningId)??null
  const textHash=fingerprint?.text===warning?.text?fingerprint?.hash??'':''
  const disasterType=scenario?.disaster_type??'flood'
  const decisionMode=scenario?.decision_mode??'bedrock'
  const report=useCallback((message:string,error=false)=>setNotice({message,error}),[])
  const refresh=useCallback(async()=>{
    const options={signal:AbortSignal.timeout(15000)}
    const [s,w,r,a,st,c,health]=await Promise.all([api<Scenario[]>('/scenarios',options),api<Warning[]>('/warnings',options),api<Run[]>('/runs',options),api<Analysis[]>('/neural/analyses',options),api<Stimulus[]>('/stimuli',options),api<Comparison[]>('/comparisons',options),api<{simulation_version:string;campus_simulation_version?:string;campus_default_origins?:Partial<Record<DisasterType,[number,number]>>}>('/health',options)])
    const initial=s.find(x=>x.id==='osu-campus')??s[0],initialType=initial?.disaster_type??'thunderstorm'
    setScenario(old=>old??({...initial,name:'Ohio State · Campus & neighborhood',disaster_type:initialType,hazard_origin:health.campus_default_origins?.[initialType]??initial?.hazard_origin,decision_mode:'bedrock',layout:'campus',town_life:true,town_start_tick:140,town_start_minutes:700} as Scenario))
    setCampusOrigins(health.campus_default_origins??{})
    setWarnings(w);setRuns(r);setAnalyses(a);setStimuli(st);setComparisons(c)
    setSimulationVersion(health.simulation_version);setCampusSimulationVersion(health.campus_simulation_version??null)
    if(!initialized.current){const first=s.find(x=>x.id==='osu-campus')??s[0];setWarningId(presetId(first?.disaster_type??'thunderstorm',false,first?.layout==='campus'));initialized.current=true}
    else setWarningId(id=>w.some(x=>x.id===id)?id:w[0]?.id??'')
  },[])
  const refreshAgentStatus=useCallback(async()=>{
    const status=await api<AgentStatus>('/agents/status')
    setAgentStatus(status)
    return status
  },[])
  useEffect(()=>{void refresh().catch(()=>{setLoadError(true);report('Connection to the campus was interrupted. Reconnect to continue.',true)}).finally(()=>setLoading(false))},[refresh,report])
  useEffect(()=>{
    if(!scenario||scenario.town_life)return
    let cancelled=false
    const timer=setTimeout(()=>{void api<{city:City;frame:Frame}>('/scenarios/preview',{method:'POST',body:payload(scenario),signal:AbortSignal.timeout(15000)}).then(r=>{if(!cancelled){setPreview(r);setLoadError(false)}}).catch(e=>{if(!cancelled){setLoadError(true);report(e.message,true)}})},180)
    return()=>{cancelled=true;clearTimeout(timer)}
  },[scenario,report])
  const townKey=scenario?.town_life?JSON.stringify([scenario.layout??'organic',scenario.population,scenario.seed,scenario.disaster_type,scenario.campus_day_type??'teaching',scenario.transit_enabled??true]):''
  const townDay=townResponse?.key===townKey?townResponse.day:null
  useEffect(()=>{if(!recording&&scenario?.town_life){townScenario.current=scenario;townWarningId.current=warningId}},[scenario,warningId,recording])
  useEffect(()=>{
    if(!scenario||!townKey||recording)return
    if(townResponse?.key===townKey)return
    let cancelled=false
    const controller=new AbortController()
    void api<TownDay>('/town-life/preview',{method:'POST',body:payload({...scenario,town_start_tick:0}),signal:controller.signal}).then(day=>{
      if(!cancelled){
        const identity=JSON.stringify([scenario.layout??'organic',scenario.population,scenario.seed,scenario.campus_day_type??'teaching',scenario.transit_enabled??true])
        const changed=townIdentity.current!==identity;townIdentity.current=identity
        setTownResponse({key:townKey,day});setTownIndex(value=>Math.min(changed?Math.floor((scenario.town_start_minutes??480)/day.minutes_per_tick):value,day.frames.length-1))
        if(changed)setTownCycles(0)
        setLoadError(false)
      }
    }).catch(error=>{if(!cancelled){setLoadError(true);report((error as Error).message,true)}})
    return()=>{cancelled=true;controller.abort()}
  },[townKey,!!recording,report])
  useEffect(()=>{
    let live=true
    if(warning){const text=warning.text;void crypto.subtle.digest('SHA-256',new TextEncoder().encode(text)).then(value=>{if(live)setFingerprint({text,hash:Array.from(new Uint8Array(value),b=>b.toString(16).padStart(2,'0')).join('')})})}
    return()=>{live=false}
  },[warning?.text])
  useEffect(()=>{const dialog=dialogRef.current;if(drawer){if(!dialog?.open)dialog?.showModal();requestAnimationFrame(()=>dialog?.querySelector<HTMLButtonElement>('.drawer-header button')?.focus())}else if(dialog?.open)dialog.close()},[drawer])
  useEffect(()=>{const outside=(event:PointerEvent)=>{for(const menu of [menuRef.current,hazardMenuRef.current])if(menu?.open&&!menu.contains(event.target as Node))menu.open=false}
    const escape=(event:KeyboardEvent)=>{if(event.key==='Escape'){setPlacingHazard(false);for(const menu of [menuRef.current,hazardMenuRef.current])if(menu?.open){menu.open=false;menu.querySelector('summary')?.focus()}}}
    document.addEventListener('pointerdown',outside);document.addEventListener('keydown',escape)
    return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',escape)}
  },[])
  useEffect(()=>{if(!notice||notice.error)return;const timer=setTimeout(()=>setNotice(null),5500);return()=>clearTimeout(timer)},[notice])
  const activeRecord=showPair&&pair?pair.recordings[1]:recording
  const livingTown=!activeRecord&&scenario?.town_life===true
  const townFrame=townDay?.frames[Math.min(townIndex,townDay.frames.length-1)]
  const frame=activeRecord?.frames[Math.min(index,activeRecord.frames.length-1)]??(livingTown?townFrame:preview?.frame)
  const city=activeRecord?.city??(livingTown?townDay?.city:preview?.city)
  const frameCount=activeRecord?.frames.length??0
  useEffect(()=>{
    if(opening||!livingTown||!townDay||!townPlaying||drawer||busy||job?.status==='running'||job?.status==='queued'||pendingRequest)return
    const timer=setTimeout(()=>{if(townIndex>=townDay.frames.length-1){setTownCycles(value=>value+1);setTownIndex(0)}else setTownIndex(townIndex+1)},(scenario?.layout==='campus'?5000:900)/townSpeed)
    return()=>clearTimeout(timer)
  },[opening,livingTown,townDay,townPlaying,townIndex,townSpeed,drawer,busy,job?.status,pendingRequest])
  useEffect(()=>{
    if(opening||!playing||!frameCount)return
    if(index>=frameCount-1){setPlaying(false);return}
    const timer=setTimeout(()=>setIndex(n=>n+1),1000/speed)
    return()=>clearTimeout(timer)
  },[opening,playing,index,frameCount,speed])
  useEffect(()=>{
    const handleKey=(event:KeyboardEvent)=>{
      if(opening||event.key!==' '||drawer||event.repeat||(event.target as HTMLElement).closest('input,textarea,select,button,summary,[contenteditable="true"]'))return
      if(livingTown&&townDay){event.preventDefault();setTownPlaying(value=>{townResumeWanted.current=!value;return !value});return}
      if(!frameCount)return
      event.preventDefault();if(index>=frameCount-1)setIndex(0);setPlaying(value=>!value)
    }
    document.addEventListener('keydown',handleKey)
    return()=>document.removeEventListener('keydown',handleKey)
  },[opening,drawer,frameCount,index,livingTown,townDay])
  const exactAnalysis=analyses.find(a=>a.warning_id===warningId&&a.provenance==='REAL_TRIBE'&&a.model_id==='facebook/tribev2-mini'&&a.stimulus_hash===textHash&&a.warning_text_hash===textHash&&a.sampling_information.stimulus_protocol==='controlled_word_reading_v1'&&a.sampling_information.words_per_second===2.5)
  const viewedAnalysis=current?.neural_analysis_id?analyses.find(a=>a.id===current.neural_analysis_id):null
  const linkedAnalysis=recording&&!baseline?viewedAnalysis:exactAnalysis
  const visibleWarnings=warnings.filter(w=>!isPreset(w.id)||[presetId(disasterType,false,scenario?.layout==='campus'),presetId(disasterType,true,scenario?.layout==='campus')].includes(w.id))
  function editWarning(changes:Partial<Warning>){if(warning){setDrafts(old=>({...old,[warningId]:{...warning,...changes}}));if(!baseline)resetView()}}
  function resetView(){setCameraTarget(null);setCurrent(null);setRecording(null);setRecordedWarning(null);setPair(null);setShowPair(false);setBaseline(null);setIndex(0);setPlaying(false);setSelectedAgent(null);setFollowSelected(false);setPlacingHazard(false)}
  function returnToTown(){resetView();closeDrawer();setScenario(townScenario.current??({...scenario,layout:'campus',town_life:true,town_start_tick:140,town_start_minutes:700} as Scenario));setWarningId(townWarningId.current);setTownPlaying(townResumeWanted.current)}
  function switchWarning(id:string){setWarningId(id);setDeleteConfirm(false);setCoupling(false);if(!baseline)resetView()}
  function switchDisaster(type:DisasterType){if(!scenario)return;resetView();const campus=scenario.layout==='campus';setScenario({...scenario,disaster_type:type,hazard_origin:city?.default_origins?.[type]??disasters[type].origin,hazard_spread:1,...(campus?{duration_ticks:120,tick_seconds:type==='blizzard'?120:['hailstorm','thunderstorm'].includes(type)?30:type==='public_safety'?10:5}:{})});setWarningId(presetId(type,false,campus));setCoupling(false)}
  function openDrawer(value:Drawer){if(value==='warning')setCameraTarget(null);returnFocus.current=menuRef.current?.contains(document.activeElement)?menuRef.current.querySelector('summary'):document.activeElement as HTMLElement;setPlaying(false);setDrawer(value);if(menuRef.current)menuRef.current.open=false;if(hazardMenuRef.current)hazardMenuRef.current.open=false
    if(value==='scenario'||value==='method')void refreshAgentStatus().catch(()=>setAgentStatus(null))
  }
  function closeDrawer(){setDrawer(null);requestAnimationFrame(()=>{if(returnFocus.current?.isConnected)returnFocus.current.focus();else document.querySelector<HTMLButtonElement>('.toolbelt>button')?.focus()})}
  async function reconnectWorld(){
    setLoadError(false);setLoading(true);setScenario(null)
    try{await refresh();setNotice(null)}catch{setLoadError(true);report('Connection to the campus was interrupted. Reconnect to continue.',true)}finally{setLoading(false)}
  }
  async function persistWarning(source:Warning){
    const exists=warnings.some(w=>w.id===source.id)
    const saved=await api<Warning>(exists?`/warnings/${source.id}`:'/warnings',{method:exists?'PUT':'POST',body:payload(source)})
    setDrafts(old=>({...old,[saved.id]:saved}));setWarningId(saved.id);setRecordedWarning(null);return saved
  }
  async function displayCompletedRun(result:Run){
    const savedRecording=await api<Recording>(`/runs/${result.id}/frames`)
    setCameraTarget(null);setCurrent(result);setRecording(savedRecording);setIndex(0);setSelectedAgent(null);setFollowSelected(false)
    setScenario({...result.configuration,id:result.scenario_id,disaster_type:result.configuration.disaster_type??'flood',decision_mode:result.configuration.decision_mode??'rules'})
    setWarningId(result.warning_id);setRecordedWarning({...result.warning,id:result.warning_id})
    if(result.baseline_run_id){
      const [baselineRun,baselineRecording]=await Promise.all([api<Run>(`/runs/${result.baseline_run_id}`),api<Recording>(`/runs/${result.baseline_run_id}/frames`)])
      const c=await api<Comparison>('/comparisons',{method:'POST',body:JSON.stringify({baseline_run_id:baselineRun.id,alternative_run_id:result.id})})
      setPair({runs:[baselineRun,result],recordings:[baselineRecording,savedRecording],comparison:c});setShowPair(true);setBaseline(null)
      report('Both warnings share the same city and starting population.')
    }else{setPair(null);setShowPair(false);setBaseline(null)}
    await refresh();setPlaying(!window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  }
  async function monitorJob(id:string){
    let failures=0
    for(;;){
      let value:RunJob
      try{value=await api<RunJob>(`/run-jobs/${id}`,{signal:AbortSignal.timeout(12000)});failures=0}
      catch(error){
        failures++;if(failures>=5)throw new Error(`Connection interrupted. This run may still be active. Reconnect to check it before starting another run. ${(error as Error).message}`)
        setBusy('Reconnecting to the run');await new Promise(resolve=>setTimeout(resolve,1500));continue
      }
      setJob(value)
      if(value.status==='completed'){
        if(!value.run_id)throw new Error('The run completed without a recording. Open saved runs to check the result.')
        setBusy('Opening the recorded world')
        const result=await api<Run>(`/runs/${value.run_id}`)
        await displayCompletedRun(result);sessionStorage.removeItem('last-warning-active-job');setJob(null);return
      }
      if(['failed','cancelled','interrupted'].includes(value.status)){
        sessionStorage.removeItem('last-warning-active-job');setJob(null)
        if(value.status==='cancelled'){report('Run stopped. Completed model requests remain accounted for.');return}
        throw new Error(value.error?.detail??(value.status==='interrupted'?'The server stopped before the run finished. No partial result was applied.':'The run could not be completed.'))
      }
      setBusy(value.cancel_requested?'Stopping after the current request':value.stage==='neural'?'Computing the local Mini response':value.stage==='neural_queued'?'Waiting for local Mini':value.stage==='queued'?'Preparing the run':value.stage==='agent_decisions'?'Residents are making decisions':'Simulating the city')
      await new Promise(resolve=>setTimeout(resolve,900))
    }
  }
  async function cancelJob(){
    if(!job)return
    try{const value=await api<RunJob>(`/run-jobs/${job.id}/cancel`,{method:'POST'});setJob(value);setBusy('Stopping after the current request')}
    catch(error){report((error as Error).message,true)}
  }
  async function reconnectJob(){
    if(!job&&!pendingRequest)return
    setBusy('Reconnecting to the run')
    try{if(pendingRequest)await submitRunJob(pendingRequest);else if(job)await monitorJob(job.id)}catch(error){report((error as Error).message,true)}finally{setBusy('');void refreshAgentStatus().catch(()=>setAgentStatus(null))}
  }
  async function submitRunJob(body:string){
    setPendingRequest(body);sessionStorage.setItem('last-warning-pending-request',body)
    let value:RunJob
    try{value=await api<RunJob>('/run-jobs',{method:'POST',body,signal:AbortSignal.timeout(12000)})}
    catch(error){
      if(error instanceof TypeError||error instanceof DOMException)throw new Error('The run request could not be confirmed. Reconnect to check it safely; the same request will be reused.')
      setPendingRequest(null);sessionStorage.removeItem('last-warning-pending-request');throw error
    }
    setJob(value);sessionStorage.setItem('last-warning-active-job',value.id)
    setPendingRequest(null);sessionStorage.removeItem('last-warning-pending-request');closeDrawer()
    await monitorJob(value.id)
  }
  useEffect(()=>{
    if(loading||resumedJob.current)return
    resumedJob.current=true
    const id=sessionStorage.getItem('last-warning-active-job')
    const pending=sessionStorage.getItem('last-warning-pending-request')
    if(id){setJob({id,status:'running',stage:'queued',progress:{tick:0,total_ticks:scenario?.duration_ticks??0,decision_rounds_completed:0},run_id:null,analysis_id:null,error:null,cancel_requested:false,created_at:'',updated_at:''});setBusy('Reconnecting to the active run');void monitorJob(id).catch(error=>report((error as Error).message,true)).finally(()=>setBusy(''))}
    else if(pending){setPendingRequest(pending);setBusy('Confirming the active run');void submitRunJob(pending).catch(error=>report((error as Error).message,true)).finally(()=>setBusy(''))}
  },[loading])
  async function runWarning(){
    if(!scenario||!warning)return
    const runScenario=!baseline&&livingTown&&townFrame?{...scenario,town_start_tick:Math.floor((townFrame.world_clock_minutes??townFrame.tick*5)/5),...(scenario.layout==='campus'?{town_start_minutes:townFrame.world_clock_minutes}:{})}:scenario
    if(livingTown)townResumeWanted.current=townPlaying
    setNotice(null);setPlaying(false);setTownPlaying(false);setBusy('Saving warning');setScenario(runScenario)
    try{
      if(decisionMode==='bedrock'){
        setBusy('Checking Bedrock access')
        const status=await refreshAgentStatus()
        if(!status.available)throw new Error(status.error||'Bedrock is unavailable. Check AWS access in Scenario settings.')
        if(status.remaining_usd<=0)throw new Error('The Bedrock spending limit has been reached.')
      }
      const saved=await persistWarning(warning)
      if(!baseline)await api(`/scenarios/${runScenario.id}`,{method:'PUT',body:payload(runScenario)})
      setBusy(decisionMode==='bedrock'?'Running residents with Bedrock decisions':'Simulating residents and evacuation routes')
      await submitRunJob(JSON.stringify({scenario_id:runScenario.id,warning_id:saved.id,baseline_run_id:baseline?.id??null,neural_analysis_id:null,analyze_warning:includeNeural,coupling_strength:includeNeural&&coupling&&decisionMode==='rules'?strength:0,idempotency_key:crypto.randomUUID()}))
    }catch(e){report((e as Error).message,true)}finally{setBusy('');if(decisionMode==='bedrock')void refreshAgentStatus().catch(()=>setAgentStatus(null))}
  }
  function createAlternative(){
    if(!current)return
    if(current.simulation_version!==(current.configuration.layout==='campus'?campusSimulationVersion:simulationVersion)){resetView();setScenario({...current.configuration,id:current.scenario_id,disaster_type:current.configuration.disaster_type??'flood',decision_mode:current.configuration.decision_mode??'rules',...(current.configuration.layout==='campus'?{hazard_origin:campusOrigins[current.configuration.disaster_type]??current.configuration.hazard_origin}:{})});report('This recording uses an earlier simulation model. The current map and default event location are ready for a new run.');return}
    setBaseline(current);setScenario({...current.configuration,id:current.scenario_id,disaster_type:current.configuration.disaster_type??'flood',decision_mode:current.configuration.decision_mode??'rules'})
    const type=current.configuration.disaster_type??'flood'
    setWarningId(presetId(type,current.warning_id!==presetId(type,true,current.configuration.layout==='campus'),current.configuration.layout==='campus'))
    setRecordedWarning(null);setPlaying(false);setIndex(0);setShowPair(false);setCoupling(false)
  }
  async function loadRun(value:Run){
    const seq=++loadSeq.current;setBusy('Opening saved run');setPlaying(false)
    try{const r=await api<Recording>(`/runs/${value.id}/frames`);if(seq!==loadSeq.current)return
      setCameraTarget(null);setCurrent(value);setRecording(r);setPair(null);setShowPair(false);setBaseline(null);setIndex(0);setSelectedAgent(null)
      setScenario({...value.configuration,id:value.scenario_id,disaster_type:value.configuration.disaster_type??'flood',decision_mode:value.configuration.decision_mode??'rules'});setWarningId(value.warning_id);setRecordedWarning({...value.warning,id:value.warning_id});closeDrawer()
    }catch(e){report((e as Error).message,true)}finally{if(seq===loadSeq.current)setBusy('')}
  }
  async function loadComparison(c:Comparison){
    setBusy('Opening comparison');setPlaying(false)
    try{const [a,b,ar,br]=await Promise.all([api<Run>(`/runs/${c.baseline_run_id}`),api<Run>(`/runs/${c.alternative_run_id}`),api<Recording>(`/runs/${c.baseline_run_id}/frames`),api<Recording>(`/runs/${c.alternative_run_id}/frames`)])
      setCameraTarget(null);setPair({runs:[a,b],recordings:[ar,br],comparison:c});setShowPair(true);setCurrent(b);setRecording(br);setBaseline(null);setIndex(0);setSelectedAgent(null)
      setScenario({...b.configuration,id:b.scenario_id,disaster_type:b.configuration.disaster_type??'flood',decision_mode:b.configuration.decision_mode??'rules'});setWarningId(b.warning_id);setRecordedWarning({...b.warning,id:b.warning_id});closeDrawer()
    }catch(e){report((e as Error).message,true)}finally{setBusy('')}
  }
  async function addWarning(duplicate=false){
    if(!warning)return
    setBusy('Creating warning')
    try{const {id,created_at,...source}=warning;void id;void created_at
      const value=await api<Warning>('/warnings',{method:'POST',body:JSON.stringify({...source,name:duplicate?`${source.name} copy`:'Custom warning'})})
      await refresh();setWarningId(value.id);setDrafts(old=>({...old,[value.id]:value}));if(!baseline)resetView();else{setRecordedWarning(null);setShowPair(false);setPlaying(false);setIndex(0);setSelectedAgent(null)}setDrawer('warning');setDeleteConfirm(false)
    }catch(e){report((e as Error).message,true)}finally{setBusy('')}
  }
  async function deleteWarning(){
    if(!warning||!warnings.some(value=>value.id===warning.id))return
    setBusy('Deleting warning')
    try{await api(`/warnings/${warning.id}`,{method:'DELETE'});setDrafts(old=>{const next={...old};delete next[warning.id];return next});await refresh();setWarningId(presetId(disasterType,false,scenario?.layout==='campus'));setDeleteConfirm(false);resetView()}
    catch(e){report((e as Error).message,true)}finally{setBusy('')}
  }
  const selected=frame?.agents.find(a=>a[0]===selectedAgent)
  const selectedDecision=frame?.agent_decisions?.find(value=>value.id===selectedAgent)
  const agentPolicy=(showPair&&pair?pair.runs[1]:current)?.agent_policy
  const agentUsage=agentPolicy?.usage
  const viewedDecisionMode=current?(current.decision_mode??current.configuration.decision_mode??'rules'):decisionMode
  const liveType=(showPair&&pair?pair.runs[1]:current)?.configuration.disaster_type??disasterType
  useEffect(()=>setRouteSelection(null),[selectedAgent,current?.id])
  useEffect(()=>{
    setResidentDetailsResponse(null)
    if(selectedAgent===null||!current||!frame)return
    const runId=current.id
    let cancelled=false
    void api<ResidentDetails>(`/runs/${runId}/residents/${selectedAgent}?tick=${frame.tick}`).then(value=>{if(!cancelled)setResidentDetailsResponse({runId,value})}).catch(()=>{})
    return()=>{cancelled=true}
  },[selectedAgent,current?.id,frame?.tick])
  const residentDetails=residentDetailsResponse?.runId===current?.id&&residentDetailsResponse?.value.id===selectedAgent&&residentDetailsResponse?.value.tick===frame?.tick?residentDetailsResponse.value:null
  const canShowRoute=residentDetails?.route_source==='recorded_plan'&&!!residentDetails.route?.length
  const showRoute=!!routeSelection&&routeSelection.runId===current?.id&&routeSelection.residentId===selectedAgent
  const selectedRoute=showRoute&&canShowRoute?residentDetails.route:null
  const isBusy=!!busy||!!pendingRequest||job?.status==='queued'||job?.status==='running'
  const worldPlaying=!opening&&(livingTown?townPlaying&&!drawer&&!isBusy:playing)
  const worldFrameDuration=livingTown?(scenario?.layout==='campus'?5000:900)/townSpeed:1000/speed
  const profiles=activeRecord?.profiles??activeRecord?.initial_conditions?.agents??(livingTown?townDay?.profiles:undefined)??[]
  const selectedProfile=profiles.find(value=>value.id===selectedAgent)
  const selectedActivity=frame?.agent_activities?.find(value=>value.id===selectedAgent)
  const householdMembers=selectedProfile?.household_id?profiles.filter(value=>value.household_id===selectedProfile.household_id):[]
  const residentName=(id:number)=>profiles.find(value=>value.id===id)?.name??`Resident ${id+1}`
  const selectedName=selectedAgent===null?'':residentName(selectedAgent)
  const minuteOfDay=((frame?.world_clock_minutes??townIndex*5)%1440+1440)%1440
  const upcomingRoutine=selectedProfile?.routine?[...selectedProfile.routine.filter(value=>value.start_minute>minuteOfDay),...selectedProfile.routine.filter(value=>value.start_minute<=minuteOfDay)]:[]
  const nextRoutine=upcomingRoutine.find(value=>value.activity!==selectedActivity?.activity||value.place_id!==selectedActivity?.place_id)
  const profileById=new Map(profiles.map(profile=>[profile.id,profile]))
  const inspectionGroups=new Map<string,number[][]>()
  if(drawer==='outcomes')for(const resident of frame?.agents??[]){const p=profileById.get(resident[0]);const group=p?.household_type==='family'?'Local families':p?`${roleLabel(p)}s`:'Residents';inspectionGroups.set(group,[...(inspectionGroups.get(group)??[]),resident])}
  const activityById=new Map((frame?.agent_activities??[]).map(activity=>[activity.id,activity]))
  const homeCount=frame?.agent_activities?.filter(value=>value.inside&&value.place_id===profileById.get(value.id)?.home_place_id).length??0
  const awayCount=(frame?.agents.length??scenario?.population??0)-homeCount
  const audio=useWorldAudio({playing:worldPlaying,time:frame?.time??0,tick:frame?.tick,frameDurationMs:worldFrameDuration,runId:current?.id,disasterType:liveType,hazardActive:typeof frame?.hazard?.active==='boolean'?frame.hazard.active:!!frame?.active_hazard_cells?.length,lastThunderSeconds:typeof frame?.hazard?.last_thunder_seconds==='number'?frame.hazard.last_thunder_seconds:frame?.hazard?.last_thunder_seconds===null?null:undefined,warningTickSeconds:current?.configuration.layout==='campus'?(current.warning.broadcast_seconds??current.warning.broadcast_tick*5):(current?.warning.broadcast_tick??0)*(current?.configuration.tick_seconds??5)})
  useEffect(()=>{if(notice)audio.cue(notice.error?'error':'confirm')},[notice,audio.cue])
  const selectResident=useCallback((id:number|null)=>{setSelectedAgent(id);if(id!==null)audio.cue('select')},[audio.cue])
  const openingArrival=useCallback(()=>audio.cue('arrival'),[audio.cue])
  const wordCount=warning?.text.trim().split(/\s+/).filter(Boolean).length??0
  const hazardPhase=frame?.hazard?.phase,holdSeconds=Number(frame?.hazard?.shelter_hold_seconds_remaining??0)
  const hazardCaption=hazardPhase==='all_clear'?'All-clear':hazardPhase==='shelter_hold'?`Stay inside · ${Math.ceil(holdSeconds/60)} min`:hazardPhase==='approaching'?'Approaching':hazardPhase==='active'?'Event active':null
  const weatherReadout=!livingTown&&frame?.hazard?(liveType==='blizzard'?`${Math.round(Number(frame.hazard.wind_mph))} mph wind · ${Number(frame.hazard.visibility_miles).toFixed(2)} mi visibility`:['hailstorm','thunderstorm'].includes(liveType)?`${Math.round(Number(frame.hazard.wind_mph))} mph wind · ${Number(frame.hazard.hail_inches).toFixed(2)} in hail`:null):null
  const drawerTitles:Record<Drawer,string>={scenario:'World settings',warning:baseline?'Alternative warning':'Broadcast warning',neural:'TRIBE Mini',history:'Saved runs',method:'Sources & methods',outcomes:livingTown?'Residents':'Results',transit:'Shuttle & crossings'}

  const scenarioError=scenario?.layout==='campus'&&scenario.duration_ticks*scenario.tick_seconds<(disasterType==='blizzard'?10800:['hailstorm','thunderstorm'].includes(disasterType)?3600:0)?(disasterType==='blizzard'?'Blizzards need at least 3 simulated hours.':'Storm scenarios need at least 1 simulated hour, including the shelter hold.'):null
  const metrics=frame?.metrics
  const canRun=!loading&&!isBusy&&!scenarioError&&!!warning?.name.trim()&&!!warning?.text.trim()&&!!scenario&&(!livingTown||!!townFrame)&&(!includeNeural||wordCount<=200)
  const changeResident=(direction:number)=>{
    if(!frame?.agents.length)return
    const at=frame.agents.findIndex(value=>value[0]===selectedAgent)
    setSelectedAgent(frame.agents[(at+direction+frame.agents.length)%frame.agents.length][0])
  }
  const openCompare=()=>{
    if(pair){setShowPair(value=>!value);setIndex(0);setPlaying(false);setSelectedAgent(null)}
    else if(current&&!baseline){createAlternative();openDrawer('warning')}
    else if(baseline)openDrawer('warning')
    else report('Run a warning first, then compare it with a different message.')
  }

  return <><div className={`app-shell${livingTown?' living-town':''}${recording?' has-recording':''}${opening?' opening-active':''}`} inert={opening||undefined} onClickCapture={event=>{
    const control=(event.target as HTMLElement).closest('button,summary')
    if(!control||control.hasAttribute('disabled')||control.getAttribute('aria-label')==='Sound')return
    audio.cue('select')
  }}>
    <a href="#simulator" className="skip-link">Skip to city</a>
    <main id="simulator" className="game-world" tabIndex={-1} aria-label="Last Warning campus simulator">
      <div className={`city-viewports ${showPair&&pair?'paired':''}`}>
        {city&&frame?(showPair&&pair?<PixelComparison city={pair.recordings[0].city}
          frame={pair.recordings[0].frames[Math.min(index,pair.recordings[0].frames.length-1)]}
          comparisonFrame={pair.recordings[1].frames[Math.min(index,pair.recordings[1].frames.length-1)]}
          labels={[`Baseline · ${pair.runs[0].warning.name}`,`Alternative · ${pair.runs[1].warning.name}`]} selected={selectedAgent} onSelect={selectResident} cameraTarget={cameraTarget} cameraInsets={cameraInsets} onOpeningCamera={connectOpeningCamera}
          artSeed={pair.runs[0].art_seed??pair.runs[0].seed} comparisonArtSeed={pair.runs[1].art_seed??pair.runs[1].seed}
          profiles={profiles} selectedRoute={selectedRoute} routeAccessible={selectedRoute?residentDetails?.route_accessible:null}
          followSelected={followSelected} onFollowChange={setFollowSelected} hazardType={liveType} playing={playing} frameDurationMs={1000/speed}/>
          :<CityMap city={city} frame={frame} selected={selectedAgent} onSelect={selectResident} cameraTarget={cameraTarget} cameraInsets={cameraInsets} onOpeningCamera={connectOpeningCamera}
            artSeed={current?.art_seed??scenario?.seed} placementMode={placingHazard} hazardOrigin={scenario?.hazard_origin}
            profiles={profiles} selectedRoute={selectedRoute} routeAccessible={selectedRoute?residentDetails?.route_accessible:null}
            onPlaceOrigin={point=>{if(!scenario||isBusy)return;resetView();setScenario({...scenario,hazard_origin:point});report('Disaster origin placed. Changes apply to the next run.')}}
            followSelected={followSelected} onFollowChange={setFollowSelected} hazardType={liveType} playing={worldPlaying} frameDurationMs={worldFrameDuration}/>)
          :<div className="world-loading" role="status"><PixelIcon name="beacon" size={40}/><span>{loadError?'Campus is unavailable':loading?'Opening campus':'Building the campus day'}</span>{loadError?<button className="secondary" onClick={()=>void reconnectWorld()}>Reconnect to city</button>:<i/>}</div>}
      </div>
    </main>

    <header className="game-header">
      <a className="brand pixel-frame" href="#simulator" aria-label="Last Warning simulator"><span className="brand-symbol"><PixelIcon name="beacon" size={28}/></span><span>Last Warning<small>{(city?.layout??scenario?.layout)==='campus'?<>Ohio State<span className="brand-region"> · Columbus</span></>:'Riverside'}</small></span></a>
      <div className="world-counters pixel-frame" aria-label={livingTown?'Town population':showPair?'Alternative warning outcomes':'Current outcomes'}>
        {showPair&&<span className="counter-scope">Alternative</span>}
        <button title="View population and outcomes" aria-label={`${metrics?.population??scenario?.population??'Unknown'} residents${showPair?' in the alternative warning':''}`} onClick={()=>openDrawer('outcomes')}><PixelIcon name="people" size={20}/><span><strong>{metrics?.population??scenario?.population??'—'}</strong><small>Residents</small></span></button>
        <button title={livingTown?'Residents at home':'View sheltered residents'} aria-label={livingTown?`${frame?homeCount:'Unknown'} residents at home`:`${metrics?.evacuated??'Unknown'} residents sheltered${showPair?' in the alternative warning':''}`} onClick={()=>openDrawer('outcomes')} className="sheltered-counter"><PixelIcon name="shelter" size={20}/><span><strong>{livingTown?(frame?homeCount:'—'):metrics?.evacuated??'—'}</strong><small>{livingTown?'At home':'Sheltered'}</small></span></button>
        <button title={livingTown?'Residents away from home':'Residents exposed at any point in this run'} aria-label={livingTown?`${frame?awayCount:'Unknown'} residents away from home`:`${metrics?.exposed??'Unknown'} residents exposed${showPair?' in the alternative warning':''}`} onClick={()=>openDrawer('outcomes')} className={livingTown?'away-counter':'exposed-counter'}><PixelIcon name={livingTown?'people':'danger'} size={20}/><span><strong>{livingTown?(frame?awayCount:'—'):metrics?.exposed??'—'}</strong><small>{livingTown?'Away':'Ever exposed'}</small></span></button>
      </div>
      <button className="world-status pixel-frame" title="World settings" onClick={()=>openDrawer('scenario')}><PixelIcon name={disasters[liveType].icon} size={20}/><span>{disasters[liveType].name}<small>{livingTown?'Next event':hazardCaption??(frame?.world_clock_minutes!==undefined?townClock(frame.world_clock_minutes):clock(frame?.time??0))}</small></span><PixelIcon name="settings" size={16}/></button>
    </header>

    {notice&&!drawer&&<div className={`notice pixel-frame ${notice.error?'error':''}`} role={notice.error?'alert':'status'}><PixelIcon name={notice.error?'danger':'check'} size={20}/><span>{notice.message}</span><button aria-label="Dismiss notification" onClick={()=>setNotice(null)}><PixelIcon name="close" size={14}/></button></div>}

    {baseline&&<div className="branch-banner pixel-frame"><PixelIcon name="compare" size={20}/><span><strong>Alternative warning</strong><small>Same city and residents as “{baseline.warning.name}”</small></span><button className="text-button" disabled={isBusy} onClick={resetView}>Cancel</button></div>}
    {placingHazard&&<div className="placement-prompt pixel-frame"><PixelIcon name="pin" size={18}/><span>Select the {disasters[disasterType].label.toLowerCase()} origin on the map</span><button className="text-button" onClick={()=>setPlacingHazard(false)}>Cancel</button></div>}

    {isBusy&&<section className="run-progress pixel-frame" aria-label="Run progress">
      <div className="progress-heading"><span className="activity-pixels" aria-hidden="true"><i/><i/><i/></span><strong role="status">{busy||'Run in progress'}</strong></div>
      {job&&<><div className="progress-track" role="progressbar" aria-label="Simulation ticks completed" aria-valuemin={0} aria-valuemax={Math.max(1,job.progress.total_ticks)} aria-valuenow={job.progress.tick}><span style={{width:`${Math.min(100,100*job.progress.tick/Math.max(1,job.progress.total_ticks))}%`}}/></div>
        <div className="progress-details"><span>{job.stage==='neural'||job.stage==='neural_queued'?'Local warning analysis':`Tick ${job.progress.tick} / ${job.progress.total_ticks}`}{job.progress.decision_round?` · Round ${job.progress.decision_round}`:''}{job.stage==='agent_decisions'&&job.progress.batches_total?` · Batch ${job.progress.batches_completed??0}/${job.progress.batches_total}`:''}</span>
          <button className="text-button" disabled={!!job.cancel_requested} onClick={()=>void cancelJob()}>{job.cancel_requested?'Stop requested':'Stop run'}</button></div>
        {!busy&&<button className="secondary" onClick={()=>void reconnectJob()}>Reconnect to run</button>}
        {job.cancel_requested&&<p className="muted">The current model request can finish and incur its normal cost.</p>}</>}
      {pendingRequest&&!busy&&<button className="secondary reconnect-button" onClick={()=>void reconnectJob()}>Reconnect to run</button>}
    </section>}

    {!drawer&&!selected&&!cameraTarget&&warning&&<section className="warning-brief pixel-frame" aria-label="Current warning">
      <div className="brief-heading"><PixelIcon name="warning" size={18}/><strong>{baseline?'Your alternative':warning.name}</strong><button aria-label="Edit warning" title="Edit warning" onClick={()=>openDrawer('warning')}><PixelIcon name="edit" size={16}/></button></div>
      <p>{warning.text}</p>{weatherReadout&&<div className="scenario-weather"><span>Scenario conditions</span><strong>{weatherReadout}</strong>{hazardCaption&&<small>{hazardCaption}</small>}</div>}<button className="brief-neural" onClick={()=>openDrawer('neural')}><PixelIcon name="brain" size={14}/>{linkedAnalysis?'View real Mini response':recording?'Analyze this warning':includeNeural?'Mini analysis included':'Mini analysis off'}<PixelIcon name="arrow" size={12}/></button>
    </section>}

    {selected&&<aside ref={inspectorRef} className="resident-inspector pixel-frame" aria-label={`Resident ${selected[0]+1}${selectedProfile?.name?` · ${selectedName}`:''}`}>
      <div className="resident-header"><ResidentPortrait id={selected[0]} character={selectedProfile?.appearance} seed={current?.art_seed??scenario?.seed??42} appearance={residentAppearance(selected[0],current?.art_seed??current?.seed??scenario?.seed??42)}/><div><h2>{selectedProfile?.name??<>Resident <span className="numeric-text">{selected[0]+1}</span></>}</h2><span className="resident-state"><i style={{background:livingTown?'#7c9364':stateColors[selected[3]]}}/>{livingTown&&selectedProfile?roleLabel(selectedProfile):stateNames[selected[3]]}</span></div><button className="icon-button" aria-label="Close resident inspector" onClick={()=>{setSelectedAgent(null);setFollowSelected(false)}}><PixelIcon name="close" size={14}/></button></div>
      {selectedProfile?.household_id&&<ResidentLife profile={selectedProfile} activity={selectedActivity} places={city?.places??[]} household={householdMembers} next={nextRoutine} nextDay={!!nextRoutine&&nextRoutine.start_minute<=minuteOfDay} nameOf={residentName} onSelect={setSelectedAgent} onLocate={place=>{setFollowSelected(false);if(window.innerWidth<=700)setSelectedAgent(null);setCameraTarget(old=>({position:place.entrance,serial:(old?.serial??0)+1}))}}/>}
      {!livingTown&&<dl className="resident-facts"><div><dt>Location</dt><dd>{selected[1].toFixed(2)}, {selected[2].toFixed(2)}</dd></div><div><dt>Exposure</dt><dd>{selected[4]} seconds</dd></div></dl>}
      {!livingTown&&frame?.agent_impacts?.some(e=>e.id===selected[0])&&<div className="resident-impact"><strong>Recorded hazard contact</strong><p>{frame.agent_impacts.filter(e=>e.id===selected[0]).map(e=>`${e.kind==='knockdown'?'Knocked down by wind':'Bracing against the hazard'} · ${clock(e.started_at)}`).join(' · ')}. Recovery preserves the resident’s chosen action.</p></div>}
      {showPair&&<p className="muted comparison-resident-note">Alternative warning · right view</p>}
      {selectedDecision?<div className="resident-decision"><span>Recorded decision · {clock(selectedDecision.time_seconds??selectedDecision.tick*(current?.configuration.tick_seconds??scenario?.tick_seconds??5))}</span><strong>{actionLabels[selectedDecision.action]}</strong><p>{selectedDecision.reason}</p></div>:!livingTown&&<p className="muted resident-no-decision">{viewedDecisionMode==='bedrock'?'No model decision recorded at this point.':'This recording uses the rules baseline.'}</p>}
      {residentDetails&&<details className="details-block resident-details"><summary>Resident details</summary><dl className="metric-details">{residentDetails.goal&&<div><dt>Goal</dt><dd>{residentDetails.goal}</dd></div>}{residentDetails.trust!==null&&<div><dt>Trust</dt><dd>{Math.round(residentDetails.trust*100)}%</dd></div>}{residentDetails.movement_speed_mps!=null&&<div><dt>Usual walking pace</dt><dd>{residentDetails.movement_speed_mps.toFixed(2)} m/s</dd></div>}{residentDetails.movement_speed_cells_per_tick!=null&&<div><dt>Travel speed</dt><dd>{residentDetails.movement_speed_cells_per_tick.toFixed(2)} cells/tick</dd></div>}{residentDetails.response_timing_seconds&&<><div><dt>Mobile delivery delay</dt><dd>{residentDetails.response_timing_seconds.mobile} s</dd></div><div><dt>Attention delay</dt><dd>{residentDetails.response_timing_seconds.attention} s</dd></div></>}{residentDetails.social_connections&&<div><dt>Social connections</dt><dd>{residentDetails.social_connections.length}</dd></div>}{residentDetails.route&&<div><dt>Recorded route</dt><dd>{residentDetails.route.length} waypoints{residentDetails.destination?` to ${residentDetails.destination.join(', ')}`:''}</dd></div>}</dl></details>}
      {canShowRoute&&<button className="text-button resident-route-toggle" aria-pressed={showRoute} onClick={()=>setRouteSelection(showRoute?null:{runId:current!.id,residentId:selected[0]})}><PixelIcon name="route" size={16}/>{showRoute?'Hide recorded route':'Show recorded route'}</button>}
      <div className="resident-actions"><button aria-label="Previous resident" onClick={()=>changeResident(-1)}><PixelIcon name="chevron-left" size={16}/></button><button className={`follow-button ${followSelected?'selected':''}`} aria-pressed={followSelected} onClick={()=>setFollowSelected(value=>!value)}><PixelIcon name="follow" size={16}/>{followSelected?'Following':'Follow resident'}</button><button aria-label="Next resident" onClick={()=>changeResident(1)}><PixelIcon name="chevron-right" size={16}/></button></div>
    </aside>}

    <footer className="game-dock">
      {livingTown&&townFrame&&<div className="living-town-dock pixel-frame"><TownTransport day={townCycles+1} dayType={scenario?.layout==='campus'?(scenario.campus_day_type??'teaching'):undefined} minutes={townFrame.world_clock_minutes??townIndex*5} playing={worldPlaying} speed={townSpeed} disabled={isBusy} onPlaying={value=>{townResumeWanted.current=value;setTownPlaying(value)}} onSpeed={setTownSpeed} onTime={minutes=>{setTownIndex(Math.min(townDay!.frames.length-1,Math.floor(minutes/(townDay!.minutes_per_tick||5))));setTownPlaying(false);townResumeWanted.current=false}}/><span className="town-picking-hint">Select a person, vehicle or building</span></div>}
      {!livingTown&&!!recording&&<button className="return-town-button pixel-frame" disabled={isBusy} onClick={returnToTown}><PixelIcon name="town" size={16}/>Return to town</button>}
      {frameCount>0&&<div className="replay-row"><div className="replay-label">{showPair?'Warning comparison':current?.warning.name}<span>{playing?'Playing':'Paused'}</span></div><Timeline frame={frame} length={frameCount} index={index} setIndex={setIndex} playing={playing} setPlaying={setPlaying} speed={speed} setSpeed={setSpeed} tickSeconds={current?.configuration.tick_seconds??scenario?.tick_seconds??5}/></div>}
      <nav className="toolbelt pixel-frame" aria-label="Simulation tools">
        <details ref={hazardMenuRef} className="hazard-menu"><summary className="tool-button" aria-label="Choose disaster"><PixelIcon name={disasters[disasterType].icon} size={25}/><span>{disasters[disasterType].label} ▴</span></summary><div className="hazard-options pixel-frame">
          {(Object.keys(disasters) as DisasterType[]).filter(type=>scenario?.layout==='campus'||['flood','wildfire','tornado'].includes(type)).map(type=><button className={`hazard-choice ${disasterType===type?'selected':''}`} key={type} aria-label={`Select ${disasters[type].name}`} aria-pressed={disasterType===type} disabled={isBusy||!!baseline} onClick={event=>{if(type!==disasterType)switchDisaster(type);event.currentTarget.closest('details')?.removeAttribute('open')}}><PixelIcon name={disasters[type].icon} size={24}/><span><strong>{disasters[type].name}</strong><small>{disasters[type].description}</small></span>{disasterType===type&&<PixelIcon name="check" size={14}/>}</button>)}
        </div></details>
        <span className="tool-divider"/>
        <button className={`tool-button ${drawer==='warning'?'selected':''}`} aria-expanded={drawer==='warning'} onClick={()=>openDrawer('warning')}><PixelIcon name="warning" size={24}/><span>Warning</span></button>
        <button className={`tool-button ${showPair||baseline?'selected':''}`} disabled={isBusy} aria-pressed={!!showPair} title={current?'Compare a different warning':'Run a warning to create a comparison'} onClick={openCompare}><PixelIcon name="compare" size={24}/><span>Compare</span></button>
        <button className={`tool-button ${drawer==='history'?'selected':''}`} aria-expanded={drawer==='history'} onClick={()=>openDrawer('history')}><PixelIcon name="runs" size={24}/><span>Runs</span></button>
        <details ref={menuRef} className="advanced-menu"><summary className="tool-button" aria-label="More tools"><PixelIcon name="menu" size={24}/><span>More</span></summary><div className="advanced-options pixel-frame">
          <span className="advanced-group-label">World</span>
          <button onClick={()=>openDrawer('scenario')}><PixelIcon name="settings" size={18}/>World settings<PixelIcon name="chevron-right" size={12}/></button>
          <button onClick={()=>openDrawer('outcomes')}><PixelIcon name={livingTown?'people':'chart'} size={18}/>{livingTown?'Residents':'Results & charts'}<PixelIcon name="chevron-right" size={12}/></button>
          <button onClick={()=>openDrawer('transit')}><PixelIcon name="bus" size={18}/>Shuttle & crossings<PixelIcon name="chevron-right" size={12}/></button>
          <span className="advanced-group-label">Analysis</span>
          <button onClick={()=>openDrawer('neural')}><PixelIcon name="brain" size={18}/>TRIBE Mini<PixelIcon name="chevron-right" size={12}/></button>
          <span className="advanced-group-label">Reference</span>
          <button onClick={()=>openDrawer('method')}><PixelIcon name="book" size={18}/>Sources & methods<PixelIcon name="chevron-right" size={12}/></button>
          <button disabled={isBusy||showPair||city?.layout!=='campus'} title={showPair?'Return to a single campus view to replay the opening':undefined} onClick={()=>{if(menuRef.current)menuRef.current.open=false;setOpening(true)}}><PixelIcon name="globe" size={18}/>Replay opening<PixelIcon name="replay" size={12}/></button>
          <span className="advanced-group-label">Preferences</span>
          <button disabled={audio.unavailable} aria-label={audio.unavailable?'Sound unavailable':'Sound'} aria-pressed={audio.enabled} onClick={()=>void audio.toggle()}><PixelIcon name={audio.enabled?'volume-on':'volume-off'} size={18}/>{audio.unavailable?'Audio unavailable':'Sound'}<span className="audio-switch" aria-hidden="true">{audio.enabled?'ON':'OFF'}</span></button>
        </div></details>
        <span className="tool-divider run-divider"/>
        <button className="run-button" disabled={!canRun} onClick={()=>void runWarning()}><PixelIcon name={isBusy?'loading':'play'} className={isBusy?'pixel-loading':''} size={20}/><span>{isBusy?'Running…':baseline?'Run alternative':'Run warning'}</span></button>
      </nav>
    </footer>
    <dialog ref={dialogRef} className="advanced-drawer pixel-frame" data-panel={drawer} aria-labelledby="advanced-title" onCancel={closeDrawer} onClick={e=>{if(e.target===e.currentTarget){const r=e.currentTarget.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)closeDrawer()}}}>
      <div className="drawer-header"><h2 id="advanced-title">{drawer?drawerTitles[drawer]:''}</h2><button className="icon-button" aria-label="Close panel" onClick={closeDrawer}><PixelIcon name="close" size={16}/></button></div>
      <div className="drawer-content">
      {notice?.error&&drawer!=='neural'&&<div className="panel-error" role="alert"><PixelIcon name="danger" size={18}/><p>{notice.message}</p><button className="icon-button" aria-label="Dismiss error" onClick={()=>setNotice(null)}><PixelIcon name="close" size={12}/></button></div>}
      {busy&&<p className="panel-progress" role="status"><span className="activity-pixels" aria-hidden="true"><i/><i/><i/></span>{busy}</p>}
      {drawer==='scenario'&&scenario&&<><p className="muted">Population, seed and campus day rebuild the town. Event settings apply to the next warning run.</p><fieldset disabled={isBusy||!!baseline}>
        <label>Resident decisions<select aria-label="Resident decisions" value={decisionMode} onChange={e=>{resetView();setCoupling(false);setScenario({...scenario,decision_mode:e.target.value as DecisionMode})}}><option value="bedrock">Bedrock agents</option><option value="rules">Rules baseline</option></select></label>
        {decisionMode==='bedrock'&&<div className="panel-section"><p className="muted">Residents read the warning and choose actions through Amazon Bedrock. Disaster spread, travel and exposure remain simulated.</p>
          {agentStatus?<><p className={agentStatus.available?'muted':'field-error'}>{agentStatus.available?'Bedrock is configured.':agentStatus.error||'Bedrock is unavailable. Runs will wait for working AWS access.'}</p><dl className="metadata"><dt>Model</dt><dd><code>{agentStatus.model_id}</code></dd><dt>Region</dt><dd>{agentStatus.region}</dd><dt>Run limit</dt><dd>${(agentStatus.max_run_usd??.30).toFixed(2)}</dd><dt>Phase budget</dt><dd>${agentStatus.spent_usd.toFixed(4)} of ${agentStatus.spend_limit_usd.toFixed(2)} · ${agentStatus.remaining_usd.toFixed(2)} remaining</dd></dl></>:<p className="muted">AWS access and the remaining budget are checked before each run.</p>}
        </div>}
        <div className="form-grid"><label>Population<input type="number" min={10} max={1000} value={scenario.population} onChange={e=>{resetView();setScenario({...scenario,population:Number(e.target.value)})}}/></label><label>Random seed<input type="number" min={0} max={4294967295} value={scenario.seed} onChange={e=>{resetView();setScenario({...scenario,seed:Number(e.target.value)})}}/></label></div>
        {scenario.layout==='campus'&&<><label>Campus day<select aria-label="Campus day" value={scenario.campus_day_type??'teaching'} onChange={e=>{resetView();setScenario({...scenario,campus_day_type:e.target.value as CampusDayType})}}><option value="teaching">Teaching day</option><option value="weekend">Weekend</option><option value="class_break">Class break · offices open</option><option value="closed">University closed</option></select></label><label className="checkbox-label"><input type="checkbox" checked={scenario.transit_enabled??true} onChange={e=>{resetView();setScenario({...scenario,transit_enabled:e.target.checked})}}/>Scheduled campus shuttle</label></>}
        <div className="form-grid"><label>Recorded frames<input type="number" min={12} max={360} value={scenario.duration_ticks} onChange={e=>{resetView();setScenario({...scenario,duration_ticks:Number(e.target.value)})}}/></label><label>Seconds between frames<input type="number" min={1} max={scenario.layout==='campus'?120:30} value={scenario.tick_seconds} onChange={e=>{resetView();setScenario({...scenario,tick_seconds:Number(e.target.value)})}}/></label></div>
        {scenarioError&&<p className="field-error">{scenarioError}</p>}
        {(scenario.layout!=='campus'||['flood','wildfire','tornado'].includes(disasterType))&&<label>Disaster intensity<div className="range-row"><input type="range" min={.1} max={3} step={.1} value={scenario.hazard_spread} onChange={e=>{resetView();setScenario({...scenario,hazard_spread:Number(e.target.value)})}}/><output>{scenario.hazard_spread.toFixed(1)}×</output></div></label>}
        <details className="details-block"><summary>Hazard origin</summary><div className="form-grid"><label>X position<input type="number" min={0} max={(city?.size??40)-1} value={scenario.hazard_origin[0]} onChange={e=>{resetView();setScenario({...scenario,hazard_origin:[Number(e.target.value),scenario.hazard_origin[1]]})}}/></label><label>Y position<input type="number" min={0} max={(city?.size??40)-1} value={scenario.hazard_origin[1]} onChange={e=>{resetView();setScenario({...scenario,hazard_origin:[scenario.hazard_origin[0],Number(e.target.value)]})}}/></label></div><button className="secondary" onClick={()=>{closeDrawer();setPlacingHazard(true)}}><PixelIcon name="pin" size={16}/>Place origin on map</button></details>
        <button className="primary" onClick={closeDrawer}>Done</button></fieldset></>}
      {drawer==='warning'&&warning&&<><fieldset disabled={isBusy}><label>Saved warning<select aria-label="Warning preset" value={warningId} onChange={e=>switchWarning(e.target.value)}>{recordedWarning&&!visibleWarnings.some(w=>w.id===recordedWarning.id)&&<option value={recordedWarning.id}>{recordedWarning.name} (recorded)</option>}{visibleWarnings.map(w=><option key={w.id} value={w.id}>{recordedWarning?.id===w.id?recordedWarning.name:w.name}</option>)}</select></label><label>Warning name<input maxLength={100} value={warning.name} onChange={e=>editWarning({name:e.target.value})}/></label><label>Message<textarea id="warning-message" rows={5} maxLength={5000} value={warning.text} onChange={e=>editWarning({text:e.target.value})}/></label><div className="message-meta"><span>{wordCount} words</span><span>{includeNeural?'Local Mini included':'Mini analysis off'}</span></div>
        {includeNeural&&wordCount>200&&<p className="field-error">Mini supports up to 200 words. Shorten the message or turn off analysis in More → TRIBE Mini.</p>}
        <div className="warning-run-actions"><button className="primary" disabled={!canRun} onClick={()=>void runWarning()}><PixelIcon name="play" size={16}/>{baseline?'Run alternative':'Run warning'}</button><button className="secondary" onClick={()=>openDrawer('neural')}><PixelIcon name="brain" size={16}/>TRIBE Mini</button></div>
        <details className="details-block warning-assumptions"><summary>Delivery & response settings</summary>
        {assumptions.filter(([key])=>decisionMode==='rules'||key==='delivery_reach_probability').map(([key,label])=><label key={key}>{label}<div className="range-row"><input type="range" min={0} max={1} step={.01} value={warning[key]} onChange={e=>editWarning({[key]:Number(e.target.value)})}/><output>{Math.round(warning[key]*100)}%</output></div></label>)}
        <div className="form-grid">{decisionMode==='rules'&&<label>Preparation delay ({scenario?.layout==='campus'?'seconds':'ticks'})<input type="number" min={0} max={scenario?.layout==='campus'?3600:120} value={scenario?.layout==='campus'?(warning.preparation_seconds??warning.response_delay*5):warning.response_delay} onChange={e=>editWarning(scenario?.layout==='campus'?{preparation_seconds:Number(e.target.value)}:{response_delay:Number(e.target.value)})}/></label>}<label>Broadcast at ({scenario?.layout==='campus'?'seconds':'tick'})<input type="number" min={0} max={scenario?.layout==='campus'?43200:360} value={scenario?.layout==='campus'?(warning.broadcast_seconds??warning.broadcast_tick*5):warning.broadcast_tick} onChange={e=>editWarning(scenario?.layout==='campus'?{broadcast_seconds:Number(e.target.value)}:{broadcast_tick:Number(e.target.value)})}/></label></div>
        <div className="channel-options">{(['mobile','siren','social'] as const).map(c=><label className="checkbox-label" key={c}><input type="checkbox" checked={warning.channels.includes(c)} onChange={e=>editWarning({channels:e.target.checked?[...warning.channels,c]:warning.channels.filter(x=>x!==c)})}/>{c==='mobile'?'Mobile alerts':c==='siren'?'Outdoor siren tones':'Social sharing'}</label>)}</div>
        <p className="muted">{decisionMode==='bedrock'?'Bedrock agents decide how to respond to the message. These settings control when and how alerts reach them.':'Text alone does not change behavior. These probabilities define the simulated response.'}</p></details><div className="actions warning-save-actions"><button className="secondary" disabled={!warning.name.trim()||!warning.text.trim()} onClick={async()=>{setBusy('Saving warning');try{await persistWarning(warning);await refresh();report('Warning saved.');closeDrawer()}catch(e){report((e as Error).message,true)}finally{setBusy('')}}}>Save warning</button><button className="quiet" onClick={()=>void addWarning(true)}>Duplicate</button><button className="quiet" onClick={()=>void addWarning()}>New warning</button></div>
        {!isPreset(warning.id)&&warnings.some(value=>value.id===warning.id)&&<div className="delete-warning"><button className="text-button danger" onClick={()=>setDeleteConfirm(!deleteConfirm)}><PixelIcon name="trash" size={16}/>Delete warning</button>{deleteConfirm&&<div className="inline-confirm"><p>Delete “{warning.name}”? Saved recordings will remain.</p><button className="secondary danger" onClick={()=>void deleteWarning()}>Delete warning</button><button className="quiet" onClick={()=>setDeleteConfirm(false)}>Keep warning</button></div>}</div>}</fieldset></>}
      {drawer==='neural'&&<><div className="panel-section"><label className="checkbox-label"><input type="checkbox" checked={includeNeural} disabled={isBusy} onChange={e=>{setIncludeNeural(e.target.checked);if(!e.target.checked)setCoupling(false)}}/>Analyze the warning when running</label><p className="muted">Uses the official Mini model on this Mac. Exact text matches reuse an existing result.</p></div><fieldset disabled={isBusy}><NeuralPanel warning={warning} analyses={analyses} stimuli={stimuli} refresh={refresh} report={report} saveWarning={persistWarning}/></fieldset>
        {decisionMode==='rules'?<details className="details-block"><summary>Experimental behavior coupling</summary><p className="muted">A sensitivity experiment, not an established relationship. Adds strength × tanh(mean absolute response) to notice probability.</p><label className="checkbox-label"><input type="checkbox" checked={coupling} disabled={isBusy||!includeNeural} onChange={e=>setCoupling(e.target.checked)}/>Enable coupling for the next run</label>{coupling&&<label>Strength<div className="range-row"><input type="range" min={-1} max={1} step={.05} value={strength} disabled={isBusy} onChange={e=>setStrength(Number(e.target.value))}/><output>{strength.toFixed(2)}</output></div></label>}</details>:<p className="muted">Mini predictions are recorded alongside Bedrock decisions. They do not alter residents’ actions.</p>}</>}
      {drawer==='history'&&<><p className="muted">Replay a recording or reopen a comparison.</p><div className="saved-runs">{runs.map(r=><div className="saved-run" key={r.id}><button disabled={isBusy} onClick={()=>void loadRun(r)}><span><strong>{r.warning.name}</strong><small>{disasters[r.configuration.disaster_type??'flood'].name} · {(r.decision_mode??r.configuration.decision_mode)==='bedrock'?'Bedrock':'Rules'} · {new Date(r.created_at).toLocaleString([], {month:'short',day:'numeric',hour:'numeric',minute:'2-digit'})}</small></span><span className="saved-run-outcomes"><span className="saved-run-number">{r.metrics.evacuated}<small>sheltered</small></span><span className="saved-run-number saved-run-exposure">{r.metrics.exposed}<small>ever exposed</small></span></span><PixelIcon name="replay" size={16}/></button><a aria-label={`Download ${r.warning.name} recording`} href={`/api/runs/${r.id}/export`} download><PixelIcon name="download" size={16}/></a></div>)}{!runs.length&&<p>No saved runs yet.</p>}</div>
        {!!comparisons.length&&<><h3>Comparisons</h3><div className="saved-comparisons">{comparisons.map(c=><button className="saved-comparison" key={c.id} aria-label={`Replay comparison: ${runs.find(r=>r.id===c.baseline_run_id)?.warning.name??'Baseline'} versus ${runs.find(r=>r.id===c.alternative_run_id)?.warning.name??'Alternative'}`} disabled={isBusy} onClick={()=>void loadComparison(c)}><PixelIcon name="compare" size={16}/><span>{runs.find(r=>r.id===c.baseline_run_id)?.warning.name??'Baseline'}<PixelIcon name="chevron-right" size={12}/>{runs.find(r=>r.id===c.alternative_run_id)?.warning.name??'Alternative'}</span><strong>{(c.deltas.evacuated??0)>0?'+':''}{c.deltas.evacuated??0}</strong></button>)}</div></>}
      </>}
      {drawer==='outcomes'&&frame&&<>{livingTown?<div className="town-population-summary"><h3>{frame.agents.length} residents · {new Set(profiles.map(profile=>profile.household_id)).size} households</h3><p className="muted">Day {townCycles+1} · {townClock(frame.world_clock_minutes??townIndex*5)}</p><dl className="metric-details"><div><dt>At home</dt><dd>{homeCount}</dd></div><div><dt>Away from home</dt><dd>{awayCount}</dd></div><div><dt>Owned cars</dt><dd>{frame.vehicles?.filter(v=>v.type!=='bus').length??0}</dd></div><div><dt>Walking</dt><dd>{frame.agent_activities?.filter(a=>a.mode==='walking').length??0}</dd></div><div><dt>In cars</dt><dd>{frame.agent_activities?.filter(a=>a.mode==='driving'||a.mode==='riding').length??0}</dd></div><div><dt>In conversation</dt><dd>{new Set(frame.interactions?.flatMap(interaction=>interaction.agent_ids)??[]).size}</dd></div></dl></div>:<OutcomeNumbers metrics={frame.metrics} baseline={showPair&&pair?pair.recordings[0].frames[Math.min(index,pair.recordings[0].frames.length-1)].metrics:undefined}/>}
        {activeRecord&&<OutcomeChart recording={showPair&&pair?pair.recordings[0]:activeRecord} alternative={showPair&&pair?pair.recordings[1]:undefined} index={index}/>}
        {!livingTown&&<details className="details-block" open><summary>Recorded metrics</summary><dl className="metric-details">{[...(frame.metrics.siren_heard===undefined?[]:[['Siren tones heard',frame.metrics.siren_heard]]),['Messages delivered',frame.metrics.warning_delivered],['Warnings shared',frame.metrics.warning_shared],[city?.layout==='campus'?'Protective actions started':'Evacuation starts',frame.metrics.evacuation_started],['Road closures',frame.metrics.road_closures],['Routes replanned',frame.metrics.route_replans],['Hazard coverage',`${(frame.metrics.hazard_coverage*100).toFixed(1)}%`]].map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></details>}
        <details className="details-block" open={livingTown||undefined}><summary>Inspect a resident</summary><label>Resident<select value={selectedAgent??''} onChange={e=>{setSelectedAgent(Number(e.target.value));closeDrawer()}}><option value="" disabled>Choose a resident</option>{[...inspectionGroups].map(([group,residents])=><optgroup key={group} label={`${group} · ${residents.length}`}>{residents.map(a=><option key={a[0]} value={a[0]}>{residentName(a[0])} · {livingTown?activityLabel(activityById.get(a[0])?.activity??'home'):stateNames[a[3]]}</option>)}</optgroup>)}</select></label></details>{!livingTown&&<div className="legend-panel"><Legend/></div>}
        {current&&!baseline&&<button className="primary" disabled={isBusy} onClick={()=>{createAlternative();setDrawer('warning')}}><PixelIcon name="compare" size={16}/>Compare another warning</button>}</>}
      {drawer==='transit'&&<CampusTravel frame={frame} nameOf={residentName} onResident={id=>{setSelectedAgent(id);closeDrawer()}} onLocate={position=>{setSelectedAgent(null);setFollowSelected(false);setCameraTarget(old=>({position,serial:(old?.serial??0)+1}));closeDrawer()}}/>}
      {drawer==='method'&&<SourcesPanel mode={viewedDecisionMode} usage={agentUsage} policy={agentPolicy} status={agentStatus}/>}
      </div>
    </dialog>
  </div>{opening&&<CampusOpening camera={openingCamera} city={city} failed={loadError} onComplete={finishOpening} onSoundFlight={audio.flight} onArrival={openingArrival}/>}</>
}
