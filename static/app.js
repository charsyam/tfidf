const $ = id => document.getElementById(id);
const examples = {ko:['우주 영화는 재미있다.','나는 영화와 음악을 좋아한다.','우주 탐사는 새로운 발견을 만든다.'],en:['Cats are running in the garden.','Dogs are running in the park.','The garden has beautiful flowers.']};
let mode = 'ko', result = null, activeDoc = 0, selectedWord = null, revision = 0, timer;
let defaultStops = {ko:[],en:[]};
const stopDrafts = {ko:null,en:null};
const drafts = {ko:[...examples.ko],en:[...examples.en]};
const stopStorageKey = 'tfidf.stopwords.v1';
function loadStopwords(){
 try{
  const stored=JSON.parse(localStorage.getItem(stopStorageKey));
  if(!stored || stored.version!==1)return;
  for(const language of ['ko','en']){
   if(typeof stored.lists?.[language]==='string')stopDrafts[language]=stored.lists[language];
  }
  if(typeof stored.enabled==='boolean')$('stop').checked=stored.enabled;
 }catch(error){
  $('stop-save-status').textContent='저장된 목록을 불러오지 못했습니다. 기본 목록으로 시작합니다.';
 }
}
function persistStopwords(){
 stopDrafts[mode]=$('stopwords').value;
 try{
  localStorage.setItem(stopStorageKey,JSON.stringify({version:1,lists:stopDrafts,enabled:$('stop').checked}));
  $('stop-save-status').textContent='이 브라우저에 자동 저장되었습니다.';
 }catch(error){
  $('stop-save-status').textContent='브라우저에 저장할 수 없습니다. 현재 화면에서는 목록을 사용할 수 있습니다.';
 }
}

