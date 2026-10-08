const API = ""; // same-origin: dashboard is served by the same FastAPI app it talks to
let selectedSlug = null;
let candidatesCache = [];

document.getElementById('toggleTheme').addEventListener('click', function(){
  var html = document.documentElement;
  var isDark = html.getAttribute('data-theme') === 'dark';
  html.setAttribute('data-theme', isDark ? 'light' : 'dark');
  this.textContent = isDark ? 'Dark mode' : 'Light mode';
});

async function api(path, opts){
  const resp = await fetch(API + path, Object.assign({headers: {'Content-Type': 'application/json'}}, opts||{}));
  if(!resp.ok){
    const body = await resp.text().catch(function(){return '';});
    throw new Error('API ' + resp.status + ' on ' + path + (body ? ': ' + body : ''));
  }
  if(resp.status === 204) return null;
  return resp.json();
}

function showConnectionError(err){
  const el = document.getElementById('connectionBanner');
  el.style.display = 'block';
  el.textContent = 'Could not reach the CADDTARD API at this origin (' + err.message + '). Confirm the backend container is running and this page was loaded from the same host/port as the API (default http://localhost:8000/).';
}

function agentCard(id, title, sub, pillHtml, bodyHtml, footHtml){
  return '<div class="card" id="'+id+'">'+
    '<div class="card-head"><div><h3>'+title+'</h3><div class="card-sub">'+sub+'</div></div>'+pillHtml+'</div>'+
    '<div class="card-body">'+bodyHtml+'</div>'+
    (footHtml ? '<div class="card-foot">'+footHtml+'</div>' : '') +
  '</div>';
}
function livePill(){ return '<span class="pill pill-live"><span class="status-dot dot-green"></span>Live agent</span>'; }
function staticPill(){ return '<span class="pill pill-static">Reference</span>'; }
function statusPill(status){
  if(status==='success') return '<span class="pill pill-live">success</span>';
  if(status==='error') return '<span class="pill pill-danger">error</span>';
  return '<span class="pill pill-warn">running</span>';
}
function fmtTime(iso){
  if(!iso) return 'never';
  var d = new Date(iso);
  return d.toLocaleString();
}

async function loadKPIs(){
  const [genes, scoring, candidates, agentsList, sourcesList] = await Promise.all([
    api('/api/genes'), api('/api/scoring'), api('/api/candidates'), api('/api/agents'), api('/api/sources'),
  ]);
  const top3Genes = genes.filter(function(g){return g.in_top3;});
  const topScore = Math.max.apply(null, scoring.map(function(s){return s.composite;}));
  const implementedAgents = agentsList.filter(function(a){return a.status==='implemented';}).length;
  const connectedSources = sourcesList.filter(function(s){return s.status==='connected';}).length;
  const kpis = [
    {n: genes.length, l:'Genes in verified reference DB'},
    {n: candidates.length, l:'Selected top-3 programs'},
    {n: top3Genes.length, l:'Genes behind the top-3 programs'},
    {n: scoring.length, l:'Programs scored in prioritization rubric'},
    {n: topScore.toFixed(2), l:'Top composite score (of 5)'},
    {n: implementedAgents+' / '+agentsList.length, l:'Agents live (of full taxonomy)'},
    {n: connectedSources+' / '+sourcesList.length, l:'Data sources connected (of registry)'},
  ];
  document.getElementById('kpiRow').innerHTML = kpis.map(function(k){
    return '<div class="kpi"><div class="n">'+k.n+'</div><div class="l">'+k.l+'</div></div>';
  }).join('');
}

