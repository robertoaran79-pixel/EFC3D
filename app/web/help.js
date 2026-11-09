// EFC3D: Ajuda dentro do app (módulo separado; só lê a página, não mexe no modelo).
// Conteúdo em ajuda.js. Abre pelo ❓ do cabeçalho, pelo ? de cada seção, pela tecla ? ou ⌘/.
import { DOCS as DOCS_PT } from './ajuda.js?v=1.47';
import { DOCS as DOCS_EN } from './ajuda.en.js?v=1.47';
import { DOCS as DOCS_ES } from './ajuda.es.js?v=1.47';

// a Ajuda no idioma escolhido (i18n.js); troca junto com o idioma da tela
const ALL = { pt: DOCS_PT, en: DOCS_EN, es: DOCS_ES };
let DOCS = ALL[window.FLEXI_LANG] || DOCS_PT;

const $ = (s, r = document) => r.querySelector(s);
const store = {
  get(k, d) { try { const v = localStorage.getItem('flexi-ajuda-' + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem('flexi-ajuda-' + k, JSON.stringify(v)); } catch (e) { /* sem armazenamento */ } },
};
let byId = Object.fromEntries(DOCS.topicos.map((t) => [t.id, t]));
let order = DOCS.topicos.map((t) => t.id);
let appVer = null;
let cur = store.get('ultimo', 'visao');
let built = false;
let query = '';

// ------------------------------------------------------------------ montagem
function build() {
  if (built) return;
  built = true;
  const ov = document.createElement('div');
  ov.id = 'help';
  ov.className = 'hl-ov hidden';
  ov.setAttribute('role', 'dialog');
  ov.setAttribute('aria-modal', 'true');
  ov.setAttribute('aria-label', 'Ajuda do EFC3D');
  ov.innerHTML = `
  <div class="hl-win">
    <div class="hl-top">
      <b class="hl-title">❓ Ajuda</b>
      <input type="search" id="hl-q" placeholder="Buscar na ajuda…" aria-label="Buscar na ajuda" autocomplete="off">
      <span id="hl-count" class="hl-count"></span>
      <span class="hl-ver"></span>
      <button class="btn hl-x" id="hl-close" title="Fechar (Esc)" aria-label="Fechar">✕</button>
    </div>
    <div id="hl-warn" class="hl-warn hidden"></div>
    <div class="hl-body">
      <nav id="hl-nav" class="hl-nav" aria-label="Tópicos"></nav>
      <article id="hl-art" class="hl-art" tabindex="-1"></article>
    </div>
  </div>`;
  document.body.appendChild(ov);
  ov.addEventListener('mousedown', (e) => { if (e.target === ov) close(); });
  $('#hl-close').onclick = close;
  $('#hl-q').addEventListener('input', (e) => { query = e.target.value.trim(); renderNav(); renderTopic(cur); });
  $('#hl-q').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { const f = $('#hl-nav a[data-id]'); if (f) open(f.dataset.id); }
  });
  $('.hl-ver', ov).textContent = `documentação ${DOCS.versao} · ${DOCS.atualizado}`;
  checkVersion();
}

function plain(html) { const d = document.createElement('div'); d.innerHTML = html; return d.textContent || ''; }
const norm = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
function matches(t) {
  if (!query) return true;
  const hay = norm(t.titulo + ' ' + plain(t.html) + (t.id === 'novidades' ? ' ' + DOCS.novidades.map((n) => n.itens.join(' ')).join(' ') : ''));
  return norm(query).split(/\s+/).every((w) => hay.includes(w));
}

function renderNav() {
  const nav = $('#hl-nav');
  let n = 0;
  nav.innerHTML = DOCS.grupos.map((g) => {
    const items = DOCS.topicos.filter((t) => t.grupo === g && matches(t));
    n += items.length;
    if (!items.length) return '';
    return `<div class="hl-g">${g}</div>` + items.map((t) =>
      `<a href="#" data-id="${t.id}" class="${t.id === cur ? 'on' : ''}" ${t.id === cur ? 'aria-current="page"' : ''}><span class="hl-ic" aria-hidden="true">${t.icone || '•'}</span>${t.titulo}</a>`).join('');
  }).join('') || '<p class="hl-none">Nada encontrado. Tente outra palavra.</p>';
  $('#hl-count').textContent = query ? `${n} tópico(s)` : '';
  nav.querySelectorAll('a[data-id]').forEach((a) => { a.onclick = (e) => { e.preventDefault(); open(a.dataset.id); }; });
}

