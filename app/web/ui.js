// EFC3D: casca da interface no estilo do Fusion 360 (v1.27).
// Abas das etapas no topo com a faixa de ferramentas, navegador de objetos à esquerda, canvas 3D
// no centro (cubo de vistas e barra de navegação), painel do comando à direita e linha do tempo
// embaixo. Não muda o funcionamento: os botões da faixa e do navegador acionam os mesmos
// controles do painel (mesmos ids), que continuam existindo.
const F = window.flexi;
const { THREE, camera, controls, S } = F;
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const store = {
  get: (k, d) => { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* sem armazenamento */ } },
};

// ---------------------------------------------------------------- abas (etapas)
const TABS = {
  modelo: { titulo: 'Modelo', icone: '📦' },
  juntas: { titulo: 'Juntas', icone: '🦴' },
  cores: { titulo: 'Cores', icone: '🎨' },
  cortes: { titulo: 'Cortes', icone: '✂' },
  exportar: { titulo: 'Exportar', icone: '📤' },
};
let tab = store.get('flexi-aba', 'modelo');
if (!TABS[tab]) tab = 'modelo';

function click(sel) {
  const el = typeof sel === 'string' ? $(sel) : sel;
  if (!el) return;
  if (el.closest('#file-menu')) openFileMenu(true);
  reveal(el, false);
  el.click();
}
const isPainting = () => !!S.painting;
const isMarking = () => !!(window.flexiFree && window.flexiFree.FC.marking);

