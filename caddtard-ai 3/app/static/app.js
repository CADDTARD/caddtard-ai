const API = ""; // same-origin: dashboard is served by the same FastAPI app it talks to
let selectedSlug = null;
let candidatesCache = [];
let compoundsCache = [];
let selectedCompoundSlug = null;
let compoundSearchTimer = null;
let pocCache = null;
let pocView = 'plain';

var savedTheme = localStorage.getItem('caddtard-theme');
if(savedTheme){ document.documentElement.setAttribute('data-theme', savedTheme); }
document.getElementById('toggleTheme').addEventListener('click', function(){
  var html = document.documentElement;
  var nextTheme = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', nextTheme);
  localStorage.setItem('caddtard-theme', nextTheme);
  this.setAttribute('aria-label', nextTheme === 'dark' ? 'Use light theme' : 'Use dark theme');
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
  el.hidden = false;
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
  const [genes, scoring, candidates, agentsList, sourcesList, compoundSummary] = await Promise.all([
    api('/api/genes'), api('/api/scoring'), api('/api/candidates'), api('/api/agents'), api('/api/sources'), api('/api/compounds/summary'),
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
    {n: compoundSummary.verified+' / '+compoundSummary.total, l:'Compounds independently verified'},
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
    loadGraphForSelected(), loadHypotheses(), loadExperiments(), loadDiseaseBiologyWorkbench(),
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
        '<span class="scheduled-chip">Scheduled automatically</span>';
    } else {
      body = '<div class="small">Reserved slot in the ~100-agent taxonomy &mdash; interface defined, not yet wired to a live source.</div>';
      foot = '<span>'+a.division+' &middot; planned</span>';
    }
    return agentCard('agent-'+a.key, a.name, a.description, pill, body, foot);
  }).join('');

}

function biologyStage(state, step, title, description, meta){
  var cls = state === 'live' ? 'is-live' : (state === 'active' ? 'is-active' : 'is-planned');
  var label = state === 'live' ? 'LIVE' : (state === 'active' ? 'CONNECTED' : 'PLANNED');
  return '<div class="biology-stage '+cls+'"><div class="biology-stage-index">'+step+'</div><div><div class="biology-stage-label">'+label+'</div><h4>'+escapeGraphHtml(title)+'</h4><p>'+escapeGraphHtml(description)+'</p><small>'+escapeGraphHtml(meta || '')+'</small></div></div>';
}

function biologyRunDetail(agent){
  if(!agent.latest_run) return '<div class="small">Awaiting the first scheduled run.</div>';
  var run = agent.latest_run;
  var detail = run.detail || {};
  var facts = [];
  if(Array.isArray(detail.genes)){
    facts = detail.genes.slice(0,4).map(function(g){
      return '<span class="biology-fact">'+escapeGraphHtml(g.gene)+(g.monarch_hit ? ' · '+escapeGraphHtml(g.monarch_hit) : '')+'</span>';
    });
  } else if(Array.isArray(detail.searches)){
    var named = detail.searches.filter(function(s){return s.who_gho_has_named_indicator;}).length;
    facts.push('<span class="biology-fact">'+named+' named WHO indicators</span>');
    detail.searches.slice(0,3).forEach(function(s){ facts.push('<span class="biology-fact">'+escapeGraphHtml(s.term)+'</span>'); });
  } else if(detail.error){
    facts.push('<span class="biology-fact danger">'+escapeGraphHtml(detail.error)+'</span>');
  }
  return '<div class="biology-run-head">'+statusPill(run.status)+'<span class="small">'+fmtTime(run.finished_at || run.started_at)+'</span></div>'+
    '<p>'+escapeGraphHtml(run.summary || 'Scheduled run completed.')+'</p>'+
    (facts.length ? '<div class="biology-facts">'+facts.join('')+'</div>' : '');
}

