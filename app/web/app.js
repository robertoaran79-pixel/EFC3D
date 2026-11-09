// EFC3D (Easy Flexy and Cuts 3D): joint editor.
// Every joint is a proven cutter from the library, placed by you: position, rotation on three
// axes, scale per axis (locked or free), side limits that trim only the plate, and "cut inside
// the border". Each joint is checked in seconds with a traffic light; export cuts everything and
// runs the mesh quality tests.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TransformControls } from 'three/addons/controls/TransformControls.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';
import { initPrompts } from './prompts.js?v=1.0';
import { computeBoundsTree, disposeBoundsTree, acceleratedRaycast } from './vendor/bvh/three-mesh-bvh.module.js';
// Clique, caneta e pincel acham o ponto do modelo por uma árvore de caixas (BVH) em vez de testar os 130 mil
// triângulos a cada movimento. "indirect" mantém a ordem dos triângulos: faceIndex continua o mesmo de antes.
THREE.BufferGeometry.prototype.computeBoundsTree = computeBoundsTree;
THREE.BufferGeometry.prototype.disposeBoundsTree = disposeBoundsTree;
THREE.Mesh.prototype.raycast = acceleratedRaycast;
const comBVH = (g) => { try { g.computeBoundsTree({ indirect: true }); } catch (e) { /* sem a árvore o teste é o comum */ } return g; };

const $ = (s) => document.querySelector(s);
const statusEl = $('#status');
const setStatus = (t) => { statusEl.textContent = t; };
const nf = (v, d = 2) => (+v).toFixed(d).replace('.', ',');

// ---------------------------------------------------------------- scene
const host = $('#canvas');
// Placa de vídeo: sem ela (driver ausente, área de trabalho remota, máquina virtual, WebView2 que recusou a GPU) o
// navegador desenha o 3D no processador e tudo fica lento. Nesse caso o app desenha mais leve e avisa.
const GPU = (() => {
  let nome = '';
  try {
    const g = document.createElement('canvas').getContext('webgl2') || document.createElement('canvas').getContext('webgl');
    const e = g && g.getExtension('WEBGL_debug_renderer_info');
    nome = g ? String(e ? g.getParameter(e.UNMASKED_RENDERER_WEBGL) : g.getParameter(g.RENDERER)) : '';
    const lose = g && g.getExtension('WEBGL_lose_context'); if (lose) lose.loseContext();
  } catch (err) { /* sem WebGL */ }
  return { nome, soft: /swiftshader|basic render|llvmpipe|softpipe|software|warp/i.test(nome) };
})();
const renderer = new THREE.WebGLRenderer({ antialias: !GPU.soft, powerPreference: 'high-performance' });
renderer.debug.checkShaderErrors = false;   // a checagem trava o desenho a cada shader novo (no Windows, muito)
const DPR = () => Math.min(window.devicePixelRatio || 1, GPU.soft ? 1 : 2);
renderer.setPixelRatio(DPR());
const VIEW = { dirty: true, ativo: 0, escala: 1, medio: 16, ultimo: 0, desenhado: 0, sig: '', nitido: true };
renderer.localClippingEnabled = true;
host.appendChild(renderer.domElement);
const labelR = new CSS2DRenderer();
labelR.domElement.style.position = 'absolute';
labelR.domElement.style.top = '0';
labelR.domElement.style.pointerEvents = 'none';
host.appendChild(labelR.domElement);
if (GPU.soft) {                          // aviso fixo no canto da vista: ícone e texto, não só cor
  const av = document.createElement('button');
  av.id = 'gpu-aviso'; av.className = 'gpu-aviso';
  av.textContent = '⚠ 3D sem placa de vídeo';
  av.title = 'O 3D está sendo desenhado pelo processador, por isso girar e pintar ficam lentos. Clique para ver como resolver.';
  av.onclick = () => { if (window.flexiHelp) window.flexiHelp.open('desempenho'); };
  host.appendChild(av);
}

const scene = new THREE.Scene();
const sysDark = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
const isDark = () => { const t = document.documentElement.dataset.theme; return t === 'dark' || (t !== 'light' && !!(sysDark && sysDark.matches)); };
renderer.setClearColor(isDark() ? 0x121416 : 0xe9e7e1, 1);
const camera = new THREE.PerspectiveCamera(35, 1, 0.5, 5000);
camera.up.set(0, 0, 1);
camera.position.set(160, -220, 160);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.zoomToCursor = true;          // a roda aproxima onde o mouse está (pescoço, mão), não no centro do modelo
scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8478, 1.6));
const sun = new THREE.DirectionalLight(0xffffff, 1.6);
sun.position.set(120, -160, 260);
scene.add(sun);
let grid = null;
function makeGrid() {
  const vis = grid ? grid.visible : true;
  if (grid) { scene.remove(grid); grid.geometry.dispose(); }
  const d = isDark();
  grid = new THREE.GridHelper(300, 30, d ? 0x3a3f45 : 0xb8b2a6, d ? 0x26292d : 0xd6d1c7);
  grid.rotation.x = Math.PI / 2;
  grid.visible = vis;
  scene.add(grid);
}
makeGrid();

const gizmo = new TransformControls(camera, renderer.domElement);
gizmo.setSpace('local');
gizmo.setSize(0.6);
scene.add(gizmo.getHelper());
// rotation only by the three rings, like Bambu Studio: the free trackball and the outer screen
// ring would cover the cutter and steal the drag that moves it
for (const grp of [gizmo._gizmo.picker.rotate, gizmo._gizmo.gizmo.rotate]) {
  grp.children.filter((c) => c.name === 'E' || c.name === 'XYZE').forEach((c) => grp.remove(c));
}

function resize() {
  const w = host.clientWidth, h = host.clientHeight;
  renderer.setPixelRatio(DPR() * VIEW.escala); VIEW.dirty = true;
  renderer.setSize(w, h);
  labelR.setSize(w, h);
  camera.aspect = w / Math.max(h, 1);
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
resize();
// Desenho sob demanda e resolução que se adapta: parado, a cena só é redesenhada quando algo muda (e de tempos em
// tempos, para pegar o que chega do motor); navegando ou pintando, se o quadro passar de ~40 ms a resolução cai
// aos poucos até ficar fluido, e volta à nitidez total assim que o mouse para.
const redraw = () => { VIEW.dirty = true; };
['pointerdown', 'pointermove', 'wheel', 'keydown'].forEach((ev) => window.addEventListener(ev, () => { VIEW.ativo = performance.now(); }, { capture: true, passive: true }));
function setEscala(k) {
  const r = DPR() * k;
  if (Math.abs(renderer.getPixelRatio() - r) > 1e-3) { renderer.setPixelRatio(r); renderer.setSize(host.clientWidth, host.clientHeight); }
}
(function loop(t) {
  requestAnimationFrame(loop);
  const mudouCam = controls.update();
  const cp = camera.position, cq = camera.quaternion, sig = `${cp.x.toFixed(3)},${cp.y.toFixed(3)},${cp.z.toFixed(3)},${cq.x.toFixed(5)},${cq.y.toFixed(5)},${cq.z.toFixed(5)},${cq.w.toFixed(5)},${camera.zoom},${camera.fov},${camera.aspect}`;
  const camMoveu = mudouCam || sig !== VIEW.sig; VIEW.sig = sig;
  const agora = t || performance.now(), mexendo = agora - VIEW.ativo < 600 || camMoveu;
  if (mexendo) {
    if (VIEW.ultimo) VIEW.medio = VIEW.medio * 0.8 + Math.min(agora - VIEW.ultimo, 500) * 0.2;
    if (VIEW.medio > 40 && VIEW.escala > 0.5) VIEW.escala = Math.max(0.5, VIEW.escala * 0.85);
    else if (VIEW.medio < 22 && VIEW.escala < 1) VIEW.escala = Math.min(1, VIEW.escala * 1.05);
    setEscala(VIEW.escala); VIEW.nitido = VIEW.escala >= 1;
  } else if (!VIEW.nitido) { setEscala(1); VIEW.nitido = true; VIEW.dirty = true; }
  VIEW.ultimo = mexendo ? agora : 0;
  if (!(mexendo || VIEW.dirty || agora - VIEW.desenhado > 250)) return;
  VIEW.dirty = false; VIEW.desenhado = agora;
  renderer.render(scene, camera); labelR.render(scene, camera);
})();

// ---------------------------------------------------------------- state
const S = {
  base: null, baseBox: null, joints: [], sel: -1, adding: false, lib: {}, cutGeo: {},
  jointGroup: new THREE.Group(), prevGroup: new THREE.Group(), pieceGroup: new THREE.Group(), pieces: [],
  showPieces: false, checking: 0, nextId: 1,
};
scene.add(S.jointGroup); scene.add(S.prevGroup); scene.add(S.pieceGroup);
const bedGroup = new THREE.Group(); scene.add(bedGroup);   // print beds of the "Na mesa" view
const loader = new STLLoader();
const PIECE_COLORS = [0xd9622b, 0x2f8f6b, 0x6a5acd, 0xc2417a, 0x6f9a2b, 0xc99a1e, 0x2b7bb9, 0x8c564b, 0x7f7f7f, 0x17a2b8, 0xb5651d, 0x9467bd];
const LUZ = { ok: '🟢', aviso: '🟡', erro: '🔴', nada: '⚪' };
const LUZ_TXT = { ok: 'verde', aviso: 'amarelo', erro: 'vermelho', nada: 'não verificada' };
const secPlane = new THREE.Plane(new THREE.Vector3(1, 0, 0), 0);

const api = async (path, opts = {}) => {
  const r = await fetch(path, opts);
  const ct = r.headers.get('content-type') || '';
  if (ct.includes('application/json')) {
    const j = await r.json();
    if (!r.ok || j.error) throw new Error(j.error || r.statusText);
    return j;
  }
  if (!r.ok) throw new Error(r.statusText);
  return r.arrayBuffer();
};
const post = (path, body) => api(path, { method: 'POST', body: JSON.stringify(body) });
const clr = () => parseFloat($('#clr').value) || 0.4;

// ---------------------------------------------------------------- overhang colouring
function colorize(geom, baseColor, showOv) {
  const pos = geom.attributes.position;
  const n = pos.count;
  const col = new Float32Array(n * 3);
  const c = new THREE.Color(baseColor);
  const red = new THREE.Color(0xe0312a);
  const a = new THREE.Vector3(), b = new THREE.Vector3(), d = new THREE.Vector3(), e1 = new THREE.Vector3(), e2 = new THREE.Vector3();
  for (let i = 0; i < n; i += 3) {
    a.fromBufferAttribute(pos, i); b.fromBufferAttribute(pos, i + 1); d.fromBufferAttribute(pos, i + 2);
    e1.subVectors(b, a); e2.subVectors(d, a);
    const nr = e1.clone().cross(e2).normalize();
    const zc = (a.z + b.z + d.z) / 3;
    const cc = showOv && nr.z < -0.72 && zc > 0.3 ? red : c;
    for (let k = 0; k < 3; k++) { col[(i + k) * 3] = cc.r; col[(i + k) * 3 + 1] = cc.g; col[(i + k) * 3 + 2] = cc.b; }
  }
  geom.setAttribute('color', new THREE.BufferAttribute(col, 3));
}
const solidMat = (opts = {}) => new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.75, metalness: 0.0, side: THREE.DoubleSide, ...opts });

// ---------------------------------------------------------------- cutter library
async function loadLibrary(selectId) {
  const r = await api('/api/cutters');
  S.lib = {};
  r.cutters.forEach((c) => { S.lib[c.id] = c; });
  const sel = $('#cut-type');
  const keep = selectId || sel.value || 'rla_arco';
  sel.innerHTML = r.cutters.map((c) => `<option value="${c.id}">${c.nome}${c.origem === 'sua' ? ' (sua)' : ''}</option>`).join('');
  if (S.lib[keep]) sel.value = keep;
  showUso();
}
function showUso() {
  const c = S.lib[$('#cut-type').value];
  $('#cut-uso').textContent = c ? (c.uso || '') : '';
}
$('#cut-type').addEventListener('change', showUso);
async function cutterGeo(id) {
  if (!S.cutGeo[id]) {
    const g = loader.parse(await api('/api/cutter.stl?id=' + encodeURIComponent(id)));
    g.computeVertexNormals();
    S.cutGeo[id] = g;
  }
  return S.cutGeo[id];
}
$('#cut-file').addEventListener('change', async () => {
  const f = $('#cut-file').files[0];
  if (!f) return;
  setStatus('Importando a peça de corte…');
  try {
    const r = await api('/api/cutters/import?name=' + encodeURIComponent(f.name.replace(/\.stl$/i, '')), { method: 'POST', body: await f.arrayBuffer() });
    await loadLibrary(r.id);
    setStatus(r.msg + ` Placa ${nf(r.meta.placa)} mm` + (r.meta.folga ? `, folga própria ${nf(r.meta.folga)} mm.` : '.'));
  } catch (e) { setStatus('Erro ao importar: ' + e.message); }
  $('#cut-file').value = '';
});
$('#btn-imp-wrap').addEventListener('click', () => $('#cut-file').click());

// ---------------------------------------------------------------- model
async function showBase(fit = true) {
  const buf = await api('/api/base.stl');
  const g = loader.parse(buf);
  g.computeVertexNormals();
  if (S.base) { setBaseHidden(null); scene.remove(S.base); S.base.geometry.dispose(); }
  g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(g.attributes.position.count * 3), 3));
  comBVH(g);
  S.base = new THREE.Mesh(g, solidMat({ transparent: true, opacity: 1 }));
  scene.add(S.base);
  baseTriData(g);
  await loadPaint();
  baseColorize();
  g.computeBoundingBox();
  S.baseBox = g.boundingBox.clone();
  if (fit) fitCamera('iso');
  setView(false);
  applyClipping();
}

function fitCamera(mode) {
  if (!S.baseBox) return;
  let c = S.baseBox.getCenter(new THREE.Vector3());
  let r = S.baseBox.getSize(new THREE.Vector3()).length() * 0.9;
  const j = S.joints[S.sel];
  if (mode === 'joint' && j) {
    c = new THREE.Vector3(...j.pos);
    r = 30 * Math.max(...j.escala, 0.4);
    const m = jointMatrix(j);
    const xa = new THREE.Vector3().setFromMatrixColumn(m, 0);
    camera.position.copy(c.clone().add(xa.multiplyScalar(r * 1.6)).add(new THREE.Vector3(0, 0, r * 0.5)));
  } else if (mode === 'top') camera.position.set(c.x, c.y - 0.001, c.z + r * 2.2);
  else if (mode === 'side') camera.position.set(c.x + r * 2.2, c.y, c.z + r * 0.15);
  else camera.position.set(c.x + r * 1.2, c.y - r * 1.6, c.z + r * 1.3);
  controls.target.copy(c);
  camera.lookAt(c);
  document.querySelectorAll('[data-cam]').forEach((b) => b.classList.toggle('on', b.dataset.cam === mode));
}
document.querySelectorAll('[data-cam]').forEach((b) => b.addEventListener('click', () => fitCamera(b.dataset.cam)));

function setView(pieces) {
  S.showPieces = pieces && S.pieces.length > 0;
  if (S.base) S.base.visible = !S.showPieces;
  S.pieceGroup.visible = S.showPieces;
  S.jointGroup.visible = !S.showPieces && !(S.painting || S.splitting);
  S.prevGroup.visible = !S.showPieces && !(S.painting || S.splitting) && $('#t-prev').checked;
  attachGizmo();
  $('#tg-junta').classList.toggle('hidden', S.showPieces || !!(S.painting || S.splitting));
  $('#t-orig').classList.toggle('on', !S.showPieces);
  $('#mesa-seg').classList.toggle('hidden', !S.showPieces || !S.mesa);
  bedGroup.visible = S.showPieces;
  $('#t-pieces').classList.toggle('on', S.showPieces);
  updateBaseOpacity();
}
$('#t-orig').onclick = () => { if (S.onMesa) showMesa(false); setView(false); };
$('#t-pieces').onclick = () => { if (!S.pieces.length) { setStatus('Exporte primeiro para ver as peças.'); return; } setView(true); };
$('#t-ov').onchange = () => {
  const on = $('#t-ov').checked;
  if (S.base) baseColorize();
  colorPieces();
};
$('#t-prev').onchange = () => { S.prevGroup.visible = $('#t-prev').checked && !S.showPieces; updateBaseOpacity(); };
$('#t-sec').onchange = () => { $('#sec-off').classList.toggle('hidden', !$('#t-sec').checked); applyClipping(); };
$('#sec-off').oninput = applyClipping;

function updateBaseOpacity() {
  if (!S.base) return;
  const prev = S.prevGroup.visible && S.prevGroup.children.length > 0;
  S.base.material.opacity = prev ? 0.22 : 1;
  S.base.material.depthWrite = !prev;
  S.base.material.needsUpdate = true;
}

// section plane: through the selected joint, across it (local X), to see the loops inside
function applyClipping() {
  const on = $('#t-sec').checked && S.joints[S.sel];
  const planes = on ? [secPlane] : [];
  if (on) {
    const j = S.joints[S.sel];
    const m = jointMatrix(j);
    const xa = new THREE.Vector3().setFromMatrixColumn(m, 0).normalize();
    const p = new THREE.Vector3(...j.pos).add(xa.clone().multiplyScalar(parseFloat($('#sec-off').value) || 0));
    secPlane.setFromNormalAndCoplanarPoint(xa.clone().negate(), p);
  }
  const set = (o) => { if (o.material) { o.material.clippingPlanes = planes; o.material.needsUpdate = true; } };
  if (S.base) set(S.base);
  S.prevGroup.traverse(set);
  S.jointGroup.traverse((o) => { if (o.userData.cutter) set(o); });
}

// file loading
const fileIn = $('#file');
const drop = $('#drop');
['dragover', 'dragenter'].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add('over'); }));
['dragleave', 'drop'].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove('over')));
drop.addEventListener('drop', (e) => {
  e.preventDefault();
  const f = e.dataTransfer.files[0];
  if (!f) return;
  if (/\.flexiproj$|\.json$/i.test(f.name)) openProjectFile(f); else loadFile(f);
});
fileIn.addEventListener('change', () => {
  const f = fileIn.files[0];
  if (f) { if (/\.flexiproj$|\.json$/i.test(f.name)) openProjectFile(f); else loadFile(f); }
  fileIn.value = '';
});
async function reveal(path) {
  try {
    const r = await post('/api/reveal', { path: path || '' });
    if (!r.ok) setStatus('Pasta: ' + (r.path || path));
  } catch (e) { setStatus('Erro: ' + e.message); }
}
$('#out-reveal').onclick = () => reveal(S.outDir);
$('#btn-reveal').onclick = () => reveal(S.lastExportDir);

async function loadFile(f) {
  setStatus(`Lendo ${f.name}… (modelos de IA grandes levam até 1 minuto)`);
  try {
    const buf = await f.arrayBuffer();
    const r = await api('/api/load?name=' + encodeURIComponent(f.name), { method: 'POST', body: buf });
    await afterModelLoad(r, f.name);
  } catch (e) { setStatus('Erro: ' + e.message); $('#model-info').textContent = '❌ ' + e.message; }
}
async function afterModelLoad(r, label) {
  {
    if (window.flexiFree) window.flexiFree.restore(null);      // linhas de corte eram do modelo anterior
    S.projPath = null;
    $('#drop-text').textContent = label;
    clearResult(); clearPreview();
    S.joints = []; S.sel = -1;
    showInfo(r.info, r.log);
    await showBase();
    renderJoints();
    $('#tex-box').classList.toggle('hidden', !r.textura);
    if (r.textura) {
      $('#tex-k').value = '';
      setStatus(`Modelo com textura: pintado automaticamente com ${r.textura.cores} filamentos (aba Cores). Retoque com o pincel, ajuste o número de cores ou siga para juntas e cortes.`);
    } else {
      setStatus('Modelo aberto. Clique em "＋ Adicionar junta" e depois no modelo onde deve dobrar, ou em "Sugerir juntas".');
    }
  }
  $('#p-simp').value = String(r.simplificar_mm !== undefined ? r.simplificar_mm : 0.005);
  if (r.qualidade) await askQuality(r.qualidade);
}