// Faixa de ferramentas de cada aba: grupos com rótulo, como no Fusion (CRIAR, MODIFICAR...).
const RIBBON = {
  modelo: [
    { g: 'ARQUIVO', it: [
      { ic: '📂', t: 'Abrir', tip: 'Abrir modelo ou projeto (⌘O)', a: '#btn-open' },
      { ic: '🕘', t: 'Recentes', tip: 'Projetos e modelos recentes', a: () => { openFileMenu(true); $('#btn-recent').click(); } },
      { ic: '💾', t: 'Salvar', tip: 'Salvar projeto (⌘S)', a: '#btn-proj-save' },
    ] },
    { g: 'PREPARAR', it: [
      { ic: '📏', t: 'Tamanho e base', tip: 'Comprimento, simetria, base achatada', a: () => openDetails('#s-model details.adv') },
      { ic: '✨', t: 'Criar com IA', tip: 'Prompts do ChatGPT para criar o animal', a: () => openDetails('#prompts-det') },
    ] },
  ],
  juntas: [
    { g: 'CRIAR', it: [
      { ic: '＋', t: 'Junta', tip: 'Adicionar junta: clique no modelo onde deve dobrar', a: '#btn-add', on: () => $('#btn-add').classList.contains('active') },
      { ic: '💡', t: 'Sugerir', tip: 'Sugerir juntas pelo formato do modelo', a: '#btn-suggest' },
      { ic: '📥', t: 'Importar peça', tip: 'Importar uma peça de corte sua (STL)', a: '#btn-imp-wrap' },
    ] },
    { g: 'MODIFICAR', it: [
      { ic: '✥', t: 'Tudo', tip: 'Mover, girar e escala juntos (A)', a: '[data-gz="all"]', on: () => $('[data-gz="all"]').classList.contains('on') },
      { ic: '↔', t: 'Mover', tip: 'Mover (M)', a: '[data-gz="translate"]', on: () => $('[data-gz="translate"]').classList.contains('on') },
      { ic: '⟳', t: 'Girar', tip: 'Girar (R)', a: '[data-gz="rotate"]', on: () => $('[data-gz="rotate"]').classList.contains('on') },
      { ic: '⤡', t: 'Escala', tip: 'Escala (S)', a: '[data-gz="scale"]', on: () => $('[data-gz="scale"]').classList.contains('on') },
      { ic: '⊹', t: 'Eixos', tip: 'Direção das setas e anéis: da junta ou do mundo', a: '#gz-space', lbl: () => ($('#gz-space').textContent || 'Eixos').replace('Eixos: ', 'Eixos ') },
    ] },
    { g: 'INSPECIONAR', it: [
      { ic: '✔', t: 'Verificar', tip: 'Verificar todas as juntas', a: '#btn-check-all' },
      { ic: '🎯', t: 'Ver junta', tip: 'Câmera na junta selecionada', a: '[data-cam="joint"]' },
    ] },
  ],
  cores: [
    { g: 'PINTAR', it: [
      { ic: '🖌', t: 'Pintar', tip: 'Entrar ou sair da pintura', a: '#btn-paint', on: isPainting },
      { ic: '🖌', t: 'Pincel', tip: 'Pincel (B)', a: () => paintTool('brush'), on: () => isPainting() && S.tool === 'brush' },
      { ic: '🪣', t: 'Balde', tip: 'Balde (F)', a: () => paintTool('fill'), on: () => isPainting() && S.tool === 'fill' },
      { ic: '▤', t: 'Faixa', tip: 'Faixa de altura (H)', a: () => paintTool('band'), on: () => isPainting() && S.tool === 'band' },
      { ic: '✏', t: 'Linha', tip: 'Linha (L)', a: () => paintTool('contour'), on: () => isPainting() && S.tool === 'contour' },
      { ic: '🧽', t: 'Borracha', tip: 'Borracha (E)', a: () => paintTool('erase'), on: () => isPainting() && S.tool === 'erase' },
    ] },
    { g: 'CONCLUIR', it: [
      { ic: '↶', t: 'Desfazer', tip: 'Desfazer a pintura (⌘Z)', a: '#paint-undo', en: isPainting },
      { ic: '✓', t: 'Concluir', tip: 'Concluir a pintura (Enter)', a: '#paint-done', en: isPainting },
    ] },
  ],
  cortes: [
    { g: 'CRIAR', it: [
      { ic: '✂', t: 'Corte livre', tip: 'Novo corte: desenhe a linha ou marque a parte', a: '#fc-new', on: isMarking },
      { ic: '▭', t: 'Corte plano', tip: 'Novo plano, como no fatiador', a: '#pl-new' },
      { ic: '🎨', t: 'Por cor', tip: 'Separar peças pelas cores pintadas', a: '#btn-split', on: () => !!(window.flexiSplit && window.flexiSplit.SP.on) },
    ] },
    { g: 'INSPECIONAR', it: [
      { ic: '👁', t: 'Prévia', tip: 'Prévia das peças, como na exportação', a: '#t-prevp', on: () => !!(window.flexiPecas && window.flexiPecas.active()) },
      { ic: '◻', t: 'Modelo', tip: 'Voltar ao modelo', a: '#t-orig' },
    ] },
  ],
  exportar: [
    { g: 'VERIFICAR', it: [
      { ic: '✔', t: 'Juntas', tip: 'Verificar juntas', a: '#btn-check-all' },
      { ic: '👁', t: 'Prévia', tip: 'Prévia das peças', a: '#t-prevp' },
    ] },
    { g: 'EXPORTAR', it: [
      { ic: '📤', t: 'Exportar', tip: 'Gerar 3MF, STLs e placas', a: '#btn-export', primary: true },
      { ic: '⬇', t: 'Baixar 3MF', tip: 'Baixar o 3MF da última exportação', a: '#btn-dl3mf', en: () => !$('#dl-box').classList.contains('hidden') },
      { ic: '📁', t: 'Abrir pasta', tip: 'Abrir a pasta da exportação', a: '#btn-reveal', en: () => !$('#dl-box').classList.contains('hidden') },
    ] },
    { g: 'VER', it: [
      { ic: '🧩', t: 'Exportado', tip: 'Peças da última exportação', a: '#t-pieces', on: () => !!S.showPieces },
      { ic: '▦', t: 'Na mesa', tip: 'Peças na mesa da impressora', a: () => { if (!S.showPieces) $('#t-pieces').click(); if (S.showPieces) $('[data-mesa="mesa"]').click(); }, on: () => !!S.onMesa },
    ] },
  ],
};
function paintTool(t) {
  if (!S.base) { F.setStatus('Carregue um modelo primeiro.'); return; }
  if (!S.painting) $('#btn-paint').click();
  const b = $(`[data-tool="${t}"]`);
  if (b) b.click();
}
function openDetails(sel) {
  const d = $(sel);
  if (!d) return;
  d.open = true;
  reveal(d, true);
}

function renderRibbon() {
  const rb = $('#ribbon');
  rb.innerHTML = '';
  for (const grp of RIBBON[tab]) {
    const g = document.createElement('div');
    g.className = 'rb-group';
    const row = document.createElement('div');
    row.className = 'rb-items';
    for (const it of grp.it) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'rb-btn' + (it.primary ? ' primary' : '');
      b.title = it.tip || it.t;
      b.innerHTML = `<span class="rb-ic" aria-hidden="true"></span><span class="rb-t"></span>`;
      b.querySelector('.rb-ic').textContent = it.ic;
      b.querySelector('.rb-t').textContent = it.t;
      b.onclick = () => { if (typeof it.a === 'function') it.a(); else click(it.a); refreshSoon(); };
      b._it = it;
      row.append(b);
    }
    const lab = document.createElement('div');
    lab.className = 'rb-label';
    lab.textContent = grp.g;
    g.append(row, lab);
    rb.append(g);
  }
  refreshRibbon();
}
function refreshRibbon() {
  $$('#ribbon .rb-btn').forEach((b) => {
    const it = b._it;
    const on = it.on ? !!it.on() : false;
    b.classList.toggle('on', on);
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
    b.disabled = it.en ? !it.en() : false;
    if (it.lbl) b.querySelector('.rb-t').textContent = it.lbl();
  });
}

