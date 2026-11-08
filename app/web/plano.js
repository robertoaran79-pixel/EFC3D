// EFC3D: corte plano (v1.23), como no OrcaSlicer e no Bambu Studio.
// Um plano com altura e inclinação em qualquer direção atravessa tudo o que cruza e divide em
// duas partes com faces planas. Fica numa seção própria, separada do Corte livre (que só corta
// a parte indicada). Os planos vão para o servidor junto com os cortes livres, depois deles.
import { TransformControls } from 'three/addons/controls/TransformControls.js';

const F = window.flexi;
const { THREE, S, scene, camera, renderer, controls, setStatus, nf } = F;
const $ = (s) => document.querySelector(s);
const LUZ = { ok: '🟢', aviso: '🟡', erro: '🔴', nada: '⚪' };
const CON = {
  nenhum: 'Nenhum: faces planas para colar',
  losango: 'Pino fixo (losango) na parte de baixo',
  peca: 'Pino fixo na parte de cima',
  trava: 'Trava de pressão: encaixa sem cola',
  cavilha: 'Cavilha solta (pino à parte, furo nos dois lados)',
};
const CON_CURTO = { nenhum: 'colar', losango: 'pino em baixo', peca: 'pino em cima', trava: 'trava', cavilha: 'cavilha' };
const ALVO = { tudo: 'Todas as peças que o plano atravessa', corpo: 'Só o corpo (não corta peças já separadas)', peca: 'Só a peça onde está o centro do plano' };
const PL = { planes: [], sel: -1, nextId: 1, editing: false, mode: 'translate', result: null };
const DEF = { alvo: 'tudo', conector: 'nenhum', pino_mm: 0, folga_pino: 0.4 };

// ---------------------------------------------------------------- vista 3D
const group = new THREE.Group();
group.visible = false;
scene.add(group);
const contour = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: 0x1f4fa3, depthTest: false }));
contour.renderOrder = 10;
scene.add(contour);
const gz = new TransformControls(camera, renderer.domElement);
gz.setSpace('local');
gz.setSize(1.2);
scene.add(gz.getHelper());
for (const grp of [gz._gizmo.picker.rotate, gz._gizmo.gizmo.rotate]) {
  grp.children.filter((c) => c.name === 'E' || c.name === 'XYZE').forEach((c) => grp.remove(c));
}
gz.addEventListener('dragging-changed', (e) => { controls.enabled = !e.value; if (!e.value) { renderList(); invalidate(); } });
gz.addEventListener('objectChange', () => {
  const p = PL.planes[PL.sel];
  const o = gz.object;
  if (!p || !o) return;
  p.p = [o.position.x, o.position.y, o.position.z].map((v) => +v.toFixed(2));
  const eu = new THREE.Euler().setFromQuaternion(o.quaternion, 'XYZ');
  p.rot = [eu.x, eu.y, eu.z].map((v) => +THREE.MathUtils.radToDeg(v).toFixed(1));
  refreshFields(p);
  requestContour();
});