// ---------------------------------------------------------------- qualidade ao abrir modelo denso
// Modelo com muitos triângulos (figuras de IA): o usuário escolhe entre manter a malha, média ou
// baixa, vendo o efeito de cada uma. A escolha é o "Simplificar" do Ajustar tamanho e base.
const QUAL_TXT = {
  manter: { ic: '💎', t: 'Manter a qualidade', ef: 'Malha como no arquivo (desvio até 0,005 mm). Melhor acabamento possível. Abrir, pintar e cada corte ficam mais lentos e usam mais memória.' },
  media: { ic: '⚖', t: 'Média (recomendada)', ef: 'Desvio até 0,02 mm, abaixo do que a impressora reproduz (camada de 0,08 a 0,2 mm, bico de 0,4 mm). Na peça impressa não se vê diferença; os cortes ficam bem mais rápidos.' },
  baixa: { ic: '⚡', t: 'Baixa', ef: 'Desvio até 0,05 mm, como antes da versão 1.28. Rosto, olhos e relevo fino podem sair levemente facetados. O mais rápido para testar cortes.' },
};
function askQuality(q) {
  return new Promise((resolve) => {
    const base = q.opcoes.find((o) => o.nivel === 'manter') || q.opcoes[0];
    const ov = document.createElement('div');
    ov.className = 'qual-ov';
    ov.setAttribute('role', 'dialog');
    ov.setAttribute('aria-modal', 'true');
    ov.setAttribute('aria-label', 'Qualidade da malha');
    ov.innerHTML = `<div class="qual-box"><h3>Modelo com ${q.triangulos.toLocaleString('pt-BR')} triângulos</h3>
      <p class="hint">É uma malha densa (comum em modelos de IA). Escolha a qualidade de trabalho. Dá para mudar depois em Modelo › Ajustar tamanho e base › Simplificar.</p>
      <div class="qual-ops"></div>
      <div class="row"><button class="btn primary" id="qual-ok">Usar esta qualidade</button></div></div>`;
    const box = ov.querySelector('.qual-ops');
    let pick = q.opcoes.find((o) => o.nivel === 'media') ? 'media' : base.nivel;
    for (const o of q.opcoes) {
      const tx = QUAL_TXT[o.nivel];
      const rel = base.triangulos / Math.max(1, o.triangulos);
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'qual-op';
      b.dataset.nivel = o.nivel;
      b.innerHTML = `<span class="qual-ic" aria-hidden="true"></span><span class="qual-main"><b></b><span class="qual-num"></span><span class="hint qual-ef"></span></span><span class="qual-sel" aria-hidden="true"></span>`;
      b.querySelector('.qual-ic').textContent = tx.ic;
      b.querySelector('b').textContent = tx.t;
      b.querySelector('.qual-num').textContent = `${o.nivel === 'manter' ? '' : 'cerca de '}${o.triangulos.toLocaleString('pt-BR')} triângulos · desvio até ${nf(o.desvio_mm, 3)} mm` +
        (o.nivel === 'manter' ? ' · tempo de corte: referência' : ` · cortes cerca de ${nf(rel, 1)}× mais rápidos`);
      b.querySelector('.qual-ef').textContent = tx.ef;
      b.onclick = () => { pick = o.nivel; mark(); };
      box.append(b);
    }
    function mark() {
      box.querySelectorAll('.qual-op').forEach((b) => {
        const on = b.dataset.nivel === pick;
        b.classList.toggle('on', on);
        b.setAttribute('aria-pressed', on ? 'true' : 'false');
        b.querySelector('.qual-sel').textContent = on ? '✓ escolhida' : '';
      });
    }
    mark();
    document.body.append(ov);
    ov.querySelector('#qual-ok').focus();
    ov.querySelector('#qual-ok').onclick = async () => {
      const o = q.opcoes.find((x) => x.nivel === pick) || base;
      ov.remove();
      $('#p-simp').value = String(o.desvio_mm);
      if (o.nivel !== 'manter') {
        setStatus(`Aplicando a qualidade ${QUAL_TXT[o.nivel].t.toLowerCase()} (desvio até ${nf(o.desvio_mm, 3)} mm)…`);
        const pr = await prepareNow();
        const nt = pr && pr.info ? pr.info.triangulos : o.triangulos;
        setStatus(`Qualidade ${QUAL_TXT[o.nivel].t.toLowerCase()}: ${nt.toLocaleString('pt-BR')} triângulos (desvio até ${nf(o.desvio_mm, 3)} mm). Para mudar, use Modelo › Ajustar tamanho e base › Simplificar.`);
      } else setStatus(`Qualidade mantida: ${o.triangulos.toLocaleString('pt-BR')} triângulos. Os cortes levam mais tempo.`);
      resolve(o.nivel);
    };
  });
}
function showInfo(i, log) {
  const t = `Tamanho: ${nf(i.tamanho[0], 1)} × ${nf(i.tamanho[1], 1)} × ${nf(i.tamanho[2], 1)} mm\nTriângulos: ${i.triangulos.toLocaleString('pt-BR')}   Volume: ${Math.round(i.volume).toLocaleString('pt-BR')} mm³`;
  $('#model-info').textContent = t + (log && log.length ? '\n' + log.join(' · ') : '');
}
$('#btn-prep').onclick = () => prepareNow();
async function prepareNow() {
  setStatus('Preparando o modelo…');
  try {
    const free = window.flexiFree;
    const body = Object.assign(prepOpts(), { mascaras: free ? free.masksOut() : [] });
    const r = await post('/api/prepare', body);
    clearResult(); clearPreview();
    if (window.flexiPecas) window.flexiPecas.invalidate();
    showInfo(r.info, r.log);
    await showBase(false);
    // juntas, cortes livres e planos acompanham o novo tamanho e posição do modelo
    const mp = r.mapa;
    let nCut = 0;
    if (mp && (Math.abs(mp.s - 1) > 1e-6 || mp.t.some((v) => Math.abs(v) > 1e-6))) {
      S.joints.forEach((j) => { j.pos = j.pos.map((v, i) => +(mp.s * v + mp.t[i]).toFixed(3)); });   // o tamanho da junta não muda
      if (free) { free.remap(mp, r.mascaras); nCut = free.FC.cuts.length; }
      if (window.flexiPlano) window.flexiPlano.remap(mp);
    }
    S.joints.forEach((j) => { j.luz = 'nada'; j.checks = null; });
    renderJoints();
    setStatus(mp && Math.abs(mp.s - 1) > 1e-6 ? `Modelo preparado (escala ×${nf(mp.s, 3)}). Juntas${nCut ? ', cortes' : ''} e planos foram junto com o modelo: verifique de novo.`
      : 'Modelo preparado. Juntas, cortes e planos acompanharam o modelo: verifique de novo.');
    return r;
  } catch (e) { setStatus('Erro: ' + e.message); return null; }
}
function prepOpts() {
  return { length_mm: parseFloat($('#p-len').value) || 0, center: $('#p-center').checked, mirror: $('#p-mir').value,
           flatten_mm: parseFloat($('#p-flat').value) || 0, simplify_mm: parseFloat($('#p-simp').value) || 0 };
}

// ---------------------------------------------------------------- joints
// joint = {id, nome, tipo, pos[3], rot[3] (degrees, XYZ), escala[3], cadeado, borda, limites[6] (mm or null), folga (mm or null)}
const deg = THREE.MathUtils.degToRad;
function jointMatrix(j) {
  const m = new THREE.Matrix4();
  m.compose(new THREE.Vector3(...j.pos), new THREE.Quaternion().setFromEuler(new THREE.Euler(deg(j.rot[0]), deg(j.rot[1]), deg(j.rot[2]), 'XYZ')), new THREE.Vector3(1, 1, 1));
  return m;
}
function cleanJoint(j) {
  return { tipo: j.tipo, nome: j.nome || '', pos: j.pos.map(Number), rot: j.rot.map(Number), escala: j.escala.map(Number),
           cadeado: !!j.cadeado, borda: j.borda !== false, limites: j.limites ? j.limites.map((v) => (v === null || v === '' || isNaN(v) ? null : +v)) : null,
           folga: j.folga ? +j.folga : null, espelho: !!j.espelho };
}
function newFromServer(q) {
  return Object.assign({ id: S.nextId++, luz: 'nada', checks: null, nome: '' }, q);
}

async function renderJoints() {
  // 3D: one semi-transparent cutter per joint (colour = traffic light), label, gizmo on the selected.
  // Never rebuilt in the middle of a drag (a verification finishing would drop the handle).
  if (S.dragging) { S.pendingRender = true; return; }
  S.pendingRender = false;
  gizmo.detach();
  clearGroup(S.jointGroup);
  for (let i = 0; i < S.joints.length; i++) {
    const j = S.joints[i];
    const sel = i === S.sel;
    const g = new THREE.Group();
    g.position.set(...j.pos);
    g.rotation.set(deg(j.rot[0]), deg(j.rot[1]), deg(j.rot[2]), 'XYZ');
    g.userData.joint = i;
    const col = { ok: 0x2f8f6b, aviso: 0xc99a1e, erro: 0xc0392b, nada: 0x2b7bb9 }[j.luz || 'nada'];
    let geo = null;
    try { geo = await cutterGeo(j.tipo); } catch (e) { /* unknown cutter */ }
    if (geo) {
      const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: sel ? 0xd9622b : col, transparent: true, opacity: sel ? 0.5 : 0.32, depthWrite: false, side: THREE.DoubleSide }));
      mesh.scale.set(j.espelho ? -j.escala[0] : j.escala[0], j.escala[1], j.escala[2]);
      mesh.userData.cutter = true; mesh.userData.joint = i;
      mesh.renderOrder = 5;
      g.add(mesh);
    }
    const div = document.createElement('div');
    div.className = 'lbl' + (sel ? ' sel' : '');
    div.textContent = `${LUZ[j.luz || 'nada']} J${i + 1}`;
    const lab = new CSS2DObject(div);
    lab.position.set(0, 0, 18 * Math.max(...j.escala, 0.5));
    g.add(lab);
    S.jointGroup.add(g);
    g.visible = !j.oculta;
    j._obj = g;
  }
  renderList();
  renderEditor();
  applyClipping();
  attachGizmo();
  persist();
}
function clearGroup(g) {
  g.traverse((o) => { if (o.isCSS2DObject && o.element) o.element.remove(); });
  g.clear();
}
function renderList() {
  const list = $('#joint-list');
  list.innerHTML = '';
  S.joints.forEach((j, i) => {
    const nome = j.nome || (S.lib[j.tipo]?.nome || j.tipo);
    const esc = j.escala.map((v) => nf(v, 2)).join(' × ');
    const li = window.flexiUI.row({ list: 'juntas', luz: LUZ[j.luz || 'nada'], luzTitle: 'Semáforo: ' + LUZ_TXT[j.luz || 'nada'],
      tag: `J${i + 1}`, meta: `${nome} · ${esc}`, selected: i === S.sel, hidden: !!j.oculta,
      onSelect: () => select(i), onDelete: () => removeJoint(i), delTitle: 'Excluir a junta (Delete)',
      onToggle: () => { j.oculta = !j.oculta; if (j._obj) j._obj.visible = !j.oculta; renderList(); } });
    list.appendChild(li);
  });
}
function select(i) {
  S.sel = i;
  if (window.flexiUI) window.flexiUI.setActive('juntas', null);
  clearPreview();
  renderJoints().then(() => { if (S.joints[i] && S.joints[i].luz !== 'nada') showPreviewFor(i); });
}
function removeJoint(i) {
  const gone = S.joints[i];
  if (gone && window.flexiUI) window.flexiUI.push(`Junta J${i + 1}`, () => { S.joints.splice(Math.min(i, S.joints.length), 0, gone); S.sel = Math.min(i, S.joints.length - 1); jointsChanged(); renderJoints(); });
  S.joints.splice(i, 1);
  S.sel = Math.min(S.sel, S.joints.length - 1);
  clearPreview(); jointsChanged(); renderJoints();
}

// ---------------------------------------------------------------- editor panel
const LIM_NOMES = ['Esquerda (−X)', 'Direita (+X)', 'Frente (−Y)', 'Trás (+Y)', 'Baixo (−Z)', 'Cima (+Z)'];
function renderEditor() {
  const box = $('#joint-edit');
  const j = S.joints[S.sel];
  if (!j) { box.classList.add('hidden'); return; }
  box.classList.remove('hidden');
  const lim = j.limites || [null, null, null, null, null, null];
  const opts = Object.values(S.lib).map((c) => `<option value="${c.id}"${c.id === j.tipo ? ' selected' : ''}>${c.nome}</option>`).join('');
  const fx = (v) => (v === null || v === undefined ? '' : +(+v).toFixed(2));
  box.innerHTML = `
    <h3>${LUZ[j.luz || 'nada']} Junta J${S.sel + 1}</h3>
    <div class="grid2">
      <label>Nome<input data-k="nome" type="text" value="${(j.nome || '').replace(/"/g, '&quot;')}" placeholder="ex.: pata dianteira"></label>
      <label>Peça de corte<select data-k="tipo">${opts}</select></label>
    </div>
    <div class="lbl3">Posição (mm)</div>
    <div class="grid3">
      <label>X<input data-k="pos.0" type="number" step="0.5" value="${fx(j.pos[0])}"></label>
      <label>Y<input data-k="pos.1" type="number" step="0.5" value="${fx(j.pos[1])}"></label>
      <label>Z<input data-k="pos.2" type="number" step="0.25" value="${fx(j.pos[2])}"></label>
    </div>
    <div class="lbl3">Rotação (°)</div>
    <div class="grid3">
      <label>em X<input data-k="rot.0" type="number" step="5" value="${fx(j.rot[0])}"></label>
      <label>em Y<input data-k="rot.1" type="number" step="5" value="${fx(j.rot[1])}"></label>
      <label>em Z<input data-k="rot.2" type="number" step="5" value="${fx(j.rot[2])}"></label>
    </div>
    <div class="lbl3">Escala <button class="lock${j.cadeado ? ' on' : ''}" data-act="lock" title="${j.cadeado ? 'Cadeado fechado: proporção mantida (simétrica)' : 'Cadeado aberto: cada eixo livre (assimétrica)'}">${j.cadeado ? '🔒 simétrica' : '🔓 assimétrica'}</button></div>
    <div class="grid3">
      <label>Largura<input data-k="escala.0" type="number" step="0.05" min="0.1" value="${fx(j.escala[0])}"></label>
      <label>Espessura<input data-k="escala.1" type="number" step="0.05" min="0.1" value="${fx(j.escala[1])}"></label>
      <label>Altura<input data-k="escala.2" type="number" step="0.05" min="0.1" value="${fx(j.escala[2])}"></label>
    </div>
    <div class="row"><button class="btn" data-act="fit">Ajustar tamanho ao local</button><button class="btn" data-act="flip">↻ Inverter lado</button></div>
    <details class="adv"${j._limOpen ? ' open' : ''} data-act="limdet"><summary>Limites do corte (mm a partir do centro)</summary>
      <p class="hint">Recortam só a placa da peça de corte. Os elos nunca são recortados. Vazio = sem limite.</p>
      <div class="grid3">${lim.map((v, k) => `<label>${LIM_NOMES[k]}<input data-k="limites.${k}" type="number" step="0.5" min="0" value="${fx(v)}"></label>`).join('')}</div>
      <div class="row"><button class="btn" data-act="limauto">Limites pela seção</button><button class="btn" data-act="limnone">Sem limites</button></div>
    </details>
    <label class="chk"><input data-k="borda" type="checkbox"${j.borda !== false ? ' checked' : ''}> Corte dentro da borda (só a parte onde a junta está; uma parte colada ali é cortada junto)</label>
    <label class="inline">Folga só desta junta (mm)<input data-k="folga" type="number" step="0.05" min="0.05" value="${fx(j.folga)}" placeholder="${nf(clr())}"></label>
    <div class="row">
      <button class="btn primary" data-act="check">Verificar</button>
      <button class="btn" data-act="mirror">Espelhar</button>
      <button class="btn" data-act="dup">Duplicar</button>
      <button class="btn" data-act="del">Remover</button>
    </div>
    <div id="checks">${renderChecks(j)}</div>
    <p class="hint">Mouse: arraste a peça de corte para mover (Shift sobe e desce), os anéis para girar e as alças da caixa para a escala. Teclas A, M, R, S trocam a ferramenta. A verificação roda sozinha ao soltar.</p>`;
  box.querySelectorAll('[data-k]').forEach((el) => el.addEventListener('change', () => fieldChanged(j, el)));
  box.querySelectorAll('button[data-act]').forEach((b) => b.addEventListener('click', (e) => { e.preventDefault(); act(j, b.dataset.act); }));
  box.querySelector('details[data-act="limdet"]').addEventListener('toggle', (e) => { j._limOpen = e.target.open; });
}
function renderChecks(j) {
  if (S.checking && S.joints[S.sel] === j) return '<p class="hint">Verificando…</p>';
  if (!j.checks) return '<p class="hint">Ainda não verificada.</p>';
  const ic = { ok: '✅', aviso: '⚠️', erro: '❌' };
  return '<ul class="checks">' + j.checks.map((c) => `<li class="${c.nivel}">${ic[c.nivel]} ${c.texto}</li>`).join('') + '</ul>' +
    (j.segundos != null ? `<p class="hint">Verificado em ${nf(j.segundos, 1)} s.</p>` : '');
}
function fieldChanged(j, el) {
  const k = el.dataset.k;
  if (k === 'borda') j.borda = el.checked;
  else if (k === 'nome') { j.nome = el.value; renderList(); persist(); return; }
  else if (k === 'tipo') j.tipo = el.value;
  else if (k === 'folga') j.folga = el.value === '' ? null : parseFloat(el.value);
  else {
    const [a, i] = k.split('.');
    let v = el.value === '' ? null : parseFloat(el.value);
    if (a === 'limites') {
      j.limites = j.limites || [null, null, null, null, null, null];
      j.limites[+i] = v === null ? null : Math.abs(v);
    } else if (a === 'escala') {
      v = Math.max(0.1, v || 0.1);
      if (j.cadeado) { const f = v / (j.escala[+i] || 1); j.escala = j.escala.map((s) => +(s * f).toFixed(3)); } else j.escala[+i] = v;
    } else if (v !== null) j[a][+i] = v;
  }
  touched(j);
}
async function act(j, a) {
  const i = S.joints.indexOf(j);
  if (a === 'lock') { j.cadeado = !j.cadeado; renderEditor(); persist(); return; }
  if (a === 'check') { verify(i); return; }
  if (a === 'del') { removeJoint(i); return; }
  if (a === 'flip') { j.rot[2] = ((j.rot[2] + 360) % 360) - 180; touched(j); return; }
  if (a === 'limnone') { j.limites = null; touched(j); return; }
  if (a === 'fit' || a === 'limauto') {
    setStatus(a === 'fit' ? 'Ajustando o tamanho dos elos à parte…' : 'Calculando limites pela seção…');
    try {
      const r = await post('/api/editor/fit', { joint: cleanJoint(j) });
      if (!r.ok) { setStatus(r.msg); return; }
      if (a === 'fit') { j.escala = r.joint.escala; j.pos = r.joint.pos; }
      j.limites = r.joint.limites;
      touched(j);
      setStatus(a === 'fit' ? `Escala ajustada: ${j.escala.map((v) => nf(v)).join(' × ')}.` : 'Limites ajustados à seção.');
    } catch (e) { setStatus('Erro: ' + e.message); }
    return;
  }
  if (a === 'mirror') {
    if (!S.baseBox) return;
    const cx = (S.baseBox.min.x + S.baseBox.max.x) / 2;
    const m = cleanJoint(j);
    m.pos[0] = +(2 * cx - m.pos[0]).toFixed(3);
    m.rot = [m.rot[0], -m.rot[1], -m.rot[2]];
    if (m.limites) m.limites = [m.limites[1], m.limites[0], m.limites[2], m.limites[3], m.limites[4], m.limites[5]];
    m.nome = j.nome ? j.nome + ' (espelho)' : '';
    m.espelho = !j.espelho;
    const nj = newFromServer(m);
    S.joints.push(nj);
    S.sel = S.joints.length - 1;
    jointsChanged(); await renderJoints(); await verify(S.sel);
    if (nj.luz === 'erro') {
      // the two sides of a model are rarely identical: fit the copy to its own side
      try {
        const r = await post('/api/editor/fit', { joint: cleanJoint(nj) });
        if (r.ok) { nj.escala = r.joint.escala; nj.pos = r.joint.pos; nj.limites = r.joint.limites; await renderJoints(); await verify(S.sel); }
      } catch (e) { /* keep the plain copy */ }
      setStatus(`J${S.sel + 1} espelhada de J${i + 1}. Os dois lados do modelo não são iguais, então ajustei o tamanho ao lado espelhado: ${LUZ[nj.luz]} ${LUZ_TXT[nj.luz]}.`);
    } else setStatus(`J${S.sel + 1} criada espelhando J${i + 1} no centro do modelo: ${LUZ[nj.luz]} ${LUZ_TXT[nj.luz]}.`);
    return;
  }
  if (a === 'dup') {
    const m = cleanJoint(j);
    const n = new THREE.Vector3().setFromMatrixColumn(jointMatrix(j), 1).normalize();
    const step = 12 * Math.max(...j.escala, 0.5);
    m.pos = [m.pos[0] + n.x * step, m.pos[1] + n.y * step, m.pos[2]];
    S.joints.push(newFromServer(m));
    S.sel = S.joints.length - 1;
    jointsChanged(); await renderJoints(); verify(S.sel);
    setStatus(`J${S.sel + 1} duplicada de J${i + 1}, ${nf(step, 0)} mm à frente. Arraste para o lugar.`);
  }
}
function touched(j) {
  S.dragging = false;
  j.luz = 'nada'; j.checks = null;
  clearPreview(); jointsChanged(); renderJoints();
  scheduleVerify(S.joints.indexOf(j));
}