function setTab(t, opts = {}) {
  if (!TABS[t]) return;
  tab = t;
  store.set('flexi-aba', t);
  document.body.dataset.tab = t;
  $$('#tabs [data-tab]').forEach((b) => {
    const on = b.dataset.tab === t;
    b.classList.toggle('on', on);
    b.setAttribute('aria-selected', on ? 'true' : 'false');
  });
  $$('#side section[data-tab]').forEach((s) => s.classList.toggle('tab-off', s.dataset.tab !== t));
  $('#cmd-title').textContent = TABS[t].titulo;
  if (opts.openPanel !== false) foldPanel(false);
  renderRibbon();
  renderTimeline();
  if (!opts.keepScroll) $('#side').scrollTop = 0;
}
$$('#tabs [data-tab]').forEach((b) => b.addEventListener('click', () => setTab(b.dataset.tab)));

// mostra o elemento: ativa a aba em que ele está e rola até ele
function reveal(el, scroll = true) {
  if (typeof el === 'string') el = $(el);
  if (!el) return;
  const sec = el.closest('#side section[data-tab]');
  if (sec && sec.dataset.tab !== tab) setTab(sec.dataset.tab, { keepScroll: true });
  if (el.closest('#side')) foldPanel(false);
  if (el.closest('#browser')) foldBrowser(false);
  if (scroll && el.getClientRects().length) el.scrollIntoView({ block: 'nearest' });
}

// ---------------------------------------------------------------- menu Arquivo
function openFileMenu(on) {
  const m = $('#file-menu');
  m.classList.toggle('hidden', !on);
  $('#file-btn').setAttribute('aria-expanded', on ? 'true' : 'false');
}
$('#file-btn').addEventListener('click', (e) => { e.stopPropagation(); openFileMenu($('#file-menu').classList.contains('hidden')); });
$('#file-menu').addEventListener('click', (e) => {
  e.stopPropagation();
  const b = e.target.closest('button');
  // ações que abrem um diálogo ou terminam fecham o menu; Recentes e a pasta continuam nele
  if (b && ['btn-open', 'btn-proj-save', 'btn-proj-saveas'].includes(b.id)) setTimeout(() => openFileMenu(false), 0);
});
document.addEventListener('click', (e) => { if (!e.target.closest('#file-menu') && !e.target.closest('#file-btn')) openFileMenu(false); });
$$('[data-proxy]').forEach((b) => b.addEventListener('click', () => click(b.dataset.proxy)));
$('#tb-undo').addEventListener('click', () => {
  // o mesmo ⌘Z de sempre (pintura, marcação ou o que foi excluído)
  window.dispatchEvent(new KeyboardEvent('keydown', { key: 'z', code: 'KeyZ', metaKey: true, ctrlKey: !/Mac/.test(navigator.platform), bubbles: true }));
});

// ---------------------------------------------------------------- painéis recolhíveis
function foldBrowser(on) {
  document.body.classList.toggle('br-folded', on);
  $('#br-fold').textContent = on ? '⟩' : '⟨';
  $('#br-fold').title = on ? 'Abrir o navegador' : 'Recolher o navegador';
  store.set('flexi-nav-fold', on ? '1' : '0');
}
function foldPanel(on) {
  if (document.body.classList.contains('cmd-folded') === on) return;
  document.body.classList.toggle('cmd-folded', on);
  $('#cmd-fold').textContent = on ? '⟨' : '⟩';
  $('#cmd-fold').title = on ? 'Abrir o painel' : 'Recolher o painel';
}
$('#br-fold').onclick = () => foldBrowser(!document.body.classList.contains('br-folded'));
$('#cmd-fold').onclick = () => foldPanel(!document.body.classList.contains('cmd-folded'));
foldBrowser(store.get('flexi-nav-fold', innerWidth < 1100 ? '1' : '0') === '1');
// o canvas acompanha o tamanho (painéis abrindo e fechando)
if (window.ResizeObserver) new ResizeObserver(() => window.dispatchEvent(new Event('resize'))).observe(F.host);

// ---------------------------------------------------------------- barra do canvas
// Os controles de vista que já existiam vão para cima do canvas (Ver, Junta) e para a barra de
// navegação embaixo (vistas e exibição), como no Fusion. Os botões são os mesmos.
const tbar = $('#toolbar');
const groups = $$('.tgroup', tbar);
const gCam = groups[0], gVer = groups[1], gJunta = $('#tg-junta'), gShow = groups[3];
const viewbar = document.createElement('div');
viewbar.id = 'viewbar';
viewbar.className = 'float-bar';
viewbar.append(gVer);
const jointbar = document.createElement('div');
jointbar.id = 'jointbar';
jointbar.className = 'float-bar';
jointbar.append(gJunta);
tbar.after(viewbar, jointbar);
tbar.classList.add('hidden');