async function loadDiseaseBiologyWorkbench(){
  var programs = candidatesCache.length ? candidatesCache : await api('/api/candidates');
  if(!selectedSlug && programs.length) selectedSlug = programs[0].slug;
  var responses = await Promise.all([
    api('/api/agents/disease-biology/workbench'),
    api('/api/candidates/' + selectedSlug),
    api('/api/hypotheses?candidate=' + encodeURIComponent(selectedSlug)),
  ]);
  var workbench = responses[0], candidate = responses[1], hypotheses = responses[2];
  var implemented = workbench.agents.filter(function(a){return a.status === 'implemented';});
  var agentByKey = {};
  workbench.agents.forEach(function(a){agentByKey[a.key] = a;});

  document.getElementById('biologyProgramTitle').textContent = candidate.name;
  document.getElementById('biologyProgramSummary').innerHTML =
    '<strong>'+escapeGraphHtml(candidate.genes)+'</strong> · '+escapeGraphHtml(candidate.organ)+' · '+escapeGraphHtml(candidate.inheritance)+
    '<br><span class="small">Mechanistic focus: '+escapeGraphHtml(candidate.mechanism)+'</span>';

  var kpis = [
    {n: workbench.counts.implemented+' / '+workbench.counts.total, l:'Disease biology agents live'},
    {n: workbench.counts.healthy_latest_runs, l:'Healthy latest scheduled runs'},
    {n: workbench.counts.connected_sources, l:'Connected biology sources'},
    {n: hypotheses.length, l:'Evidence-graded hypotheses for program'},
  ];
  document.getElementById('biologyKpis').innerHTML = kpis.map(function(k){
    return '<div class="kpi"><div class="n">'+k.n+'</div><div class="l">'+k.l+'</div></div>';
  }).join('');

  var diseaseLive = agentByKey.disease_phenotype && agentByKey.disease_phenotype.latest_run && agentByKey.disease_phenotype.latest_run.status === 'success';
  var burdenLive = agentByKey.who_burden && agentByKey.who_burden.latest_run && agentByKey.who_burden.latest_run.status === 'success';
  document.getElementById('biologyPipeline').innerHTML = [
    biologyStage(diseaseLive?'live':'active','01','Disease resolution','Normalize genes, diseases and cross-species phenotype links.','Monarch Initiative'),
    biologyStage(diseaseLive?'active':'planned','02','Phenotype profile','Organize gene-associated phenotypes into a program-ready signature.','Phenotype interface staged'),
    biologyStage(burdenLive?'live':'active','03','Burden & natural history','Separate measured burden from explicit evidence gaps.','WHO GHO + natural-history interface'),
    biologyStage('planned','04','Cell & pathway systems','Connect lysosome, autophagy, mitochondria and immune biology.','Reserved specialist agents'),
    biologyStage(hypotheses.length?'active':'planned','05','Experimental handoff','Translate open causal links into testable biological experiments.',hypotheses.length+' active hypothesis chains'),
  ].join('');

  document.getElementById('biologyEvidenceFeed').innerHTML = implemented.map(function(agent){
    return '<article class="biology-evidence-item"><div class="flex-between"><h4>'+escapeGraphHtml(agent.name)+'</h4><span class="small">every '+agent.interval_minutes+' min</span></div>'+biologyRunDetail(agent)+'</article>';
  }).join('') || '<div class="small">No Disease Biology agents are implemented yet.</div>';

  document.getElementById('biologyAgentGrid').innerHTML = workbench.agents.map(function(agent){
    var pill = agent.status === 'implemented' ? livePill() : '<span class="pill pill-static">interface reserved</span>';
    var body = agent.status === 'implemented'
      ? biologyRunDetail(agent)
      : '<p class="small">'+escapeGraphHtml(agent.description)+'</p><div class="biology-interface-note">Defined contract · awaiting validated data source</div>';
    return agentCard('biology-agent-'+agent.key, escapeGraphHtml(agent.name), escapeGraphHtml(agent.description), pill, body,
      agent.status === 'implemented' ? '<span>Scheduled every '+agent.interval_minutes+' min</span><span>Read only</span>' : '<span>Planned capability</span>');
  }).join('');

  var sourceRows = workbench.sources.map(function(source){
    return '<tr><td><b>'+escapeGraphHtml(source.name)+'</b><div class="small">'+escapeGraphHtml(source.integration_type)+'</div></td><td>'+(source.status==='connected'?livePill():staticPill())+'</td><td>'+escapeGraphHtml(source.agent_key)+'</td><td class="small">'+escapeGraphHtml(source.description)+'</td></tr>';
  }).join('');
  document.getElementById('biologySourcesCard').innerHTML = '<div class="card-head"><div><h3>Disease biology data fabric</h3><div class="card-sub">Only connected sources are represented as live evidence.</div></div><span class="pill pill-select">'+workbench.sources.length+' sources</span></div>'+
    (sourceRows ? '<div class="scrollbox"><table><thead><tr><th>Source</th><th>Status</th><th>Agent</th><th>Purpose</th></tr></thead><tbody>'+sourceRows+'</tbody></table></div>' : '<div class="small">No sources registered for this division.</div>');
}