// ---------------------------------------------------------------- mouse editing (like Bambu Studio)
// M move, R rotate, S scale. Drag the selected cutter itself to slide it over the bed plane
// (Shift: up and down). Scale has a box with handles: faces change one axis (or all, with the
// lock closed), corners change all axes together. Option + wheel scales too. Arrows nudge.
S.mode = 'all';
S.space = 'local';
S.dragging = false;
S.pendingRender = false;
const hudEl = document.createElement('div');
hudEl.className = 'hud hidden';
host.appendChild(hudEl);
let lastPointer = null;
function hud(txt, e = lastPointer) {
  if (!txt || !e) { hudEl.classList.add('hidden'); return; }
  const r = host.getBoundingClientRect();
  hudEl.style.left = (e.clientX - r.left + 18) + 'px';
  hudEl.style.top = (e.clientY - r.top + 18) + 'px';
  hudEl.textContent = txt;
  hudEl.classList.remove('hidden');
}
const fmtPos = (j) => `X ${nf(j.pos[0], 1)}  Y ${nf(j.pos[1], 1)}  Z ${nf(j.pos[2], 1)} mm`;
const fmtRot = (j) => `Rotação  X ${nf(j.rot[0], 0)}°  Y ${nf(j.rot[1], 0)}°  Z ${nf(j.rot[2], 0)}°`;
const fmtEsc = (j) => `Largura ${nf(j.escala[0])} × Espessura ${nf(j.escala[1])} × Altura ${nf(j.escala[2])}` + (j.cadeado ? '  🔒' : '  🔓');

function setGizmoMode(m) {
  S.mode = m;
  document.querySelectorAll('[data-gz]').forEach((b) => b.classList.toggle('on', b.dataset.gz === m));
  attachGizmo();
}
document.querySelectorAll('[data-gz]').forEach((b) => b.addEventListener('click', () => setGizmoMode(b.dataset.gz)));
$('#gz-space').addEventListener('click', () => {
  S.space = S.space === 'local' ? 'world' : 'local';
  $('#gz-space').textContent = S.space === 'local' ? 'Eixos: da junta' : 'Eixos: do modelo';
  gizmo.setSpace(S.space);
});

// scale handles: a box around the selected cutter
const handles = new THREE.Group();
handles.renderOrder = 20;
scene.add(handles);
const AXN = ['Largura', 'Espessura', 'Altura'];
function clearHandles() { clearGroup(handles); handles.visible = false; }
function buildHandles() {
  clearHandles();
  const j = S.joints[S.sel];
  if (!j || (S.mode !== 'scale' && S.mode !== 'all') || S.showPieces || S.adding || !S.cutGeo[j.tipo]) return;
  const g = S.cutGeo[j.tipo];
  if (!g.boundingBox) g.computeBoundingBox();
  const bb = g.boundingBox;
  const sc = new THREE.Vector3(j.espelho ? -j.escala[0] : j.escala[0], j.escala[1], j.escala[2]);
  const lo = bb.min.clone().multiply(sc), hi = bb.max.clone().multiply(sc);
  const mn = lo.clone().min(hi), mx = lo.clone().max(hi);
  const c = mn.clone().add(mx).multiplyScalar(0.5), h = mx.clone().sub(mn).multiplyScalar(0.5);
  handles.position.set(...j.pos);
  handles.rotation.set(deg(j.rot[0]), deg(j.rot[1]), deg(j.rot[2]), 'XYZ');
  const box = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(2 * h.x, 2 * h.y, 2 * h.z)),
    new THREE.LineBasicMaterial({ color: 0xd9622b, depthTest: false, transparent: true }));
  box.position.copy(c); box.renderOrder = 20;
  handles.add(box);
  const size = Math.max(0.9, 0.07 * Math.max(h.x, h.y, h.z));
  const mk = (color, data, pos, label) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(size, size, size),
      new THREE.MeshBasicMaterial({ color, depthTest: false, transparent: true, opacity: 0.95 }));
    m.position.copy(pos); m.renderOrder = 21; m.userData.handle = data;
    if (label) {
      const d = document.createElement('div'); d.className = 'hlbl'; d.textContent = label;
      const l = new CSS2DObject(d); l.position.set(0, 0, size * 1.4); m.add(l);
    }
    handles.add(m);
  };
  const cols = [0xe0312a, 0x2f8f3f, 0x2b6fd9];
  for (let k = 0; k < 3; k++) for (const sg of [-1, 1]) {
    const p = c.clone(); p.setComponent(k, c.getComponent(k) + sg * h.getComponent(k));
    mk(cols[k], { kind: 'face', axis: k, sign: sg }, p, sg > 0 ? AXN[k] : null);
  }
  for (const sx of [-1, 1]) for (const sy of [-1, 1]) for (const sz of [-1, 1]) {
    mk(0xffffff, { kind: 'corner', dir: new THREE.Vector3(sx * h.x, sy * h.y, sz * h.z) },
      new THREE.Vector3(c.x + sx * h.x, c.y + sy * h.y, c.z + sz * h.z), null);
  }
  handles.userData.center = c;
  handles.visible = true;
}

function attachGizmo() {
  const j = S.joints[S.sel];
  if (!j || !j._obj || S.showPieces || S.adding || (S.painting || S.splitting)) { gizmo.detach(); clearHandles(); return; }
  if (S.mode === 'scale') { gizmo.detach(); buildHandles(); return; }
  // "Tudo": rings to rotate + box handles to scale + drag the cutter to move, all at once
  if (S.mode === 'all') buildHandles(); else clearHandles();
  gizmo.attach(j._obj);
  gizmo.setMode(S.mode === 'all' ? 'rotate' : S.mode);
  gizmo.setSpace(S.space);
}

// rotate / translate with the gizmo (arrows and rings)
gizmo.addEventListener('dragging-changed', (e) => {
  controls.enabled = !e.value;
  S.dragging = e.value;
  if (e.value) clearPreview();
  else { hud(null); gizmoReleased(); }
});
gizmo.addEventListener('objectChange', () => {
  const j = S.joints[S.sel];
  const o = gizmo.object;
  if (!j || !o) return;
  if (gizmo.mode === 'translate') { j.pos = [o.position.x, o.position.y, o.position.z].map((v) => +v.toFixed(3)); hud(fmtPos(j)); }
  if (gizmo.mode === 'rotate') {
    const eu = new THREE.Euler().setFromQuaternion(o.quaternion, 'XYZ');
    j.rot = [eu.x, eu.y, eu.z].map((v) => +THREE.MathUtils.radToDeg(v).toFixed(2));
    hud(fmtRot(j) + (gizmo.rotationSnap ? '  (passos de 15°)' : ''));
  }
  liveFields(j);
});
function gizmoReleased() { const j = S.joints[S.sel]; if (j) touched(j); }
window.addEventListener('keydown', (e) => { if (e.key === 'Shift') { gizmo.setRotationSnap(deg(15)); gizmo.setTranslationSnap(0.5); } });
window.addEventListener('keyup', (e) => { if (e.key === 'Shift') { gizmo.setRotationSnap(null); gizmo.setTranslationSnap(null); } });

function liveFields(j) {
  if (!S._edFrame) S._edFrame = requestAnimationFrame(() => { S._edFrame = 0; refreshFields(j); });
}
function refreshFields(j) {
  const box = $('#joint-edit');
  const put = (k, v) => { const el = box.querySelector(`[data-k="${k}"]`); if (el && document.activeElement !== el) el.value = +(+v).toFixed(2); };
  j.pos.forEach((v, i) => put('pos.' + i, v));
  j.rot.forEach((v, i) => put('rot.' + i, v));
  j.escala.forEach((v, i) => put('escala.' + i, v));
  applyClipping();
}
function applyLive(j) {
  // move the 3D objects without rebuilding them (keeps the drag alive)
  const o = j._obj;
  if (o) {
    o.position.set(...j.pos);
    o.rotation.set(deg(j.rot[0]), deg(j.rot[1]), deg(j.rot[2]), 'XYZ');
    const mesh = o.children.find((c) => c.userData.cutter);
    if (mesh) mesh.scale.set(j.espelho ? -j.escala[0] : j.escala[0], j.escala[1], j.escala[2]);
  }
  if (S.mode === 'scale' || S.mode === 'all') buildHandles();
  liveFields(j);
}

// drag the cutter body / the scale handles
let mdrag = null;
const planeHit = (e, plane) => { ray.setFromCamera(ndc(e), camera); const p = new THREE.Vector3(); return ray.ray.intersectPlane(plane, p) ? p : null; };
function axisParam(e, C, a) {
  // position along the line C + t a closest to the mouse ray
  ray.setFromCamera(ndc(e), camera);
  const d = ray.ray.direction, w0 = ray.ray.origin.clone().sub(C);
  const b = a.dot(d), den = 1 - b * b;
  if (Math.abs(den) < 1e-4) return null;
  return (a.dot(w0) - b * d.dot(w0)) / den;
}
host.addEventListener('pointerdown', (e) => {
  lastPointer = e;
  if (e.button !== 0 || S.adding || S.showPieces || (S.painting || S.splitting) || gizmo.axis) return;
  ray.setFromCamera(ndc(e), camera);
  const j = S.joints[S.sel];
  if (j && handles.visible) {
    const hh = ray.intersectObjects(handles.children, false).filter((h) => h.object.userData.handle);
    if (hh.length) {
      const hd = hh[0].object.userData.handle;
      const C = handles.localToWorld(handles.userData.center.clone());
      const q = handles.getWorldQuaternion(new THREE.Quaternion());
      const a = (hd.kind === 'face' ? new THREE.Vector3().setComponent(hd.axis, hd.sign) : hd.dir.clone()).applyQuaternion(q).normalize();
      const t0 = axisParam(e, C, a);
      if (t0 && t0 > 0.05) {
        mdrag = { kind: 'scale', j, hd, C, a, t0, s0: j.escala.slice(), moved: false };
        startDrag(e);
        return;
      }
    }
  }
  const hits = ray.intersectObjects(S.jointGroup.children, true).filter((h) => h.object.userData.cutter);
  if (!hits.length || hits[0].object.userData.joint !== S.sel || !j) return;   // other cutters: click selects
  const p0 = hits[0].point.clone();
  mdrag = { kind: 'move', j, p0, pos0: j.pos.slice(), plane: new THREE.Plane(new THREE.Vector3(0, 0, 1), -p0.z), moved: false, x0: e.clientX, y0: e.clientY };
  startDrag(e);
}, true);
function startDrag(e) {
  e.stopPropagation(); e.preventDefault();
  controls.enabled = false;
  host.setPointerCapture?.(e.pointerId);
}
host.addEventListener('pointermove', (e) => {
  lastPointer = e;
  if (!mdrag) {
    if (e.buttons === 0 && !S.adding && !gizmo.axis) {
      ray.setFromCamera(ndc(e), camera);
      let cur = '';
      if (handles.visible && ray.intersectObjects(handles.children, false).some((h) => h.object.userData.handle)) cur = 'nwse-resize';
      else {
        const hits = ray.intersectObjects(S.jointGroup.children, true).filter((h) => h.object.userData.cutter);
        if (hits.length) cur = hits[0].object.userData.joint === S.sel ? 'move' : 'pointer';
      }
      renderer.domElement.style.cursor = cur;
    }
    return;
  }
  e.stopPropagation();
  const d = mdrag, j = d.j;
  if (d.kind === 'move') {
    if (!d.moved && Math.hypot(e.clientX - d.x0, e.clientY - d.y0) < 3) return;
    if (!d.moved) { d.moved = true; S.dragging = true; clearPreview(); }
    if (e.shiftKey) {
      // up and down: vertical plane facing the camera
      const n = camera.getWorldDirection(new THREE.Vector3()); n.z = 0;
      if (n.lengthSq() < 1e-6) n.set(0, 1, 0);
      const pl = new THREE.Plane().setFromNormalAndCoplanarPoint(n.normalize(), new THREE.Vector3(...j.pos));
      if (d.zRef == null) { const p = planeHit(e, pl); d.zRef = p ? p.z - j.pos[2] : 0; }
      const p = planeHit(e, pl);
      if (p) j.pos = [j.pos[0], j.pos[1], +(p.z - d.zRef).toFixed(3)];
    } else {
      d.zRef = null;
      d.plane.constant = -(d.p0.z + (j.pos[2] - d.pos0[2]));
      const p = planeHit(e, d.plane);
      if (p) j.pos = [+(d.pos0[0] + p.x - d.p0.x).toFixed(3), +(d.pos0[1] + p.y - d.p0.y).toFixed(3), j.pos[2]];
    }
    applyLive(j);
    hud(fmtPos(j) + (e.shiftKey ? '  (subindo/descendo)' : ''), e);
  } else {
    const t = axisParam(e, d.C, d.a);
    if (t == null) return;
    let f = Math.max(0.05, t / d.t0);
    d.moved = true; S.dragging = true;
    let s = d.s0.slice();
    if (d.hd.kind === 'corner' || j.cadeado) s = s.map((v) => v * f);
    else s[d.hd.axis] = s[d.hd.axis] * f;
    s = s.map((v) => {
      v = Math.min(4, Math.max(0.1, v));
      return e.shiftKey ? Math.round(v / 0.05) * 0.05 : +v.toFixed(3);
    });
    j.escala = s;
    applyLive(j);
    hud(fmtEsc(j) + (e.shiftKey ? '  (passos de 0,05)' : ''), e);
  }
}, true);
function endMouseDrag(e) {
  if (!mdrag) return;
  e?.stopPropagation?.();
  const d = mdrag; mdrag = null;
  controls.enabled = true;
  S.dragging = false;
  hud(null);
  if (d.moved) { touched(d.j); downXY = null; }
}
host.addEventListener('pointerup', endMouseDrag, true);
host.addEventListener('pointercancel', endMouseDrag, true);
window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && mdrag) {          // cancel: back to where it was
    const d = mdrag; mdrag = null;
    if (d.kind === 'move') d.j.pos = d.pos0; else d.j.escala = d.s0;
    controls.enabled = true; S.dragging = false; hud(null); applyLive(d.j);
  }
});

// Option (Alt) + wheel over the model: scale the selected joint (all axes, or the lock rule)
let wheelTimer = null;
host.addEventListener('wheel', (e) => {
  const j = S.joints[S.sel];
  if (!e.altKey || !j || S.showPieces || (S.painting || S.splitting)) return;
  e.preventDefault(); e.stopPropagation();
  const f = e.deltaY < 0 ? 1.03 : 1 / 1.03;
  j.escala = j.escala.map((v) => Math.min(4, Math.max(0.1, +(v * f).toFixed(3))));
  S.dragging = true;
  applyLive(j);
  hud(fmtEsc(j), e);
  clearTimeout(wheelTimer);
  wheelTimer = setTimeout(() => { S.dragging = false; hud(null); touched(j); }, 500);
}, { capture: true, passive: false });

