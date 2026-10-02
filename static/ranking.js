const rankingModels = {tfidf:'TF-IDF',bm25:'BM25',bm25l:'BM25L',bm25plus:'BM25+'};
let previousRetrieval = null;
const queryDrafts = {ko:'우주 영화',en:'garden running'};
function renderRanking(){
 const ids=['query-tokens','ranking-summary','ranking-table','ranking-bars','ranking-detail'];
 if(!result){ids.forEach(id=>$(id).innerHTML='');return;}
 const retrieval=result.retrieval;
 $('query-tokens').innerHTML='<span class="hint">검색어 전처리: </span>'+retrieval.query.tokens.map(t=>`<span class="query-chip ${t.included?'':'removed'}" title="${esc(t.form)} → ${esc(t.lower)} → ${esc(t.root)}${t.reason?' · '+esc(t.reason):''}">${esc(t.root)}${!t.included?' (제외)':''}</span>`).join('');
 $('ranking-summary').textContent=`문서 ${result.n}개 · 평균 길이 ${fmt(retrieval.avgdl)} · k₁=${retrieval.parameters.k1} · b=${retrieval.parameters.b} · δL=${retrieval.parameters.delta_l} · δ+=${retrieval.parameters.delta_plus}`;
 if(!retrieval.words.length){
  $('ranking-table').innerHTML='<p class="empty">검색어를 입력해 주세요. 전처리 후 검색 토큰이 남아 있어야 점수를 비교할 수 있습니다.</p>';
  $('ranking-bars').innerHTML='';$('ranking-detail').innerHTML='';return;
 }
 const keys=Object.keys(rankingModels);
 const delta=(row,key)=>{
  const before=previousRetrieval?.rows[row.index];
  if(!before)return '';
  const difference=row.scores[key]-before.scores[key];
  const rankDifference=before.ranks[key]-row.ranks[key];
  return `<small class="change">점수 ${difference>=0?'+':''}${fmt(difference)} · 순위 ${rankDifference>0?'↑'+rankDifference:rankDifference<0?'↓'+Math.abs(rankDifference):'유지'}</small>`;
 };
 $('ranking-table').innerHTML=`<table><thead><tr><th>문장 · 길이</th>${keys.map(k=>`<th>${rankingModels[k]}</th>`).join('')}</tr></thead><tbody>${retrieval.rows.map(row=>`<tr><td><button data-doc="${row.index}" aria-label="문장 ${row.index+1} 계산 상세 보기">문장 ${row.index+1} · ${row.length} 토큰</button></td>${keys.map(k=>`<td><strong>${row.ranks[k]}위</strong> · ${fmt(row.scores[k])}${delta(row,k)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
 $('ranking-bars').innerHTML=`<div class="model-charts">${keys.map(k=>{
  const max=Math.max(...retrieval.rows.map(row=>row.scores[k]),0);
  const rows=[...retrieval.rows].sort((a,b)=>b.scores[k]-a.scores[k]);
  return `<div class="model-chart"><h3>${rankingModels[k]}</h3>${rows.map(row=>`<div class="bar-row"><span>${row.ranks[k]}위 · 문장 ${row.index+1}</span><div class="track"><div class="fill" style="width:${max?row.scores[k]/max*100:0}%"></div></div><span>${fmt(row.scores[k])}</span></div>`).join('')}</div>`;
 }).join('')}</div>`;
 const row=retrieval.rows[activeDoc];
 const absent=row.contributions.filter(t=>!t.df).map(t=>t.word);
 $('ranking-detail').innerHTML=`<p class="ranking-note">문장 ${activeDoc+1}: L=${row.length}, avgL=${fmt(retrieval.avgdl)}, A=1−${retrieval.parameters.b}+${retrieval.parameters.b}×${row.length}/${fmt(retrieval.avgdl)}=${fmt(row.norm)}${retrieval.avgdl===0?' (전체 토큰이 없어 A=1로 처리)':''}<br>각 셀: IDF × 빈도 가중치 = 단어 기여도${absent.length?'<br>문서에 없는 검색 토큰: '+absent.map(esc).join(', ')+' · 기여도 0':''}</p><table><thead><tr><th>검색 단어</th><th>f / DF / c</th>${keys.map(k=>`<th>${rankingModels[k]}</th>`).join('')}</tr></thead><tbody>${row.contributions.map(t=>`<tr><td>${esc(t.word)}</td><td>${t.frequency} / ${t.df} / ${fmt(t.c)}</td>${keys.map(k=>`<td>${fmt(t.idfs[k])} × ${fmt(t.weights[k])}<br><strong>= ${fmt(t.scores[k])}</strong></td>`).join('')}</tr>`).join('')}</tbody></table>`;
}
function setupRanking(){
 $('query').addEventListener('input',schedule);
 for(const id of ['k1','b','delta_l','delta_plus']){
  $(id).addEventListener('input',()=>{$(id+'-value').textContent=Number($(id).value).toFixed(2);schedule();});
 }
 $('ranking-example').onclick=()=>{
  saveDraft();
  drafts[mode]=mode==='ko'?['우주 영화','우주 우주 우주 영화 음악 탐사 발견 행성 여행 이야기','음악 공연 영화']:['space movie','space space space movie music exploration discovery planet travel story','music concert movie'];
  queryDrafts[mode]=mode==='ko'?'우주 영화':'space movie';
  $('query').value=queryDrafts[mode];activeDoc=0;renderInputs();run();
 };
}