function compoundVerificationPill(status){
  return '<span class="compound-verify '+escapeGraphHtml(status)+'">'+escapeGraphHtml(status)+'</span>';
}

function compoundRoleLabel(role){ return String(role || '').replace(/_/g, ' '); }

function renderCompoundDetail(compound){
  var evidence = (compound.evidence || []).map(function(item){
    var title = escapeGraphHtml(item.title);
    var heading = item.url
      ? '<a href="'+escapeGraphHtml(item.url)+'" target="_blank" rel="noreferrer">'+title+' ↗</a>'
      : '<strong>'+title+'</strong>';
    return '<div class="evidence-item">'+heading+'<small>'+escapeGraphHtml(item.evidence_type.replace(/_/g,' '))+' · '+escapeGraphHtml(item.supports)+'</small></div>';
  }).join('');
  var identifiers = [
    compound.cas_number ? 'CAS '+escapeGraphHtml(compound.cas_number) : '',
    compound.pubchem_cid ? 'PubChem '+escapeGraphHtml(compound.pubchem_cid) : '',
    compound.molecular_formula ? escapeGraphHtml(compound.molecular_formula) : '',
    compound.molecular_weight ? compound.molecular_weight+' g/mol' : ''
  ].filter(Boolean).join(' · ') || 'Exact registry identifiers incomplete';
  document.getElementById('compoundDetail').innerHTML =
    '<div class="flex-between"><span class="pill pill-select">Tier '+escapeGraphHtml(compound.tier)+'</span>'+compoundVerificationPill(compound.verification_status)+'</div>'+
    '<h3>'+escapeGraphHtml(compound.name)+'</h3><div class="compound-subtitle">'+escapeGraphHtml(compound.chemical_class)+'<br>'+identifiers+'</div>'+
    '<div class="identity-flags"><span class="identity-flag '+(compound.identity_verified?'yes':'')+'">'+(compound.identity_verified?'✓':'?')+' Identity</span><span class="identity-flag '+(compound.mechanism_verified?'yes':'')+'">'+(compound.mechanism_verified?'✓':'?')+' Mechanism</span><span class="identity-flag">0 FTO clearances</span></div>'+
    '<div class="compound-caveat"><b>Limitation:</b> '+escapeGraphHtml(compound.caveat)+'</div>'+
    '<div class="compound-detail-section"><span>Role / target</span><p><b>'+escapeGraphHtml(compoundRoleLabel(compound.role))+'</b><br>'+escapeGraphHtml(compound.target_site)+'</p></div>'+
    '<div class="compound-detail-section"><span>Potency interpretation</span><p>'+escapeGraphHtml(compound.potency)+'</p></div>'+
    '<div class="compound-detail-section"><span>Platform fit</span><p>'+escapeGraphHtml(compound.platform_fit)+'</p></div>'+
    '<div class="compound-detail-section"><span>Development / availability</span><p>'+escapeGraphHtml(compound.development_status)+'<br><br>'+escapeGraphHtml(compound.availability_note)+'</p></div>'+
    '<div class="compound-detail-section"><span>Evidence ledger</span><div class="evidence-list">'+evidence+'</div></div>';
}