// keyboard: M R S like Bambu Studio (W E also work), arrows nudge, Delete removes
let nudgeTimer = null;
window.addEventListener('keydown', (e) => {
  if (document.activeElement && ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return;
  if ((S.painting || S.splitting) || e.metaKey || e.ctrlKey) return;          // painting has its own keys; ⌘ shortcuts elsewhere
  const k = e.key.toLowerCase();
  if (k === 'a') setGizmoMode('all');
  if (k === 'm' || k === 'w') setGizmoMode('translate');
  if (k === 'r' || k === 'e') setGizmoMode('rotate');
  if (k === 's') setGizmoMode('scale');
  if (e.key === 'Escape' && S.adding) { S.adding = false; $('#btn-add').classList.remove('active'); attachGizmo(); setStatus('Pronto.'); }
  if ((e.key === 'Delete' || e.key === 'Backspace') && S.sel >= 0 && !mdrag && (!window.flexiUI || [null, 'juntas'].includes(window.flexiUI.active()))) removeJoint(S.sel);
  const j = S.joints[S.sel];
  const step = e.shiftKey ? 0.1 : 0.5;
  const mv = { ArrowLeft: [-step, 0, 0], ArrowRight: [step, 0, 0], ArrowUp: [0, step, 0], ArrowDown: [0, -step, 0], PageUp: [0, 0, step], PageDown: [0, 0, -step] }[e.key];
  if (mv && j) {
    e.preventDefault();
    j.pos = j.pos.map((v, i) => +(v + mv[i]).toFixed(3));
    S.dragging = true;
    applyLive(j);
    setStatus(`J${S.sel + 1}: ${fmtPos(j)}`);
    clearTimeout(nudgeTimer);
    nudgeTimer = setTimeout(() => { S.dragging = false; touched(j); }, 600);
  }
});
host.addEventListener('dblclick', (e) => {
  ray.setFromCamera(ndc(e), camera);
  if (!(S.painting || S.splitting)) {
    const hits = ray.intersectObjects(S.jointGroup.children, true).filter((h) => h.object.userData.cutter);
    if (hits.length) { if (hits[0].object.userData.joint !== S.sel) select(hits[0].object.userData.joint); setTimeout(() => fitCamera('joint'), 50); return; }
  }
  // duplo clique no modelo: a vista passa a girar e aproximar em volta desse ponto
  const h = S.base && S.base.visible ? ray.intersectObject(S.base)[0] : null;
  if (!h) return;
  const d = h.point.clone().sub(controls.target);
  controls.target.add(d);
  camera.position.add(d);
  controls.update();
  setStatus('Vista centrada no ponto (duplo clique). A roda aproxima onde está o mouse.');
});

// ---------------------------------------------------------------- verify (preview)
let verifyTimer = null;
function scheduleVerify(i) {
  clearTimeout(verifyTimer);
  verifyTimer = setTimeout(() => verify(i), 350);
}
let verifySeq = 0;
async function verify(i) {
  const j = S.joints[i];
  if (!j || !S.base) return;
  const seq = ++verifySeq;
  S.checking++;
  if (i === S.sel) $('#checks') && ($('#checks').innerHTML = '<p class="hint">Verificando…</p>');
  setStatus(`Verificando J${i + 1}…`);
  try {
    const others = S.joints.map((o, k) => (k === i ? null : cleanJoint(o)));
    const r = await post('/api/editor/check', { joint: cleanJoint(j), others, clearance: clr() });
    if (S.joints[i] !== j) return;
    j.checks = r.checks; j.luz = r.luz; j.segundos = r.segundos;
    if (seq === verifySeq && i === S.sel) await loadPreview(r.tem);
    const msg = { ok: 'tudo verde', aviso: 'com avisos (amarelo)', erro: 'com problemas (vermelho)' }[r.luz];
    setStatus(`J${i + 1} verificada em ${nf(r.segundos, 1)} s: ${msg}.`);
  } catch (e) { setStatus('Erro na verificação: ' + e.message); }
  finally { S.checking--; renderJoints(); }
}
async function showPreviewFor(i) {
  // the server keeps only the last preview: verify again to show this one
  verify(i);
}
async function loadPreview(tem) {
  clearPreview();
  const parts = [['a', 0xd9622b], ['b', 0x2f8f6b]];
  for (const [p, c] of parts) {
    if (!tem || !tem[p]) continue;
    const g = loader.parse(await api('/api/preview.stl?p=' + p));
    g.computeVertexNormals();
    colorize(g, c, false);
    const m = new THREE.Mesh(g, solidMat());
    S.prevGroup.add(m);
  }
  S.prevGroup.visible = $('#t-prev').checked && !S.showPieces;
  updateBaseOpacity();
  applyClipping();
}
function clearPreview() {
  S.prevGroup.traverse((o) => { if (o.geometry) o.geometry.dispose(); });
  S.prevGroup.clear();
  updateBaseOpacity();
}
$('#btn-check-all').onclick = async () => {
  if (!S.joints.length) { setStatus('Posicione pelo menos uma junta.'); return; }
  for (let i = 0; i < S.joints.length; i++) await verify(i);
  const n = { ok: 0, aviso: 0, erro: 0 };
  S.joints.forEach((j) => { n[j.luz] = (n[j.luz] || 0) + 1; });
  setStatus(`Verificação: ${n.ok} verde(s), ${n.aviso} amarela(s), ${n.erro} vermelha(s).`);
};

// ---------------------------------------------------------------- add joints
$('#btn-add').onclick = () => {
  if (!S.base) { setStatus('Carregue um modelo primeiro.'); return; }
  S.adding = !S.adding;
  $('#btn-add').classList.toggle('active', S.adding);
  attachGizmo();
  setStatus(S.adding ? 'Clique no modelo onde deve dobrar. A junta nasce ajustada à seção daquele ponto; as outras não mudam (Esc para terminar).' : 'Pronto.');
  setView(false);
};
const ray = new THREE.Raycaster();
let downXY = null;
function ndc(e) {
  const r = renderer.domElement.getBoundingClientRect();
  return new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
}
renderer.domElement.addEventListener('pointerdown', (e) => { downXY = [e.clientX, e.clientY]; });
renderer.domElement.addEventListener('pointerup', async (e) => {
  if (!downXY || Math.hypot(e.clientX - downXY[0], e.clientY - downXY[1]) > 4) return;
  if (gizmo.dragging || gizmo.axis || mdrag || (S.painting || S.splitting)) return;
  ray.setFromCamera(ndc(e), camera);
  if (S.adding && S.base) {
    const hit = ray.intersectObject(S.base)[0];
    if (!hit) return;
    await addAt(hit.point.x, hit.point.y);
    return;
  }
  // click on a cutter selects its joint
  const hits = ray.intersectObjects(S.jointGroup.children, true).filter((h) => h.object.userData.cutter);
  if (hits.length) select(hits[0].object.userData.joint);
});
async function addAt(x, y) {
  setStatus('Criando a junta e ajustando ao local…');
  try {
    const r = await post('/api/editor/suggest', { x, y, tipo: $('#cut-type').value, others: S.joints.map(cleanJoint) });
    S.joints.push(newFromServer(r.joint));
    S.sel = S.joints.length - 1;
    jointsChanged();
    await renderJoints();
    if (r.joint.aviso) setStatus(r.joint.aviso);
    else if (r.joint.movida_mm) setStatus(`Junta deslizada ${nf(r.joint.movida_mm, 0)} mm ao longo da parte, onde cabem elos mais fortes.`);
    verify(S.sel);
  } catch (e) { setStatus('Erro ao adicionar: ' + e.message); }
}
window.addEventListener('keydown', (e) => { if (e.key === 'Escape' && gizmo.dragging) { /* gizmo handles */ } });

$('#btn-suggest').onclick = async () => {
  if (!S.base) { setStatus('Carregue um modelo primeiro.'); return; }
  setStatus('Sugerindo juntas pelo formato do modelo…');
  try {
    const r = await post('/api/editor/suggest_all', { tipo: $('#cut-type').value, clearance: clr() });
    if (!r.joints.length) { setStatus(r.msg || 'Nenhuma sugestão. Adicione clicando no modelo.'); return; }
    const before = S.joints.length;
    r.joints.forEach((q) => S.joints.push(newFromServer(q)));
    S.sel = before;
    jointsChanged();
    await renderJoints();
    setStatus(`${r.joints.length} junta(s) sugerida(s), somadas às que já existiam. Ajuste cada uma e verifique.`);
    for (let i = before; i < S.joints.length; i++) await verify(i);
  } catch (e) { setStatus('Erro: ' + e.message); }
};

// ---------------------------------------------------------------- export
function clearResult() {
  if (typeof showMesa === 'function' && S.onMesa) { S.mesa = null; try { showMesa(false); } catch (e) {} }
  S.mesa = null;
  $('#mesa-seg').classList.add('hidden');
  grid.visible = true;
  S.pieces.forEach((m) => m.geometry.dispose());
  S.pieces = []; clearGroup(S.pieceGroup);
  $('#report').innerHTML = '';
  $('#dl-box').classList.add('hidden');
  $('#pcol-seg').classList.add('hidden');
  setView(false);
}
function jointsChanged() {
  if (S.pieces.length) { clearResult(); setStatus('As juntas mudaram. Exporte de novo para ver as peças.'); }
}
$('#btn-export').onclick = () => doExport(false);
async function doExport(force) {
  if (!S.base) { setStatus('Carregue um modelo primeiro.'); return; }
  // one export for both tools: joints (section 2), parts separated by colour (section 4), or both
  let sep = null;
  try { sep = window.flexiSplit ? await window.flexiSplit.forExport() : null; } catch (e) { setStatus('Erro: ' + e.message); return; }
  const semPintura = !!(sep && sep.vazio);
  if (semPintura) sep = null;
  const livres = window.flexiFree ? window.flexiFree.forExport() : null;
  if (semPintura && !S.joints.length && !livres) { setStatus('A pintura do modelo está vazia: não há peças por cor para separar. Se ela sumiu sem querer, na aba Cores o ⌘Z (Ctrl+Z) traz de volta.'); return; }
  if (!S.joints.length && !sep && !livres) { setStatus('Nada para exportar: posicione juntas (aba Juntas), marque áreas para separar, desenhe um corte livre ou crie um plano (aba Cortes).'); return; }
  if (window.flexiFree) window.flexiFree.close();
  if (S.splitting && window.flexiSplit) window.flexiSplit.close();
  const btn = $('#btn-export');
  btn.disabled = true;
  S.exporting = true;
  $('#dl-box').classList.add('hidden');          // files of the previous export are not these
  $('#report').innerHTML = '';
  setStatus(S.joints.length && sep ? 'Exportando juntas e peças por cor…' : sep ? 'Exportando as peças por cor…' : 'Exportando…');
  const t0 = performance.now();
  const poll = setInterval(async () => {
    try { const s = await api('/api/status'); if (S.exporting) $('#progress').textContent = `Exportando… ${s.progress} (${((performance.now() - t0) / 1000).toFixed(0)} s)`; } catch (e) {}
  }, 800);
  try {
    await syncPaintNow();
    const projeto = { prepare: prepOpts(), separar: window.flexiSplit ? window.flexiSplit.state() : null,
                      livres: window.flexiFree ? window.flexiFree.state() : null };
    const conectores = window.flexiConectores ? window.flexiConectores.forExport() : [];
    const r = await post('/api/editor/export', Object.assign({ joints: S.joints.map(cleanJoint), clearance: clr(), force, separar: sep, livres, projeto, conectores }, printerBody()));
    clearInterval(poll);
    S.exporting = false;            // a status poll still in flight must not write over the result
    (r.juntas || []).forEach((q, k) => { if (S.joints[k]) { S.joints[k].checks = q.checks; S.joints[k].luz = q.luz; } });
    await renderJoints();
    renderReport(r);
    if (r.ok) {
      $('#progress').textContent = `${r.pecas} peças exportadas em ${nf(r.segundos, 0)} s.`;
      $('#progress').textContent += `  Salvo em: ${r.pasta}`;
      S.lastExportDir = r.pasta;
      const t = Date.now();
      $('#btn-dl3mf').href = '/api/export.3mf?t=' + t;
      $('#btn-dl3mf').setAttribute('download', r.arquivo3mf || 'modelo.3mf');
      $('#btn-dl').href = '/api/export.stl?t=' + t;
      $('#btn-dlzip').href = '/api/export.zip?t=' + t;
      renderFiles(r.arquivos || [], t, r.arquivo3mf);
      $('#dl-hint').textContent = r.modo === 'juntas_e_cortes'
        ? `${r.arquivo3mf}: corpo articulado e peças cortadas, prontos para imprimir, cada um no seu filamento. O STL montado não leva cores.`
        : r.modo === 'cortes'
          ? `${r.arquivo3mf}: as peças deitadas na posição de impressão, cada uma no seu filamento. O STL montado não leva cores.`
          : 'O 3MF leva as peças e as cores; é o arquivo para o Bambu Studio e o OrcaSlicer. O STL não leva cores.';
      $('#dl-box').classList.remove('hidden');
      S.exportPainted = !!r.pintado;
      S.mesa = r.mesa || null;
      await loadPieces(r.pecas);
      setView(true);
      // with separated parts, show them as they go on the bed (the articulated body stays together)
      showMesa(!!(S.mesa && (r.modo === 'cortes' || r.modo === 'juntas_e_cortes')));
      const what = r.modo === 'cortes' ? 'peças separadas' : r.modo === 'juntas_e_cortes' ? 'corpo articulado e peças separadas' : 'corpo articulado';
      const falhas = r.cortes ? r.cortes.regioes.filter((x) => !x.ok).length + (r.cortes.livres || []).filter((x) => !x.ok).length : 0;
      setStatus(`Exportado (${what}): 3MF, STLs separados e relatório na pasta indicada.` +
        (falhas ? ` Atenção: ${falhas} corte(s) não feito(s), veja os itens vermelhos no relatório.` : '') +
        (semPintura ? ' A pintura está vazia, então nada foi separado por cor (na aba Cores o ⌘Z traz a pintura de volta).' : ''));
    } else if (r.precisa_confirmar) {
      $('#progress').textContent = '';
      setStatus('Há juntas vermelhas. Confira e confirme se quer exportar mesmo assim.');
    } else if (r.bloqueado) {
      $('#progress').textContent = '';
      setStatus('Exportação bloqueada: a malha não passou em todos os testes.');
    } else {
      $('#progress').textContent = '';
      setStatus(r.msg || 'Não exportou: veja o relatório.');
    }
  } catch (e) {
    clearInterval(poll);
    $('#progress').textContent = '';
    setStatus('Erro: ' + e.message);
  } finally { btn.disabled = false; S.exporting = false; }
}
function renderFiles(list, t, main) {
  list = list.slice().sort((a, b) => (b.rel === main) - (a.rel === main));   // the main 3MF first
  const kb = (b) => b > 1048576 ? nf(b / 1048576, 1) + ' MB' : Math.max(1, Math.round(b / 1024)) + ' KB';
  $('#dl-files').innerHTML = list.map((f) => {
    const name = f.rel.split(/[\\/]/).pop();
    return `<li><span class="fn">${f.rel}${f.rel === main ? ' <b>(principal)</b>' : ''}</span><span class="sz">${kb(f.bytes)}</span>` +
      `<a href="/api/export/file?rel=${encodeURIComponent(f.rel)}&t=${t}" download="${name}" title="Baixar ${name}">⬇</a></li>`;
  }).join('');
  $('#dl-files-det').classList.toggle('hidden', !list.length);
}
function renderReport(r) {
  let h = '';
  if (r.precisa_confirmar) {
    h += `<div class="card warnbox"><b>Juntas vermelhas: ${r.vermelhas.map((k) => 'J' + (k + 1)).join(', ')}</b>
      <p class="hint">Vermelho avisa, não bloqueia. Se você conferiu e quer assim, exporte mesmo assim. Fica registrado no relatório.</p>
      <button class="btn primary" id="btn-force">Exportar mesmo assim</button></div>`;
  }
  if (r.testes) {
    const ok = r.testes.every((t) => t.ok);
    h += `<h4>Qualidade da malha ${ok ? '✅' : '❌'}</h4><ul class="checks">` +
      r.testes.map((t) => `<li class="${t.ok ? 'ok' : 'erro'}">${t.ok ? '✅' : '❌'} ${t.texto}</li>`).join('') + '</ul>';
    if (!ok) h += '<p class="hint">A exportação só sai com todos os testes de malha passando. Ajuste a junta indicada (escala, limites ou posição) e exporte de novo.</p>';
  }
  if (r.cores) {
    h += `<h4>Cores ${r.cores.conferido ? '✅' : '❌'}</h4><p class="hint">${r.cores.arquivo3mf} (e .obj + .mtl) com os filamentos ` +
      r.cores.filamentos.map((f, i) => `${f} <span class="swatch" style="background:${r.cores.cores[i]}"></span>`).join(', ') +
      '. Abra o .3mf no Bambu Studio ou OrcaSlicer: cada parte pintada já vem no filamento certo.</p>';
  }
  if (r.conflitos && r.conflitos.length) {
    h += '<h4>Juntas e cortes ⚠️</h4><ul class="checks">' + r.conflitos.map((c) => `<li class="aviso">🟡 ${c}</li>`).join('') + '</ul>';
  }
  if (r.placas) {
    const av = r.avisos_placa || [];
    h += `<h4>Placas: ${r.impressora} ${av.length ? '⚠️' : '✅'}</h4><ul class="checks">` +
      r.placas.map((p) => `<li>🟫 Placa ${p.placa}: ${p.itens.join(', ')}</li>`).join('') +
      av.map((a) => `<li class="aviso">🟡 ${a}</li>`).join('') + '</ul>' +
      '<p class="hint">Cada placa sai como um 3MF em placas/, com as peças já dentro da mesa e na posição de impressão.</p>';
  }
  if (r.malha_stl && r.malha_stl.length) {
    const ruins = r.malha_stl.filter((m) => !m.ok);
    h += `<h4>Malha dos arquivos ${ruins.length ? '⚠️' : '✅'}</h4><p class="hint">` + (ruins.length
      ? 'Com erro: ' + ruins.map((m) => `${m.nome} (${m.abertas} arestas abertas, ${m.multiplas} com 3+ faces)`).join('; ') + '.'
      : `${r.malha_stl.length} peça(s) conferidas como o fatiador lê o STL: fechadas, sem arestas com 3 ou mais faces e sem triângulos degenerados.`) + '</p>';
  }
  if (r.impressao && r.impressao.length) {
    const cm = (v) => nf(v, 1) + ' cm²';
    h += '<h4>Na mesa: posição e suporte</h4><ul class="checks">' + r.impressao.map((o) => {
      const semSup = o.suporte_cm2 < 0.5;
      const ic = semSup && !o.brim ? '✅' : '🟡';
      return `<li class="${semSup && !o.brim ? 'ok' : 'aviso'}">${ic} ${o.nome}: ${semSup ? 'sem suporte' : 'suporte em cerca de ' + cm(o.suporte_cm2)}; ` +
        `apoio na mesa ${cm(o.contato_cm2)}${o.brim ? '; 🧱 use brim (aba) nesta peça' : ''}` +
        `${o.mudou ? ' · ↻ posição escolhida para menos suporte' : ''}${o.fixa ? ' · ⬆ fica de pé como no modelo' : ''}</li>`;
    }).join('') + '</ul><p class="hint">Estimativa para PLA: face virada para baixo a mais de 45° da parede pede suporte. ' +
      'Ative a compensação de pé de elefante no fatiador para os encaixes que ficam na face da mesa.</p>';
  }
  if (r.cortes && r.cortes.livres && r.cortes.livres.length) {
    const grp = (lst, t) => lst.length ? `<h4>${t}</h4><ul class="checks">` + lst.map((x) => {
      const prob = x.checks.filter((c) => c.nivel !== 'ok').map((c) => c.texto).join(' ');
      return `<li class="${x.luz}">${LUZ[x.luz]} ${x.nome}: ${x.ok ? 'cortado' : 'não cortado'}${prob ? '. ' + prob : ''}</li>`;
    }).join('') + '</ul>' : '';
    h += grp(r.cortes.livres.filter((x) => !x.plano), 'Corte livre') + grp(r.cortes.livres.filter((x) => x.plano), 'Corte plano');
  }
  if (r.cortes && r.cortes.regioes.length) {
    h += '<h4>Peças por cor</h4><ul class="checks">' + r.cortes.regioes.slice().sort((a, b) => a.id - b.id).map((x) => {
      const prob = x.checks.filter((c) => c.nivel !== 'ok').map((c) => c.texto).join(' ');
      return `<li class="${x.luz}">${LUZ[x.luz]} Área ${x.id + 1}: ${x.ok ? 'cortada' : 'não cortada'}${prob ? '. ' + prob : ''}</li>`;
    }).join('') + '</ul>';
    if (r.cortes.malha) h += `<p class="hint">Malha: ${nf(r.cortes.malha.pct, 2)}% dos triângulos originais idênticos; o resto mudou só na borda dos cortes.</p>`;
  }
  if (r.juntas) {
    h += '<h4>Juntas</h4><ul class="checks">' + r.juntas.map((q, k) => {
      const prob = q.checks.filter((c) => c.nivel !== 'ok').map((c) => c.texto).join(' ');
      return `<li class="${q.luz}">${LUZ[q.luz]} J${k + 1}${prob ? ': ' + prob : ''}</li>`;
    }).join('') + '</ul>';
  }
  $('#report').innerHTML = h;
  const f = $('#btn-force');
  if (f) f.onclick = () => doExport(true);
}
async function loadPieces(n) {
  S.pieces.forEach((m) => m.geometry.dispose());
  S.pieces = []; clearGroup(S.pieceGroup);
  for (let i = 0; i < n; i++) {
    const g = loader.parse(await api('/api/piece.stl?i=' + i));
    g.computeVertexNormals();
    g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(g.attributes.position.count * 3), 3));
    const m = new THREE.Mesh(g, solidMat());
    g.computeBoundingBox();
    try {
      const r = await api('/api/piece_paint?i=' + i);
      const u = unb64(r.pintura);
      if (u.length === g.attributes.position.count / 3) { m.userData.paint = u; m.userData.palette = r.paleta; }
    } catch (e) { /* older export: piece colours */ }
    const div = document.createElement('div');
    div.className = 'lbl piece'; div.textContent = 'P' + (i + 1);
    const lab = new CSS2DObject(div);
    const c = g.boundingBox.getCenter(new THREE.Vector3());
    lab.position.set(c.x, c.y, g.boundingBox.max.z + 3);
    m.add(lab);
    m.matrixAutoUpdate = false;                 // posição: base (montado ou na mesa) + afastamento arrastado
    m.userData.baseM = new THREE.Matrix4();
    m.updateMatrix();
    S.pieceGroup.add(m);
    S.pieces.push(m);
  }
  S.pcol = S.exportPainted ? 'pintura' : 'peca';
  $('#pcol-seg').classList.toggle('hidden', !S.exportPainted);
  document.querySelectorAll('[data-pcol]').forEach((b) => b.classList.toggle('on', b.dataset.pcol === S.pcol));
  colorPieces();
}
// ---------------------------------------------------------------- pieces on the bed
function showMesa(on) {
  const ok = !!(S.mesa && S.mesa.pecas && S.mesa.pecas.length === S.pieces.length);
  $('#mesa-seg').classList.toggle('hidden', !ok);
  on = on && ok;
  S.onMesa = on;
  document.querySelectorAll('[data-mesa]').forEach((b) => b.classList.toggle('on', (b.dataset.mesa === 'mesa') === on));
  clearGroup(bedGroup);
  S.pieces.forEach((m, i) => {
    const a = on ? S.mesa.pecas[i] : null;
    m.matrixAutoUpdate = false;
    m.userData.baseM = a ? new THREE.Matrix4().set(a[0][0], a[0][1], a[0][2], a[0][3], a[1][0], a[1][1], a[1][2], a[1][3], a[2][0], a[2][1], a[2][2], a[2][3], 0, 0, 0, 1)
      : new THREE.Matrix4();
    placePiece(m);
  });
  grid.visible = !on;
  if (on) {
    const pr = S.mesa.impressora || { x: 256, y: 256, nome: '' };
    for (let k = 0; k < (S.mesa.placas || 1); k++) {
      const x0 = k * (pr.x + 30);
      const g = new THREE.BufferGeometry();
      const sq = [x0, 0, 0, x0 + pr.x, 0, 0, x0 + pr.x, 0, 0, x0 + pr.x, pr.y, 0, x0 + pr.x, pr.y, 0, x0, pr.y, 0, x0, pr.y, 0, x0, 0, 0];
      for (let t = 10; t < pr.x; t += 10) sq.push(x0 + t, 0, 0, x0 + t, pr.y, 0);
      for (let t = 10; t < pr.y; t += 10) sq.push(x0, t, 0, x0 + pr.x, t, 0);
      g.setAttribute('position', new THREE.Float32BufferAttribute(sq, 3));
      bedGroup.add(new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: isDark() ? 0x3a3f45 : 0xb8b2a6 })));
      const plate = new THREE.Mesh(new THREE.PlaneGeometry(pr.x, pr.y), new THREE.MeshBasicMaterial({ color: isDark() ? 0x1d2024 : 0xdcd7cc, transparent: true, opacity: 0.6, depthWrite: false }));
      plate.position.set(x0 + pr.x / 2, pr.y / 2, -0.05);
      bedGroup.add(plate);
      const div = document.createElement('div');
      div.className = 'lbl'; div.textContent = `Placa ${k + 1} · ${pr.nome || ''}`;
      const lab = new CSS2DObject(div); lab.position.set(x0 + pr.x / 2, -6, 0); bedGroup.add(lab);
    }
    const n = S.mesa.placas || 1, W = n * (pr.x + 30) - 30;
    const c = new THREE.Vector3(W / 2, pr.y / 2, 0), r = Math.max(W, pr.y) * 0.75;
    camera.position.set(c.x + r * 0.2, c.y - r * 1.3, c.z + r * 1.1);
    controls.target.copy(c); camera.lookAt(c);
    setStatus('Peças na mesa, como no 3MF: cada parte cortada separada e na posição de impressão; o corpo articulado fica inteiro.');
  } else if (S.showPieces) fitCamera('iso');
}
document.querySelectorAll('[data-mesa]').forEach((b) => b.addEventListener('click', () => showMesa(b.dataset.mesa === 'mesa')));