const NAV = $('#navbar');
NAV.innerHTML = `
  <div class="nb-grp">
    <button class="nb" id="nb-orbit" title="Orbitar: arrastar com o botão esquerdo gira a vista">⟲<span>Orbitar</span></button>
    <button class="nb" id="nb-pan" title="Mover: arrastar com o botão esquerdo move a vista">✋<span>Mover</span></button>
    <button class="nb" id="nb-fit" title="Ajustar: enquadra tudo (F6, ou duplo clique no botão do meio)">⤢<span>Ajustar</span></button>
    <button class="nb" id="nb-home" title="Vista inicial (Home)">⌂<span>Início</span></button>
  </div>
  <div class="nb-grp nb-cam"></div>
  <div class="nb-grp">
    <button class="nb" id="nb-disp" aria-haspopup="true" aria-expanded="false" title="Exibição: cortes das juntas, seção, balanço, grade">◐<span>Exibição ▾</span></button>
    <button class="nb" id="nb-mouse" aria-haspopup="true" aria-expanded="false" title="Como o mouse navega">🖱<span>Mouse ▾</span></button>
  </div>
  <div id="nb-disp-pop" class="nb-pop hidden"></div>
  <div id="nb-mouse-pop" class="nb-pop hidden">
    <b>Navegação do mouse</b>
    <label class="chk"><input type="radio" name="nbm" value="fusion"> Fusion 360: botão do meio move, Shift + botão do meio gira, roda aproxima no cursor</label>
    <label class="chk"><input type="radio" name="nbm" value="classico"> Clássico: roda do meio aproxima arrastando</label>
    <p class="hint">Nos dois: botão esquerdo arrastando no vazio gira, botão direito move, roda aproxima onde o mouse está. Na pintura e na marcação o esquerdo pinta e o direito gira.</p>
  </div>`;
const camSeg = $('.seg', gCam);
$('.nb-cam', NAV).append(camSeg);
const disp = $('#nb-disp-pop');
disp.append(...[...gShow.children].filter((c) => !c.classList.contains('tlabel')));
const gl = document.createElement('label');
gl.className = 'chk tb';
gl.innerHTML = '<input id="t-grid" type="checkbox" checked> Grade';
disp.append(gl);
$('#t-grid').onchange = (e) => { F.scene.children.filter((c) => c.type === 'GridHelper').forEach((g) => { g.visible = e.target.checked; }); };
function pop(btn, el) {
  const on = el.classList.contains('hidden');
  $$('.nb-pop').forEach((p) => p.classList.add('hidden'));
  $$('#navbar [aria-haspopup]').forEach((b) => b.setAttribute('aria-expanded', 'false'));
  el.classList.toggle('hidden', !on);
  btn.setAttribute('aria-expanded', on ? 'true' : 'false');
}
$('#nb-disp').onclick = (e) => { e.stopPropagation(); pop(e.currentTarget, disp); };
$('#nb-mouse').onclick = (e) => { e.stopPropagation(); pop(e.currentTarget, $('#nb-mouse-pop')); };
$$('.nb-pop').forEach((p) => p.addEventListener('click', (e) => e.stopPropagation()));
document.addEventListener('click', () => { $$('.nb-pop').forEach((p) => p.classList.add('hidden')); $$('#navbar [aria-haspopup]').forEach((b) => b.setAttribute('aria-expanded', 'false')); });

// esquema do mouse
let scheme = store.get('flexi-mouse', 'fusion');
function applyScheme() {
  controls.mouseButtons.MIDDLE = scheme === 'fusion' ? THREE.MOUSE.PAN : THREE.MOUSE.DOLLY;   // PAN com Shift vira girar (OrbitControls)
  $$('input[name="nbm"]').forEach((r) => { r.checked = r.value === scheme; });
}
$$('input[name="nbm"]').forEach((r) => r.addEventListener('change', () => { scheme = r.value; store.set('flexi-mouse', scheme); applyScheme(); F.setStatus(scheme === 'fusion' ? 'Mouse como no Fusion 360: botão do meio move, Shift + botão do meio gira.' : 'Mouse clássico.'); }));
applyScheme();
let lastMid = 0;
F.renderer.domElement.addEventListener('pointerdown', (e) => {
  if (e.button !== 1 || scheme !== 'fusion') return;
  const t = performance.now();
  if (t - lastMid < 350) { fitAll(); lastMid = 0; } else lastMid = t;
});
F.renderer.domElement.addEventListener('auxclick', (e) => { if (e.button === 1) e.preventDefault(); });