async function loadScoring(){
  const scoring = await api('/api/scoring');
  const rows = scoring.map(function(s){
    const badge = s.selected ? '<span class="pill pill-select">selected</span>' : '<span class="small">not selected</span>';
    return '<tr><td>'+s.program+'<div class="small">'+s.genes+'</div></td>'+
      '<td>'+s.commercial+'</td><td>'+s.patients+'</td><td>'+s.cmc+'</td><td>'+s.feasibility+'</td>'+
      '<td><b>'+s.composite.toFixed(2)+'</b></td><td>'+badge+'</td></tr>'+
      '<tr><td colspan="7" class="small" style="padding-bottom:14px; color:var(--text-2);">'+s.rationale+'</td></tr>';
  }).join('');
  document.getElementById('scoringCard').innerHTML =
    '<div class="card-head"><div><h3>Composite scoring, 1-5 per criterion, equal weights</h3>'+
    '<div class="card-sub">Served live from GET /api/scoring, sorted by composite score</div></div>'+staticPill()+'</div>'+
    '<div class="scrollbox" style="max-height:520px;"><table><thead><tr><th>Program</th><th>Commercial</th><th>Patients</th><th>CMC</th><th>Feasibility</th><th>Composite</th><th>Status</th></tr></thead><tbody>'+rows+'</tbody></table></div>';
}

function field(label, value){
  return '<div style="margin-bottom:8px;"><div style="font-weight:600; font-size:12px; color:var(--text-muted); text-transform:uppercase; letter-spacing:.02em;">'+label+'</div><div style="font-size:13px; color:var(--text-2);">'+value+'</div></div>';
}

async function loadCandidateTabs(){
  candidatesCache = await api('/api/candidates');
  if(!selectedSlug) selectedSlug = candidatesCache[0].slug;
  renderTabs();
  await loadSelectedCandidatePanels();
}

async function loadSelectedCandidatePanels(){
  await Promise.all([
    loadCandidateDetail(), loadTimeline(), loadCost(), loadChecklist(),
    loadGraphForSelected(), loadHypotheses(), loadExperiments(),
  ]);
}

function renderTabs(){
  const box = document.getElementById('candidateTabs');
  box.innerHTML = candidatesCache.map(function(c){
    return '<button class="tabbtn'+(c.slug===selectedSlug?' active':'')+'" data-slug="'+c.slug+'">'+c.name+'</button>';
  }).join('');
  Array.prototype.forEach.call(box.querySelectorAll('.tabbtn'), function(btn){
    btn.addEventListener('click', async function(){
      selectedSlug = btn.getAttribute('data-slug');
      renderTabs();
      await loadSelectedCandidatePanels();
    });
  });
}

async function loadCandidateDetail(){
  const c = await api('/api/candidates/' + selectedSlug);
  document.getElementById('candidateGrid').innerHTML = '<div class="card card-wide">'+
    '<div class="card-head"><div><h3>'+c.name+'</h3><div class="card-sub">'+c.genes+' &middot; '+c.uniprot+'</div></div><span class="pill pill-select">Top-3 selected</span></div>'+
    field('Organ system / inheritance', c.organ+' &middot; '+c.inheritance)+
    field('OMIM', c.omim)+
    field('Mechanism', c.mechanism)+
    field('Current standard of care', c.soc)+
    field('Lead modality recommendation', c.modality)+
    field('Biomarkers / endpoints', c.biomarkers)+
    field('Commercial precedent', c.commercial_precedent)+
    field('Key risks', c.risks)+
  '</div>';
}

async function loadTimeline(){
  const c = await api('/api/candidates/' + selectedSlug);
  document.getElementById('timelineIntro').textContent = '12-month plan for: ' + c.name + ' (served from GET /api/candidates/' + selectedSlug + ').';
  document.getElementById('timelineBox').innerHTML = c.timeline.map(function(t){
    return '<div class="timeline-row"><div class="m">'+t.month_label+'</div><div class="t">'+t.track+'</div><div>'+t.detail+'</div></div>';
  }).join('');
}