// Peças exportadas: arraste uma peça para afastá-la e ver melhor (só na vista; não muda os arquivos).
// Cada vista (Montado / Na mesa) guarda o próprio afastamento. ↺ Repor volta tudo ao lugar.
function pieceOff(m) {
  const k = S.onMesa ? 'mesa' : 'montado';
  m.userData.off = m.userData.off || {};
  return (m.userData.off[k] = m.userData.off[k] || new THREE.Vector3());
}
function placePiece(m) {
  const off = pieceOff(m);
  m.matrix.copy(new THREE.Matrix4().makeTranslation(off.x, off.y, off.z).multiply(m.userData.baseM || new THREE.Matrix4()));
  m.matrixWorldNeedsUpdate = true;
}
let pdrag = null;
host.addEventListener('pointerdown', (e) => {
  if (!S.showPieces || e.button !== 0 || !S.pieces.length) return;
  ray.setFromCamera(ndc(e), camera);
  const hit = ray.intersectObjects(S.pieces, false)[0];
  if (!hit) return;
  const m = hit.object;
  pdrag = { m, plane: new THREE.Plane(new THREE.Vector3(0, 0, 1), -hit.point.z), p0: hit.point.clone(), off0: pieceOff(m).clone(), lift: e.shiftKey };
  if (e.shiftKey) {                       // Shift + arrastar: sobe e desce
    const n = new THREE.Vector3().subVectors(camera.position, hit.point); n.z = 0; n.normalize();
    pdrag.plane = new THREE.Plane().setFromNormalAndCoplanarPoint(n, hit.point);
  }
  controls.enabled = false;
  host.setPointerCapture?.(e.pointerId);
  e.stopPropagation(); e.preventDefault();
}, true);
host.addEventListener('pointermove', (e) => {
  if (!pdrag) {
    if (S.showPieces && e.buttons === 0 && S.pieces.length) {
      ray.setFromCamera(ndc(e), camera);
      renderer.domElement.style.cursor = ray.intersectObjects(S.pieces, false).length ? 'grab' : '';
    }
    return;
  }
  ray.setFromCamera(ndc(e), camera);
  const q = new THREE.Vector3();
  if (!ray.ray.intersectPlane(pdrag.plane, q)) return;
  const d = q.sub(pdrag.p0);
  if (!pdrag.lift) d.z = 0; else { d.x = 0; d.y = 0; }
  pieceOff(pdrag.m).copy(pdrag.off0).add(d);
  placePiece(pdrag.m);
  renderer.domElement.style.cursor = 'grabbing';
  e.stopPropagation();
}, true);
function endPieceDrag() {
  if (!pdrag) return;
  pdrag = null; controls.enabled = true;
  renderer.domElement.style.cursor = '';
  setStatus('Peça afastada só na vista (os arquivos não mudam). ↺ Repor posições volta tudo ao lugar.');
}
host.addEventListener('pointerup', endPieceDrag, true);
host.addEventListener('pointercancel', endPieceDrag, true);
$('#pc-reset').onclick = () => { S.pieces.forEach((m) => { m.userData.off = {}; placePiece(m); }); setStatus('Peças de volta ao lugar.'); };

function colorPieces() {
  const ov = $('#t-ov').checked;
  S.pieces.forEach((m, i) => {
    const g = m.geometry;
    if (S.pcol === 'pintura' && m.userData.paint) {
      const pal = (m.userData.palette && m.userData.palette.length ? m.userData.palette : S.palette).map(hexRGB);
      const a = g.attributes.color.array, pos = g.attributes.position.array, P = m.userData.paint;
      const red = [0.878, 0.192, 0.165];
      for (let t = 0; t < P.length; t++) {
        let c = pal[P[t] - 1] || pal[0];
        if (ov) {
          const o = t * 9;
          const ux = pos[o + 3] - pos[o], uy = pos[o + 4] - pos[o + 1], uz = pos[o + 5] - pos[o + 2];
          const vx = pos[o + 6] - pos[o], vy = pos[o + 7] - pos[o + 1], vz = pos[o + 8] - pos[o + 2];
          const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
          const l = Math.hypot(nx, ny, nz) || 1;
          if (nz / l < -0.72 && (pos[o + 2] + pos[o + 5] + pos[o + 8]) / 3 > 0.3) c = red;
        }
        for (let k = 0; k < 3; k++) { const q = (t * 3 + k) * 3; a[q] = c[0]; a[q + 1] = c[1]; a[q + 2] = c[2]; }
      }
      g.attributes.color.needsUpdate = true;
    } else {
      colorize(g, PIECE_COLORS[i % PIECE_COLORS.length], ov);
      g.attributes.color.needsUpdate = true;
    }
  });
}
document.querySelectorAll('[data-pcol]').forEach((b) => b.addEventListener('click', () => {
  S.pcol = b.dataset.pcol;
  document.querySelectorAll('[data-pcol]').forEach((x) => x.classList.toggle('on', x === b));
  colorPieces();
}));

// ---------------------------------------------------------------- coupon
$('#btn-cupom').onclick = async () => {
  const j = S.joints[S.sel] || { tipo: $('#cut-type').value, pos: [0, 0, 0], rot: [0, 0, 0], escala: [0.45, 0.35, 0.35], borda: false, limites: null };
  const btn = $('#btn-cupom');
  btn.disabled = true;
  const t0 = performance.now();
  const timer = setInterval(async () => {
    try { const s = await api('/api/status'); $('#progress').textContent = `Cupom… ${s.progress} (${((performance.now() - t0) / 1000).toFixed(0)} s)`; } catch (e) {}
  }, 1000);
  try {
    const r = await post('/api/editor/coupon', { joint: cleanJoint(j) });
    const ok = r.report.amostras.filter((x) => x.presa).length;
    $('#progress').textContent = `Cupom (${r.report.peca}, escala ${r.report.escala.map((v) => nf(v)).join(' × ')}) salvo em ${r.folder}: ${ok} de ${r.report.amostras.length} amostras ok. Veja o LEIA.txt.`;
    setStatus('Cupom de calibração pronto.');
  } catch (e) {
    $('#progress').textContent = 'Erro ao gerar o cupom: ' + e.message;
  } finally { clearInterval(timer); btn.disabled = false; }
};

// ---------------------------------------------------------------- project
// Save: overwrites the project that is open; the first time (or "Salvar como…") asks where.
async function nativeDialog(tipo, nome = '') {
  // Mac app window: its own dialogs; browser: the server asks macOS (AppleScript)
  try {
    const A = window.pywebview && window.pywebview.api;
    if (A) {
      const ini = S.outDir || '';
      const p = tipo === 'pasta' ? await A.escolher_pasta(ini) : tipo === 'salvar' ? await A.salvar_como(nome, ini) : await A.abrir(ini);
      return { path: p || '', cancelado: !p };
    }
  } catch (e) { /* fall back to the server dialog */ }
  try {
    const r = await post('/api/dialog', { tipo, nome });
    if (r.indisponivel) return { indisponivel: true };
    return { path: r.path || '', cancelado: !r.path };
  } catch (e) { return { indisponivel: true }; }
}
// Janela do app no Mac: o WebKit não grava por cima de um arquivo que já existe, mesmo com "Substituir".
// Os links de baixar viram: diálogo nativo para o caminho e o servidor grava (substituindo).
document.addEventListener('click', async (e) => {
  const a = e.target.closest && e.target.closest('a[href^="/api/"]');
  const A = window.pywebview && window.pywebview.api;
  if (!a || !A || !A.salvar_como || !/Mac/i.test(navigator.platform || navigator.userAgent)) return;
  if (!a.hasAttribute('download') && !/^\/api\/export[./]/.test(a.getAttribute('href'))) return;
  e.preventDefault();
  e.stopPropagation();
  try {
    setStatus('Preparando o arquivo…');
    const r = await post('/api/download/prepare', { url: a.getAttribute('href') });
    const nome = a.getAttribute('download') || r.nome;
    const path = await A.salvar_como(nome, S.lastExportDir || S.outDir || '');
    if (!path) { setStatus('Download cancelado.'); return; }
    const w = await post('/api/download/save', { token: r.token, path });
    setStatus('Arquivo salvo em ' + w.path);
  } catch (err) { setStatus('Erro ao salvar o arquivo: ' + err.message); }
}, true);
async function saveProject(como = false) {
  if (!S.base) { setStatus('Carregue um modelo primeiro.'); return; }
  let path = '';
  if (como || !S.projPath) {
    const nome = (($('#drop-text').textContent || 'modelo').replace(/\.(stl|flexiproj|json)$/i, '')) + '.flexiproj';
    const d = await nativeDialog('salvar', nome);
    if (d.cancelado) { setStatus('Salvar cancelado.'); return; }
    if (!d.indisponivel) path = d.path;
  }
  try {
    await syncPaintNow();
    const separar = window.flexiSplit ? window.flexiSplit.state() : null;
    const livres = window.flexiFree ? window.flexiFree.state() : null;
    const r = await post('/api/project/save', { joints: S.joints.map(cleanJoint), clearance: clr(), prepare: prepOpts(), path, como, separar, livres });
    S.projPath = r.path;
    $('#save-info').textContent = 'Projeto salvo em:\n' + r.path;
    setStatus('Projeto salvo (modelo, juntas e cores vão juntos no arquivo). ⌘S salva de novo no mesmo arquivo.');
  } catch (e) { setStatus('Erro ao salvar: ' + e.message); }
}
$('#btn-proj-save').onclick = () => saveProject(false);
$('#btn-proj-saveas').onclick = () => saveProject(true);
// One "Abrir…" for models and projects (decided by the extension), plus the recent list.
async function openPath(path) {
  const nome = path.split(/[\\/]/).pop();
  hideRecent();
  if (/\.(flexiproj|json)$/i.test(path)) {
    setStatus('Abrindo projeto…');
    try {
      const r = await post('/api/project/open_path', { path });
      await afterProjectOpen(r, nome);
      S.projPath = r.path;
      $('#save-info').textContent = 'Projeto aberto:\n' + r.path;
    } catch (e) { setStatus('Erro ao abrir projeto: ' + e.message); }
    return;
  }
  setStatus(`Lendo ${nome}… (modelos de IA grandes levam até 1 minuto)`);
  try {
    const r = await post('/api/load_path', { path });
    await afterModelLoad(r, nome);
    $('#save-info').textContent = '';
  } catch (e) { setStatus('Erro: ' + e.message); $('#model-info').textContent = '❌ ' + e.message; }
}
$('#btn-open').onclick = async () => {
  const d = await nativeDialog('abrir');
  if (d.indisponivel) { fileIn.click(); return; }
  if (d.cancelado) return;
  openPath(d.path);
};
const recentMenu = $('#recent-menu');
function hideRecent() { recentMenu.classList.add('hidden'); $('#btn-recent').setAttribute('aria-expanded', 'false'); }
async function showRecent() {
  let lst = [];
  try { lst = (await api('/api/recentes')).recentes || []; } catch (e) { /* empty list */ }
  recentMenu.innerHTML = '';
  if (!lst.length) {
    recentMenu.innerHTML = '<div class="rempty">Nenhum arquivo recente ainda. Projetos que você abrir ou salvar, e modelos abertos por "Abrir…", aparecem aqui.</div>';
  }
  lst.forEach((it) => {
    const b = document.createElement('button');
    b.className = 'ri'; b.setAttribute('role', 'menuitem'); b.title = it.path;
    const tipo = it.tipo === 'modelo' ? 'modelo' : 'projeto';
    b.innerHTML = `<span class="rn"><span class="rt"></span></span><span class="rd"></span>`;
    b.querySelector('.rt').textContent = tipo;
    b.querySelector('.rn').append(it.nome);
    b.querySelector('.rd').textContent = (it.quando ? it.quando + ' · ' : '') + it.pasta.replace(/^\/Users\/[^/]+/, '~').replace(/^[A-Za-z]:\\Users\\[^\\]+/, '%USERPROFILE%');
    b.onclick = () => openPath(it.path);
    recentMenu.append(b);
  });
  if (lst.length) {
    const f = document.createElement('div'); f.className = 'rfoot';
    const c = document.createElement('button'); c.className = 'btn'; c.textContent = 'Limpar lista';
    c.onclick = async () => { try { await post('/api/recentes/limpar', {}); } catch (e) { /* ignore */ } showRecent(); };
    f.append(c); recentMenu.append(f);
  }
  recentMenu.classList.remove('hidden');
  $('#btn-recent').setAttribute('aria-expanded', 'true');
}
$('#btn-recent').onclick = (e) => { e.stopPropagation(); if (recentMenu.classList.contains('hidden')) showRecent(); else hideRecent(); };
document.addEventListener('click', (e) => { if (!recentMenu.contains(e.target) && e.target.id !== 'btn-recent') hideRecent(); });
window.addEventListener('keydown', (e) => { if (e.key === 'Escape') hideRecent(); });
window.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') { e.preventDefault(); saveProject(e.shiftKey); }
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'o') { e.preventDefault(); $('#btn-open').click(); }
});
$('#proj-file').onchange = () => { const f = $('#proj-file').files[0]; if (f) openProjectFile(f); $('#proj-file').value = ''; };
async function openProjectFile(f) {
  setStatus('Abrindo projeto…');
  try {
    const d = JSON.parse(await f.text());
    const r = await post('/api/project/open', d);
    await afterProjectOpen(r, f.name);
    S.projPath = null;
  } catch (e) { setStatus('Erro ao abrir projeto: ' + e.message); }
}
async function afterProjectOpen(r, label) {
  await loadLibrary();
  $('#tex-box').classList.add('hidden');
  $('#drop-text').textContent = label;
  $('#clr').value = r.clearance;
  clearResult(); clearPreview();
  showInfo(r.info, []);
  await showBase();
  S.joints = r.joints.map(newFromServer);
  S.sel = S.joints.length ? 0 : -1;
  await renderJoints();
  if (window.flexiSplit) window.flexiSplit.restore(r.separar || null);
  if (window.flexiFree) window.flexiFree.restore(r.livres || null);
  const av = r.avisos_juntas || [];
  setStatus(`Projeto "${r.nome}" aberto com ${S.joints.length} junta(s). Clique em "Verificar todas".` +
    (av.length ? ` ${av.length} junta(s) trocada(s) pela junta própria: ${av.join(' ')}` : ''));
}

// theme: Claro / Auto / Escuro (saved on this Mac, in the app config and in the window)
function applyTheme(t, save = true) {
  if (!['light', 'dark', 'auto'].includes(t)) t = 'auto';
  if (t === 'auto') delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = t;
  document.querySelectorAll('[data-theme-set]').forEach((b) => { const on = b.dataset.themeSet === t; b.classList.toggle('on', on); b.setAttribute('aria-pressed', on); });
  renderer.setClearColor(isDark() ? 0x121416 : 0xe9e7e1, 1);
  makeGrid();
  if (S.onMesa && typeof showMesa === 'function') { try { showMesa(true); } catch (e) { /* keep going */ } }
  if (save) {
    try { localStorage.setItem('flexi-tema', t); } catch (e) { /* private window */ }
    post('/api/config', { tema: t }).catch(() => {});
  }
}
document.querySelectorAll('[data-theme-set]').forEach((b) => b.addEventListener('click', () => applyTheme(b.dataset.themeSet)));
if (sysDark) {
  const onSys = () => { if (!document.documentElement.dataset.theme) applyTheme('auto', false); };
  if (sysDark.addEventListener) sysDark.addEventListener('change', onSys); else if (sysDark.addListener) sysDark.addListener(onSys);
}
(() => { let t = null; try { t = localStorage.getItem('flexi-tema'); } catch (e) { /* none */ } applyTheme(t || 'auto', false); })();

