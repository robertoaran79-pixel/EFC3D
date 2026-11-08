// EFC3D: lista das áreas pintadas (v1.8). Cada área ligada de uma mesma cor vira um
// item: 👁 oculta a cor dela na tela (sem mudar a pintura) e ✕ devolve a área à cor base.
// ⌘Z traz de volta. Só lê e escreve a pintura pelo window.flexi.
const F = window.flexi;
const { THREE, S, scene, setStatus, nf } = F;
const $ = (s) => document.querySelector(s);
const UI = window.flexiUI;
const MAX = 40;                     // áreas listadas; as menores entram em "manchas"
const SPECK = 2.0;                  // mm²: abaixo disso é mancha

const A = { list: [], sel: -1, sig: '', area: null, hide: new Set() };
const outline = new THREE.LineSegments(new THREE.BufferGeometry(),
  new THREE.LineBasicMaterial({ color: 0xffffff, depthTest: false, transparent: true, opacity: 0.95 }));
outline.renderOrder = 27; outline.visible = false; scene.add(outline);

function sig() {                    // muda quando a pintura muda
  const p = S.paint;
  if (!p) return '';
  let h = p.length, n = 0;
  for (let i = 0; i < p.length; i += 1) { h = (h * 31 + p[i]) | 0; if (p[i] > 1) n++; }
  return h + ':' + n;
}
function triAreas() {
  if (A.area && A.area.length === F.tri().n) return A.area;
  const pos = S.base.geometry.attributes.position.array, n = F.tri().n, ar = new Float32Array(n);
  for (let t = 0; t < n; t++) {
    const o = t * 9;
    const ux = pos[o + 3] - pos[o], uy = pos[o + 4] - pos[o + 1], uz = pos[o + 5] - pos[o + 2];
    const vx = pos[o + 6] - pos[o], vy = pos[o + 7] - pos[o + 1], vz = pos[o + 8] - pos[o + 2];
    ar[t] = 0.5 * Math.hypot(uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx);
  }
  A.area = ar;
  return ar;
}
function adjQuiet() {
  const el = $('#status'), prev = el ? el.textContent : '';
  const a = F.adjacency();
  if (el && el.textContent !== prev) setStatus(prev);
  return a;
}
function compute() {
  const p = S.paint, n = F.tri().n, adj = adjQuiet(), ar = triAreas();
  const lab = new Int32Array(n).fill(-1), q = new Int32Array(n);
  const out = [];
  for (let s0 = 0; s0 < n; s0++) {
    if (p[s0] <= 1 || lab[s0] >= 0) continue;
    const id = out.length, col = p[s0];
    let qh = 0, qt = 0, area = 0;
    q[qt++] = s0; lab[s0] = id;
    while (qh < qt) {
      const t = q[qh++];
      area += ar[t];
      for (let k = 0; k < 3; k++) { const u = adj[t * 3 + k]; if (u >= 0 && lab[u] < 0 && p[u] === col) { lab[u] = id; q[qt++] = u; } }
    }
    out.push({ cor: col, area, tris: Int32Array.from(q.subarray(0, qt)) });
  }
  out.sort((a, b) => b.area - a.area);
  return out;
}
function refresh(force) {
  if (!S.base || !S.paint || !F.tri()) { $('#area-box').classList.add('hidden'); return; }
  if (A.n !== F.tri().n) { A.n = F.tri().n; A.hide.clear(); A.sel = -1; A.area = null; S.paintHide = null; outline.visible = false; }
  const g = sig();
  if (!force && g === A.sig) return;
  A.sig = g;
  A.list = compute();
  if (A.sel >= A.list.length) A.sel = -1;
  render();
}
function render() {
  const box = $('#area-box'), ol = $('#area-list');
  const big = A.list.filter((x) => x.area >= SPECK);
  const specks = A.list.filter((x) => x.area < SPECK);
  box.classList.toggle('hidden', !A.list.length);
  ol.innerHTML = '';
  big.slice(0, MAX).forEach((x) => {
    const k = A.list.indexOf(x);
    ol.appendChild(UI.row({
      list: 'areas', cor: S.palette[x.cor - 1] || '#ccc', tag: `Área ${k + 1}`, meta: `Cor ${x.cor} · ${nf(x.area, 0)} mm²`,
      selected: k === A.sel, hidden: A.hide.has(key(x)),
      onSelect: () => select(k), onToggle: () => toggle(x), onDelete: () => remove(x, `Área ${k + 1}`), delTitle: 'Apagar a pintura desta área (Delete)',
    }));
  });
  const extra = big.length > MAX ? big.length - MAX : 0;
  const more = $('#area-more');
  more.innerHTML = '';
  if (extra || specks.length) {
    more.textContent = (extra ? `+${extra} área(s) menores não listadas. ` : '') + (specks.length ? `${specks.length} mancha(s) com menos de ${nf(SPECK, 0)} mm². ` : '');
    if (specks.length) {
      const b = document.createElement('button');
      b.className = 'btn'; b.textContent = 'Apagar as manchas';
      b.onclick = () => removeMany(specks, `${specks.length} mancha(s)`);
      more.appendChild(b);
    }
  }
}
const key = (x) => `${x.cor}:${x.tris[0]}`;
function select(k) {
  A.sel = k;
  const x = A.list[k];
  render();
  if (!x) { outline.visible = false; return; }
  const pos = S.base.geometry.attributes.position.array, N = F.tri().nrm, adj = adjQuiet();
  const inA = new Uint8Array(F.tri().n);
  x.tris.forEach((t) => { inA[t] = 1; });
  const seg = [];
  x.tris.forEach((t) => {
    for (let j = 0; j < 3; j++) {
      const u = adj[t * 3 + j];
      if (u >= 0 && inA[u]) continue;
      const a = t * 9 + j * 3, b = t * 9 + ((j + 1) % 3) * 3, l = 0.06;
      seg.push(pos[a] + N[t * 3] * l, pos[a + 1] + N[t * 3 + 1] * l, pos[a + 2] + N[t * 3 + 2] * l, pos[b] + N[t * 3] * l, pos[b + 1] + N[t * 3 + 1] * l, pos[b + 2] + N[t * 3 + 2] * l);
    }
  });
  outline.geometry.dispose();
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(seg, 3));
  outline.geometry = g;
  outline.visible = true;
  setStatus(`Área ${k + 1}: cor ${x.cor}, ${nf(x.area, 0)} mm². 👁 oculta a cor na tela; ✕ ou Delete apaga a pintura dela (⌘Z traz de volta).`);
}
function applyHide() {
  const n = F.tri().n;
  if (!A.hide.size) { S.paintHide = null; F.baseColorize(); return; }
  const m = new Uint8Array(n);
  A.list.forEach((x) => { if (A.hide.has(key(x))) x.tris.forEach((t) => { m[t] = 1; }); });
  S.paintHide = m;
  F.baseColorize();
}
function toggle(x) {
  const k = key(x);
  if (A.hide.has(k)) A.hide.delete(k); else A.hide.add(k);
  applyHide();
  render();
}
function removeMany(items, label) {
  const p = S.paint;
  if (S.painting && F.pushPaintUndo) F.pushPaintUndo();
  const saved = items.map((x) => ({ tris: x.tris, cor: x.cor }));
  const changed = [];
  items.forEach((x) => { x.tris.forEach((t) => { p[t] = 1; changed.push(t); }); A.hide.delete(key(x)); });
  UI.push(label, () => {
    const back = [];
    saved.forEach((x) => x.tris.forEach((t) => { S.paint[t] = x.cor; back.push(t); }));
    F.baseColorize(back); F.syncPaint(); refresh(true);
  });
  applyHide();
  F.baseColorize(changed);
  F.syncPaint();
  A.sel = -1; outline.visible = false;
  refresh(true);
  setStatus(`${label}: pintura apagada (volta à cor base). ⌘Z traz de volta.`);
}
function remove(x, label) { removeMany([x], label); }
function deleteSelected() { const x = A.list[A.sel]; if (x) remove(x, `Área ${A.sel + 1}`); }
// Delete apaga a área selecionada quando esta lista foi a última usada
document.addEventListener('click', (e) => { if (e.target.closest && e.target.closest('#area-list')) UI.setActive('areas', deleteSelected); }, true);
setInterval(() => refresh(false), 1200);
window.flexiAreas = { refresh, A };