async function loadCost(){
  const c = await api('/api/candidates/' + selectedSlug);
  let itemsHtml = '';
  if(c.cost_items && c.cost_items.length){
    itemsHtml = '<table style="margin-top:8px;"><tbody>'+c.cost_items.map(function(item){
      return '<tr><td>'+item.name+(item.optional?' <span class="small">(optional)</span>':'')+'</td><td>$'+item.low_usd_k+'K - $'+item.high_usd_k+'K</td></tr>';
    }).join('')+'</tbody></table>';
  }
  const s = c.cost_summary;
  document.getElementById('costBreakdown').innerHTML = itemsHtml +
    (s ? '<div class="result-box" style="margin-top:8px; background:var(--accent-bg);"><div class="small" style="color:var(--accent-text);">All-in non-clinical / IND-enabling estimate</div>'+
    '<div class="big" style="color:var(--accent-text);">$'+s.allin_low_usd_k.toLocaleString()+'K – $'+s.allin_high_usd_k.toLocaleString()+'K</div>'+
    '<div class="small" style="margin-top:8px; color:var(--text-2);">'+s.note+'</div></div>'+
    '<div class="small" style="margin-top:6px;">Source: '+s.source+'</div>' : '');
}

async function loadChecklist(){
  const items = await api('/api/checklist?candidate=' + encodeURIComponent(selectedSlug));
  const categories = {};
  items.forEach(function(it){ (categories[it.category] = categories[it.category] || []).push(it); });
  const checked = items.filter(function(i){return i.checked;}).length;
  const pct = items.length ? Math.round(checked/items.length*100) : 0;

  let html = Object.keys(categories).map(function(cat){
    return '<div style="margin-bottom:8px;"><div style="font-weight:600; font-size:12.5px; margin-bottom:3px;">'+cat+'</div>'+
      categories[cat].map(function(it){
        return '<label class="chk"><input type="checkbox" data-id="'+it.id+'" '+(it.checked?'checked':'')+'> '+it.label+
          ' <span class="small">(updated '+fmtTime(it.updated_at)+')</span></label>';
      }).join('')+
    '</div>';
  }).join('');

  document.getElementById('checklistCard').innerHTML =
    '<div class="card-head"><div><h3>Non-clinical package checklist</h3><div class="card-sub">GET/PATCH /api/checklist &mdash; persisted in the database, shared across every browser</div></div></div>'+
    html +
    '<div style="width:100%; margin-top:6px;"><div class="flex-between"><span class="small">Package completion</span><span class="small">'+pct+'%</span></div><div class="bar-outer"><div class="bar-inner" style="width:'+pct+'%"></div></div></div>';

  Array.prototype.forEach.call(document.querySelectorAll('#checklistCard input[type=checkbox]'), function(box){
    box.addEventListener('change', async function(){
      const id = box.getAttribute('data-id');
      try{
        await api('/api/checklist/' + id, {method:'PATCH', body: JSON.stringify({checked: box.checked})});
        loadChecklist();
      }catch(e){ alert('Could not save: ' + e.message); box.checked = !box.checked; }
    });
  });
}

let agentDivisions = [];
let activeDivision = null;
let activeAgentStatus = null;

async function loadAgents(){
  if(!agentDivisions.length){
    agentDivisions = await api('/api/agents/divisions');
    renderAgentFilters();
  }
  let path = '/api/agents?';
  if(activeDivision) path += 'division=' + encodeURIComponent(activeDivision) + '&';
  if(activeAgentStatus) path += 'status=' + encodeURIComponent(activeAgentStatus) + '&';
  const agentsList = await api(path);
  document.getElementById('agentCount').textContent = agentsList.length + ' agents shown';

  document.getElementById('agentGrid').innerHTML = agentsList.map(function(a){
    const pill = a.status === 'implemented' ? livePill() : staticPill();
    let body, foot;
    if(a.status === 'implemented'){
      const last = a.last_run;
      body = last
        ? ('<div style="margin-bottom:6px;">'+statusPill(last.status)+' <span class="small">'+last.trigger+' run, '+fmtTime(last.started_at)+'</span></div>'+
           '<div>'+ (last.summary || '') + '</div>')
        : '<div class="small">No runs yet &mdash; first scheduled run happens shortly after startup.</div>';
      foot = '<span>'+a.division+' &middot; every '+a.interval_minutes+' min</span>'+
        '<button data-agent="'+a.key+'" class="runBtn">Run now</button>';
    } else {
      body = '<div class="small">Reserved slot in the ~100-agent taxonomy &mdash; interface defined, not yet wired to a live source.</div>';
      foot = '<span>'+a.division+' &middot; planned</span>';
    }
    return agentCard('agent-'+a.key, a.name, a.description, pill, body, foot);
  }).join('');

  Array.prototype.forEach.call(document.querySelectorAll('.runBtn'), function(btn){
    btn.addEventListener('click', async function(){
      btn.disabled = true; btn.textContent = 'Running...';
      try{
        await api('/api/agents/' + btn.getAttribute('data-agent') + '/run', {method:'POST'});
        setTimeout(loadAgents, 3000); // give the background task a moment to finish
      }catch(e){ alert('Could not trigger agent: ' + e.message); }
      finally{ btn.disabled = false; btn.textContent = 'Run now'; }
    });
  });
}