function modelBox() {
  if (!S.base) return null;
  return new THREE.Box3().setFromObject(S.base);
}
function normalOf(p) {
  const q = new THREE.Quaternion().setFromEuler(new THREE.Euler(...p.rot.map((d) => THREE.MathUtils.degToRad(d)), 'XYZ'));
  return new THREE.Vector3(0, 0, 1).applyQuaternion(q).normalize();
}
function planeObject(p, size, selected) {
  const g = new THREE.Group();
  g.position.set(...p.p);
  g.quaternion.setFromEuler(new THREE.Euler(...p.rot.map((d) => THREE.MathUtils.degToRad(d)), 'XYZ'));
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(size, size),
    new THREE.MeshBasicMaterial({ color: selected ? 0xd9622b : 0x8a8478, transparent: true, opacity: selected ? 0.22 : 0.12,
      side: THREE.DoubleSide, depthWrite: false }));
  g.add(quad);
  const h = size / 2;
  const edge = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-h, -h, 0), new THREE.Vector3(h, -h, 0), new THREE.Vector3(h, h, 0), new THREE.Vector3(-h, h, 0)]),
  new THREE.LineBasicMaterial({ color: selected ? 0xd9622b : 0x8a8478 }));
  g.add(edge);
  // seta da parte de cima (o lado da normal), com rótulo: não depende só da cor
  g.add(new THREE.ArrowHelper(new THREE.Vector3(0, 0, 1), new THREE.Vector3(0, 0, 0), size * 0.18, selected ? 0xd9622b : 0x8a8478));
  const div = document.createElement('div');
  div.className = 'fc-lbl';
  div.textContent = `▲ cima · ${p.nome}`;
  const lab = new F.CSS2DObject(div);
  lab.position.set(0, 0, size * 0.2);
  g.add(lab);
  g.userData.plane = p;
  return g;
}
function clearGroup() {
  group.traverse((o) => { if (o.element) o.element.remove(); });
  F.disposeTree ? F.disposeTree(group) : null;
  group.clear();
}
let planeObjs = [];
function draw() {
  clearGroup();
  planeObjs = [];
  const box = modelBox();
  if (!box || !PL.planes.length) { group.visible = false; gz.detach(); setContour(null); return; }
  const size = box.getSize(new THREE.Vector3()).length() * 0.85;
  PL.planes.forEach((p, k) => {
    if (p.oculto) { planeObjs.push(null); return; }
    const o = planeObject(p, size, k === PL.sel);
    planeObjs.push(o);
    group.add(o);
  });
  group.visible = open();
  const cur = planeObjs[PL.sel];
  if (PL.editing && cur && open()) {
    gz.attach(cur);
    gz.setMode(PL.mode);
    // mover só na direção da normal (a altura), como no fatiador
    gz.showX = PL.mode !== 'translate';
    gz.showY = PL.mode !== 'translate';
    gz.showZ = true;
  } else gz.detach();
  requestContour();
}
function open() {
  const sec = $('#s-plane');
  return !!(sec && PL.planes.length && !sec.classList.contains('collapsed')) && !(window.flexiPecas && window.flexiPecas.active()) && !S.showPieces;
}

// contorno do corte sobre o modelo (onde o plano encontra a superfície)
let ctFrame = 0;
function requestContour() {
  if (ctFrame) return;
  ctFrame = requestAnimationFrame(() => { ctFrame = 0; updateContour(); });
}
function setContour(arr) {
  contour.geometry.dispose();
  contour.geometry = new THREE.BufferGeometry();
  if (arr && arr.length) contour.geometry.setAttribute('position', new THREE.BufferAttribute(arr, 3));
  contour.visible = !!(arr && arr.length);
}
function updateContour() {
  const p = PL.planes[PL.sel];
  if (!p || !S.base || !open() || p.oculto) { setContour(null); return; }
  const pos = S.base.geometry.attributes.position;
  const idx = S.base.geometry.index;
  const n = normalOf(p);
  const d0 = n.x * p.p[0] + n.y * p.p[1] + n.z * p.p[2];
  const a = pos.array;
  const m = S.base.matrixWorld;
  const ident = m.equals(new THREE.Matrix4());
  const v = new THREE.Vector3();
  const nv = pos.count;
  const dist = new Float32Array(nv);
  const W = new Float32Array(nv * 3);
  for (let i = 0; i < nv; i++) {
    v.set(a[i * 3], a[i * 3 + 1], a[i * 3 + 2]);
    if (!ident) v.applyMatrix4(m);
    W[i * 3] = v.x; W[i * 3 + 1] = v.y; W[i * 3 + 2] = v.z;
    dist[i] = n.x * v.x + n.y * v.y + n.z * v.z - d0;
  }
  const out = [];
  const nt = idx ? idx.count / 3 : nv / 3;
  for (let t = 0; t < nt; t++) {
    const ia = idx ? idx.getX(t * 3) : t * 3, ib = idx ? idx.getX(t * 3 + 1) : t * 3 + 1, ic = idx ? idx.getX(t * 3 + 2) : t * 3 + 2;
    const tri = [ia, ib, ic];
    const pts = [];
    for (let e = 0; e < 3; e++) {
      const i = tri[e], j = tri[(e + 1) % 3];
      const di = dist[i], dj = dist[j];
      if ((di < 0) !== (dj < 0)) {
        const s = di / (di - dj);
        pts.push(W[i * 3] + s * (W[j * 3] - W[i * 3]), W[i * 3 + 1] + s * (W[j * 3 + 1] - W[i * 3 + 1]), W[i * 3 + 2] + s * (W[j * 3 + 2] - W[i * 3 + 2]));
      }
    }
    if (pts.length === 6) out.push(...pts);
  }
  setContour(new Float32Array(out));
}

