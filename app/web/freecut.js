// EFC3D: Corte livre (módulo novo, v1.6).
// Arquivo separado de propósito: só lê o modelo pelo window.flexi e desenha os próprios objetos.
// O editor de juntas, a pintura e o "Separar por cor" não dependem dele.
//
// Um corte é definido por linhas desenhadas e/ou por uma área marcada (pincel e balde). A
// marcação não é pintura: não muda o filamento. A borda da área marcada vira linha de corte, e a
// área marcada diz qual lado é a peça.
import { baseSurface, meshSurface } from './surface.js';
const F = window.flexi;
const { THREE, S, scene, host, camera, controls, api, post, setStatus, nf, solidMat, hexRGB, unb64, CSS2DObject } = F;
const $ = (s) => document.querySelector(s);
// Superfície onde a marcação trabalha: o modelo inteiro, ou a peça de um corte numa peça já recortada
// (surface.js). Todas as ferramentas abaixo falam só com SF.
const BASE = baseSurface();
let SF = BASE;
let pieceMesh = null, basePrevVis = true;

const ENC = {
  colar: 'Só colar (sem pino)',
  redondo: 'Pino redondo: a peça gira',
  giratorio: 'Pino redondo com trava: gira e não sai',
  losango: 'Pino fixo (losango): alinha e cola',
  trava: 'Trava de pressão: encaixa sem cola',
  peca: 'Pino na peça (furo no corpo)',
  cavilha: 'Cavilha solta (furo nos dois lados)',
  manual: 'Conector manual: você posiciona depois da prévia',
};
const ENC_CURTO = { colar: 'colar', redondo: 'gira', giratorio: 'gira com trava', losango: 'pino fixo', trava: 'trava', peca: 'pino na peça', cavilha: 'cavilha', manual: 'conector manual' };
const FORMAS = { auto: 'Automático (plano quando a linha permite)', curva: 'Seguir a linha (face curva)', plano: 'Plano pela linha (face plana)', tampao: 'Tampão: paredes retas (beta)' };
const FOLGA_TAMPAO = 0.3;
const GIRA = ['redondo', 'giratorio'];
const LUZ = { ok: '🟢', aviso: '🟡', erro: '🔴', nada: '⚪' };
const DEF = { forma: 'auto', encaixe: 'colar', folga: 0.2, folga_pino: 0.4, pino_mm: 0, inverter: false, soquete: true, soquete_mm: 4 };
const TINTS = ['#d9622b', '#2b6fd9', '#2f8f3f', '#9b51c9', '#c9a227', '#1fa3a3', '#c94f7c'];
const TOOLS = { linha: '✏ Linha', pincel: '🖌 Pincel', balde: '🪣 Balde', borracha: '🧽 Borracha' };
const store = { get(k, d) { try { const v = localStorage.getItem('flexi-fc-' + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem('flexi-fc-' + k, JSON.stringify(v)); } catch (e) { /* sem armazenamento */ } } };

const FC = {
  marking: false, cur: -1, tool: store.get('tool', 'linha'), pts: [], path: [], undo: [],
  cuts: [], sel: -1, nextId: 1, result: null, ownSplitting: false,
};
const group = new THREE.Group(); group.renderOrder = 29; scene.add(group);
const maskGroup = new THREE.Group(); maskGroup.renderOrder = 26; scene.add(maskGroup);
const prevOn = () => !!(window.flexiPecas && window.flexiPecas.active());
const hover = new THREE.LineSegments(new THREE.BufferGeometry(),
  new THREE.LineBasicMaterial({ color: 0xffffff, depthTest: false, transparent: true, opacity: 0.95 }));
hover.renderOrder = 30; hover.visible = false; scene.add(hover);
const hoverTint = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.4,
  depthWrite: false, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -3, polygonOffsetUnits: -3 }));
hoverTint.renderOrder = 28; hoverTint.visible = false; scene.add(hoverTint);
const ring = new THREE.Mesh(new THREE.RingGeometry(0.92, 1, 40), new THREE.MeshBasicMaterial({ color: 0xd9622b, depthTest: false, side: THREE.DoubleSide }));
ring.renderOrder = 31; ring.visible = false; scene.add(ring);

// ---------------------------------------------------------------- modo (bloqueia as juntas enquanto marca ou mostra a prévia)
function busy(on) {
  if (on && !FC.ownSplitting) {
    if (S.painting) F.setPainting(false);
    if (window.flexiSplit && window.flexiSplit.SP.on) window.flexiSplit.close();
    FC.ownSplitting = true;
    S.splitting = true;
    F.setView(false);
  } else if (!on && FC.ownSplitting) {
    FC.ownSplitting = false;
    if (!(window.flexiSplit && window.flexiSplit.SP.on)) S.splitting = false;
    F.setView(false);
    F.renderJoints();
  }
}
// como na pintura: botão esquerdo marca, botão direito (ou Espaço + arrastar) gira a vista
let spaceDown = false;
function mouseForMarking(on) {
  controls.mouseButtons.LEFT = on && !spaceDown ? -1 : THREE.MOUSE.ROTATE;
  controls.mouseButtons.RIGHT = on ? THREE.MOUSE.ROTATE : THREE.MOUSE.PAN;
}

