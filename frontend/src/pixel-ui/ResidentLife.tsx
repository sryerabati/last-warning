import type {AgentActivity, ResidentProfile, TownPlace} from '../types'
import {townClock} from './TownTransport'
import {residentMobility} from './ResidentMobility'

const labels:Record<string,string>={home:'At home',at_home:'At home',sleeping:'Sleeping',work:'Working',working:'Working',school:'At school',shopping:'Shopping',park:'At the park',leisure:'Taking a break',socializing:'Socializing',commuting:'Walking',commute_work:'Walking to work',commute_home:'Walking home',walking:'Walking',conversation:'Talking',greeting:'Greeting a neighbor'}
export const activityLabel=(value:string)=>labels[value]??value.replaceAll('_',' ').replace(/^./,letter=>letter.toUpperCase())
export const roleLabel=(profile:ResidentProfile)=>profile.role==='child'&&profile.age_years!=null&&profile.age_years<=5?'Preschooler':activityLabel(profile.role)

export function ResidentLife({profile,activity,places,household,next,nextDay,nameOf,onSelect,onLocate}: {
  profile:ResidentProfile;activity?:AgentActivity;places:TownPlace[];household:ResidentProfile[];
  next?:ResidentProfile['routine'][number];nextDay?:boolean;nameOf:(id:number)=>string;onSelect:(id:number)=>void;onLocate?:(place:TownPlace)=>void
}) {
  const place=(id:string|null|undefined)=>places.find(value=>value.id===id)
  const current=place(activity?.place_id),destination=place(activity?.destination_place_id),home=place(profile.home_place_id),work=place(profile.work_place_id)
  const traveling=!!activity?.mode&&['walking','boarding','driving','riding','alighting'].includes(activity.mode)
  const mobility=residentMobility(activity,profile)
  const activityText=activity?activityLabel(activity.activity):''
  const movementTitle=mobility?.label==='Careful steps'?'Walking carefully':mobility?.label
  const activityTitle=activity?.mode==='walking'&&/^Walking\b/.test(activityText)&&movementTitle
    ? ['Waiting','Bracing','Recovering'].includes(movementTitle)?movementTitle:activityText.replace(/^Walking\b/,movementTitle)
    : activityText
  const address=(value:TownPlace|undefined,fallback:string)=>value&&!value.is_portal&&onLocate?<button className="resident-address-link" title={`Show ${value.name} on the map`} onClick={()=>onLocate(value)}>{value.name}</button>:value?.name??fallback
  return <div className="resident-life">
    {activity&&<div className="resident-activity"><strong>{activityTitle}</strong><span>{activity.inside?'Inside · ':''}{current?.name??(destination?`To · ${destination.name}`:'Campus paths')}</span></div>}
    {activity?.mode&&<div className="resident-travel"><span>{mobility?.label||activityLabel(activity.mode)}</span>{mobility?.speed&&!activity.inside&&<small>Current pace · {mobility.speed}</small>}{activity.vehicle_id&&<small>{activity.vehicle_id.startsWith('bus-')?'Campus shuttle':`Car ${activity.vehicle_id.replace('car-', '')}`}</small>}{activity.group_id&&<small>{traveling?'Traveling with household':'With household'}</small>}{mobility?.response&&<small>{mobility.response}</small>}</div>}
    <dl className="resident-addresses"><div><dt>Home</dt><dd>{address(home,profile.home_place_id)}</dd></div>{work?.id!==home?.id&&<div><dt>{work?(profile.role.includes('student')?'Study':'Work'):'Role'}</dt><dd>{address(work,roleLabel(profile))}</dd></div>}</dl>
    {!!activity?.partner_ids.length&&<div className="resident-conversation"><span>With</span>{activity.partner_ids.map(id=><button key={id} className="text-button" onClick={()=>onSelect(id)}>{nameOf(id)}</button>)}</div>}
    {next&&<p className="resident-next"><span>Next · {nextDay?'Tomorrow · ':''}{townClock(next.start_minute)}</span>{activityLabel(next.activity)}<small>{place(next.place_id)?.name}</small></p>}
    <details className="details-block resident-household"><summary>Household · {household.length}</summary><div className="household-members">{household.map(member=><button key={member.id} aria-pressed={member.id===profile.id} onClick={()=>onSelect(member.id)}><span>{nameOf(member.id)}</span><small>{roleLabel(member)}{member.family_relationship==='parent'?' · Parent':member.age_years!=null&&member.role==='child'?` · Age ${member.age_years}`:''}</small></button>)}</div></details>
    {profile.biography&&<details className="details-block resident-about"><summary>About {profile.identity?.given_name??'this resident'}</summary><p className="muted">{profile.biography}</p></details>}
    <details className="details-block resident-routine"><summary>Daily routine</summary><ol>{profile.routine.map((step,i)=><li key={`${step.start_minute}-${i}`}><time>{townClock(step.start_minute)}</time><span>{activityLabel(step.activity)}<small>{place(step.place_id)?.name??step.place_id}</small></span></li>)}</ol><p className="muted">{profile.goal}</p></details>
  </div>
}