function renderCompoundGrid(){
  var grid = document.getElementById('compoundGrid');
  document.getElementById('compoundCount').textContent = compoundsCache.length+' records shown';
  if(!compoundsCache.length){
    grid.innerHTML = '<div class="card"><div class="small">No compounds match the current verification filters.</div></div>';
    document.getElementById('compoundDetail').innerHTML = '<div class="small">Adjust the filters to inspect a compound.</div>';
    return;
  }
  if(!selectedCompoundSlug || !compoundsCache.some(function(c){return c.slug===selectedCompoundSlug;})) selectedCompoundSlug = compoundsCache[0].slug;
  grid.innerHTML = compoundsCache.map(function(c){
    var selected = c.slug === selectedCompoundSlug ? ' active' : '';
    return '<button type="button" class="compound-card'+selected+'" data-compound="'+escapeGraphHtml(c.slug)+'">'+
      '<div class="compound-card-head"><h3>'+escapeGraphHtml(c.name)+'</h3>'+compoundVerificationPill(c.verification_status)+'</div>'+
      '<div class="compound-meta"><span class="pill pill-static">Tier '+escapeGraphHtml(c.tier)+'</span><span class="pill pill-select">'+escapeGraphHtml(compoundRoleLabel(c.role))+'</span></div>'+
      '<p>'+escapeGraphHtml(c.target_site)+'</p></button>';
  }).join('');
  Array.prototype.forEach.call(grid.querySelectorAll('[data-compound]'), function(card){
    card.addEventListener('click', function(){
      selectedCompoundSlug = card.getAttribute('data-compound');
      renderCompoundGrid();
    });
  });
  renderCompoundDetail(compoundsCache.find(function(c){return c.slug===selectedCompoundSlug;}));
}

async function loadCompounds(){
  var summary = await api('/api/compounds/summary');
  var kpis = [
    {n:summary.total,l:'Landscape records'},
    {n:summary.verified,l:'Identity + mechanism verified'},
    {n:summary.partial,l:'Partially verified'},
    {n:summary.unverified,l:'Quarantined / unverified'},
    {n:summary.direct_inhibitors,l:'Direct-inhibitor records'},
    {n:summary.fto_cleared,l:'FTO clearances completed'},
  ];
  document.getElementById('compoundKpis').innerHTML = kpis.map(function(k){return '<div class="kpi"><div class="n">'+k.n+'</div><div class="l">'+k.l+'</div></div>';}).join('');
  var params = new URLSearchParams();
  var q = document.getElementById('compoundSearch').value.trim();
  var tier = document.getElementById('compoundTier').value;
  var role = document.getElementById('compoundRole').value;
  var verification = document.getElementById('compoundVerification').value;
  if(q) params.set('q',q); if(tier) params.set('tier',tier); if(role) params.set('role',role); if(verification) params.set('verification',verification);
  compoundsCache = await api('/api/compounds'+(params.toString()?'?'+params.toString():''));
  renderCompoundGrid();
}

['compoundTier','compoundRole','compoundVerification'].forEach(function(id){
  document.getElementById(id).addEventListener('change', loadCompounds);
});
document.getElementById('compoundSearch').addEventListener('input', function(){
  clearTimeout(compoundSearchTimer);
  compoundSearchTimer = setTimeout(loadCompounds, 220);
});

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

const graphTypeColor = {gene:'#1769aa', disease:'#c33d4a', pathway:'#16866a', drug:'#b56a10', variant:'#6f63a8'};

function escapeGraphHtml(value){
  return String(value == null ? '' : value).replace(/[&<>"']/g, function(ch){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[ch];
  });
}