// ---------------------------------------------------------------- máscara (área marcada)
function adjQuiet() {          // vizinhança da malha sem trocar a mensagem do status
  const el = document.querySelector('#status'), prev = el ? el.textContent : '';
  const a = SF.adjacency();
  if (el && el.textContent !== prev) setStatus(prev);
  return a;
}
const triN = () => (SF.tri() ? SF.tri().n : 0);
function cutMask(c, make) {
  if (!c.mask && make) c.mask = new Uint8Array(triN());
  return c.mask;
}
const marked = (c) => { let n = 0; if (c.mask) for (let i = 0; i < c.mask.length; i++) n += c.mask[i]; return n; };
function pushUndo(c) {
  FC.undo.push({ mask: c.mask ? c.mask.slice() : null, lines: c.linhas.slice(), pts: FC.pts.slice() });
  if (FC.undo.length > 30) FC.undo.shift();
}
function undoAction() {
  const c = FC.cuts[FC.cur];
  const u = FC.undo.pop();
  if (!c || !u) { setStatus('Nada para desfazer.'); return; }
  c.mask = u.mask; c.linhas = u.lines;
  if (u.pts) rebuildPath(u.pts);
  changed(c);
  setStatus('Desfeito.');
}
function brushR() { return parseFloat($('#fc-brush-r').value) || 3; }
function brushAt(p, dir, erase) {
  const c = FC.cuts[FC.cur];
  const m = cutMask(c, true);
  const { cen, nrm, n } = SF.tri();
  const r2 = brushR() ** 2, vis = $('#fc-brush-vis').checked;
  let ch = 0;
  for (let t = 0; t < n; t++) {
    const dx = cen[t * 3] - p.x, dy = cen[t * 3 + 1] - p.y, dz = cen[t * 3 + 2] - p.z;
    if (dx * dx + dy * dy + dz * dz > r2) continue;
    if (vis && nrm[t * 3] * dir.x + nrm[t * 3 + 1] * dir.y + nrm[t * 3 + 2] * dir.z > 0.15) continue;
    const v = erase ? 0 : 1;
    if (m[t] !== v) { m[t] = v; ch++; }
  }
  if (ch) requestMaskDraw();
}
// borracha: tira as linhas deste corte que ela toca
function eraseLines(p) {
  const c = FC.cuts[FC.cur];
  if (!c || !c.linhas.length) return 0;
  const r2 = brushR() ** 2;
  const keep = c.linhas.filter((L) => !L.p.some((q) => (q[0] - p.x) ** 2 + (q[1] - p.y) ** 2 + (q[2] - p.z) ** 2 <= r2));
  const gone = c.linhas.length - keep.length;
  if (gone) { c.linhas = keep; hoverKey = ''; draw(); }
  return gone;
}
// linhas deste corte, como arestas bloqueadas para o balde
function lineVerts(L) {
  if (L.v && L.v.length) return L.v;
  const { vp, nv } = SF.ensureVGraph();
  const near = (q) => { let b = 0, bd = Infinity; for (let v = 0; v < nv; v++) { const d = (vp[v * 3] - q[0]) ** 2 + (vp[v * 3 + 1] - q[1]) ** 2 + (vp[v * 3 + 2] - q[2]) ** 2; if (d < bd) { bd = d; b = v; } } return b; };
  const ids = L.p.map(near);
  const out = [];
  for (let i = 0; i < ids.length; i++) {
    const seg = SF.surfacePath(ids[i], ids[(i + 1) % ids.length]);
    out.push(...seg.slice(0, -1));
  }
  L.v = out;
  return out;
}
function blockedEdges(c) {
  const set = new Set();
  if (!$('#fc-fill-stop').checked) return set;
  SF.adjacency();
  const nvk = SF.nv();
  c.linhas.forEach((L) => {
    const v = lineVerts(L);
    for (let i = 0; i < v.length; i++) { const a = v[i], b = v[(i + 1) % v.length]; set.add(a < b ? a * nvk + b : b * nvk + a); }
  });
  return set;
}
function region(seed, erase) {
  const c = FC.cuts[FC.cur];
  const adj = SF.adjacency(), vid = SF.vid(), nvk = SF.nv();
  const { nrm, n } = SF.tri();
  const ang = parseFloat($('#fc-fill-a').value) || 30;
  const all = ang >= 180, cosT = Math.cos(THREE.MathUtils.degToRad(Math.min(179.9, ang)));
  const byDir = $('#fc-fill-mode').value === 'direcao';
  const blk = blockedEdges(c);
  const m = c.mask;
  if (erase && (!m || !m[seed])) return { list: new Int32Array(0), mask: new Uint8Array(n) };
  const mask = new Uint8Array(n), q = new Int32Array(n);
  let qh = 0, qt = 0;
  q[qt++] = seed; mask[seed] = 1;
  while (qh < qt) {
    const t = q[qh++];
    for (let k = 0; k < 3; k++) {
      const u = adj[t * 3 + k];
      if (u < 0 || mask[u]) continue;
      if (erase && !m[u]) continue;
      if (blk.size) { const a = vid[t * 3 + k], b = vid[t * 3 + (k + 1) % 3]; if (blk.has(a < b ? a * nvk + b : b * nvk + a)) continue; }
      const r0 = byDir ? seed : t;
      const dot = nrm[r0 * 3] * nrm[u * 3] + nrm[r0 * 3 + 1] * nrm[u * 3 + 1] + nrm[r0 * 3 + 2] * nrm[u * 3 + 2];
      if (!all && dot < cosT) continue;
      mask[u] = 1; q[qt++] = u;
    }
  }
  return { list: q.subarray(0, qt), mask };
}
function outline(list, inMask, lift = 0.05) {
  const pos = SF.mesh().geometry.attributes.position.array, N = SF.tri().nrm, adj = adjQuiet();
  const seg = [];
  for (let i = 0; i < list.length; i++) {
    const t = list[i];
    const nx = N[t * 3] * lift, ny = N[t * 3 + 1] * lift, nz = N[t * 3 + 2] * lift;
    for (let k = 0; k < 3; k++) {
      const u = adj[t * 3 + k];
      if (u >= 0 && inMask[u]) continue;
      const a = t * 9 + k * 3, b = t * 9 + ((k + 1) % 3) * 3;
      seg.push(pos[a] + nx, pos[a + 1] + ny, pos[a + 2] + nz, pos[b] + nx, pos[b + 1] + ny, pos[b + 2] + nz);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(seg, 3));
  return g;
}
let hoverSeed = -1, hoverFrame = 0, hoverKey = '';
function hoverRegion(seed, erase) {
  if (seed < 0) { hover.visible = false; hoverTint.visible = false; hoverKey = ''; return; }
  const key = `${seed}|${erase}|${$('#fc-fill-a').value}|${$('#fc-fill-stop').checked}|${$('#fc-fill-mode').value}`;
  if (key === hoverKey) return;
  hoverKey = key;
  const r = region(seed, erase);
  hover.geometry.dispose();
  hover.geometry = outline(r.list, r.mask, 0.08);
  hover.material.color.set(erase ? 0x2b6fd9 : 0xffffff);
  hover.visible = true;
  const pos = SF.mesh().geometry.attributes.position.array;
  const tp = new Float32Array(r.list.length * 9);
  for (let i = 0; i < r.list.length; i++) tp.set(pos.subarray(r.list[i] * 9, r.list[i] * 9 + 9), i * 9);
  hoverTint.geometry.dispose();
  const tg = new THREE.BufferGeometry();
  tg.setAttribute('position', new THREE.BufferAttribute(tp, 3));
  hoverTint.geometry = tg;
  hoverTint.material.color.set(erase ? 0x2b6fd9 : 0xffffff);
  hoverTint.visible = true;
  hover.userData = { seed, erase, r };
  setStatus(erase ? `Balde: ${r.list.length.toLocaleString('pt-BR')} triângulos saem da marcação (Shift + clique).`
    : `Balde: ${r.list.length.toLocaleString('pt-BR')} triângulos; clique para marcar. Se vazar, desenhe uma linha onde deve parar (L) e volte ao balde.`);
}
function bucketAt(seed, erase) {
  const c = FC.cuts[FC.cur];
  const r = hover.visible && hover.userData.seed === seed && hover.userData.erase === erase ? hover.userData.r : region(seed, erase);
  if (!r.list.length) return;
  pushUndo(c);
  const m = cutMask(c, true);
  for (let i = 0; i < r.list.length; i++) m[r.list[i]] = erase ? 0 : 1;
  hoverKey = '';
  hover.visible = false; hoverTint.visible = false;
  changed(c);
  setStatus(`${c.nome}: ${marked(c).toLocaleString('pt-BR')} triângulos marcados. A borda da área vira a linha do corte.`);
}

// ---------------------------------------------------------------- desenho da linha
function clickLine(e, h) {
  const v = SF.nearestCorner(h);
  const { vp } = SF.ensureVGraph();
  if (FC.pts.length >= 3) {
    const [sx, sy] = SF.screenOf(FC.pts[0]);
    const f0 = FC.pts[0];
    const dw = Math.hypot(vp[v * 3] - vp[f0 * 3], vp[v * 3 + 1] - vp[f0 * 3 + 1], vp[v * 3 + 2] - vp[f0 * 3 + 2]);
    if (Math.hypot(sx - e.clientX, sy - e.clientY) < 14 && dw < 4) { closeLine(); return; }
  }
  if (FC.pts.length && FC.pts[FC.pts.length - 1] === v) return;
  if (FC.pts.length) FC.path.push(SF.surfacePath(FC.pts[FC.pts.length - 1], v).slice(1));
  else FC.path.push([v]);
  FC.pts.push(v);
  draw();
  setStatus(`Linha: ${FC.pts.length} ponto(s). Clique no primeiro ponto ou tecle Enter para fechar; Backspace desfaz o último ponto.`);
}
function undoPoint() {
  if (!FC.pts.length) return false;
  FC.pts.pop(); FC.path.pop(); draw();
  setStatus(FC.pts.length ? `Linha: ${FC.pts.length} ponto(s). Último ponto desfeito.` : 'Linha em andamento apagada.');
  return true;
}
// ⌘Z: com uma linha em andamento, desfaz só o último ponto dela (a linha fechada antes fica)
function undoSmart() { if (!undoPoint()) undoAction(); }
function rebuildPath(pts) {
  FC.pts = pts.slice(); FC.path = [];
  FC.pts.forEach((v, i) => FC.path.push(i ? SF.surfacePath(FC.pts[i - 1], v).slice(1) : [v]));
  draw();
}
// borracha sobre a linha em andamento: tira os pontos (e trechos) que ela toca; o resto continua
function eraseOpen(p) {
  if (!FC.pts.length) return 0;
  const { vp } = SF.ensureVGraph(), r2 = brushR() ** 2;
  const hit = (v) => (vp[v * 3] - p.x) ** 2 + (vp[v * 3 + 1] - p.y) ** 2 + (vp[v * 3 + 2] - p.z) ** 2 <= r2;
  const keep = FC.pts.filter((v, i) => !hit(v) && !(FC.path[i] || []).some(hit));
  const gone = FC.pts.length - keep.length;
  if (gone) rebuildPath(keep);
  return gone;
}
function closeLine() {
  const c = FC.cuts[FC.cur];
  if (!c) return false;
  if (FC.pts.length < 3) { setStatus('Linha: marque pelo menos 3 pontos em volta da parte.'); return false; }
  const back = SF.closingPath(FC.path, FC.pts[FC.pts.length - 1], FC.pts[0]);
  const full = [].concat(...FC.path, back.slice(1, -1));
  if (new Set(full).size < 6) { setStatus('Linha curta demais: clique pontos que deem a volta na parte (gire a vista com o botão direito).'); return false; }
  const { vp, vn } = SF.ensureVGraph();
  const step = Math.max(1, Math.ceil(full.length / 600));
  const loop = full.filter((_, k) => k % step === 0);
  pushUndo(c);
  c.linhas.push({ p: loop.map((v) => [vp[v * 3], vp[v * 3 + 1], vp[v * 3 + 2]].map((x) => +x.toFixed(3))),
    n: loop.map((v) => [vn[v * 3], vn[v * 3 + 1], vn[v * 3 + 2]].map((x) => +x.toFixed(3))), v: full });
  FC.pts = []; FC.path = [];
  changed(c);
  setStatus(`${c.nome}: linha fechada (${c.linhas.length} no total). Continue marcando, ou Enter para concluir. ` +
    'Dica: com o balde (F) você marca o lado que vai sair, e ele para nesta linha.');
  return true;
}

// ---------------------------------------------------------------- modo de marcação
function newCut() {
  if (!S.base) { setStatus('Carregue um modelo primeiro.'); return; }
  FC.cuts.push(Object.assign({ id: FC.nextId, nome: novoNome(), linhas: [], mask: null, luz: 'nada', checks: null }, DEF));
  FC.nextId++;
  startMark(FC.cuts.length - 1);
}
// Corte numa peça já recortada: a marcação é a mesma, só que sobre a malha da peça como ela está antes
// deste corte (inclusive as faces de corte), que vem do servidor (a mesma malha que o corte vai usar).
async function enterPiece(c, k) {
  const pn = c.peca.nome || '';
  setStatus(`${c.nome}: preparando a peça "${pn}" para marcar (os cortes anteriores são aplicados)…`);
  const geo = await window.flexiPecaCorte.hostGeometry(k);
  if (!geo.attributes.normal) geo.computeVertexNormals();
  const col = new Float32Array(geo.attributes.position.count * 3).fill(0.82);
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  if (F.comBVH) F.comBVH(geo);
  pieceMesh = new THREE.Mesh(geo, solidMat({}));
  scene.add(pieceMesh);
  basePrevVis = S.base.visible;
  S.base.visible = false;
  SF = meshSurface(pieceMesh);
  const n = SF.tri().n;
  if (c.mask && c.mask.length !== n) {
    c.mask = null;
    setStatus(`${c.nome}: a peça mudou desde a marcação (um corte anterior foi editado); a área marcada foi apagada. Marque de novo.`);
  }
  c.linhas.forEach((L) => { delete L.v; });              // vértices da linha: são achados de novo nesta malha
}
function leavePiece() {
  if (SF === BASE) return;
  const c = FC.cuts[FC.cur];
  if (c) {
    const p = labelPos(c);                               // posição do rótulo (a área marcada é da peça, não do modelo)
    c.rotulo = p ? p.map((x) => +x.toFixed(2)) : null;
    c.linhas.forEach((L) => { delete L.v; });
  }
  SF = BASE;
  if (pieceMesh) { scene.remove(pieceMesh); pieceMesh.geometry.dispose(); pieceMesh = null; }
  if (S.base) S.base.visible = basePrevVis;
}
const onSurface = (c, k) => (SF === BASE ? !c.peca : k === FC.cur);
async function startMark(k) {
  if (!FC.cuts[k]) return;
  if (FC.marking) finishMark(true);
  showPreview(false);
  const c0 = FC.cuts[k];
  if (c0.peca) {
    try { await enterPiece(c0, k); } catch (err) {
      leavePiece();
      setStatus(`${c0.nome}: não deu para preparar a peça: ${err.message}`);
      if (!c0.linhas.length && !marked(c0)) { FC.cuts.splice(k, 1); FC.sel = FC.cuts.length - 1; renderList(); draw(); }
      return;
    }
  }
  busy(true);
  if (SF !== BASE) S.base.visible = false;               // busy() mostra o modelo de novo: na peça ele fica escondido
  SF.ensureVGraph(); SF.adjacency();
  FC.marking = true; FC.cur = k; FC.sel = k; FC.undo = []; FC.pts = []; FC.path = [];
  mouseForMarking(true);
  $('#fc-mark').classList.remove('hidden');
  $('#fc-new').classList.add('hidden');
  if ($('#pm-new')) $('#pm-new').classList.add('hidden');
  $('#fc-mark-name').textContent = FC.cuts[k].peca ? `${FC.cuts[k].nome} · na peça ${FC.cuts[k].peca.nome || ''}` : FC.cuts[k].nome;
  setTool(FC.tool);
  info(FC.cuts[k]);
  renderList(); draw(); requestMaskDraw();
}
function finishMark(silent) {
  if (!FC.marking) return;
  const c = FC.cuts[FC.cur];
  if (FC.pts.length >= 3) closeLine();
  FC.marking = false; FC.pts = []; FC.path = [];
  hover.visible = false; hoverTint.visible = false; ring.visible = false;
  leavePiece();
  mouseForMarking(false);
  $('#fc-mark').classList.add('hidden');
  $('#fc-new').classList.remove('hidden');
  if ($('#pm-new')) $('#pm-new').classList.remove('hidden');
  busy(false);
  if (c && !c.linhas.length && !marked(c)) {
    FC.cuts.splice(FC.cur, 1);
    FC.sel = FC.cuts.length - 1;
    if (!silent) setStatus('Corte vazio descartado: desenhe uma linha ou marque uma área.');
  } else if (c && !silent) {
    const mk = marked(c);
    setStatus(`${c.nome}: ${c.linhas.length} linha(s)${mk ? ` e área marcada (${mk.toLocaleString('pt-BR')} triângulos)` : ''}. ` +
      'Escolha o encaixe e clique em "Prévia das peças".');
  }
  FC.cur = -1;
  renderList(); draw(); requestMaskDraw();
}
function setTool(t) {
  FC.tool = TOOLS[t] ? t : 'linha';
  store.set('tool', FC.tool);
  document.querySelectorAll('[data-fct]').forEach((b) => { const on = b.dataset.fct === FC.tool; b.classList.toggle('on', on); b.setAttribute('aria-pressed', on); });
  ['linha', 'pincel', 'balde'].forEach((x) => $('#fc-opt-' + x).classList.toggle('hidden', x !== (FC.tool === 'borracha' ? 'pincel' : FC.tool)));
  hover.visible = false; hoverTint.visible = false; hoverKey = ''; ring.visible = false;
  const msg = { linha: 'Linha: clique pontos em volta da parte; a linha segue a superfície. Primeiro ponto ou Enter fecha.',
    pincel: 'Pincel: arraste sobre a parte que vai sair para marcá-la. Shift + arrastar desmarca. [ e ] mudam o tamanho.',
    balde: 'Balde: passe o mouse para ver a área e clique para marcar. Shift + clique desmarca. Ele para nas linhas deste corte.',
    borracha: 'Borracha: arraste para desmarcar a área; as linhas que ela tocar também saem. [ e ] mudam o tamanho. ⌘Z desfaz.' }[FC.tool];
  setStatus(msg);
}
function changed(c) {
  c.luz = 'nada'; c.checks = null;
  invalidate();
  renderList(); draw(); requestMaskDraw();
  info(c);
}
function info(c) {
  const mk = marked(c);
  $('#fc-mark-info').textContent = `${c.linhas.length} linha(s) · ${mk ? mk.toLocaleString('pt-BR') + ' triângulos marcados' : 'nenhuma área marcada'}`;
}

// ---------------------------------------------------------------- desenho na tela
let maskFrame = 0;
function requestMaskDraw() {
  if (maskFrame) return;
  maskFrame = requestAnimationFrame(() => { maskFrame = 0; drawMasks(); });
}
function drawMasks() {
  maskGroup.children.slice().forEach((o) => { maskGroup.remove(o); F.disposeTree(o); });
  if (!SF.mesh() || !SF.tri()) return;
  const pos = SF.mesh().geometry.attributes.position.array;
  FC.cuts.forEach((c, k) => {
    if (c.oculto && k !== FC.cur) return;
    if (!onSurface(c, k)) return;
    if (!c.mask || c.mask.length !== triN()) return;
    const list = [];
    for (let t = 0; t < c.mask.length; t++) if (c.mask[t]) list.push(t);
    if (!list.length) return;
    const on = k === FC.sel;
    const tp = new Float32Array(list.length * 9);
    list.forEach((t, i) => tp.set(pos.subarray(t * 9, t * 9 + 9), i * 9));
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(tp, 3));
    const tint = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ color: on ? 0xd9622b : 0x8a8f96, transparent: true, opacity: on ? 0.38 : 0.22,
      depthWrite: false, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }));
    tint.renderOrder = 26;
    maskGroup.add(tint);
    const og = outline(list, c.mask, 0.08);
    const ol = F.penSegments(og.attributes.position.array, on ? 0xd9622b : 0x1f2328);
    og.dispose();
    if (ol) maskGroup.add(ol);
  });
}
function lineObj(pts, norms, color, closed) { return F.penLine(pts, color, closed, norms, 0.15); }
function labelPos(c) {
  const L = c.linhas[0];
  if (L && L.p.length) {
    const m = [0, 0, 0];
    L.p.forEach((q) => { m[0] += q[0]; m[1] += q[1]; m[2] += q[2]; });
    return m.map((x) => x / L.p.length);
  }
  if (c.peca && SF === BASE) return c.rotulo || null;     // área marcada numa peça: não é do modelo
  if (c.mask && SF.tri()) {
    const { cen } = SF.tri();
    const m = [0, 0, 0]; let n = 0;
    for (let t = 0; t < c.mask.length; t += 7) if (c.mask[t]) { m[0] += cen[t * 3]; m[1] += cen[t * 3 + 1]; m[2] += cen[t * 3 + 2]; n++; }
    if (n) return m.map((x) => x / n);
  }
  return null;
}
function draw() {
  group.children.slice().forEach((o) => { group.remove(o); if (o.element) o.element.remove(); F.disposeTree(o); });
  FC.cuts.forEach((c, k) => {
    if (c.oculto && k !== FC.cur) return;
    if (SF !== BASE && k !== FC.cur) return;             // marcando numa peça: só o corte dela
    const col = k === FC.sel ? 0xd9622b : 0x1f2328;
    c.linhas.forEach((L) => { const o = lineObj(L.p, L.n, col, true); if (o) group.add(o); });
    const p = labelPos(c);
    if (p) {
      const div = document.createElement('div');
      div.className = 'fc-lbl' + (k === FC.sel ? ' on' : '');
      div.textContent = `✂ C${k + 1}`;
      const lab = new CSS2DObject(div);
      lab.position.set(p[0], p[1], p[2]);
      group.add(lab);
    }
  });
  if (FC.marking && FC.pts.length) {
    const { vp, vn } = SF.ensureVGraph();
    const cur = [].concat(...FC.path);
    const o = lineObj(cur.map((v) => [vp[v * 3], vp[v * 3 + 1], vp[v * 3 + 2]]), cur.map((v) => [vn[v * 3], vn[v * 3 + 1], vn[v * 3 + 2]]), 0xd9622b, false);
    if (o) group.add(o);
    FC.pts.forEach((v) => {
      const s = new THREE.Mesh(new THREE.SphereGeometry(0.35, 10, 8), new THREE.MeshBasicMaterial({ color: 0xd9622b }));
      s.position.set(vp[v * 3], vp[v * 3 + 1], vp[v * 3 + 2]);
      group.add(s);
    });
  }
}
setInterval(() => {
  if (SF !== BASE && S.base && S.base.visible) S.base.visible = false;   // marcando numa peça: o modelo inteiro não aparece
  const vis = !!S.base && !S.showPieces && !prevOn() && !S.painting;
  if (group.visible !== vis) { group.visible = vis; group.children.forEach((o) => { if (o.element) o.element.style.display = vis ? '' : 'none'; }); }
  maskGroup.visible = vis;
}, 400);

