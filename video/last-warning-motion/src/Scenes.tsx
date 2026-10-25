import React, {type CSSProperties} from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

export type Content = {
  projectName: string;
  teamName: string;
  repositoryUrl: string;
  eventCredit: string;
  baseline: number;
  alternative: number;
  population: number;
  baselineLabel: string;
  alternativeLabel: string;
  comparisonId: string;
};

const C = {
  forest: '#172E27', deep: '#10251F', panel: '#203B31', line: '#436050',
  cream: '#F1EDDA', gold: '#DFBA66', sage: '#A8C399', muted: '#B5C3AD',
  rust: '#BC745A', ink: '#223D31', paperLine: '#D0D0B9', cyan: '#8BBDBA',
};
const ease = Easing.out(Easing.cubic);
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const at = (frame: number, fps: number, seconds: number, duration = 0.6) =>
  interpolate(frame, [seconds * fps, (seconds + duration) * fps], [0, 1], {...clamp, easing: ease});

const icons = {
  beacon: 'M7 2h2v2H7zM4 4h2v2H4zM10 4h2v2h-2zM2 7h2v3H2zM12 7h2v3h-2zM6 6h4v5H6zM5 11h6v2H5zM4 13h8v1H4z',
  people: 'M6 1h4v4H6zM4 6h8v5h-2v4H8v-4H7v4H5v-4H3V7h1zM0 4h3v3H0zM13 4h3v3h-3zM0 8h2v5H0zM14 8h2v5h-2z',
  shelter: 'M7 1h2v2h2v2h2v2h2v2h-2v6H3V9H1V7h2V5h2V3h2zM7 9v5h3V9zM4 8v3h2V8z',
  brain: 'M4 2h3v2h2V2h3v2h2v7h-2v3H9v-3H7v3H4v-3H2V4h2zM4 5v3h2V5zM10 5v3h2V5z',
  check: 'M13 3h2v3h-2v2h-2v2H9v2H7v2H5v-2H3v-2H1V7h3v2h2v1h1V8h2V6h2V4h2z',
  route: 'M1 2h5v2H3v7h7V8h2v5H1zM10 1h5v5h-2V4l-5 5-2-2 5-4h-1z',
  chip: 'M4 3h8v10H4zM6 5v6h4V5zM1 4h3v2H1zM1 9h3v2H1zM12 4h3v2h-3zM12 9h3v2h-3zM5 0h2v3H5zM9 0h2v3H9zM5 13h2v3H5zM9 13h2v3H9z',
  runs: 'M3 1h9v2h2v11H3zM5 4v1h7V4zM5 7v1h7V7zM5 10v1h5v-1zM1 4h1v11h10v1H1z',
} as const;

export const Icon = ({name, size = 42, color = C.gold}: {name: keyof typeof icons; size?: number; color?: string}) =>
  <svg width={size} height={size} viewBox="0 0 16 16" fill={color} fillRule="evenodd" shapeRendering="crispEdges" aria-hidden><path d={icons[name]}/></svg>;

const Reveal = ({seconds = 0, children, style = {}}: {seconds?: number; children: React.ReactNode; style?: CSSProperties}) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig(); const p = at(f, fps, seconds);
  return <div style={{...style, opacity: p, transform: `translateY(${(1 - p) * 22}px)`}}>{children}</div>;
};

const Background = ({light = false}: {light?: boolean}) =>
  <AbsoluteFill style={{backgroundColor: light ? C.cream : C.forest}}>
    <svg width="1920" height="1080" style={{position: 'absolute', opacity: light ? 0.3 : 0.22}}>
      <defs><pattern id="grid" width="64" height="64" patternUnits="userSpaceOnUse"><path d="M64 0H0V64" fill="none" stroke={light ? '#B6BEA9' : '#4A6858'} strokeWidth="1"/></pattern></defs>
      <rect width="1920" height="1080" fill="url(#grid)"/>
    </svg>
    <div style={{position: 'absolute', left: 108, right: 108, top: 74, height: 2, background: light ? C.paperLine : C.line}}/>
  </AbsoluteFill>;