function renderGraphDetails(node){
  const panel = document.getElementById('graphDetails');
  if(!node){
    panel.innerHTML = '<div class="graph-details-kicker">Selected node</div><h3>Explore the pathway</h3><p>Select a node to see its type, reference, scientific context, and direct relationships.</p>';
    return;
  }
  const data = node.data();
  const props = data.properties || {};
  const relations = node.connectedEdges().map(function(edge){
    const other = edge.source().id() === node.id() ? edge.target() : edge.source();
    return '<li><b>'+escapeGraphHtml(edge.data('label').replace(/_/g, ' '))+'</b> &rarr; '+escapeGraphHtml(other.data('label'))+'</li>';
  }).join('');
  const context = props.description || props.protein_name || props.organ || props.inheritance || props.omim || '';
  panel.innerHTML =
    '<div class="graph-details-kicker">Selected node</div>'+
    '<span class="graph-detail-type" style="background:'+ (graphTypeColor[data.type] || '#5c5b57') +'">'+escapeGraphHtml(data.type)+'</span>'+
    '<h3>'+escapeGraphHtml(data.label)+'</h3>'+
    (context ? '<p>'+escapeGraphHtml(context)+'</p>' : '')+
    (data.externalRef ? '<div class="graph-detail-row"><span>External reference</span><strong>'+escapeGraphHtml(data.externalRef)+'</strong></div>' : '')+
    (props.inheritance ? '<div class="graph-detail-row"><span>Inheritance</span><strong>'+escapeGraphHtml(props.inheritance)+'</strong></div>' : '')+
    (props.organ ? '<div class="graph-detail-row"><span>Clinical system</span><strong>'+escapeGraphHtml(props.organ)+'</strong></div>' : '')+
    '<div class="graph-detail-row"><span>Direct relationships ('+node.degree()+')</span>'+(relations ? '<ul class="graph-relations">'+relations+'</ul>' : '<strong>None recorded</strong>')+'</div>';
}

function setGraphFocus(node){
  if(!cyInstance) return;
  cyInstance.elements().removeClass('focused faded selected');
  if(!node){ renderGraphDetails(null); return; }
  const neighborhood = node.closedNeighborhood();
  cyInstance.elements().not(neighborhood).addClass('faded');
  neighborhood.addClass('focused');
  node.addClass('selected');
  renderGraphDetails(node);
}

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
    renderGraphDetails(null);
    return;
  }
  const elements = sub.nodes.map(function(n){
    return {data:{id:'n'+n.id, label:n.label, type:n.node_type, externalRef:n.external_ref, properties:n.properties || {}, focal:n.label===symbol}};
  }).concat(sub.edges.map(function(e){
    return {data:{id:'e'+e.id, source:'n'+e.source_id, target:'n'+e.target_id, label:e.edge_type}};
  }));
  if(cyInstance){ cyInstance.destroy(); }
  cyInstance = cytoscape({
    container: document.getElementById('graphViz'),
    elements: elements,
    style: [
      {selector:'node', style:{
        'background-color': function(ele){ return graphTypeColor[ele.data('type')] || '#5c5b57'; },
        'border-width':3, 'border-color':'#ffffff', 'border-opacity':1,
        'label':'data(label)', 'color':'#1c1c1a', 'font-size':12, 'font-weight':600,
        'text-wrap':'wrap', 'text-max-width':125, 'text-valign':'bottom', 'text-halign':'center',
        'text-margin-y':8, 'text-background-color':'#ffffff', 'text-background-opacity':0.92,
        'text-background-padding':3, 'text-background-shape':'roundrectangle',
        'width':34, 'height':34, 'overlay-padding':6, 'overlay-opacity':0,
      }},
      {selector:'node[type = "pathway"]', style:{'shape':'round-rectangle', 'width':44, 'height':36}},
      {selector:'node[type = "disease"]', style:{'shape':'diamond', 'width':40, 'height':40}},
      {selector:'node[type = "drug"]', style:{'shape':'hexagon', 'width':40, 'height':40}},
      {selector:'node[focal]', style:{'width':54, 'height':54, 'border-width':5, 'border-color':'#d6ecff', 'font-size':14, 'z-index':10}},
      {selector:'edge', style:{
        'width':2, 'line-color':'#a7afb8', 'target-arrow-color':'#7d8792',
        'target-arrow-shape':'triangle', 'arrow-scale':0.9, 'curve-style':'bezier',
        'label':'data(label)', 'font-size':9.5, 'font-weight':500, 'color':'#4f5964',
        'text-rotation':'autorotate', 'text-background-color':'#ffffff', 'text-background-opacity':0.88,
        'text-background-padding':2, 'text-margin-y':-7,
      }},
      {selector:'.faded', style:{'opacity':0.13, 'text-opacity':0.08}},
      {selector:'node.selected', style:{'border-color':'#f2b84b', 'border-width':5, 'overlay-color':'#f2b84b', 'overlay-opacity':0.12}},
      {selector:'edge.focused', style:{'width':3, 'line-color':'#4d8fc7', 'target-arrow-color':'#4d8fc7', 'z-index':8}},
    ],
    layout: {
      name:'concentric', animate:false, padding:72, minNodeSpacing:72, avoidOverlap:true,
      concentric:function(node){ return node.data('focal') ? 100 : (node.data('type') === 'pathway' ? 70 : 30); },
      levelWidth:function(){ return 25; }, startAngle:Math.PI * 1.5, sweep:Math.PI * 2,
    },
    minZoom:0.45, maxZoom:2.2,
  });
  cyInstance.on('tap', 'node', function(evt){ setGraphFocus(evt.target); });
  cyInstance.on('tap', function(evt){ if(evt.target === cyInstance) setGraphFocus(null); });
  cyInstance.on('mouseover', 'node', function(){ document.getElementById('graphViz').style.cursor = 'pointer'; });
  cyInstance.on('mouseout', 'node', function(){ document.getElementById('graphViz').style.cursor = 'grab'; });
  const focalNode = cyInstance.nodes().filter(function(n){ return n.data('focal'); }).first();
  if(focalNode && focalNode.length){ setGraphFocus(focalNode); }
  cyInstance.fit(undefined, 52);
  const types = Array.from(new Set(sub.nodes.map(function(n){return n.node_type;})));
  document.getElementById('graphLegend').innerHTML = types.map(function(t){
    return '<span class="graph-legend-item"><span class="graph-legend-dot" style="background:'+(graphTypeColor[t]||'#5c5b57')+';"></span>'+escapeGraphHtml(t)+'</span>';
  }).join('') + '<span class="graph-count">'+sub.nodes.length+' nodes &middot; '+sub.edges.length+' relationships</span>';
}