// ---------------------------------------------------------------- lista e painel
function newPlane() {
  if (!S.base) { setStatus('Carregue um modelo primeiro.'); return; }
  const box = modelBox();
  const c = box.getCenter(new THREE.Vector3());
  const p = Object.assign({}, DEF, { id: PL.nextId, nome: `Plano ${PL.nextId}`, p: [+c.x.toFixed(2), +c.y.toFixed(2), +c.z.toFixed(2)], rot: [0, 0, 0], luz: 'nada', checks: null });
  PL.nextId++;
  PL.planes.push(p);
  PL.sel = PL.planes.length - 1;
  PL.editing = true;
  PL.mode = 'translate';
  takeOver(true);
  invalidate();
  renderList();
  setStatus('Arraste a seta para mudar a altura do plano, ou use os campos. "Girar" inclina o plano em qualquer direção.');
}
function renderList(edit = true) {
  const ol = $('#pl-list');
  ol.innerHTML = '';
  PL.planes.forEach((p, k) => {
    const n = normalOf(p);
    const ang = THREE.MathUtils.radToDeg(Math.acos(Math.min(1, Math.abs(n.z))));
    ol.append(window.flexiUI.row({ list: 'planos', luz: LUZ[p.luz || 'nada'], tag: `P${k + 1}`,
      meta: `${p.nome} · altura ${nf(p.p[2], 1)} mm · ${nf(ang, 0)}° · ${CON_CURTO[p.conector]}`,
      selected: k === PL.sel, hidden: !!p.oculto,
      onSelect: () => select(k), onDelete: () => removePlane(k), delTitle: 'Excluir este plano (Delete)',
      onToggle: () => { p.oculto = !p.oculto; invalidate(); renderList(); } }));
  });
  $('#pl-actions').classList.toggle('hidden', !PL.planes.length);
  if (edit) renderEdit();
  draw();
}
function select(k) {
  PL.sel = k;
  PL.editing = true;
  takeOver(true);
  renderList();
}
function removePlane(k) {
  const gone = PL.planes[k];
  if (gone) window.flexiUI.push(`Plano P${k + 1}`, () => { PL.planes.splice(Math.min(k, PL.planes.length), 0, gone); PL.sel = k; invalidate(); renderList(); });
  PL.planes.splice(k, 1);
  if (PL.sel >= PL.planes.length) PL.sel = PL.planes.length - 1;
  if (!PL.planes.length) { PL.editing = false; takeOver(false); }
  invalidate();
  renderList();
  setStatus('Plano excluído. ⌘Z traz de volta.');
}
// enquanto edita um plano, as juntas não pegam cliques (como na marcação do corte livre)
let own = false;
function takeOver(on) {
  if (on && !own && !S.splitting) { S.splitting = true; own = true; if (F.gizmo) F.gizmo.detach(); }
  if (!on && own) {
    own = false;
    const sp = window.flexiSplit && window.flexiSplit.SP.on;
    const fc = window.flexiFree && window.flexiFree.FC.ownSplitting;
    if (!sp && !fc && !(window.flexiPecas && window.flexiPecas.active())) S.splitting = false;
    if (F.renderJoints) F.renderJoints();
  }
}
function finishEdit() {
  PL.editing = false;
  takeOver(false);
  renderList();
}
const fld = (k, label, step, v, min, max) => `<label>${label}<input type="number" data-f="${k}" step="${step}" value="${v}" ${min !== undefined ? `min="${min}"` : ''} ${max !== undefined ? `max="${max}"` : ''}></label>`;
function renderEdit() {
  const box = $('#pl-edit');
  const p = PL.planes[PL.sel];
  if (!p) { box.innerHTML = ''; return; }
  const pino = p.conector !== 'nenhum';
  box.innerHTML = `<div class="card">
    <label>Nome<input type="text" data-k="nome" value=""></label>
    <div class="seg" role="group" aria-label="Como mexer o plano">
      <button data-mode="translate" class="${PL.editing && PL.mode === 'translate' ? 'on' : ''}" title="Arraste a seta para subir ou descer o plano">↕ Altura</button>
      <button data-mode="rotate" class="${PL.editing && PL.mode === 'rotate' ? 'on' : ''}" title="Arraste os anéis para inclinar o plano">⟳ Girar</button>
      <button data-act="done" title="Esconde as setas">✓ Pronto</button>
    </div>
    <div class="grid2">
      ${fld('pz', 'Altura do centro (mm)', 0.1, p.p[2])}
      ${fld('dn', 'Mover na normal (mm)', 0.1, 0)}
      ${fld('px', 'Centro X (mm)', 0.1, p.p[0])}
      ${fld('py', 'Centro Y (mm)', 0.1, p.p[1])}
      ${fld('rx', 'Inclinação em X (°)', 1, p.rot[0], -180, 180)}
      ${fld('ry', 'Inclinação em Y (°)', 1, p.rot[1], -180, 180)}
    </div>
    <div class="row">
      <button class="btn" data-preset="0,0">Deitado (0°)</button>
      <button class="btn" data-preset="90,0">De pé (frente)</button>
      <button class="btn" data-preset="0,90">De pé (lado)</button>
      <button class="btn" data-act="flip" title="Troca qual lado é a parte de cima">⇅ Inverter</button>
    </div>
    <label>Cortar<select data-k="alvo">${Object.entries(ALVO).map(([k, t]) => `<option value="${k}" ${p.alvo === k ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
    ${p.alvo === 'peca' ? '<p class="hint">Leve o centro do plano para dentro da parte que quer cortar (o pescoço, por exemplo): só essa peça é cortada, as outras ficam inteiras. Funciona também numa peça que já saiu de um corte. Para uma peça entre duas (o pescoço entre a cabeça e o tronco), use dois planos.</p>' : ''}
    <label>Conector<select data-k="conector">${Object.entries(CON).map(([k, t]) => `<option value="${k}" ${p.conector === k ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
    ${pino ? `<div class="grid2">
      <label>Folga do pino (mm)<input type="number" data-k="folga_pino" min="0.05" max="1" step="0.05" value="${p.folga_pino}"></label>
      <label>Largura do pino (mm)<input type="number" data-k="pino_mm" min="1.2" step="0.1" value="${p.pino_mm || ''}" placeholder="automática"></label>
    </div><p class="hint">Um conector no meio de cada parte cortada (no ponto mais longe das bordas). Seção pequena demais fica sem conector, e o relatório avisa.</p>` : ''}
    <p class="hint">A linha azul no modelo mostra onde o plano corta. A seta ▲ aponta a parte de cima. As faces do corte saem planas e encostadas, e cada uma vai para a mesa na impressão.</p>
    ${p.checks ? '<ul class="checks">' + p.checks.map((x) => `<li class="${x.nivel}">${LUZ[x.nivel] || ''} ${x.texto}</li>`).join('') + '</ul>' : ''}
  </div>`;
  box.querySelector('[data-k="nome"]').value = p.nome;
  box.querySelectorAll('[data-k]').forEach((el) => {
    el.onchange = () => {
      const k = el.dataset.k;
      let v = el.value;
      if (el.type === 'number') v = parseFloat(v) || (k === 'pino_mm' ? 0 : DEF[k]);
      p[k] = v;
      if (k !== 'nome') invalidate();
      // o painel muda (campos do pino) só depois do evento: refazer agora tira o campo da tela no meio dele
      if (el.tagName === 'SELECT') setTimeout(() => renderList(), 0); else renderList(false);
    };
  });
  box.querySelectorAll('[data-f]').forEach((el) => {
    el.onchange = () => {
      const v = parseFloat(el.value);
      if (!isFinite(v)) return;
      const f = el.dataset.f;
      if (f === 'pz') p.p[2] = v;
      if (f === 'px') p.p[0] = v;
      if (f === 'py') p.p[1] = v;
      if (f === 'rx') p.rot[0] = v;
      if (f === 'ry') p.rot[1] = v;
      if (f === 'dn') { const n = normalOf(p); p.p = p.p.map((x, i) => +(x + n.getComponent(i) * v).toFixed(2)); el.value = 0; }
      invalidate();
      renderList(false);
      refreshFields(p);
    };
  });
  box.querySelectorAll('[data-mode]').forEach((b) => { b.onclick = () => { PL.mode = b.dataset.mode; PL.editing = true; takeOver(true); renderList(); }; });
  box.querySelectorAll('[data-preset]').forEach((b) => { b.onclick = () => { const [x, y] = b.dataset.preset.split(',').map(Number); p.rot = [x, y, 0]; invalidate(); renderList(); }; });
  box.querySelector('[data-act="done"]').onclick = () => finishEdit();
  box.querySelector('[data-act="flip"]').onclick = () => {
    // gira 180° em volta do X local: a mesma posição, normal ao contrário
    const q = new THREE.Quaternion().setFromEuler(new THREE.Euler(...p.rot.map((d) => THREE.MathUtils.degToRad(d)), 'XYZ'));
    q.multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), Math.PI));
    const eu = new THREE.Euler().setFromQuaternion(q, 'XYZ');
    p.rot = [eu.x, eu.y, eu.z].map((r) => +THREE.MathUtils.radToDeg(r).toFixed(1));
    invalidate(); renderList();
  };
}
function refreshFields(p) {
  const box = $('#pl-edit');
  const set = (f, v) => { const el = box.querySelector(`[data-f="${f}"]`); if (el && document.activeElement !== el) el.value = v; };
  set('pz', p.p[2]); set('px', p.p[0]); set('py', p.p[1]); set('rx', p.rot[0]); set('ry', p.rot[1]);
}
function invalidate() {
  PL.result = null;
  PL.planes.forEach((p) => { p.luz = 'nada'; p.checks = null; });
  $('#pl-report').innerHTML = '';
  if (window.flexiPecas) window.flexiPecas.invalidate();
}