const Frame = ({children, light = false}: {children: React.ReactNode; light?: boolean}) =>
  <AbsoluteFill style={{fontFamily: 'Inter', color: light ? C.ink : C.cream, overflow: 'hidden'}}>
    <Background light={light}/>{children}
  </AbsoluteFill>;

const Header = ({kicker, title, light = false}: {kicker: string; title: string; light?: boolean}) =>
  <>
    <Reveal seconds={0.05} style={{position: 'absolute', left: 108, top: 105, fontSize: 23, fontWeight: 650, letterSpacing: 3, color: light ? '#61725F' : C.gold}}>{kicker}</Reveal>
    <Reveal seconds={0.17} style={{position: 'absolute', left: 104, top: 163, fontSize: 76, lineHeight: 1.1, fontWeight: 650, letterSpacing: -3}}>{title}</Reveal>
  </>;

const Pill = ({children, light = false}: {children: React.ReactNode; light?: boolean}) =>
  <span style={{display: 'inline-flex', alignItems: 'center', padding: '13px 20px', border: `1px solid ${light ? C.paperLine : '#5A7059'}`, background: light ? '#E5E4D0' : '#213D31', fontSize: 24, lineHeight: 1.1, fontWeight: 550, color: light ? C.ink : C.cream}}>{children}</span>;

const CityMotif = () => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  const p = at(f, fps, 0.55, 1.5);
  const path = 'M65 490H225V355H405V170H575';
  return <svg width="720" height="650" viewBox="0 0 720 650" style={{overflow: 'visible'}}>
    <defs><clipPath id="map-window"><rect x="0" y="0" width="720" height="650" rx="4"/></clipPath></defs>
    <g clipPath="url(#map-window)">
      <rect width="720" height="650" fill="#1C382C"/>
      <path d="M320 -30H395V245H350V440H395V700H320V450H276V245H320Z" fill="#315A53"/>
      {[90, 225, 405, 575].map(x => <g key={x}><rect x={x-16} width="32" height="650" fill="#3E5140"/><path d={`M${x} 0V650`} stroke="#87916C" strokeDasharray="10 14" strokeWidth="2"/></g>)}
      {[80,170,355,490,605].map(y => <g key={y}><rect y={y-16} width="720" height="32" fill="#3E5140"/><path d={`M0 ${y}H720`} stroke="#87916C" strokeDasharray="10 14" strokeWidth="2"/></g>)}
      {[0,1,2,3,4,5].map(row => [0,1,2,3,4].map(col => {
        const x=30+col*140, y=24+row*106; if(col===2)return null;
        return <g key={`${row}-${col}`} opacity={0.42 + (row+col)%3 * 0.1}>
          <rect x={x} y={y} width="35" height="30" fill="#75866B"/>
          <rect x={x-4} y={y-4} width="43" height="8" fill="#A09F71"/>
          <rect x={x+8} y={y+10} width="6" height="8" fill="#1F3E30"/>
          <rect x={x+21} y={y+10} width="6" height="8" fill="#1F3E30"/>
        </g>;
      }))}
      <path d={path} stroke={C.gold} strokeWidth="7" fill="none" pathLength="1" strokeDasharray="1" strokeDashoffset={1-p}/>
      {[{x:65,y:490,t:0.7},{x:225,y:355,t:1.25},{x:405,y:170,t:1.8},{x:575,y:170,t:2.3}].map((point,i)=>{
        const a=at(f,fps,point.t,0.45); const pulse=0.5+0.5*Math.sin(f/14-i);
        return <g key={i} opacity={a}><circle cx={point.x} cy={point.y} r={15+pulse*7} fill="none" stroke={C.gold} opacity={0.2}/><rect x={point.x-5} y={point.y-5} width="10" height="10" fill={C.gold}/></g>;
      })}
    </g>
    <rect x="0" y="0" width="720" height="650" fill="none" stroke="#587052" strokeWidth="2"/>
  </svg>;
};

