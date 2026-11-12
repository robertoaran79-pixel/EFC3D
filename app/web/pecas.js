// EFC3D: prévia única das peças (v1.9).
// Peças por cor e cortes livres (aba Cortes) aparecem juntos, como vão sair na exportação.
// Fica na barra de cima: Ver › Modelo | Prévia | Exportado, com um só controle "Afastar".
// Os módulos Separar e Corte livre chamam flexiPecas.run() e recebem o resultado em applyResult().
const F = window.flexi;
const { THREE, S, scene, api, post, setStatus, nf, solidMat, hexRGB, unb64, CSS2DObject } = F;
const $ = (s) => document.querySelector(s);

const TINTS = ['#d9622b', '#2b6fd9', '#2f8f3f', '#9b51c9', '#c9a227', '#1fa3a3', '#c94f7c'];
const PC = { on: false, parts: [], result: null, running: false, own: false, base: null };
const group = new THREE.Group(); group.visible = false; scene.add(group);

function buttons() {
  const b = $('#t-prevp');
  b.classList.toggle('on', PC.on);
  b.title = PC.parts.length ? 'Peças por cor e cortes livres juntos, como na exportação' : 'Calcula a prévia das peças por cor e dos cortes livres';
  $('#pc-gaprow').classList.toggle('hidden', !PC.on);
  ['#split-prev', '#fc-prev'].forEach((s) => { const x = $(s); if (x) x.disabled = PC.running; });
}

async function run() {
  if (PC.running) return;
  if (!S.base) { setStatus('Carregue um modelo primeiro.'); return; }
  const free = window.flexiFree;
  if (free && free.FC.marking) free.finishMark(true);
  let separar = null;
  try { separar = window.flexiSplit ? await window.flexiSplit.forExport() : null; } catch (e) { separar = null; }
  const livres = free ? free.forExport() : null;
  if (!separar && !livres) {
    setStatus('Nada para separar: marque áreas para separar por cor, crie um corte livre ou um corte plano (aba Cortes).');
    return;
  }
  PC.running = true; buttons();
  const t0 = performance.now();
  const poll = setInterval(async () => {
    try { const s = await api('/api/status'); if (s.progress) setStatus(`Separando as peças… ${s.progress} (${((performance.now() - t0) / 1000).toFixed(0)} s)`); } catch (e) { /* segue */ }
  }, 700);
  try {
    await F.syncPaintNow();
    setStatus('Separando as peças…');
    const conectores = window.flexiConectores ? window.flexiConectores.forExport() : [];
    const r = await post('/api/pieces/preview', { separar, livres, joints: S.joints.map(F.cleanJoint),
      clearance: parseFloat($('#clr').value) || 0.4, conectores });
    clearInterval(poll);
    PC.result = r;
    PC.owner = null;                                         // dono de cada triângulo: vem desta prévia
    PC.ownerParts = r.partes;
    if (window.flexiSplit && window.flexiSplit.applyResult) window.flexiSplit.applyResult(separar ? r : null);
    if (free && free.applyResult) free.applyResult(livres ? r : null);
    setStatus(`Prévia pronta; carregando ${r.partes.length} peça(s)…`);
    await loadParts(r.partes);
    show(true);
    applyHide();                                             // peças marcadas com 👁 continuam ocultas
    if (free && free.renderList) free.renderList();          // a linha do Corpo (👁) aparece na lista de cortes
    if (window.flexiConectores) await window.flexiConectores.afterPreview(r);   // juntas dos cortes com conector manual
    const bad = r.regioes.filter((x) => !x.ok).length + (r.livres || []).filter((x) => !x.ok).length;
    setStatus(`${r.partes.length} peça(s) em ${nf(r.segundos, 1)} s.` + (bad ? ` ${bad} corte(s) não feito(s): veja os itens vermelhos na aba Cortes.` : ' Confira e exporte na aba Exportar.'));
  } catch (e) {
    setStatus('Erro: ' + e.message);
  } finally { clearInterval(poll); PC.running = false; buttons(); }
}