// orbitar / mover com o botão esquerdo (como os botões da barra do Fusion)
let leftPan = false;
function setLeftPan(on) {
  leftPan = on;
  if (!isPainting() && !isMarking()) controls.mouseButtons.LEFT = on ? THREE.MOUSE.PAN : THREE.MOUSE.ROTATE;
  refreshNav();
}
$('#nb-orbit').onclick = () => setLeftPan(false);
$('#nb-pan').onclick = () => setLeftPan(true);
function refreshNav() {
  const busy = isPainting() || isMarking();
  if (!busy && controls.mouseButtons.LEFT !== -1) controls.mouseButtons.LEFT = leftPan ? THREE.MOUSE.PAN : THREE.MOUSE.ROTATE;
  $('#nb-orbit').classList.toggle('on', !leftPan && !busy);
  $('#nb-pan').classList.toggle('on', leftPan && !busy);
}

// enquadrar mantendo a direção da câmera
// caixa só das malhas visíveis (a grade da mesa, as luzes e os rótulos ficam de fora: na Prévia o
// "Ajustar" levava a câmera para longe)
function meshBox(root) {
  const box = new THREE.Box3(), b = new THREE.Box3();
  root.updateMatrixWorld(true);
  root.traverseVisible((o) => {
    if (!o.isMesh || !o.geometry) return;
    if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
    b.copy(o.geometry.boundingBox).applyMatrix4(o.matrixWorld);
    const sz = b.getSize(new THREE.Vector3());
    if (b.isEmpty() || !isFinite(sz.x + sz.y + sz.z) || Math.max(sz.x, sz.y, sz.z) > 5000) return;
    box.union(b);
  });
  return box;
}
function sceneBox() {
  let box = new THREE.Box3();
  if (S.showPieces && S.pieceGroup.children.length) box = meshBox(S.pieceGroup);
  else if (window.flexiPecas && window.flexiPecas.active() && S.prevGroup) box = meshBox(F.scene);
  if (box.isEmpty() && S.baseBox) box.copy(S.baseBox);
  return box;
}
function fitAll() {
  const box = sceneBox();
  if (box.isEmpty()) return;
  const c = box.getCenter(new THREE.Vector3());
  const r = box.getSize(new THREE.Vector3()).length() * 0.5;
  const dir = camera.position.clone().sub(controls.target).normalize();
  const dist = r / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2)) * 1.05;
  fly(c, c.clone().add(dir.multiplyScalar(dist)));
}
let flying = null;
function fly(target, pos) {
  const t0 = performance.now(), p0 = camera.position.clone(), c0 = controls.target.clone();
  const d0 = p0.clone().sub(c0), d1 = pos.clone().sub(target);
  const l0 = d0.length(), l1 = d1.length();
  const q = new THREE.Quaternion().setFromUnitVectors(d0.clone().normalize(), d1.clone().normalize());
  flying = { t0, p0, c0, d0, l0, l1, q, target, pos };
  requestAnimationFrame(step);
}
function step() {
  if (!flying) return;
  const f = Math.min(1, (performance.now() - flying.t0) / 320), e = 1 - Math.pow(1 - f, 3);
  const qi = new THREE.Quaternion().slerp(flying.q, e);
  const d = flying.d0.clone().normalize().applyQuaternion(qi).multiplyScalar(flying.l0 + (flying.l1 - flying.l0) * e);
  controls.target.lerpVectors(flying.c0, flying.target, e);
  camera.position.copy(controls.target).add(d);
  camera.lookAt(controls.target);
  controls.update();
  if (f < 1) requestAnimationFrame(step);
  else { camera.position.copy(flying.pos); controls.target.copy(flying.target); controls.update(); flying = null; }
}
function viewDir(n) {
  // vista por uma direção (do cubo): mesma distância e mesmo alvo
  const t = controls.target.clone();
  const dist = camera.position.distanceTo(t);
  const d = new THREE.Vector3(...n).normalize();
  if (Math.abs(d.z) > 0.999) d.y -= 0.002;            // topo ou baixo: o "para cima" da câmera é o Z
  $$('[data-cam]').forEach((b) => b.classList.remove('on'));
  fly(t, t.clone().add(d.normalize().multiplyScalar(dist)));
}
$('#nb-fit').onclick = () => fitAll();
const home = (e) => {
  if (e && e.stopPropagation) e.stopPropagation();
  if (!S.baseBox) { F.setStatus('Abra um modelo primeiro.'); return; }
  flying = null;                                      // para a animação do cubo, se houver
  F.fitCamera('iso');
  controls.update();
};
$('#nb-home').onclick = home;
$('#vc-home').onclick = home;
window.addEventListener('keydown', (e) => {
  const el = document.activeElement;
  if (el && ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)) return;
  if (e.key === 'F6') { e.preventDefault(); fitAll(); }
  if (e.key === 'Home') { e.preventDefault(); home(); }
});