function renderAgentFilters(){
  const box = document.getElementById('agentFilters');
  const divisionBtns = ['All divisions'].concat(agentDivisions).map(function(d){
    const val = d === 'All divisions' ? null : d;
    const active = activeDivision === val;
    return '<button class="tabbtn'+(active?' active':'')+'" data-division="'+(val||'')+'">'+d+'</button>';
  }).join('');
  const statusBtns = ['All statuses', 'implemented', 'planned'].map(function(s){
    const val = s === 'All statuses' ? null : s;
    const active = activeAgentStatus === val;
    return '<button class="tabbtn'+(active?' active':'')+'" data-status="'+(val||'')+'">'+s+'</button>';
  }).join('');
  box.innerHTML = '<div class="row" style="gap:6px;">'+divisionBtns+'</div><div class="row" style="gap:6px;">'+statusBtns+'</div>';
  Array.prototype.forEach.call(box.querySelectorAll('[data-division]'), function(btn){
    btn.addEventListener('click', function(){ activeDivision = btn.getAttribute('data-division') || null; renderAgentFilters(); loadAgents(); });
  });
  Array.prototype.forEach.call(box.querySelectorAll('[data-status]'), function(btn){
    btn.addEventListener('click', function(){ activeAgentStatus = btn.getAttribute('data-status') || null; renderAgentFilters(); loadAgents(); });
  });
}

async function loadSources(){
  const sources = await api('/api/sources');
  const rows = sources.map(function(s){
    const badge = s.status === 'connected' ? livePill() : staticPill();
    return '<tr><td>'+s.name+'<div class="small">'+s.category+' &middot; '+s.integration_type+'</div></td>'+
      '<td>'+badge+'</td><td>'+s.agent_key+'</td><td class="small">'+s.description+'</td></tr>';
  }).join('');
  const connected = sources.filter(function(s){return s.status==='connected';}).length;
  document.getElementById('sourcesCard').innerHTML =
    '<div class="card-head"><div><h3>Source registry, '+connected+' of '+sources.length+' connected</h3>'+
    '<div class="card-sub">Served live from GET /api/sources &mdash; every source named in the architecture spec, with its real integration status</div></div></div>'+
    '<div class="scrollbox" style="max-height:420px;"><table><thead><tr><th>Source</th><th>Status</th><th>Agent</th><th>Description</th></tr></thead><tbody>'+rows+'</tbody></table></div>';
}

let cyInstance = null;