function clearParts() {
  PC.parts.forEach((m) => { m.geometry.dispose(); if (m.userData.lab) m.userData.lab.element.remove(); });
  PC.parts = [];
  group.clear();
}
async function loadParts(list) {
  clearParts();
  PC.base = S.base;
  let tint = 0;
  for (const p of list) {
    const g = F.loader.parse(await api('/api/pieces/part.stl?i=' + p.i));
    g.computeVertexNormals();
    const n = g.attributes.position.count;
    const col = new Float32Array(n * 3);
    let paint = null, pal = S.palette;
    try { const r = await api('/api/pieces/part_paint?i=' + p.i); paint = unb64(r.pintura); if (r.paleta && r.paleta.length) pal = r.paleta; } catch (e) { /* sem pintura */ }
    const rgb = pal.map(hexRGB);
    const painted = paint && paint.length === n / 3 && paint.some((x) => x > 1);
    // peça sem pintura (corte livre num modelo de uma cor): tom próprio para ver onde termina
    const own = p.tipo === 'livre' && !painted ? hexRGB(TINTS[tint++ % TINTS.length]) : null;
    for (let t = 0; t < n / 3; t++) {
      const c = own || (painted ? (rgb[paint[t] - 1] || rgb[0]) : (rgb[(p.cor || 1) - 1] || rgb[0]));
      for (let k = 0; k < 3; k++) { col[(t * 3 + k) * 3] = c[0]; col[(t * 3 + k) * 3 + 1] = c[1]; col[(t * 3 + k) * 3 + 2] = c[2]; }
    }
    g.setAttribute('color', new THREE.BufferAttribute(col, 3));
    const m = new THREE.Mesh(g, solidMat({}));
    m.userData = { axis: p.eixo, tipo: p.tipo };
    g.computeBoundingBox();
    const div = document.createElement('div');
    div.className = 'fc-lbl';
    div.textContent = p.tipo === 'cavilha' ? 'Cavilha' : p.tipo === 'corpo' ? p.nome : p.rid !== null && p.rid !== undefined && p.tipo !== 'livre' && /^Cor \d+ · área \d+( \d+)?$/.test(p.nome || '') ? `Área ${p.rid + 1}` : p.nome;
    div.style.display = PC.on ? '' : 'none';
    const lab = new CSS2DObject(div);
    lab.position.copy(g.boundingBox.getCenter(new THREE.Vector3()));
    lab.position.z = g.boundingBox.max.z + 2;
    m.add(lab);
    m.userData.lab = lab;
    group.add(m);
    PC.parts.push(m);
  }
  explode();
}
function explode() {
  const d = parseFloat($('#pc-gap').value) || 0;
  let low = 0;
  // peças em cadeia (tronco, calça, sapato): quanto mais longe do corpo ao longo do eixo, mais a peça se
  // afasta. Assim cada nível da cadeia se separa do anterior, não só do corpo.
  const ctr = (m) => m.geometry.boundingBox.getCenter(new THREE.Vector3());
  const corpo = PC.parts.find((m) => m.userData.tipo === 'corpo');
  const c0 = corpo ? ctr(corpo) : null;
  const all = new THREE.Box3();
  PC.parts.forEach((m) => all.union(m.geometry.boundingBox));
  const L = Math.max(1, 0.15 * all.getSize(new THREE.Vector3()).length());
  const cm = all.getCenter(new THREE.Vector3());
  PC.parts.forEach((m) => {
    const a = m.userData.axis;
    let k = m.userData.tipo === 'cavilha' ? 1.6 : 1;
    if (a && c0) {
      const v = ctr(m).sub(c0);
      k *= 1 + Math.max(0, v.x * a[0] + v.y * a[1] + v.z * a[2]) / L;
    }
    if (a && m.userData.tipo !== 'corpo') {
      // eixo de pé (braço que entra na manga de cima para baixo): afasta também para o lado, para fora
      // do centro da figura, senão a peça desce colada ao tronco
      const c = ctr(m), up = Math.abs(a[2]) > 0.9;
      const hx = up ? (c.x - cm.x) / L * 0.6 * d : 0, hy = up ? (c.y - cm.y) / L * 0.6 * d : 0;
      m.position.set(a[0] * d * k + hx, a[1] * d * k + hy, a[2] * d * k);
    } else m.position.set(0, 0, 0);
    low = Math.min(low, m.geometry.boundingBox.min.z + m.position.z);
  });
  // uma peça que sai para baixo (uma perna) não entra na mesa: sobe tudo junto
  PC.parts.forEach((m) => { m.position.z -= low; });
}