// output folder
async function loadConfig() {
  try {
    const c = await api('/api/config');
    S.outDir = c.pasta_saida;
    let lt = null; try { lt = localStorage.getItem('flexi-tema'); } catch (e) { /* none */ }
    if (!lt && c.tema) applyTheme(c.tema, false);       // window storage empty: use the app config
    if (c.impressoras) {
      const sel = $('#printer');
      sel.innerHTML = c.impressoras.map((p) => `<option value="${p.id}">${p.nome} (${p.x} × ${p.y} × ${p.z} mm)</option>`).join('') +
        '<option value="custom">Personalizada…</option>';
      sel.value = c.impressora || 'a1';
      const cu = c.impressora_custom || {};
      $('#pc-x').value = cu.x || ''; $('#pc-y').value = cu.y || ''; $('#pc-z').value = cu.z || '';
      $('#printer-custom').classList.toggle('hidden', sel.value !== 'custom');
    }
    $('#out-dir').textContent = c.pasta_saida + (c.pasta_saida === c.padrao ? '  (padrão)' : '');
  } catch (e) { /* server starting */ }
}
$('#out-change').onclick = async () => {
  const d = await nativeDialog('pasta');
  let p = d.path;
  if (d.indisponivel) p = window.prompt('Caminho da pasta onde salvar:', S.outDir || '');
  if (!p) return;
  try {
    const r = await post('/api/config', { pasta_saida: p });
    await loadConfig();
    setStatus('Pasta de saída: ' + r.pasta_saida);
  } catch (e) { setStatus('Não consegui usar essa pasta: ' + e.message); }
};
function printerBody() {
  const id = $('#printer').value || 'a1';
  return { impressora: id, impressora_custom: id === 'custom' ? { x: +$('#pc-x').value || 0, y: +$('#pc-y').value || 0, z: +$('#pc-z').value || 0 } : null };
}
async function savePrinter() {
  $('#printer-custom').classList.toggle('hidden', $('#printer').value !== 'custom');
  try { await post('/api/config', printerBody()); } catch (e) { setStatus('Erro: ' + e.message); }
  if (S.pieces.length) setStatus('Impressora mudou: exporte de novo para refazer as placas.');
}
$('#printer').onchange = savePrinter;
['#pc-x', '#pc-y', '#pc-z'].forEach((id) => $(id).addEventListener('change', savePrinter));
$('#out-default').onclick = async () => {
  try { await post('/api/config', { pasta_saida: '' }); await loadConfig(); setStatus('Pasta de saída voltou para a padrão.'); }
  catch (e) { setStatus('Erro: ' + e.message); }
};
loadConfig();

// last session (joints only; the model must be the same one)
const SESSION_KEY = 'flexi_sessao_v4';
let canPersist = false;
function persist() {
  if (!canPersist || !S.base) return;
  try { localStorage.setItem(SESSION_KEY, JSON.stringify({ clearance: clr(), joints: S.joints.map(cleanJoint), modelo: $('#drop-text').textContent })); } catch (e) {}
}
try {
  const p = JSON.parse(localStorage.getItem(SESSION_KEY) || 'null');
  if (p && p.joints && p.joints.length) {
    $('#btn-restore').classList.remove('hidden');
    $('#btn-restore').textContent = `Restaurar juntas (${p.modelo || 'sessão anterior'})`;
    $('#btn-restore').onclick = async () => {
      if (!S.base) { setStatus('Abra o mesmo modelo primeiro, depois restaure as juntas.'); return; }
      S.joints = p.joints.map(newFromServer); S.sel = 0;
      if (p.clearance) $('#clr').value = p.clearance;
      $('#btn-restore').classList.add('hidden');
      await renderJoints();
      setStatus('Juntas da sessão anterior restauradas. Verifique de novo.');
    };
  }
} catch (e) {}
setTimeout(() => { canPersist = true; }, 0);
$('#clr').addEventListener('change', () => { S.joints.forEach((j) => { j.luz = 'nada'; j.checks = null; }); renderJoints(); setStatus('Folga mudou: verifique as juntas de novo.'); });

api('/api/status').then((s) => { $('#versao').textContent = 'versão ' + (s.versao || '?'); }).catch(() => {});
loadLibrary().catch((e) => setStatus('Erro ao ler a biblioteca de peças de corte: ' + e.message));
initPrompts();

// ---------------------------------------------------------------- colours (painting)
// One filament number per triangle of the model (1 = base filament). Tools like OrcaSlicer and
// Bambu Studio: brush, bucket (smart fill by angle) and height band (exact edge on the server).
const DEFAULT_PALETTE = ['#cfc8bc', '#d9622b', '#2b6fd9', '#2f8f3f'];
const EXTRA_COLOURS = ['#f2c14e', '#1f2328', '#ffffff', '#c2417a', '#17a2b8', '#8c564b', '#6a5acd', '#6f9a2b', '#e0312a', '#7f7f7f', '#b5651d', '#9467bd'];
S.palette = (() => { try { const p = JSON.parse(localStorage.getItem('flexi_paleta') || 'null'); return Array.isArray(p) && p.length >= 2 ? p : DEFAULT_PALETTE.slice(); } catch (e) { return DEFAULT_PALETTE.slice(); } })();
S.curColor = 2;
S.paint = null;
S.painting = false;
S.tool = 'brush';
S.undo = [];
let tri = null;          // centres, normals, overhang flags of the base triangles
let vgraph = null;       // vertex graph for the contour tool, built on first use
let adj = null;          // neighbour triangles (bucket), built on first use

function baseTriData(g) {
  const pos = g.attributes.position.array;
  const n = pos.length / 9;
  const cen = new Float32Array(n * 3), nrm = new Float32Array(n * 3), ov = new Uint8Array(n);
  for (let t = 0; t < n; t++) {
    const o = t * 9;
    const ax = pos[o], ay = pos[o + 1], az = pos[o + 2], bx = pos[o + 3], by = pos[o + 4], bz = pos[o + 5], cx = pos[o + 6], cy = pos[o + 7], cz = pos[o + 8];
    cen[t * 3] = (ax + bx + cx) / 3; cen[t * 3 + 1] = (ay + by + cy) / 3; cen[t * 3 + 2] = (az + bz + cz) / 3;
    const ux = bx - ax, uy = by - ay, uz = bz - az, vx = cx - ax, vy = cy - ay, vz = cz - az;
    let nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    const l = Math.hypot(nx, ny, nz) || 1;
    nx /= l; ny /= l; nz /= l;
    nrm[t * 3] = nx; nrm[t * 3 + 1] = ny; nrm[t * 3 + 2] = nz;
    ov[t] = nz < -0.72 && cen[t * 3 + 2] > 0.3 ? 1 : 0;
  }
  tri = { n, cen, nrm, ov };
  if (typeof clearFillPreview === "function") try { clearFillPreview(); } catch (e) {}
  adj = null;
  vgraph = null;
  if (typeof clearContours === 'function') try { clearContours(true); } catch (e) {}
}
const hexRGB = (h) => { const c = new THREE.Color(h); return [c.r, c.g, c.b]; };
function baseColorize(list = null) {
  if (!S.base || !tri) return;
  const col = S.base.geometry.attributes.color;
  const a = col.array;
  const rgb = S.palette.map(hexRGB);
  const red = [0.878, 0.192, 0.165];
  const showOv = $('#t-ov').checked;
  const one = (t) => {
    const c = showOv && tri.ov[t] ? red : (S.paintHide && S.paintHide[t] ? rgb[0] : (rgb[(S.paint ? S.paint[t] : 1) - 1] || rgb[0]));
    for (let k = 0; k < 3; k++) { const o = (t * 3 + k) * 3; a[o] = c[0]; a[o + 1] = c[1]; a[o + 2] = c[2]; }
  };
  if (list) list.forEach(one); else for (let t = 0; t < tri.n; t++) one(t);
  col.needsUpdate = true;
}
function b64(u8) { let s = ''; for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000)); return btoa(s); }
function unb64(s) { const b = atob(s); const u = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u; }
async function loadPaint() {
  S.paint = tri ? new Uint8Array(tri.n).fill(1) : null;
  try {
    const r = await api('/api/paint');
    if (r.paleta && r.paleta.length >= 2) S.palette = r.paleta;
    if (r.pintura && tri) { const u = unb64(r.pintura); if (u.length === tri.n) S.paint = u; }
  } catch (e) { /* no model yet */ }
  S.undo = [];
  renderPalette();
  syncPaint();
}
let syncTimer = null;
function syncPaint() { clearTimeout(syncTimer); syncTimer = setTimeout(syncPaintNow, 400); }
async function syncPaintNow() {
  clearTimeout(syncTimer);
  if (!S.paint || !S.base) return;
  try { localStorage.setItem('flexi_paleta', JSON.stringify(S.palette)); } catch (e) {}
  try { await post('/api/paint', { pintura: b64(S.paint), paleta: S.palette }); } catch (e) { setStatus('Erro ao guardar a pintura: ' + e.message); }
}
function pushUndo() { if (S.paint) { S.undo.push(S.paint.slice()); if (S.undo.length > 25) S.undo.shift(); } }

// palette
function renderPalette() {
  const box = $('#palette');
  if (!box) return;
  if (S.curColor > S.palette.length) S.curColor = S.palette.length;
  box.innerHTML = '';
  S.palette.forEach((c, i) => {
    const n = i + 1;
    const d = document.createElement('label');
    d.className = 'pal-item' + (n === S.curColor ? ' sel' : '');
    d.innerHTML = `<input type="radio" name="pal" ${n === S.curColor ? 'checked' : ''}><span class="pn">${n}</span><input type="color" value="${c}"><span>${n === 1 ? 'Base (sem pintura)' : 'Filamento ' + n}</span>`;
    d.querySelector('input[type=radio]').onchange = () => { S.curColor = n; renderPalette(); if (fillPrev) { const sd = fillPrev.seed; fillPrev = null; showFillPreview(sd); } };
    d.querySelector('input[type=color]').oninput = (e) => { S.palette[i] = e.target.value; baseColorize(); };
    d.querySelector('input[type=color]').onchange = () => syncPaint();
    box.appendChild(d);
  });
}
$('#pal-add').onclick = () => {
  if (S.palette.length >= 16) { setStatus('Máximo de 16 filamentos.'); return; }
  S.palette.push(EXTRA_COLOURS[(S.palette.length - 4 + EXTRA_COLOURS.length) % EXTRA_COLOURS.length]);
  S.curColor = S.palette.length;
  renderPalette(); syncPaint();
};
$('#pal-del').onclick = () => {
  if (S.palette.length <= 2) return;
  const last = S.palette.length;
  if (S.paint) { pushUndo(); for (let t = 0; t < S.paint.length; t++) if (S.paint[t] === last) S.paint[t] = 1; }
  S.palette.pop();
  renderPalette(); baseColorize(); syncPaint();
  setStatus(`Cor ${last} removida: o que estava pintado com ela voltou para a cor 1.`);
};

// paint mode
const ring = new THREE.Mesh(new THREE.RingGeometry(0.9, 1, 48), new THREE.MeshBasicMaterial({ color: 0xd9622b, side: THREE.DoubleSide, depthTest: false, transparent: true, opacity: 0.9 }));
ring.renderOrder = 30; ring.visible = false; scene.add(ring);
const bandPlanes = new THREE.Group(); bandPlanes.visible = false; scene.add(bandPlanes);
function setPainting(on) {
  if (on && !S.base) { setStatus('Carregue um modelo primeiro.'); return; }
  S.painting = on;
  $('#btn-paint').classList.toggle('active', on);
  $('#btn-paint').textContent = on ? '🖌 Pintando… (clique para concluir)' : '🖌 Pintar o modelo';
  $('#paint-box').classList.toggle('hidden', !on);
  if (on) { if (S.showPieces) setView(false); S.adding = false; $('#btn-add').classList.remove('active'); }
  setView(false);
  controls.mouseButtons.LEFT = on ? -1 : THREE.MOUSE.ROTATE;
  controls.mouseButtons.RIGHT = on ? THREE.MOUSE.ROTATE : THREE.MOUSE.PAN;
  ring.visible = false;
  clearFillPreview();
  updateBands();
  ctLine.visible = on;
  if (!on) { syncPaintNow(); renderJoints(); }
  setStatus(on ? 'Pintando: botão esquerdo pinta, Shift apaga, botão direito gira a vista.' : 'Pintura guardada.');
}
$('#btn-paint').onclick = () => setPainting(!S.painting);
$('#paint-done').onclick = () => setPainting(false);
function setTool(t) {
  S.tool = t;
  document.querySelectorAll('[data-tool]').forEach((b) => b.classList.toggle('on', b.dataset.tool === t));
  ['brush', 'fill', 'band', 'contour'].forEach((k) => $('#tool-' + k).classList.toggle('hidden', k !== (t === 'erase' ? 'brush' : t)));
  ring.material.color.set(t === 'erase' ? 0x2b6fd9 : 0xd9622b);
  if (t === 'erase') setStatus('Borracha: arraste para apagar a pintura (volta à cor 1); as linhas que ela tocar também saem. ⌘Z desfaz.');
  ring.visible = false;
  clearFillPreview();
  if (t === 'contour') setTimeout(() => { ensureVGraph(); setStatus('Linha: clique pontos em volta da área; a linha segue a superfície. Clique no primeiro ponto (ou Enter) para fechar.'); }, 30);
  if (t === 'fill') setTimeout(() => { ensureAdjacency(); setStatus('Balde: passe o mouse no modelo para ver a área; clique para pintar.'); }, 30);
  updateBands();
}
document.querySelectorAll('[data-tool]').forEach((b) => b.addEventListener('click', () => setTool(b.dataset.tool)));
const brushR = () => parseFloat($('#brush-r').value) || 3;
$('#brush-r').oninput = () => { $('#brush-v').textContent = nf(brushR(), 1) + ' mm'; };
$('#fill-a').oninput = () => { $('#fill-v').textContent = $('#fill-a').value + '°'; };

function updateBands() {
  clearGroup(bandPlanes);
  bandPlanes.visible = S.painting && S.tool === 'band' && !!S.baseBox;
  if (!bandPlanes.visible) return;
  const sz = S.baseBox.getSize(new THREE.Vector3()), c = S.baseBox.getCenter(new THREE.Vector3());
  for (const id of ['#band-z0', '#band-z1']) {
    const z = parseFloat($(id).value) || 0;
    const m = new THREE.Mesh(new THREE.PlaneGeometry(sz.x * 1.15, sz.y * 1.15),
      new THREE.MeshBasicMaterial({ color: 0xd9622b, transparent: true, opacity: 0.18, side: THREE.DoubleSide, depthWrite: false }));
    m.position.set(c.x, c.y, z);
    const e = new THREE.LineSegments(new THREE.EdgesGeometry(m.geometry), new THREE.LineBasicMaterial({ color: 0xd9622b }));
    e.position.copy(m.position);
    bandPlanes.add(m, e);
  }
}
['#band-z0', '#band-z1'].forEach((id) => $(id).addEventListener('input', updateBands));

// brush
function paintSphere(p, dir, erase) {
  const r2 = brushR() ** 2, col = erase ? 1 : S.curColor, vis = $('#brush-vis').checked;
  const changed = [];
  const { cen, nrm, n } = tri;
  for (let t = 0; t < n; t++) {
    const dx = cen[t * 3] - p.x, dy = cen[t * 3 + 1] - p.y, dz = cen[t * 3 + 2] - p.z;
    if (dx * dx + dy * dy + dz * dz > r2) continue;
    if (vis && nrm[t * 3] * dir.x + nrm[t * 3 + 1] * dir.y + nrm[t * 3 + 2] * dir.z > 0.15) continue;
    if (S.paint[t] !== col) { S.paint[t] = col; changed.push(t); }
  }
  if (changed.length) baseColorize(changed);
}
// Ocultar peças já recortadas (só na vista): a malha do modelo continua inteira para as linhas e a
// pintura (tudo segue gravado na superfície original); uma cópia sem os triângulos ocultos é a que
// aparece, e o clique atravessa o que está oculto.
let baseHid = null;
function setBaseHidden(mask) {
  if (!S.base) return 0;
  const g = S.base.geometry, n = g.attributes.position.count / 3;
  if (baseHid) {
    S.base.remove(baseHid.mesh);
    baseHid.mesh.geometry.setIndex(null);
    baseHid.mesh.geometry.dispose();
    delete S.base.raycast;
    g.setDrawRange(0, Infinity);
    baseHid = null;
  }
  if (!mask || mask.length !== n) return 0;
  let nv = 0;
  for (let t = 0; t < n; t++) if (!mask[t]) nv++;
  if (nv === n) return 0;
  const vis = new Uint32Array(nv), idx = new Uint32Array(nv * 3);
  for (let t = 0, j = 0; t < n; t++) if (!mask[t]) { vis[j] = t; idx[j * 3] = t * 3; idx[j * 3 + 1] = t * 3 + 1; idx[j * 3 + 2] = t * 3 + 2; j++; }
  const sg = new THREE.BufferGeometry();
  ['position', 'normal', 'color'].forEach((k) => { if (g.attributes[k]) sg.setAttribute(k, g.attributes[k]); });
  sg.setIndex(new THREE.BufferAttribute(idx, 1));
  sg.boundingBox = g.boundingBox; sg.boundingSphere = g.boundingSphere;
  const m = new THREE.Mesh(sg, S.base.material);
  m.raycast = () => {};                       // quem responde ao clique é o modelo (com o número do triângulo original)
  S.base.add(m);
  g.setDrawRange(0, 0);
  S.base.raycast = function (rc, out) {
    const tmp = [];
    THREE.Mesh.prototype.raycast.call(m, rc, tmp);
    for (const h of tmp) { h.faceIndex = vis[h.faceIndex]; h.object = S.base; out.push(h); }
  };
  baseHid = { mesh: m, n: n - nv };
  return n - nv;
}
function hitBase(e) { ray.setFromCamera(ndc(e), camera); return S.base ? ray.intersectObject(S.base)[0] : null; }
let stroke = null;
let spaceDown = false;
window.addEventListener('keydown', (e) => {
  if (!S.painting) return;
  if (document.activeElement && ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName) && document.activeElement.type !== 'range' && document.activeElement.type !== 'radio') return;
  if (e.code === 'Space' && !spaceDown) { spaceDown = true; controls.mouseButtons.LEFT = THREE.MOUSE.ROTATE; e.preventDefault(); }
  const k = e.key.toLowerCase();
  if ((e.metaKey || e.ctrlKey) && k === 'z') { e.preventDefault(); if (CT.pts.length) { CT.pts.pop(); CT.path.pop(); drawContours(); setStatus(CT.pts.length ? 'Último ponto da linha desfeito.' : 'Linha em andamento apagada.'); } else undoPaint(); return; }
  if (e.metaKey || e.ctrlKey) return;
  if (k === 'b') setTool('brush');
  if (k === 'f') setTool('fill');
  if (k === 'h') setTool('band');
  if (k === 'c' || k === 'l') setTool('contour');
  if (k === 'e') setTool('erase');
  if (S.tool === 'contour' && (e.key === 'Enter') && CT.pts.length) { e.preventDefault(); closeContour(); return; }
  if (e.key === 'Enter') { e.preventDefault(); setPainting(false); return; }
  if (S.tool === 'contour' && (e.key === 'Backspace')) { e.preventDefault(); undoContourPoint(); return; }
  if (k === '[' || k === ']') { $('#brush-r').value = Math.max(0.5, Math.min(20, brushR() + (k === ']' ? 0.5 : -0.5))); $('#brush-r').oninput(); }
  if (/^[1-9]$/.test(k) && +k <= S.palette.length) { S.curColor = +k; renderPalette(); }
  if (e.key === 'Escape') {
    if (S.tool === 'contour' && CT.pts.length) { CT.pts = []; CT.path = []; drawContours(); setStatus('Linha em andamento apagada.'); return; }
    setPainting(false);
  }
});
window.addEventListener('keyup', (e) => { if (e.code === 'Space' && spaceDown) { spaceDown = false; if (S.painting) controls.mouseButtons.LEFT = -1; } });
host.addEventListener('pointerdown', (e) => {
  if (!S.painting || e.button !== 0 || spaceDown) return;
  const h = hitBase(e);
  if (!h) return;
  e.stopPropagation(); e.preventDefault();
  if (S.tool === 'band') {
    const z = +h.point.z.toFixed(2);
    $(e.shiftKey ? '#band-z1' : '#band-z0').value = z;
    updateBands();
    setStatus(`${e.shiftKey ? 'Até' : 'De'} Z = ${nf(z, 2)} mm`);
    return;
  }
  if (S.tool === 'contour') { contourClick(h, e.shiftKey, e); return; }
  pushUndo();
  if (S.tool === 'fill') { bucket(h.faceIndex, e.shiftKey); syncPaint(); return; }
  const er = e.shiftKey || S.tool === 'erase';
  stroke = { last: h.point.clone(), erase: er };
  host.setPointerCapture?.(e.pointerId);
  paintSphere(h.point, ray.ray.direction, er);
  if (S.tool === 'erase') eraseContours(h.point);
}, true);
host.addEventListener('pointermove', (e) => {
  if (!S.painting) return;
  const h = ((S.tool === 'brush' || S.tool === 'erase') && !spaceDown) ? hitBase(e) : null;
  if (h) {
    const n = h.face.normal.clone().transformDirection(S.base.matrixWorld);
    ring.position.copy(h.point).add(n.clone().multiplyScalar(0.05));
    ring.lookAt(h.point.clone().add(n));
    ring.scale.setScalar(brushR());
    ring.visible = true;
  } else ring.visible = false;
  if (!stroke || !h) return;
  e.stopPropagation();
  const step = Math.max(0.3, brushR() / 2);
  const d = h.point.distanceTo(stroke.last);
  const k = Math.max(1, Math.ceil(d / step));
  for (let i = 1; i <= k; i++) paintSphere(stroke.last.clone().lerp(h.point, i / k), ray.ray.direction, stroke.erase || e.shiftKey);
  if (S.tool === 'erase') eraseContours(h.point);
  stroke.last.copy(h.point);
}, true);
const endStroke = () => { if (stroke) { stroke = null; syncPaint(); } };
host.addEventListener('pointerup', endStroke, true);
host.addEventListener('pointercancel', endStroke, true);
host.addEventListener('wheel', (e) => {
  if (!S.painting || !e.altKey) return;
  e.preventDefault(); e.stopPropagation();
  $('#brush-r').value = Math.max(0.5, Math.min(20, brushR() * (e.deltaY < 0 ? 1.1 : 1 / 1.1)));
  $('#brush-r').oninput();
  ring.scale.setScalar(brushR());
}, { capture: true, passive: false });