function renderTopic(id) {
  const t = byId[id] || byId.visao;
  cur = t.id;
  store.set('ultimo', cur);
  const art = $('#hl-art');
  const i = order.indexOf(t.id);
  const prev = byId[order[i - 1]], next = byId[order[i + 1]];
  art.innerHTML = `<h2><span aria-hidden="true">${t.icone || ''}</span> ${t.titulo}</h2>${t.html}
    <div class="hl-pn">
      ${prev ? `<a href="#" data-go="${prev.id}">← ${prev.titulo}</a>` : '<span></span>'}
      ${next ? `<a href="#" data-go="${next.id}">${next.titulo} →</a>` : '<span></span>'}
    </div>`;
  enhance(art);
  if (query) highlight(art, query);
  art.scrollTop = 0;
}

// ------------------------------------------------------------------ interação no conteúdo
function enhance(art) {
  art.querySelectorAll('[data-go]').forEach((a) => { a.href = '#'; a.onclick = (e) => { e.preventDefault(); open(a.dataset.go); }; });
  art.querySelectorAll('[data-show]').forEach((b) => {
    if (!b.classList.contains('btn')) b.classList.add('hl-show');
    b.type = 'button';
    if (!/^👁/.test(b.textContent)) b.textContent = '👁 ' + b.textContent;
    b.onclick = () => { close(); spotlight(b.dataset.show, { titulo: b.dataset.tip || '', texto: '' }); };
  });
  art.querySelectorAll('[data-tour]').forEach((b) => { b.onclick = () => { close(); tour(0); }; });
  art.querySelectorAll('ul.hl-check').forEach((ul) => {
    const key = 'check-' + ul.dataset.id;
    const st = store.get(key, []);
    const lis = [...ul.children];
    lis.forEach((li, k) => {
      const cb = document.createElement('input');
      cb.type = 'checkbox'; cb.checked = !!st[k];
      cb.setAttribute('aria-label', 'Passo ' + (k + 1) + ' feito');
      cb.onchange = () => { st[k] = cb.checked; store.set(key, st); prog(); };
      const lab = document.createElement('label');
      const txt = document.createElement('span');     // o texto do passo fica junto, numa linha só
      txt.append(...li.childNodes);
      lab.append(cb, txt);
      li.append(lab);
    });
    const bar = document.createElement('div');
    bar.className = 'hl-prog';
    const reset = document.createElement('button');
    reset.className = 'btn'; reset.textContent = 'Desmarcar tudo';
    reset.onclick = () => { store.set(key, []); renderTopic(cur); };
    const txt = document.createElement('span');
    bar.append(txt, reset);
    ul.after(bar);
    function prog() { const d = ul.querySelectorAll('input:checked').length; txt.textContent = `${d} de ${lis.length} passos feitos${d === lis.length ? ' ✅' : ''}`; }
    prog();
  });
  art.querySelectorAll('input.hl-filter').forEach((inp) => {
    const tbl = inp.closest('article').querySelector('table.hl-filterable');
    inp.oninput = () => {
      const q = norm(inp.value.trim());
      [...tbl.rows].slice(1).forEach((r) => { r.style.display = !q || norm(r.textContent).includes(q) ? '' : 'none'; });
    };
  });
  const nv = art.querySelector('.hl-novidades');
  if (nv) {
    nv.innerHTML = DOCS.novidades.map((n) => `<div class="hl-nov"><h3>Versão ${n.versao}${n.data ? ` <small>${n.data}</small>` : ''}${n.versao === DOCS.versao ? ' <span class="newtag">atual</span>' : ''}</h3><ul>${n.itens.map((x) => `<li>${x}</li>`).join('')}</ul></div>`).join('');
  }
  art.querySelectorAll('.hl-appver').forEach((s) => { s.textContent = appVer || '?'; });
  art.querySelectorAll('.hl-docver').forEach((s) => { s.textContent = DOCS.versao; });
  art.querySelectorAll('.hl-docdate').forEach((s) => { s.textContent = DOCS.atualizado; });
  art.querySelectorAll('.hl-sys').forEach((s) => { s.textContent = (window.flexiPlat && window.flexiPlat.sistema) || '?'; });
  const SOFT_TXT = 'sem aceleração: o 3D é desenhado pelo processador';
  art.querySelectorAll('.hl-gpu').forEach((s) => { const g = window.flexi && window.flexi.GPU; s.textContent = g ? (g.nome || '?') + (g.soft ? ' · ' + (window.T ? window.T(SOFT_TXT) : SOFT_TXT) : '') : '?'; });
}