function show(on) {
  on = !!on && PC.parts.length > 0;
  if (on) {
    if (S.painting) F.setPainting(false);
    const free = window.flexiFree;
    if (free && free.FC.marking) free.finishMark(false);
    if (S.showPieces) $('#t-orig').click();              // sai da vista Exportado
    if (!S.splitting) { S.splitting = true; PC.own = true; }   // bloqueia as juntas enquanto mostra
    PC.on = true;
    F.setView(false);
    if (S.base) S.base.visible = false;
    $('#t-orig').classList.remove('on');
  } else if (PC.on) {
    PC.on = false;
    if (PC.own) {
      PC.own = false;
      const sp = window.flexiSplit && window.flexiSplit.SP.on;
      const fc = window.flexiFree && window.flexiFree.FC.ownSplitting;
      if (!sp && !fc) S.splitting = false;
    }
    if (S.showPieces) F.setView(true);                     // a exportação abriu a vista Exportado: fica nela
    else { if (S.base) S.base.visible = true; F.setView(false); }
    if (F.renderJoints) F.renderJoints();
  }
  if (window.flexiSplit && window.flexiSplit.drawMarks) window.flexiSplit.drawMarks();
  group.visible = PC.on;
  group.traverse((o) => { if (o.element) o.element.style.display = PC.on ? '' : 'none'; });
  buttons();
}
// algo mudou (pintura, opções, cortes, juntas): a prévia não vale mais
function invalidate() {
  if (!PC.parts.length && !PC.result) return;
  const was = PC.on;
  show(false);
  if (window.flexiConectores) window.flexiConectores.clearMarkers();
  clearParts();
  PC.result = null;
  buttons();
  if (was) setStatus('As opções mudaram: clique em Ver › Prévia para refazer.');
}

$('#t-prevp').onclick = () => { if (PC.parts.length && PC.base === S.base) show(true); else run(); };
$('#t-orig').addEventListener('click', () => show(false), true);
$('#t-pieces').addEventListener('click', () => show(false), true);
$('#pc-gap').oninput = explode;
// pintar muda as peças: a prévia sai e precisa ser refeita
$('#btn-paint').addEventListener('click', () => invalidate(), true);
setInterval(() => {
  if (PC.on && S.showPieces) show(false);                  // a exportação abriu a vista Exportado
  if (PC.parts.length && PC.base !== S.base) invalidate();  // outro modelo
}, 600);
buttons();

// ---------------------------------------------------------------- ocultar peças já recortadas
// O 👁 de um corte livre (ou de uma área por cor) esconde a peça dele na vista, e o clique atravessa:
// dá para marcar ou pintar o que está por baixo (o pescoço debaixo do cabelo e do queixo). Só a vista
// muda; as linhas continuam na superfície original e a prévia e a exportação levam todas as peças.
// A peça de cada triângulo vem da última prévia e continua valendo depois que um corte novo é
// criado (a peça escondida não muda por isso); outro modelo zera tudo.
async function applyHide() {
  const free = window.flexiFree, sp = window.flexiSplit;
  const parts = PC.ownerParts;
  const hidCut = free && free.hiddenCuts ? free.hiddenCuts() : new Set();
  const hidReg = sp && sp.hiddenAreas ? sp.hiddenAreas() : new Set();
  const want = new Set();
  const hidBody = free && free.hiddenBody ? free.hiddenBody() : false;
  (parts || []).forEach((p) => {
    if (p.tipo === 'corpo') { if (hidBody) want.add(p.i); return; }
    if (p.livre !== null && p.livre !== undefined) { if (hidCut.has(p.livre)) want.add(p.i); }
    else if (p.rid !== null && p.rid !== undefined && hidReg.has(p.rid)) want.add(p.i);
  });
  // na vista da prévia: a própria peça some
  PC.parts.forEach((m, i) => { m.visible = !want.has(i); if (m.userData.lab) m.userData.lab.element.style.visibility = want.has(i) ? 'hidden' : ''; });
  if (!want.size || !S.base) { F.setBaseHidden(null); return 0; }
  if (!PC.owner || PC.ownerBase !== S.base) {
    try {
      const r = await api('/api/pieces/owner');
      PC.owner = new Int16Array(unb64(r.dono).buffer);
      PC.ownerBase = S.base;
    } catch (e) { setStatus('Para ocultar a peça, rode a prévia das peças antes (Ver › Prévia).'); return 0; }
  }
  const n = PC.owner.length, mask = new Uint8Array(n);
  let k = 0;
  for (let t = 0; t < n; t++) if (want.has(PC.owner[t])) { mask[t] = 1; k++; }
  F.setBaseHidden(k ? mask : null);
  return k;
}
function canHide() { return !!(PC.ownerParts && PC.ownerParts.length && PC.base === S.base); }
window.flexiPecas = { PC, run, show, invalidate, applyHide, canHide, active: () => PC.on };