// ---------------------------------------------------------------- servidor
function planeOut(p) {
  const n = normalOf(p);
  return { nome: p.nome, plano: { p: p.p.slice(), n: [n.x, n.y, n.z].map((v) => +v.toFixed(6)), rot: p.rot.slice() },
    alvo: p.alvo, conector: p.conector, pino_mm: p.pino_mm || 0, folga_pino: p.folga_pino };
}
function forExport() { const l = PL.planes.filter((p) => !p.oculto); return l.length ? l.map(planeOut) : null; }
function state() { return PL.planes.length ? PL.planes.map((p) => Object.assign(planeOut(p), { oculto: !!p.oculto })) : null; }
function restore(list) {
  PL.planes = []; PL.sel = -1; PL.nextId = 1; PL.editing = false; PL.result = null;
  (Array.isArray(list) ? list : []).forEach((q) => {
    if (!q || !q.plano) return;
    PL.planes.push(Object.assign({}, DEF, q, { id: PL.nextId++, p: (q.plano.p || [0, 0, 0]).slice(), rot: (q.plano.rot || [0, 0, 0]).slice(),
      luz: 'nada', checks: null, oculto: !!q.oculto }));
  });
  PL.sel = PL.planes.length ? 0 : -1;
  takeOver(false);
  $('#pl-report').innerHTML = '';
  renderList();
}
function applyResult(r, nFree) {
  PL.result = r;
  const used = PL.planes.filter((p) => !p.oculto);
  if (!r) { $('#pl-report').innerHTML = ''; renderList(); return; }
  (r.livres || []).filter((x) => x.plano).forEach((x) => {
    const p = used[x.i - nFree];
    if (p) { p.luz = x.luz; p.checks = x.checks; x.k = PL.planes.indexOf(p); }
  });
  const items = (r.livres || []).filter((x) => x.plano);
  $('#pl-report').innerHTML = items.length ? '<ul class="checks">' + items.map((x) => {
    const prob = x.checks.filter((c) => c.nivel !== 'ok').map((c) => c.texto).join(' ');
    const ok = x.checks.filter((c) => c.nivel === 'ok').map((c) => c.texto).join(' ');
    return `<li class="${x.luz}">${LUZ[x.luz]} <b>P${(x.k ?? 0) + 1} ${x.nome}</b>: ${x.ok ? ok : 'não cortado'}${prob ? ' ' + prob : ''}</li>`;
  }).join('') + '</ul>' : '';
  renderList();
}

