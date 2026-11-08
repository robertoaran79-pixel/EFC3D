// EFC3D: "Separar peças por cor" (new module, v1.1).
// Separate file on purpose: it only reads the model and the painting through window.flexi and
// draws its own objects. The joint editor, painting and joint export do not depend on it.
const F = window.flexi;
const { THREE, S, scene, host, renderer, camera, api, post, setStatus, nf, ndc, solidMat, hexRGB, unb64 } = F;
const $ = (s) => document.querySelector(s);

const TIPOS = { auto: 'Automático (recomendado)', pintura: 'Pela pintura (qualquer forma)', tampao: 'Tampão embutido', membro: 'Membro (corta a parte inteira)' };
const TIPO_CURTO = { auto: 'automático', pintura: 'pela pintura', tampao: 'tampão', membro: 'membro' };
const PINOS = { nenhum: 'Sem pino', corpo: 'Pino no corpo (recomendado)', trava: 'Trava de pressão (sem cola)', peca: 'Pino na peça', cavilha: 'Cavilha solta' };
const CORTES = { plano: 'Plano (face plana, imprime sem suporte)', borda: 'Seguir a borda pintada (face curva)' };
const LUZ = { ok: '🟢', aviso: '🟡', erro: '🔴', nada: '⚪' };
const DEF = { separar: true, tipo: 'auto', corte: 'plano', espessura: 0, profundidade: 2.0, folga: 0.3, suavizar: 0, pino: 'nenhum', pino_mm: 0, incl_a: 0, incl_b: 0 };

const SP = {
  on: false, regions: [], of: null, chave: null, cfg: {}, sel: -1, parts: [], summary: null, base: null,
  group: new THREE.Group(), marks: new THREE.Group(), showPrev: false,
};
scene.add(SP.group); scene.add(SP.marks);
const prevOn = () => !!(window.flexiPecas && window.flexiPecas.active());

