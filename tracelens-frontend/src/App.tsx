import { useCallback, useEffect, useMemo, useState } from 'react'
import { Activity, BrainCircuit, AlertCircle, AlertTriangle, ArrowDownRight, ArrowRight, ArrowUpRight, Boxes, Check, CheckCircle2, ChevronDown, CircleHelp, Clock3, Code2, Database, ExternalLink, FileSearch, GitCompareArrows, Layers3, LoaderCircle, Menu, Plus, RefreshCw, Search, Settings2, ShieldCheck, Terminal, Trash2, Download, X, Pencil, Copy, RotateCcw } from 'lucide-react'

// API response models are kept near the app shell so UI rendering stays type-safe.
type Project = { project_id: string; name: string; description?: string; framework?: string; created_at?: string }
type Run = { run_id: string; project_id: string; scenario: string; version?: string; status: string; baseline_run_id?: string | null; created_at?: string; metadata?: Record<string, unknown> }
type EventItem = { event_id: string; run_id: string; step: string; event_type: string; status: string; timestamp?: string; duration_ms?: number | null; payload?: Record<string, unknown>; error?: string | null; source_file?: string | null; source_line?: number | null }
type Finding = { finding_id: string; run_id: string; baseline_run_id?: string; rule_id: string; severity: string; title: string; explanation?: string; evidence_event_ids?: string[]; recommended_action?: string; created_at?: string }
type Investigation = { investigation_id: string; run_id: string; title: string; likely_cause: string; confidence: string; first_failure_event_id?: string|null; last_confirmed_event_id?: string|null; evidence_event_ids: string[]; timeline: {event_id?:string;timestamp?:string;step?:string;status?:string;event_type?:string;duration_ms?:number|null;error?:string;explanation?:string}[]; history_context?: {other_runs_considered:number;successful_runs:number;failed_runs:number;comparison_note:string}; historical_comparison?: string; ai_historical_commentary?: string; historical_differences?: {baseline_run_ids?:string[]; history_used?:boolean; uncomparable_fields?:{field:string;current_value:unknown;historical_run_id:string;reason:string}[]; endpoint_differences?:{field:string;current_value:unknown;historical_value:unknown;historical_run_id:string;historical_event_ids?:string[];current_event_ids?:string[]}[]; comparisons?:{run_id:string;status?:string;version?:string;scenario?:string;field_differences?:{field:string;current_value:unknown;historical_value:unknown;historical_run_id:string;historical_event_ids?:string[];current_event_ids?:string[]}[];missing_stages?:string[];additional_stages?:string[];stage_status_changes?:{stage:string;current_status:string;historical_status:string}[]}[]}; alternative_explanations: string[]; recommended_actions: string[]; limitations: string[]; analysis_method: string; model?: string; ai_status?: string; ai_fallback_reason?: string; ai_error_type?: string; created_at?: string }
type CompareResult = { baseline: {run_id:string;scenario:string;status:string}; current: {run_id:string;scenario:string;status:string}; event_counts: {baseline:number;current:number}; findings: Finding[] }
const initialApi = localStorage.getItem('tracelens-api-url') || 'http://127.0.0.1:8000'
const dateText = (v?: string) => v ? new Date(v).toLocaleString() : '—'
const shortId = (v?: string) => v ? (v.length > 20 ? `${v.slice(0, 17)}…` : v) : '—'
const severityClass = (v?: string) => `severity ${String(v || 'info').toLowerCase()}`

