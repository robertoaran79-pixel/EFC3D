// EFC3D: a superfície em que a marcação do Corte livre trabalha (1.38).
// A marcação (Linha, Pincel, Balde, Borracha) só fala com a superfície por esta interface. Há dois tipos:
//   baseSurface(): o modelo inteiro. Usa as funções do app (as mesmas de sempre, sem nenhuma mudança).
//   meshSurface(mesh): a malha de uma peça já recortada. Os mesmos dados e os mesmos algoritmos do
//     app, calculados para essa malha (triângulos, vizinhança, grafo de vértices, caminho pela superfície).
// Assim as ferramentas são as mesmas em qualquer superfície, sem código repetido na marcação.
const F = window.flexi;
const { THREE, S, camera, renderer } = F;

export function baseSurface() {
  return {
    kind: 'base',
    mesh: () => S.base,
    tri: () => F.tri(),
    adjacency: () => F.adjacency(),
    vid: () => S.vid,
    nv: () => S.nv,
    ensureVGraph: () => F.ensureVGraph(),
    hit: (e) => F.hitBase(e),
    nearestCorner: (h) => F.nearestCorner(h),
    screenOf: (v) => F.screenOf(v),
    surfacePath: (a, b, avoid) => F.surfacePath(a, b, avoid),
    closingPath: (path, a, b) => F.closingPath(path, a, b),
  };
}

