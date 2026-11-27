// 세계경제 AI — data 폴더의 JSON 을 읽어서 화면에 그려요.
// AI가 만든 글은 그대로 HTML로 넣지 않고 esc()로 안전하게 바꿔서 넣어요.

const ARROW = { 긍정: '▲ 긍정', 부정: '▼ 부정', 중립: '— 중립' };
const MOOD_CLASS = { 긍정: 'up', 부정: 'down', 중립: 'flat' };
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
function fmtDate(d) {
  const [y, m, day] = d.split('-').map(Number);
  const w = '일월화수목금토'[new Date(y, m - 1, day).getDay()];
  return `${y}년 ${m}월 ${day}일 (${w})`;
}
function shortDate(d) {
  const [, m, day] = d.split('-').map(Number);
  return `${m}/${day}`;
}
async function getJSON(path) {
  const res = await fetch(path, { cache: 'no-store' });
  if (!res.ok) throw new Error(`${path} 를 찾지 못했어요`);
  return res.json();
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
  try {
    return await getJSON(DATE ? `data/archive/${DATE}.json` : 'data/today.json');
  } catch (e) {
    throw new Error(DATE ? `${DATE} 기록이 없어요` : '데이터 파일을 못 찾았어요');
  }
}

/* ───────── 공통 머리글 (모든 화면 같은 메뉴) ───────── */
const LOGO = `<svg width="32" height="32" viewBox="0 0 32 32" fill="none" aria-hidden="true"><circle cx="16" cy="16" r="13" stroke="#F5A524" stroke-width="2"/><path d="M3 16h26M16 3c4 4 5 8.5 5 13s-1 9-5 13M16 3c-4 4-5 8.5-5 13s1 9 5 13" stroke="#F5A524" stroke-width="1.6"/></svg>`;
const MENU = [
  ['home', 'index.html', '오늘', true],
  ['korea', 'korea.html', '한국', true],
  ['weekly', 'weekly.html', '주간 정리', false],
  ['glossary', 'glossary.html', '용어 사전', false],
];
function renderHeader() {
  const header = document.querySelector('header[data-page]');
  if (!header) return;
  const page = header.dataset.page;
  header.className = 'top';
  header.innerHTML = `
    <div class="wrap">
      <a href="index.html" class="logo">${LOGO}<span>세계경제 AI</span></a>
      <nav class="menu" aria-label="주요 메뉴">
        ${MENU.map(([id, href, label, keep]) => `<a href="${keep ? withDate(href) : href}" ${id === page ? 'aria-current="page"' : ''}>${label}</a>`).join('')}
      </nav>
      <div class="spacer"></div>
      <div class="datenav" data-datenav hidden></div>
      <span class="updated" data-updated></span>
      <button type="button" class="install-btn" data-install hidden>📲 앱 설치</button>
    </div>`;
  if (!['home', 'korea', 'issue'].includes(page)) header.querySelector('[data-datenav]').remove();
}

async function setupDateNav(data) {
  const nav = document.querySelector('[data-datenav]');
  if (!nav) return;
  let dates = [];
  try { dates = (await getJSON('data/archive/index.json')).dates || []; } catch (e) { /* 기록 목록이 아직 없어요 */ }
  if (data.date && !dates.includes(data.date)) dates.unshift(data.date);
  dates = dates.filter((d) => /^\d{4}-\d{2}-\d{2}$/.test(d)).sort().reverse();
  if (dates.length < 2) return;

  const latest = dates[0];
  const cur = DATE || data.date || latest;
  const idx = dates.indexOf(cur);
  const file = location.pathname.split('/').pop() || 'index.html';
  const page = file === 'issue.html' ? 'index.html' : file;
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
      past.querySelector('a').href = page;
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
  document.querySelectorAll('[data-updated]').forEach((el) => { el.textContent = `업데이트 ${fmtTime(data.generated_at)}`; });
  if (data.sample) document.querySelectorAll('[data-sample]').forEach((el) => { el.hidden = false; });
}
function dots(n) {
  let s = `<span class="dots" role="img" aria-label="중요도 5점 중 ${n}점">`;
  for (let i = 1; i <= 5; i++) s += `<i class="${i <= n ? 'on' : ''}"></i>`;
  return s + '</span>';
}
function impactTag(v) {
  return `<span class="impact ${esc(v)}">${esc(ARROW[v] || v)}</span>`;
}
function articleList(list) {
  return (list || []).map((a) => `
    <li><a href="${safeUrl(a.link)}" target="_blank" rel="noopener noreferrer">
      <span>${esc(a.title)}</span><span>${esc(a.source)}${a.published ? ' · ' + esc(fmtTime(a.published)) : ''} ↗</span></a></li>`).join('');
}