// bucket: neighbours by shared edges (vertices welded by position)
function buildAdjacency() {
  // neighbour across each edge of each triangle (-1 = open edge), vertices welded by position
  const pos = S.base.geometry.attributes.position.array;
  const vid = new Map(); let nv = 0;
  const id = new Int32Array(tri.n * 3);
  for (let i = 0; i < tri.n * 3; i++) {
    const key = `${Math.round(pos[i * 3] * 1e4)},${Math.round(pos[i * 3 + 1] * 1e4)},${Math.round(pos[i * 3 + 2] * 1e4)}`;
    let v = vid.get(key);
    if (v === undefined) { v = nv++; vid.set(key, v); }
    id[i] = v;
  }
  const edge = new Map();
  const nbE = new Int32Array(tri.n * 3).fill(-1);
  for (let t = 0; t < tri.n; t++) {
    for (let k = 0; k < 3; k++) {
      const a = id[t * 3 + k], b = id[t * 3 + (k + 1) % 3];
      const key = a < b ? a * 4194304 + b : b * 4194304 + a;
      const o = edge.get(key);
      if (o === undefined) edge.set(key, t * 3 + k);
      else { nbE[t * 3 + k] = (o / 3) | 0; nbE[o] = t; edge.delete(key); }
    }
  }
  adj = nbE;
  S.vid = id; S.nv = nv;            // welded vertex of each corner (the contour tool walks on them)
}
function ensureAdjacency() {
  if (!adj && tri) { setStatus('Preparando o balde (só na primeira vez)…'); buildAdjacency(); }
}
function fillParams() {
  return { ang: parseFloat($('#fill-a').value) || 30, same: $('#fill-same').checked, byDir: $('#fill-mode').value === 'direcao' };
}
function computeRegion(seed, prm) {
  // the triangles the bucket would paint from this seed: returns { list, mask }
  ensureAdjacency();
  const all = prm.ang >= 180;
  const cosT = Math.cos(THREE.MathUtils.degToRad(Math.min(179.9, prm.ang)));
  const from = S.paint[seed], N = tri.nrm;
  const mask = new Uint8Array(tri.n), q = new Int32Array(tri.n);
  let qh = 0, qt = 0;
  q[qt++] = seed; mask[seed] = 1;
  while (qh < qt) {
    const t = q[qh++];
    for (let k = 0; k < 3; k++) {
      const u = adj[t * 3 + k];
      if (u < 0 || mask[u]) continue;
      if (prm.same && S.paint[u] !== from) continue;
      const r0 = prm.byDir ? seed : t;   // compare with the clicked triangle, or with the neighbour
      const dot = N[r0 * 3] * N[u * 3] + N[r0 * 3 + 1] * N[u * 3 + 1] + N[r0 * 3 + 2] * N[u * 3 + 2];
      if (!all && dot < cosT) continue;
      mask[u] = 1; q[qt++] = u;
    }
  }
  return { list: q.subarray(0, qt), mask };
}

// live preview: outline of the area the bucket will paint, like Bambu Studio
const fillOutline = new THREE.LineSegments(new THREE.BufferGeometry(),
  new THREE.LineBasicMaterial({ color: 0xffffff, depthTest: false, transparent: true, opacity: 0.95 }));
fillOutline.renderOrder = 25; fillOutline.visible = false; scene.add(fillOutline);
const fillTint = new THREE.Mesh(new THREE.BufferGeometry(),
  new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.45, depthWrite: false, side: THREE.DoubleSide,
    polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }));
fillTint.renderOrder = 24; fillTint.visible = false; scene.add(fillTint);
let fillPrev = null;          // { seed, key, region }
let fillFrame = 0, fillSeedWanted = -1;
function clearFillPreview() { fillOutline.visible = false; fillTint.visible = false; fillPrev = null; }
function showFillPreview(seed) {
  const prm = fillParams();
  const key = `${seed}|${prm.ang}|${prm.same}|${prm.byDir}|${S.curColor}`;
  if (fillPrev && fillPrev.key === key) return;
  const reg = computeRegion(seed, prm);
  const pos = S.base.geometry.attributes.position.array, N = tri.nrm;
  const seg = [];
  for (let i = 0; i < reg.list.length; i++) {
    const t = reg.list[i];
    const nx = N[t * 3] * 0.04, ny = N[t * 3 + 1] * 0.04, nz = N[t * 3 + 2] * 0.04;
    for (let k = 0; k < 3; k++) {
      const u = adj[t * 3 + k];
      if (u >= 0 && reg.mask[u]) continue;
      const a = t * 9 + k * 3, b = t * 9 + ((k + 1) % 3) * 3;
      seg.push(pos[a] + nx, pos[a + 1] + ny, pos[a + 2] + nz, pos[b] + nx, pos[b + 1] + ny, pos[b + 2] + nz);
    }
  }
  fillOutline.geometry.dispose();
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(seg, 3));
  fillOutline.geometry = g;
  fillOutline.visible = true;
  // light tint of the area, in the colour it will get
  const tp = new Float32Array(reg.list.length * 9);
  for (let i = 0; i < reg.list.length; i++) tp.set(pos.subarray(reg.list[i] * 9, reg.list[i] * 9 + 9), i * 9);
  fillTint.geometry.dispose();
  const tg = new THREE.BufferGeometry();
  tg.setAttribute('position', new THREE.BufferAttribute(tp, 3));
  fillTint.geometry = tg;
  fillTint.material.color.set(S.palette[S.curColor - 1] || '#ffffff');
  fillTint.visible = true;
  fillPrev = { seed, key, region: reg };
  let diff = 0;
  for (let i = 0; i < reg.list.length; i++) if (S.paint[reg.list[i]] !== S.curColor) diff++;
  setStatus(diff ? `Balde: área de ${reg.list.length.toLocaleString('pt-BR')} triângulos; clique para pintar com a cor ${S.curColor} (Shift + clique apaga).`
    : `Balde: esta área (${reg.list.length.toLocaleString('pt-BR')} triângulos) já está na cor ${S.curColor}.`);
}
function requestFillPreview(seed) {
  fillSeedWanted = seed;
  if (fillFrame) return;
  fillFrame = requestAnimationFrame(() => { fillFrame = 0; if (fillSeedWanted >= 0 && S.painting && S.tool === 'fill') showFillPreview(fillSeedWanted); });
}
host.addEventListener('pointermove', (e) => {
  if (!S.painting || S.tool !== 'fill' || spaceDown || e.buttons) return;
  const h = hitBase(e);
  if (!h) { clearFillPreview(); fillSeedWanted = -1; return; }
  requestFillPreview(h.faceIndex);
}, true);
host.addEventListener('pointerleave', () => { if (S.tool === 'fill') clearFillPreview(); });
['#fill-a', '#fill-mode', '#fill-same'].forEach((id) => $(id).addEventListener('input', () => {
  if (fillPrev) { const sd = fillPrev.seed; fillPrev = null; showFillPreview(sd); }
}));
$('#fill-mode').addEventListener('change', () => { if (fillPrev) { const sd = fillPrev.seed; fillPrev = null; showFillPreview(sd); } });
$('#fill-same').addEventListener('change', () => { if (fillPrev) { const sd = fillPrev.seed; fillPrev = null; showFillPreview(sd); } });

function bucket(seed, erase) {
  const col = erase ? 1 : S.curColor;
  const reg = (fillPrev && fillPrev.seed === seed) ? fillPrev.region : computeRegion(seed, fillParams());
  const changed = [];
  for (let i = 0; i < reg.list.length; i++) { const t = reg.list[i]; if (S.paint[t] !== col) { S.paint[t] = col; changed.push(t); } }
  baseColorize(changed);
  clearFillPreview();             // the outline comes back on the next mouse move
  setStatus(`Balde: ${changed.length.toLocaleString('pt-BR')} triângulos pintados com a cor ${col}.`);
}

// painting from the texture (models with colour)
$('#tex-apply').onclick = async () => {
  setStatus('Refazendo a pintura pela textura…');
  try {
    pushUndo();
    const r = await post('/api/texture/paint', { cores: $('#tex-k').value ? +$('#tex-k').value : null, limpar: parseFloat($('#tex-clean').value) || 0 });
    await loadPaint();
    baseColorize();
    setStatus(`Pintura refeita pela textura: ${r.cores} filamentos.`);
  } catch (e) { setStatus('Erro: ' + e.message); }
};