const esc = s => String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = n => n.toFixed(4);
function saveDraft(){ queryDrafts[mode]=$('query').value; stopDrafts[mode] = $('stopwords').value; drafts[mode] = [...document.querySelectorAll('.document-input')].map(el=>el.value); }
function renderInputs(){
  $('inputs').innerHTML=drafts[mode].map((text,i)=>`<div class="input-heading"><label for="doc-${i}">문장 ${i+1}</label><button class="remove" data-remove="${i}" aria-label="문장 ${i+1} 삭제" ${drafts[mode].length===1?'disabled':''}>삭제</button></div><textarea class="document-input" id="doc-${i}" rows="2" maxlength="500">${esc(text)}</textarea>`).join('');
  $('add').disabled=drafts[mode].length>=10;
}
function schedule(){revision++;clearTimeout(timer);$('status').textContent='입력이 바뀌었습니다. 분석 중…';timer=setTimeout(run,500);}
function modeUI(){
 document.querySelectorAll('[data-mode]').forEach(b=>{const on=b.dataset.mode===mode;b.classList.toggle('active',on);b.setAttribute('aria-pressed',on);});
 $('dictionary-section').hidden=mode!=='ko';$('stem-option').hidden=mode==='ko';
 $('filter-label').textContent=mode==='ko'?'품사 필터 · 내용어 중심':'문장부호 제거';
 $('mode-note').textContent=mode==='ko'?'Kiwi 기본 사전으로 형태소와 품사를 분석합니다.':'단어·문장부호를 분리하고 Porter 어간 추출을 적용합니다.';
 $('query').value=queryDrafts[mode];
 $('stopwords').value=stopDrafts[mode] ?? defaultStops[mode].join('\n');
}
async function run(){
 clearTimeout(timer);saveDraft();const current=++revision;
 const documents=drafts[mode].map(t=>t.trim()).filter(Boolean);
 if(!documents.length){result=null;render();$('status').textContent='문장을 하나 이상 입력해 주세요.';return;}
 $('status').textContent='분석 중… 첫 한국어 분석은 사전 로딩으로 시간이 걸릴 수 있습니다.';
 const payload={mode,documents,query:$('query').value,parameters:Object.fromEntries(['k1','b','delta_l','delta_plus'].map(id=>[id,Number($(id).value)])),stopwords:$('stopwords').value.split('\n').map(w=>w.trim()).filter(Boolean),dictionary:mode==='ko'?$('dictionary').value.split('\n').map(w=>w.trim()).filter(Boolean):[],options:Object.fromEntries(['lower','stemming','filter','stop'].map(k=>[k,$(k).checked]))};
 try{
  const response=await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const data=await response.json();if(current!==revision)return;
  if(!response.ok)throw new Error(data.error||'분석에 실패했습니다.');
  previousRetrieval=result?.retrieval ?? null;result=data;activeDoc=Math.min(activeDoc,data.n-1);if(!data.terms.some(t=>t.word===selectedWord))selectedWord=data.terms[0]?.word;
  render();$('status').textContent=`${data.n}개 문장 · ${data.terms.length}개 단어 분석 완료`;
 }catch(error){if(current===revision){result=null;render();$('status').textContent=error.message;}}
}
function render(){
 renderRanking();
 if(!result){$('doc-tabs').innerHTML='';['pipeline','matrix','bars'].forEach(id=>$(id).innerHTML='<p class="empty">문장을 입력하면 분석 결과가 표시됩니다.</p>');$('calculation').innerHTML='';return;}
 $('doc-tabs').innerHTML=result.documents.map((d,i)=>`<button data-doc="${i}" class="${i===activeDoc?'active':''}" aria-pressed="${i===activeDoc}">문장 ${i+1}</button>`).join('');
 const doc=result.documents[activeDoc];
 $('pipeline').innerHTML=`<p class="original">${esc(doc.text)}</p><div class="scroll"><table><thead><tr><th>Tokenize${mode==='ko'?' · 형태소 분석':''}</th><th>Lowercase${$('lower').checked?'':' · 꺼짐'}</th><th>불용어 제거${$('stop').checked?'':' · 꺼짐'}</th><th>${mode==='ko'?'형태소 유지':'Stemming'+($('stemming').checked?'':' · 꺼짐')}</th><th>계산 포함 여부</th></tr></thead><tbody>${doc.tokens.map(t=>`<tr><td title="원문: ${esc(t.surface)}">${esc(t.form)}<span class="token-tag">${esc(t.tag)}</span></td><td class="${t.lower!==t.form?'changed':''}">${esc(t.lower)}</td><td><span class="${t.stopword?'removed':''}">${esc(t.lower)}</span>${t.stopword?'<div class="reason">불용어 목록에 포함</div>':''}</td><td class="${t.root!==t.lower?'changed':''}">${t.stopword?'—':esc(t.root)}</td><td><span class="${t.included?'':'removed'}">${esc(t.root)}</span>${t.reason?`<div class="reason">${esc(t.reason)}</div>`:''}</td></tr>`).join('')}</tbody></table></div><p class="hint">불용어 ${doc.tokens.filter(t=>t.stopword).length}개 제거 · 포함 토큰 ${doc.total}개 · ${mode==='ko'?'NN: 명사 / VV: 동사 / VA: 형용사 / MAG: 일반부사 / SL: 외국어 / SN: 숫자 / XR: 어근. 한국어는 형태소 분석에서 어간이 분리되므로 영어 stemming을 적용하지 않습니다.':'Stemming 결과는 사전에 있는 단어와 다를 수 있습니다.'}</p>`;
 if(!result.terms.length){$('matrix').innerHTML='<p class="empty">포함된 토큰이 없습니다. 필터를 끄거나 문장을 바꿔 보세요.</p>';$('bars').innerHTML='';$('calculation').innerHTML='';return;}
 const max=Math.max(...result.terms.flatMap(t=>t.cells.map(c=>c.score)),0);
 $('matrix').innerHTML=`<table><thead><tr><th>단어</th><th>DF</th><th>IDF</th>${result.documents.map((_,i)=>`<th>문장 ${i+1}</th>`).join('')}</tr></thead><tbody>${result.terms.map((t,i)=>`<tr><td>${esc(t.word)}</td><td>${t.df}/${result.n}</td><td>${fmt(t.idf)}</td>${t.cells.map((c,j)=>`<td><button class="cell ${selectedWord===t.word&&activeDoc===j?'selected':''}" data-term="${i}" data-cell-doc="${j}" style="background:rgba(114,170,93,${max?c.score/max*.35:0})" aria-label="${esc(t.word)}, 문장 ${j+1}, 점수 ${fmt(c.score)} 계산 보기">${fmt(c.score)}</button></td>`).join('')}</tr>`).join('')}</tbody></table>`;
 const term=result.terms.find(t=>t.word===selectedWord)||result.terms[0],cell=term.cells[activeDoc];
 $('calculation').innerHTML=`<div class="calc"><strong>${esc(term.word)} · 문장 ${activeDoc+1}</strong><br>TF = 단어 출현 횟수 = ${cell.count}<br>IDF = ln(${result.n} / ${term.df}) = ${fmt(term.idf)}<br>TF-IDF = ${fmt(cell.tf)} × ${fmt(term.idf)} = <strong>${fmt(cell.score)}</strong>${term.df===result.n?'<br>모든 문장에 등장하는 단어라서 IDF와 최종 점수가 0입니다.':''}</div>`;
 const ranking=[...result.terms].filter(t=>t.cells[activeDoc].count).sort((a,b)=>b.cells[activeDoc].score-a.cells[activeDoc].score);const localMax=Math.max(...ranking.map(t=>t.cells[activeDoc].score),0);
 $('bars').innerHTML=ranking.map(t=>`<div class="bar-row"><span>${esc(t.word)}</span><div class="track"><div class="fill" style="width:${localMax?t.cells[activeDoc].score/localMax*100:0}%"></div></div><span>${fmt(t.cells[activeDoc].score)}</span></div>`).join('')||'<p class="empty">이 문장에는 포함된 토큰이 없습니다.</p>';
}
document.addEventListener('click',e=>{
 const b=e.target.closest('button');if(!b)return;
 if(b.dataset.mode){saveDraft();mode=b.dataset.mode;activeDoc=0;result=null;modeUI();renderInputs();render();run();}
 if(b.dataset.remove!==undefined){saveDraft();drafts[mode].splice(Number(b.dataset.remove),1);renderInputs();schedule();}
 if(b.dataset.doc!==undefined){activeDoc=Number(b.dataset.doc);render();}
 if(b.dataset.term!==undefined){selectedWord=result.terms[Number(b.dataset.term)].word;activeDoc=Number(b.dataset.cellDoc);render();}
});
$('add').onclick=()=>{saveDraft();drafts[mode].push('');renderInputs();$('inputs').lastElementChild.focus();schedule();};
$('run').onclick=run;
$('stopwords').addEventListener('input',()=>{persistStopwords();schedule();});
$('reset-stopwords').onclick=()=>{$('stopwords').value=defaultStops[mode].join('\n');persistStopwords();schedule();};
$('inputs').addEventListener('input',schedule);$('dictionary').addEventListener('input',schedule);
['lower','stemming','filter'].forEach(id=>$(id).addEventListener('change',schedule));
$('stop').addEventListener('change',()=>{persistStopwords();schedule();});
async function initialize(){
 loadStopwords();
 try{
  const response=await fetch('/api/stopwords');
  if(!response.ok)throw new Error('기본 불용어 목록을 불러오지 못했습니다.');
  defaultStops=await response.json();modeUI();renderInputs();render();run();
 }catch(error){$('status').textContent=error.message;}
}
setupRanking();
initialize();