// ---------------------------------------------------------------- cubo de vistas (ViewCube)
const VC = 74;                                            // lado do cubo em px
const FACES = [
  { n: [0, -1, 0], u: [0, 0, 1], t: 'FRENTE' }, { n: [0, 1, 0], u: [0, 0, 1], t: 'TRÁS' },
  { n: [1, 0, 0], u: [0, 0, 1], t: 'DIREITA' }, { n: [-1, 0, 0], u: [0, 0, 1], t: 'ESQUERDA' },
  { n: [0, 0, 1], u: [0, 1, 0], t: 'TOPO' }, { n: [0, 0, -1], u: [0, -1, 0], t: 'BAIXO' },
];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const cubeEl = $('#vc-cube');
FACES.forEach((f) => {
  const d = document.createElement('button');
  d.className = 'vc-face';
  d.type = 'button';
  d.textContent = f.t;
  d.title = 'Vista ' + f.t.toLowerCase();
  d.style.width = d.style.height = VC + 'px';
  d.style.left = d.style.top = -VC / 2 + 'px';
  d.onclick = () => viewDir(f.n);
  f.el = d;
  f.r = cross(f.u, f.n);
  cubeEl.append(d);
});
const corners = [];
for (const x of [-1, 1]) for (const y of [-1, 1]) for (const z of [-1, 1]) {
  const d = document.createElement('button');
  d.className = 'vc-corner';
  d.type = 'button';
  d.title = 'Vista de canto';
  d.onclick = () => viewDir([x, y, z]);
  $('#vc-corners').append(d);
  corners.push({ p: [x, y, z], el: d });
}
const mInv = new THREE.Matrix4();
function cubeFrame() {
  camera.updateMatrixWorld();
  mInv.copy(camera.matrixWorldInverse);
  const e = mInv.elements;                                // coluna a coluna
  const R = [[e[0], e[4], e[8]], [e[1], e[5], e[9]], [e[2], e[6], e[10]]];
  const toCss = (v) => [R[0][0] * v[0] + R[0][1] * v[1] + R[0][2] * v[2], -(R[1][0] * v[0] + R[1][1] * v[1] + R[1][2] * v[2]), R[2][0] * v[0] + R[2][1] * v[1] + R[2][2] * v[2]];
  const h = VC / 2;
  for (const f of FACES) {
    const cx = toCss(f.r), cy = toCss(f.u.map((v) => -v)), cz = toCss(f.n);
    const t = cz.map((v) => v * h);
    f.el.style.transform = `matrix3d(${cx[0]},${cx[1]},${cx[2]},0,${cy[0]},${cy[1]},${cy[2]},0,${cz[0]},${cz[1]},${cz[2]},0,${t[0]},${t[1]},${t[2]},1)`;
    f.el.style.zIndex = String(Math.round(cz[2] * 10 + 20));
    f.el.classList.toggle('back', cz[2] < 0.05);
  }
  for (const c of corners) {
    const v = toCss(c.p.map((x) => x * h));
    c.el.style.transform = `translate(${v[0]}px, ${v[1]}px)`;
    c.el.classList.toggle('hidden', v[2] < h * 0.25);
  }
  requestAnimationFrame(cubeFrame);
}
requestAnimationFrame(cubeFrame);