// Malha não indexada (cada triângulo com seus 3 vértices), como o modelo do app.
export function meshSurface(mesh) {
  const pos = () => mesh.geometry.attributes.position.array;
  let tri = null, adj = null, vid = null, nv = 0, vgraph = null;
  const ray = new THREE.Raycaster();

  function triData() {                                   // = baseTriData do app (sem o efeito na pintura)
    if (tri) return tri;
    const p = pos(), n = p.length / 9;
    const cen = new Float32Array(n * 3), nrm = new Float32Array(n * 3);
    for (let t = 0; t < n; t++) {
      const o = t * 9;
      const ax = p[o], ay = p[o + 1], az = p[o + 2], bx = p[o + 3], by = p[o + 4], bz = p[o + 5], cx = p[o + 6], cy = p[o + 7], cz = p[o + 8];
      cen[t * 3] = (ax + bx + cx) / 3; cen[t * 3 + 1] = (ay + by + cy) / 3; cen[t * 3 + 2] = (az + bz + cz) / 3;
      const ux = bx - ax, uy = by - ay, uz = bz - az, vx = cx - ax, vy = cy - ay, vz = cz - az;
      let nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
      const l = Math.hypot(nx, ny, nz) || 1;
      nrm[t * 3] = nx / l; nrm[t * 3 + 1] = ny / l; nrm[t * 3 + 2] = nz / l;
    }
    tri = { n, cen, nrm };
    return tri;
  }
  function adjacency() {                                 // = buildAdjacency do app
    if (adj) return adj;
    const p = pos(), n = triData().n;
    const map = new Map(); let k = 0;
    vid = new Int32Array(n * 3);
    for (let i = 0; i < n * 3; i++) {
      const key = `${Math.round(p[i * 3] * 1e4)},${Math.round(p[i * 3 + 1] * 1e4)},${Math.round(p[i * 3 + 2] * 1e4)}`;
      let v = map.get(key);
      if (v === undefined) { v = k++; map.set(key, v); }
      vid[i] = v;
    }
    nv = k;
    const edge = new Map(), nbE = new Int32Array(n * 3).fill(-1);
    for (let t = 0; t < n; t++) {
      for (let j = 0; j < 3; j++) {
        const a = vid[t * 3 + j], b = vid[t * 3 + (j + 1) % 3];
        const key = a < b ? a * 4194304 + b : b * 4194304 + a;
        const o = edge.get(key);
        if (o === undefined) edge.set(key, t * 3 + j);
        else { nbE[t * 3 + j] = (o / 3) | 0; nbE[o] = t; edge.delete(key); }
      }
    }
    adj = nbE;
    return adj;
  }
  function ensureVGraph() {                              // = ensureVGraph do app
    if (vgraph) return vgraph;
    adjacency();
    const p = pos(), T = triData(), n = T.n;
    const vp = new Float32Array(nv * 3), vn = new Float32Array(nv * 3), deg = new Int32Array(nv + 1);
    for (let c = 0; c < n * 3; c++) {
      const v = vid[c], t = (c / 3) | 0;
      vp[v * 3] = p[c * 3]; vp[v * 3 + 1] = p[c * 3 + 1]; vp[v * 3 + 2] = p[c * 3 + 2];
      vn[v * 3] += T.nrm[t * 3]; vn[v * 3 + 1] += T.nrm[t * 3 + 1]; vn[v * 3 + 2] += T.nrm[t * 3 + 2];
    }
    for (let t = 0; t < n; t++) for (let j = 0; j < 3; j++) { deg[vid[t * 3 + j]]++; deg[vid[t * 3 + (j + 1) % 3]]++; }
    const start = new Int32Array(nv + 1);
    for (let i = 0; i < nv; i++) start[i + 1] = start[i] + deg[i];
    const fp = start.slice(0, nv), nbr = new Int32Array(start[nv]);
    for (let t = 0; t < n; t++) for (let j = 0; j < 3; j++) {
      const a = vid[t * 3 + j], b = vid[t * 3 + (j + 1) % 3];
      nbr[fp[a]++] = b; nbr[fp[b]++] = a;
    }
    for (let v = 0; v < nv; v++) { const l = Math.hypot(vn[v * 3], vn[v * 3 + 1], vn[v * 3 + 2]) || 1; vn[v * 3] /= l; vn[v * 3 + 1] /= l; vn[v * 3 + 2] /= l; }
    vgraph = { vp, vn, start, nbr, nv };
    return vgraph;
  }
  function surfacePath(a, b, avoid) {                    // = surfacePath do app (A* pelas arestas)
    const { vp, start, nbr } = ensureVGraph();
    const g = new Float64Array(nv).fill(Infinity), prev = new Int32Array(nv).fill(-1), done = new Uint8Array(nv);
    const H = (v) => Math.hypot(vp[v * 3] - vp[b * 3], vp[v * 3 + 1] - vp[b * 3 + 1], vp[v * 3 + 2] - vp[b * 3 + 2]);
    const heap = [[H(a), a]];
    const push = (it) => { heap.push(it); let i = heap.length - 1; while (i > 0) { const q = (i - 1) >> 1; if (heap[q][0] <= heap[i][0]) break; [heap[q], heap[i]] = [heap[i], heap[q]]; i = q; } };
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
  function closingPath(path, a, b) {                     // = closingPath do app
    const { vp } = ensureVGraph();
    const drawn = [].concat(...path);
    if (drawn.length < 3) return surfacePath(a, b);
    const dab = Math.hypot(vp[a * 3] - vp[b * 3], vp[a * 3 + 1] - vp[b * 3 + 1], vp[a * 3 + 2] - vp[b * 3 + 2]);
    const r = Math.min(8, Math.max(1.5, 0.4 * dab, F.penWidth() * 4)), r2 = r * r, cell = r, H = new Map();
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
  function nearestCorner(h) {                            // = nearestCorner do app
    adjacency();
    const t = h.faceIndex, { vp } = ensureVGraph();
    let best = vid[t * 3], bd = Infinity;
    for (let k = 0; k < 3; k++) {
      const v = vid[t * 3 + k];
      const d = Math.hypot(vp[v * 3] - h.point.x, vp[v * 3 + 1] - h.point.y, vp[v * 3 + 2] - h.point.z);
      if (d < bd) { bd = d; best = v; }
    }
    return best;
  }
  function screenOf(v) {                                 // = screenOf do app
    const { vp } = ensureVGraph();
    const q = new THREE.Vector3(vp[v * 3], vp[v * 3 + 1], vp[v * 3 + 2]).project(camera);
    const r = renderer.domElement.getBoundingClientRect();
    return [r.left + (q.x + 1) / 2 * r.width, r.top + (1 - q.y) / 2 * r.height];
  }
  return {
    kind: 'peca',
    mesh: () => mesh,
    tri: triData,
    adjacency,
    vid: () => { adjacency(); return vid; },
    nv: () => { adjacency(); return nv; },
    ensureVGraph,
    hit: (e) => { ray.setFromCamera(F.ndc(e), camera); return ray.intersectObject(mesh, false)[0] || null; },
    nearestCorner,
    screenOf,
    surfacePath,
    closingPath,
  };
}
