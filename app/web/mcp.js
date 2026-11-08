// EFC3D: controle pelo Claude (MCP), lado da janela.
// Com o controle ligado (🤖 Claude, no topo), a janela busca comandos no servidor do app e
// executa: estado, captura da vista 3D, câmera, cliques e teclas na vista, botões da barra
// lateral, prévia das peças e JavaScript. Desligado, nada é executado.
const F = window.flexi;
const { THREE, S, camera, controls, renderer, host, api, post, setStatus } = F;
const $ = (s) => document.querySelector(s);

const MC = { ativo: false, registrado: false, arquivo: '', loop: false, ultimo: '' };

// ---------------------------------------------------------------- interface (botão no topo)
const btn = $('#btn-mcp');
const pop = document.createElement('div');
pop.id = 'mcp-pop';
pop.className = 'mcp-pop hidden';
pop.innerHTML = `
  <div class="lbl3">Controle pelo Claude (MCP)</div>
  <label class="chk"><input type="checkbox" id="mcp-on"> Permitir que o Claude controle o app</label>
  <p class="hint" id="mcp-info"></p>
  <div class="row"><button class="btn" id="mcp-reg">Registrar no Claude Desktop</button><button class="btn" id="mcp-close">Fechar</button></div>
  <p class="hint">Ligado, o Claude pode ver a vista 3D, mexer na câmera, clicar, digitar atalhos, apertar botões e rodar a prévia, como você faria. Desligue quando não quiser.</p>`;
document.body.appendChild(pop);
function place() {
  const r = btn.getBoundingClientRect();
  pop.style.left = Math.max(8, Math.min(r.left, innerWidth - 336)) + 'px';   // o botão fica no canto direito do topo
  pop.style.top = (r.bottom + 6) + 'px';
}
function render() {
  $('#mcp-on').checked = MC.ativo;
  btn.classList.toggle('on', MC.ativo);
  btn.textContent = MC.ativo ? '🤖 ●' : '🤖';
  btn.title = MC.ativo ? 'Controle pelo Claude: LIGADO' : 'Controle pelo Claude: desligado';
  $('#mcp-info').innerHTML = (MC.ativo ? '● <b>Ligado.</b> ' : '○ <b>Desligado.</b> ') +
    (MC.registrado ? 'Já registrado no Claude Desktop.' : 'Ainda não registrado no Claude Desktop: clique em Registrar e reinicie o Claude Desktop.') +
    (MC.ultimo ? `<br>Último comando: ${MC.ultimo}` : '');
}
async function load() {
  try {
    const r = await api('/api/mcp/config');
    MC.ativo = !!r.ativo; MC.registrado = !!r.registrado; MC.arquivo = r.arquivo_claude || '';
  } catch (e) { /* servidor antigo */ }
  render();
  if (MC.ativo) startLoop();
}
btn.onclick = () => { pop.classList.toggle('hidden'); place(); render(); };
$('#mcp-close').onclick = () => pop.classList.add('hidden');
$('#mcp-on').onchange = async () => {
  MC.ativo = $('#mcp-on').checked;
  await post('/api/mcp/config', { ativo: MC.ativo });
  render();
  setStatus(MC.ativo ? 'Controle pelo Claude ligado.' : 'Controle pelo Claude desligado.');
  if (MC.ativo) startLoop();
};
$('#mcp-reg').onclick = async () => {
  const r = await post('/api/mcp/registrar', {});
  if (r.ok) {
    MC.registrado = true;
    setStatus('Registrado no Claude Desktop (' + r.arquivo + '). Feche e abra o Claude Desktop para ele carregar o EFC3D.');
  } else setStatus('Não registrei: ' + (r.msg || 'erro'));
  render();
};

