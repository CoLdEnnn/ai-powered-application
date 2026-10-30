const el=id=>document.getElementById(id);
async function updateStatus(){
  try{
    const response=await fetch('/api/health');
    if(!response.ok)throw new Error('Health check failed');
    const data=await response.json();
    const ready=data.status==='ready';
    el('status-dot').className=ready?'ready':'unavailable';
    el('status-text').textContent=ready?'Local model ready':'Local model unavailable — check the app terminal';
  }catch{
    el('status-dot').className='unavailable';
    el('status-text').textContent='App unavailable — check the app terminal';
  }
}
function node(tag,text,className){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(className)n.className=className;return n;}
function showSources(sources,citations){
  const list=el('source-list');list.replaceChildren();
  sources.forEach(s=>{
    const d=node('details',undefined,'source');
    const cited=(citations||[]).includes(s.context_id);
    d.append(node('summary',`${s.context_id}${cited?' · cited in answer':''}`));
    const score=typeof s.score==='number'?s.score.toFixed(3):'not available';
    d.append(node('p',`Snapshot: ${s.source_snapshot_date||'not stated'} · Review: ${(s.verification_status||'unknown').replaceAll('_',' ')} · Similarity: ${score}`,'meta'));
    d.append(node('p',s.text,'passage'));
    d.append(node('p',`Source: ${(s.source_ids||[]).join(', ')} · ${s.source_locator_en||''}`,'meta'));
    if(s.review_notes)d.append(node('p',s.review_notes,'meta'));
    const links=node('div',undefined,'links');
    (s.source_urls||[]).forEach(raw=>{
      try{const url=new URL(raw);if(!['http:','https:'].includes(url.protocol))return;const a=node('a',url.hostname+' — source page');a.href=url.href;a.target='_blank';a.rel='noopener noreferrer';links.append(a);}catch{}
    });
    d.append(links);list.append(d);
  });
  el('evidence').hidden=!sources.length;
}
el('question-form').addEventListener('submit',async event=>{
  event.preventDefault();const question=el('question').value.trim();if(question.length<2)return;
  el('ask-button').disabled=true;el('ask-button').textContent='Reading sources and answering…';
  el('answer-panel').setAttribute('aria-busy','true');
  ['answer','error','warnings','empty-state','evidence'].forEach(id=>el(id).hidden=true);
  el('elapsed').textContent='';
  try{
    const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question,audience:el('audience').value})});
    const data=await response.json();
    if(!response.ok){const detail=typeof data.detail==='string'?data.detail:'The question could not be processed. Check its length and the local app terminal.';throw new Error(detail);}
    el('answer').textContent=data.answer;el('answer').hidden=false;
    el('elapsed').textContent=`${Number(data.timing_seconds).toFixed(1)} s`;
    const warnings=el('warnings');warnings.replaceChildren();
    (data.warnings||[]).forEach(w=>warnings.append(node('li',w)));warnings.hidden=!warnings.children.length;
    showSources(data.sources||[],data.citation_status?.cited_context_ids);
  }catch(error){el('error').textContent=error.message||'The local app did not respond.';el('error').hidden=false;}
  finally{el('ask-button').disabled=false;el('ask-button').textContent='Ask the assistant ↗';el('answer-panel').setAttribute('aria-busy','false');updateStatus();}
});
document.querySelectorAll('[data-question]').forEach(button=>button.addEventListener('click',()=>{el('question').value=button.dataset.question;el('question').focus();}));
updateStatus();