export const Title = (content: Content) =>
  <Frame>
    <Reveal seconds={0.05} style={{position: 'absolute', left: 108, top: 112, display: 'flex', alignItems: 'center', gap: 18}}>
      <Icon name="beacon" size={44}/><span style={{fontSize: 24, letterSpacing: 2.5, fontWeight: 600}}>HACKOHI/O 2026</span>
    </Reveal>
    <Reveal seconds={0.2} style={{position: 'absolute', left: 101, top: 255, fontFamily: 'Pixelify Sans', fontSize: 178, lineHeight: 0.94, letterSpacing: -4, fontWeight: 600}}>
      {content.projectName === 'Last Warning' ? <>Last<br/>Warning</> : content.projectName}
    </Reveal>
    <Reveal seconds={0.55} style={{position: 'absolute', left: 108, top: 640, width: 840, fontSize: 38, lineHeight: 1.42, color: C.muted}}>Explore the response<br/>before an emergency happens.</Reveal>
    <Reveal seconds={1} style={{position: 'absolute', left: 108, top: 802, display: 'flex', gap: 16}}>
      <Pill>AI resident swarm</Pill><Pill>TRIBE v2 Mini</Pill>
    </Reveal>
    <Reveal seconds={0.4} style={{position: 'absolute', left: 1080, top: 182}}><CityMotif/></Reveal>
    <Reveal seconds={1.5} style={{position: 'absolute', right: 120, top: 858, fontSize: 22, color: C.muted}}>Warning → decision → route</Reveal>
  </Frame>;

export const EndCard = (content: Content) => {
  const f=useCurrentFrame(); const alpha=interpolate(f,[0,5],[0,1],clamp);
  return <Frame>
    <div style={{opacity:alpha,position:'absolute',inset:0,display:'flex',alignItems:'center',flexDirection:'column'}}>
      <div style={{marginTop:186}}><Icon name="beacon" size={100}/></div>
      <div style={{fontFamily:'Pixelify Sans',fontSize:146,lineHeight:1.15,letterSpacing:-2,fontWeight:600,marginTop:45}}>{content.projectName}</div>
      <div style={{fontSize:39,color:C.muted,marginTop:30}}>Before the emergency happens.</div>
      <div style={{width:140,height:3,background:C.gold,marginTop:58}}/>
      <div style={{fontSize:29,color:C.gold,marginTop:39}}>{content.eventCredit}</div>
      {content.teamName&&<div style={{fontSize:30,marginTop:25}}>{content.teamName}</div>}
      {content.repositoryUrl&&<div style={{fontSize:25,color:C.muted,marginTop:22}}>{content.repositoryUrl}</div>}
    </div>
  </Frame>;
};

export const Results = (content: Content) => {
  const f=useCurrentFrame();const {fps}=useVideoConfig();
  const generic=at(f,fps,0.9,1.15); const alternative=at(f,fps,2.25,1.4);
  const chartX=124, chartW=1060;
  return <Frame light>
    <Header light kicker="SAVED FLOOD COMPARISON" title="More residents reached shelter."/>
    <Reveal seconds={0.45} style={{position:'absolute',left:108,top:274,display:'flex',gap:15}}>
      <Pill light>300 simulated residents</Pill><Pill light>Same starting city + flood</Pill>
    </Reveal>
    <svg width="1920" height="1080" style={{position:'absolute',inset:0}}>
      {[0,100,200,300].map(v=><g key={v} opacity={at(f,fps,0.6)}>
        <line x1={chartX+chartW*v/content.population} y1="418" x2={chartX+chartW*v/content.population} y2="784" stroke={C.paperLine} strokeWidth="2"/>
        <text x={chartX+chartW*v/content.population} y="825" fontFamily="Inter" fontSize="24" fill="#6A7A67" textAnchor={v===0?'start':v===300?'end':'middle'}>{v}</text>
      </g>)}
      <g opacity={at(f,fps,0.85)}>
        <text x={chartX} y="403" fontSize="32" fontWeight="550" fill={C.ink}>{content.baselineLabel}</text>
        <rect x={chartX} y="434" width={chartW*content.baseline/content.population*generic} height="92" fill={C.rust}/>
        <text x={chartX+chartW*content.baseline/content.population+25} y="500" fontSize="66" fontWeight="650" fill={C.ink}>{content.baseline}</text>
      </g>
      <g opacity={at(f,fps,2.1)}>
        <text x={chartX} y="625" fontSize="32" fontWeight="550" fill={C.ink}>{content.alternativeLabel}</text>
        <rect x={chartX} y="657" width={chartW*content.alternative/content.population*alternative} height="92" fill="#52714E"/>
        <text x={chartX+chartW*content.alternative/content.population+25} y="723" fontSize="66" fontWeight="650" fill={C.ink}>{content.alternative}</text>
      </g>
    </svg>
    <Reveal seconds={4.1} style={{position:'absolute',left:1312,top:371,width:500,height:455,background:C.forest,padding:44,color:C.cream}}>
      <Icon name="shelter" size={43}/>
      <div style={{fontSize:148,fontWeight:600,letterSpacing:-7,lineHeight:1.1,marginTop:30,color:C.gold}}>+{content.alternative-content.baseline}</div>
      <div style={{fontSize:33,lineHeight:1.35,marginTop:18}}>more simulated<br/>residents sheltered</div>
    </Reveal>
    <Reveal seconds={0.7} style={{position:'absolute',left:124,top:867,fontSize:25,color:'#53664F'}}>Simulated outcomes · Warning text and delivery settings both changed</Reveal>
  </Frame>;
};

