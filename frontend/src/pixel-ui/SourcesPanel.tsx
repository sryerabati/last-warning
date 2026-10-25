import {useState} from 'react'
import {campusEvidence,campusEvidenceReviewedOn} from '../data/campusEvidence'
import type {AgentPolicy,AgentStatus,AgentUsage,DecisionMode} from '../types'
import './SourcesPanel.css'

export function SourcesPanel({mode,usage,policy,status}:{mode:DecisionMode;usage?:AgentUsage|null;policy?:AgentPolicy|null;status:AgentStatus|null}){
  const [section,setSection]=useState<'simulation'|'evidence'|'models'>('simulation')
  return <div className="sources-panel">
    <nav className="source-sections" aria-label="Sources sections">{(['simulation','evidence','models'] as const).map(value=><button key={value} aria-pressed={section===value} onClick={()=>setSection(value)}>{value==='simulation'?'Simulation':value==='evidence'?'Evidence':'Models'}</button>)}</nav>
    {section==='simulation'&&<div className="method-copy">
      <h3>Real geography. Fictional residents.</h3>
      <p>The map covers the academic core, South Campus and part of the University District. Buildings and streets are sourced; the people and their lives are generated for this simulation.</p>
      <dl className="source-overview">
        <div><dt>Geography</dt><dd>Pinned OpenStreetMap footprints, paths, streets and trees. Building elevations are illustrative.</dd></div>
        <div><dt>Daily life</dt><dd>Seeded homes, classes, work, meals and travel for the chosen campus day, with a scheduled shuttle and crossing queues. The daily loop makes no model requests.</dd></div>
        <div><dt>Warning response</dt><dd>{mode==='bedrock'?'Bedrock selects residents’ intentions at recorded checkpoints.':'The selected rules baseline uses configured probabilities and delays.'} Local simulation resolves travel, shelter access and exposure. Shelter choices use feasible route travel time; outdoor tones and delivered warning text are tracked separately.</dd></div>
      </dl>
      <details className="details-block"><summary>People & identity</summary><p>Names, biographies and appearances describe fictional people. Naming styles and family relationships are authored; they are not inferred identities of real students. Appearance is not inferred from a surname. New campus runs exclude cosmetic identity from the resident decision context.</p></details>
      <details className="details-block"><summary>Hazards & model limits</summary><p>Seven scenarios cover flood, wildfire, tornado, blizzard, hail, destructive thunderstorm and an abstract restricted area. Storm shelter holds follow source-informed timing; the weather fields are illustrative.</p><p>Household proportions, schedules, building capacities and shelter suitability are authored assumptions. Exposure counts time in modeled danger, not injury probability. Recorded wind contact interrupts movement and animates bracing, knockdown and recovery; these are authored reactions. Routing around steps does not certify real-world accessibility. Vehicles yield at modeled conflicts and maintain spacing. Traffic and shuttle service are simplified; there is no collision injury model or live signal timing.</p></details>
      <details className="details-block"><summary>Replay & fair comparisons</summary><p>A warning starts from the town’s visible time and actual resident positions. Alternative warnings share the baseline’s city, residents, event and seed. Model responses are saved for exact replay; a fresh model request can differ.</p></details>
      <details className="details-block"><summary>Map & opening credits</summary><p><a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors · ODbL</a></p><p>The pixel Earth and Ohio region use public-domain <a href="https://www.naturalearthdata.com/" target="_blank" rel="noreferrer">Natural Earth geometry</a>. Columbus roads, rivers and surrounding footprints use pinned OpenStreetMap extracts. The geographic camera lands on the live Oval; terrain colors and surrounding roof heights are illustrative. Opening-only context does not expand the playable world.</p></details>
    </div>}
    {section==='evidence'&&<div className="evidence-list">
      <p className="muted">Dated public references. Each entry states whether it informs the current model or is context for future improvements.</p>
      {campusEvidence.map(item=><details className="evidence-entry" key={item.id}><summary><span><small>{item.category}</small><strong>{item.title}</strong><em>{item.status}</em></span></summary>
        <p>{item.summary}</p><dl><div><dt>Period</dt><dd>{item.period}</dd></div><div><dt>Scope</dt><dd>{item.scope}</dd></div><div><dt>Use here</dt><dd>{item.application}</dd></div><div><dt>Limit</dt><dd>{item.limitation}</dd></div></dl>
        <div className="evidence-links">{item.sources.map(source=><a key={source.url} href={source.url} target="_blank" rel="noreferrer">{source.title} ↗</a>)}</div>
      </details>)}
      <p className="evidence-reviewed">Sources reviewed {campusEvidenceReviewedOn}.</p>
    </div>}
    {section==='models'&&<div className="method-copy">
      <h3>{mode==='bedrock'?'Bedrock resident decisions':'Rules baseline'}</h3><p>{mode==='bedrock'?'Residents receive available warning information, nearby conditions, current activity and permitted actions. Their choice and a short explanation are saved with the replay. New campus runs omit names and cosmetic appearance from decision inputs; historical recordings retain their original context.':'This recording uses configured response probabilities and delays. Historical recordings retain their original model.'}</p>
      <h3>Local TRIBE Mini</h3><p>Mini predicts an average subject’s cortical fMRI response to text presented at 2.5 words per second. It does not measure a resident’s brain or determine compliance. Neural results stay separate from Bedrock actions; optional rules-only coupling is a sensitivity experiment.</p>
      {usage&&<details className="details-block"><summary>Recorded model usage</summary><dl className="metadata"><dt>Model</dt><dd><code>{policy?.model_id??usage.model_id}</code></dd><dt>Region</dt><dd>{policy?.region??usage.region}</dd><dt>Requests</dt><dd>{usage.calls}</dd><dt>Decisions</dt><dd>{policy?.decision_count??usage.decision_count}</dd><dt>Input tokens</dt><dd>{usage.input_tokens.toLocaleString()}</dd><dt>Output tokens</dt><dd>{usage.output_tokens.toLocaleString()}</dd><dt>Estimated cost</dt><dd>${usage.estimated_cost_usd.toFixed(6)}</dd><dt>Accounted cost</dt><dd>${usage.accounted_cost_usd.toFixed(6)}</dd></dl></details>}
      {status&&<details className="details-block"><summary>Budget & connection</summary><p>${status.spent_usd.toFixed(4)} accounted against the ${status.spend_limit_usd.toFixed(2)} phase limit. Each run is limited to ${(status.max_run_usd??.30).toFixed(2)}. Application accounting is not a verified AWS billing statement.</p><p>{status.available?'Bedrock is configured.':status.error??'Bedrock is unavailable.'}</p><dl className="metadata"><dt>Model</dt><dd><code>{status.model_id}</code></dd><dt>Region</dt><dd>{status.region}</dd></dl></details>}
    </div>}
  </div>
}