async function loadGraphForSelected(){
  const c = candidatesCache.find(function(x){return x.slug===selectedSlug;});
  const symbol = c ? c.genes.split(/[,+]/)[0].trim() : '';
  document.getElementById('graphIntro').textContent = 'Knowledge graph neighborhood around ' + symbol + ' (served from GET /api/graph/genes/' + symbol + '/subgraph).';
  let sub;
  try{
    sub = await api('/api/graph/genes/' + encodeURIComponent(symbol) + '/subgraph?depth=2');
  }catch(e){
    document.getElementById('graphViz').innerHTML = '<div class="small" style="padding:12px;">No graph node seeded for '+symbol+' yet.</div>';
    document.getElementById('graphLegend').textContent = '';
    return;
  }
  const typeColor = {gene:'#185fa5', disease:'#a32d2d', pathway:'#0f6e56', drug:'#854f0b', variant:'#5c5b57'};
  const elements = sub.nodes.map(function(n){
    return {data:{id:'n'+n.id, label:n.label, type:n.node_type}};
  }).concat(sub.edges.map(function(e){
    return {data:{id:'e'+e.id, source:'n'+e.source_id, target:'n'+e.target_id, label:e.edge_type}};
  }));
  if(cyInstance){ cyInstance.destroy(); }
  cyInstance = cytoscape({
    container: document.getElementById('graphViz'),
    elements: elements,
    style: [
      {selector:'node', style:{
        'background-color': function(ele){ return typeColor[ele.data('type')] || '#5c5b57'; },
        'label':'data(label)', 'color': getComputedStyle(document.documentElement).getPropertyValue('--text'),
        'font-size':10, 'text-valign':'bottom', 'text-margin-y':4, 'width':26, 'height':26,
      }},
      {selector:'edge', style:{
        'width':1.5, 'line-color': getComputedStyle(document.documentElement).getPropertyValue('--border-strong'),
        'target-arrow-color': getComputedStyle(document.documentElement).getPropertyValue('--border-strong'),
        'target-arrow-shape':'triangle', 'curve-style':'bezier',
        'label':'data(label)', 'font-size':8, 'color': getComputedStyle(document.documentElement).getPropertyValue('--text-muted'),
      }},
    ],
    layout: {name:'cose', animate:false, padding:20},
  });
  const types = Array.from(new Set(sub.nodes.map(function(n){return n.node_type;})));
  document.getElementById('graphLegend').innerHTML = types.map(function(t){
    return '<span style="display:inline-flex; align-items:center; gap:4px; margin-right:12px;"><span style="width:9px; height:9px; border-radius:50%; display:inline-block; background:'+(typeColor[t]||'#5c5b57')+';"></span>'+t+'</span>';
  }).join('') + '<span>'+sub.nodes.length+' nodes, '+sub.edges.length+' edges</span>';
}

function confidencePill(c){
  const pct = Math.round(c*100);
  const cls = c >= 0.7 ? 'pill-live' : (c >= 0.4 ? 'pill-warn' : 'pill-danger');
  return '<span class="pill '+cls+'">'+pct+'% confidence</span>';
}

async function loadHypotheses(){
  const hyps = await api('/api/hypotheses?candidate=' + encodeURIComponent(selectedSlug));
  if(!hyps.length){
    document.getElementById('hypothesesBox').innerHTML = '<div class="card"><div class="small">No hypothesis chains seeded for this candidate yet.</div></div>';
    return;
  }
  document.getElementById('hypothesesBox').innerHTML = hyps.map(function(h){
    const steps = h.steps.map(function(s){
      const papers = s.supporting_papers.map(function(p){
        return p.url ? '<a href="'+p.url+'" target="_blank">'+p.title+'</a>' : p.title;
      }).join('; ');
      return '<div style="padding:10px 0; border-bottom:0.5px solid var(--border);">'+
        '<div class="flex-between"><b style="font-size:12.5px;">'+s.from_label+' &rarr; '+s.to_label+'</b>'+confidencePill(s.confidence)+'</div>'+
        '<div class="small" style="margin:4px 0;">Status: '+s.experimental_status+(s.conflicting_evidence?(' &middot; Conflicting evidence: '+s.conflicting_evidence):'')+'</div>'+
        (papers ? '<div class="small">Evidence: '+papers+'</div>' : '')+
        (s.recommended_next_experiment ? '<div class="small" style="color:var(--accent-text); margin-top:3px;">Next experiment: '+s.recommended_next_experiment+'</div>' : '')+
      '</div>';
    }).join('');
    return '<div class="card card-wide" style="margin-bottom:14px;">'+
      '<div class="card-head"><div><h3>Hypothesis '+h.number+': '+h.title+'</h3><div class="card-sub">'+h.gene_symbol+' &middot; status: '+h.status+'</div></div>'+confidencePill(h.overall_confidence)+'</div>'+
      steps +
    '</div>';
  }).join('');
}

