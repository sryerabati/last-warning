"""Prepare the Sites client from the existing simulator without local inference UI."""
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "sites" / "last-warning"
source = ROOT / "frontend" / "src"
target = SITE / "ui"
shutil.copytree(source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("main.tsx", "NeuralPanel.tsx"))
shutil.copytree(ROOT / "frontend" / "public", SITE / "public", dirs_exist_ok=True)

path = target / "App.tsx"
text = path.read_text()
text = text.replace("import NeuralPanel from './NeuralPanel'\n", "")
text = text.replace("AgentStatus, Analysis,", "AgentStatus,").replace("Scenario, Stimulus,", "Scenario,")
text = text.replace("|'neural'", "")
text = re.sub(r"^  const \[analyses,setAnalyses\].*\n", "", text, flags=re.M)
text = re.sub(r"^  const \[includeNeural,setIncludeNeural\].*\n", "", text, flags=re.M)
text = text.replace("const [fingerprint,setFingerprint]=useState<{text:string;hash:string}|null>(null),[busy,setBusy]", "const [busy,setBusy]")
text = re.sub(r"^  const textHash=.*\n", "", text, flags=re.M)
text = text.replace("const [s,w,r,a,st,c,health]", "const [s,w,r,c,health]")
text = text.replace("api<Analysis[]>('/neural/analyses',options),api<Stimulus[]>('/stimuli',options),", "")
text = text.replace(";setAnalyses(a);setStimuli(st)", "")
text = re.sub(r"  useEffect\(\(\)=>\{\n    let live=true\n    if\(warning\).*?\n  \},\[warning\?\.text\]\)\n", "", text, flags=re.S)
text = re.sub(r"^  const (exactAnalysis|viewedAnalysis|linkedAnalysis)=.*\n", "", text, flags=re.M)
text = text.replace("setCoupling(false);", "").replace(";setCoupling(false)", "")
text = text.replace("value.stage==='neural'?'Computing the local Mini response':value.stage==='neural_queued'?'Waiting for local Mini':", "")
text = text.replace("analyze_warning:includeNeural,coupling_strength:includeNeural&&coupling&&decisionMode==='rules'?strength:0", "analyze_warning:false,coupling_strength:0")
text = text.replace("neural:'TRIBE Mini',", "")
text = text.replace("&&(!includeNeural||wordCount<=200)", "")
text = text.replace("job.stage==='neural'||job.stage==='neural_queued'?'Local warning analysis':", "")
text = re.sub(r'<button className="brief-neural".*?</button>', "", text)
text = re.sub(r"^.*<button onClick=\{\(\)=>openDrawer\('neural'\)\}.*\n", "", text, flags=re.M)
text = text.replace("notice?.error&&drawer!=='neural'", "notice?.error")
text = text.replace("<span>{includeNeural?'Local Mini included':'Mini analysis off'}</span>", "<span>{decisionMode==='bedrock'?'Bedrock resident decisions':'Rules baseline'}</span>")
text = re.sub(r"^.*\{includeNeural&&wordCount>200.*\n", "", text, flags=re.M)
text = re.sub(r'<button className="secondary" onClick=\{\(\)=>openDrawer\(\'neural\'\)\}.*?</button>', "", text)
text = re.sub(r"^      \{drawer==='neural'.*?^      \{drawer==='history'", "      {drawer==='history'", text, flags=re.M | re.S)
assert not any(value in text for value in ["includeNeural", "setCoupling", "linkedAnalysis", "NeuralPanel", "setFingerprint", "openDrawer('neural')"])
path.write_text(text)
sources = target / "pixel-ui" / "SourcesPanel.tsx"
text = sources.read_text()
text = re.sub(r"^      <h3>Local TRIBE Mini</h3>.*\n", "", text, flags=re.M)
sources.write_text(text)

package = json.loads((SITE / "package.json").read_text())
package["name"] = "last-warning-site"
package["dependencies"]["pixi.js"] = "8.22.0"
(SITE / "package.json").write_text(json.dumps(package, indent=2) + "\n")
(SITE / "app" / "page.tsx").write_text('import Simulator from "./simulator";\n\nexport default function Page() { return <Simulator />; }\n')
(SITE / "app" / "simulator.tsx").write_text('"use client";\nimport {useEffect, useState} from "react";\nimport type {ComponentType} from "react";\n\nexport default function Simulator() {\n  const [App, setApp] = useState<ComponentType | null>(null);\n  useEffect(() => { let active = true; void import("../ui/App").then(module => { if (active) setApp(() => module.default); }); return () => { active = false; }; }, []);\n  return App ? <App /> : <div role="status" style={{padding: 32, fontFamily: "monospace"}}>Opening Last Warning…</div>;\n}\n')
(SITE / "app" / "layout.tsx").write_text('import type {Metadata} from "next";\nimport "../ui/style.css";\n\nexport const metadata: Metadata = {title: "Last Warning", description: "A living pixel-art campus simulator with Amazon Bedrock resident decisions.", icons: {icon: "/favicon.svg"}};\nexport default function RootLayout({children}: Readonly<{children: React.ReactNode}>) { return <html lang="en"><body>{children}</body></html>; }\n')
print("Prepared existing simulator UI with local inference controls removed.")