// ---------------------------------------------------------------- utilidades
const frame = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function rect() { return renderer.domElement.getBoundingClientRect(); }
function client(x, y) { const r = rect(); return [r.left + x, r.top + y]; }
function ptr(type, x, y, o = {}) {
  const [cx, cy] = client(x, y);
  const el = document.elementFromPoint(cx, cy) || renderer.domElement;
  const ev = new PointerEvent(type, { bubbles: true, cancelable: true, composed: true, clientX: cx, clientY: cy, pointerId: 1, pointerType: 'mouse', isPrimary: true,
    button: o.botao === 'direito' ? 2 : 0, buttons: type === 'pointerup' ? 0 : (o.botao === 'direito' ? 2 : 1), shiftKey: !!o.shift, altKey: !!o.alt, metaKey: !!o.meta, ctrlKey: !!o.ctrl });
  el.dispatchEvent(ev);
  return el;
}
function move(x, y, o = {}) {
  const [cx, cy] = client(x, y);
  const el = document.elementFromPoint(cx, cy) || renderer.domElement;
  el.dispatchEvent(new PointerEvent('pointermove', { bubbles: true, cancelable: true, clientX: cx, clientY: cy, pointerId: 1, pointerType: 'mouse', isPrimary: true,
    buttons: o.pressed ? (o.botao === 'direito' ? 2 : 1) : 0, shiftKey: !!o.shift }));
}
function key(k, o = {}) {
  const code = k === ' ' ? 'Space' : k.length === 1 ? (/[a-z]/i.test(k) ? 'Key' + k.toUpperCase() : /[0-9]/.test(k) ? 'Digit' + k : '') : k;
  const init = { key: k, code, bubbles: true, cancelable: true, metaKey: !!o.meta, ctrlKey: !!o.ctrl, shiftKey: !!o.shift, altKey: !!o.alt };
  (document.activeElement || window).dispatchEvent(new KeyboardEvent('keydown', init));
  (document.activeElement || window).dispatchEvent(new KeyboardEvent('keyup', init));
}
function visText(el) { return (el.innerText || '').replace(/\n{3,}/g, '\n\n').trim(); }
function shortChecks(list) { return (list || []).map((c) => `${c.nivel}: ${c.texto}`); }