async function loadLabRecommendations(){
  const recs = await api('/api/lab/recommendations');
  if(!recs.length){
    document.getElementById('labRecommendationsCard').innerHTML = '<div class="small">No open recommendations &mdash; every seeded hypothesis step is validated.</div>';
    return;
  }
  const rows = recs.map(function(r){
    return '<tr><td>H'+r.hypothesis_number+': '+r.hypothesis_title+'<div class="small">'+r.step.from_label+' &rarr; '+r.step.to_label+'</div></td>'+
      '<td>'+confidencePill(r.step.confidence)+'</td><td>'+r.step.recommended_next_experiment+'</td><td class="small">'+r.reason+'</td></tr>';
  }).join('');
  document.getElementById('labRecommendationsCard').innerHTML =
    '<div class="card-head"><div><h3>AI-recommended next experiments</h3><div class="card-sub">GET /api/lab/recommendations &mdash; traceable readout of the weakest-evidenced open hypothesis steps, ranked ascending by confidence</div></div></div>'+
    '<div class="scrollbox" style="max-height:320px;"><table><thead><tr><th>Hypothesis / link</th><th>Confidence</th><th>Recommended experiment</th><th>Why</th></tr></thead><tbody>'+rows+'</tbody></table></div>';
}

function experimentStatusPill(status){
  if(status==='completed') return '<span class="pill pill-live">completed</span>';
  if(status==='in_progress') return '<span class="pill pill-warn">in progress</span>';
  if(status==='blocked') return '<span class="pill pill-danger">blocked</span>';
  return '<span class="pill pill-static">planned</span>';
}

async function loadExperiments(){
  const exps = await api('/api/lab/experiments?candidate=' + encodeURIComponent(selectedSlug));
  if(!exps.length){
    document.getElementById('experimentsCard').innerHTML = '<div class="small">No experiments logged for this candidate yet. Use POST /api/lab/experiments to add one.</div>';
    return;
  }
  const rows = exps.map(function(e){
    return '<tr><td>'+e.title+'<div class="small">'+e.objective+'</div></td><td>'+e.assay_type+'</td>'+
      '<td>'+experimentStatusPill(e.status)+'</td><td>'+e.owner+'</td><td class="small">'+fmtTime(e.updated_at)+'</td></tr>';
  }).join('');
  document.getElementById('experimentsCard').innerHTML =
    '<div class="card-head"><div><h3>Experiment log</h3><div class="card-sub">GET /api/lab/experiments?candidate='+selectedSlug+'</div></div></div>'+
    '<table><thead><tr><th>Experiment</th><th>Assay</th><th>Status</th><th>Owner</th><th>Updated</th></tr></thead><tbody>'+rows+'</tbody></table>';
}

async function loadPortfolioHealth(){
  const health = await api('/api/dashboard/health');
  document.getElementById('portfolioGrid').innerHTML = health.map(function(h){
    const body =
      field('Checklist completion', h.checklist_completion_pct+'%') +
      field('Avg. hypothesis confidence', Math.round(h.avg_hypothesis_confidence*100)+'%') +
      field('Open high-risk flags', h.open_high_risk_flags) +
      field('Experiments in progress / completed', h.experiments_in_progress+' / '+h.experiments_completed) +
      field('Milestones planned', h.milestones_total);
    return agentCard('health-'+h.candidate_slug, h.candidate_name, 'Portfolio composite score '+h.scoring_composite.toFixed(2)+' / 5', staticPill(), body, '');
  }).join('');
}