function highlight(root, q) {
  const words = norm(q).split(/\s+/).filter((w) => w.length > 1);
  if (!words.length) return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => (n.parentElement.closest('h2,button,input,.hl-pn') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  let first = null;
  nodes.forEach((n) => {
    const txt = n.nodeValue, low = norm(txt);
    const ranges = [];
    words.forEach((w) => { let p = low.indexOf(w); while (p >= 0) { ranges.push([p, p + w.length]); p = low.indexOf(w, p + w.length); } });
    if (!ranges.length) return;
    ranges.sort((a, b) => a[0] - b[0]);
    const frag = document.createDocumentFragment();
    let pos = 0;
    ranges.forEach(([a, b]) => {
      if (a < pos) return;
      frag.append(txt.slice(pos, a));
      const m = document.createElement('mark'); m.textContent = txt.slice(a, b); frag.append(m);
      if (!first) first = m;
      pos = b;
    });
    frag.append(txt.slice(pos));
    n.replaceWith(frag);
  });
  if (first) setTimeout(() => first.scrollIntoView({ block: 'center' }), 30);
}

// ------------------------------------------------------------------ abrir / fechar
let lastFocus = null;
export function open(id) {
  build();
  hideSpot();
  const ov = $('#help');
  if (ov.classList.contains('hidden')) lastFocus = document.activeElement;
  ov.classList.remove('hidden');
  if (id) cur = id;
  if (query && !matches(byId[cur])) { query = ''; $('#hl-q').value = ''; }
  renderNav();
  renderTopic(cur);
  markSeen();
  setTimeout(() => (id ? $('#hl-art') : $('#hl-q')).focus(), 20);
}
export function close() {
  const ov = $('#help');
  if (!ov || ov.classList.contains('hidden')) return;
  ov.classList.add('hidden');
  if (lastFocus && lastFocus.focus) lastFocus.focus();
}
const isOpen = () => { const ov = $('#help'); return ov && !ov.classList.contains('hidden'); };

// ------------------------------------------------------------------ destaque na tela e tour
let spot = null, tip = null, spotEl = null, tourIdx = -1;
function visibleTarget(sel) {
  let el = document.querySelector(sel);
  if (!el) return null;
  if (window.flexiShell) window.flexiShell.reveal(el, false);   // abre a aba onde o controle está
  for (let d = el.closest('details'); d; d = d.parentElement && d.parentElement.closest('details')) d.open = true;
  while (el && el.getClientRects().length === 0) el = el.parentElement;
  return el;
}
function place() {
  if (!spot || !spotEl) return;
  const r = spotEl.getBoundingClientRect(), pad = 6;
  Object.assign(spot.style, { left: r.left - pad + 'px', top: r.top - pad + 'px', width: r.width + pad * 2 + 'px', height: r.height + pad * 2 + 'px' });
  const tw = tip.offsetWidth, th = tip.offsetHeight, W = innerWidth, H = innerHeight;
  let x = r.right + 14, y = r.top;
  if (x + tw > W - 10) { x = Math.max(10, Math.min(W - tw - 10, r.left)); y = r.bottom + 12; }
  if (y + th > H - 10) y = Math.max(10, r.top - th - 12);
  if (y < 10) y = 10;
  Object.assign(tip.style, { left: x + 'px', top: y + 'px' });
}
function spotlight(sel, { titulo, texto }, tourMode = false) {
  hideSpot();
  spotEl = visibleTarget(sel);
  if (!spotEl) return;
  spotEl.scrollIntoView({ block: 'center', behavior: 'smooth' });
  spot = document.createElement('div');
  spot.className = 'hl-spot';
  tip = document.createElement('div');
  tip.className = 'hl-tip';
  tip.setAttribute('role', 'status');
  const nav = tourMode ? `<div class="hl-tnav"><span>${tourIdx + 1} de ${DOCS.tour.length}</span>
      <button class="btn" data-t="prev" ${tourIdx === 0 ? 'disabled' : ''}>← Anterior</button>
      <button class="btn primary" data-t="next">${tourIdx === DOCS.tour.length - 1 ? 'Concluir ✓' : 'Próximo →'}</button></div>`
    : '<div class="hl-tnav"><button class="btn" data-t="back">← Voltar à ajuda</button><button class="btn" data-t="ok">Entendi</button></div>';
  tip.innerHTML = `${titulo ? `<b>${titulo}</b>` : ''}${texto ? `<p>${texto}</p>` : ''}${nav}`;
  document.body.append(spot, tip);
  tip.querySelectorAll('[data-t]').forEach((b) => {
    b.onclick = () => {
      const t = b.dataset.t;
      if (t === 'next') tour(tourIdx + 1); else if (t === 'prev') tour(tourIdx - 1);
      else if (t === 'back') open(); else hideSpot();
    };
  });
  spot.onclick = () => { if (!tourMode) hideSpot(); };
  place();
  setTimeout(place, 350);
  setTimeout(() => { const b = tip && tip.querySelector('.primary, [data-t="ok"]'); if (b) b.focus(); }, 360);
}
function hideSpot() {
  if (spot) spot.remove();
  if (tip) tip.remove();
  spot = tip = spotEl = null;
}
export function tour(i) {
  if (i < 0) return;
  if (i >= DOCS.tour.length) { tourIdx = -1; hideSpot(); store.set('tour-feito', true); return; }
  tourIdx = i;
  const s = DOCS.tour[i];
  spotlight(s.alvo, s, true);
}
addEventListener('resize', place);
document.addEventListener('scroll', place, true);

// ------------------------------------------------------------------ versão e novidades
function checkVersion() {
  const w = $('#hl-warn');
  if (!w || !appVer) return;
  if (appVer !== DOCS.versao) {
    w.textContent = `⚠ Esta documentação é da versão ${DOCS.versao} e o app está na ${appVer}. Algumas telas podem estar diferentes.`;
    w.classList.remove('hidden');
  } else w.classList.add('hidden');
}
function markSeen() {
  store.set('vista', DOCS.versao);
  const b = $('#btn-help');
  if (b) b.classList.remove('hl-new');
}

// ------------------------------------------------------------------ pontos de entrada na página
function wire() {
  const b = $('#btn-help');
  if (b) {
    b.onclick = () => open();
    if (store.get('vista', null) !== DOCS.versao) { b.classList.add('hl-new'); b.title = `Ajuda: veja as novidades da ${DOCS.versao}`; }
  }
  // ? ao lado do título de cada seção
  const map = {};
  DOCS.topicos.forEach((t) => { if (t.secao && !map[t.secao]) map[t.secao] = t.id; });
  Object.entries(map).forEach(([sec, id]) => {
    const h = document.querySelector(`#${sec} h2`) || document.querySelector(`#${sec}`);
    if (!h || h.querySelector('.hl-q')) return;
    const q = document.createElement('button');
    q.className = 'hl-q'; q.type = 'button'; q.textContent = '?';
    q.title = 'Ajuda desta seção'; q.setAttribute('aria-label', 'Ajuda: ' + byId[id].titulo);
    q.onclick = (e) => { e.preventDefault(); e.stopPropagation(); open(id); };
    if (sec === 's-file') { h.prepend(q); q.classList.add('hl-q-file'); } else h.append(q);
  });
  addEventListener('keydown', (e) => {
    const typing = document.activeElement && ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName);
    if (e.key === 'Escape') {
      if (tourIdx >= 0 || spot) { tourIdx = -1; hideSpot(); e.stopImmediatePropagation(); return; }
      if (isOpen()) { close(); e.stopImmediatePropagation(); return; }
    }
    if (tourIdx >= 0 && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) { e.preventDefault(); e.stopImmediatePropagation(); tour(tourIdx + (e.key === 'ArrowRight' ? 1 : -1)); return; }
    if (((e.metaKey || e.ctrlKey) && e.key === '/') || (!typing && !e.metaKey && !e.ctrlKey && e.key === '?')) {
      e.preventDefault(); e.stopImmediatePropagation();
      if (isOpen()) close(); else open();
      return;
    }
    if (isOpen() && !typing && !e.metaKey && !e.ctrlKey) {
      // a ajuda aberta não deixa as teclas chegarem ao editor (A, M, R, S, B, F…)
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') return;
      e.stopImmediatePropagation();
    }
  }, true);
  fetch('/api/status').then((r) => r.json()).then((s) => { appVer = s.versao || null; checkVersion(); }).catch(() => {});
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire); else wire();

addEventListener('flexi-lang', (e) => {
  DOCS = ALL[e.detail] || DOCS_PT;
  byId = Object.fromEntries(DOCS.topicos.map((t) => [t.id, t]));
  order = DOCS.topicos.map((t) => t.id);
  const was = isOpen();
  const el = document.getElementById('help');
  if (el) el.remove();
  built = false;
  if (was) open(cur);
});

window.flexiHelp = { open, close, tour, get DOCS() { return DOCS; } };