// ---------------------------------------------------------------- contour tool
// Click points around an area: consecutive points are joined by the shortest path along the
// mesh edges. A closed contour blocks the fill: click inside to paint exactly up to the line.
// Made for organic models (AI figures) where the bucket finds no crease to stop at.
const CT = { pts: [], path: [], loops: [], blocked: new Set(), mode: 'tracar', prev: null };
const ctLine = new THREE.Group(); ctLine.renderOrder = 28; scene.add(ctLine);
function ensureVGraph() {
  if (vgraph) return vgraph;
  ensureAdjacency();
  const pos = S.base.geometry.attributes.position.array, n = tri.n, vid = S.vid, nv = S.nv;
  const vp = new Float32Array(nv * 3), vn = new Float32Array(nv * 3), deg = new Int32Array(nv + 1);
  for (let c = 0; c < n * 3; c++) {
    const v = vid[c], t = (c / 3) | 0;
    vp[v * 3] = pos[c * 3]; vp[v * 3 + 1] = pos[c * 3 + 1]; vp[v * 3 + 2] = pos[c * 3 + 2];
    vn[v * 3] += tri.nrm[t * 3]; vn[v * 3 + 1] += tri.nrm[t * 3 + 1]; vn[v * 3 + 2] += tri.nrm[t * 3 + 2];
  }
  for (let t = 0; t < n; t++) for (let k = 0; k < 3; k++) { deg[vid[t * 3 + k]]++; deg[vid[t * 3 + (k + 1) % 3]]++; }
  const start = new Int32Array(nv + 1);
  for (let i = 0; i < nv; i++) start[i + 1] = start[i] + deg[i];
  const fp = start.slice(0, nv), nbr = new Int32Array(start[nv]);
  for (let t = 0; t < n; t++) for (let k = 0; k < 3; k++) {
    const a = vid[t * 3 + k], b = vid[t * 3 + (k + 1) % 3];
    nbr[fp[a]++] = b; nbr[fp[b]++] = a;
  }
  for (let v = 0; v < nv; v++) { const l = Math.hypot(vn[v * 3], vn[v * 3 + 1], vn[v * 3 + 2]) || 1; vn[v * 3] /= l; vn[v * 3 + 1] /= l; vn[v * 3 + 2] /= l; }
  vgraph = { vp, vn, start, nbr, nv };
  return vgraph;
}
// A* along the edges (straight-line distance as the estimate): fast on 100k+ vertices
// avoid: vértices que o caminho não pode usar (fechar a linha pela volta que falta)
function surfacePath(a, b, avoid) {
  const { vp, start, nbr, nv } = ensureVGraph();
  const g = new Float64Array(nv).fill(Infinity), prev = new Int32Array(nv).fill(-1), done = new Uint8Array(nv);
  const H = (v) => Math.hypot(vp[v * 3] - vp[b * 3], vp[v * 3 + 1] - vp[b * 3 + 1], vp[v * 3 + 2] - vp[b * 3 + 2]);
  const heap = [[H(a), a]];
  const push = (it) => { heap.push(it); let i = heap.length - 1; while (i > 0) { const p = (i - 1) >> 1; if (heap[p][0] <= heap[i][0]) break; [heap[p], heap[i]] = [heap[i], heap[p]]; i = p; } };
  const pop = () => { const top = heap[0], last = heap.pop(); if (heap.length) { heap[0] = last; let i = 0; for (;;) { const l = 2 * i + 1, r = l + 1; let m = i; if (l < heap.length && heap[l][0] < heap[m][0]) m = l; if (r < heap.length && heap[r][0] < heap[m][0]) m = r; if (m === i) break; [heap[m], heap[i]] = [heap[i], heap[m]]; i = m; } } return top; };
  g[a] = 0;
  while (heap.length) {
    const [, v] = pop();
    if (done[v]) continue;
    if (v === b) break;
    done[v] = 1;
    for (let k = start[v]; k < start[v + 1]; k++) {
      const u = nbr[k];
      if (done[u] || (avoid && u !== b && avoid[u])) continue;
      const d = g[v] + Math.hypot(vp[v * 3] - vp[u * 3], vp[v * 3 + 1] - vp[u * 3 + 1], vp[v * 3 + 2] - vp[u * 3 + 2]);
      if (d < g[u]) { g[u] = d; prev[u] = v; push([d + H(u), u]); }
    }
  }
  const out = [b];
  while (out[out.length - 1] !== a && prev[out[out.length - 1]] >= 0) out.push(prev[out[out.length - 1]]);
  if (avoid && out[out.length - 1] !== a) return null;
  return out.reverse();
}
// Fechar a linha: volta do último ponto ao primeiro SEM passar de novo por perto do que já foi
// desenhado. Assim, com pontos só na frente do pescoço, a linha fecha por trás (escondida pelo
// cabelo), e não volta pela frente. Se não houver outro caminho, usa o mais curto.
function closingPath(path, a, b) {
  const { vp, nv } = ensureVGraph();
  const drawn = [].concat(...path);
  if (drawn.length < 3) return surfacePath(a, b);
  const dab = Math.hypot(vp[a * 3] - vp[b * 3], vp[a * 3 + 1] - vp[b * 3 + 1], vp[a * 3 + 2] - vp[b * 3 + 2]);
  const r = Math.min(8, Math.max(1.5, 0.4 * dab, penWidth() * 4)), r2 = r * r, cell = r, H = new Map();
  const key = (x, y, z) => `${Math.floor(x / cell)},${Math.floor(y / cell)},${Math.floor(z / cell)}`;
  drawn.forEach((v) => { const k = key(vp[v * 3], vp[v * 3 + 1], vp[v * 3 + 2]); if (!H.has(k)) H.set(k, []); H.get(k).push(v); });
  const near = (v, list) => list.some((w) => (vp[v * 3] - vp[w * 3]) ** 2 + (vp[v * 3 + 1] - vp[w * 3 + 1]) ** 2 + (vp[v * 3 + 2] - vp[w * 3 + 2]) ** 2 < r2);
  const ends = [a, b];
  const avoid = new Uint8Array(nv);
  for (let v = 0; v < nv; v++) {
    const x = vp[v * 3], y = vp[v * 3 + 1], z = vp[v * 3 + 2];
    const cx = Math.floor(x / cell), cy = Math.floor(y / cell), cz = Math.floor(z / cell);
    let hit = false;
    for (let i = -1; i <= 1 && !hit; i++) for (let j = -1; j <= 1 && !hit; j++) for (let k = -1; k <= 1 && !hit; k++) {
      const L = H.get(`${cx + i},${cy + j},${cz + k}`);
      if (L && near(v, L)) hit = true;
    }
    if (hit && !near(v, ends)) avoid[v] = 1;
  }
  return surfacePath(a, b, avoid) || surfacePath(a, b);
}
function nearestCorner(h) {
  const t = h.faceIndex, vid = S.vid, { vp } = ensureVGraph();
  let best = vid[t * 3], bd = Infinity;
  for (let k = 0; k < 3; k++) {
    const v = vid[t * 3 + k];
    const d = Math.hypot(vp[v * 3] - h.point.x, vp[v * 3 + 1] - h.point.y, vp[v * 3 + 2] - h.point.z);
    if (d < bd) { bd = d; best = v; }
  }
  return best;
}
const ekey = (a, b) => (a < b ? a * S.nv + b : b * S.nv + a);
function setContourMode(m) {
  CT.mode = m;
  document.querySelectorAll('[data-ctm]').forEach((b) => b.classList.toggle('on', b.dataset.ctm === m));
  clearFillPreview();
  setStatus(m === 'pintar'
    ? 'Pintar dentro: passe o mouse para ver a área (ela para nas linhas) e clique para pintar com a cor escolhida.'
    : 'Traçar: clique pontos em volta da área; a linha segue a superfície. Clique no primeiro ponto (ou Enter) para fechar.');
}
document.querySelectorAll('[data-ctm]').forEach((b) => b.addEventListener('click', () => setContourMode(b.dataset.ctm)));
function screenOf(v) {
  const { vp } = ensureVGraph();
  const q = new THREE.Vector3(vp[v * 3], vp[v * 3 + 1], vp[v * 3 + 2]).project(camera);
  const r = renderer.domElement.getBoundingClientRect();
  return [r.left + (q.x + 1) / 2 * r.width, r.top + (1 - q.y) / 2 * r.height];
}
function contourClick(h, shift, ev) {
  ensureVGraph();
  if (CT.mode === 'pintar') { contourFill(h.faceIndex); return; }
  const v = nearestCorner(h);
  if (CT.pts.length >= 3 && ev) {                    // click on the first point closes: close on screen
    const [sx, sy] = screenOf(CT.pts[0]);              // (14 px) and on the model (not a point hidden behind)
    const { vp } = vgraph, f0 = CT.pts[0];
    const dw = Math.hypot(vp[v * 3] - vp[f0 * 3], vp[v * 3 + 1] - vp[f0 * 3 + 1], vp[v * 3 + 2] - vp[f0 * 3 + 2]);
    if (Math.hypot(sx - ev.clientX, sy - ev.clientY) < 14 && dw < 4) { closeContour(); return; }
  }
  if (CT.pts.length) {
    const seg = surfacePath(CT.pts[CT.pts.length - 1], v);
    CT.path.push(seg.slice(1));
  } else CT.path.push([v]);
  CT.pts.push(v);
  drawContours();
  setStatus(`Linha: ${CT.pts.length} ponto(s). Clique no primeiro ponto ou tecle Enter para fechar; Backspace desfaz o último.`);
}
function undoContourPoint() {
  if (!CT.pts.length) {                                 // nothing being drawn: remove the last closed contour
    const L = CT.loops.pop();
    if (!L) return;
    CT.blocked = new Set();
    CT.loops.forEach((lp) => { for (let i = 0; i < lp.length; i++) CT.blocked.add(ekey(lp[i], lp[(i + 1) % lp.length])); });
    CT.prev = null;
    drawContours();
    setStatus('Última linha apagada.');
    return;
  }
  CT.pts.pop(); CT.path.pop();
  drawContours();
}
function closeContour() {
  if (CT.pts.length < 3) { setStatus('Linha: marque pelo menos 3 pontos em volta da área.'); return; }
  const back = closingPath(CT.path, CT.pts[CT.pts.length - 1], CT.pts[0]);
  const loop = [].concat(...CT.path, back.slice(1, -1));
  for (let i = 0; i < loop.length; i++) CT.blocked.add(ekey(loop[i], loop[(i + 1) % loop.length]));
  CT.loops.push(loop);
  CT.pts = []; CT.path = [];
  drawContours();
  setContourMode('pintar');
  setStatus(`Linha fechada (${CT.loops.length} no total). Passe o mouse para ver a área e clique para pintar com a cor ${S.curColor}. "Traçar" desenha outra linha.`);
}
function clearContours(silent) {
  CT.pts = []; CT.path = []; CT.loops = []; CT.blocked = new Set(); CT.prev = null; CT.mode = 'tracar';
  document.querySelectorAll('[data-ctm]').forEach((b) => b.classList.toggle('on', b.dataset.ctm === 'tracar'));
  drawContours();
  if (!silent) setStatus('Linhas apagadas.');
}
// caneta: linha grossa (tubo) sobre a superfície, que não some dentro da malha, mais um traço
// fraco que aparece através do modelo onde o tubo fica escondido
// espessura escolhida no topo (Linha: fina, média, grossa), guardada neste Mac
const PEN_MULT = { fina: 0.4, media: 0.7, grossa: 1.0 };
let penKind = (() => { try { const v = localStorage.getItem('flexi-linha'); return PEN_MULT[v] ? v : 'fina'; } catch (e) { return 'fina'; } })();
function penWidth() {
  const d = S.baseBox ? S.baseBox.getSize(new THREE.Vector3()).length() : 120;
  return Math.min(0.6, Math.max(0.15, d * 0.0022)) * PEN_MULT[penKind];
}
// troca a espessura de todas as linhas já desenhadas (cada uma guarda como foi feita)
function setPenKind(k) {
  if (!PEN_MULT[k]) return;
  penKind = k;
  try { localStorage.setItem('flexi-linha', k); } catch (e) { /* sem armazenamento */ }
  const sel = document.getElementById('pen-sel'); if (sel) sel.value = k;
  const old = [];
  scene.traverse((o) => { if (o.userData && o.userData.pen && o.parent) old.push(o); });
  old.forEach((o) => {
    const a = o.userData.pen;
    const n = a.kind === 'seg' ? penSegments(a.seg, a.color, a.fixedR ? a.r : penWidth() * 0.8) : penLine(a.pts, a.color, a.closed, a.norms, a.lift);
    if (!n) return;
    n.position.copy(o.position); n.quaternion.copy(o.quaternion); n.scale.copy(o.scale); n.visible = o.visible;
    Object.keys(o.userData).forEach((key) => { if (key !== 'pen') n.userData[key] = o.userData[key]; });
    const par = o.parent, i = par.children.indexOf(o);
    par.remove(o); par.children.splice(i, 0, n); n.parent = par;
    disposeTree(o);
  });
}
{ const ps = document.getElementById('pen-sel'); if (ps) { ps.value = penKind; ps.addEventListener('change', () => setPenKind(ps.value)); } }
function penLine(pts, color, closed, norms, lift = 0.15) {
  if (!pts || pts.length < 2) return null;
  const P = pts.map((q, i) => { const m = (norms && norms[i]) || [0, 0, 0]; return new THREE.Vector3(q[0] + m[0] * lift, q[1] + m[1] * lift, q[2] + m[2] * lift); });
  const list = closed ? P.concat([P[0]]) : P;
  const path = new THREE.CurvePath();
  for (let i = 0; i + 1 < list.length; i++) if (list[i].distanceToSquared(list[i + 1]) > 1e-10) path.add(new THREE.LineCurve3(list[i], list[i + 1]));
  if (!path.curves.length) return null;
  const g = new THREE.Group();
  const tube = new THREE.Mesh(new THREE.TubeGeometry(path, Math.min(4000, Math.max(8, path.curves.length * 2)), penWidth(), 6, false),
    new THREE.MeshBasicMaterial({ color }));
  tube.renderOrder = 29;
  const lg = new THREE.BufferGeometry().setFromPoints(list);
  const ghost = new THREE.Line(lg, new THREE.LineBasicMaterial({ color, depthTest: false, transparent: true, opacity: 0.35 }));
  ghost.renderOrder = 27;
  g.add(tube, ghost);
  g.renderOrder = 29;
  g.userData.pen = { kind: 'line', pts, color, closed, norms, lift };
  return g;
}
// mesma caneta para bordas feitas de segmentos soltos (borda da área marcada): prismas finos
function penSegments(seg, color, r) {
  const fixedR = r !== undefined;
  if (!fixedR) r = penWidth() * 0.8;
  const ns = (seg.length / 6) | 0;
  if (!ns) return null;
  const V = new Float32Array(ns * 8 * 3), I = new Uint32Array(ns * 24);
  const a = new THREE.Vector3(), b = new THREE.Vector3(), d = new THREE.Vector3(), u = new THREE.Vector3(), w = new THREE.Vector3();
  const ax = new THREE.Vector3(1, 0, 0), ay = new THREE.Vector3(0, 1, 0);
  for (let i = 0; i < ns; i++) {
    a.fromArray(seg, i * 6); b.fromArray(seg, i * 6 + 3);
    d.subVectors(b, a); const L = d.length(); if (L < 1e-9) continue; d.divideScalar(L);
    u.crossVectors(d, Math.abs(d.x) < 0.9 ? ax : ay).normalize(); w.crossVectors(d, u);
    // estende um pouco as pontas para os segmentos se emendarem sem falhas
    const a2 = a.clone().addScaledVector(d, -r * 0.6), b2 = b.clone().addScaledVector(d, r * 0.6);
    const c4 = [[1, 0], [0, 1], [-1, 0], [0, -1]];
    [a2, b2].forEach((p, e) => c4.forEach(([x, y], k) => {
      const o = (i * 8 + e * 4 + k) * 3;
      V[o] = p.x + (u.x * x + w.x * y) * r; V[o + 1] = p.y + (u.y * x + w.y * y) * r; V[o + 2] = p.z + (u.z * x + w.z * y) * r;
    }));
    for (let k = 0; k < 4; k++) {
      const k2 = (k + 1) % 4, o = i * 8, q = i * 24 + k * 6;
      I[q] = o + k; I[q + 1] = o + 4 + k; I[q + 2] = o + 4 + k2; I[q + 3] = o + k; I[q + 4] = o + 4 + k2; I[q + 5] = o + k2;
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(V, 3));
  g.setIndex(new THREE.BufferAttribute(I, 1));
  const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide }));
  m.renderOrder = 27;
  m.userData.pen = { kind: 'seg', seg: Float32Array.from(seg), color, r, fixedR };
  return m;
}
// Só a geometria é liberada: liberar o material apaga o shader quando ninguém mais usa, e o próximo desenho igual
// compila tudo de novo (no Windows cada compilação leva dezenas de ms, e a pincelada travava). Material sem uso é
// recolhido sozinho pelo navegador; textura, se houver, sai junto.
function disposeTree(o) { o.traverse((x) => { if (x.geometry) x.geometry.dispose(); const ms = Array.isArray(x.material) ? x.material : x.material ? [x.material] : []; ms.forEach((mt) => { if (mt.map) mt.map.dispose(); }); }); }
// borracha: tira as linhas fechadas que ela toca (a pintura apagada fica no ⌘Z da pintura)
function eraseContours(p) {
  if (!vgraph || (!CT.loops.length && !CT.pts.length)) return;
  const { vp } = vgraph, r2 = brushR() ** 2;
  const near = (L) => L.some((v) => (vp[v * 3] - p.x) ** 2 + (vp[v * 3 + 1] - p.y) ** 2 + (vp[v * 3 + 2] - p.z) ** 2 <= r2);
  // linha em andamento: tira os pontos e trechos tocados; o resto continua
  if (CT.pts.length) {
    const hit = (v) => (vp[v * 3] - p.x) ** 2 + (vp[v * 3 + 1] - p.y) ** 2 + (vp[v * 3 + 2] - p.z) ** 2 <= r2;
    const kp = CT.pts.filter((v, i) => !hit(v) && !(CT.path[i] || []).some(hit));
    if (kp.length !== CT.pts.length) {
      CT.pts = kp; CT.path = kp.map((v, i) => (i ? surfacePath(kp[i - 1], v).slice(1) : [v]));
      drawContours();
      setStatus(kp.length ? `Borracha: linha em andamento com ${kp.length} ponto(s); volte à Linha (L) para continuar.` : 'Borracha: linha em andamento apagada.');
    }
  }
  const keep = CT.loops.filter((L) => !near(L));
  if (keep.length === CT.loops.length) return;
  const gone = CT.loops.length - keep.length;
  CT.loops = keep;
  CT.blocked = new Set();
  CT.loops.forEach((lp) => { for (let i = 0; i < lp.length; i++) CT.blocked.add(ekey(lp[i], lp[(i + 1) % lp.length])); });
  CT.prev = null;
  drawContours();
  setStatus(`Borracha: ${gone} linha(s) apagada(s).`);
}
function drawContours() {
  ctLine.children.slice().forEach((o) => { ctLine.remove(o); disposeTree(o); });
  if (!vgraph) return;
  const { vp, vn } = vgraph;
  const mk = (verts, closed, color) => {
    if (verts.length < 2) return;
    const o = penLine(verts.map((v) => [vp[v * 3], vp[v * 3 + 1], vp[v * 3 + 2]]), color, closed,
      verts.map((v) => [vn[v * 3], vn[v * 3 + 1], vn[v * 3 + 2]]), 0.12);
    if (o) ctLine.add(o);
  };
  CT.loops.forEach((L) => mk(L, true, 0x1f2328));
  const cur = [].concat(...CT.path);
  mk(cur, false, 0xd9622b);
  CT.pts.forEach((v) => {
    const m = new THREE.Mesh(new THREE.SphereGeometry(0.35, 10, 8), new THREE.MeshBasicMaterial({ color: 0xd9622b }));
    m.position.set(vp[v * 3], vp[v * 3 + 1], vp[v * 3 + 2]);
    ctLine.add(m);
  });
  ctLine.visible = S.painting;
}
function contourRegion(seed) {
  ensureAdjacency();
  const vid = S.vid, same = $('#ct-same').checked, from = S.paint[seed];
  const mask = new Uint8Array(tri.n), q = new Int32Array(tri.n);
  let qh = 0, qt = 0;
  q[qt++] = seed; mask[seed] = 1;
  while (qh < qt) {
    const t = q[qh++];
    for (let k = 0; k < 3; k++) {
      const u = adj[t * 3 + k];
      if (u < 0 || mask[u]) continue;
      if (CT.blocked.has(ekey(vid[t * 3 + k], vid[t * 3 + (k + 1) % 3]))) continue;
      if (same && S.paint[u] !== from) continue;
      mask[u] = 1; q[qt++] = u;
    }
  }
  return { list: q.subarray(0, qt), mask };
}
function contourFill(seed) {
  const reg = (CT.prev && CT.prev.seed === seed && CT.prev.n === CT.loops.length) ? CT.prev.region : contourRegion(seed);
  const qt = reg.list.length, q = reg.list;
  clearFillPreview();
  CT.prev = { seed, region: reg, n: CT.loops.length };      // hovering the same area keeps this message
  pushUndo();
  const changed = [];
  for (let i = 0; i < qt; i++) { const t = q[i]; if (S.paint[t] !== S.curColor) { S.paint[t] = S.curColor; changed.push(t); } }
  baseColorize(changed);
  syncPaint();
  const share = qt / tri.n;
  setStatus(share > 0.6
    ? `Atenção: a pintura passou da linha (${Math.round(share * 100)}% do modelo). A linha não fecha a área: ⌘Z desfaz; feche a linha em volta dela.`
    : `Linha: ${changed.length.toLocaleString('pt-BR')} triângulos pintados com a cor ${S.curColor}. Clique do outro lado da linha para pintar o outro lado.`);
}
// hover preview: the area the click will paint, with its size (a leak shows before painting)
let ctFrame = 0, ctWanted = -1;
host.addEventListener('pointermove', (e) => {
  if (!S.painting || S.tool !== 'contour' || CT.mode !== 'pintar' || e.buttons) return;
  const h = hitBase(e);
  if (!h) { clearFillPreview(); return; }
  ctWanted = h.faceIndex;
  if (ctFrame) return;
  ctFrame = requestAnimationFrame(() => {
    ctFrame = 0;
    if (ctWanted < 0 || S.tool !== 'contour' || CT.mode !== 'pintar') return;
    if (CT.prev && CT.prev.region.mask[ctWanted] && CT.prev.n === CT.loops.length) return;
    const reg = contourRegion(ctWanted);
    CT.prev = { seed: ctWanted, region: reg, n: CT.loops.length };
    const pos = S.base.geometry.attributes.position.array;
    const tp = new Float32Array(reg.list.length * 9);
    for (let i = 0; i < reg.list.length; i++) tp.set(pos.subarray(reg.list[i] * 9, reg.list[i] * 9 + 9), i * 9);
    fillTint.geometry.dispose();
    const tg = new THREE.BufferGeometry();
    tg.setAttribute('position', new THREE.BufferAttribute(tp, 3));
    fillTint.geometry = tg;
    fillTint.material.color.set(S.palette[S.curColor - 1] || '#ffffff');
    fillTint.visible = true;
    const share = reg.list.length / tri.n;
    setStatus(share > 0.5
      ? `⚠️ Esta área é ${Math.round(share * 100)}% do modelo: a linha não fecha (há uma passagem). Feche a linha em volta da área antes de pintar.`
      : `Pintar dentro: ${reg.list.length.toLocaleString('pt-BR')} triângulos (${Math.round(share * 100)}% do modelo). Clique para pintar com a cor ${S.curColor}.`);
  });
}, true);
$('#ct-close').onclick = closeContour;
$('#ct-undo').onclick = undoContourPoint;
$('#ct-clear').onclick = () => clearContours(false);

// height band (the server splits the triangles on the band edges when "exata")
$('#band-apply').onclick = async () => {
  const z0 = parseFloat($('#band-z0').value), z1 = parseFloat($('#band-z1').value);
  if (!(z1 > z0 || z0 > z1)) { setStatus('Escolha duas alturas diferentes.'); return; }
  setStatus('Pintando a faixa…');
  try {
    await syncPaintNow();
    pushUndo();
    const r = await post('/api/paint/bands', { z0, z1, cor: S.curColor, exato: $('#band-exact').checked });
    if (r.mudou_malha) {
      S.undo = [];                        // the triangles changed: older steps no longer fit
      await showBase(false);
      $('#paint-box').classList.remove('hidden');
    } else {
      const p = await api('/api/paint');
      if (p.pintura) { S.paint = unb64(p.pintura); baseColorize(); }
    }
    updateBands();
    setStatus(`Faixa de ${nf(Math.min(z0, z1), 2)} a ${nf(Math.max(z0, z1), 2)} mm pintada com a cor ${S.curColor} (${r.pintados.toLocaleString('pt-BR')} triângulos).`);
  } catch (e) { setStatus('Erro na faixa: ' + e.message); }
};
function undoPaint() {
  const p = S.undo.pop();
  if (!p || !S.paint || p.length !== S.paint.length) { setStatus('Nada para desfazer.'); return; }
  S.paint = p; baseColorize(); syncPaint(); setStatus('Desfeito.');
}
$('#paint-undo').onclick = () => { if (CT.pts.length) { CT.pts.pop(); CT.path.pop(); drawContours(); } else undoPaint(); };
$('#paint-clear').onclick = () => { if (!S.paint) return; pushUndo(); S.paint.fill(1); baseColorize(); syncPaint(); setStatus('Pintura limpa (⌘Z desfaz).'); };
renderPalette();

// Esta janela avisa o motor que está aberta (a cada 5 s). O motor roda no processo da primeira janela e
// só fecha quando não sobra nenhuma janela do app aberta.
(() => {
  const j = new URLSearchParams(location.search).get('j') || ('j' + Math.random().toString(36).slice(2, 10));
  let falhas = 0;
  const ping = async () => {
    try {
      const r = await fetch('/api/ping?j=' + encodeURIComponent(j), { cache: 'no-store' });
      if (!r.ok) throw new Error(String(r.status));
      if (falhas >= 2) setStatus('O motor do app voltou a responder.');
      falhas = 0;
    } catch (e) {
      falhas++;
      if (falhas === 2) setStatus('O motor do app parou de responder. Feche esta janela e abra o app de novo pelo ícone (o projeto salvo continua no arquivo).');
    }
  };
  ping();
  setInterval(ping, 5000);
})();

// test / automation hook
window.flexi = { GPU, VIEW, redraw, comBVH, closingPath, penWidth, setPenKind, penLine, penSegments, disposeTree, ctDebug: () => ({ pts: CT.pts.length, loops: CT.loops.length, mode: CT.mode, loopLens: CT.loops.map((l) => l.length) }), scene, host, renderer, controls, loader, api, post, setStatus, nf, ndc, solidMat, hexRGB, unb64, syncPaintNow, reveal, clearGroup, CSS2DObject, THREE,
  S, camera, gizmo, handlesGroup: handles, setPainting, setTool, bucket, saveProject, baseColorize, syncPaint, pushPaintUndo: () => pushUndo(), tri: () => tri, setBaseHidden, ensureVGraph, surfacePath, nearestCorner, screenOf, hitBase, adjacency: () => { ensureAdjacency(); return adj; }, pick: (cx, cy) => { ray.setFromCamera(ndc({ clientX: cx, clientY: cy }), camera); return ray.intersectObjects(S.jointGroup.children, true).map((h) => [h.object.type, !!h.object.userData.cutter, +h.distance.toFixed(1)]); }, addAt, verify, select, renderJoints, loadFile, fitCamera, setView, doExport, openProjectFile, openPath, showRecent, cleanJoint, act };
