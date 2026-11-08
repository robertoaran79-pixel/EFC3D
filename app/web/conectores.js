// EFC3D: conectores manuais (1.46).
// Módulo à parte do motor de corte. Um corte com o encaixe "Conector manual" sai só com as faces (navalha);
// depois da prévia, cada junta desse corte aparece aqui com um conector sugerido, que o usuário muda:
// tipo (pino com lado plano, pino redondo, cavilha, ímã ou nenhum), lugar na face (clique), giro, diâmetro,
// profundidade, folga e lado. A conferência responde a cada mudança; "Aplicar nas peças" refaz só os
// pinos e furos (os cortes ficam guardados no servidor).
const F = window.flexi;
const { THREE, host, camera, controls, post, setStatus, nf, CSS2DObject } = F;
const $ = (s) => document.querySelector(s);

const TIPOS = {
  pino: 'Pino com lado plano (não gira)',
  redondo: 'Pino redondo (a peça gira)',
  cavilha: 'Cavilha solta (furo nos dois lados)',
  ima: 'Furo para ímã (nos dois lados)',
  nenhum: 'Sem conector (só colar)',
};
const ICONE = { ok: '✓', aviso: '⚠', erro: '✕' };
const COR = { ok: 0x2f8f3f, aviso: 0xc9a227, erro: 0xc0392b };
const CN = { juntas: [], list: [], sel: -1, moving: -1, dirty: false, markers: [] };
const ray = new THREE.Raycaster();

function box() { return $('#cn-box'); }
function temManual() {
  const free = window.flexiFree;
  return !!(free && free.FC.cuts.some((c) => c.encaixe === 'manual' && (c.linhas.length || c.mask)));
}
function junta(id) { return CN.juntas.find((j) => j.id === id); }
function limpo(c) {
  const o = {};
  ['junta', 'tipo', 'd', 'h', 'h2', 'giro', 'lado', 'ponto', 'folga', 'eixo'].forEach((k) => { if (c[k] !== undefined) o[k] = c[k]; });
  return o;
}
function forExport() { return temManual() ? CN.list.map(limpo) : []; }
function state() { return CN.list.map(limpo); }
function restore(list) {
  CN.list = Array.isArray(list) ? list.map((c) => Object.assign({}, c)) : [];
  CN.juntas = []; CN.sel = -1; CN.dirty = false;
  clearMarkers(); render();
}

// ---------------------------------------------------------------- depois da prévia
async function afterPreview(r) {
  if (!temManual() || !r) { CN.juntas = []; clearMarkers(); render(); return; }
  try {
    const q = await post('/api/conectores/juntas', {});
    CN.juntas = q.juntas || [];
  } catch (e) { CN.juntas = []; setStatus('Conectores: ' + e.message); render(); return; }
  const ids = new Set(CN.juntas.map((j) => j.id));
  const antes = CN.list.length;
  CN.list = CN.list.filter((c) => ids.has(c.junta));
  const sumiu = antes - CN.list.length;
  let novos = 0;
  CN.juntas.forEach((j) => {
    if (!CN.list.some((c) => c.junta === j.id)) { CN.list.push(Object.assign({}, j.sugestao)); novos++; }
  });
  // o resultado da prévia já traz a conferência dos conectores aplicados (na mesma ordem)
  if (r.conectores && r.conectores.length === CN.list.length && !novos && !sumiu) {
    r.conectores.forEach((x, i) => { CN.list[i].luz = x.luz; CN.list[i].checks = x.checks; CN.list[i].ponto = x.ponto; });
    CN.dirty = false;
  } else {
    CN.dirty = CN.list.length > 0;
    await conferir();
  }
  if (sumiu) setStatus(`${sumiu} conector(es) saíram: a junta deles não existe mais (o corte mudou).`);
  else if (novos) setStatus(`${novos} conector(es) sugerido(s) nas juntas dos cortes manuais: ajuste e clique em "Aplicar nas peças".`);
  render();
}