document.getElementById('graphZoomIn').addEventListener('click', function(){
  if(cyInstance) cyInstance.zoom({level:Math.min(cyInstance.zoom()*1.25, cyInstance.maxZoom()), renderedPosition:{x:cyInstance.width()/2,y:cyInstance.height()/2}});
});
document.getElementById('graphZoomOut').addEventListener('click', function(){
  if(cyInstance) cyInstance.zoom({level:Math.max(cyInstance.zoom()/1.25, cyInstance.minZoom()), renderedPosition:{x:cyInstance.width()/2,y:cyInstance.height()/2}});
});
document.getElementById('graphFit').addEventListener('click', function(){ if(cyInstance) cyInstance.animate({fit:{eles:cyInstance.elements(),padding:52},duration:280}); });

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

function pocStateLabel(state){
  if(state === 'live_evidence') return '<span class="poc-state live"><span class="status-dot dot-green"></span>Live evidence feed</span>';
  if(state === 'connected_waiting') return '<span class="poc-state waiting"><span class="status-dot dot-amber"></span>Connected · awaiting successful run</span>';
  return '<span class="poc-state ready">Interface ready</span>';
}

function renderPocWorkbench(){
  if(!pocCache) return;
  var data = pocCache;
  var detailed = pocView === 'scientist';
  document.getElementById('pocPlainView').classList.toggle('active', !detailed);
  document.getElementById('pocScientistView').classList.toggle('active', detailed);
  document.getElementById('pocTitle').textContent = data.program.title;
  document.getElementById('pocMission').textContent = detailed ? data.program.mission : data.program.plain_language;

  document.getElementById('pocTruthStrip').innerHTML =
    '<div><span>Program variant</span><strong>'+escapeGraphHtml(data.program.transcript)+' · '+escapeGraphHtml(data.program.program_variant)+'</strong></div>'+
    '<div><span>Evidence boundary</span><strong>'+escapeGraphHtml(detailed ? data.evidence_boundary.variant_status : 'The exact variant still needs mechanism confirmation')+'</strong></div>'+
    '<div><span>Model rule</span><strong>'+escapeGraphHtml(detailed ? data.evidence_boundary.model_anchor : 'A512P informs the pathway; it does not prove Leu756Arg biology')+'</strong></div>';

  var kpis = [
    {n:data.counts.biology_steps, l:'linked biology steps'},
    {n:data.counts.experimental_groups, l:'experimental groups'},
    {n:data.counts.go_no_go_gates, l:'go / no-go gates'},
    {n:data.counts.validated_gates+' / '+data.counts.go_no_go_gates, l:'experimentally validated gates'},
    {n:data.counts.live_copilots+' / '+data.counts.copilot_interfaces, l:'copilots with successful live evidence'},
  ];
  document.getElementById('pocKpis').innerHTML = kpis.map(function(k){return '<div class="kpi"><div class="n">'+k.n+'</div><div class="l">'+k.l+'</div></div>';}).join('');

  document.getElementById('pocChain').innerHTML = data.biology_chain.map(function(step){
    var assay = detailed ? '<div class="poc-assays">'+step.assays.map(function(a){return '<span>'+escapeGraphHtml(a)+'</span>';}).join('')+'</div>' : '';
    return '<article class="poc-chain-step"><div class="poc-chain-number">'+step.step+'</div><div><small>'+escapeGraphHtml(step.label)+'</small><p>'+escapeGraphHtml(detailed ? step.scientist : step.plain)+'</p>'+assay+'</div></article>';
  }).join('');

  document.getElementById('pocGroups').innerHTML = data.experimental_groups.map(function(group, index){
    return '<div class="poc-list-row"><span>'+(index+1)+'</span><div><strong>'+escapeGraphHtml(group.name)+'</strong><small>'+escapeGraphHtml(group.purpose)+'</small></div></div>';
  }).join('');

  document.getElementById('pocTiers').innerHTML = data.development_tiers.map(function(tier){
    return '<div class="poc-tier"><b>Tier '+tier.tier+'</b><div><strong>'+escapeGraphHtml(tier.name)+'</strong><small>'+escapeGraphHtml(tier.models)+'</small><p>'+escapeGraphHtml(tier.decision)+'</p></div></div>';
  }).join('');

  document.getElementById('pocGates').innerHTML = data.go_no_go_gates.map(function(gate, index){
    return '<article class="poc-gate"><div class="poc-gate-top"><span>Gate '+(index+1)+'</span><b>Planned</b></div><h4>'+escapeGraphHtml(gate.name)+'</h4><p>'+escapeGraphHtml(gate.question)+'</p></article>';
  }).join('');

  document.getElementById('pocCopilots').innerHTML = data.execution_copilots.map(function(copilot){
    var sourceNames = copilot.sources.length ? copilot.sources.map(function(source){
      var resultClass = source.latest_status === 'success' ? 'ok' : (source.latest_status === 'error' ? 'bad' : 'idle');
      return '<span class="poc-agent-source '+resultClass+'">'+escapeGraphHtml(source.name)+'</span>';
    }).join('') : '<span class="poc-agent-source idle">ELN / LIMS connector not yet configured</span>';
    return '<article class="poc-copilot"><div class="poc-copilot-head"><span class="poc-emoji">'+copilot.emoji+'</span><div><h4>'+escapeGraphHtml(copilot.name)+'</h4>'+pocStateLabel(copilot.state)+'</div></div><p>'+escapeGraphHtml(detailed ? copilot.scientist : copilot.plain)+'</p><div class="poc-deliverable"><span>Delivers</span>'+escapeGraphHtml(copilot.deliverable)+'</div><div class="poc-agent-sources">'+sourceNames+'</div></article>';
  }).join('');

  document.getElementById('pocRigor').innerHTML = data.rigor_locks.map(function(rule){return '<li>'+escapeGraphHtml(rule)+'</li>';}).join('');
  document.getElementById('pocFunding').innerHTML =
    '<div class="poc-funding-truth"><span>'+escapeGraphHtml(data.funding_truth.headline)+'</span><strong>'+escapeGraphHtml(data.funding_truth.current_state)+'</strong><p>'+escapeGraphHtml(data.funding_truth.investment_case)+'</p></div>'+
    data.funding_milestones.map(function(milestone){
      return '<div class="poc-milestone"><span class="poc-milestone-status '+escapeGraphHtml(milestone.status)+'">'+escapeGraphHtml(milestone.status.replace(/_/g,' '))+'</span><div><strong>'+escapeGraphHtml(milestone.name)+'</strong><small>'+escapeGraphHtml(milestone.unlocks)+'</small></div></div>';
    }).join('');

  document.getElementById('pocSources').innerHTML = '<div class="poc-source-grid">'+data.verification_sources.map(function(source){
    return '<a class="poc-source" href="'+escapeGraphHtml(source.url)+'" target="_blank" rel="noreferrer"><strong>'+escapeGraphHtml(source.name)+' ↗</strong><span>'+escapeGraphHtml(source.supports)+'</span></a>';
  }).join('')+'</div>';
}