/* ───────── 📖 용어 밑줄 + 설명 카드 ───────── */
let TERMS = {};      // 용어 → 설명
let TERM_RE = null;  // 글에서 용어를 찾는 정규식

async function loadTerms(today) {
  TERMS = {};
  try {
    const book = await getJSON('data/glossary.json');
    Object.values(book.terms || {}).forEach((t) => { TERMS[t.term] = t; });
  } catch (e) { /* 사전이 아직 없어요 */ }
  (today || []).forEach((t) => { TERMS[t.term] = { ...TERMS[t.term], ...t }; });
  const keys = Object.keys(TERMS).filter((k) => k.length >= 2).sort((a, b) => b.length - a.length);
  TERM_RE = keys.length ? new RegExp(keys.map((k) => esc(k).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'), 'g') : null;
}
// esc() 한 글에서 용어에 밑줄 버튼을 달아요. 같은 글에서 같은 용어는 처음 한 번만.
function withTerms(text) {
  const safe = esc(text);
  if (!TERM_RE) return safe;
  const used = new Set();
  return safe.replace(TERM_RE, (m) => {
    if (used.has(m)) return m;
    used.add(m);
    return `<button type="button" class="term" data-term="${m}">${m}</button>`;
  });
}
function setupTermPopup() {
  const pop = document.createElement('div');
  pop.className = 'term-pop';
  pop.setAttribute('role', 'dialog');
  pop.setAttribute('aria-live', 'polite');
  pop.hidden = true;
  document.body.appendChild(pop);
  const close = () => { pop.hidden = true; };
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('button.term');
    if (btn) {
      const t = TERMS[btn.dataset.term];  // 속성 값은 브라우저가 원래 글자로 돌려줘요
      if (!t) return;
      pop.innerHTML = `
        <div class="tp-head"><b>${esc(t.term)}</b>${t.english ? `<span class="small">${esc(t.english)}</span>` : ''}
          <button type="button" class="tp-close" aria-label="닫기">✕</button></div>
        <p>${esc(t.easy)}</p>
        ${t.example ? `<p class="small">예: ${esc(t.example)}</p>` : ''}
        <a href="glossary.html#${encodeURIComponent(t.term)}" class="small">용어 사전에서 보기 →</a>`;
      pop.hidden = false;
      pop.querySelector('.tp-close').focus();
      return;
    }
    if (e.target.closest('.tp-close') || !e.target.closest('.term-pop')) close();
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(); });
}

