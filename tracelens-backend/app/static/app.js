/* TraceLens dashboard. All API access is centralized here for easy testing and replacement. */
(() => {
  const $ = (id) => document.getElementById(id);
  const state = { projects: [], selectedProject: "", runs: [], activeRun: null, llm: false, apiKey: "", view: "overview" };
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const date = (v) => { try { return new Date(v).toLocaleString([], {month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"}); } catch { return "—"; } };
  const duration = (v) => v == null ? "—" : (v < 1000 ? Math.round(v)+" ms" : (v/1000).toFixed(2)+" s");
  const status = (s) => '<span class="status '+esc(s)+'">'+esc(s || "unknown")+'</span>';
  const toast = (message) => { $("toast").textContent = message; $("toast").classList.remove("hidden"); setTimeout(()=>$("toast").classList.add("hidden"), 3200); };
  const notice = (message) => { $("notice").textContent = message; $("notice").classList.toggle("hidden", !message); };
  async function api(path, options={}) {
    const headers = {"Content-Type":"application/json", ...(state.apiKey ? {"X-API-Key":state.apiKey}:{}), ...(options.headers||{})};
    const response = await fetch(path, {...options, headers});
    const raw = await response.text(); let data = null;
    try { data = raw ? JSON.parse(raw) : null; } catch { data = raw; }
    if (!response.ok) throw new Error(data?.detail || data?.message || response.statusText || "API request failed");
    return data;
  }
  function go(view) {
    state.view = view;
    document.querySelectorAll(".view").forEach(x => x.classList.toggle("hidden", x.id !== "view-"+view));
    document.querySelectorAll(".nav[data-view]").forEach(x => x.classList.toggle("active", x.dataset.view === view));
    const labels = {overview:["WORKSPACE / OVERVIEW","System overview"],runs:["WORKSPACE / TRACES","Traces & runs"],knowledge:["WORKSPACE / KNOWLEDGE","Knowledge base"],diagnose:["WORKSPACE / DIAGNOSIS","AI diagnosis"]};
    $("crumb").textContent = labels[view][0]; $("page-title").textContent = labels[view][1];
    if(view==="runs") refreshRuns(); if(view==="knowledge") refreshKnowledge(); if(view==="diagnose") refreshDiagnoses();
  }
  function fillProjectSelects() {
    const selects = ["run-project-select","knowledge-project-select","diagnose-project-select"];
    for(const id of selects) {
      const el=$(id), old=el.value || state.selectedProject;
      el.innerHTML='<option value="">Select project</option>'+state.projects.map(p=>'<option value="'+esc(p.project_id)+'">'+esc(p.name)+'</option>').join("");
      if(state.projects.some(p=>p.project_id===old)) el.value=old;
    }
    state.selectedProject = $("run-project-select").value || $("knowledge-project-select").value || $("diagnose-project-select").value || state.selectedProject;
  }
  async function loadProjects() {
    state.projects = await api("/api/projects");
    fillProjectSelects();
    $("metric-projects").textContent=state.projects.length;
    renderProjects();
    if(state.projects.length && !state.selectedProject) {
      state.selectedProject=state.projects[0].project_id;
      for(const id of ["run-project-select","knowledge-project-select","diagnose-project-select"]) $(id).value=state.selectedProject;
    }
  }
  function renderProjects() {
    const el=$("project-grid");
    if(!state.projects.length){el.innerHTML='<div class="empty" style="grid-column:1/-1"><strong>Your first project starts here</strong>Create a workspace, then instrument your first RAG run or add a runbook.</div>';return;}
    el.innerHTML=state.projects.slice(0,6).map((p,i)=>'<article class="project-card" data-project="'+esc(p.project_id)+'"><div class="project-head"><span class="project-glyph">'+["⌘","⌁","✳","◈"][i%4]+'</span><span class="tag">'+esc(p.framework||"python")+'</span></div><h4>'+esc(p.name)+'</h4><p>'+esc(p.description||"No description yet. Add a run to start tracing this project.")+'</p><div class="project-meta"><span>▤ '+esc(p.project_id.slice(0,14))+'</span><span>Open workspace ↗</span></div></article>').join("");
    el.querySelectorAll("[data-project]").forEach(card=>card.addEventListener("click",()=>{state.selectedProject=card.dataset.project;fillProjectSelects();$("run-project-select").value=state.selectedProject;go("runs");}));
  }
  async function loadAll() {
    try {
      const [health, meta] = await Promise.all([api("/health"),api("/api/meta")]);
      $("connection-label").textContent="API connected · MongoDB "+health.database;
      $("connection-label").previousElementSibling.style.background="#6be5a0";
      state.llm=!!meta.llm_configured;
      $("llm-pill").innerHTML='<i style="background:'+(state.llm?"#6be5a0":"#e4b15f")+'"></i>'+(state.llm?"LLM configured":"Evidence-only mode");
      $("diagnose-mode-note").textContent=state.llm?"LLM enabled · responses include retrieved sources and trace evidence.":"No LLM key detected. Retrieval and source inspection work; generation will be labelled evidence-only.";
      notice("");
    } catch(e) {
      $("connection-label").textContent="API unavailable";
      $("connection-label").previousElementSibling.style.background="#ff8b91";
      notice("Cannot reach the TraceLens API. Start MongoDB and run uvicorn app.main:app --reload from tracelens-backend. "+e.message);
    }
    try { await loadProjects(); await loadOverviewRuns(); await loadMetrics(); }
    catch(e) { notice(e.message); }
  }
  async function loadMetrics() {
    const runLists=await Promise.all(state.projects.map(p=>api("/api/projects/"+encodeURIComponent(p.project_id)+"/runs")));
    state.runs=runLists.flat().sort((a,b)=>new Date(b.created_at)-new Date(a.created_at));
    $("metric-runs").textContent=state.runs.length;
    $("metric-failed").textContent=state.runs.filter(r=>r.status==="failed").length;
    const knowledge=await Promise.all(state.projects.map(p=>api("/api/projects/"+encodeURIComponent(p.project_id)+"/knowledge")));
    $("metric-docs").textContent=knowledge.flat().length;
  }
  async function loadOverviewRuns() {
    const lists=await Promise.all(state.projects.map(p=>api("/api/projects/"+encodeURIComponent(p.project_id)+"/runs")));
    const runs=lists.flat().sort((a,b)=>new Date(b.created_at)-new Date(a.created_at)).slice(0,6);
    $("recent-runs").innerHTML=renderRunsTable(runs,false);
    bindRunRows($("recent-runs"));
  }
  function renderRunsTable(runs, showProject=true) {
    if(!runs.length)return '<div class="empty"><strong>No runs recorded yet</strong>Instrument your app with the TraceLens SDK, or open the API docs to create a run.</div>';
    const headers=showProject?["RUN / SCENARIO","PROJECT","STATUS","CREATED"]:["RUN / SCENARIO","VERSION","STATUS","CREATED"];
    return '<div class="table-head">'+headers.map(x=>'<span>'+x+'</span>').join("")+'</div>'+runs.map(r=>{
      const project=state.projects.find(p=>p.project_id===r.project_id);
      return '<div class="table-row clickable" data-run="'+esc(r.run_id)+'"><div><span class="run-name">'+esc(r.scenario)+'</span><span class="run-sub">'+esc(r.run_id)+'</span></div><div>'+esc(showProject?(project?.name||r.project_id):r.version||"dev")+'</div><div>'+status(r.status)+'</div><div>'+date(r.created_at)+'</div></div>';
    }).join("");
  }
  function bindRunRows(root) { root.querySelectorAll("[data-run]").forEach(row=>row.addEventListener("click",()=>openRun(row.dataset.run))); }
  async function refreshRuns() {
    try {
      const project=$("run-project-select").value;
      if(!project){$("runs-table").innerHTML='<div class="empty"><strong>Select a project</strong>Choose a project to explore its traces.</div>';return;}
      state.selectedProject=project;
      const runs=await api("/api/projects/"+encodeURIComponent(project)+"/runs");
      const filter=$("run-filter").value;
      $("runs-table").innerHTML=renderRunsTable(runs.filter(r=>filter==="all"||r.status===filter),false);
      bindRunRows($("runs-table"));
    } catch(e) { notice(e.message); }
  }
  async function openRun(runId) {
    try {
      const run=await api("/api/runs/"+encodeURIComponent(runId));
      const events=await api("/api/runs/"+encodeURIComponent(runId)+"/events");
      state.activeRun=run;
      $("run-detail").classList.remove("hidden");
      $("run-detail").innerHTML='<div class="detail-card"><div class="eyebrow">RUN DETAILS</div><h3>'+esc(run.scenario)+'</h3><p class="muted">Run ID</p><div class="run-sub">'+esc(run.run_id)+'</div><p class="muted">Version</p><p>'+esc(run.version||"dev")+'</p><p class="muted">Created</p><p>'+date(run.created_at)+'</p><p class="muted">Status</p>'+status(run.status)+'<div style="margin-top:18px"><button class="button button-ghost" id="use-baseline">Use as baseline</button> <button class="button button-ghost" id="use-current">Use as current</button></div></div><div class="detail-card"><div class="eyebrow">EXECUTION TIMELINE · '+events.length+' EVENTS</div><h3>Step-by-step trace</h3>'+(events.length?events.map(e=>'<div class="event '+(e.status==="failed"?"failed":"")+'"><small>'+date(e.timestamp)+' · '+duration(e.duration_ms)+'</small><h4>'+esc(e.step)+' · '+esc(e.event_type)+'</h4><p>'+esc(e.error||JSON.stringify(e.payload||{}))+'</p></div>').join(""):'<div class="empty">No events captured for this run.</div>')+'</div>';
      $("use-baseline").onclick=()=>{$("baseline-id").value=run.run_id;$("compare-panel").classList.remove("hidden");$("compare-panel").scrollIntoView({behavior:"smooth"});};
      $("use-current").onclick=()=>{$("current-id").value=run.run_id;$("compare-panel").classList.remove("hidden");$("compare-panel").scrollIntoView({behavior:"smooth"});};
      $("run-detail").scrollIntoView({behavior:"smooth",block:"start"});
    } catch(e) { toast(e.message); }
  }
  async function compareRuns() {
    const baseline=$("baseline-id").value.trim(), current=$("current-id").value.trim();
    if(!baseline||!current){toast("Enter both baseline and current run IDs.");return;}
    $("compare-result").innerHTML='<p class="muted">Comparing traces…</p>';
    try {
      const result=await api("/api/runs/compare",{method:"POST",body:JSON.stringify({baseline_run_id:baseline,current_run_id:current})});
      $("compare-result").innerHTML='<div class="compare-result"><div class="muted">Baseline <b>'+esc(result.baseline.scenario)+'</b> ('+result.event_counts.baseline+' events) → Current <b>'+esc(result.current.scenario)+'</b> ('+result.event_counts.current+' events)</div>'+result.findings.map(f=>'<div class="finding"><span class="severity">'+esc(f.severity.toUpperCase())+' · '+esc(f.rule_id)+'</span><h4>'+esc(f.title)+'</h4><p>'+esc(f.explanation)+'</p><p style="margin-top:8px;color:#b2e9c5">Next: '+esc(f.recommended_action)+'</p></div>').join("")+'</div>';
    } catch(e) { $("compare-result").innerHTML='<div class="notice">'+esc(e.message)+'</div>'; }
  }
  async function refreshKnowledge() {
    const project=$("knowledge-project-select").value || state.selectedProject;
    if(!project){$("knowledge-list").innerHTML='<div class="empty">Select a project to view its knowledge.</div>';return;}
    try {
      const docs=await api("/api/projects/"+encodeURIComponent(project)+"/knowledge");
      $("knowledge-list").innerHTML=docs.length?'<div class="table-head" style="grid-template-columns:1.6fr 1fr .5fr .8fr"><span>DOCUMENT</span><span>SOURCE</span><span>CHUNKS</span><span>ADDED</span></div>'+docs.map(d=>'<div class="table-row" style="grid-template-columns:1.6fr 1fr .5fr .8fr"><div class="run-name">'+esc(d.title)+'<span class="run-sub">'+esc(d.document_id)+'</span></div><div>'+esc(d.source||"manual")+'</div><div>'+esc(d.chunks)+'</div><div>'+date(d.created_at)+'</div></div>').join(""):'<div class="empty"><strong>No documents yet</strong>Ingest a runbook or troubleshooting note above.</div>';
    } catch(e){toast(e.message);}
  }
  async function ingestKnowledge() {
    const project=$("knowledge-project-select").value, title=$("knowledge-title").value.trim(), content=$("knowledge-content").value.trim(), source=$("knowledge-source").value.trim()||"manual";
    if(!project||!title||!content){toast("Choose a project and provide a title and content.");return;}
    const button=$("ingest-button");button.disabled=true;button.textContent="Ingesting…";
    try {
      const result=await api("/api/projects/"+encodeURIComponent(project)+"/knowledge",{method:"POST",body:JSON.stringify({title,content,source})});
      toast("Document ingested · "+result.chunks_created+" chunks created.");
      $("knowledge-title").value="";$("knowledge-content").value="";$("knowledge-source").value="";
      await refreshKnowledge();await loadMetrics();
    }catch(e){toast(e.message);}finally{button.disabled=false;button.textContent="Ingest document ↗";}
  }
  async function searchKnowledge() {
    const project=$("knowledge-project-select").value||state.selectedProject, q=$("knowledge-query").value.trim();
    if(!project||q.length<2){toast("Choose a project and enter a search query.");return;}
    $("search-results").innerHTML='<p class="muted">Searching project knowledge…</p>';
    try{
      const result=await api("/api/projects/"+encodeURIComponent(project)+"/knowledge/search?q="+encodeURIComponent(q)+"&top_k=5");
      $("search-results").innerHTML=result.results.length?result.results.map((x,i)=>'<div class="search-result"><div style="display:flex;justify-content:space-between;gap:12px"><h4>'+esc(x.title||"Untitled")+' <span class="muted">· '+esc(x.source||"manual")+'</span></h4><span class="score">S'+(i+1)+' · '+esc(x.score)+'</span></div><p>'+esc(x.text)+'</p><div class="run-sub">chunk '+esc(x.chunk_id)+' · matched '+esc((x.matched_terms||[]).join(", "))+'</div></div>').join(""):'<div class="empty">No matching chunks. Try broader terms or ingest more documentation.</div>';
    }catch(e){$("search-results").innerHTML='<div class="notice">'+esc(e.message)+'</div>';}
  }
  async function runDiagnosis() {
    const project=$("diagnose-project-select").value||state.selectedProject, question=$("diagnose-question").value.trim(), runId=$("diagnose-run-id").value.trim()||null;
    if(!project||question.length<3){toast("Choose a project and enter a diagnostic question.");return;}
    const button=$("diagnose-button");button.disabled=true;button.textContent="Investigating…";
    $("diagnosis-result").innerHTML='<div class="panel"><p class="muted">Retrieving evidence and examining trace context…</p></div>';
    try{
      const result=await api("/api/projects/"+encodeURIComponent(project)+"/diagnose",{method:"POST",body:JSON.stringify({question,run_id:runId,top_k:5})});
      $("diagnosis-result").innerHTML='<article class="diagnosis-card"><div class="eyebrow">INVESTIGATION RESULT · '+esc(result.mode==="llm_rag"?"LLM + RETRIEVED EVIDENCE":"EVIDENCE-ONLY MODE")+'</div><h3>'+esc(question)+'</h3><div class="diagnosis-answer">'+esc(result.answer)+'</div><div style="margin-top:18px"><div class="eyebrow">RETRIEVED SOURCES · '+result.sources.length+'</div>'+result.sources.map(s=>'<span class="source-chip">['+esc(s.citation)+'] '+esc(s.title)+' · score '+esc(s.score)+'</span>').join("")+'</div><p class="muted" style="margin-top:15px">Run events inspected: '+esc(result.trace_event_count)+' · Saved diagnosis: '+esc(result.diagnosis_id)+'</p></article>';
      await refreshDiagnoses();
    }catch(e){$("diagnosis-result").innerHTML='<div class="notice">'+esc(e.message)+'</div>';}finally{button.disabled=false;button.innerHTML='Investigate <span>✳</span>';}
  }
  async function refreshDiagnoses(){
    const project=$("diagnose-project-select").value||state.selectedProject;
    if(!project){$("diagnosis-history").innerHTML='<div class="empty">Select a project to view diagnosis history.</div>';return;}
    try{
      const list=await api("/api/projects/"+encodeURIComponent(project)+"/diagnoses");
      $("diagnosis-history").innerHTML=list.length?list.map(d=>'<div class="table-row" style="grid-template-columns:1.4fr .7fr .8fr"><div><span class="run-name">'+esc(d.question)+'</span><span class="run-sub">'+esc(d.diagnosis_id)+'</span></div><div><span class="tag">'+esc(d.mode)+'</span></div><div>'+date(d.created_at)+'</div></div>').join(""):'<div class="empty">No saved investigations yet.</div>';
    }catch(e){$("diagnosis-history").innerHTML='<div class="empty">'+esc(e.message)+'</div>';}
  }
  function showProjectDialog(){ $("project-dialog").showModal(); }
  async function createProject(e){
    e.preventDefault();
    const name=$("project-name").value.trim();if(!name)return;
    try{
      const project=await api("/api/projects",{method:"POST",body:JSON.stringify({name,description:$("project-description").value.trim(),framework:$("project-framework").value.trim()||"python"})});
      $("project-dialog").close();$("project-form").reset();$("project-framework").value="python";
      await loadProjects();state.selectedProject=project.project_id;fillProjectSelects();
      for(const id of ["run-project-select","knowledge-project-select","diagnose-project-select"])$(id).value=project.project_id;
      await loadMetrics();toast("Project created.");go("runs");
    }catch(e){toast(e.message);}
  }
  document.querySelectorAll(".nav[data-view]").forEach(b=>b.addEventListener("click",()=>go(b.dataset.view)));
  document.querySelectorAll("[data-goto]").forEach(b=>b.addEventListener("click",()=>go(b.dataset.goto)));
  $("new-project-button").onclick=showProjectDialog;$("hero-project").onclick=showProjectDialog;
  $("project-form").addEventListener("submit",createProject);
  $("settings-button").onclick=()=>{$("api-key-input").value=state.apiKey;$("settings-dialog").showModal();};
  $("settings-form").addEventListener("submit",async e=>{e.preventDefault();state.apiKey=$("api-key-input").value.trim();$("settings-dialog").close();await loadAll();toast("API key updated for this tab.");});
  $("refresh-button").onclick=loadAll;$("run-project-select").onchange=refreshRuns;$("run-filter").onchange=refreshRuns;
  $("compare-open").onclick=()=>{$("compare-panel").classList.remove("hidden");$("compare-panel").scrollIntoView({behavior:"smooth"});};
  $("compare-close").onclick=()=>$("compare-panel").classList.add("hidden");$("compare-button").onclick=compareRuns;
  $("knowledge-project-select").onchange=()=>{state.selectedProject=$("knowledge-project-select").value;refreshKnowledge();};
  $("knowledge-refresh").onclick=refreshKnowledge;$("ingest-button").onclick=ingestKnowledge;$("search-button").onclick=searchKnowledge;
  $("knowledge-query").addEventListener("keydown",e=>{if(e.key==="Enter")searchKnowledge();});
  $("diagnose-project-select").onchange=()=>{state.selectedProject=$("diagnose-project-select").value;refreshDiagnoses();};
  $("diagnose-button").onclick=runDiagnosis;
  loadAll();
})();