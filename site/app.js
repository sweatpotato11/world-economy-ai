// 세계경제 AI — data/today.json 을 읽어서 화면에 그려요.
// AI가 만든 글은 그대로 HTML로 넣지 않고 esc()로 안전하게 바꿔서 넣어요.

const ARROW = { 긍정: '▲ 긍정', 부정: '▼ 부정', 중립: '— 중립' };
const DIR = { up: ['▲ 오를 가능성', 'up'], down: ['▼ 내릴 가능성', 'down'], flat: ['— 방향 불확실', 'flat'] };

function esc(text) {
  return String(text ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function safeUrl(url) {
  return /^https?:\/\//i.test(url || '') ? esc(url) : '#';
}
function fmtTime(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return '';
  return d.toLocaleString('ko-KR', { timeZone: 'Asia/Seoul', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}
// 주소에 ?date=2026-11-22 가 있으면 그날 기록을, 없으면 오늘 것을 보여줘요.
const DATE = (() => {
  const d = new URLSearchParams(location.search).get('date');
  return /^\d{4}-\d{2}-\d{2}$/.test(d || '') ? d : null;
})();
function withDate(url) {
  return DATE ? url + (url.includes('?') ? '&' : '?') + 'date=' + DATE : url;
}
async function loadData() {
  const file = DATE ? `data/archive/${DATE}.json` : 'data/today.json';
  const res = await fetch(file, { cache: 'no-store' });
  if (!res.ok) throw new Error(DATE ? `${DATE} 기록이 없어요` : '데이터 파일을 못 찾았어요');
  return res.json();
}
function fmtDate(d) {
  const [y, m, day] = d.split('-').map(Number);
  const w = '일월화수목금토'[new Date(y, m - 1, day).getDay()];
  return `${y}년 ${m}월 ${day}일 (${w})`;
}
async function setupDateNav(data) {
  const nav = document.querySelector('[data-datenav]');
  if (!nav) return;
  let dates = [];
  try {
    const res = await fetch('data/archive/index.json', { cache: 'no-store' });
    if (res.ok) dates = (await res.json()).dates || [];
  } catch (e) { /* 기록 목록이 아직 없으면 날짜 고르기를 숨겨요 */ }
  if (data.date && !dates.includes(data.date)) dates.unshift(data.date);
  dates = dates.filter((d) => /^\d{4}-\d{2}-\d{2}$/.test(d)).sort().reverse();
  if (dates.length < 2) return;

  const latest = dates[0];
  const cur = DATE || data.date || latest;
  const idx = dates.indexOf(cur);
  const page = location.pathname.endsWith('issue.html') ? 'index.html' : location.pathname.split('/').pop() || 'index.html';
  const go = (d) => { location.href = d === latest ? page : `${page}?date=${d}`; };
  const older = dates[idx + 1];
  const newer = idx > 0 ? dates[idx - 1] : null;

  nav.innerHTML = `
    <button type="button" class="dn-btn" data-go="${older || ''}" ${older ? '' : 'disabled'} aria-label="이전 날짜">◀</button>
    <label for="dn-select" class="sr">날짜 고르기</label>
    <select id="dn-select" class="dn-select">
      ${dates.map((d) => `<option value="${d}" ${d === cur ? 'selected' : ''}>${fmtDate(d)}${d === latest ? ' · 최신' : ''}</option>`).join('')}
    </select>
    <button type="button" class="dn-btn" data-go="${newer || ''}" ${newer ? '' : 'disabled'} aria-label="다음 날짜">▶</button>`;
  nav.hidden = false;
  nav.addEventListener('click', (e) => {
    const b = e.target.closest('button[data-go]');
    if (b && b.dataset.go) go(b.dataset.go);
  });
  nav.querySelector('select').addEventListener('change', (e) => go(e.target.value));

  if (DATE && DATE !== latest) {
    const past = document.querySelector('[data-past]');
    if (past) {
      past.querySelector('span').textContent = `${fmtDate(DATE)} 기록을 보고 있어요.`;
      past.querySelector('a').href = page === 'index.html' ? 'index.html' : page;
      past.hidden = false;
    }
  }
}
function showError(el, err) {
  el.innerHTML = `<div class="box empty">데이터를 불러오지 못했어요. (${esc(err.message)})<br>
  컴퓨터에서 볼 때는 README의 '내 컴퓨터에서 미리 보기' 방법으로 열어 주세요.</div>`;
}
function setCommon(data) {
  setupDateNav(data);
  document.querySelectorAll('a[data-keep-date]').forEach((a) => { a.href = withDate(a.getAttribute('href')); });
  document.querySelectorAll('[data-updated]').forEach((el) => { el.textContent = `마지막 업데이트 ${fmtTime(data.generated_at)}`; });
  if (data.sample) document.querySelectorAll('[data-sample]').forEach((el) => { el.hidden = false; });
}
function dots(n) {
  let s = `<span class="dots" role="img" aria-label="중요도 5점 중 ${n}점">`;
  for (let i = 1; i <= 5; i++) s += `<i class="${i <= n ? 'on' : ''}"></i>`;
  return s + '</span>';
}

/* ───────── 홈 화면 ───────── */
async function initHome() {
  const root = document.getElementById('app');
  let data;
  try { data = await loadData(); } catch (e) { return showError(root, e); }
  setCommon(data);

  // 지표
  document.getElementById('tickers').innerHTML = data.indicators.map((t) => `
    <div class="ticker">
      <span class="name">${esc(t.name)}</span>
      <span class="value mono">${esc(t.value)}</span>
      <div class="row">
        <span class="mono ${esc(t.direction)}">${esc(t.change)}</span>
        <svg width="74" height="24" viewBox="0 0 74 24" fill="none" aria-hidden="true">
          <polyline points="${esc(t.points)}" stroke="#6B7684" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"></polyline>
        </svg>
      </div>
    </div>`).join('');

  // 브리핑
  const b = data.briefing || {};
  document.getElementById('brief-count').textContent = `${DATE ? "이날" : "오늘"} 수집한 기사 ${data.article_count}개를 읽고 정리했어요`;
  document.getElementById('brief-h').textContent = b.summary || '';
  document.getElementById('brief-top').textContent = b.top_issue || '—';
  document.getElementById('brief-region').textContent = b.focus_region || '—';
  document.getElementById('brief-mood').textContent = ARROW[b.mood] || '—';

  // 지역 필터
  const regionNames = ['전체', ...new Set(data.issues.map((i) => i.region))];
  let selected = '전체';
  let query = '';
  const chips = document.getElementById('chips');
  chips.innerHTML = regionNames.map((r) => `<button type="button" class="chip-btn" data-region="${esc(r)}" aria-pressed="${r === '전체'}">${esc(r)}</button>`).join('');

  function renderIssues() {
    chips.querySelectorAll('button').forEach((btn) => btn.setAttribute('aria-pressed', String(btn.dataset.region === selected)));
    const q = query.trim().toLowerCase();
    const list = data.issues.filter((i) =>
      (selected === '전체' || i.region === selected) &&
      (!q || [i.title, i.what, i.why, i.effect, i.region, i.sector].join(' ').toLowerCase().includes(q)));
    const box = document.getElementById('issues');
    const moreWrap = document.getElementById('more-wrap');
    const rest = list.slice(5);
    moreWrap.hidden = !rest.length;
    document.getElementById('more-count').textContent = rest.length ? `${rest.length}개` : '';
    document.getElementById('more').innerHTML = rest.map((i, n) => `
      <li><a href="${withDate('issue.html?id=' + encodeURIComponent(i.id))}">
        <span class="mono rank-s">${n + 6}</span>
        <span class="t">${esc(i.title)}<small>${esc(i.what)}</small></span>
        <span class="meta-s"><span class="tag">${esc(i.region)}</span><span class="impact ${esc(i.impact)}">${esc(ARROW[i.impact] || i.impact)}</span></span>
      </a></li>`).join('');
    if (!list.length) { box.innerHTML = '<div class="box empty">조건에 맞는 이슈가 없어요.</div>'; return; }
    box.innerHTML = list.slice(0, 5).map((i, n) => `
      <article class="issue">
        <div class="rank mono">${n + 1}</div>
        <div class="body">
          <div class="meta">
            <span class="tag">${esc(i.region)}</span><span class="tag">${esc(i.sector)}</span>
            <span class="impact ${esc(i.impact)}">${esc(ARROW[i.impact] || i.impact)}</span>
            <span style="flex:1"></span>
            <span class="small">중요도 ${dots(i.importance)}</span>
          </div>
          <h3>${esc(i.title)}</h3>
          <ul>
            <li><strong>무슨 일</strong>${esc(i.what)}</li>
            <li><strong>왜 중요</strong>${esc(i.why)}</li>
            <li><strong>영향</strong>${esc(i.effect)}</li>
          </ul>
          <div class="foot">
            <span>관련 기사 ${i.articles.length}개${i.articles[0] ? ' · ' + esc(i.articles[0].source) : ''}</span>
            <a href="${withDate('issue.html?id=' + encodeURIComponent(i.id))}">자세히 보기 →</a>
          </div>
        </div>
      </article>`).join('');
  }
  chips.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-region]');
    if (btn) { selected = btn.dataset.region; renderIssues(); }
  });
  document.getElementById('q').addEventListener('input', (e) => { query = e.target.value; renderIssues(); });
  renderIssues();

  // 지역별 분위기
  const regionGrid = document.getElementById('regions');
  regionGrid.innerHTML = data.regions.map((r) => `
    <button type="button" class="region-btn" data-region="${esc(r.name)}">
      <b>${esc(r.name)}</b><small class="${r.mood === '긍정' ? 'up' : r.mood === '부정' ? 'down' : 'flat'}">${esc(ARROW[r.mood] || r.mood)}</small>
    </button>`).join('');
  regionGrid.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-region]');
    if (!btn) return;
    selected = regionNames.includes(btn.dataset.region) ? btn.dataset.region : '전체';
    renderIssues();
    document.getElementById('top-h').scrollIntoView({ behavior: 'smooth' });
  });

  // 오늘 읽은 모든 기사 (30개씩 더 보기)
  const all = data.all_articles || [];
  let shown = 30;
  const allBtn = document.getElementById('all-more');
  document.getElementById('all-count').textContent = `${all.length}개`;
  function renderAll() {
    document.getElementById('all').innerHTML = all.slice(0, shown).map((a) => `
      <li><a href="${safeUrl(a.link)}" target="_blank" rel="noopener noreferrer">
        <span>${esc(a.title)}</span><span>${esc(a.source)} · ${esc(fmtTime(a.published))} ↗</span></a></li>`).join('')
      || '<li class="small" style="padding:10px 0">기사 목록이 없어요.</li>';
    allBtn.hidden = shown >= all.length;
  }
  allBtn.addEventListener('click', () => { shown += 30; renderAll(); });
  renderAll();

  // 분야별 분위기
  document.getElementById('sectors').innerHTML = data.sectors.map((s) => {
    const p = Math.max(0, Math.min(100, Number(s.positive_percent) || 0));
    return `<div class="sector">
      <div class="label"><span>${esc(s.name)}</span><span class="small">긍정 ${p}%</span></div>
      <div class="bar" aria-hidden="true"><span class="p" style="width:${p}%"></span><span class="n" style="width:${100 - p}%"></span></div>
    </div>`;
  }).join('');
}

