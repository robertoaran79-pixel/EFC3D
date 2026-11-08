// EFC3D: corte numa peça já recortada (1.37, refeito na 1.38).
// Depois do corte do cabelo, a nuca só existe como face do corte da peça: no modelo original ela não
// existe (cabelo e nuca eram uma malha só). Este módulo só faz duas coisas:
//   1. escolher a peça na prévia (clique sobre ela);
//   2. buscar no servidor a malha dessa peça como ela está antes do corte (hostGeometry), a mesma
//      malha que o corte vai usar.
// A marcação é a do Corte livre, sem nada à parte: Linha, Pincel, Balde, Borracha, desfazer, encaixe e
// pino funcionam igual, só que sobre a peça (freecut.js troca a superfície, surface.js).
const F = window.flexi;
const { THREE, S, host, camera, controls, api, post, setStatus } = F;
const $ = (s) => document.querySelector(s);

const PM = { pick: false };
const ray = new THREE.Raycaster();

// ---------------------------------------------------------------- malha da peça (servidor)
async function hostGeometry(k) {
  const free = window.flexiFree;
  const c = free.FC.cuts[k];
  let separar = null;
  try { separar = window.flexiSplit ? await window.flexiSplit.forExport() : null; } catch (e) { separar = null; }
  await post('/api/pieces/host', { separar, livres: free.exportBefore(k), ponto: c.peca.ponto });
  const buf = await api('/api/pieces/host.stl');
  const geo = F.loader.parse(buf);
  geo.computeVertexNormals();
  return geo;
}

// ---------------------------------------------------------------- escolher a peça
function mouse(on) {
  controls.mouseButtons.LEFT = on ? -1 : THREE.MOUSE.ROTATE;
  controls.mouseButtons.RIGHT = on ? THREE.MOUSE.ROTATE : THREE.MOUSE.PAN;
  // o clique deste modo não chega ao OrbitControls: se um giro estava em andamento, ele ficaria preso
  // seguindo o mouse. Zera o estado do giro.
  controls.state = -1;
  if (Array.isArray(controls._pointers)) controls._pointers.length = 0;
}
// o pointerup da escolha para aqui; o OrbitControls precisa saber que o botão foi solto
function releaseOrbit(e) {
  if (Array.isArray(controls._pointers) && controls._pointers.includes(e.pointerId) && controls._onPointerUp) controls._onPointerUp(e);
}
function card(on) {
  $('#pm-card').classList.toggle('hidden', !on);
  $('#fc-new').classList.toggle('hidden', on);
  $('#pm-new').classList.toggle('hidden', on);
  if (on && window.flexiShell) window.flexiShell.reveal($('#pm-card'));
}
function cancelPick(msg) {
  if (!PM.pick) return;
  PM.pick = false;
  F.renderer.domElement.style.cursor = '';
  mouse(false);
  card(false);
  if (msg !== false) setStatus(msg || 'Escolha da peça cancelada.');
}
async function startNew() {
  const free = window.flexiFree, P = window.flexiPecas;
  if (!S.base) { setStatus('Carregue um modelo primeiro.'); return; }
  if (free.FC.marking) free.finishMark(true);
  if (!(P.PC.parts.length && P.PC.base === S.base)) {
    setStatus('Calculando a prévia para escolher a peça…');
    await P.run();
    if (!P.PC.parts.length) return;
  } else if (!P.active()) P.show(true);
  PM.pick = true;
  mouse(true);                                           // o clique escolhe a peça; o botão direito gira
  card(true);
  setStatus('Clique na peça que quer cortar (por exemplo, a cabeça com o pescoço depois do corte do cabelo). Esc cancela.');
}
function pickAt(e) {
  const P = window.flexiPecas;
  ray.setFromCamera(F.ndc(e), camera);
  const h = ray.intersectObjects(P.PC.parts.filter((m) => m.visible), false)[0];
  if (!h) { setStatus('Clique sobre uma peça (Esc cancela).'); return; }
  const m = h.object, i = P.PC.parts.indexOf(m);
  const part = (P.PC.result && P.PC.result.partes || [])[i] || {};
  const n = h.face ? h.face.normal.clone() : new THREE.Vector3();
  const ponto = h.point.clone().sub(m.position).addScaledVector(n, -0.25);   // logo abaixo da superfície, dentro da peça
  cancelPick(false);
  const free = window.flexiFree;
  const k = free.addPieceCut({ ponto: [ponto.x, ponto.y, ponto.z].map((x) => +x.toFixed(3)), nome: part.nome || '' });
  free.startMark(k);                                     // a marcação de sempre, sobre a peça
}

let down = null;
host.addEventListener('pointerdown', (e) => {
  if (!PM.pick || e.button !== 0) return;
  down = [e.clientX, e.clientY];
}, true);
host.addEventListener('pointerup', (e) => {
  if (!PM.pick || e.button !== 0 || !down) return;
  const [x, y] = down;
  down = null;
  if (Math.hypot(e.clientX - x, e.clientY - y) > 4) return;
  e.stopPropagation();
  releaseOrbit(e);
  pickAt(e);
}, true);
host.addEventListener('pointermove', (e) => {
  if (!PM.pick || e.buttons) return;
  const P = window.flexiPecas;
  ray.setFromCamera(F.ndc(e), camera);
  F.renderer.domElement.style.cursor = ray.intersectObjects(P.PC.parts.filter((m) => m.visible), false).length ? 'pointer' : '';
}, true);
host.addEventListener('click', (e) => { if (PM.pick) e.stopPropagation(); }, true);
window.addEventListener('keydown', (e) => {
  if (!PM.pick || e.key !== 'Escape') return;
  if (document.activeElement && ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return;
  cancelPick();
}, true);
$('#pm-new').onclick = () => startNew();
$('#pm-cancel').onclick = () => cancelPick();
// a prévia fechou (outra aba, outro modelo): a escolha acaba
setInterval(() => {
  if (PM.pick && (!S.base || S.showPieces || !(window.flexiPecas && window.flexiPecas.active()))) cancelPick('Escolha da peça cancelada (a prévia foi fechada).');
}, 500);

window.flexiPecaCorte = { PM, startNew, hostGeometry, cancelPick, edit: (k) => window.flexiFree.startMark(k), active: () => PM.pick };