function estado() {
  const FC = window.flexiFree && window.flexiFree.FC;
  const PC = window.flexiPecas && window.flexiPecas.PC;
  const box = S.baseBox ? S.baseBox.getSize(new THREE.Vector3()) : null;
  const r = rect();
  return {
    versao: ($('#versao') || {}).textContent || '',
    modelo: S.base ? { nome: ($('#drop-text') || {}).textContent || '', triangulos: F.tri() ? F.tri().n : null, tamanho_mm: box ? [box.x, box.y, box.z].map((v) => +v.toFixed(1)) : null } : null,
    modo: S.painting ? 'pintura' : (FC && FC.marking) ? 'marcacao_corte_livre' : (window.flexiSplit && window.flexiSplit.SP.on) ? 'separar_por_cor' : 'normal',
    ferramenta: S.painting ? S.tool : (FC && FC.marking) ? FC.tool : null,
    vista: S.showPieces ? 'exportado' : (PC && PC.on) ? 'previa' : 'modelo',
    juntas: S.joints.map((j, i) => ({ i, nome: j.nome || `J${i + 1}`, luz: j.luz || 'nada' })),
    cortes_livres: FC ? FC.cuts.map((c, k) => ({ k, nome: c.nome, linhas: c.linhas.length, pontos_em_andamento: k === FC.cur ? FC.pts.length : 0,
      triangulos_marcados: c.mask ? c.mask.reduce((a, b) => a + b, 0) : 0, encaixe: c.encaixe, luz: c.luz, verificacao: shortChecks(c.checks) })) : [],
    previa: PC && PC.result ? { partes: PC.result.partes.map((p) => ({ nome: p.nome, tipo: p.tipo, tamanho: p.tamanho })) } : null,
    status: visText($('#status') || document.body).slice(0, 400),
    vista_3d_px: [Math.round(r.width), Math.round(r.height)],
  };
}
async function captura(a) {
  await frame();
  renderer.render(F.scene, camera);
  const src = renderer.domElement;
  const r = rect();
  const maxW = Math.max(200, Math.min(2000, +a.largura || 1100));
  const w = Math.min(maxW, Math.round(r.width));
  const h = Math.round(w * r.height / r.width);
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const g = c.getContext('2d');
  g.drawImage(src, 0, 0, w, h);
  // rótulos (CSS2D) por cima, para o Claude ver C1, Corpo etc.
  g.font = '12px sans-serif';
  document.querySelectorAll('.fc-lbl, .lbl').forEach((el) => {
    const b = el.getBoundingClientRect();
    if (!b.width || el.style.display === 'none' || b.right < r.left || b.left > r.right || b.bottom < r.top || b.top > r.bottom) return;
    const x = (b.left - r.left) * w / r.width, y = (b.top - r.top) * h / r.height;
    g.fillStyle = 'rgba(217,98,43,0.9)'; g.fillRect(x, y, g.measureText(el.textContent).width + 8, 16);
    g.fillStyle = '#fff'; g.fillText(el.textContent, x + 4, y + 12);
  });
  const url = c.toDataURL('image/jpeg', 0.85);
  return { imagem: url.split(',')[1], mime: 'image/jpeg', largura: w, altura: h, escala_px: +(r.width / w).toFixed(4),
    obs: 'Para clicar, use x e y em pixels desta imagem multiplicados por escala_px.' };
}
function cameraCmd(a) {
  const t = a.alvo ? new THREE.Vector3(...a.alvo) : controls.target.clone();
  const named = { frente: [0, 0], tras: [180, 0], direita: [90, 0], esquerda: [-90, 0], topo: [0, 89.9], baixo: [0, -89.9], '3d': [-30, 25] };
  let az = a.azimute, el = a.elevacao;
  if (a.vista && named[a.vista]) [az, el] = named[a.vista];
  const cur = camera.position.clone().sub(controls.target);
  let dist = cur.length();
  if (az === undefined || el === undefined) {
    const sph = new THREE.Spherical().setFromVector3(new THREE.Vector3(cur.x, cur.z, -cur.y));
    if (az === undefined) az = THREE.MathUtils.radToDeg(Math.atan2(cur.x, -cur.y));
    if (el === undefined) el = THREE.MathUtils.radToDeg(Math.asin(cur.z / Math.max(dist, 1e-9)));
    void sph;
  }
  if (a.distancia) dist = +a.distancia;
  if (a.zoom) dist /= +a.zoom;
  const A = THREE.MathUtils.degToRad(+az), E = THREE.MathUtils.degToRad(+el);
  const dir = new THREE.Vector3(Math.cos(E) * Math.sin(A), -Math.cos(E) * Math.cos(A), Math.sin(E));
  controls.target.copy(t);
  camera.up.set(0, 0, 1);
  camera.position.copy(t).addScaledVector(dir, dist);
  camera.lookAt(t);
  controls.update();
  return { azimute: +(+az).toFixed(1), elevacao: +(+el).toFixed(1), distancia: +dist.toFixed(1), alvo: t.toArray().map((v) => +v.toFixed(2)) };
}
function ponto3d(a) {
  const [cx, cy] = client(+a.x, +a.y);
  const h = F.hitBase({ clientX: cx, clientY: cy });
  if (!h) return { ponto: null };
  const n = h.face.normal.clone().transformDirection(S.base.matrixWorld);
  return { ponto: h.point.toArray().map((v) => +v.toFixed(3)), triangulo: h.faceIndex, normal: n.toArray().map((v) => +v.toFixed(3)) };
}
function tela(a) {
  const r = rect();
  return (a.pontos || []).map((p) => {
    const v = new THREE.Vector3(...p).project(camera);
    return [+(((v.x + 1) / 2) * r.width).toFixed(1), +(((1 - v.y) / 2) * r.height).toFixed(1), v.z < 1];
  });
}
function findEl(a) {
  const sh = window.flexiShell;
  if (a.seletor) { const el = document.querySelector(a.seletor); if (el && sh) sh.reveal(el, false); return el; }
  const t = (a.texto || '').toLowerCase();
  const all = [...document.querySelectorAll('button, a, label, [role="button"], li.item, summary')];
  const vis = all.find((e) => e.offsetParent !== null && visText(e).toLowerCase() === t) ||
    all.find((e) => e.offsetParent !== null && visText(e).toLowerCase().includes(t));
  if (vis) return vis;
  // controle de outra aba: abre a aba dele (os painéis das outras etapas ficam escondidos)
  const hid = all.find((e) => e.closest('#side section[data-tab]') && (e.textContent || '').trim().toLowerCase() === t) ||
    all.find((e) => e.closest('#side section[data-tab]') && (e.textContent || '').toLowerCase().includes(t));
  if (hid && sh) sh.reveal(hid, false);
  return hid && hid.offsetParent !== null ? hid : null;
}
function lerTela() {
  const side = $('#side');
  const btns = [...document.querySelectorAll('button')].filter((b) => b.offsetParent !== null && !b.disabled)
    .map((b) => (b.id ? '#' + b.id + ' ' : '') + visText(b).replace(/\s+/g, ' ').slice(0, 40)).slice(0, 150);
  return { status: visText($('#status') || document.body).slice(0, 400), aba: window.flexiShell ? window.flexiShell.tab() : '', faixa: visText($('#ribbon') || document.body).slice(0, 600), navegador: visText($('#browser') || document.body).slice(0, 1500), barra_lateral: visText(side).slice(0, 9000), botoes: btns };
}
async function previa() {
  if (!window.flexiPecas) return { erro: 'Prévia indisponível.' };
  await window.flexiPecas.run();
  const r = window.flexiPecas.PC.result;
  if (!r) return { erro: visText($('#status')) };
  return { status: visText($('#status')), partes: r.partes.map((p) => ({ nome: p.nome, tipo: p.tipo, tamanho_mm: p.tamanho })),
    pecas_por_cor: r.regioes.map((x) => ({ area: x.id + 1, luz: x.luz, verificacao: shortChecks(x.checks) })),
    cortes_livres: (r.livres || []).map((x) => ({ nome: x.nome, luz: x.luz, verificacao: shortChecks(x.checks) })) };
}