// ---------------------------------------------------------------- lista e painel do corte
function renderList() {
  const ol = $('#fc-list');
  ol.innerHTML = '';
  // o que sobra depois dos cortes (o "Corpo"): também pode ser ocultado, depois da prévia. Num modelo
  // em que a linha contorna o rosto, o Corpo é o cabelo, e é ele que cobre o pescoço.
  if (FC.cuts.length && window.flexiPecas && window.flexiPecas.canHide()) {
    ol.append(window.flexiUI.row({ luz: '▪', tag: 'Corpo', meta: 'o que sobra depois dos cortes (na prévia)', hidden: !!FC.corpoOculto,
      onToggle: () => toggleBody() }));
  }
  FC.cuts.forEach((c, k) => {
    const mk = c.mask && marked(c);
    ol.append(window.flexiUI.row({ list: 'cortes', luz: LUZ[c.luz || 'nada'], tag: `C${k + 1}`,
      meta: `${c.nome} · ${ENC_CURTO[c.encaixe]}${c.semPino && c.luz !== 'nada' ? ' (⚠ saiu sem pino)' : ''} · ${c.linhas.length} linha(s)${mk ? ' + área marcada' : ''}${c.peca ? ` · na peça ${c.peca.nome || ''}` : ''}`,
      selected: k === FC.sel, hidden: !!c.oculto,
      onSelect: () => select(k), onDelete: () => removeCut(k), delTitle: 'Excluir este corte (Delete)',
      onToggle: () => toggleHide(c) }));
  });
  $('#fc-actions').classList.toggle('hidden', !FC.cuts.length || FC.marking);
  renderEdit();
}
// 👁 de um corte: esconde as linhas dele e, se a prévia já rodou, a peça dele na vista (o clique
// atravessa para marcar o que está por baixo). Não muda a prévia nem a exportação.
async function toggleHide(c) {
  c.oculto = !c.oculto;
  renderList(); draw(); requestMaskDraw();
  const P = window.flexiPecas;
  if (!P) return;
  if (c.oculto && !P.canHide()) { setStatus(`${c.nome}: linhas ocultas. Para ocultar também a peça e marcar o que está por baixo, rode a prévia das peças (Ver › Prévia).`); return; }
  const k = await P.applyHide();
  if (c.oculto && k) setStatus(`${c.nome} oculto: a peça some da vista e o clique passa por ela. Marque ou pinte o que está por baixo; a prévia e a exportação continuam com todas as peças. 👁 mostra de novo.`);
  else if (!c.oculto) setStatus(`${c.nome} aparece de novo.`);
}
async function toggleBody() {
  FC.corpoOculto = !FC.corpoOculto;
  renderList();
  const k = await window.flexiPecas.applyHide();
  setStatus(FC.corpoOculto && k ? 'Corpo oculto: a peça que sobra depois dos cortes some da vista e o clique passa por ela. A prévia e a exportação continuam com todas as peças. 👁 mostra de novo.'
    : 'Corpo aparece de novo.');
}
function hiddenCuts() {
  const s = new Set();
  FC.cuts.filter((c) => c.linhas.length || (c.mask && marked(c))).forEach((c, i) => { if (c.oculto) s.add(i); });
  return s;
}
function select(k) {
  if (FC.marking && k !== FC.cur) finishMark(false);
  FC.sel = k;
  renderList(); draw(); requestMaskDraw();
}
// ---------------------------------------------------------------- cascata de cortes (regra A, 06/11/2026)
// Um corte desenhado na peça que outro corte gerou depende dele (o nome da peça é o do corte, ou o do corte e um
// número). Excluir ou modificar o pai exclui todos os que dependem dele (filhos, netos), com aviso antes e desfazer.
function depende(c, pai) {
  const pn = String((c.peca && c.peca.nome) || '').trim();
  if (!pn || !pai) return false;
  if (pn === pai) return true;
  return pn.startsWith(pai + ' ') && /^[()0-9 ]+$/.test(pn.slice(pai.length + 1));
}
function dependentes(nome) {
  const fila = [nome], achados = new Set();
  while (fila.length) {
    const n = fila.pop();
    FC.cuts.forEach((c) => { if (c.nome !== nome && !achados.has(c.nome) && depende(c, n)) { achados.add(c.nome); fila.push(c.nome); } });
  }
  return FC.cuts.filter((c) => achados.has(c.nome)).map((c) => c.nome);
}
function avisoCascata(nome, deps, modificar) {
  return modificar ? `Modificar o ${nome} exclui os cortes desenhados na peça dele: ${deps.join(', ')}.`
    : `Excluir o ${nome} exclui também os cortes desenhados na peça dele: ${deps.join(', ')}.`;
}
// janela de confirmação (Esc ou Cancelar desistem); resolve true se a pessoa confirmar
function confirmar(titulo, texto, botao) {
  return new Promise((resolve) => {
    const ov = document.createElement('div');
    ov.className = 'qual-ov';
    ov.setAttribute('role', 'alertdialog');
    ov.setAttribute('aria-modal', 'true');
    ov.innerHTML = `<div class="qual-box"><h3></h3><p class="hint"></p><p class="hint">⌘Z desfaz depois.</p>
      <div class="row"><button class="btn" data-r="0">Cancelar</button><button class="btn primary" data-r="1"></button></div></div>`;
    ov.querySelector('h3').textContent = titulo;
    ov.querySelector('p').textContent = texto;
    ov.querySelector('[data-r="1"]').textContent = botao;
    ov.setAttribute('aria-label', titulo);
    const fim = (v) => { document.removeEventListener('keydown', esc, true); ov.remove(); resolve(v); };
    const esc = (e) => { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); fim(false); } };
    document.addEventListener('keydown', esc, true);
    ov.querySelectorAll('[data-r]').forEach((b) => { b.onclick = () => fim(b.dataset.r === '1'); });
    document.body.append(ov);
    if (window.flexiI18n && window.flexiI18n.retranslate) window.flexiI18n.retranslate(ov);
    ov.querySelector('[data-r="1"]').focus();
  });
}
// antes de mudar a marcação de um corte (linhas, área, lado): se outros cortes dependem dele, avisa, e ao
// confirmar exclui os dependentes (um passo de desfazer traz todos de volta). Devolve false se a pessoa desistir.
async function antesDeModificar(c) {
  const deps = dependentes(c.nome);
  if (!deps.length) return true;
  if (!await confirmar(`Modificar o ${c.nome}?`, avisoCascata(c.nome, deps, true), 'Modificar e excluir')) return false;
  const antes = FC.cuts.slice(), sel = FC.sel;
  window.flexiUI.push(`Cortes de ${c.nome}`, () => { FC.cuts.splice(0, FC.cuts.length, ...antes); FC.sel = sel; invalidate(); renderList(); draw(); requestMaskDraw(); });
  const fora = new Set(deps);
  for (let i = FC.cuts.length - 1; i >= 0; i--) if (fora.has(FC.cuts[i].nome)) FC.cuts.splice(i, 1);
  FC.sel = FC.cuts.indexOf(c);
  invalidate(); renderList(); draw(); requestMaskDraw();
  setStatus(`Excluídos com o ${c.nome}: ${deps.join(', ')}. ⌘Z traz de volta.`);
  return true;
}
async function removeCut(k) {
  if (FC.marking) finishMark(true);
  const gone = FC.cuts[k];
  if (!gone) return;
  const deps = dependentes(gone.nome);
  if (deps.length && !await confirmar(`Excluir o ${gone.nome}?`, avisoCascata(gone.nome, deps, false), 'Excluir todos')) return;
  const antes = FC.cuts.slice(), sel = FC.sel;
  window.flexiUI.push(`Corte C${k + 1}`, () => { FC.cuts.splice(0, FC.cuts.length, ...antes); FC.sel = Math.min(sel, FC.cuts.length - 1); invalidate(); renderList(); draw(); requestMaskDraw(); });
  const fora = new Set([gone.nome, ...deps]);
  for (let i = FC.cuts.length - 1; i >= 0; i--) if (FC.cuts[i] === gone || fora.has(FC.cuts[i].nome)) FC.cuts.splice(i, 1);
  if (FC.sel >= FC.cuts.length) FC.sel = FC.cuts.length - 1;
  invalidate();
  renderList(); draw(); requestMaskDraw();
  setStatus(deps.length ? `Excluídos: ${gone.nome}, ${deps.join(', ')}. ⌘Z traz de volta.` : 'Corte excluído. ⌘Z traz de volta.');
}
function invalidate() {
  FC.result = null;
  $('#fc-report').innerHTML = '';
  if (window.flexiPecas) window.flexiPecas.invalidate();
}
function renderEdit() {
  const box = $('#fc-edit');
  // durante a marcação o painel mostra as opções do corte que está sendo marcado (encaixe, pino,
  // soquete), para não ter de concluir antes de escolher
  const c = FC.marking ? FC.cuts[FC.cur] : FC.cuts[FC.sel];
  if (!c) { box.innerHTML = ''; return; }
  const mkMode = FC.marking;
  const gira = GIRA.includes(c.encaixe);
  const manual = c.encaixe === 'manual';
  const pino = c.encaixe !== 'colar' && !manual;
  const tamp = c.forma === 'tampao' && !gira;           // tampão (beta): a direção, o soquete e o motor são os dele
  const mk = marked(c);
  box.innerHTML = `<div class="card">
    ${mkMode ? `<div class="lbl3">Encaixe e pino de ${c.nome}</div>` : ''}
    <label>Nome<input type="text" data-k="nome" value=""></label>
    <label>Encaixe<select data-k="encaixe">${Object.entries(ENC).map(([k, t]) => `<option value="${k}" ${c.encaixe === k ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
    <label>Forma do corte<select data-k="forma" ${gira ? 'disabled' : ''}>${Object.entries(FORMAS).map(([k, t]) => `<option value="${k}" ${(gira ? 'plano' : c.forma) === k ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
    ${gira ? '<p class="hint">Para girar, a face do corte é plana.</p>' : ''}
    ${tamp ? `<p class="hint">Beta. A área dentro da linha sai como um tampão: paredes retas na direção de encaixe (o app acha a direção livre), fundo plano 2 mm abaixo do ponto mais baixo da área e a mesma folga em toda a volta. A costura fica exatamente na linha; com área marcada por pincel ou balde, a borda é suavizada como no corte por cor. Serve para o que se vê inteiro de um lado só (casco, olho, tampa, emblema); num braço ou numa perna ele recusa e diz por quê.${manual ? ' O conector manual não vale aqui: escolha outro encaixe.' : ''}</p>` : ''}
    ${gira || tamp ? '' : `<label>Direção de encaixe<select data-k="dir_modo"><option value="auto" ${c.dir_modo !== 'manual' ? 'selected' : ''}>Automática (o app sugere)</option><option value="manual" ${c.dir_modo === 'manual' ? 'selected' : ''}>Escolher</option></select></label>
    ${c.dir_modo === 'manual' ? `<div class="grid2"><label>Azimute (°)<input type="number" data-k="dir_az" min="0" max="359" step="5" value="${c.dir_az ?? 0}"></label>
      <label>Elevação (°)<input type="number" data-k="dir_el" min="-90" max="90" step="5" value="${c.dir_el ?? 0}"></label></div>
    <label>Quem sai nessa direção<select data-k="dir_quem"><option value="peca" ${c.dir_quem !== 'resto' ? 'selected' : ''}>A peça deste corte</option><option value="resto" ${c.dir_quem === 'resto' ? 'selected' : ''}>O resto do modelo</option></select></label>
    <p class="hint">Azimute 0 = para a frente, 90 = para a direita, 180 = para trás, 270 = para a esquerda. Elevação 90 = para cima, −90 = para baixo. Exemplo: cabelo que desce de cima, encaixando de trás: o resto sai com azimute 180 e elevação 60.</p>` : ''}
    ${c.dirSug ? `<p class="hint">Direção da última prévia: azimute ${c.dirSug.az}°, elevação ${c.dirSug.el}° (${c.dirSug.sugerida ? 'sugerida pelo app' : 'escolhida por você'}), para a peça deste corte.</p>` : ''}
    <label class="chk"><input type="checkbox" data-k="motor_antigo" ${c.motor_antigo ? 'checked' : ''}> Usar o motor anterior (1.44) neste corte</label>`}
    ${manual ? '<p class="hint">O corte sai só com as faces (navalha). Depois da prévia, em "Conectores manuais" logo abaixo, você posiciona o conector em cada junta: tipo, lugar, giro, diâmetro, profundidade e lado.</p>' : ''}
    ${manual || tamp ? '' : `<label class="chk"><input type="checkbox" data-k="soquete" ${c.soquete && !gira ? 'checked' : ''} ${gira ? 'disabled' : ''}> A peça entra no corpo (soquete)</label>`}
    ${c.soquete && !gira && !manual && !tamp ? `<label>Profundidade do soquete (mm)<input type="number" data-k="soquete_mm" min="1" max="30" step="0.5" value="${c.soquete_mm || 4}"></label>
    <p class="hint">Da linha para dentro o corte desce reto: toda a superfície dentro da linha vai com a peça e o corpo fica com a cavidade onde ela encaixa. O pino, se houver, fica no fundo.</p>
    <label class="chk"><input type="checkbox" data-k="anel_plano" ${c.anel_plano ? 'checked' : ''}> ▭ Anel plano na junta (apoio na mesa)</label>
    <p class="hint">Opcional. A face em volta do soquete fica plana nas duas peças, de frente para o eixo do encaixe, e a parede da boca do soquete fica com 2 mm. Assim a peça apoia na mesa por esse anel. Na pele, a divisa vira uma reta nesse trecho.</p>` : ''}
    <div class="grid2">
      <label>Folga entre as faces (mm)<input type="number" data-k="folga" min="0.05" max="2" step="0.05" value="${c.folga}"></label>
      ${pino && !tamp ? `<label>Folga do pino (mm)<input type="number" data-k="folga_pino" min="0.05" max="1" step="0.05" value="${c.folga_pino}"></label>` : '<span></span>'}
      ${pino ? `<label>Largura do pino (mm)<input type="number" data-k="pino_mm" min="1.2" step="0.1" value="${c.pino_mm || ''}" placeholder="automática"></label>` : ''}
    </div>
    ${tamp ? '' : `<label class="chk"><input type="checkbox" data-k="pele_exata" ${c.pele_exata ? 'checked' : ''}> ✂ Borda exata na pele (mais lento)</label>`}
    ${c.pele_exata && !tamp ? '<p class="hint">Para a divisa entre duas partes que se encostam num vinco (a mecha de cabelo na testa). Quando o corte precisa do volume, a borda na pele ficava até 1,5 mm para dentro da linha (uma faixa de pele lisa colada na outra peça). Com esta opção a borda chega no vinco. O corte demora mais (até uns 2 minutos a mais).</p>' : ''}
    <label class="chk"><input type="checkbox" data-k="inverter" ${c.inverter ? 'checked' : ''}> ${mk ? 'Inverter: a peça é o lado sem marcação' : 'Inverter: a peça é o outro lado da linha'}</label>
    ${mkMode ? '' : `<div class="row">
      <button class="btn primary" data-act="edit">✏ Editar a marcação</button>
      ${c.linhas.length ? '<button class="btn" data-act="less">− Última linha</button>' : ''}
      ${mk ? '<button class="btn" data-act="clear">Apagar a área marcada</button>' : ''}
    </div>`}
    <p class="hint">${c.linhas.length} linha(s)${mk ? ` e ${mk.toLocaleString('pt-BR')} triângulos marcados (a área marcada é a peça)` : ''}.
      Se a parte encosta em outro ponto (uma mão na perna, uma trança no peito), marque até lá ou desenhe uma linha nesse ponto.</p>
    ${!mkMode && c.checks ? '<ul class="checks">' + c.checks.map((x) => `<li class="${x.nivel}">${LUZ[x.nivel] || ''} ${x.texto}</li>`).join('') + '</ul>' : ''}
  </div>`;
  box.querySelector('[data-k="nome"]').value = c.nome;
  box.querySelectorAll('[data-k]').forEach((el) => {
    el.onchange = async () => {
      const k = el.dataset.k;
      let v = el.type === 'checkbox' ? el.checked : el.value;
      if (el.type === 'number') v = k.startsWith('dir_') ? (isNaN(parseFloat(v)) ? 0 : parseFloat(v)) : (parseFloat(v) || (k === 'pino_mm' ? 0 : DEF[k]));
      if (k === 'dir_modo' && v === 'manual' && c.dir_az === undefined && c.dirSug) { c.dir_az = c.dirSug.az; c.dir_el = c.dirSug.el; c.dir_quem = 'peca'; }
      if (k === 'nome') {                                // nomes únicos: as peças e os conectores são achados pelo nome
        v = String(v).trim() || c.nome;
        if (FC.cuts.some((x) => x !== c && x.nome === v)) { let n = 2; while (FC.cuts.some((x) => x !== c && x.nome === `${v} (${n})`)) n++; v = `${v} (${n})`; el.value = v; }
        // os cortes desenhados nas peças dele guardam o nome da peça: acompanham a troca
        const velho = c.nome;
        if (v !== velho) FC.cuts.forEach((x) => { if (x !== c && depende(x, velho)) x.peca = Object.assign({}, x.peca, { nome: v + x.peca.nome.slice(velho.length) }); });
      }
      if (k === 'inverter' && !await antesDeModificar(c)) { el.checked = !v; return; }
      c[k] = v;
      if (k === 'forma') {
        c.forma_fixa = v !== 'auto';                     // escolha do usuário: o app não troca a forma
        // tampão: folga de 0,3 mm (a do corte por cor) se o usuário não tinha mudado a folga; a volta desfaz
        if (v === 'tampao' && +c.folga === DEF.folga) c.folga = FOLGA_TAMPAO;
        else if (v !== 'tampao' && +c.folga === FOLGA_TAMPAO) c.folga = DEF.folga;
      }
      if (k !== 'nome') { c.luz = 'nada'; c.checks = null; invalidate(); }
      renderList(); draw();
      if (FC.marking) el.blur();                       // as teclas da marcação (L, B, F, E, Enter) voltam a valer
    };
  });
  if (mkMode) return;
  box.querySelector('[data-act="edit"]').onclick = async () => { const k = FC.sel; if (await antesDeModificar(c)) startMark(FC.cuts.indexOf(c) >= 0 ? FC.cuts.indexOf(c) : k); };   // corte numa peça: marca sobre a peça
  const less = box.querySelector('[data-act="less"]');
  if (less) less.onclick = async () => { if (!await antesDeModificar(c)) return; c.linhas.pop(); changed(c); };
  const clr = box.querySelector('[data-act="clear"]');
  if (clr) clr.onclick = async () => { if (!await antesDeModificar(c)) return; c.mask = null; changed(c); if (!c.linhas.length) setStatus('Sem linha e sem área: este corte não corta nada. Edite a marcação ou remova o corte.'); };
}

// ---------------------------------------------------------------- prévia
// a prévia é a única (pecas.js): peças por cor e cortes livres juntos
function runPreview() {
  if (FC.marking) finishMark(true);
  if (!forExport()) { setStatus('Crie um corte primeiro: desenhe uma linha ou marque uma área.'); return null; }
  return window.flexiPecas ? window.flexiPecas.run() : null;
}
function showPreview(on) { if (window.flexiPecas) window.flexiPecas.show(on); }
function applyResult(r) {
  FC.result = r;
  if (!r) { $('#fc-report').innerHTML = ''; renderList(); return; }
  const used = FC.cuts.filter((c) => c.linhas.length || (c.mask && marked(c)));
  (r.livres || []).forEach((x) => { const c = used[x.i]; if (c) { c.luz = x.luz; c.checks = x.checks; c.semPino = !!x.sem_pino; c.dirSug = x.dir || null; x.k = FC.cuts.indexOf(c); } });
  renderList();
  renderReport(r);
}
function renderReport(r) {
  const h = '<ul class="checks">' + r.livres.filter((x) => !x.plano).map((x) => {
    const prob = x.checks.filter((c) => c.nivel !== 'ok').map((c) => c.texto).join(' ');
    const ok = x.checks.filter((c) => c.nivel === 'ok').map((c) => c.texto).join(' ');
    return `<li class="${x.luz}">${LUZ[x.luz]} <b>C${(x.k ?? x.i) + 1} ${x.nome}</b>: ${x.ok ? ok : 'não cortado'}${prob ? ' ' + prob : ''}</li>`;
  }).join('') + '</ul>';
  $('#fc-report').innerHTML = h;
}

// ---------------------------------------------------------------- eventos
$('#fc-new').onclick = () => newCut();
$('#fc-done').onclick = () => finishMark(false);
$('#fc-close').onclick = () => closeLine();
$('#fc-undo-pt').onclick = () => undoPoint();
$('#fc-undo').onclick = () => undoSmart();
$('#fc-clear').onclick = () => { const c = FC.cuts[FC.cur]; if (!c) return; pushUndo(c); c.mask = null; c.linhas.length = 0; FC.pts = []; FC.path = []; changed(c); setStatus('Marcação limpa (⌘Z desfaz).'); };
document.querySelectorAll('[data-fct]').forEach((b) => b.addEventListener('click', () => setTool(b.dataset.fct)));
$('#fc-brush-r').oninput = () => { $('#fc-brush-v').textContent = nf(brushR(), 1) + ' mm'; };
$('#fc-fill-a').oninput = () => { $('#fc-fill-v').textContent = Math.round(parseFloat($('#fc-fill-a').value)) + '°'; hoverKey = ''; };
$('#fc-fill-stop').onchange = () => { hoverKey = ''; };
$('#fc-fill-mode').onchange = () => { hoverKey = ''; };
document.addEventListener('click', (e) => { if (e.target.closest && e.target.closest('#fc-list')) window.flexiUI.setActive('cortes', () => { if (FC.sel >= 0) removeCut(FC.sel); }); }, true);
$('#fc-prev').onclick = () => runPreview();
// marcando numa peça: sair da aba Cortes conclui a marcação (o modelo inteiro volta a aparecer)
document.querySelectorAll('#tabs [data-tab]').forEach((b) => b.addEventListener('click', () => { if (FC.marking && SF !== BASE && b.dataset.tab !== 'cortes') finishMark(false); }, true));
['#btn-split', '#btn-paint'].forEach((sel) => { const b = $(sel); if (b) b.addEventListener('click', () => { if (FC.marking) finishMark(false); }, true); });

let down = null, stroke = null;
host.addEventListener('pointerdown', (e) => {
  if (!FC.marking || e.button !== 0 || spaceDown) return;
  down = [e.clientX, e.clientY];
  if (FC.tool === 'pincel' || FC.tool === 'borracha') {
    const h = SF.hit(e);
    if (!h) return;
    const c = FC.cuts[FC.cur];
    pushUndo(c);
    const er = e.shiftKey || FC.tool === 'borracha';
    stroke = { last: h.point.clone(), erase: er, lines: 0 };
    brushAt(h.point, F.camera ? h.point.clone().sub(camera.position).normalize() : new THREE.Vector3(0, 0, -1), er);
    if (FC.tool === 'borracha') stroke.lines += eraseLines(h.point) + eraseOpen(h.point);
    host.setPointerCapture?.(e.pointerId);
    e.stopPropagation();
  }
}, true);
host.addEventListener('pointermove', (e) => {
  if (!FC.marking) return;
  if (FC.tool === 'pincel' || FC.tool === 'borracha') {
    const h = SF.hit(e);
    if (h) {
      const n = new THREE.Vector3(...[0, 1, 2].map((k) => SF.tri().nrm[h.faceIndex * 3 + k]));
      ring.position.copy(h.point).addScaledVector(n, 0.05);
      ring.lookAt(h.point.clone().add(n));
      ring.scale.setScalar(brushR());
      ring.material.color.set(e.shiftKey || FC.tool === 'borracha' ? 0x2b6fd9 : 0xd9622b);
      ring.visible = true;
    } else ring.visible = false;
    if (stroke && h && (e.buttons & 1)) {
      const dir = h.point.clone().sub(camera.position).normalize();
      const d = h.point.distanceTo(stroke.last), step = Math.max(0.3, brushR() * 0.4);
      for (let s = step; s < d; s += step) brushAt(stroke.last.clone().lerp(h.point, s / d), dir, stroke.erase);
      brushAt(h.point, dir, stroke.erase);
      if (FC.tool === 'borracha') stroke.lines += eraseLines(h.point) + eraseOpen(h.point);
      stroke.last = h.point.clone();
    }
    return;
  }
  if (FC.tool === 'balde' && !e.buttons) {
    const h = SF.hit(e);
    hoverSeed = h ? h.faceIndex : -1;
    const er = e.shiftKey;
    if (hoverFrame) return;
    hoverFrame = requestAnimationFrame(() => { hoverFrame = 0; if (FC.marking && FC.tool === 'balde') hoverRegion(hoverSeed, er); });
  }
}, true);
host.addEventListener('pointerleave', () => { ring.visible = false; if (FC.tool === 'balde') { hover.visible = false; hoverTint.visible = false; hoverKey = ''; } });
host.addEventListener('pointerup', (e) => {
  if (!FC.marking) return;
  if (stroke) {
    const nl = stroke.lines;
    stroke = null;
    const c = FC.cuts[FC.cur];
    changed(c);
    setStatus(`${c.nome}: ${marked(c).toLocaleString('pt-BR')} triângulos marcados${nl ? `, ${nl} linha(s) ou ponto(s) apagado(s)` : ''}${FC.pts.length ? `; linha em andamento com ${FC.pts.length} ponto(s), volte à Linha (L) para continuar` : ''}. Enter conclui; ⌘Z desfaz.`);
    return;
  }
  if (!down || e.button !== 0) return;
  const [x, y] = down;
  down = null;
  if (Math.hypot(e.clientX - x, e.clientY - y) > 4) return;
  const h = SF.hit(e);
  if (!h) return;
  e.stopPropagation();
  const oc = F.controls;                                  // o OrbitControls não vê este pointerup: avisa que o botão foi solto
  if (oc && Array.isArray(oc._pointers) && oc._pointers.includes(e.pointerId) && oc._onPointerUp) oc._onPointerUp(e);
  if (FC.tool === 'linha') clickLine(e, h);
  else if (FC.tool === 'balde') bucketAt(h.faceIndex, e.shiftKey);
}, true);
window.addEventListener('keydown', (e) => {
  if (!FC.marking) return;
  if (document.activeElement && ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName) && document.activeElement.type !== 'range' && document.activeElement.type !== 'checkbox') return;
  if (e.code === 'Space' && !spaceDown) { spaceDown = true; mouseForMarking(true); e.preventDefault(); return; }
  const k = e.key.toLowerCase();
  if ((e.metaKey || e.ctrlKey) && k === 'z') { e.preventDefault(); undoSmart(); return; }
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  if (k === 'l') setTool('linha');
  else if (k === 'b') setTool('pincel');
  else if (k === 'f') setTool('balde');
  else if (k === 'e') setTool('borracha');
  else if (k === '[' || k === ']') { $('#fc-brush-r').value = Math.max(0.5, Math.min(20, brushR() + (k === ']' ? 0.5 : -0.5))); $('#fc-brush-r').oninput(); }
  else if (e.key === 'Enter') { e.preventDefault(); if (FC.pts.length) closeLine(); else finishMark(false); }
  else if (e.key === 'Backspace') { e.preventDefault(); if (FC.pts.length) undoPoint(); }
  else if (e.key === 'Escape') { e.preventDefault(); if (FC.pts.length) { FC.pts = []; FC.path = []; draw(); setStatus('Linha em andamento apagada.'); } else finishMark(false); }
  else if (e.key === 'Shift' && FC.tool === 'balde' && hoverSeed >= 0) hoverRegion(hoverSeed, true);
});
window.addEventListener('keyup', (e) => {
  if (e.code === 'Space' && spaceDown) { spaceDown = false; if (FC.marking) mouseForMarking(true); }
  if (e.key === 'Shift' && FC.marking && FC.tool === 'balde' && hoverSeed >= 0) hoverRegion(hoverSeed, false);
});

// ---------------------------------------------------------------- projeto
function b64mask(m) {
  const n = m.length, bytes = new Uint8Array((n + 7) >> 3);
  for (let t = 0; t < n; t++) if (m[t]) bytes[t >> 3] |= 1 << (t & 7);
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(s);
}
function unmask(b64, n) {
  try {
    const raw = unb64(b64);
    if (raw.length * 8 < n) return null;
    const m = new Uint8Array(n);
    for (let t = 0; t < n; t++) m[t] = (raw[t >> 3] >> (t & 7)) & 1;
    return m;
  } catch (e) { return null; }
}
// nome de um corte novo que ainda não existe (depois de abrir um projeto, "Corte 10" pode já estar na lista)
function novoNome() {
  const usados = new Set(FC.cuts.map((c) => c.nome));
  let k = FC.nextId;
  FC.cuts.forEach((c) => { const m = /^Corte (\d+)$/.exec(c.nome || ''); if (m) k = Math.max(k, +m[1] + 1); });
  while (usados.has(`Corte ${k}`)) k++;
  FC.nextId = Math.max(FC.nextId, k);
  return `Corte ${k}`;
}
function cutOut(c) {
  const o = { nome: c.nome, linhas: c.linhas.map((L) => L.p), forma: GIRA.includes(c.encaixe) ? 'plano' : c.forma,
    encaixe: c.encaixe, folga: c.folga, folga_pino: c.folga_pino, pino_mm: c.pino_mm || 0, inverter: !!c.inverter,
    soquete: !!c.soquete && !GIRA.includes(c.encaixe) && c.encaixe !== 'manual' && c.forma !== 'tampao', soquete_mm: c.soquete_mm || 4 };
  if (c.forma_fixa) o.forma_fixa = true;
  if (o.soquete && c.anel_plano) o.anel_plano = true;
  if (c.encaixe === 'manual') o.manual = true;
  if (c.pele_exata) o.pele_exata = true;
  if (c.dir_modo === 'manual') o.direcao = { modo: 'manual', az: +c.dir_az || 0, el: +c.dir_el || 0, quem: c.dir_quem === 'resto' ? 'resto' : 'peca' };
  if (c.motor_antigo) o.motor_antigo = true;
  if (c.peca) o.peca = { ponto: c.peca.ponto, nome: c.peca.nome || '' };   // corte numa peça recortada
  if (c.mask && marked(c)) { o.mascara = b64mask(c.mask); o.n = c.mask.length; }   // (na peça: triângulos da malha da peça)
  return o;
}
// cortes antes do k (na ordem em que o servidor corta): a peça de um corte numa peça é a que existe
// depois deles
function exportBefore(k) {
  return FC.cuts.slice(0, k).filter((c) => c.linhas.length || (c.mask && marked(c))).map(cutOut);
}
function addPieceCut(peca) {
  FC.cuts.push(Object.assign({ id: FC.nextId, nome: novoNome(), linhas: [], mask: null, luz: 'nada', checks: null }, DEF, { peca }));
  FC.nextId++;
  FC.sel = FC.cuts.length - 1;
  renderList(); draw();
  return FC.cuts.length - 1;
}
function forExport() {
  const list = FC.cuts.filter((c) => c.linhas.length || (c.mask && marked(c)));
  return list.length ? list.map(cutOut) : null;
}
function state() {
  if (!FC.cuts.length) return null;
  const st = { versao: 2, cortes: FC.cuts.map((c) => Object.assign(cutOut(c), { linhas: c.linhas.map((L) => ({ p: L.p, n: L.n })), forma: c.forma },
    c.peca && c.rotulo ? { rotulo: c.rotulo } : {})) };
  const cn = window.flexiConectores ? window.flexiConectores.state() : null;
  if (cn && cn.length) st.conectores = cn;
  return st;
}
function restore(st) {
  if (FC.marking) finishMark(true);
  FC.corpoOculto = false;
  showPreview(false);
  FC.result = null;
  if (window.flexiPecas) window.flexiPecas.invalidate();
  FC.cuts = []; FC.sel = -1; FC.nextId = 1;
  if (st && Array.isArray(st.cortes)) {
    st.cortes.forEach((c) => {
      const linhas = (c.linhas || []).map((L) => (Array.isArray(L) ? { p: L, n: L.map(() => [0, 0, 0]) } : { p: L.p, n: L.n || L.p.map(() => [0, 0, 0]) }))
        .filter((L) => L.p && L.p.length >= 3);
      const mask = c.peca ? (c.mascara && c.n ? unmask(c.mascara, c.n) : null)      // área marcada na peça: da malha da peça
        : (c.mascara && triN() && (c.n || triN()) === triN() ? unmask(c.mascara, triN()) : null);
      if (!linhas.length && !(mask && mask.some((x) => x))) return;
      const cc = Object.assign({}, DEF, { soquete: false }, c, { id: FC.nextId++, linhas, mask, luz: 'nada', checks: null });
      delete cc.mascara; delete cc.n;
      if (c.direcao && c.direcao.modo === 'manual') { cc.dir_modo = 'manual'; cc.dir_az = c.direcao.az; cc.dir_el = c.direcao.el; cc.dir_quem = c.direcao.quem; }
      delete cc.direcao;
      if (cc.forma === 'curva' && !cc.forma_fixa) cc.forma = 'auto';   // projeto antigo: 'curva' era só o padrão
      // dois cortes com o mesmo nome (um corte recriado num projeto antigo): o segundo ganha outro nome
      if (FC.cuts.some((x) => x.nome === cc.nome)) { let k = 2; while (FC.cuts.some((x) => x.nome === `${c.nome} (${k})`)) k++; cc.nome = `${c.nome} (${k})`; }
      FC.cuts.push(cc);
    });
    FC.sel = FC.cuts.length ? 0 : -1;
  }
  $('#fc-report').innerHTML = '';
  if (window.flexiConectores) window.flexiConectores.restore(st && st.conectores);
  renderList(); draw(); requestMaskDraw();
}
function close() { if (FC.marking) finishMark(false); showPreview(false); }
// o modelo mudou de tamanho ou de lugar (Ajustar tamanho e base): as linhas e as áreas vão junto
function masksOut() {
  return FC.cuts.map((c, k) => (c.mask && marked(c) && !c.peca ? { k, mascara: b64mask(c.mask), n: c.mask.length } : null)).filter(Boolean);
}
function remap(mapa, masks) {
  if (FC.marking) finishMark(true);
  const s = mapa.s, t = mapa.t;
  FC.cuts.forEach((c) => {
    c.linhas.forEach((L) => { L.p = L.p.map((q) => [s * q[0] + t[0], s * q[1] + t[1], s * q[2] + t[2]]); });
    if (c.peca && c.peca.ponto) { const q = c.peca.ponto; c.peca = Object.assign({}, c.peca, { ponto: [s * q[0] + t[0], s * q[1] + t[1], s * q[2] + t[2]] }); }
    c.mask = null; c.luz = 'nada'; c.checks = null; c.rotulo = null;   // corte numa peça: a peça mudou, a área é marcada de novo
  });
  (masks || []).forEach((m) => { const c = FC.cuts[m.k]; if (c) c.mask = unmask(m.mascara, m.n); });
  FC.result = null;
  $('#fc-report').innerHTML = '';
  renderList(); draw(); requestMaskDraw();
}

window.flexiFree = { FC, forExport, state, restore, close, hiddenCuts, hiddenBody: () => !!FC.corpoOculto, renderList, count: () => FC.cuts.filter((c) => c.linhas.length || (c.mask && marked(c))).length,
  newCut, startMark, finishMark, setTool, runPreview, applyResult, bucketAt, brushAt, closeLine, masksOut, remap, exportBefore, addPieceCut, changed, draw,
  surface: () => SF };
renderList();