/* ───────── 이슈 상세 화면 ───────── */
async function initIssue() {
  const root = document.getElementById('app');
  let data;
  try { data = await loadData(); } catch (e) { return showError(root, e); }
  setCommon(data);

  const id = new URLSearchParams(location.search).get('id');
  const issue = data.issues.find((i) => i.id === id) || data.issues[0];
  if (!issue) { root.innerHTML = '<div class="box empty">이슈를 찾지 못했어요.</div>'; return; }
  document.title = `${issue.title} — 세계경제 AI`;

  document.getElementById('tags').innerHTML = `
    <span class="tag">${esc(issue.region)}</span><span class="tag">${esc(issue.sector)}</span>
    <span class="impact ${esc(issue.impact)}">${esc(ARROW[issue.impact] || issue.impact)}</span>
    <span class="small">중요도 ${dots(issue.importance)}</span>`;
  document.getElementById('title').textContent = issue.title;
  document.getElementById('meta').textContent = `관련 기사 ${issue.articles.length}개 · 마지막 업데이트 ${fmtTime(data.generated_at)}`;
  document.getElementById('why').textContent = issue.why_important;

  let easy = true;
  const toggle = document.getElementById('toggle');
  function renderSummary() {
    toggle.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String((b.dataset.mode === 'easy') === easy)));
    const lines = easy ? issue.easy_summary : issue.pro_summary;
    document.getElementById('lines').innerHTML = (lines || []).map((l) => `<li>${esc(l)}</li>`).join('');
  }
  toggle.addEventListener('click', (e) => {
    const b = e.target.closest('button[data-mode]');
    if (b) { easy = b.dataset.mode === 'easy'; renderSummary(); }
  });
  renderSummary();

  document.getElementById('effects').innerHTML = (issue.market_effects || []).map((m) => {
    const [label, cls] = DIR[m.direction] || DIR.flat;
    return `<div class="box effect"><span class="small">${esc(m.name)}</span><span class="dir ${cls}">${label}</span><span style="font-size:13px;color:var(--text-2)">${esc(m.reason)}</span></div>`;
  }).join('');

  document.getElementById('timeline').innerHTML = issue.articles.map((a) => `
    <li><div class="rail"><i></i><span></span></div>
      <div class="item">
        <span class="mono small">${esc(fmtTime(a.published))}</span>
        <b>${esc(a.title)}</b>
        <span class="small">${esc(a.source)} · <a href="${safeUrl(a.link)}" target="_blank" rel="noopener noreferrer">원문 보기 ↗</a></span>
      </div></li>`).join('') || '<li class="small">연결된 기사가 없어요.</li>';

  document.getElementById('sources').innerHTML = issue.articles.map((a) => `
    <li><a href="${safeUrl(a.link)}" target="_blank" rel="noopener noreferrer"><span>${esc(a.title)}</span><span>${esc(a.source)} ↗</span></a></li>`).join('');

  document.getElementById('related').innerHTML = data.issues.filter((i) => i.id !== issue.id).slice(0, 3)
    .map((i) => `<a href="${withDate('issue.html?id=' + encodeURIComponent(i.id))}" style="display:block;padding:10px 0;text-decoration:none;color:var(--text)">${esc(i.title)} →</a>`).join('');
}
