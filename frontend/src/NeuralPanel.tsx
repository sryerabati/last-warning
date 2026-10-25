import {useEffect, useRef, useState} from 'react'
import {PixelIcon} from './pixel-ui/PixelIcon'
import {CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis} from 'recharts'
import {api, payload} from './api'
import type {Analysis, NeuralDifference, Stimulus, Warning} from './types'

type TextAnalysis = Analysis & {warning_text_hash?: string}
type Props = {
  warning: Warning | null
  analyses: Analysis[]
  stimuli: Stimulus[]
  refresh: () => Promise<void>
  report: (message: string, error?: boolean) => void
  onAnalysis?: (analysis: Analysis) => void
  saveWarning?: (warning: Warning) => Promise<Warning>
}

export default function NeuralPanel({warning, analyses, stimuli, refresh, report, onAnalysis, saveWarning}: Props) {
  const [fingerprint, setFingerprint] = useState<{text: string; hash: string} | null>(null)
  const [selectedId, setSelectedId] = useState('')
  const [stimulusId, setStimulusId] = useState('')
  const [otherId, setOtherId] = useState('')
  const [externalId, setExternalId] = useState('')
  const [difference, setDifference] = useState<NeuralDifference | null>(null)
  const [metadata, setMetadata] = useState<File | null>(null)
  const [artifact, setArtifact] = useState<File | null>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const context = useRef({id: warning?.id, text: warning?.text})
  context.current = {id: warning?.id, text: warning?.text}

  useEffect(() => {
    let cancelled = false
    setDifference(null)
    setOtherId('')
    setError('')
    setMetadata(null)
    setArtifact(null)
    if (!warning) {setFingerprint(null); return}
    const text = warning.text
    void crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)).then(buffer => {
      if (!cancelled) setFingerprint({text, hash: Array.from(new Uint8Array(buffer), n => n.toString(16).padStart(2, '0')).join('')})
    }).catch(() => {if (!cancelled) setFingerprint(null)})
    return () => {cancelled = true}
  }, [warning?.id, warning?.text])

  const hash = fingerprint?.text === warning?.text ? fingerprint?.hash : null
  const matches = analyses.filter((analysis: TextAnalysis) => warning && hash
    && analysis.warning_id === warning.id && analysis.provenance === 'REAL_TRIBE'
    && analysis.model_id === 'facebook/tribev2-mini'
    && analysis.warning_text_hash === hash && analysis.stimulus_hash === hash
    && analysis.sampling_information.stimulus_protocol === 'controlled_word_reading_v1'
    && analysis.sampling_information.words_per_second === 2.5)
  const analysis = matches.find(value => value.id === selectedId) ?? matches[0]
  const registered = stimuli.filter(value => value.warning_id === warning?.id)
  const stimulus = registered.find(value => value.id === stimulusId)
    ?? registered.find(value => value.sha256 === hash) ?? registered[0]
  const comparable = analyses.filter(value => analysis && value.id !== analysis.id
    && value.provenance === 'REAL_TRIBE' && value.model_id === analysis.model_id
    && value.model_revision === analysis.model_revision && value.code_revision === analysis.code_revision)
  const other = comparable.find(value => value.id === otherId)
  const externalAnalyses = analyses.filter((value: TextAnalysis) => value.warning_id === warning?.id
    && value.warning_text_hash === hash && !matches.some(match => match.id === value.id))
  const external = externalAnalyses.find(value => value.id === externalId) ?? externalAnalyses[0]
  const sameWarning = (id: string, text: string) => context.current.id === id && context.current.text === text
  function fail(cause: unknown) {
    const message = cause instanceof Error ? cause.message : 'The request failed. Try again.'
    setError(message)
    report(message, true)
  }

  async function analyze() {
    if (!warning || !hash) return
    const snapshot = warning
    const expectedHash = hash
    setError('')
    setBusy('Computing local predictions…')
    try {
      const savedWarning = saveWarning ? await saveWarning(snapshot)
        : await api<Warning>(`/warnings/${snapshot.id}`, {method: 'PUT', body: payload(snapshot)})
      await refresh()
      const result = await api<{analysis: Analysis; cached: boolean}>('/neural/analyze-warning', {
        method: 'POST', body: JSON.stringify({warning_id: savedWarning.id}),
      })
      await refresh()
      if (result.analysis.stimulus_hash !== expectedHash || (result.analysis as TextAnalysis).warning_text_hash !== expectedHash) {
        throw new Error('The saved warning changed during analysis. Run the current warning again.')
      }
      if (sameWarning(snapshot.id, snapshot.text) || sameWarning(savedWarning.id, snapshot.text)) {
        setSelectedId(result.analysis.id)
        setDifference(null)
        onAnalysis?.(result.analysis)
        report(result.cached ? 'Predictions loaded for this exact warning.' : 'Local TRIBE Mini predictions saved.')
      } else report('Predictions saved for the previous warning text.')
    } catch (cause) {fail(cause)} finally {setBusy('')}
  }

  async function register(file: File) {
    if (!warning) return
    const snapshot = warning
    if (!file.size || file.size > 32 * 1024 * 1024) {
      fail(new Error('Choose a nonempty stimulus file up to 32 MiB.'))
      return
    }
    setError('')
    setBusy('Registering stimulus…')
    try {
      const savedWarning = saveWarning ? await saveWarning(snapshot)
        : await api<Warning>(`/warnings/${snapshot.id}`, {method: 'PUT', body: payload(snapshot)})
      const form = new FormData()
      form.append('warning_id', savedWarning.id)
      form.append('file', file)
      const saved = await api<Stimulus>('/stimuli', {method: 'POST', body: form})
      await refresh()
      if (sameWarning(snapshot.id, snapshot.text) || sameWarning(savedWarning.id, snapshot.text)) {
        setStimulusId(saved.id)
        report('Stimulus registered.')
      } else report('Stimulus registered for the previous warning text.')
    } catch (cause) {fail(cause)} finally {setBusy('')}
  }

  async function importResults() {
    if (!stimulus || !metadata || !artifact) return
    if (metadata.size > 32000 || !artifact.size || artifact.size > 160 * 1024 * 1024) {
      fail(new Error('Choose metadata up to 32 KB and a nonempty prediction file up to 160 MiB.'))
      return
    }
    setError('')
    setBusy('Validating predictions…')
    try {
      const form = new FormData()
      form.append('stimulus_id', stimulus.id)
      form.append('metadata', await metadata.text())
      form.append('file', artifact)
      const saved = await api<Analysis>('/neural/import', {method: 'POST', body: form})
      await refresh()
      setSelectedId(saved.id)
      setExternalId(saved.id)
      setDifference(null)
      report(saved.stimulus_hash === hash ? 'Predictions validated and imported.' : 'Predictions imported for the registered stimulus.')
    } catch (cause) {fail(cause)} finally {setBusy('')}
  }

  async function compare() {
    if (!analysis || !other || !warning) return
    const snapshot = warning
    setError('')
    setBusy('Comparing predictions…')
    try {
      const result = await api<NeuralDifference>('/neural/compare', {method: 'POST', body: JSON.stringify({
        baseline_analysis_id: analysis.id, alternative_analysis_id: other.id,
      })})
      if (sameWarning(snapshot.id, snapshot.text)) setDifference(result)
    } catch (cause) {fail(cause)} finally {setBusy('')}
  }

  return <section className="neural-panel" aria-label="TRIBE Mini predictions">
    <div className="panel-section">
      <div className="actions">
        <button className="secondary" type="button" disabled={!warning || !hash || !!busy} onClick={() => void analyze()}>
          {busy ? <PixelIcon name="loading" size={15} className="pixel-loading"/> : <PixelIcon name="brain" size={15}/>}
          Analyze current warning
        </button>
        {analysis && <span className="muted">{analysis.prediction_shape[0]} samples · {analysis.prediction_shape[1].toLocaleString()} vertices</span>}
      </div>
      {busy && <p className="muted" role="status">{busy}</p>}
      {error && <p className="muted" role="alert">{error}</p>}
      {!analysis && <p className="muted">{warning ? 'Run this warning to compute its local neural response.' : 'Choose a warning first.'}</p>}
      {analysis && <>
        {matches.length > 1 && <label className="field">Saved response<select name="neural-response" value={analysis.id} disabled={!!busy} onChange={event => {
          setSelectedId(event.target.value); setDifference(null); setOtherId('')
        }}>{matches.map(value => <option key={value.id} value={value.id}>{new Date(value.inference_timestamp).toLocaleString()}</option>)}</select></label>}
        <div className="mini-chart" role="img" aria-label="Predicted mean absolute cortical response over stimulus time">
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={analysis.series} margin={{top: 10, right: 10, bottom: 0, left: -15}}>
              <CartesianGrid vertical={false} stroke="var(--border)"/>
              <XAxis dataKey="time" tick={{fill: 'var(--muted)', fontSize: 10}} unit="s" tickLine={false} axisLine={false}/>
              <YAxis tick={{fill: 'var(--muted)', fontSize: 10}} width={54} tickLine={false} axisLine={false}/>
              <Tooltip contentStyle={{background: 'var(--surface)', border: '2px solid var(--border)', borderRadius: 0, fontSize: 12}}
                labelFormatter={value => `${value}s`} formatter={value => [Number(value).toFixed(5), 'Mean absolute response']}/>
              <Line dataKey="mean_absolute" name="Mean absolute response" stroke="var(--accent)" strokeWidth={2} dot={analysis.series.length === 1 ? ({cx=0,cy=0})=><rect x={Math.round(cx)-3} y={Math.round(cy)-3} width={6} height={6} fill="var(--accent)"/> : false} activeDot={false} isAnimationActive={false}/>
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="actions">
          <a className="text-button" href={`/api/neural/analyses/${analysis.id}/download`} download><PixelIcon name="download" size={13}/> Predictions</a>
          <a className="text-button" href={`/api/neural/analyses/${analysis.id}/metadata`} download={`${analysis.id}-metadata.json`}>Metadata</a>
        </div>
        <details className="details-block"><summary>Model and reading protocol</summary>
          <p className="muted">TRIBE Mini predicts an average subject’s cortical fMRI response. It does not measure fear, comprehension, or evacuation success. Text is presented at 2.5 words per second using defined reading times.</p>
          <dl className="metadata">
            <dt>Model</dt><dd>{analysis.model_id}</dd>
            <dt>Model revision</dt><dd><code>{analysis.model_revision}</code></dd>
            <dt>Code revision</dt><dd><code>{analysis.code_revision}</code></dd>
            <dt>Stimulus SHA-256</dt><dd><code>{analysis.stimulus_hash}</code></dd>
            <dt>Computed</dt><dd>{new Date(analysis.inference_timestamp).toLocaleString()}</dd>
            <dt>Sampling</dt><dd><code>{JSON.stringify(analysis.sampling_information)}</code></dd>
          </dl>
          <p className="muted">{analysis.provenance_note}</p>
          {analysis.notes && <p className="muted">{analysis.notes}</p>}
        </details>
        {comparable.length > 0 && <details className="details-block"><summary>Compare another response</summary>
          <label className="field">Comparison response<select name="comparison-response" value={otherId} disabled={!!busy} onChange={event => {setOtherId(event.target.value); setDifference(null)}}>
            <option value="">Choose a saved response</option>
            {comparable.map(value => <option key={value.id} value={value.id}>{value.warning_id === warning?.id ? warning.name : value.warning_id} · {new Date(value.inference_timestamp).toLocaleString()}</option>)}
          </select></label>
          <button type="button" className="secondary" disabled={!other || !!busy} onClick={() => void compare()}>Compare responses</button>
          {difference && <p className="muted" role="status">{difference.aligned_samples} shared time samples. Mean absolute difference: {difference.mean_absolute_difference.toFixed(5)}.</p>}
        </details>}
      </>}
    </div>
    <details className="details-block"><summary>Import external predictions</summary>
      <p className="muted">Register the original text, audio, or video, then import its matching metadata and prediction file.</p>
      <label className="field">Original stimulus<input type="file" name="original-stimulus" disabled={!warning || !!busy}
        accept=".txt,.wav,.mp3,.flac,.ogg,.mp4,.avi,.mkv,.mov,.webm" onChange={event => {
          const file = event.target.files?.[0]
          if (file) void register(file)
          event.target.value = ''
        }}/></label>
      <label className="field">Registered stimulus<select name="registered-stimulus" value={stimulus?.id ?? ''} disabled={!!busy} onChange={event => setStimulusId(event.target.value)}>
        {!registered.length && <option value="">Register a stimulus first</option>}
        {registered.map(value => <option key={value.id} value={value.id}>{value.filename} · {value.sha256.slice(0, 8)}</option>)}
      </select></label>
      <div className="form-grid">
        <label className="field">Metadata JSON<input type="file" name="prediction-metadata" accept=".json" disabled={!!busy} onChange={event => setMetadata(event.target.files?.[0] ?? null)}/></label>
        <label className="field">Predictions NPZ<input type="file" name="prediction-artifact" accept=".npz" disabled={!!busy} onChange={event => setArtifact(event.target.files?.[0] ?? null)}/></label>
      </div>
      <button type="button" className="secondary" disabled={!!busy || !stimulus || !metadata || !artifact} onClick={() => void importResults()}><PixelIcon name="upload" size={14}/> Validate and import</button>
      {stimulus && <a className="text-button" href={`/api/stimuli/${stimulus.id}/download`} download>Download original stimulus</a>}
      <p className="muted">Original files up to 32 MiB. Imports retain their declared source; only an exact text match appears with the current warning.</p>
      {external && <details className="details-block"><summary>Saved external analyses</summary>
        <label className="field">External analysis<select name="external-analysis" value={external.id} disabled={!!busy} onChange={event => setExternalId(event.target.value)}>
          {externalAnalyses.map(value => <option key={value.id} value={value.id}>{value.model_id} · {new Date(value.inference_timestamp).toLocaleString()}</option>)}
        </select></label>
        <p className="muted">{external.provenance === 'TEST_FIXTURE' ? 'Synthetic test fixture. These are not TRIBE predictions.' : 'Imported predictions for the registered stimulus.'}</p>
        <dl className="metadata">
          <dt>Output</dt><dd>{external.prediction_shape[0]} samples × {external.prediction_shape[1].toLocaleString()} vertices</dd>
          <dt>Model</dt><dd>{external.model_id}</dd>
          <dt>Model revision</dt><dd><code>{external.model_revision}</code></dd>
          <dt>Code revision</dt><dd><code>{external.code_revision}</code></dd>
          <dt>Stimulus SHA-256</dt><dd><code>{external.stimulus_hash}</code></dd>
          <dt>Sampling</dt><dd><code>{JSON.stringify(external.sampling_information)}</code></dd>
        </dl>
        <p className="muted">{external.provenance_note}</p>
        {external.notes && <p className="muted">{external.notes}</p>}
        <div className="actions">
          <a className="text-button" href={`/api/neural/analyses/${external.id}/download`} download><PixelIcon name="download" size={13}/> Predictions</a>
          <a className="text-button" href={`/api/neural/analyses/${external.id}/metadata`} download={`${external.id}-metadata.json`}>Metadata</a>
        </div>
      </details>}
    </details>
  </section>
}