let timer = null;
function mudou() {
  CN.dirty = true;
  render();
  clearTimeout(timer);
  timer = setTimeout(conferir, 250);
}
async function conferir() {
  if (!CN.list.length) { drawMarkers(); return; }
  try {
    const q = await post('/api/conectores/conferir', { conectores: CN.list.map(limpo) });
    (q.conectores || []).forEach((x, i) => { if (CN.list[i]) { CN.list[i].luz = x.luz; CN.list[i].checks = x.checks; CN.list[i].ponto = x.ponto; } });
  } catch (e) { setStatus('Conferência dos conectores: ' + e.message); }
  render();
}
async function aplicar() {
  const P = window.flexiPecas;
  if (!P) return;
  await P.run();                    // os cortes vêm do que está guardado; só os conectores são refeitos
}

// ---------------------------------------------------------------- painel
function nomeDono(c, j) { return c.lado === 'vizinha' ? j.vizinha : j.peca; }
function nomeOutro(c, j) { return c.lado === 'vizinha' ? j.peca : j.vizinha; }
function num(k, label, v, min, max, step) {
  return `<label>${label}<input type="number" data-k="${k}" min="${min}" max="${max}" step="${step}" value="${v}"></label>`;
}
function render() {
  const el = box();
  if (!el) return;
  if (!temManual() || !CN.juntas.length) {
    el.innerHTML = temManual() ? '<div class="card"><div class="lbl3">Conectores manuais</div><p class="hint">Clique em "Prévia das peças": as juntas dos cortes com conector manual aparecem aqui, cada uma com um conector sugerido.</p></div>' : '';
    clearMarkers();
    return;
  }
  const cards = CN.list.map((c, i) => {
    const j = junta(c.junta);
    if (!j) return '';
    const sel = i === CN.sel;
    const furo = c.tipo === 'cavilha' || c.tipo === 'ima';
    const luz = c.luz || 'nada';
    const head = `<b>C${i + 1}</b> ${j.peca} ↔ ${j.vizinha} · ${TIPOS[c.tipo] ? TIPOS[c.tipo].split(' (')[0] : c.tipo}`;
    const checks = (c.checks || []).map((x) => `<li class="${x.nivel}">${ICONE[x.nivel] || ''} ${x.texto}</li>`).join('');
    if (!sel) {
      return `<li class="cn-item" data-i="${i}"><button class="btn wide cn-sel" data-i="${i}">${ICONE[luz] || '·'} ${head}</button></li>`;
    }
    return `<li class="cn-item on" data-i="${i}"><div class="card">
      <div class="lbl3">${ICONE[luz] || '·'} ${head}</div>
      <label>Tipo<select data-k="tipo">${Object.entries(TIPOS).map(([k, t]) => `<option value="${k}" ${c.tipo === k ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
      ${c.tipo === 'nenhum' ? '' : `<label>Eixo<select data-k="eixo"><option value="face" ${c.eixo !== 'vertical' ? 'selected' : ''}>Perpendicular à face</option><option value="vertical" ${c.eixo === 'vertical' ? 'selected' : ''}>Vertical da mesa (imprime de pé)</option></select></label>`}
      ${c.tipo === 'nenhum' ? '' : `<div class="grid2">
        ${num('d', c.tipo === 'ima' ? 'Diâmetro do ímã (mm)' : 'Diâmetro (mm)', c.d, 1, 30, 0.5)}
        ${num('h', c.tipo === 'ima' ? `Espessura do ímã em "${nomeOutro(c, j)}" (mm)` : `Profundidade em "${nomeOutro(c, j)}" (mm)`, c.h, 0.5, 40, 0.5)}
        ${furo ? num('h2', c.tipo === 'ima' ? `Espessura do ímã em "${nomeDono(c, j)}" (mm)` : `Profundidade em "${nomeDono(c, j)}" (mm)`, c.h2, 0.5, 40, 0.5) : ''}
        ${c.tipo === 'pino' ? num('giro', 'Giro do lado plano (°)', c.giro || 0, -180, 180, 15) : ''}
        ${num('folga', 'Folga (mm)', c.folga, 0, 1.5, 0.05)}
      </div>`}
      <p class="hint">${c.tipo === 'nenhum' ? '' : furo ? `Furo em "${nomeDono(c, j)}" e em "${nomeOutro(c, j)}".` : `O pino sai de "${nomeDono(c, j)}" e entra em "${nomeOutro(c, j)}".`}
        Face da junta: ${nf(j.area, 0)} mm², até ${nf(j.raio_livre, 1)} mm do ponto mais livre até a pele.</p>
      <div class="row">
        <button class="btn${CN.moving === i ? ' primary' : ''}" data-act="mover">⌖ ${CN.moving === i ? 'Clique na face… (Esc)' : 'Mover o conector'}</button>
        ${c.tipo !== 'nenhum' ? '<button class="btn" data-act="lado">⇄ Trocar o lado</button>' : ''}
        <button class="btn" data-act="sugestao">↺ Sugestão</button>
      </div>
      <div class="row">
        <button class="btn" data-act="mais">＋ Outro conector nesta junta</button>
        ${CN.list.filter((x) => x.junta === c.junta).length > 1 ? '<button class="btn" data-act="tirar">✕ Remover</button>' : ''}
      </div>
      ${checks ? `<ul class="checks">${checks}</ul>` : ''}
    </div></li>`;
  }).join('');
  const nErr = CN.list.filter((c) => c.luz === 'erro').length;
  el.innerHTML = `<div class="card cn">
    <div class="lbl3">Conectores manuais</div>
    <p class="hint">Escolha um conector para editar. Para mover, clique em ⌖ Mover o conector e depois na face da junta (use "Afastar" no topo para ver as faces). Um conector com ✕ não entra nas peças.</p>
    <ol class="cn-list">${cards}</ol>
    <div class="row"><button class="btn ${CN.dirty ? 'primary' : ''}" data-act="aplicar">${CN.dirty ? '✓ Aplicar nas peças' : '✓ Aplicado nas peças'}</button></div>
    ${nErr ? `<p class="hint">✕ ${nErr} conector(es) com erro ficam de fora até serem corrigidos.</p>` : ''}
  </div>`;
  el.querySelectorAll('.cn-sel').forEach((b) => { b.onclick = () => { CN.sel = +b.dataset.i; render(); }; });
  const c = CN.list[CN.sel];
  el.querySelector('[data-act="aplicar"]').onclick = aplicar;
  if (c) {
    const card = el.querySelector('.cn-item.on');
    card.querySelectorAll('[data-k]').forEach((inp) => {
      inp.onchange = () => {
        const k = inp.dataset.k;
        c[k] = inp.tagName === 'SELECT' ? inp.value : (parseFloat(inp.value) || 0);
        mudou();
      };
    });
    card.querySelector('[data-act="mover"]').onclick = () => startMove(CN.sel);
    const lado = card.querySelector('[data-act="lado"]');
    if (lado) lado.onclick = () => { c.lado = c.lado === 'vizinha' ? 'peca' : 'vizinha'; mudou(); };
    card.querySelector('[data-act="sugestao"]').onclick = () => { const j = junta(c.junta); if (j) { Object.assign(c, j.sugestao); mudou(); } };
    card.querySelector('[data-act="mais"]').onclick = () => {
      const j = junta(c.junta);
      CN.list.splice(CN.sel + 1, 0, Object.assign({}, c, { ponto: j ? j.centro.slice() : c.ponto }));
      CN.sel += 1;
      mudou();
      setStatus('Conector novo na mesma junta: clique em ⌖ Mover o conector e na face para colocá-lo no lugar.');
    };
    const tirar = card.querySelector('[data-act="tirar"]');
    if (tirar) tirar.onclick = () => { CN.list.splice(CN.sel, 1); CN.sel = -1; mudou(); };
  }
  drawMarkers();
}

// ---------------------------------------------------------------- marcadores na prévia
function clearMarkers() {
  CN.markers.forEach((m) => {
    if (m.parent) m.parent.remove(m);
    m.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.element) o.element.remove(); });
  });
  CN.markers = [];
}
function drawMarkers() {
  clearMarkers();
  const P = window.flexiPecas;
  if (!P || !P.PC.parts.length || !P.PC.result) return;
  const partes = P.PC.result.partes || [];
  CN.list.forEach((c, i) => {
    const j = junta(c.junta);
    if (!j || c.tipo === 'nenhum') return;
    const dono = nomeDono(c, j);
    const k = partes.findIndex((p) => p.nome === dono);
    const mesh = P.PC.parts[k];
    if (!mesh) return;
    const n = new THREE.Vector3(...j.normal);
    if (c.lado === 'vizinha') n.negate();
    if (c.eixo === 'vertical' && Math.abs(n.z) > 0.2) n.set(0, 0, Math.sign(n.z));
    const h = Math.max(0.5, +c.h || 1);
    const g = new THREE.CylinderGeometry((+c.d || 2) / 2, (+c.d || 2) / 2, h, 32);
    g.rotateX(Math.PI / 2);                               // o eixo do cilindro em Z
    g.translate(0, 0, h / 2);
    const mat = new THREE.MeshBasicMaterial({ color: COR[c.luz] || 0x2b6fd9, transparent: true, opacity: i === CN.sel ? 0.75 : 0.45, depthTest: false });
    const m = new THREE.Mesh(g, mat);
    m.renderOrder = 10;
    m.position.set(...c.ponto);
    m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), n);
    m.raycast = () => {};
    const div = document.createElement('div');
    div.className = 'fc-lbl' + (i === CN.sel ? ' on' : '');
    div.textContent = `C${i + 1} ${ICONE[c.luz] || ''}`;
    const lab = new CSS2DObject(div);
    lab.position.set(0, 0, h + 1);
    m.add(lab);
    mesh.add(m);
    CN.markers.push(m);
  });
}

// ---------------------------------------------------------------- mover: clique na face
function mouse(on) {
  controls.mouseButtons.LEFT = on ? -1 : THREE.MOUSE.ROTATE;
  controls.mouseButtons.RIGHT = on ? THREE.MOUSE.ROTATE : THREE.MOUSE.PAN;
  controls.state = -1;
  if (Array.isArray(controls._pointers)) controls._pointers.length = 0;
}
function startMove(i) {
  const P = window.flexiPecas;
  if (!P || !P.PC.parts.length) { setStatus('Faça a prévia das peças primeiro.'); return; }
  if (!P.active()) P.show(true);
  CN.moving = i;
  mouse(true);
  render();
  setStatus('Clique na face da junta onde o conector deve ficar (use "Afastar" no topo para ver as faces). Botão direito gira; Esc cancela.');
}
function stopMove(msg) {
  if (CN.moving < 0) return;
  CN.moving = -1;
  F.renderer.domElement.style.cursor = '';
  mouse(false);
  render();
  if (msg) setStatus(msg);
}
let down = null;
host.addEventListener('pointerdown', (e) => { if (CN.moving >= 0 && e.button === 0) down = [e.clientX, e.clientY]; }, true);
host.addEventListener('pointerup', (e) => {
  if (CN.moving < 0 || e.button !== 0 || !down) return;
  const [x, y] = down;
  down = null;
  if (Math.hypot(e.clientX - x, e.clientY - y) > 4) return;
  e.stopPropagation();
  if (Array.isArray(controls._pointers) && controls._pointers.includes(e.pointerId) && controls._onPointerUp) controls._onPointerUp(e);
  const P = window.flexiPecas;
  ray.setFromCamera(F.ndc(e), camera);
  const hit = ray.intersectObjects(P.PC.parts.filter((m) => m.visible), false)[0];
  if (!hit) { setStatus('Clique sobre a face da junta (Esc cancela).'); return; }
  const p = hit.point.clone().sub(hit.object.position);
  const c = CN.list[CN.moving];
  const j = c && junta(c.junta);
  if (!c || !j) { stopMove(); return; }
  const antes = c.ponto;
  c.ponto = [p.x, p.y, p.z].map((v) => +v.toFixed(3));
  stopMove();
  mudou();
  conferir().then(() => {
    const q = c.ponto, d = Math.hypot(q[0] - p.x, q[1] - p.y, q[2] - p.z);
    if (d > 3) setStatus(`O clique ficou a ${nf(d, 1)} mm da face desta junta: o conector foi para o ponto da face mais perto. Se não era aí, clique em ⌖ Mover o conector de novo.`);
    else setStatus('Conector no lugar. Clique em "Aplicar nas peças" para ver o resultado.');
    if (!antes) render();
  });
}, true);
host.addEventListener('click', (e) => { if (CN.moving >= 0) e.stopPropagation(); }, true);
window.addEventListener('keydown', (e) => {
  if (CN.moving < 0 || e.key !== 'Escape') return;
  stopMove('Mover cancelado.');
}, true);

window.flexiConectores = { CN, afterPreview, forExport, state, restore, render, clearMarkers };
render();