/* ───────── 📈 지표 큰 그래프 ───────── */
let HISTORY = null;
async function openChart(name) {
  const modal = document.getElementById('chart-modal');
  if (!HISTORY) {
    try { HISTORY = await getJSON('data/indicators.json'); } catch (e) { HISTORY = {}; }
  }
  const h = HISTORY[name];
  modal.querySelector('h2').textContent = name;
  const body = modal.querySelector('.chart-body');
  if (!h || !h.closes || h.closes.length < 2) {
    body.innerHTML = '<p class="empty">아직 그래프 데이터가 없어요. 다음 자동 업데이트 후에 볼 수 있어요.</p>';
    modal.showModal();
    return;
  }
  const ranges = [['1개월', 22], ['3개월', 66], ['6개월', 130], ['1년', 9999]];
  let range = 66;
  function draw() {
    const n = Math.min(range, h.closes.length);
    const closes = h.closes.slice(-n);
    const dates = h.dates.slice(-n);
    const W = 640, H = 260, P = { l: 8, r: 8, t: 16, b: 24 };
    const lo = Math.min(...closes), hi = Math.max(...closes), span = hi - lo || 1;
    const x = (i) => P.l + (i / (closes.length - 1)) * (W - P.l - P.r);
    const y = (v) => P.t + (1 - (v - lo) / span) * (H - P.t - P.b);
    const pts = closes.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
    const first = closes[0], last = closes[closes.length - 1];
    const pct = h.suffix === '%' ? `${(last - first) >= 0 ? '+' : ''}${(last - first).toFixed(2)}%p` : `${((last - first) / first * 100) >= 0 ? '+' : ''}${((last - first) / first * 100).toFixed(2)}%`;
    const cls = last > first ? 'up' : last < first ? 'down' : 'flat';
    const stroke = cls === 'up' ? 'var(--pos)' : cls === 'down' ? 'var(--neg)' : 'var(--muted)';
    const fmt = (v) => `${v.toLocaleString('ko-KR', { minimumFractionDigits: h.decimals ?? 2, maximumFractionDigits: h.decimals ?? 2 })}${h.suffix || ''}`;
    body.innerHTML = `
      <div class="chart-top">
        <div><span class="mono chart-val">${fmt(last)}</span> <span class="mono ${cls}">${pct}</span>
          <div class="small">${shortDate(dates[0])} ~ ${shortDate(dates[dates.length - 1])} · 최고 ${fmt(hi)} · 최저 ${fmt(lo)}</div></div>
        <div class="chips" role="group" aria-label="기간">${ranges.map(([l, v]) => `<button type="button" class="chip-btn" data-range="${v}" aria-pressed="${v === range}">${l}</button>`).join('')}</div>
      </div>
      <div class="chart-wrap">
        <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(name)} ${shortDate(dates[0])}부터 ${pct}" preserveAspectRatio="none">
          <line x1="${P.l}" x2="${W - P.r}" y1="${y(hi)}" y2="${y(hi)}" class="grid"/>
          <line x1="${P.l}" x2="${W - P.r}" y1="${y(lo)}" y2="${y(lo)}" class="grid"/>
          <polyline points="${P.l},${H - P.b} ${pts} ${W - P.r},${H - P.b}" fill="${stroke}" opacity="0.08" stroke="none"/>
          <polyline points="${pts}" fill="none" stroke="${stroke}" stroke-width="2" vector-effect="non-scaling-stroke"/>
          <line class="cross" x1="0" x2="0" y1="${P.t}" y2="${H - P.b}" hidden/>
        </svg>
        <div class="chart-tip mono" hidden></div>
      </div>`;
    body.querySelectorAll('button[data-range]').forEach((b) => b.addEventListener('click', () => { range = Number(b.dataset.range); draw(); }));
    const wrap = body.querySelector('.chart-wrap');
    const svg = wrap.querySelector('svg');
    const cross = svg.querySelector('.cross');
    const tip = wrap.querySelector('.chart-tip');
    const move = (clientX) => {
      const r = svg.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (clientX - r.left) / r.width));
      const i = Math.round(ratio * (closes.length - 1));
      const cx = x(i);
      cross.setAttribute('x1', cx); cross.setAttribute('x2', cx); cross.hidden = false;
      tip.hidden = false;
      tip.textContent = `${shortDate(dates[i])}  ${fmt(closes[i])}`;
      tip.style.left = `${Math.min(r.width - 120, Math.max(0, (cx / W) * r.width - 60))}px`;
    };
    svg.addEventListener('pointermove', (e) => move(e.clientX));
    svg.addEventListener('pointerleave', () => { cross.hidden = true; tip.hidden = true; });
  }
  draw();
  modal.showModal();
}
function setupChartModal() {
  const modal = document.createElement('dialog');
  modal.id = 'chart-modal';
  modal.className = 'chart-modal';
  modal.innerHTML = `<div class="chart-head"><h2></h2><button type="button" class="tp-close" aria-label="닫기">✕</button></div><div class="chart-body"></div>
    <p class="small" style="margin:12px 0 0">하루 마감 가격 기준 · 출처: 야후 파이낸스</p>`;
  document.body.appendChild(modal);
  modal.addEventListener('click', (e) => { if (e.target === modal || e.target.closest('.tp-close')) modal.close(); });
  document.addEventListener('click', (e) => {
    const t = e.target.closest('[data-chart]');
    if (t) openChart(t.dataset.chart);
  });
}
function tickersHTML(list) {
  return (list || []).map((t) => `
    <button type="button" class="ticker" data-chart="${esc(t.name)}" aria-label="${esc(t.name)} 그래프 크게 보기">
      <span class="name">${esc(t.name)} <span class="zoom" aria-hidden="true">⤢</span></span>
      <span class="value mono">${esc(t.value)}</span>
      <span class="row">
        <span class="mono ${esc(t.direction)}">${esc(t.change)}</span>
        <svg width="74" height="24" viewBox="0 0 74 24" fill="none" aria-hidden="true">
          <polyline points="${esc(t.points)}" stroke="#6B7684" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"></polyline>
        </svg>
      </span>
    </button>`).join('');
}