// ---------------------------------------------------------------- navegador (árvore de objetos)
// Espelha as listas do painel (juntas, áreas, peças por cor, cortes, planos): clicar seleciona o
// mesmo item e abre a aba dele; o olho mostra e oculta como na lista.
const TREE = [
  { id: 'modelo', t: 'Modelo', ic: '📦', tab: 'modelo' },
  { id: 'juntas', t: 'Juntas', ic: '🦴', tab: 'juntas', list: '#joint-list' },
  { id: 'areas', t: 'Áreas pintadas', ic: '🎨', tab: 'cores', list: '#area-list' },
  { id: 'cor', t: 'Peças por cor', ic: '🧩', tab: 'cortes', list: '#split-list' },
  { id: 'livres', t: 'Cortes livres', ic: '✂', tab: 'cortes', list: '#fc-list' },
  { id: 'planos', t: 'Cortes planos', ic: '▭', tab: 'cortes', list: '#pl-list' },
  { id: 'pecas', t: 'Peças', ic: '🧱', tab: 'exportar' },
];
const openGroups = new Set(JSON.parse(store.get('flexi-nav-open', '["juntas","livres","planos"]')));
function itemsOf(sel) { const ol = $(sel); return ol ? $$(':scope > li', ol) : []; }
let treeSig = '';
function treeSignature() {
  const parts = [tab, S.base ? ($('#drop-text').textContent || '') : '', S.pieces.length, window.flexiPecas ? window.flexiPecas.PC.parts.length : 0, [...openGroups].join(',')];
  for (const g of TREE) if (g.list) parts.push(itemsOf(g.list).map((li) => li.className + '|' + li.textContent).join('§'));
  return parts.join('¦');
}
function renderTree(force) {
  const sig = treeSignature();
  if (!force && sig === treeSig) return;          // sem mudança: não refaz (o clique e o hover não se perdem)
  treeSig = sig;
  const root = $('#br-tree');
  const frag = document.createDocumentFragment();
  for (const g of TREE) {
    const items = g.list ? itemsOf(g.list) : [];
    const wrap = document.createElement('div');
    wrap.className = 'br-g';
    const head = document.createElement('button');
    head.type = 'button';
    head.className = 'br-gh' + (g.tab === tab ? ' cur' : '');
    const open = openGroups.has(g.id);
    let extra = '';
    if (g.id === 'modelo') extra = S.base ? ($('#drop-text').textContent || '') : 'nenhum';
    else if (g.id === 'pecas') {
      const np = window.flexiPecas ? window.flexiPecas.PC.parts.length : 0;
      extra = S.pieces.length ? `${S.pieces.length} exportadas` : np ? `${np} na prévia` : '';
    } else extra = items.length ? String(items.length) : '';
    head.innerHTML = `<span class="br-car">${g.list && items.length ? (open ? '▾' : '▸') : '·'}</span><span class="br-ic"></span><span class="br-t"></span><span class="br-n"></span>`;
    head.querySelector('.br-ic').textContent = g.ic;
    head.querySelector('.br-t').textContent = g.t;
    head.querySelector('.br-n').textContent = extra;
    head.title = extra ? `${g.t}: ${extra}` : g.t;
    head.onclick = () => {
      if (g.list && items.length) { if (open) openGroups.delete(g.id); else openGroups.add(g.id); store.set('flexi-nav-open', JSON.stringify([...openGroups])); }
      treeSig = '';
      setTab(g.tab);
      if (g.id === 'pecas') { if (S.pieces.length) $('#t-pieces').click(); else if (window.flexiPecas && window.flexiPecas.PC.parts.length) $('#t-prevp').click(); }
      renderTree();
    };
    wrap.append(head);
    if (g.list && open) {
      for (const li of items) {
        const r = document.createElement('div');
        r.className = 'br-it' + (li.classList.contains('sel') ? ' sel' : '') + (li.classList.contains('hid') ? ' hid' : '');
        const luz = li.querySelector('.i-luz');
        const tag = li.querySelector('.tag');
        const meta = li.querySelector('.meta');
        const sw = li.querySelector('.swatch');
        r.innerHTML = '<span class="br-luz"></span><span class="br-sw"></span><button type="button" class="br-name"></button><button type="button" class="br-eye"></button>';
        r.querySelector('.br-luz').textContent = luz ? luz.textContent : '';
        if (sw) r.querySelector('.br-sw').style.background = sw.style.background; else r.querySelector('.br-sw').remove();
        const nm = r.querySelector('.br-name');
        nm.textContent = ((tag ? tag.textContent : '') + ' ' + (meta ? meta.textContent.split(' · ')[0] : '')).trim();
        nm.title = meta ? meta.textContent : '';
        nm.onclick = () => { setTab(g.tab); li.click(); refreshSoon(); };
        const eye = li.querySelector('.i-eye');
        const be = r.querySelector('.br-eye');
        if (eye) { be.textContent = eye.textContent; be.title = eye.title; be.setAttribute('aria-label', eye.getAttribute('aria-label') || eye.title); be.onclick = () => { eye.click(); refreshSoon(); }; } else be.remove();
        wrap.append(r);
      }
    }
    frag.append(wrap);
  }
  root.replaceChildren(frag);
}

// ---------------------------------------------------------------- linha do tempo
let tlSig = '';
function renderTimeline() {
  const n = (sel) => itemsOf(sel).length;
  const sig = [tab, !!S.base, $('#drop-text').textContent, S.joints.length, n('#area-list'), n('#fc-list'), n('#pl-list'), n('#split-list'), S.pieces.length].join('|');
  if (sig === tlSig) return;
  tlSig = sig;
  const steps = [
    { tab: 'modelo', t: 'Modelo', s: S.base ? '✓' : '', d: S.base ? ($('#drop-text').textContent || '') : 'abrir um modelo' },
    { tab: 'juntas', t: 'Juntas', s: S.joints.length ? String(S.joints.length) : '', d: S.joints.length ? `${S.joints.length} junta(s)` : 'opcional' },
    { tab: 'cores', t: 'Cores', s: n('#area-list') ? String(n('#area-list')) : '', d: n('#area-list') ? `${n('#area-list')} área(s)` : 'opcional' },
    { tab: 'cortes', t: 'Cortes', s: (n('#fc-list') + n('#pl-list') + n('#split-list')) ? String(n('#fc-list') + n('#pl-list') + n('#split-list')) : '',
      d: `${n('#fc-list')} livre(s) · ${n('#pl-list')} plano(s) · ${n('#split-list')} por cor` },
    { tab: 'exportar', t: 'Exportar', s: S.pieces.length ? '✓' : '', d: S.pieces.length ? `${S.pieces.length} peça(s) exportadas` : 'ainda não exportado' },
  ];
  const tl = $('#timeline');
  tl.innerHTML = '';
  steps.forEach((st, i) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'tl-step' + (st.tab === tab ? ' cur' : '') + (st.s ? ' done' : '');
    b.title = `${st.t}: ${st.d}`;
    b.innerHTML = '<span class="tl-n"></span><span class="tl-t"></span><span class="tl-s"></span>';
    b.querySelector('.tl-n').textContent = String(i + 1);
    b.querySelector('.tl-t').textContent = st.t;
    b.querySelector('.tl-s').textContent = st.s ? (st.s === '✓' ? '✓ ' + st.d : st.d) : st.d;
    b.onclick = () => setTab(st.tab);
    tl.append(b);
    if (i < steps.length - 1) { const a = document.createElement('span'); a.className = 'tl-arrow'; a.textContent = '›'; a.setAttribute('aria-hidden', 'true'); tl.append(a); }
  });
}