/** Main dashboard shell: owns API state, selected project/run, and page navigation. */
function App() {
  const [apiUrl, setApiUrl] = useState(initialApi)
  const [apiDraft, setApiDraft] = useState(initialApi)
  const [health, setHealth] = useState<'checking'|'online'|'offline'>('checking')
  const [dbName, setDbName] = useState('MongoDB status unknown')
  const [projects, setProjects] = useState<Project[]>([])
  const [runs, setRuns] = useState<Run[]>([])
  const [findings, setFindings] = useState<Finding[]>([])
  const [selectedProject, setSelectedProject] = useState('')
  const [selectedRun, setSelectedRun] = useState('')
  const [events, setEvents] = useState<EventItem[]>([])
  const [activeTab, setActiveTab] = useState('Overview')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [showCreateProject, setShowCreateProject] = useState(false)
  const [showEditProject, setShowEditProject] = useState(false)
  const [projectName, setProjectName] = useState('')
  const [projectDescription, setProjectDescription] = useState('')
  const [framework, setFramework] = useState('python')
  const [baselineId, setBaselineId] = useState('')
  const [currentId, setCurrentId] = useState('')
  const [comparison, setComparison] = useState<CompareResult|null>(null)
  const [investigation, setInvestigation] = useState<Investigation|null>(null)
  const [investigationLoading, setInvestigationLoading] = useState(false)
  const [investigationError, setInvestigationError] = useState('')
  const [investigationHistory, setInvestigationHistory] = useState<Investigation[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [findingFilter, setFindingFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [mobileNav, setMobileNav] = useState(false)

  // Centralize API errors and JSON handling so every screen reports failures consistently.
  const request = useCallback(async <T,>(path: string, init?: RequestInit): Promise<T> => {
    const response = await fetch(`${apiUrl.replace(/\/$/, '')}${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) } })
    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`
      try { const body = await response.json(); detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body) } catch { /* response may not be JSON */ }
      throw new Error(detail)
    }
    return response.json() as Promise<T>
  }, [apiUrl])

  // Refresh workspace data from the backend; `quiet` avoids replacing the page with a spinner.
  const refresh = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true)
    setError('')
    try {
      const h = await request<{status:string;database?:string;database_name?:string}>('/health')
      setHealth(h.status === 'ok' && h.database === 'connected' ? 'online' : 'offline')
      setDbName(h.database_name || 'Database connected')
      const ps = await request<Project[]>('/api/projects')
      setProjects(ps)
      const projectId = selectedProject && ps.some(p => p.project_id === selectedProject) ? selectedProject : ps[0]?.project_id || ''
      if (projectId !== selectedProject) setSelectedProject(projectId)
      const rs = projectId ? await request<Run[]>(`/api/projects/${encodeURIComponent(projectId)}/runs`) : []
      setRuns(rs)
      const fs = await Promise.all(rs.slice(0, 30).map(async r => {
        try { return await request<Finding[]>(`/api/runs/${encodeURIComponent(r.run_id)}/findings`) } catch { return [] }
      }))
      setFindings(fs.flat().sort((a,b) => (b.created_at || '').localeCompare(a.created_at || '')))
      if (selectedRun && !rs.some(r => r.run_id === selectedRun)) setSelectedRun('')
      if (health === 'offline') setHealth('online')
    } catch (e) {
      setHealth('offline')
      setDbName('Backend or database unavailable')
      setError(e instanceof Error ? e.message : 'Could not connect to TraceLens API')
    } finally { if (!quiet) setLoading(false) }
  }, [request, selectedProject, selectedRun, health])

  useEffect(() => { void refresh() }, [apiUrl])
  useEffect(() => {
    if (!selectedProject) { setRuns([]); return }
    let alive = true
    request<Run[]>(`/api/projects/${encodeURIComponent(selectedProject)}/runs`).then(v => { if (alive) setRuns(v) }).catch(e => { if (alive) setError(e instanceof Error ? e.message : 'Could not load runs') })
    return () => { alive = false }
  }, [selectedProject, request])
  useEffect(() => {
    if (!selectedRun) { setEvents([]); return }
    let alive = true
    request<EventItem[]>(`/api/runs/${encodeURIComponent(selectedRun)}/events`).then(v => { if (alive) setEvents(v) }).catch(e => { if (alive) setError(e instanceof Error ? e.message : 'Could not load events') })
    return () => { alive = false }
  }, [selectedRun, request])

  const visibleRuns = useMemo(() => runs.filter(r => `${r.scenario} ${r.run_id} ${r.status}`.toLowerCase().includes(query.toLowerCase())), [runs, query])
  const highFindings = findings.filter(f => ['high','critical'].includes(f.severity.toLowerCase())).length
  const visibleFindings = findings.filter(f => findingFilter === 'all' || f.severity.toLowerCase() === findingFilter)
  const failedRuns = runs.filter(r => r.status === 'failed').length
  const totalEvents = events.length
  const selectedRunInfo = runs.find(r => r.run_id === selectedRun)

  // Project creation is explicit user action; normal app startup must never create projects.
  async function createProject(e: React.FormEvent) {
    e.preventDefault(); setError(''); setLoading(true)
    try {
      const p = await request<Project>('/api/projects', { method:'POST', body: JSON.stringify({ name: projectName, description: projectDescription, framework }) })
      setProjects(prev => [p, ...prev]); setSelectedProject(p.project_id); setProjectName(''); setProjectDescription(''); setFramework('python'); setShowCreateProject(false); setActiveTab('Projects')
      await refresh(true)
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not create project') } finally { setLoading(false) }
  }
  async function updateProject(e: React.FormEvent) {
    e.preventDefault()
    const project = projects.find(p => p.project_id === selectedProject)
    if (!project) return
    setError(''); setLoading(true)
    try {
      const updated = await request<Project>(`/api/projects/${encodeURIComponent(project.project_id)}`, { method: 'PATCH', body: JSON.stringify({ name: projectName.trim(), description: projectDescription.trim(), framework }) })
      setProjects(prev => prev.map(p => p.project_id === updated.project_id ? updated : p))
      setShowEditProject(false)
      await refresh(true)
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not update project') }
    finally { setLoading(false) }
  }

  async function renameSelectedRun() {
    const run = runs.find(item => item.run_id === selectedRun)
    if (!run) { setError('Select a run before renaming it.'); return }
    const nextName = window.prompt('New display name for this run:', run.scenario)
    if (nextName === null) return
    if (!nextName.trim()) { setError('Run name cannot be empty.'); return }
    setError(''); setLoading(true)
    try {
      await request(`/api/runs/${encodeURIComponent(run.run_id)}/details`, { method: 'PATCH', body: JSON.stringify({ scenario: nextName.trim() }) })
      await refresh(true)
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not rename run') }
    finally { setLoading(false) }
  }

  async function duplicateSelectedProject() {
    const project = projects.find(p => p.project_id === selectedProject)
    if (!project) { setError('Select a project to duplicate.'); return }
    setError(''); setLoading(true)
    try {
      const copy = await request<Project>('/api/projects', { method: 'POST', body: JSON.stringify({ name: `${project.name} (copy)`, description: project.description || '', framework: project.framework || 'python' }) })
      setProjects(prev => [copy, ...prev.filter(p => p.project_id !== copy.project_id)])
      setSelectedProject(copy.project_id)
      setSelectedRun(''); setEvents([]); setInvestigation(null); setInvestigationHistory([]); setComparison(null)
      await refresh(true)
      setActiveTab('Projects')
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not duplicate project') }
    finally { setLoading(false) }
  }

  async function copySelectedProjectId() {
    const project = projects.find(p => p.project_id === selectedProject)
    if (!project) return
    try { await navigator.clipboard.writeText(project.project_id); setError(''); }
    catch { setError(`Clipboard access was blocked. Project ID: ${project.project_id}`) }
  }

  async function deleteProject(project: Project) {
    const confirmed = window.confirm(`Delete project "${project.name}" and all of its runs, events, findings, and investigations? This cannot be undone.`)
    if (!confirmed) return
    setError(''); setLoading(true)
    try {
      await request<{status:string}>(`/api/projects/${encodeURIComponent(project.project_id)}`, { method: 'DELETE' })
      if (selectedProject === project.project_id) {
        setSelectedProject(''); setSelectedRun(''); setEvents([]); setRuns([])
        setFindings([]); setInvestigation(null); setInvestigationHistory([]); setComparison(null)
      }
      await refresh(true)
      setActiveTab('Projects')
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not delete project') }
    finally { setLoading(false) }
  }

  async function deleteSelectedRun() {
    const run = runs.find(item => item.run_id === selectedRun)
    if (!run) { setError('Select a run before deleting it.'); return }
    const confirmed = window.confirm(`Delete run "${run.scenario}" (${run.run_id}) and its events, findings, and investigations? This cannot be undone.`)
    if (!confirmed) return
    setError(''); setLoading(true)
    try {
      await request<{status:string}>(`/api/runs/${encodeURIComponent(run.run_id)}`, { method: 'DELETE' })
      setSelectedRun(''); setEvents([]); setInvestigation(null); setInvestigationError('')
      setInvestigationHistory(prev => prev.filter(item => item.run_id !== run.run_id))
      setComparison(null)
      await refresh(true)
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not delete run') }
    finally { setLoading(false) }
  }

  function exportSelectedEvents() {
    if (!selectedRun || events.length === 0) { setError('Select a run with recorded events before exporting.'); return }
    const run = runs.find(item => item.run_id === selectedRun)
    const payload = { exported_at: new Date().toISOString(), project_id: selectedProject, run, events }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `tracelens-${selectedRun}-events.json`
    document.body.appendChild(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url)
  }

  // Compare two selected executions and keep the backend's evidence-linked findings intact.
  async function compareRuns(e: React.FormEvent) {
    e.preventDefault(); setError(''); setComparison(null); setLoading(true)
    try { const result = await request<CompareResult>('/api/runs/compare', { method:'POST', body: JSON.stringify({ baseline_run_id: baselineId, current_run_id: currentId }) }); setComparison(result); setActiveTab('Compare'); await refresh(true) }
    catch (err) { setError(err instanceof Error ? err.message : 'Comparison failed') } finally { setLoading(false) }
  }
  // Ask the RCA endpoint to analyze the selected run and preserve the returned report for review.
  async function investigateRun() {
    if (!selectedRun) return
    setInvestigationLoading(true); setInvestigationError(''); setInvestigation(null)
    try { const result = await request<Investigation>(`/api/runs/${encodeURIComponent(selectedRun)}/investigate`, { method:'POST' }); setInvestigation(result) }
    catch (err) { setInvestigationError(err instanceof Error ? err.message : 'Investigation failed') }
    finally { setInvestigationLoading(false) }
  }
  function saveApiUrl(e: React.FormEvent) { e.preventDefault(); const clean = apiDraft.trim().replace(/\/$/, ''); setApiUrl(clean); localStorage.setItem('tracelens-api-url', clean); setShowSettings(false) }

  // Load persisted investigations only when History is opened; ignore stale responses on navigation.
  useEffect(() => {
    if (activeTab !== 'History' || !selectedProject) return
    let alive = true
    setHistoryLoading(true)
    Promise.all(runs.slice(0, 30).map(async r => {
      try { return await request<Investigation[]>(`/api/runs/${encodeURIComponent(r.run_id)}/investigations`) } catch { return [] }
    })).then(groups => {
      if (alive) setInvestigationHistory(groups.flat().sort((a,b) => (b.created_at || '').localeCompare(a.created_at || '')))
    }).finally(() => { if (alive) setHistoryLoading(false) })
    return () => { alive = false }
  }, [activeTab, selectedProject, runs, request])

  const nav = [
    {name:'Overview', icon:Layers3}, {name:'Projects', icon:Boxes}, {name:'Runs', icon:Activity}, {name:'Compare', icon:GitCompareArrows}, {name:'Findings', icon:FileSearch}, {name:'History', icon:Clock3}, {name:'Events', icon:Terminal}
  ]
  // Page content is selected from local navigation state; reusable UI primitives live below App.
  return <div className="app-shell">
    <aside className={`sidebar ${mobileNav ? 'open' : ''}`}>
      <div className="brand"><div className="brand-mark"><Activity size={21}/></div><div><div className="brand-name">TraceLens</div><div className="brand-sub">AI TRACE OBSERVATORY</div></div><button className="icon-btn mobile-close" onClick={() => setMobileNav(false)} aria-label="Close menu"><X size={18}/></button></div>
      <div className="workspace-label">WORKSPACE</div><div className="workspace-select"><div className="workspace-icon">TL</div><div className="workspace-copy"><strong>Local workspace</strong><span>Personal environment</span></div><ChevronDown size={15}/></div>
      <div className="nav-label">MONITOR</div><nav>{nav.map(item => {const Icon=item.icon; return <button key={item.name} className={`nav-item ${activeTab===item.name?'active':''}`} onClick={() => {setActiveTab(item.name);setMobileNav(false)}}><Icon size={17}/><span>{item.name}</span>{item.name==='Findings'&&highFindings>0&&<span className="nav-count">{highFindings}</span>}</button>})}</nav>
      <div className="sidebar-bottom"><div className="side-health"><span className={`health-dot ${health}`}/><div><strong>{health==='online'?'API connected':health==='checking'?'Checking API':'API offline'}</strong><span>{health==='online'?dbName:apiUrl}</span></div></div><button className="nav-item" onClick={() => {setApiDraft(apiUrl);setShowSettings(true)}}><Settings2 size={17}/><span>Settings</span></button><div className="version">TRACELENS · MVP <span>v0.5.5</span></div></div>
    </aside>
    {mobileNav && <button className="mobile-scrim" aria-label="Close navigation" onClick={() => setMobileNav(false)}/>}
    <main className="main-area">
      <header className="topbar"><div className="topbar-left"><button className="icon-btn mobile-menu" onClick={() => setMobileNav(true)} aria-label="Open menu"><Menu size={19}/></button><div className="breadcrumb">TraceLens <span>/</span> <strong>{activeTab}</strong></div></div><div className="top-actions"><div className={`connection-pill ${health}`}><span className="health-dot"/>{health==='online'?'Connected':health==='checking'?'Checking':'Disconnected'}</div><button className="icon-btn" onClick={() => void refresh()} aria-label="Refresh" title="Refresh data"><RefreshCw size={17} className={loading?'spin':''}/></button><button className="icon-btn" onClick={() => setShowSettings(true)} aria-label="Settings" title="API settings"><Settings2 size={17}/></button><div className="avatar">TL</div></div></header>
      <div className="page-wrap">
        {error && <div className="alert error-alert"><AlertCircle size={18}/><div><strong>Something needs attention</strong><p>{error}</p>{health==='offline'&&<small>Check that FastAPI is running and MongoDB readiness returns healthy.</small>}</div><button className="icon-btn" onClick={() => setError('')} aria-label="Dismiss"><X size={16}/></button></div>}
        {health==='offline' && <div className="connect-banner"><div className="banner-icon"><Database size={20}/></div><div className="banner-copy"><strong>Connect to your TraceLens backend</strong><span>Start FastAPI at 127.0.0.1:8000 and verify MongoDB readiness, or configure another API URL.</span></div><button className="button secondary" onClick={() => setShowSettings(true)}>Configure API <ArrowRight size={15}/></button></div>}
        {activeTab==='Overview' && <>
          <div className="page-heading"><div><div className="eyebrow">EXECUTION INTELLIGENCE</div><h1>Pipeline overview<span className="heading-period">.</span></h1><p>Observe RAG execution, compare historical runs, and investigate evidence-backed diagnostic findings.</p></div><div className="heading-actions"><button className="button secondary" onClick={() => setActiveTab('Compare')}><GitCompareArrows size={16}/> Compare runs</button><button className="button primary" onClick={() => setShowCreateProject(true)}><Plus size={16}/> New project</button></div></div>
          <div className="stat-grid"><Stat icon={<Boxes size={18}/>} label="Projects" value={projects.length} note="Registered applications" tone="blue"/><Stat icon={<Activity size={18}/>} label="Runs tracked" value={runs.length} note="Selected project" tone="violet"/><Stat icon={<AlertTriangle size={18}/>} label="High severity" value={highFindings} note="Findings in recent runs" tone="orange"/><Stat icon={<ShieldCheck size={18}/>} label="Failed runs" value={failedRuns} note="Explicit execution failures" tone="red"/></div>
          <div className="content-grid"><section className="panel runs-panel"><div className="panel-heading"><div><h2>Recent runs</h2><p>Latest executions for the selected project</p></div><button className="text-button" onClick={() => setActiveTab('Runs')}>View all <ArrowRight size={14}/></button></div><div className="filter-row"><div className="select-wrap"><Layers3 size={15}/><select value={selectedProject} onChange={e=>setSelectedProject(e.target.value)} aria-label="Selected project">{projects.length===0&&<option value="">No projects yet</option>}{projects.map(p=><option value={p.project_id} key={p.project_id}>{p.name}</option>)}</select><ChevronDown size={14}/></div><div className="search-box"><Search size={15}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Filter runs..."/></div></div><RunTable runs={visibleRuns.slice(0,7)} onSelect={r=>{setSelectedRun(r.run_id);setActiveTab('Events')}} selectedRun={selectedRun}/>{visibleRuns.length===0&&<EmptyState title="No runs found" detail={projects.length?'Run one of your RAG demos to populate this table.':'Create a project and run a RAG demo to get started.'} icon={<Activity size={21}/>}/>}</section>
            <section className="panel findings-panel"><div className="panel-heading"><div><h2>Latest findings</h2><p>Rule-based regression signals</p></div><button className="text-button" onClick={() => setActiveTab('Findings')}>View all <ArrowRight size={14}/></button></div>{findings.slice(0,5).map(f=><FindingRow key={f.finding_id} finding={f} onClick={()=>{setSelectedRun(f.run_id);setActiveTab('Findings')}}/>)}{findings.length===0&&<EmptyState title="No findings yet" detail="Compare a baseline and current run to generate diagnostic findings." icon={<FileSearch size={21}/>}/>}</section></div>
          <div className="bottom-grid"><section className="panel"><div className="panel-heading"><div><h2>Observation pipeline</h2><p>How supported framework events flow into TraceLens diagnostics</p></div><span className="mini-label">LIVE ARCHITECTURE</span></div><div className="pipeline-flow"><PipelineNode icon={<Code2 size={17}/>} title="RAG application" sub="LangChain or custom"/><ArrowRight className="pipeline-arrow" size={17}/><PipelineNode icon={<Activity size={17}/>} title="TraceLens SDK" sub="Automatic callbacks"/><ArrowRight className="pipeline-arrow" size={17}/><PipelineNode icon={<Layers3 size={17}/>} title="FastAPI" sub="Compare + diagnose"/><ArrowRight className="pipeline-arrow" size={17}/><PipelineNode icon={<Database size={17}/>} title="MongoDB" sub="Persistent records"/></div></section><section className="panel quick-panel"><div className="panel-heading"><div><h2>Quick actions</h2><p>Continue your workflow</p></div></div><button className="quick-action" onClick={()=>setShowCreateProject(true)}><span className="quick-icon blue"><Plus size={17}/></span><span><strong>Create a project</strong><small>Register an instrumented application</small></span><ArrowRight size={16}/></button><button className="quick-action" onClick={()=>setActiveTab('Compare')}><span className="quick-icon violet"><GitCompareArrows size={17}/></span><span><strong>Compare two runs</strong><small>Find execution and retrieval regressions</small></span><ArrowRight size={16}/></button><button className="quick-action" onClick={()=>setActiveTab('Events')}><span className="quick-icon green"><Terminal size={17}/></span><span><strong>Inspect trace events</strong><small>Review step timings and metadata</small></span><ArrowRight size={16}/></button></section></div>
        </>}
        {activeTab==='Projects' && <><PageTitle eyebrow="WORKSPACE" title="Projects" description="Manage applications instrumented with the TraceLens SDK." action={<><div className="select-wrap"><Layers3 size={15}/><select value={selectedProject} onChange={e=>setSelectedProject(e.target.value)} aria-label="Selected project for actions"><option value="">Select project</option>{projects.map(p=><option key={p.project_id} value={p.project_id}>{p.name}</option>)}</select><ChevronDown size={14}/></div><button className="button secondary" disabled={!selectedProject||loading} onClick={()=>{const p=projects.find(p=>p.project_id===selectedProject);if(p){setProjectName(p.name);setProjectDescription(p.description||'');setFramework(p.framework||'python');setShowEditProject(true)}}}><Pencil size={15}/> Edit / rename</button><button className="button secondary" disabled={!selectedProject||loading} onClick={()=>void duplicateSelectedProject()}><Copy size={15}/> Duplicate</button><button className="button secondary" disabled={!selectedProject} onClick={()=>void copySelectedProjectId()}><Copy size={15}/> Copy ID</button><button className="button secondary danger-button" disabled={!selectedProject||loading} onClick={()=>{const project=projects.find(p=>p.project_id===selectedProject);if(project)void deleteProject(project)}}><Trash2 size={15}/> Delete project</button><button className="button primary" onClick={()=>setShowCreateProject(true)}><Plus size={16}/> New project</button></>}/><div className="project-grid">{projects.map(p=><button className="project-card" key={p.project_id} onClick={()=>{setSelectedProject(p.project_id);setActiveTab('Runs')}}><div className="project-card-top"><span className="project-icon"><Boxes size={20}/></span><span className="framework-chip">{p.framework||'python'}</span></div><h3>{p.name}</h3><p>{p.description||'No description provided.'}</p><div className="project-card-bottom"><span>{shortId(p.project_id)}</span><span>Open project <ArrowRight size={14}/></span></div></button>)}{projects.length===0&&<EmptyState title="Your workspace is empty" detail="Create your first project, then run a RAG demo with the TraceLens SDK." icon={<Boxes size={22}/>}/>}</div></>}
        {activeTab==='Runs' && <><PageTitle eyebrow="EXECUTION HISTORY" title="Runs" description="Inspect run status, scenarios, and baseline relationships." action={<><div className="select-wrap"><Layers3 size={15}/><select value={selectedProject} onChange={e=>setSelectedProject(e.target.value)} aria-label="Project filter">{projects.map(p=><option key={p.project_id} value={p.project_id}>{p.name}</option>)}</select><ChevronDown size={14}/></div><button className="button secondary" disabled={!selectedRun||loading} onClick={()=>void renameSelectedRun()}><Pencil size={15}/> Rename run</button><button className="button secondary danger-button" disabled={!selectedRun||loading} onClick={()=>void deleteSelectedRun()}><Trash2 size={15}/> Delete selected run</button></>}/><section className="panel"><div className="panel-heading"><div><h2>{projects.find(p=>p.project_id===selectedProject)?.name||'Selected project'}</h2><p>{runs.length} run(s) recorded</p></div><div className="search-box"><Search size={15}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search runs..."/></div></div><RunTable runs={visibleRuns} onSelect={r=>{setSelectedRun(r.run_id);setActiveTab('Events')}} selectedRun={selectedRun}/>{visibleRuns.length===0&&<EmptyState title="No runs yet" detail="Start either RAG project to create instrumented runs." icon={<Activity size={22}/>}/>}</section></>}
        {activeTab==='Compare' && <><PageTitle eyebrow="REGRESSION ANALYSIS" title="Compare executions" description="Compare two runs from the same project and inspect evidence-linked findings."/><section className="panel compare-form-panel"><form onSubmit={compareRuns}><div className="compare-form-grid"><label>Baseline run<select required value={baselineId} onChange={e=>setBaselineId(e.target.value)}><option value="">Select baseline</option>{runs.map(r=><option key={r.run_id} value={r.run_id}>{r.scenario} · {shortId(r.run_id)}</option>)}</select></label><div className="compare-middle"><GitCompareArrows size={22}/></div><label>Current run<select required value={currentId} onChange={e=>setCurrentId(e.target.value)}><option value="">Select current run</option>{runs.map(r=><option key={r.run_id} value={r.run_id} disabled={r.run_id===baselineId}>{r.scenario} · {shortId(r.run_id)}</option>)}</select></label></div><div className="compare-foot"><span>Runs must belong to the same project.</span><button className="button primary" disabled={loading||!baselineId||!currentId||baselineId===currentId}>{loading?<LoaderCircle size={16} className="spin"/>:<GitCompareArrows size={16}/>} Compare runs</button></div></form></section>{comparison&&<><div className="comparison-summary"><div className="compare-run-card"><span className="eyebrow">BASELINE</span><h3>{comparison.baseline.scenario}</h3><code>{comparison.baseline.run_id}</code><StatusPill status={comparison.baseline.status}/><span className="event-count">{comparison.event_counts.baseline} events</span></div><div className="compare-connector"><GitCompareArrows size={22}/><span>VS</span></div><div className="compare-run-card current"><span className="eyebrow">CURRENT</span><h3>{comparison.current.scenario}</h3><code>{comparison.current.run_id}</code><StatusPill status={comparison.current.status}/><span className="event-count">{comparison.event_counts.current} events</span></div></div><section className="panel"><div className="panel-heading"><div><h2>Diagnostic findings</h2><p>{comparison.findings.length} finding(s) returned by the backend</p></div></div>{comparison.findings.map(f=><FindingRow key={f.finding_id} finding={f} onClick={()=>{setSelectedRun(f.run_id);setActiveTab('Findings')}}/>)}{comparison.findings.length===0&&<EmptyState title="No diagnostic rules triggered" detail="No configured rule detected a regression for these runs. This does not guarantee the runs are equivalent." icon={<ShieldCheck size={22}/>}/>}</section></>}</>}
        {activeTab==='Findings' && <><PageTitle eyebrow="DIAGNOSTICS" title="Diagnostic findings" description="Prioritized signals from trace rules, with evidence and next steps." action={<div className="select-wrap"><Layers3 size={15}/><select value={selectedProject} onChange={e=>setSelectedProject(e.target.value)} aria-label="Project filter">{projects.map(p=><option key={p.project_id} value={p.project_id}>{p.name}</option>)}</select><ChevronDown size={14}/></div>}/><div className="finding-summary-grid"><div className="finding-summary critical-summary"><span>CRITICAL / HIGH</span><strong>{findings.filter(f=>['critical','high'].includes(f.severity.toLowerCase())).length}</strong><small>Requires investigation</small></div><div className="finding-summary medium-summary"><span>MEDIUM</span><strong>{findings.filter(f=>f.severity.toLowerCase()==='medium').length}</strong><small>Review recommended</small></div><div className="finding-summary all-summary"><span>ALL FINDINGS</span><strong>{findings.length}</strong><small>Across recent project runs</small></div></div><div className="filter-chips" role="group" aria-label="Filter findings">{['all','critical','high','medium','low','info'].map(level=><button key={level} className={findingFilter===level?'active':''} onClick={()=>setFindingFilter(level)}>{level==='all'?'All severities':level[0].toUpperCase()+level.slice(1)}{level==='all'?` · ${findings.length}`:` · ${findings.filter(f=>f.severity.toLowerCase()===level).length}`}</button>)}</div><section className="panel"><div className="panel-heading"><div><h2>Finding history</h2><p>Each finding links to the run that triggered it. Evidence counts reflect stored event references.</p></div><span className="mini-label">RULE-BASED</span></div>{visibleFindings.map(f=><FindingRow key={f.finding_id} finding={f} onClick={()=>{setSelectedRun(f.run_id);setActiveTab('Events')}} expanded/>)}{visibleFindings.length===0&&<EmptyState title="No matching findings" detail={findings.length?'Try another severity filter.':'Run instrumented workloads or compare a baseline with a current run to generate findings.'} icon={<FileSearch size={22}/>}/>}</section></>}
        {activeTab==='History' && <><PageTitle eyebrow="INVESTIGATION ARCHIVE" title="Investigation history" description="Revisit saved AI and deterministic investigations, inspect prior conclusions, and compare how diagnoses evolve." action={<button className="button secondary" onClick={()=>{setActiveTab('Runs');void refresh()}}><RefreshCw size={15}/> Refresh runs</button>}/><div className="history-overview"><div><span>Saved investigations</span><strong>{investigationHistory.length}</strong></div><div><span>AI-assisted</span><strong>{investigationHistory.filter(i=>String(i.analysis_method||'').toLowerCase().includes('ollama')||Boolean(i.model)).length}</strong></div><div><span>Deterministic / fallback</span><strong>{investigationHistory.filter(i=>!i.model).length}</strong></div><div><span>Runs scanned</span><strong>{Math.min(runs.length,30)}</strong></div></div><section className="panel"><div className="panel-heading"><div><h2>Saved investigation reports</h2><p>Reports are ordered newest first. History is loaded for up to 30 recent runs in this project.</p></div>{historyLoading&&<LoaderCircle className="spin" size={18}/>}</div>{investigationHistory.map(item=><button key={item.investigation_id} className="history-card" onClick={()=>{setSelectedRun(item.run_id);setInvestigation(item);setInvestigationError('');setActiveTab('Events')}}><div className="history-card-icon"><BrainCircuit size={19}/></div><div className="history-card-main"><div className="history-card-top"><strong>{item.title||'Root-cause investigation'}</strong><span className={severityClass(item.confidence==='high'?'high':item.confidence==='medium'?'medium':'info')}>{item.confidence||'unknown'} confidence</span></div><p>{item.likely_cause||'No diagnosis summary was saved.'}</p><div className="history-card-meta"><code>{shortId(item.run_id)}</code><span>{dateText(item.created_at)}</span><span>{item.evidence_event_ids?.length||0} evidence events</span><span>{item.model||item.analysis_method||'deterministic'}</span></div></div><ArrowRight size={17}/></button>)}{!historyLoading&&investigationHistory.length===0&&<EmptyState title="No saved investigations yet" detail="Open a run, select Investigate with AI, and its report will appear here for future review." icon={<Clock3 size={22}/>}/>}</section></>}
        {activeTab==='Events' && <><PageTitle eyebrow="TRACE INSPECTOR" title="Events" description="Inspect recorded pipeline steps, durations, status, and safe payload metadata." action={<><div className="select-wrap"><Activity size={15}/><select value={selectedRun} onChange={e=>setSelectedRun(e.target.value)} aria-label="Selected run"><option value="">Select run</option>{runs.map(r=><option key={r.run_id} value={r.run_id}>{r.scenario} · {shortId(r.run_id)}</option>)}</select><ChevronDown size={14}/></div><button className="button secondary" disabled={!selectedRun||loading} onClick={()=>void renameSelectedRun()}><Pencil size={15}/> Rename run</button><button className="button secondary" disabled={!selectedRun||events.length===0} onClick={exportSelectedEvents}><Download size={15}/> Export events</button><button className="button secondary danger-button" disabled={!selectedRun||loading} onClick={()=>void deleteSelectedRun()}><Trash2 size={15}/> Delete run</button></>}/>{selectedRunInfo&&<div className="selected-run-banner"><div><span className="eyebrow">SELECTED RUN</span><h3>{selectedRunInfo.scenario}</h3><code>{selectedRunInfo.run_id}</code></div><StatusPill status={selectedRunInfo.status}/><div className="selected-run-meta"><span>{events.length} events</span><span>Created {dateText(selectedRunInfo.created_at)}</span></div><button className="button primary" onClick={investigateRun} disabled={investigationLoading}><BrainCircuit size={16}/>{investigationLoading?'Investigating…':'Investigate with AI'}</button></div>}{investigationError&&<div className="event-error" role="alert">{investigationError}</div>}{investigation&&<section className="panel" style={{marginBottom:16}}><div className="panel-heading"><div><h2><BrainCircuit size={18} style={{verticalAlign:'middle',marginRight:8}}/>AI root-cause investigation</h2><p>Evidence-linked analysis · {investigation.analysis_method}{investigation.model?` · ${investigation.model}`:''}</p></div><span className={`severity ${investigation.confidence==='high'?'critical':investigation.confidence==='medium'?'high':'info'}`}>{investigation.confidence} confidence</span></div><div style={{padding:'0 20px 20px'}}><h3 style={{marginTop:4}}>{investigation.title}</h3><p style={{lineHeight:1.65}}>{investigation.likely_cause}</p>{(investigation.first_failure_event_id||investigation.last_confirmed_event_id)&&<div className="payload-details" style={{marginBottom:12}}><strong>Failure boundary</strong>{investigation.last_confirmed_event_id&&<p>Last recorded event before the first failure: <code>{investigation.last_confirmed_event_id}</code></p>}{investigation.first_failure_event_id&&<p>First observed failure: <code>{investigation.first_failure_event_id}</code></p>}<small className="muted">Event ordering is based on recorded timestamps; the preceding event is context, not proof of causation.</small></div>}{investigation.ai_fallback_reason&&<p className="muted">AI model unavailable ({investigation.ai_error_type}); showing deterministic diagnosis. {investigation.ai_fallback_reason||''}</p>}{investigation.history_context&&<div className="stat-grid" style={{margin:'16px 0'}}><Stat icon={<Activity size={18}/>} label="Other runs reviewed" value={investigation.history_context.other_runs_considered} note="Same project history" tone="blue"/><Stat icon={<CheckCircle2 size={18}/>} label="Successful" value={investigation.history_context.successful_runs} note="Historical runs" tone="green"/><Stat icon={<AlertTriangle size={18}/>} label="Failed" value={investigation.history_context.failed_runs} note="Historical runs" tone="red"/></div>}{investigation.historical_comparison&&<div className="payload-details"><strong>Historical comparison</strong><p>{investigation.ai_historical_commentary||investigation.historical_comparison}</p></div>}{Boolean(investigation.historical_differences?.endpoint_differences?.length||investigation.historical_differences?.comparisons?.some(c=>(c.field_differences?.length||0)>0||(c.missing_stages?.length||0)>0||(c.stage_status_changes?.length||0)>0))&&<div className="payload-details" style={{marginTop:12}}><strong>What changed vs successful history?</strong>{investigation.historical_differences?.endpoint_differences?.map((d,i)=><div key={`${d.field}-${d.historical_run_id}-${i}`} className="event-error" style={{color:'#e8c995',background:'#211d15',borderColor:'#49402a'}}><strong>{d.field}</strong><p style={{margin:'6px 0'}}>Previous successful value: <code>{String(d.historical_value)}</code><br/>Current value: <code>{String(d.current_value)}</code></p><small>Baseline run: <code>{d.historical_run_id}</code>{d.historical_event_ids?.length?` · historical event(s): ${d.historical_event_ids.slice(0,2).join(', ')+(d.historical_event_ids.length>2?' and '+(d.historical_event_ids.length-2)+' more':'')}`:''}{d.current_event_ids?.length?` · current event(s): ${d.current_event_ids.slice(0,2).join(', ')+(d.current_event_ids.length>2?' and '+(d.current_event_ids.length-2)+' more':'')}`:''}</small></div>)}{investigation.historical_differences?.comparisons?.slice(0,3).map(c=><div key={c.run_id} style={{padding:'9px 0',borderTop:'1px solid #242a37'}}><div className="event-meta" style={{marginTop:0}}><span>Baseline run <code>{c.run_id}</code></span><StatusPill status={c.status||'info'}/></div>{c.field_differences?.slice(0,5).map((d,i)=><p key={`${d.field}-${i}`} style={{margin:'7px 0'}}> <strong>{d.field}</strong>: <code>{String(d.historical_value)}</code> → <code>{String(d.current_value)}</code>{d.historical_event_ids?.length? <small className="muted"> · historical evidence: {d.historical_event_ids.slice(0,2).join(', ')+(d.historical_event_ids.length>2?' and '+(d.historical_event_ids.length-2)+' more':'')}</small>:null}{d.current_event_ids?.length? <small className="muted"> · current evidence: {d.current_event_ids.slice(0,2).join(', ')+(d.current_event_ids.length>2?' and '+(d.current_event_ids.length-2)+' more':'')}</small>:null}</p>)}{c.missing_stages?.length? <p>Stages missing in current trace: {c.missing_stages.join(', ')}</p>:null}{c.stage_status_changes?.length? <p>Status changes: {c.stage_status_changes.map(d=>`${d.stage}: ${d.historical_status} → ${d.current_status}`).join('; ')}</p>:null}</div>)}</div>}<h4>Recommended actions</h4><ol>{investigation.recommended_actions?.map((a,i)=><li key={i} style={{marginBottom:8}}>{a}</li>)}</ol>{investigation.alternative_explanations?.length>0&&<><h4>Alternative explanations</h4><ul>{investigation.alternative_explanations.map((a,i)=><li key={i}>{a}</li>)}</ul></>}{investigation.evidence_event_ids?.length>0&&<><h4>Supporting evidence</h4><ul style={{margin:'8px 0',paddingLeft:22}}>{investigation.evidence_event_ids.map(id=><li key={id} style={{marginBottom:6}}><code>{id}</code></li>)}</ul></>}{investigation.timeline?.length>0?<><h4>Reconstructed timeline</h4>{investigation.timeline.map((t,i)=><div key={`${t.event_id||i}`} className="event-row"><div className="event-rail"><span className={`event-dot ${t.status||'success'}`}/></div><div className="event-body"><div className="event-top"><strong>{t.step||t.event_id||'Timeline event'}</strong><StatusPill status={t.status||'info'}/></div><div className="event-meta"><span>{dateText(t.timestamp)}</span>{t.duration_ms!=null&&<span>{t.duration_ms.toFixed(2)} ms</span>}{t.event_id&&<code>{shortId(t.event_id)}</code>}</div>{t.explanation&&<p>{t.explanation}</p>}{t.error&&<div className="event-error">{t.error}</div>}</div></div>)}</>:<div className="payload-details"><strong>Reconstructed timeline unavailable</strong><p>No event documents were returned for this run. Failure-boundary references alone are not enough to reconstruct the sequence; verify that event records exist for this run ID.</p></div>}{investigation.limitations?.length>0&&<p className="muted" style={{marginTop:16}}>Limitations: {investigation.limitations.join(' ')}</p>}</div></section>}<section className="panel"><div className="panel-heading"><div><h2>Event timeline</h2><p>Ordered by timestamp</p></div><span className="mini-label">{totalEvents} EVENTS</span></div>{events.map((ev,i)=><div className="event-row" key={ev.event_id}><div className="event-rail"><span className={`event-dot ${ev.status}`}/>{i!==events.length-1&&<span className="event-line"/>}</div><div className="event-body"><div className="event-top"><div><strong>{ev.step}</strong><span className="event-type">{ev.event_type}</span></div><StatusPill status={ev.status}/></div><div className="event-meta"><span><Clock3 size={13}/>{ev.duration_ms==null?'Duration unavailable':`${ev.duration_ms.toFixed(2)} ms`}</span><span>{dateText(ev.timestamp)}</span><code>{shortId(ev.event_id)}</code></div>{ev.error&&<div className="event-error">{ev.error}</div>}{ev.payload&&Object.keys(ev.payload).length>0&&<details className="payload-details"><summary>View event payload</summary><pre>{JSON.stringify(ev.payload,null,2)}</pre></details>}</div></div>)}{!selectedRun&&<EmptyState title="Select a run to inspect" detail="Choose a run from the dropdown to load its stored events." icon={<Terminal size={22}/>}/ >}{selectedRun&&events.length===0&&<EmptyState title="No events recorded" detail="This run exists, but no events were returned by the API." icon={<Terminal size={22}/>}/>}</section></>}
        <footer className="footer"><span>TraceLens <span className="footer-dot">·</span> RAG observability & diagnostics</span><span><span className={`health-dot ${health}`}/>{health==='online'?'API and database ready':health==='checking'?'Checking connection':'Backend unavailable'} <button onClick={()=>void refresh()} className="footer-refresh">Refresh</button></span></footer>
      </div>
    </main>
    {showSettings&&<Modal title="Connection settings" onClose={()=>setShowSettings(false)}><form onSubmit={saveApiUrl} className="modal-form"><label>TraceLens API URL<input value={apiDraft} onChange={e=>setApiDraft(e.target.value)} placeholder="http://127.0.0.1:8000" required/></label><p className="form-hint">The frontend calls the FastAPI backend directly. The backend must allow requests from <code>http://127.0.0.1:5173</code>.</p><div className="modal-actions"><button type="button" className="button secondary" onClick={()=>setShowSettings(false)}>Cancel</button><button className="button primary">Save and connect</button></div></form></Modal>}
    {showEditProject&&<Modal title="Edit project" onClose={()=>setShowEditProject(false)}><form onSubmit={updateProject} className="modal-form"><label>Project name<input autoFocus value={projectName} onChange={e=>setProjectName(e.target.value)} maxLength={120} required/></label><label>Description<textarea value={projectDescription} onChange={e=>setProjectDescription(e.target.value)} rows={3} maxLength={800}/></label><label>Framework<select value={framework} onChange={e=>setFramework(e.target.value)}><option value="python">Python</option><option value="scikit-learn">scikit-learn / TF-IDF</option><option value="chromadb">ChromaDB</option><option value="langchain">LangChain</option><option value="custom">Custom pipeline</option></select></label><p className="form-hint">Editing descriptive details preserves the project's stable ID and historical runs.</p><div className="modal-actions"><button type="button" className="button secondary" onClick={()=>setShowEditProject(false)}>Cancel</button><button className="button primary" disabled={loading||!projectName.trim()}>{loading?<LoaderCircle size={16} className="spin"/>:<Check size={16}/>} Save changes</button></div></form></Modal>}
    {showCreateProject&&<Modal title="Create project" onClose={()=>setShowCreateProject(false)}><form onSubmit={createProject} className="modal-form"><label>Project name<input autoFocus value={projectName} onChange={e=>setProjectName(e.target.value)} placeholder="e.g. Customer Support RAG" maxLength={120} required/></label><label>Description<textarea value={projectDescription} onChange={e=>setProjectDescription(e.target.value)} placeholder="What does this AI pipeline do?" rows={3} maxLength={800}/></label><label>Framework<select value={framework} onChange={e=>setFramework(e.target.value)}><option value="python">Python</option><option value="scikit-learn">scikit-learn / TF-IDF</option><option value="chromadb">ChromaDB</option><option value="langchain">LangChain</option><option value="custom">Custom pipeline</option></select></label><div className="modal-actions"><button type="button" className="button secondary" onClick={()=>setShowCreateProject(false)}>Cancel</button><button className="button primary" disabled={loading||!projectName.trim()}>{loading?<LoaderCircle size={16} className="spin"/>:<Plus size={16}/>} Create project</button></div></form></Modal>}
  </div>
}

/** Compact metric card used by overview and investigation context panels. */
function Stat({icon,label,value,note,tone}:{icon:React.ReactNode;label:string;value:number;note:string;tone:string}) {return <div className="stat-card"><div className="stat-top"><span className={`stat-icon ${tone}`}>{icon}</span><span className="stat-note">LIVE</span></div><div className="stat-value">{value}</div><div className="stat-label">{label}</div><div className="stat-bottom">{note}</div></div>}
function PageTitle({eyebrow,title,description,action}:{eyebrow:string;title:string;description:string;action?:React.ReactNode}) {return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}<span className="heading-period">.</span></h1><p>{description}</p></div>{action&&<div className="heading-actions">{action}</div>}</div>}
function StatusPill({status}:{status?:string}) {const s=(status||'unknown').toLowerCase();return <span className={`status-pill ${s}`}><span/>{s}</span>}
/** Accessible tabular summary of runs; selecting a row opens its trace details. */
function RunTable({runs,onSelect,selectedRun}:{runs:Run[];onSelect:(r:Run)=>void;selectedRun:string}) {return <div className="table-scroll"><table className="data-table"><thead><tr><th>SCENARIO</th><th>RUN ID</th><th>STATUS</th><th>CREATED</th><th/></tr></thead><tbody>{runs.map(r=><tr key={r.run_id} className={selectedRun===r.run_id?'selected-row':''} onClick={()=>onSelect(r)}><td><strong>{r.scenario}</strong><small>{r.baseline_run_id?`Baseline: ${shortId(r.baseline_run_id)}`:'Run execution'}</small></td><td><code>{shortId(r.run_id)}</code></td><td><StatusPill status={r.status}/></td><td className="date-cell">{dateText(r.created_at)}</td><td><button className="row-arrow" aria-label="Inspect run"><ArrowRight size={15}/></button></td></tr>)}</tbody></table></div>}
/** A diagnostic finding with optional remediation details and evidence metadata. */
function FindingRow({finding:f,onClick,expanded=false}:{finding:Finding;onClick:()=>void;expanded?:boolean}) {return <button className={`finding-row ${expanded?'expanded':''}`} onClick={onClick}><div className={`finding-icon ${f.severity.toLowerCase()}`}><AlertTriangle size={17}/></div><div className="finding-content"><div className="finding-title-line"><strong>{f.title}</strong><span className={severityClass(f.severity)}>{f.severity}</span></div><p>{f.explanation||f.rule_id}</p>{expanded&&f.recommended_action&&<div className="recommended"><strong>Recommended action</strong><span>{f.recommended_action}</span></div>}<div className="finding-meta"><code>{f.rule_id}</code><span>{shortId(f.finding_id)}</span><span>{f.evidence_event_ids?.length||0} evidence events</span></div></div><ArrowRight className="finding-arrow" size={16}/></button>}
function EmptyState({title,detail,icon}:{title:string;detail:string;icon:React.ReactNode}) {return <div className="empty-state"><div className="empty-icon">{icon}</div><strong>{title}</strong><p>{detail}</p></div>}
function PipelineNode({icon,title,sub}:{icon:React.ReactNode;title:string;sub:string}) {return <div className="pipeline-node"><span>{icon}</span><strong>{title}</strong><small>{sub}</small></div>}
/** Shared modal shell with backdrop dismissal and an accessible close control. */
function Modal({title,children,onClose}:{title:string;children:React.ReactNode;onClose:()=>void}) {return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose()}}><section className="modal"><div className="modal-header"><div><span className="eyebrow">TRACELENS WORKSPACE</span><h2>{title}</h2></div><button className="icon-btn" onClick={onClose} aria-label="Close"><X size={18}/></button></div>{children}</section></div>}

export default App