async function run(c) {
  const a = c.args || {};
  switch (c.tipo) {
    case 'estado': return estado();
    case 'captura': return captura(a);
    case 'camera': { const r = cameraCmd(a); await frame(); return r; }
    case 'abrir': { await F.openPath(a.caminho); await sleep(300); for (let i = 0; i < 600 && !(S.base && F.tri()); i++) await sleep(200); return estado(); }
    case 'clicar': {
      const o = { botao: a.botao, shift: a.shift, alt: a.alt, meta: a.meta, ctrl: a.ctrl };
      move(+a.x, +a.y);
      for (let n = 0; n < (a.duplo ? 2 : 1); n++) {
        const el = ptr('pointerdown', +a.x, +a.y, o); ptr('pointerup', +a.x, +a.y, o);
        if (!o.botao || o.botao === 'esquerdo') el.dispatchEvent(new MouseEvent('click', { bubbles: true, clientX: client(+a.x, +a.y)[0], clientY: client(+a.x, +a.y)[1], shiftKey: !!o.shift }));
        await frame();
      }
      await sleep(+a.espera || 150);
      return { status: visText($('#status')).slice(0, 300) };
    }
    case 'arrastar': {
      const [x0, y0] = a.de, [x1, y1] = a.para, n = Math.max(2, +a.passos || 12);
      const o = { botao: a.botao, shift: a.shift };
      move(x0, y0); ptr('pointerdown', x0, y0, o);
      for (let i = 1; i <= n; i++) { move(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n, Object.assign({ pressed: true }, o)); await frame(); }
      ptr('pointerup', x1, y1, o);
      await sleep(+a.espera || 200);
      return { status: visText($('#status')).slice(0, 300) };
    }
    case 'mover_mouse': { move(+a.x, +a.y, { shift: a.shift }); await sleep(+a.espera || 250); return { status: visText($('#status')).slice(0, 300) }; }
    case 'tecla': {
      if (document.activeElement && document.activeElement !== document.body && !a.manter_foco) document.activeElement.blur();
      for (let i = 0; i < Math.max(1, +a.vezes || 1); i++) { key(a.tecla, a); await frame(); }
      await sleep(+a.espera || 150);
      return { status: visText($('#status')).slice(0, 300) };
    }
    case 'clicar_botao': {
      const el = findEl(a);
      if (!el) return { erro: 'Não achei esse botão. Use ler_tela para ver os botões.' };
      el.scrollIntoView({ block: 'center' });
      el.click();
      await sleep(+a.espera || 300);
      return { clicado: visText(el).slice(0, 60), status: visText($('#status')).slice(0, 300) };
    }
    case 'preencher': {
      const el = a.seletor ? document.querySelector(a.seletor) : null;
      if (!el) return { erro: 'Campo não encontrado.' };
      if (el.type === 'checkbox') el.checked = !!a.valor; else el.value = a.valor;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      await sleep(200);
      return { ok: true, status: visText($('#status')).slice(0, 300) };
    }
    case 'ler_tela': return lerTela();
    case 'ponto_3d': return ponto3d(a);
    case 'tela_de_3d': return { pontos: tela(a) };
    case 'previa': return previa();
    case 'js': {
      const fn = new (Object.getPrototypeOf(async function () {}).constructor)('F', 'S', a.codigo || '');
      const v = await fn(F, S);
      try { return JSON.parse(JSON.stringify(v === undefined ? null : v)); } catch (e) { return String(v); }
    }
    default: return { erro: 'Comando desconhecido: ' + c.tipo };
  }
}

async function startLoop() {
  if (MC.loop) return;
  MC.loop = true;
  while (MC.ativo) {
    let c = null;
    try { c = await api('/api/mcp/poll'); } catch (e) { await sleep(3000); continue; }
    if (!c || !c.id) continue;
    MC.ultimo = c.tipo; render();
    let res;
    try { res = { ok: true, resultado: await run(c) }; } catch (e) { res = { ok: false, erro: String(e && e.message || e) }; }
    try { await post('/api/mcp/result', { id: c.id, resultado: res }); } catch (e) { /* segue */ }
  }
  MC.loop = false;
}
load();
window.flexiMCP = { MC, run };