// ---------------------------------------------------------------- atualizar e seguir o usuário
let pend = 0;
function refreshSoon() {
  if (pend) return;
  pend = requestAnimationFrame(() => { pend = 0; renderTree(); renderTimeline(); refreshRibbon(); refreshNav(); refreshEmpty(); });
}
const mo = new MutationObserver(refreshSoon);
['#joint-list', '#area-list', '#split-list', '#fc-list', '#pl-list', '#drop-text', '#dl-box', '#paint-box', '#tool-seg', '#gizmo-seg', '#status'].forEach((s) => {
  const el = $(s);
  if (el) mo.observe(el, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'], characterData: true });
});
// Quando o usuário clica no modelo e isso abre um editor (uma junta, a pintura, a marcação de um
// corte), a aba desse editor vem para a frente, como o painel do comando no Fusion.
let lastUser = 0;
F.host.addEventListener('pointerdown', () => { lastUser = performance.now(); }, true);
window.addEventListener('keydown', () => { lastUser = performance.now(); }, true);
$('#ribbon').addEventListener('pointerdown', () => { lastUser = performance.now(); }, true);
const follow = new MutationObserver((recs) => {
  if (performance.now() - lastUser > 1500) return;
  for (const r of recs) {
    const el = r.target;
    if (el.classList && el.classList.contains('hidden')) continue;
    if (r.type === 'childList' && !el.children.length) continue;
    reveal(el, false);
    break;
  }
});
['#joint-edit', '#paint-box', '#split-box', '#fc-mark'].forEach((s) => { const el = $(s); if (el) follow.observe(el, { attributes: true, attributeFilter: ['class'] }); });
['#fc-edit', '#pl-edit'].forEach((s) => { const el = $(s); if (el) follow.observe(el, { childList: true }); });

// tela vazia: o que fazer primeiro, no meio do canvas
const empty = document.createElement('div');
empty.id = 'empty-state';
empty.innerHTML = `<div class="es-card"><div class="es-ic" aria-hidden="true">📦</div><b>Abra um modelo para começar</b>
  <p>Arraste um STL, GLB, OBJ, .zip ou projeto (.flexiproj) para cá, ou</p>
  <div class="row"><button class="btn primary" id="es-open">📂 Abrir…</button><button class="btn" id="es-recent">🕘 Recentes</button></div></div>`;
F.host.parentElement.append(empty);
$('#es-open').onclick = () => click('#btn-open');
$('#es-recent').onclick = (e) => { e.stopPropagation(); openFileMenu(true); $('#btn-recent').click(); };
function refreshEmpty() { empty.classList.toggle('hidden', !!S.base); }

// soltar um arquivo em qualquer lugar da janela abre, como na área do Modelo
const dropZone = $('#drop');
let dragDepth = 0;
const hasFiles = (e) => e.dataTransfer && [...(e.dataTransfer.types || [])].includes('Files');
window.addEventListener('dragenter', (e) => { if (!hasFiles(e) || e.target.closest('#drop')) return; dragDepth++; document.body.classList.add('dropping'); });
window.addEventListener('dragleave', (e) => { if (!hasFiles(e)) return; dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) document.body.classList.remove('dropping'); });
window.addEventListener('dragover', (e) => { if (hasFiles(e) && !e.target.closest('#drop')) e.preventDefault(); });
window.addEventListener('drop', (e) => {
  dragDepth = 0;
  document.body.classList.remove('dropping');
  if (!hasFiles(e) || e.target.closest('#drop')) return;
  e.preventDefault();
  dropZone.dispatchEvent(new DragEvent('drop', { dataTransfer: e.dataTransfer, bubbles: false, cancelable: true }));
});

window.flexiShell = { setTab, reveal, tab: () => tab, fitAll, viewDir, refresh: refreshSoon, openFileMenu };
setTab(tab, { openPanel: true });
renderTree();
refreshEmpty();
setInterval(refreshSoon, 1500);