/* ───────── 📲 휴대폰 앱 설치 ───────── */
function setupPWA() {
  if ('serviceWorker' in navigator && location.protocol === 'https:') {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  }
  let deferred = null;
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferred = e;
    document.querySelectorAll('[data-install]').forEach((b) => { b.hidden = false; });
  });
  document.addEventListener('click', async (e) => {
    if (!e.target.closest('[data-install]') || !deferred) return;
    deferred.prompt();
    await deferred.userChoice;
    deferred = null;
    document.querySelectorAll('[data-install]').forEach((b) => { b.hidden = true; });
  });
}

/* ───────── 모든 화면 공통 시작 ───────── */
function boot() {
  renderHeader();
  setupTermPopup();
  setupChartModal();
  setupPWA();
}

/* ───────── 🌏 홈 화면 ───────── */
async function initHome() {
  boot();
  const root = document.getElementById('app');
  let data;
  try { data = await loadData(); } catch (e) { return showError(root, e); }
  await loadTerms(data.glossary);
  setCommon(data);

  document.getElementById('tickers').innerHTML = tickersHTML(data.indicators);

  const b = data.briefing || {};
  document.getElementById('brief-count').textContent = `${DATE ? '이날' : '오늘'} 수집한 기사 ${data.article_count}개를 읽고 정리했어요`;
  document.getElementById('brief-h').textContent = b.summary || '';
  document.getElementById('brief-top').textContent = b.top_issue || '—';
  document.getElementById('brief-region').textContent = b.focus_region || '—';
  document.getElementById('brief-mood').textContent = ARROW[b.mood] || '—';

  // 한국 한눈에 (한국 분석이 있는 날만)
  const kb = document.getElementById('korea-brief');
  if (data.korea && kb) {
    kb.hidden = false;
    kb.querySelector('[data-k-summary]').innerHTML = withTerms(data.korea.summary);
    kb.querySelector('[data-k-mood]').innerHTML = impactTag(data.korea.mood);
    kb.querySelector('a').href = withDate('korea.html');
  }

  // 오늘의 용어
  const tb = document.getElementById('today-terms');
  if (tb && (data.glossary || []).length) {
    tb.hidden = false;
    tb.querySelector('div').innerHTML = data.glossary.map((t) => `<button type="button" class="term chip-term" data-term="${esc(t.term)}">${esc(t.term)}</button>`).join('');
  }

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
    const rest = list.slice(5);
    document.getElementById('more-wrap').hidden = !rest.length;
    document.getElementById('more-count').textContent = rest.length ? `${rest.length}개` : '';
    document.getElementById('more').innerHTML = rest.map((i, n) => `
      <li><a href="${withDate('issue.html?id=' + encodeURIComponent(i.id))}">
        <span class="mono rank-s">${n + 6}</span>
        <span class="t">${esc(i.title)}<small>${esc(i.what)}</small></span>
        <span class="meta-s"><span class="tag">${esc(i.region)}</span>${impactTag(i.impact)}</span>
      </a></li>`).join('');
    if (!list.length) { box.innerHTML = '<div class="box empty">조건에 맞는 이슈가 없어요.</div>'; return; }
    box.innerHTML = list.slice(0, 5).map((i, n) => `
      <article class="issue">
        <div class="rank mono">${n + 1}</div>
        <div class="body">
          <div class="meta">
            <span class="tag">${esc(i.region)}</span><span class="tag">${esc(i.sector)}</span>${impactTag(i.impact)}
            <span style="flex:1"></span>
            <span class="small">중요도 ${dots(i.importance)}</span>
          </div>
          <h3>${esc(i.title)}</h3>
          <ul>
            <li><strong>무슨 일</strong>${withTerms(i.what)}</li>
            <li><strong>왜 중요</strong>${withTerms(i.why)}</li>
            <li><strong>영향</strong>${withTerms(i.effect)}</li>
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

  const regionGrid = document.getElementById('regions');
  regionGrid.innerHTML = data.regions.map((r) => `
    <button type="button" class="region-btn" data-region="${esc(r.name)}">
      <b>${esc(r.name)}</b><small class="${MOOD_CLASS[r.mood] || 'flat'}">${esc(ARROW[r.mood] || r.mood)}</small>
    </button>`).join('');
  regionGrid.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-region]');
    if (!btn) return;
    if (btn.dataset.region === '한국') { location.href = withDate('korea.html'); return; }
    selected = regionNames.includes(btn.dataset.region) ? btn.dataset.region : '전체';
    renderIssues();
    document.getElementById('top-h').scrollIntoView({ behavior: 'smooth' });
  });

  const all = data.all_articles || [];
  let shown = 30;
  const allBtn = document.getElementById('all-more');
  document.getElementById('all-count').textContent = `${all.length}개`;
  function renderAll() {
    document.getElementById('all').innerHTML = articleList(all.slice(0, shown)) || '<li class="small" style="padding:10px 0">기사 목록이 없어요.</li>';
    allBtn.hidden = shown >= all.length;
  }
  allBtn.addEventListener('click', () => { shown += 30; renderAll(); });
  renderAll();

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
  boot();
  const root = document.getElementById('app');
  let data;
  try { data = await loadData(); } catch (e) { return showError(root, e); }
  await loadTerms(data.glossary);
  setCommon(data);

  const id = new URLSearchParams(location.search).get('id');
  const issue = data.issues.find((i) => i.id === id) || data.issues[0];
  if (!issue) { root.innerHTML = '<div class="box empty">이슈를 찾지 못했어요.</div>'; return; }
  document.title = `${issue.title} — 세계경제 AI`;

  document.getElementById('tags').innerHTML = `
    <span class="tag">${esc(issue.region)}</span><span class="tag">${esc(issue.sector)}</span>${impactTag(issue.impact)}
    <span class="small">중요도 ${dots(issue.importance)}</span>`;
  document.getElementById('title').textContent = issue.title;
  document.getElementById('meta').textContent = `관련 기사 ${issue.articles.length}개 · 업데이트 ${fmtTime(data.generated_at)}`;
  document.getElementById('why').innerHTML = withTerms(issue.why_important);

  let easy = true;
  const toggle = document.getElementById('toggle');
  function renderSummary() {
    toggle.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String((b.dataset.mode === 'easy') === easy)));
    const lines = easy ? issue.easy_summary : issue.pro_summary;
    document.getElementById('lines').innerHTML = (lines || []).map((l) => `<li>${withTerms(l)}</li>`).join('');
  }
  toggle.addEventListener('click', (e) => {
    const b = e.target.closest('button[data-mode]');
    if (b) { easy = b.dataset.mode === 'easy'; renderSummary(); }
  });
  renderSummary();

  // 이 이슈가 한국에 주는 영향 (한국 분석에 연결된 경우)
  const k = (data.korea?.world_to_korea || []).find((w) => w.issue_id === issue.id);
  if (k) {
    const box = document.getElementById('to-korea');
    box.hidden = false;
    box.querySelector('p').innerHTML = `${withTerms(k.effect)} <span class="small">· 영향 받는 곳: ${esc(k.who)}</span>`;
    box.querySelector('[data-impact]').innerHTML = impactTag(k.impact);
  }

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

  document.getElementById('sources').innerHTML = articleList(issue.articles);
  document.getElementById('related').innerHTML = data.issues.filter((i) => i.id !== issue.id).slice(0, 3)
    .map((i) => `<a href="${withDate('issue.html?id=' + encodeURIComponent(i.id))}" class="rel-link">${esc(i.title)} →</a>`).join('');
}

/* ───────── 🇰🇷 한국 화면 ───────── */
async function initKorea() {
  boot();
  const root = document.getElementById('app');
  let data;
  try { data = await loadData(); } catch (e) { return showError(root, e); }
  await loadTerms(data.glossary);
  setCommon(data);

  document.getElementById('tickers').innerHTML = tickersHTML(data.korea_indicators?.length ? data.korea_indicators
    : data.indicators.filter((t) => /코스피|원\//.test(t.name)));
  const k = data.korea;
  if (!k) {
    document.getElementById('korea-body').innerHTML = `<div class="box empty">이 날은 한국 집중 분석이 없어요.<br>한국 분석은 기능이 추가된 날부터 매일 만들어져요.</div>`;
    return;
  }
  document.getElementById('k-summary').innerHTML = withTerms(k.summary);
  document.getElementById('k-mood').innerHTML = impactTag(k.mood);

  document.getElementById('k-points').innerHTML = k.key_points.map((p, n) => `
    <article class="box kpoint">
      <div class="meta"><span class="mono rank-s">${n + 1}</span>${impactTag(p.impact)}</div>
      <h3>${esc(p.title)}</h3>
      <p>${withTerms(p.detail)}</p>
      ${p.easy ? `<p class="easy"><b>쉽게 말하면</b> ${withTerms(p.easy)}</p>` : ''}
    </article>`).join('');

  document.getElementById('k-world').innerHTML = k.world_to_korea.map((w) => `
    <li class="w2k">
      <div class="w2k-from"><span class="w2k-tag world">세계</span>${w.issue_id ? `<a href="${withDate('issue.html?id=' + encodeURIComponent(w.issue_id))}">${esc(w.world_issue)}</a>` : esc(w.world_issue)}</div>
      <div class="w2k-arrow" aria-hidden="true">↓</div>
      <div class="w2k-to"><span class="w2k-tag kr">한국</span>${withTerms(w.effect)}<div class="small">영향 받는 곳: ${esc(w.who)} ${impactTag(w.impact)}</div></div>
    </li>`).join('') || '<li class="small">오늘은 연결된 세계 이슈가 없어요.</li>';

  document.getElementById('k-sectors').innerHTML = k.sectors.map((s) => `
    <div class="ksector ${MOOD_CLASS[s.outlook]}"><b>${esc(s.name)}</b>${impactTag(s.outlook)}<span class="small">${esc(s.reason)}</span></div>`).join('')
    || '<p class="small">오늘 뉴스에서 근거가 있는 산업이 없어요.</p>';

  const watch = document.getElementById('k-watch');
  watch.innerHTML = k.watch.map((w) => `<li>${withTerms(w)}</li>`).join('');
  watch.closest('section').hidden = !k.watch.length;

  document.getElementById('k-articles').innerHTML = articleList(k.articles) || '<li class="small">연결된 기사가 없어요.</li>';
}

/* ───────── 📅 주간 정리 화면 ───────── */
async function initWeekly() {
  boot();
  const root = document.getElementById('app');
  let weeks = [];
  try { weeks = (await getJSON('data/weekly/index.json')).weeks || []; } catch (e) { /* 아직 없어요 */ }
  if (!weeks.length) {
    root.innerHTML = `<div class="box empty" style="margin-top:28px">📅 아직 주간 정리가 없어요.<br>
      매주 <b>일요일</b> 아침 자동 업데이트 때 지난 7일을 정리해서 여기에 올라와요.</div>`;
    return;
  }
  const wanted = new URLSearchParams(location.search).get('week');
  const cur = weeks.includes(wanted) ? wanted : weeks[0];
  let w;
  try { w = await getJSON(`data/weekly/${cur}.json`); } catch (e) { return showError(root, e); }
  await loadTerms([]);

  const sel = document.getElementById('week-select');
  sel.innerHTML = weeks.map((x) => `<option value="${x}" ${x === cur ? 'selected' : ''}>${shortDate(x)} 끝나는 주</option>`).join('');
  sel.addEventListener('change', () => { location.href = `weekly.html?week=${sel.value}`; });

  document.getElementById('w-period').textContent = `${fmtDate(w.week_start)} ~ ${fmtDate(w.week_end)} · ${w.day_count}일 치 기록으로 정리`;
  document.getElementById('w-title').textContent = w.title;
  document.getElementById('w-mood').innerHTML = impactTag(w.mood);
  document.getElementById('w-summary').innerHTML = withTerms(w.summary);
  document.getElementById('w-numbers').innerHTML = (w.numbers || []).map((n) => `
    <button type="button" class="ticker" data-chart="${esc(n.name)}"><span class="name">${esc(n.name)} <span class="zoom" aria-hidden="true">⤢</span></span>
      <span class="value mono">${esc(n.value)}</span><span class="row"><span class="mono ${esc(n.direction)}">이번 주 ${esc(n.change)}</span></span></button>`).join('');
  document.getElementById('w-stories').innerHTML = w.top_stories.map((s, i) => `
    <article class="box kpoint">
      <div class="meta"><span class="mono rank-s">${i + 1}</span><span class="tag">${esc(s.region)}</span>${impactTag(s.impact)}</div>
      <h3>${esc(s.title)}</h3>
      <p>${withTerms(s.story)}</p>
      ${s.days.length ? `<div class="day-links">${s.days.map((d) => `<a href="index.html?date=${d}" class="chip-link">${shortDate(d)} 기록 →</a>`).join('')}</div>` : ''}
    </article>`).join('');
  document.getElementById('w-korea').innerHTML = withTerms(w.korea);
  document.getElementById('w-next').innerHTML = w.next_week.map((x) => `<li>${withTerms(x)}</li>`).join('');
}

/* ───────── 📖 용어 사전 화면 ───────── */
async function initGlossary() {
  boot();
  const root = document.getElementById('app');
  let book;
  try { book = await getJSON('data/glossary.json'); } catch (e) {
    root.innerHTML = `<div class="box empty" style="margin-top:28px">📖 아직 용어 사전이 비어 있어요.<br>다음 자동 업데이트부터 매일 새 경제 용어가 쌓여요.</div>`;
    return;
  }
  const terms = Object.values(book.terms || {}).sort((a, b) => a.term.localeCompare(b.term, 'ko'));
  const latest = terms.reduce((m, t) => (t.last_seen > m ? t.last_seen : m), '');
  document.getElementById('g-count').textContent = `지금까지 모은 용어 ${terms.length}개`;
  const input = document.getElementById('g-q');
  const list = document.getElementById('g-list');
  let onlyNew = false;
  const newBtn = document.getElementById('g-new');

  function render() {
    const q = input.value.trim().toLowerCase();
    const shown = terms.filter((t) => (!onlyNew || t.first_seen === latest) &&
      (!q || [t.term, t.english, t.easy].join(' ').toLowerCase().includes(q)));
    newBtn.setAttribute('aria-pressed', String(onlyNew));
    list.innerHTML = shown.map((t) => `
      <article class="box gterm" id="${esc(t.term)}">
        <div class="gterm-head"><h2>${esc(t.term)}</h2>${t.english ? `<span class="small">${esc(t.english)}</span>` : ''}
          ${t.first_seen === latest ? '<span class="badge">NEW</span>' : ''}</div>
        <p>${esc(t.easy)}</p>
        ${t.example ? `<p class="small">예: ${esc(t.example)}</p>` : ''}
        <div class="small">처음 나온 날 <a href="index.html?date=${esc(t.first_seen)}">${shortDate(t.first_seen)}</a> · 뉴스에 ${t.count}번 등장</div>
      </article>`).join('') || '<div class="box empty">찾는 용어가 없어요.</div>';
  }
  input.addEventListener('input', render);
  newBtn.addEventListener('click', () => { onlyNew = !onlyNew; render(); });
  render();
  if (location.hash) {
    const el = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (el) { el.scrollIntoView(); el.classList.add('flash'); }
  }
}