async function loadPocWorkbench(){
  pocCache = await api('/api/poc');
  renderPocWorkbench();
}

document.getElementById('pocPlainView').addEventListener('click', function(){pocView='plain';renderPocWorkbench();});
document.getElementById('pocScientistView').addEventListener('click', function(){pocView='scientist';renderPocWorkbench();});

function renderFooter(){
  document.getElementById('footerBox').innerHTML =
    '<p>This dashboard is served by the CADDTARD API itself (FastAPI + StaticFiles) &mdash; there is no local HTML file to open. '+
    'All data comes from same-origin <code>/api/*</code> endpoints backed by a persistent database (SQLite locally, Postgres in Docker Compose). '+
    'v3.4 MVP implements the full seven-layer architecture plus a biology-verified proof-of-concept mission control: a Layer 1 data-source registry, a Layer 2 relational knowledge graph (Postgres-backed today, Neo4j-swappable per ARCHITECTURE.md), '+
    'a Layer 3 agent taxonomy spanning Genomics/Disease Biology/Therapeutics/AI Science/Development, a Layer 4 evidence-graded reasoning engine, a Layer 5 lab operating system, '+
    'and this Layer 6 executive view. "Live agent" pills call real public sources now; "Reference" pills are reserved, honestly-labeled slots not yet wired up &mdash; see ARCHITECTURE.md for the full implemented-vs-planned map.</p>'+
    '<p>Full interactive API reference: <a href="/docs" target="_blank">/docs</a> (Swagger) or <a href="/redoc" target="_blank">/redoc</a>.</p>'+
    '<p>Generated ' + new Date().toLocaleString() + '. For internal funding/R&D use only &mdash; not medical advice, not a regulatory submission.</p>';
}