async function loadOperations(){
  const ops = await api('/api/ops/summary');
  const kpis = [
    {n: ops.vendor_count, l: 'Verified CRO/vendor records'},
    {n: ops.study_count, l: 'Operational studies'},
    {n: ops.active_study_count, l: 'Active studies'},
    {n: ops.demo_study_count, l: 'Clearly labelled demo studies'},
  ];
  document.getElementById('opsKpiRow').innerHTML = kpis.map(function(k){
    return '<div class="kpi"><div class="n">'+k.n+'</div><div class="l">'+k.l+'</div></div>';
  }).join('');

  const studyRows = ops.studies.map(function(s){
    return '<tr><td>'+s.title+(s.is_demo?' <span class="pill pill-warn">DEMO</span>':'')+
      '<div class="small">'+s.study_type+'</div></td><td>'+s.candidate_slug+'</td><td>'+s.status+'</td><td>'+s.owner+'</td></tr>';
  }).join('');
  document.getElementById('studiesCard').innerHTML =
    '<div class="card-head"><div><h3>CRO study registry</h3><div class="card-sub">Live from GET /api/ops/summary</div></div></div>'+
    (studyRows ? '<table><thead><tr><th>Study</th><th>Candidate</th><th>Status</th><th>Owner</th></tr></thead><tbody>'+studyRows+'</tbody></table>' : '<div class="small">No studies imported yet.</div>');

  const readinessRows = Object.keys(ops.readiness).map(function(slug){
    const counts = ops.readiness[slug];
    return '<tr><td><b>'+slug+'</b></td><td>'+(counts.present||0)+'</td><td>'+(counts.provisional||0)+'</td><td>'+(counts.missing||0)+'</td><td>'+(counts.failed||0)+'</td></tr>';
  }).join('');
  document.getElementById('readinessCard').innerHTML =
    '<div class="card-head"><div><h3>CMC / nonclinical / regulatory readiness</h3><div class="card-sub">Evidence status is explicit; missing evidence is never represented as progress.</div></div></div>'+
    (readinessRows ? '<table><thead><tr><th>Candidate</th><th>Present</th><th>Provisional</th><th>Missing</th><th>Failed</th></tr></thead><tbody>'+readinessRows+'</tbody></table>' : '<div class="small">No readiness evidence imported yet.</div>');
}

function renderFooter(){
  document.getElementById('footerBox').innerHTML =
    '<p>This dashboard is served by the CADDTARD API itself (FastAPI + StaticFiles) &mdash; there is no local HTML file to open. '+
    'All data comes from same-origin <code>/api/*</code> endpoints backed by a persistent database (SQLite locally, Postgres in Docker Compose). '+
    'v3.1 MVP implements the full seven-layer architecture: a Layer 1 data-source registry, a Layer 2 relational knowledge graph (Postgres-backed today, Neo4j-swappable per ARCHITECTURE.md), '+
    'a Layer 3 agent taxonomy spanning Genomics/Disease Biology/Therapeutics/AI Science/Development, a Layer 4 evidence-graded reasoning engine, a Layer 5 lab operating system, '+
    'and this Layer 6 executive view. "Live agent" pills call real public sources now; "Reference" pills are reserved, honestly-labeled slots not yet wired up &mdash; see ARCHITECTURE.md for the full implemented-vs-planned map.</p>'+
    '<p>Full interactive API reference: <a href="/docs" target="_blank">/docs</a> (Swagger) or <a href="/redoc" target="_blank">/redoc</a>.</p>'+
    '<p>Generated ' + new Date().toLocaleString() + '. For internal funding/R&D use only &mdash; not medical advice, not a regulatory submission.</p>';
}

async function boot(){
  try{
    const health = await api('/health');
    document.getElementById('apiStatus').textContent = 'Connected to ' + health.app + ' v' + health.version;
  }catch(e){
    document.getElementById('apiStatus').textContent = 'API unreachable';
    showConnectionError(e);
    return;
  }
  await Promise.all([
    loadKPIs(), loadScoring(), loadCandidateTabs(), loadAgents(),
    loadSources(), loadPortfolioHealth(), loadLabRecommendations(), loadOperations(),
  ]);
  renderFooter();
}

document.getElementById('refreshAll').addEventListener('click', function(){
  loadAgents(); loadPortfolioHealth(); loadLabRecommendations(); loadOperations();
});

boot();