const DiagramNode = ({x,y,w,h=226,seconds,icon,label,title,children,accent=C.gold}: {
  x:number;y:number;w:number;h?:number;seconds:number;icon:keyof typeof icons;label:string;title:string;children?:React.ReactNode;accent?:string;
}) => <Reveal seconds={seconds} style={{position:'absolute',left:x,top:y,width:w,height:h,padding:'27px 28px',background:C.panel,border:`2px solid ${C.line}`,boxSizing:'border-box'}}>
  <div style={{display:'flex',alignItems:'center',gap:14,color:accent,fontSize:19,fontWeight:650,letterSpacing:1.5}}><Icon name={icon} size={29} color={accent}/>{label}</div>
  <div style={{fontSize:32,fontWeight:600,lineHeight:1.18,marginTop:22,letterSpacing:-0.7}}>{title}</div>
  <div style={{fontSize:24,lineHeight:1.45,color:C.muted,marginTop:17}}>{children}</div>
</Reveal>;

const Edge = ({path,seconds,color=C.gold}: {path:string;seconds:number;color?:string}) => {
  const f=useCurrentFrame();const {fps}=useVideoConfig();const p=at(f,fps,seconds,0.8);
  return <path d={path} pathLength="1" fill="none" stroke={color} strokeWidth="3" strokeDasharray="1" strokeDashoffset={1-p} opacity={p}/>;
};