async function boot(){
  try{
    const health = await api('/health');
    document.getElementById('apiStatus').innerHTML = '<span class="status-dot dot-green"></span> Connected to ' + health.app + ' v' + health.version + ' · live data';
  }catch(e){
    document.getElementById('apiStatus').textContent = 'API unreachable';
    showConnectionError(e);
    return;
  }
  await Promise.all([
    loadKPIs(), loadScoring(), loadCandidateTabs(), loadAgents(),
    loadSources(), loadPortfolioHealth(), loadLabRecommendations(), loadOperations(), loadCompounds(), loadPocWorkbench(),
  ]);
  renderFooter();
}

document.getElementById('refreshAll').addEventListener('click', async function(){
  var btn = this;
  var oldText = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Refreshing…';
  try{
    await Promise.all([loadKPIs(), loadScoring(), loadAgents(), loadPortfolioHealth(), loadLabRecommendations(), loadOperations(), loadDiseaseBiologyWorkbench(), loadCompounds(), loadPocWorkbench()]);
    btn.textContent = 'Data refreshed ✓';
    setTimeout(function(){ btn.textContent = oldText; }, 1500);
  }catch(e){
    showConnectionError(e);
    btn.textContent = 'Refresh failed';
    setTimeout(function(){ btn.textContent = oldText; }, 1800);
  }finally{
    btn.disabled = false;
  }
});

boot();