// os planos vão junto com os cortes livres (depois deles): o servidor corta na ordem
function hook() {
  const free = window.flexiFree;
  if (!free || free._plano) return;
  free._plano = true;
  const fe = free.forExport, st = free.state, rs = free.restore, ar = free.applyResult;
  free.forExport = () => {
    const a = fe() || [];
    const b = forExport() || [];
    return a.length || b.length ? a.concat(b) : null;
  };
  free.state = () => {
    const s = st() || (PL.planes.length ? { versao: 2, cortes: [] } : null);
    if (s) s.planos = state();
    return s;
  };
  free.restore = (s) => { rs(s); restore(s && s.planos); };
  free.applyResult = (r) => { ar(r); applyResult(r, (fe() || []).length); };
}
hook();

$('#pl-new').onclick = () => newPlane();
$('#pl-prev').onclick = () => { finishEdit(); if (window.flexiPecas) window.flexiPecas.run(); };
setInterval(() => {               // a seção fechada, a prévia aberta ou outro modelo: esconde o plano
  const vis = open();
  if (group.visible !== vis) { group.visible = vis; if (!vis) gz.detach(); else draw(); requestContour(); }
}, 400);
function remap(mapa) {
  PL.planes.forEach((p) => { p.p = p.p.map((v, i) => +(mapa.s * v + mapa.t[i]).toFixed(2)); });
  invalidate();
  renderList();
}
window.flexiPlano = { PL, newPlane, forExport, state, restore, applyResult, draw, finishEdit, normalOf, remap };
renderList();