export const Architecture = (_content: Content) => {
  const f=useCurrentFrame();const {fps}=useVideoConfig();
  return <Frame>
    <Header kicker="HOW LAST WARNING WORKS" title="One warning. Two analysis tracks."/>
    <svg width="1920" height="1080" style={{position:'absolute',inset:0}}>
      <Edge path="M408 491H460V430H520" seconds={1.9}/>
      <Edge path="M932 430H1010" seconds={4.1}/>
      <Edge path="M1350 430H1430" seconds={9.7}/>
      <Edge path="M408 491H460V744H520" seconds={14.3} color={C.cyan}/>
      <Edge path="M1000 744H1110" seconds={17.3} color={C.cyan}/>
      <g opacity={at(f,fps,10.25)} fill={C.gold}><path d="M1418 421l12 9-12 9Z"/><path d="M998 421l12 9-12 9Z"/></g>
      <g opacity={at(f,fps,18)} fill={C.cyan}><path d="M1098 735l12 9-12 9Z"/></g>
    </svg>
    <Reveal seconds={0.7} style={{position:'absolute',left:108,top:396,width:300,height:190,background:C.gold,color:C.forest,padding:'30px 28px'}}>
      <Icon name="beacon" size={36} color={C.forest}/>
      <div style={{fontSize:38,fontWeight:650,marginTop:15,lineHeight:1.15}}>Warning</div>
      <div style={{fontSize:24,marginTop:10}}>Text + delivery</div>
    </Reveal>
    <DiagramNode x={520} y={317} w={412} seconds={2} icon="people" label="SIMULATION TRACK" title="AI resident swarm">
      Mesa · goals + memory
      <div style={{opacity:at(f,fps,6),color:C.cream,fontSize:22,marginTop:13}}>Nova Micro on Bedrock → actions</div>
    </DiagramNode>
    <DiagramNode x={1010} y={317} w={340} seconds={4} icon="route" label="CITY ENGINE" title="Routes + hazards">
      NetworkX + engine<br/>Movement · exposure
    </DiagramNode>
    <DiagramNode x={1430} y={317} w={382} seconds={10} icon="runs" label="SAVED EVIDENCE" title="Recorded outcomes">
      Shelter + exposure<br/>Exact replay
    </DiagramNode>
    <Reveal seconds={8.5} style={{position:'absolute',left:520,top:246,fontSize:24,color:C.muted}}><span style={{color:C.gold,fontWeight:650}}>FastAPI</span> coordinates the system</Reveal>
    <DiagramNode x={520} y={639} w={480} h={205} seconds={14.2} icon="brain" label="INDEPENDENT ANALYSIS" title="TRIBE v2 Mini" accent={C.cyan}>
      Local inference on the Mac
    </DiagramNode>
    <DiagramNode x={1110} y={639} w={702} h={205} seconds={17.5} icon="brain" label="RESEARCH PREDICTION" title="Predicted cortical fMRI response" accent={C.cyan}>
      Average-subject response to the exact warning text
    </DiagramNode>
    <Reveal seconds={20.4} style={{position:'absolute',left:520,top:866,fontSize:24,color:C.muted}}>Mini results accompany the simulation; they do not drive resident decisions.</Reveal>
  </Frame>;
};

export const Pivot = (_content: Content) => {
  const f=useCurrentFrame();const {fps}=useVideoConfig();
  const cards=[
    {x:108,t:0.7,label:'01 / CONSTRAINT',color:C.rust,icon:'chip' as const,title:<>Cloud GPU<br/>quota: 0</>,body:<>Full-size TRIBE<br/>launch blocked</>},
    {x:710,t:4.8,label:'02 / CHANGE',color:C.gold,icon:'brain' as const,title:<>Run Mini<br/>on the Mac</>,body:<>Metal + CPU<br/>Resident model stays on Bedrock</>},
    {x:1312,t:10.8,label:'03 / RESULT',color:C.sage,icon:'check' as const,title:<>Both tracks<br/>working</>,body:<>Local Mini + cloud residents<br/>Artifacts and decisions saved</>},
  ];
  return <Frame>
    <Header kicker="ENGINEERING PIVOT" title="GPU quota blocked. We changed the plan."/>
    {cards.map(card=><Reveal key={card.label} seconds={card.t} style={{position:'absolute',left:card.x,top:350,width:500,height:478,background:C.panel,border:`2px solid ${C.line}`,padding:38}}>
      <div style={{fontSize:22,letterSpacing:2,color:card.color,fontWeight:600}}>{card.label}</div>
      <div style={{marginTop:30}}><Icon name={card.icon} color={card.color} size={48}/></div>
      <div style={{fontSize:48,lineHeight:1.12,letterSpacing:-1.4,fontWeight:600,marginTop:29}}>{card.title}</div>
      <div style={{fontSize:25,lineHeight:1.5,color:C.muted,marginTop:26}}>{card.body}</div>
    </Reveal>)}
    <svg width="1920" height="1080" style={{position:'absolute',inset:0}}>
      <g opacity={at(f,fps,4.6)} fill="none" stroke={C.gold} strokeWidth="3"><path d="M631 588H686M676 579l10 9-10 9"/></g>
      <g opacity={at(f,fps,10.6)} fill="none" stroke={C.gold} strokeWidth="3"><path d="M1233 588H1288M1278 579l10 9-10 9"/></g>
    </svg>
    <Reveal seconds={12} style={{position:'absolute',left:108,top:867,fontSize:25,color:C.muted}}>Verified local Mini inference + completed Bedrock simulations</Reveal>
  </Frame>;
};