// ---------------------------------------------------------------- open / close
// areas of the current painting; options already chosen follow each area (by colour and place)
async function loadRegions(newDefault) {
  const model = $('#drop-text').textContent;
  if (SP.model !== model) { SP.model = model; SP.keep = {}; SP.used = false; }
  const r = await post('/api/split/regions', {});
  if (!r.ok || !r.regioes.length) return r;
  SP.chave = r.chave;
  SP.of = new Int32Array(unb64(r.por_triangulo).buffer);
  const old = SP.keep || {};
  SP.cfg = {};
  SP.regions = r.regioes;
  // exact key first; then the nearest saved area of the same colour (a reopened project or a
  // retouched painting moves the centre a little and the rounded key no longer matches)
  const used = new Set(r.regioes.map(keyOf).filter((k) => old[k]));
  const near = (q) => {
    let best = null, bd = 6;
    Object.keys(old).forEach((k) => {
      if (used.has(k)) return;
      const a = k.split('|').map(Number);
      if (a[0] !== q.cor) return;
      const d = Math.hypot(a[1] - q.centro[0], a[2] - q.centro[1], a[3] - q.centro[2]);
      if (d < bd) { bd = d; best = k; }
    });
    if (best) used.add(best);
    return best ? old[best] : null;
  };
  r.regioes.forEach((q) => {
    const k = keyOf(q);
    const prev = old[k] || near(q);
    if (prev && !old[k]) old[k] = prev;
    SP.cfg[q.id] = Object.assign({}, DEF, prev || {}, { id: q.id, _k: k });
    // specks left by the brush start unchecked: small next to the largest area of that colour
    const big = Math.max(...r.regioes.filter((x) => x.cor === q.cor).map((x) => x.area));
    if (!old[k]) SP.cfg[q.id].separar = newDefault && q.area >= Math.max(4, 0.03 * big);
  });
  SP.keep = Object.fromEntries(Object.values(SP.cfg).map((c) => [c._k, c]));
  return r;
}
async function open() {
  if (!S.base) { setStatus('Carregue um modelo primeiro.'); return; }
  if (S.painting) F.setPainting(false);
  await F.syncPaintNow();
  let r;
  try { r = await loadRegions(true); } catch (e) { setStatus('Erro: ' + e.message); return; }
  if (!r.ok || !r.regioes.length) { setStatus(r.msg || 'Nenhuma área pintada. Pinte as partes que quer separar (aba Cores).'); return; }
  if (prevOn()) window.flexiPecas.show(false);          // a prévia fica guardada em Ver › Prévia
  SP.on = true; S.splitting = true; SP.base = S.base; SP.used = true;
  F.setView(false);
  $('#btn-split').classList.add('active');
  $('#btn-split').textContent = '✂ Separando… (clique para concluir)';
  $('#split-box').classList.remove('hidden');
  select(SP.regions.findIndex((q) => SP.cfg[q.id].separar));
  renderList();
  setStatus(`${SP.regions.length} área(s) pintada(s). Clique numa área no modelo ou na lista, ajuste e veja a prévia.`);
}
function keyOf(q) { return `${q.cor}|${Math.round(q.centro[0])}|${Math.round(q.centro[1])}|${Math.round(q.centro[2])}`; }
function close() {
  if (prevOn()) window.flexiPecas.show(false);
  SP.on = false; S.splitting = false;
  clearMarks();
  $('#btn-split').classList.remove('active');
  $('#btn-split').textContent = '✂ Separar por cor';
  $('#split-box').classList.add('hidden');
  if (S.base) S.base.visible = true;
  F.setView(false);
  if (F.renderJoints) F.renderJoints();
  setStatus('Pronto.');
}
$('#btn-split').onclick = () => (SP.on ? close() : open());
$('#split-done').onclick = close;
// painting or another model closes this mode first (the areas come from the painting)
$('#btn-paint').addEventListener('click', () => { if (SP.on) close(); }, true);
setInterval(() => { if (SP.on && S.base !== SP.base) close(); }, 700);
window.addEventListener('keydown', (e) => {
  if (!SP.on || (e.key !== 'Escape' && e.key !== 'Enter')) return;
  if (document.activeElement && ['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
  close();
});

// ---------------------------------------------------------------- list and options
function renderList() {
  const ol = $('#split-list');
  ol.innerHTML = '';
  SP.regions.forEach((q, i) => {
    const c = SP.cfg[q.id];
    const res = SP.summary && SP.summary.regioes.find((x) => x.id === q.id);
    const luz = c.separar ? (res ? res.luz : 'nada') : null;
    const meta = c.separar ? `Cor ${q.cor} · ${nf(q.area, 0)} mm² · ${TIPO_CURTO[c.tipo] || c.tipo}${c.tipo === 'auto' && res && res.tipo ? ' → ' + TIPO_CURTO[res.tipo] : ''}${c.pino !== 'nenhum' ? ' · pino' : ''}`
      : `Cor ${q.cor} · ${nf(q.area, 0)} mm² · fica no corpo`;
    const li = window.flexiUI.row({ list: 'separar', luz: luz ? LUZ[luz] : '➖', luzTitle: luz ? 'verificação' : 'não separar',
      cor: S.palette[q.cor - 1] || '#ccc', tag: `Área ${q.id + 1}`, meta, selected: i === SP.sel, off: !c.separar,
      onSelect: () => select(i), hidden: !!(SP.hid && SP.hid.has(q.id)),
      onToggle: c.separar ? () => toggleHide(q) : null,
      onDelete: () => setSep(q, c, !c.separar), onDeleteSelected: () => { if (c.separar) setSep(q, c, false); }, delIcon: c.separar ? '✕' : '↺',
      delTitle: c.separar ? 'Não separar esta área (Delete)' : 'Separar esta área de novo' });
    ol.appendChild(li);
  });
}
// 👁 de uma área: esconde a peça dela na vista (depois da prévia) para pintar ou marcar o que está
// por baixo. Só a vista muda.
async function toggleHide(q) {
  SP.hid = SP.hid || new Set();
  if (SP.hid.has(q.id)) SP.hid.delete(q.id); else SP.hid.add(q.id);
  renderList();
  const P = window.flexiPecas, on = SP.hid.has(q.id);
  if (!P) return;
  if (on && !P.canHide()) { setStatus(`Área ${q.id + 1}: para ocultar a peça, rode a prévia das peças (Ver › Prévia).`); return; }
  const k = await P.applyHide();
  setStatus(on && k ? `Área ${q.id + 1} oculta: a peça some da vista e o clique passa por ela. A prévia e a exportação continuam com todas as peças.` : `Área ${q.id + 1} aparece de novo.`);
}
function hiddenAreas() { return SP.hid || new Set(); }
function setSep(q, c, on) {
  c.separar = on;
  if (!on) window.flexiUI.push(`Área ${q.id + 1} (separação)`, () => { c.separar = true; changed(); renderList(); renderEdit(); });
  changed(); renderList(); renderEdit();
  setStatus(on ? `Área ${q.id + 1} volta a ser separada.` : `Área ${q.id + 1} não será separada (fica no corpo; a pintura continua). ⌘Z desfaz.`);
}
function select(i) {
  SP.sel = i;
  renderList();
  renderEdit();
  drawMarks();
}
function num(v, d = 0) { const x = parseFloat(String(v).replace(',', '.')); return Number.isFinite(x) ? x : d; }
function renderEdit() {
  const box = $('#split-edit');
  const q = SP.regions[SP.sel];
  if (!q) { box.innerHTML = '<p class="hint">Escolha uma área.</p>'; return; }
  const c = SP.cfg[q.id];
  const pl = c.tipo === 'tampao', mb = c.tipo === 'membro', pt = c.tipo === 'pintura', au = c.tipo === 'auto';
  const HINT = {
    auto: 'Automático: tampão quando uma direção reta alcança a área toda (olho, botão, emblema); senão, corte pela pintura. Funciona para figuras humanas: cabelo, rosto, mãos, pés, faixa.',
    pintura: 'Pela pintura: a peça é o volume mais perto da área pintada. As faces de contato seguem a borda e separam também partes que encostam no corpo (mão na perna, trança no ombro). Faces de contato curvas: cole as peças.',
    tampao: 'Tampão: a área sai como uma peça embutida, com paredes retas na direção da seta e fundo plano. O corpo fica com o encaixe.',
    membro: 'Membro: em cada borda da pintura um corte atravessa a parte inteira (pinte o membro todo a partir de onde quer cortar). Plano deixa a face reta para a mesa; seguir a borda acompanha a pintura.' };
  box.innerHTML = `<div class="card">
    <h3>Área ${q.id + 1} · cor ${q.cor} <span class="swatch" style="background:${S.palette[q.cor - 1] || '#ccc'}"></span></h3>
    <label class="chk"><input type="checkbox" data-k="separar" ${c.separar ? 'checked' : ''}> Separar esta área como peça</label>
    <label>Tipo de corte<select data-k="tipo">${Object.entries(TIPOS).map(([k, t]) => `<option value="${k}" ${c.tipo === k ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
    <p class="hint">${HINT[c.tipo] || ''}</p>
    ${mb ? `<label>Corte<select data-k="corte">${Object.entries(CORTES).map(([k, t]) => `<option value="${k}" ${(c.corte || 'plano') === k ? 'selected' : ''}>${t}</option>`).join('')}</select></label>` : ''}
    <div class="grid2">
      ${pt ? `<label>Espessura máxima (mm)<input type="number" data-k="espessura" min="0" step="0.5" value="${c.espessura || ''}" placeholder="sem limite"></label>` : ''}
      ${pl || au ? `<label>Profundidade do tampão (mm)<input type="number" data-k="profundidade" min="0.8" step="0.1" value="${c.profundidade}"></label>` : ''}
      <label>Folga (mm)<input type="number" data-k="folga" min="0.05" step="0.05" value="${c.folga}"></label>
      ${!mb ? `<label>Suavizar borda (mm)<input type="number" data-k="suavizar" min="0" step="0.1" value="${c.suavizar || ''}" placeholder="automático"></label>` : ''}
      <label>Pino<select data-k="pino">${Object.entries(PINOS).map(([k, t]) => `<option value="${k}" ${c.pino === k ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
      ${c.pino !== 'nenhum' ? `<label>Largura do pino (mm)<input type="number" data-k="pino_mm" min="1.2" step="0.1" value="${c.pino_mm || ''}" placeholder="automática"></label>` : ''}
    </div>
    ${pl || au ? `<div class="grid2">
      <label>Inclinar seta: cima/baixo (°)<input type="number" data-k="incl_up" min="-60" max="60" step="5" value="${-c.incl_a || 0}"></label>
      <label>Inclinar seta: lados (°)<input type="number" data-k="incl_b" min="-60" max="60" step="5" value="${c.incl_b || 0}"></label>
    </div><p class="hint">A seta mostra a direção em que a peça entra. Incline se algo do modelo ficar na frente.</p>` : ''}
    <div class="row"><button class="btn" data-act="todas">Usar estas opções em todas as áreas</button></div>
  </div>`;
  box.querySelectorAll('[data-k]').forEach((el) => el.addEventListener('change', () => {
    const k = el.dataset.k;
    if (k === 'separar') c.separar = el.checked;
    else if (k === 'tipo' || k === 'pino' || k === 'corte') c[k] = el.value;
    else if (k === 'incl_up') c.incl_a = -num(el.value);
    else c[k] = num(el.value, k === 'folga' ? 0.3 : 0);
    if (k === 'folga' && c.folga < 0.05) c.folga = 0.05;
    if (k === 'profundidade' && c.profundidade < 0.8) c.profundidade = 0.8;
    changed();
    renderList(); renderEdit(); drawMarks();
  }));
  box.querySelector('[data-act=todas]').onclick = () => {
    const keys = ['tipo', 'corte', 'espessura', 'profundidade', 'folga', 'suavizar', 'pino', 'pino_mm'];
    Object.values(SP.cfg).forEach((o) => { if (o !== c) keys.forEach((k) => { o[k] = c[k]; }); });
    changed(); renderList();
    setStatus('Opções copiadas para todas as áreas.');
  };
}
function changed() {
  if (SP.summary) { clearPreview(); setStatus('As opções mudaram: faça a prévia de novo.'); }
  else if (window.flexiPecas) window.flexiPecas.invalidate();
  renderPlan();
}

// ---------------------------------------------------------------- marks on the model
const tint = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial({
  color: 0xffffff, transparent: true, opacity: 0.5, depthWrite: false, side: THREE.DoubleSide,
  polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }));
tint.renderOrder = 24;
function clearMarks() {
  SP.marks.children.slice().forEach((o) => { SP.marks.remove(o); if (o.geometry && o !== tint) o.geometry.dispose(); });
}
function frame(n) {
  const up = new THREE.Vector3(0, 0, 1);
  let a = up.clone().sub(n.clone().multiplyScalar(n.z));
  if (a.length() < 0.15) a = new THREE.Vector3(0, 1, 0).sub(n.clone().multiplyScalar(n.y));
  const v = a.normalize();
  const u = new THREE.Vector3().crossVectors(v, n);
  return { u, v, n };
}
function axisOf(q, c) {
  const n = new THREE.Vector3(...q.normal).normalize();
  const { u, v } = frame(n);
  const a = THREE.MathUtils.degToRad(c.incl_a || 0), b = THREE.MathUtils.degToRad(c.incl_b || 0);
  return u.multiplyScalar(Math.sin(b)).add(v.multiplyScalar(-Math.sin(a) * Math.cos(b))).add(n.multiplyScalar(Math.cos(a) * Math.cos(b))).normalize();
}
function drawMarks() {
  clearMarks();
  if (!SP.on || prevOn() || !S.base) return;
  const q = SP.regions[SP.sel];
  if (!q) return;
  const pos = S.base.geometry.attributes.position.array;
  const list = [];
  for (let t = 0; t < SP.of.length; t++) if (SP.of[t] === q.id) list.push(t);
  const tp = new Float32Array(list.length * 9);
  list.forEach((t, i) => tp.set(pos.subarray(t * 9, t * 9 + 9), i * 9));
  tint.geometry.dispose();
  tint.geometry = new THREE.BufferGeometry();
  tint.geometry.setAttribute('position', new THREE.BufferAttribute(tp, 3));
  SP.marks.add(tint);
  const c = SP.cfg[q.id];
  if (c.tipo === 'tampao') {
    const d = axisOf(q, c);
    const L = Math.max(8, Math.sqrt(q.area) * 1.2);
    const o = new THREE.Vector3(...q.centro);
    const arrow = new THREE.ArrowHelper(d, o, L, 0xffffff, L * 0.28, L * 0.16);
    arrow.traverse((m) => { if (m.material) { m.material.depthTest = false; m.material.transparent = true; } m.renderOrder = 26; });
    SP.marks.add(arrow);
  }
}

// click on the model picks an area (left click without dragging)
let down = null;
const ray = new THREE.Raycaster();
host.addEventListener('pointerdown', (e) => { if (SP.on) down = [e.clientX, e.clientY]; }, true);
host.addEventListener('pointerup', (e) => {
  if (!SP.on || !down || e.button !== 0) return;
  const moved = Math.hypot(e.clientX - down[0], e.clientY - down[1]);
  down = null;
  if (moved > 4 || prevOn() || !S.base) return;
  ray.setFromCamera(ndc(e), camera);
  const h = ray.intersectObject(S.base)[0];
  if (!h) return;
  const id = SP.of[h.faceIndex];
  if (id < 0) { setStatus('Esta parte não está pintada. Só áreas pintadas viram peças.'); return; }
  const i = SP.regions.findIndex((q) => q.id === id);
  if (i >= 0) { select(i); setStatus(`Área ${id + 1} (cor ${SP.regions[i].cor}) selecionada.`); }
}, true);

// ---------------------------------------------------------------- preview
function configs() {
  return SP.regions.map((q) => {
    const c = SP.cfg[q.id];
    return { id: q.id, separar: !!c.separar, tipo: c.tipo, corte: c.corte || 'plano', espessura: c.espessura || 0, profundidade: c.profundidade, folga: c.folga, suavizar: c.suavizar || 0,
             pino: c.pino, pino_mm: c.pino_mm || 0, incl_a: c.incl_a || 0, incl_b: c.incl_b || 0 };
  });
}
function clearPreview() {
  SP.summary = null;
  $('#split-report').innerHTML = '';
  if (window.flexiPecas) window.flexiPecas.invalidate();
  drawMarks();
}
// a prévia é a única (pecas.js): peças por cor e cortes livres juntos
function runPreview() { return window.flexiPecas ? window.flexiPecas.run() : null; }
function applyResult(r) {
  SP.summary = r;
  if (!r) { $('#split-report').innerHTML = ''; renderList(); return; }
  renderList();
  renderReport(r);
}
$('#split-prev').onclick = () => runPreview();

// ---------------------------------------------------------------- export (section 5)
function marked() { return SP.used ? Object.values(SP.keep || {}).filter((c) => c.separar) : []; }
// what the single export takes from this module: null when no area is marked
async function forExport() {
  if (!SP.used || !marked().length || !S.base) return null;
  await F.syncPaintNow();
  const r = await loadRegions(false);           // the painting may have changed: same options, fresh areas
  if (!r.ok || !marked().length) return null;
  if (SP.on) renderList();
  return { chave: SP.chave, configs: configs() };
}
function renderPlan() {
  const box = $('#exp-plan');
  if (!box) return;
  const nj = S.joints.length, cuts = marked();
  const nf_ = window.flexiFree ? window.flexiFree.count() : 0;
  const np_ = window.flexiPlano ? (window.flexiPlano.forExport() || []).length : 0;
  const byType = {};
  cuts.forEach((c) => { byType[c.tipo] = (byType[c.tipo] || 0) + 1; });
  const cutTxt = Object.entries(byType).map(([k, n]) => `${n} ${TIPO_CURTO[k] || k}`).join(', ');
  const line = (on, label, txt) => `<div class="pl"><i>${on ? '✅' : '➖'}</i><b>${label}</b><span class="${on ? '' : 'muted'}">${txt}</span></div>`;
  const html = '<div class="lbl3">O que vai ser exportado</div>' +
    line(nj > 0, 'Juntas', nj ? `${nj} junta(s): corpo articulado` : 'nenhuma: o corpo sai inteiro') +
    line(cuts.length > 0, 'Peças por cor', cuts.length ? `${cuts.length} área(s): ${cutTxt}` : 'nenhuma área marcada') +
    line(nf_ > 0, 'Corte livre', nf_ ? `${nf_} corte(s) pronto(s)` : 'nenhum corte') +
    line(np_ > 0, 'Corte plano', np_ ? `${np_} plano(s)` : 'nenhum plano') +
    (!nj && !cuts.length && !nf_ && !np_ ? '<p class="hint">Posicione juntas, marque áreas para separar, desenhe cortes, ou combine.</p>' : '');
  if (box.innerHTML !== html) box.innerHTML = html;
  if (S.exporting) return;
  $('#btn-check-all').disabled = !nj;
  $('#btn-export').disabled = !nj && !cuts.length && !nf_ && !np_;
}
setInterval(renderPlan, 800);
renderPlan();

function renderReport(r) {
  let h = '';
  const regs = r.regioes.slice().sort((a, b) => a.id - b.id);
  h += '<h4>Áreas</h4><ul class="checks">';
  regs.forEach((x) => {
    const probs = x.checks.filter((c) => c.nivel !== 'ok');
    h += `<li class="${x.luz}">${LUZ[x.luz]} Área ${x.id + 1}: ${x.ok ? 'cortada' : 'não cortada'}${probs.length ? '. ' + probs.map((c) => c.texto).join(' ') : ''}</li>`;
  });
  h += '</ul>';
  const q = SP.regions[SP.sel];
  const mine = q && regs.find((x) => x.id === q.id);
  if (mine) {
    h += `<h4>Área ${q.id + 1} em detalhe</h4><ul class="checks">` +
      mine.checks.map((c) => `<li class="${c.nivel}">${LUZ[c.nivel]} ${c.texto}</li>`).join('') + '</ul>';
  }
  if (r.conflitos && r.conflitos.length) {
    h += '<h4>Juntas e cortes</h4><ul class="checks">' + r.conflitos.map((c) => `<li class="aviso">🟡 ${c}</li>`).join('') + '</ul>';
  }
  const mm = r.malha;
  if (mm) {
    const ok = (mm.longe_mm || 0) <= 3;
    h += `<h4>Malha ${ok ? '✅' : '⚠️'}</h4><p class="hint">${nf(mm.pct, 2)}% dos triângulos originais ficaram idênticos. ` +
      `${mm.mudaram.toLocaleString('pt-BR')} mudaram, ${ok ? 'todos na borda dos cortes' : 'alguns longe dos cortes (até ' + nf(mm.longe_mm, 1) + ' mm)'}.</p>`;
  }
  h += '<h4>Peças</h4><ul class="checks">' + r.partes.map((p) =>
    `<li><span class="swatch" style="background:${S.palette[p.cor - 1] || '#ccc'}"></span> ${p.nome} (${p.tipo}, cor ${p.cor}): ${p.tamanho.map((v) => nf(v, 1)).join(' × ')} mm</li>`).join('') + '</ul>';
  if (r.exportado) {
    h += `<p class="hint">${r.arquivo3mf}: peças deitadas na posição de impressão, cada uma no seu filamento. ${r.montado}: montado, para conferir. ` +
      'pecas/: um STL por peça. LEIA.txt: relatório e montagem.</p>';
  }
  $('#split-report').innerHTML = h;
}

// project file: the options of each area travel with the project
function state() {
  if (!SP.used || !SP.keep) return null;
  const areas = Object.values(SP.keep).map((c) => {
    const o = {};
    ['_k', 'separar', 'tipo', 'profundidade', 'folga', 'suavizar', 'pino', 'pino_mm', 'incl_a', 'incl_b', 'corte', 'espessura'].forEach((k) => { if (c[k] !== undefined) o[k] = c[k]; });
    return o;
  });
  return areas.length ? { versao: 1, areas } : null;
}
function restore(st) {
  if (SP.on) close();
  SP.model = $('#drop-text').textContent;
  SP.keep = {};
  SP.used = false;
  if (st && Array.isArray(st.areas)) {
    st.areas.forEach((a) => { if (a._k) SP.keep[a._k] = Object.assign({}, DEF, a); });
    SP.used = st.areas.length > 0;
  }
  renderPlan();
}

window.flexiSplit = { SP, open, close, hiddenAreas, runPreview, applyResult, drawMarks, select, configs, forExport, renderPlan, state, restore };
