"""EFC3D: separate painted parts (module "Separar por cor").

New module, independent of the joints: it only reads the model and the painting, and writes
its own files. Nothing here changes the base model, the joints or the joint export.

Each painted area (a connected group of triangles of one colour) can become a separate part:

  tampao  the area is cut as a plug: a straight prism along the insertion direction, from the
          surface down to the chosen depth. The body gets the pocket, the plug is smaller by the
          clearance on the sides and the bottom. Straight walls mean the plug always goes in,
          and its flat bottom sits on the bed.
  membro  the area is cut off by planes: one plane per border of the painting (a sleeve has
          two). For arms, legs, tails.

Every cut can get a pin (optional): fixed on the body, fixed on the part, or a loose dowel.
Pins have a diamond section (45 degree faces): they print without support lying down or
standing, and do not turn.

The border of the cut is the painted border, projected and smoothed (a Gaussian along the
border): the cut is clean even when the painting follows jagged triangles. The mesh only
changes where it is cut: every other triangle stays identical (checked and reported).
"""
import io
import json
import math
import os
import time
import traceback
import zipfile

import numpy as np
import manifold3d as mf

import engine as E

DEFAULTS = dict(tipo='auto', espessura=0.0, profundidade=2.0, folga=0.3, suavizar=0.0, pino='nenhum', pino_mm=0.0,
                incl_a=0.0, incl_b=0.0, parede=1.2)
PINOS = ('nenhum', 'corpo', 'peca', 'cavilha', 'trava')
MIN_AREA = 0.8          # mm2: smaller painted specks are not offered as parts
S2 = math.sqrt(2.0)


# ----------------------------------------------------------------------------- mesh helpers
def tri_array(M):
    me = M.to_mesh()
    v = np.asarray(me.vert_properties)[:, :3].astype(np.float64)
    f = np.asarray(me.tri_verts).astype(np.int64)
    return v[f]


def _topology(S):
    """Vertices, faces and the neighbour across each edge (watertight mesh: every edge has
    exactly two triangles). nb[t, k] = triangle across edge (f[t,k], f[t,k+1])."""
    me = S.to_mesh()
    v = np.asarray(me.vert_properties)[:, :3].astype(np.float64)
    f = np.asarray(me.tri_verts).astype(np.int64)
    n, nv = len(f), len(v)
    a = np.concatenate([f[:, 0], f[:, 1], f[:, 2]])
    b = np.concatenate([f[:, 1], f[:, 2], f[:, 0]])
    key = np.minimum(a, b) * nv + np.maximum(a, b)
    order = np.argsort(key, kind='stable')
    ks = key[order]
    same = np.where(ks[1:] == ks[:-1])[0]
    nb = np.full(3 * n, -1, np.int64)
    i, j = order[same], order[same + 1]
    nb[i] = j % n
    nb[j] = i % n
    nb = nb.reshape(3, n).T.copy()            # (n, 3): index k*n+t -> [t, k]
    return v, f, nb


def _tri_keys(T, dec=5):
    """Hashable key per triangle, independent of vertex order and of the triangle order."""
    q = np.round(np.asarray(T, np.float64), dec)
    q = q + 0.0
    o = np.lexsort((q[:, :, 2], q[:, :, 1], q[:, :, 0]), axis=1)
    s = np.take_along_axis(q, o[:, :, None], axis=1)
    return [r.tobytes() for r in s.reshape(len(s), 9)]


def _on_surface(points, src, k=12, tol=2e-3, chunk=60000):
    """For each point: index of the src triangle it lies on, or -1. Em blocos de pontos: com
    malhas de milhões de triângulos (sem perder qualidade) a conta inteira de uma vez passava de
    vários GB de memória; o resultado é o mesmo."""
    from scipy.spatial import cKDTree
    if len(points) == 0 or len(src) == 0:
        return np.full(len(points), -1, np.int64)
    points = np.asarray(points)
    src = np.asarray(src)
    cs = src.mean(1)
    tree = cKDTree(cs)
    hk = None
    if len(points) > 20000:
        hk_ = _hkey(cs)
        o = np.argsort(hk_, kind='stable')
        hk = (hk_[o], o)
    # um ponto sobre um triângulo fica a no máximo r (maior distância vértice-centro) do centro
    # dele: a busca para nessa distância e os pontos longe da superfície (faces do corte) saem logo
    bound = float(np.linalg.norm(src - cs[:, None, :], axis=2).max()) + tol + 1e-6
    far = np.array([[[1e9, 1e9, 1e9], [1e9 + 1, 1e9, 1e9], [1e9, 1e9 + 1, 1e9]]])
    srcp = np.concatenate([src, far])                   # índice "nenhum" da busca (nunca é escolhido)
    lo, hi = src.reshape(-1, 3).min(0) - tol - 1e-6, src.reshape(-1, 3).max(0) + tol + 1e-6
    box = np.all((points >= lo) & (points <= hi), axis=1)
    if not box.all():                                   # fora da caixa da malha: não está nela
        out = np.full(len(points), -1, np.int64)
        if box.any():
            pb = points[box]
            out[box] = (np.concatenate([_on_surface_q(pb[i:i + chunk], srcp, tree, k, tol, bound, hk) for i in range(0, len(pb), chunk)])
                        if len(pb) > chunk else _on_surface_q(pb, srcp, tree, k, tol, bound, hk))
        return out
    if len(points) > chunk:
        return np.concatenate([_on_surface_q(points[i:i + chunk], srcp, tree, k, tol, bound, hk) for i in range(0, len(points), chunk)])
    return _on_surface_q(points, srcp, tree, k, tol, bound, hk)


def _hkey(c):
    q = np.round(np.asarray(c, np.float64) * 1e4).astype(np.int64)
    return (q[:, 0] * 73856093) ^ (q[:, 1] * 19349663) ^ (q[:, 2] * 83492791)


def _on_surface_q(points, src, tree, k, tol, bound=np.inf, hk=None):
    k = int(min(k, len(src) - 1))
    if hk is not None and len(points) > 2000:
        # triângulo copiado igual da malha de origem (a pele fora do corte): o centro bate com o
        # centro de um triângulo dela. Confere e só os outros vão para a busca.
        sk, so = hk
        kq = _hkey(points)
        pos = np.clip(np.searchsorted(sk, kq), 0, len(sk) - 1)
        cand = np.where(sk[pos] == kq, so[pos], len(src) - 1)
        out = _on_surface_idx(points, src, cand[:, None], tol)
        miss = np.where(out < 0)[0]
        if len(miss):
            out[miss] = _on_surface_q_kd(points[miss], src, tree, k, tol, bound)
        return out
    return _on_surface_q_kd(points, src, tree, k, tol, bound)


def _on_surface_q_kd(points, src, tree, k, tol, bound=np.inf):
    if k > 1 and len(points) > 2000:
        # caminho rápido: quase todo ponto está no triângulo de centro mais próximo (a pele que o
        # corte não mexeu); só os outros fazem a busca completa. Mesmo resultado da busca completa.
        d1, i1 = tree.query(points, k=1, distance_upper_bound=bound)
        out = _on_surface_idx(points, src, np.asarray(i1)[:, None], tol)
        miss = np.where((out < 0) & np.isfinite(d1))[0]   # nenhum centro perto: não está em triângulo nenhum
        if len(miss):
            _, idx = tree.query(points[miss], k=k, distance_upper_bound=bound)
            out[miss] = _on_surface_idx(points[miss], src, idx, tol)
        return out
    _, idx = tree.query(points, k=k, distance_upper_bound=bound)
    if k == 1:
        idx = idx[:, None]
    return _on_surface_idx(points, src, idx, tol)


def _on_surface_idx(points, src, idx, tol):
    t = src[idx]
    a, b, c = t[:, :, 0], t[:, :, 1], t[:, :, 2]
    p = points[:, None, :]
    n = np.cross(b - a, c - a)
    nn = np.linalg.norm(n, axis=2)
    nn[nn == 0] = 1e-12
    dist = np.abs(((p - a) * n).sum(2)) / nn
    v0, v1, v2 = b - a, c - a, p - a
    d00 = (v0 * v0).sum(2); d01 = (v0 * v1).sum(2); d11 = (v1 * v1).sum(2)
    d20 = (v2 * v0).sum(2); d21 = (v2 * v1).sum(2)
    den = d00 * d11 - d01 * d01
    den[den == 0] = 1e-12
    vv = (d11 * d20 - d01 * d21) / den
    ww = (d00 * d21 - d01 * d20) / den
    uu = 1 - vv - ww
    e = 1e-3
    ok = (dist < tol) & (uu >= -e) & (vv >= -e) & (ww >= -e)
    hit = ok.any(1)
    pick = ok.argmax(1)
    out = idx[np.arange(len(points)), pick].astype(np.int64)
    out[~hit] = -1
    return out


def _frame(n):
    """Right-handed frame (u, v, n): v is "up" (world Z) projected on the plane across n, so a
    diamond with a corner on v prints without support when its axis is horizontal."""
    n = np.asarray(n, np.float64)
    n = n / max(np.linalg.norm(n), 1e-12)
    up = np.array([0.0, 0.0, 1.0])
    a = up - n * (up @ n)
    if np.linalg.norm(a) < 0.15:                     # n almost vertical
        a = np.array([0.0, 1.0, 0.0]) - n * n[1]
    v = a / np.linalg.norm(a)
    u = np.cross(v, n)
    return np.stack([u, v, n], axis=1)               # columns


def _T(R, o):
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = o
    return T


def _inv(T):
    R, o = T[:3, :3], T[:3, 3]
    return _T(R.T, -R.T @ o)


def _vol(m):
    return 0.0 if m is None or m.is_empty() else float(m.volume())


# ----------------------------------------------------------------------------- regions
class Regions:
    """Painted areas of the model: connected groups of triangles of one colour (2 and up)."""

    def __init__(self, S, paint):
        self.S = S
        self.paint = np.asarray(paint, np.uint8)
        self.v, self.f, self.nb = _topology(S)
        self.T = self.v[self.f]
        n = len(self.f)
        e1 = self.T[:, 1] - self.T[:, 0]
        e2 = self.T[:, 2] - self.T[:, 0]
        cr = np.cross(e1, e2)
        self.area = np.linalg.norm(cr, axis=1) / 2
        self.nrm = cr / np.maximum(np.linalg.norm(cr, axis=1, keepdims=True), 1e-12)
        self.cen = self.T.mean(1)
        self.list = []
        self.of = np.full(n, -1, np.int64)
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components
        for c in sorted(set(int(x) for x in np.unique(self.paint)) - {0, 1}):
            m = self.paint == c
            idx = np.where(m)[0]
            if not len(idx):
                continue
            loc = np.full(n, -1, np.int64)
            loc[idx] = np.arange(len(idx))
            nbm = self.nb[idx]
            rows, cols = [], []
            for k in range(3):
                o = nbm[:, k]
                ok = (o >= 0) & m[np.maximum(o, 0)]
                rows.append(np.arange(len(idx))[ok])
                cols.append(loc[o[ok]])
            rows = np.concatenate(rows)
            cols = np.concatenate(cols)
            G = coo_matrix((np.ones(len(rows), np.int8), (rows, cols)), shape=(len(idx), len(idx)))
            nc, lab = connected_components(G, directed=False)
            for r in range(nc):
                tris = idx[lab == r]
                a = float(self.area[tris].sum())
                if a < MIN_AREA:
                    continue
                w = self.area[tris][:, None]
                nm = (self.nrm[tris] * w).sum(0)
                ln = np.linalg.norm(nm)
                self.list.append(dict(cor=c, tris=tris, area=a,
                                      centro=(self.cen[tris] * w).sum(0) / w.sum(),
                                      normal=nm / ln if ln > 1e-9 else np.array([0, 0, 1.0]),
                                      normal_len=float(ln / max(a, 1e-9))))
        self.list.sort(key=lambda r: (r['cor'], -r['area']))
        for i, r in enumerate(self.list):
            r['id'] = i
            self.of[r['tris']] = i

    def loops(self, rid):
        return self.loops_out(rid)[0]

    def loops_out(self, rid):
        """Borders of a region as closed loops of vertex indices (outer border and holes), and
        for each loop the triangles just outside it."""
        tris = self.list[rid]['tris']
        inside = np.zeros(len(self.f), bool)
        inside[tris] = True
        nxt = {}
        for k in range(3):
            o = self.nb[tris, k]
            out = (o < 0) | ~inside[np.maximum(o, 0)]
            a = self.f[tris[out], k]
            b = self.f[tris[out], (k + 1) % 3]
            for x, y, t in zip(a.tolist(), b.tolist(), o[out].tolist()):
                nxt.setdefault(x, []).append((y, t))
        loops, outs = [], []
        while nxt:
            start = next(iter(nxt))
            loop, ot = [start], []
            cur = start
            for _ in range(10 ** 7):
                lst = nxt.get(cur)
                if not lst:
                    break
                y, t = lst.pop()
                ot.append(t)
                if not lst:
                    del nxt[cur]
                if y == start:
                    break
                loop.append(y)
                cur = y
            if len(loop) >= 3:
                loops.append(np.array(loop, np.int64))
                outs.append(np.array(ot, np.int64))
        return loops, outs

    def info(self, rid):
        r = self.list[rid]
        return dict(id=rid, cor=r['cor'], area=round(r['area'], 1), triangulos=int(len(r['tris'])),
                    centro=[round(float(x), 2) for x in r['centro']],
                    normal=[round(float(x), 3) for x in r['normal']])


# ----------------------------------------------------------------------------- 2D contour
def _resample(P, step):
    Q = np.vstack([P, P[:1]])
    seg = np.linalg.norm(np.diff(Q, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    total = s[-1]
    if total < 1e-6:
        return P
    n = max(16, int(math.ceil(total / step)))
    t = np.linspace(0, total, n, endpoint=False)
    return np.stack([np.interp(t, s, Q[:, 0]), np.interp(t, s, Q[:, 1])], axis=1), total / n


def _smooth(P, sigma):
    """Closed polyline smoothed by a Gaussian of `sigma` mm along the border (in the frequency
    domain, so the loop stays closed and the result does not depend on where it starts)."""
    R, h = _resample(P, min(0.1, max(sigma / 4, 0.03)))
    if sigma <= 0:
        return R
    k = sigma / h
    f = np.fft.fftfreq(len(R))
    g = np.exp(-2.0 * (math.pi * f * k) ** 2)
    return np.stack([np.fft.ifft(np.fft.fft(R[:, 0]) * g).real,
                     np.fft.ifft(np.fft.fft(R[:, 1]) * g).real], axis=1)


def _poly_area(P):
    x, y = P[:, 0], P[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _cs(P):
    return mf.CrossSection([np.ascontiguousarray(P, np.float64)], mf.FillRule.EvenOdd)


def _inradius(cs):
    """Largest circle inside the section: (radius, centre). Binary search on inward offsets."""
    if cs.is_empty():
        return 0.0, np.zeros(2)
    b = cs.bounds()
    lo, hi = 0.0, 0.5 * max(b[2] - b[0], b[3] - b[1])
    for _ in range(18):
        mid = 0.5 * (lo + hi)
        if cs.offset(-mid, mf.JoinType.Round, 2.0, 24).is_empty():
            hi = mid
        else:
            lo = mid
    core = cs.offset(-lo * 0.97, mf.JoinType.Round, 2.0, 24)
    if core.is_empty():
        core = cs
    parts = core.decompose()
    big = max(parts, key=lambda q: q.area()) if parts else core
    bb = big.bounds()
    return lo, np.array([(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2])


# ----------------------------------------------------------------------------- pins
def _pin(h, z0, z1, xy=(0.0, 0.0), tip_top=True, tip_bottom=False):
    """Diamond pin along local z (corner on +y = up), from z0 to z1, 45 degree pointed ends."""
    x, y = xy
    sq = lambda z: [(x + h, y, z), (x, y + h, z), (x - h, y, z), (x, y - h, z)]
    a = z0 + (h if tip_bottom else 0.0)
    b = z1 - (h if tip_top else 0.0)
    if b < a:
        b = a = 0.5 * (a + b)
    pts = sq(a) + sq(b)
    if tip_top:
        pts.append((x, y, z1))
    if tip_bottom:
        pts.append((x, y, z0))
    return mf.Manifold.hull_points([list(map(float, p)) for p in pts])


def _hole(h, z0, z1, c, xy=(0.0, 0.0), tip_top=True, tip_bottom=False):
    """The pin grown by the clearance c on every face."""
    # side faces (normal across the axis) move c*sqrt2 at the corners; tip faces (normal at
    # 1:1:1) need the apex c*sqrt3 further out to keep the gap c
    S3 = math.sqrt(3.0)
    return _pin(h + c * S2, z0 - (c * S3 if tip_bottom else 0.0), z1 + (c * S3 if tip_top else 0.0),
                xy, tip_top, tip_bottom)


def _fit(h, k, *avail):
    """Pin size that fits: half diagonal h (shrunk when the material is thin) and length up to
    k*h on each side. None when not even a 1.2 mm pin fits."""
    lim = min(avail) - 0.4
    if lim < 0.6:
        return None
    h = min(h, lim)
    return h, [max(min(k * h, a), h + 0.4) for a in avail]


def _snap(h, z0, z1, c, xy=(0.0, 0.0)):
    """Snap lock ("trava"): a diamond pin split in two prongs with a barb near the tip, and its
    hole with a chamber where the barb clicks in. Every face at 45 degrees: prints without
    support. Returns (pin, hole) in the local frame (pin from z0 to z1 along +z)."""
    x, y = xy
    b = min(0.4, max(0.25, 0.2 * h))                    # barb height over the pin faces
    zb = z1 - h - b - 0.4                               # barb centre, below the pointed tip
    sq = lambda hh, z: [(x + hh, y, z), (x, y + hh, z), (x - hh, y, z), (x, y - hh, z)]
    hp = lambda pts: mf.Manifold.hull_points([list(map(float, q)) for q in pts])
    pin = E.flat(_pin(h, z0, z1, xy) + hp(sq(h, zb - b) + sq(h + b, zb) + sq(h, zb + b)))
    # slot through the outer part: the two prongs flex inwards while the barb passes
    w = 2 * b + 0.3
    zs = z0 + 0.45 * (z1 - z0)
    slot = E.BOX(x - w / 2, x + w / 2, y - 2 * h - 2, y + 2 * h + 2, zs, z1 + 1)
    pin = E.flat(pin - slot)
    S3 = math.sqrt(3.0)
    k = c * S2 * 1.1                                    # the barb ramps need a bit more than the faces
    hole = E.flat(_hole(h, z0, z1, c, xy) + hp(sq(h + k, zb - b - k) + sq(h + b + k, zb) + sq(h + k, zb + b + k)))
    return pin, hole


def _depth_along(M, p, d, limit):
    """Material along direction d from point p (on or near the surface of M): distance to
    where the material ends. If p is just outside (a curved cut face), the material starts at
    the first hit and ends at the second."""
    p = np.asarray(p, np.float64)
    d = np.asarray(d, np.float64) / np.linalg.norm(d)
    hits = M.ray_cast(list(p - d * 0.05), list(p + d * limit))
    ds = sorted(float(np.dot(np.asarray(h.position) - p, d)) for h in hits)
    ds = [x for x in ds if x > 0.02]
    if not ds:
        return 0.0
    if len(ds) % 2 == 0 and len(ds) >= 2 and ds[0] < 1.0:     # outside: enter, then leave
        return ds[1]
    return ds[0]


# ----------------------------------------------------------------------------- one cut
def _chk(nivel, texto):
    return dict(nivel=nivel, texto=texto)


def _fmt(x, d=1):
    return f'{x:.{d}f}'.replace('.', ',')


def _inside_poly(poly, pts):
    """Pontos 2D dentro do polígono (rotina em C do scikit-image)."""
    from skimage.measure import points_in_poly
    pts = np.asarray(pts, np.float64)
    if not len(pts):
        return np.zeros(0, bool)
    return points_in_poly(pts, np.asarray(poly, np.float64))


def _paint_footprint(Tl, r):
    """Sombra (no plano do encaixe) dos triângulos pintados, já no referencial local (x, y): a união
    deles, com os dentes da borda preenchidos (fechamento de raio r: só cresce, nunca tira área)."""
    if not len(Tl):
        return None
    P = np.asarray(Tl, np.float64)[:, :, :2]
    ar = (P[:, 1, 0] - P[:, 0, 0]) * (P[:, 2, 1] - P[:, 0, 1]) - (P[:, 2, 0] - P[:, 0, 0]) * (P[:, 1, 1] - P[:, 0, 1])
    keep = np.abs(ar) > 1e-10                          # triângulo de lado (parede vertical) não tem sombra
    P = P[keep]
    ar = ar[keep]
    P[ar < 0] = P[ar < 0][:, ::-1]                     # todos no mesmo sentido: a união não cancela nada
    if not len(P):
        return None
    cs = mf.CrossSection([t.tolist() for t in P], mf.FillRule.Positive)
    if r > 0:
        J = mf.JoinType.Round
        cs = cs.offset(r, J, 2.0, 48).offset(-r, J, 2.0, 48)
    return cs


class _SemPegada(Exception):
    """Borda vinda da linha do corte livre: a sombra dos triângulos marcados não entra."""


def cut_plug(host, R, rid, prm, diag):
    """Plug (tampao). Returns dict(ok, checks, body, piece, extra, axis, ...)."""
    reg = R.list[rid]
    checks = []
    clr = float(prm['folga'])
    depth = float(prm['profundidade'])
    wall = float(prm.get('parede', 1.2))
    # insertion direction: mean normal of the painted area, tilted by the user
    n = reg['normal'].copy()
    Fr = _frame(n)
    a, b = math.radians(float(prm.get('incl_a') or 0)), math.radians(float(prm.get('incl_b') or 0))
    if a or b:
        Ra = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
        Rb = np.array([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]])
        n = Fr @ (Ra @ Rb @ np.array([0, 0, 1.0]))
        Fr = _frame(n)
    o = reg['centro']
    Tw = _T(Fr, o)                                    # local -> world
    loc = lambda P: (np.asarray(P) - o) @ Fr          # world -> local
    tris = reg['tris']
    # area facing away from the insertion direction: a plug cannot reach it
    back = R.area[tris][(R.nrm[tris] @ n) < 0.05].sum() / max(reg['area'], 1e-9)
    vidx = np.unique(R.f[tris].ravel())
    hz = loc(R.v[vidx])[:, 2]
    hmin, hmax = float(hz.min()), float(hz.max())
    # contour: painted borders projected on the plane across n, smoothed
    loops, outs = R.loops_out(rid)
    nested = prm.get('_aninhar') or set()
    borda = prm.get('_borda')                         # corte livre com tampão (beta): a borda é a linha desenhada
    blen = []
    for L in loops:
        P = R.v[L]
        blen.append(np.linalg.norm(np.diff(np.vstack([P, P[:1]]), axis=0), axis=1))
    # automatic smoothing: big enough to erase the teeth of the largest border triangles
    # (brush painting follows whole triangles), small enough to keep the shape of the area
    p90 = float(np.percentile(np.concatenate(blen), 90)) if blen else 0.5
    sigma = float(prm.get('suavizar') or 0) or min(2.5, max(0.5, 1.2 * p90), max(0.5, 0.18 * math.sqrt(reg['area'])))
    polys, fill = [], []
    for L, ot in zip(loops, outs):
        P = _smooth(loc(R.v[L])[:, :2], sigma)
        if len(P) >= 8:
            polys.append(P)
            # a hole whose inside is another part being separated is filled: that part is cut
            # later from this one (a pupil from the eye), not left as a post in the body
            ins = R.of[ot[ot >= 0]]
            fill.append(len(ins) > 0 and np.isin(ins, list(nested)).mean() > 0.5)
    if borda:
        # a linha já é lisa e é exatamente onde o usuário quer a costura: nada de suavizar nem de engordar a borda
        polys = [loc(np.asarray(L, np.float64))[:, :2] for L in borda if len(L) >= 3]
        fill = [False] * len(polys)
        sigma = 0.0
    if not polys:
        return dict(ok=False, checks=checks + [_chk('erro', 'Não consegui ler a borda desta área.')])
    areas = [abs(_poly_area(P)) for P in polys]
    k0 = int(np.argmax(areas))
    cs = _cs(polys[k0])
    for k, P in enumerate(polys):
        if k != k0 and areas[k] >= 1.0 and not fill[k]:
            cs = cs - _cs(P)                          # holes of the painting stay in the body
    # close narrow notches and open thin spikes (rounded, radius ~ the smoothing): no
    # "ranhuras" left at the border
    rr = 0.8 * sigma
    J = mf.JoinType.Round
    cs2 = cs.offset(rr, J, 2.0, 48).offset(-2 * rr, J, 2.0, 48).offset(rr, J, 2.0, 48) if not borda else cs
    if not cs2.is_empty() and cs2.area() > 0.7 * cs.area():
        cs = cs2
    # a pintura inteira sai com o tampão: a borda suavizada arredonda a forma e o passo acima apaga
    # pontas finas (a ponta de uma sobrancelha), e o que fica fora dela continuava no rosto como uma
    # lâmina fina. A borda passa a conter sempre a sombra de todos os triângulos pintados (também as
    # paredes do relevo); a suavização só cresce a borda (preenche os dentes), nunca corta pintura.
    try:
        if borda:
            raise _SemPegada()
        # fechamento na escala do bico (0,8 mm): o vão entre dois cílios pintados mais estreito que isso
        # deixaria no corpo uma cunha de pele que não imprime; ela vai junto com a peça
        foot = _paint_footprint(loc(R.T[tris]), max(0.8 * sigma, 0.8))
        if foot is not None and not foot.is_empty():
            cs = cs + foot
            for k, P in enumerate(polys):
                if k != k0 and areas[k] >= 1.0 and not fill[k]:
                    cs = cs - _cs(P)              # os furos da pintura continuam no corpo
    except _SemPegada:
        pass
    except Exception:
        traceback.print_exc()
    cs = cs.simplify(0.005)
    if cs.is_empty() or cs.area() < MIN_AREA:
        return dict(ok=False, checks=checks + [_chk('erro', 'A borda suavizada ficou pequena demais: diminua "Suavizar borda".')])
    if borda:
        checks.append(_chk('ok', 'Borda na linha desenhada: a costura fica exatamente nela.'))
    else:
        checks.append(_chk('ok', f'Borda lisa: a pintura foi suavizada em {_fmt(sigma, 2)} mm ao longo da borda.'))
    # a peça é a área pintada inteira (a sobrancelha com a largura e as paredes que tem); a folga sai do
    # bolso no corpo, que fica a folga maior em volta. Antes a peça encolhia a folga de cada lado: numa
    # sobrancelha de 2,6 mm ela ficava 23% mais fina e com laterais retas no lugar das do relevo.
    cs_in = cs
    cs = cs_in.offset(clr, mf.JoinType.Round, 2.0, 48)
    top = hmax + 1.0
    bottom = hmin - depth
    if back > 0.03:
        # parte da área fica de lado ou de costas (as paredes de um relevo, como uma sobrancelha): o
        # tampão leva o relevo inteiro, então só é problema se ele levar pele que não está pintada
        # (a pintura dá a volta numa parte, como uma manga). Mede a pele não pintada dentro do tampão,
        # longe da borda (junto da borda é a suavização).
        inner = cs_in.offset(-(sigma + 0.3), mf.JoinType.Round, 2.0, 24)
        steal = 0.0
        if not inner.is_empty():
            mine = np.zeros(len(R.area), bool)
            mine[tris] = True
            cen = R.T.mean(1)
            bb = inner.bounds()
            lc = loc(cen)
            cand = np.where(~mine & (lc[:, 0] >= bb[0]) & (lc[:, 0] <= bb[2]) & (lc[:, 1] >= bb[1]) & (lc[:, 1] <= bb[3]) &
                            (lc[:, 2] > bottom + clr) & (lc[:, 2] < top))[0]
            if len(cand):
                ins = np.zeros(len(cand), bool)
                for pl in inner.to_polygons():
                    ins ^= _inside_poly(np.asarray(pl, np.float64), lc[cand, :2])
                steal = float(R.area[cand[ins]].sum()) / max(reg['area'], 1e-9)
        if steal > 0.03:
            checks.append(_chk('erro', f'{round(back * 100)}% da área fica de costas para a direção de encaixe e o tampão levaria pele que '
                                       'não está pintada: um tampão não sai. Use "membro" ou divida a pintura em partes menores.'))
        else:
            checks.append(_chk('ok', 'Relevo: as paredes laterais da área saem inteiras com a peça (nenhuma pele sem pintura vai junto).'))

    def prism(c, z0, z1):
        return E.X(c.extrude(z1 - z0).translate([0, 0, z0]), Tw)

    P_full = prism(cs, bottom, top)
    P_in = prism(cs_in, bottom + clr, top)
    inter = E.parts(E.flat(host ^ P_full), 0.02)
    if len(inter) > 1:
        checks.append(dict(_chk('erro', 'A direção de encaixe atravessa outra parte do modelo: incline a direção ou reduza a profundidade.'), cod='direcao'))
    # the plug must come out straight: nothing of the model right above the area
    col = prism(cs_in.offset(-0.05, mf.JoinType.Round, 2.0, 24), top - 0.6, top + (top - bottom) + 2.0)
    blk = E.flat(host ^ col)
    blocked = _vol(blk)
    if blocked > 0.02:
        # uma parte do modelo cobre só um pedaço da área (uma mecha por cima da ponta da sobrancelha):
        # o tampão leva tudo o que está à vista; o pedaço escondido debaixo dela não sai reto e fica no
        # corpo (avisado). Só se o que sai é a maior parte da área.
        try:
            sh = _paint_footprint(loc(tri_array(blk)), 0.0)
            if sh is not None and not sh.is_empty():
                vis = cs_in - sh.offset(clr + 0.2, mf.JoinType.Round, 2.0, 24)
                vis = vis.offset(-0.3 * sigma, mf.JoinType.Round, 2.0, 24).offset(0.3 * sigma, mf.JoinType.Round, 2.0, 24)
                if not vis.is_empty() and vis.area() >= 0.6 * cs_in.area():
                    hid = 1.0 - vis.area() / max(cs_in.area(), 1e-9)
                    cs_in = vis
                    cs = cs_in.offset(clr, mf.JoinType.Round, 2.0, 48)
                    P_full = prism(cs, bottom, top)
                    P_in = prism(cs_in, bottom + clr, top)
                    col = prism(cs_in.offset(-0.05, mf.JoinType.Round, 2.0, 24), top - 0.6, top + (top - bottom) + 2.0)
                    blocked = _vol(E.flat(host ^ col))
                    if blocked <= 0.02:
                        checks.append(_chk('aviso', f'{round(hid * 100)}% da área fica debaixo de outra parte do modelo (uma mecha por cima, '
                                                    'por exemplo) e não sai reto com o tampão: esse pedaço fica no corpo, escondido por ela.'))
        except Exception:
            traceback.print_exc()
    if blocked > 0.02:
        checks.append(dict(_chk('erro', 'Há parte do modelo na frente da área, na direção de encaixe: a peça não sai reto. Incline a direção.'), cod='direcao'))
    else:
        checks.append(_chk('ok', 'Direção de encaixe livre: a peça entra reta.'))
    # wall left behind the pocket
    slab = prism(cs, bottom - wall, bottom)
    sv = _vol(slab)
    thin = _vol(E.flat(slab - host)) / sv if sv > 0 else 0
    if thin > 0.02:
        checks.append(_chk('aviso', f'Parede atrás do encaixe com menos de {_fmt(wall)} mm em {round(thin * 100)}% da área: reduza a profundidade.'))
    else:
        checks.append(_chk('ok', f'Parede atrás do encaixe com {_fmt(wall)} mm ou mais.'))
    if depth - clr < 0.8:
        checks.append(_chk('erro', 'Peça fina demais: a profundidade menos a folga deve dar pelo menos 0,8 mm.'))
    body = E.flat(host - P_full)
    piece = E.flat(host ^ P_in)
    pp = E.parts(piece, 0.02)
    if not pp:
        return dict(ok=False, checks=checks + [_chk('erro', 'O corte não gerou peça: confira a profundidade.')])
    if len(pp) > 1:
        pp.sort(key=lambda q: -q.volume())
        piece = pp[0]
    nb0 = len(E.parts(host, 0.02))
    nb1 = len(E.parts(body, 0.02))
    if nb1 > nb0:
        checks.append(_chk('erro', 'O encaixe atravessa o modelo e divide o corpo: reduza a profundidade.'))
    inr, pole = _inradius(cs_in)
    if inr < 0.6:
        checks.append(_chk('aviso', f'Peça muito estreita (cerca de {_fmt(2 * inr)} mm no ponto mais largo): difícil de imprimir e manusear.'))
    # pin
    extra = []
    pino = prm.get('pino', 'nenhum')
    if pino in PINOS and pino != 'nenhum':
        r_ = _plug_pin(host, body, piece, pino, prm, clr, wall, inr, pole, bottom, Tw, Fr, o, n, diag)
        checks += r_['checks']
        body, piece, extra = r_['body'], r_['piece'], r_['extra']
    gap = piece.min_gap(body, clr + 0.4)
    if gap < clr - 0.03:
        checks.append(_chk('erro', f'Folga real {_fmt(gap, 2)} mm, menor que a pedida.'))
    else:
        checks.append(_chk('ok', f'Folga real {_fmt(min(gap, clr), 2)} mm entre a peça e o encaixe.'))
    # print orientation: the flat bottom down (local n -> +Z)
    Tp = _inv(Tw)
    return dict(ok=not any(c['nivel'] == 'erro' for c in checks), checks=checks, body=body, piece=piece,
                extra=extra, axis=n, print_T=Tp, sigma=sigma, zone=(o, n, Fr, cs, bottom, top))


def _plug_pin(host, body, piece, pino, prm, clr, wall, inr, pole, bottom, Tw, Fr, o, n, diag):
    checks, extra = [], []
    want = float(prm.get('pino_mm') or 0) / 2.0       # half diagonal
    h = want or min(2.5, max(0.8, 0.4 * inr))
    room = inr - clr * S2 - 0.8
    if room < 0.7:
        checks.append(_chk('aviso', 'O pino não cabe nesta área (estreita demais): saiu sem pino.'))
        return dict(checks=checks, body=body, piece=piece, extra=extra)
    if h > room:
        h = room
    up = Fr[:, 2]
    base_pt = o + Fr @ np.array([pole[0], pole[1], bottom + clr])     # on the plug bottom
    t_piece = _depth_along(piece, base_pt + up * 0.01, up, diag)        # plug thickness at the pin
    floor_pt = o + Fr @ np.array([pole[0], pole[1], bottom])
    t_body = _depth_along(host, floor_pt - up * 0.01, -up, diag) if pino in ('peca', 'cavilha') else 0.0
    xy = (pole[0], pole[1])
    W = lambda m: E.X(m, Tw)
    if pino == 'corpo':
        f_ = _fit(h, 4, t_piece - clr * S2 - 0.8)
        if f_ is None:
            checks.append(_chk('aviso', 'A peça é fina demais para um pino no corpo: saiu sem pino. Aumente a profundidade.'))
            return dict(checks=checks, body=body, piece=piece, extra=extra)
        h, (L,) = f_
        pin = W(_pin(h, bottom - 0.6, bottom + clr + L, xy))
        hole = W(_hole(h, bottom - 0.05, bottom + clr + L, clr, xy))
        body = E.flat(body + pin)
        piece = E.flat(piece - hole)
        checks.append(_chk('ok', f'Pino no corpo: {_fmt(2 * h)} mm de largura, {_fmt(L)} mm dentro da peça.'))
    elif pino == 'trava':
        f_ = _fit(max(h, 1.4), 4, t_piece - clr * S2 - 0.8)
        if f_ is None or f_[0] < 1.4 or room < 1.4:
            checks.append(_chk('aviso', 'A trava precisa de pino com 2,8 mm ou mais e de peça mais funda: saiu sem pino. '
                                        'Aumente a profundidade ou use o pino no corpo.'))
            return dict(checks=checks, body=body, piece=piece, extra=extra)
        h, (L,) = f_
        pin, hole = _snap(h, bottom - 0.6, bottom + clr + L, clr, xy)
        body = E.flat(body + W(pin))
        piece = E.flat(piece - W(hole))
        checks.append(_chk('ok', f'Trava de pressão: pino partido com garra ({_fmt(2 * h)} mm), {_fmt(L)} mm dentro da peça. '
                                 'Entra com pressão e segura sem cola.'))
    elif pino == 'peca':
        f_ = _fit(h, 4, t_body - clr * S2 - wall)
        if f_ is None:
            checks.append(_chk('aviso', 'Pouco material atrás do encaixe para o pino: saiu sem pino.'))
            return dict(checks=checks, body=body, piece=piece, extra=extra)
        h, (L,) = f_
        pin = W(_pin(h, bottom + clr - L - clr, bottom + clr + 0.6, xy, tip_top=False, tip_bottom=True))
        hole = W(_hole(h, bottom - L - clr, bottom + 0.05, clr, xy, tip_top=False, tip_bottom=True))
        body = E.flat(body - hole)
        piece = E.flat(piece + pin)
        checks.append(_chk('aviso', f'Pino na peça ({_fmt(2 * h)} × {_fmt(L)} mm): a peça perde a base plana; imprima com suporte '
                                    'ou prefira o pino no corpo.'))
    else:  # cavilha (loose dowel): holes in both, the dowel prints lying down
        f_ = _fit(h, 3, t_piece - clr * S2 - 0.8, t_body - clr * S2 - wall)
        if f_ is None:
            checks.append(_chk('aviso', 'Não há material para a cavilha dos dois lados: saiu sem pino.'))
            return dict(checks=checks, body=body, piece=piece, extra=extra)
        h, (La, Lb) = f_
        z_lo, z_hi = bottom - Lb, bottom + clr + La
        dowel_local = _pin(h, z_lo + clr * S2, z_hi - clr * S2, xy, tip_top=True, tip_bottom=True)
        hole = W(_hole(h, z_lo + clr * S2, z_hi - clr * S2, clr, xy, tip_top=True, tip_bottom=True))
        body = E.flat(body - hole)
        piece = E.flat(piece - hole)
        extra.append(dict(mesh=W(dowel_local), axis=up))
        checks.append(_chk('ok', f'Cavilha solta de {_fmt(2 * h)} × {_fmt(z_hi - z_lo - 2 * clr * S2)} mm: furos com folga dos dois lados.'))
    return dict(checks=checks, body=body, piece=piece, extra=extra)


def _lay_dowel():
    """Print orientation of a dowel along local z (corners on x and y): turned 45 degrees so a
    face is down, then laid along X."""
    r45 = E.rot_z(45)
    ry = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1.0]])
    return ry @ r45


def _plane_fit(P):
    c = P.mean(0)
    _, s, vt = np.linalg.svd(P - c, full_matrices=False)     # mesmo resultado, sem a matriz N x N
    return c, vt[2], float(np.abs((P - c) @ vt[2]).max())


def _smooth_loop3(P, sigma, step=0.25):
    """Closed 3D polyline resampled along its length and smoothed (Gaussian, sigma mm)."""
    Q = np.vstack([P, P[:1]])
    seg = np.linalg.norm(np.diff(Q, axis=0), axis=1)
    s_ = np.concatenate([[0], np.cumsum(seg)])
    n = max(24, int(s_[-1] / step))
    t = np.linspace(0, s_[-1], n, endpoint=False)
    R_ = np.stack([np.interp(t, s_, Q[:, k]) for k in range(3)], axis=1)
    h = s_[-1] / n
    f = np.fft.fftfreq(n)
    g = np.exp(-2.0 * (math.pi * f * sigma / h) ** 2)
    return np.stack([np.fft.ifft(np.fft.fft(R_[:, k]) * g).real for k in range(3)], axis=1)


def border_surface(P, c, nn, diag, sigma=0.8):
    """Smooth surface through a painted border (not flat): heights over the plane (c, nn).
    Inside and around the border the heights are harmonic (Laplace): the surface passes
    through the smoothed border and never bulges beyond it (no overshoot, unlike a spline),
    then it fades back to the plane away from the border.
    Returns (half-space solid on the +nn side, height function of local x,y, info)."""
    from scipy.sparse.linalg import spsolve
    from scipy.interpolate import RegularGridInterpolator
    Fr = _frame(nn)
    Q = _smooth_loop3((P - c) @ Fr, sigma)
    R0 = float(np.linalg.norm(Q[:, :2], axis=1).max())
    stepg = max(0.15, R0 / 60.0)
    g = np.arange(-1.7 * R0, 1.7 * R0 + stepg, stepg)
    ng = len(g)
    GX, GY = np.meshgrid(g, g, indexing='ij')
    fixed = np.full((ng, ng), np.nan)
    acc = np.zeros((ng, ng))
    cnt = np.zeros((ng, ng))
    ix = np.clip(np.round((Q[:, 0] - g[0]) / stepg).astype(int), 0, ng - 1)
    iy = np.clip(np.round((Q[:, 1] - g[0]) / stepg).astype(int), 0, ng - 1)
    np.add.at(acc, (ix, iy), Q[:, 2])
    np.add.at(cnt, (ix, iy), 1)
    fixed[cnt > 0] = acc[cnt > 0] / cnt[cnt > 0]
    rr = np.hypot(GX, GY)
    fixed[(rr >= 1.6 * R0) & np.isnan(fixed)] = 0.0              # back to the plane far out
    fixed[[0, -1], :] = np.where(np.isnan(fixed[[0, -1], :]), 0.0, fixed[[0, -1], :])
    fixed[:, [0, -1]] = np.where(np.isnan(fixed[:, [0, -1]]), 0.0, fixed[:, [0, -1]])
    free = np.isnan(fixed)
    idx = -np.ones((ng, ng), int)
    idx[free] = np.arange(free.sum())
    # Laplace na grade, montado de uma vez (mesma matriz da versão ponto a ponto)
    from scipy.sparse import coo_matrix
    nf_ = int(free.sum())
    fi, fj = np.where(free)
    rows, cols, vals = [np.arange(nf_)], [np.arange(nf_)], [np.full(nf_, 4.0)]
    bvec = np.zeros(nf_)
    fx = np.nan_to_num(fixed)
    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        a, b_ = fi + di, fj + dj
        nbf = free[a, b_]
        rows.append(np.arange(nf_)[nbf])
        cols.append(idx[a[nbf], b_[nbf]])
        vals.append(np.full(int(nbf.sum()), -1.0))
        np.add.at(bvec, np.arange(nf_)[~nbf], fx[a[~nbf], b_[~nbf]])
    A = coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(nf_, nf_))
    Hg = np.where(free, 0.0, fixed)
    if free.any():
        Hg[free] = spsolve(A.tocsr(), bvec)
    interp = RegularGridInterpolator((g, g), Hg, bounds_error=False, fill_value=0.0)

    def hf(xy):
        return interp(np.atleast_2d(xy))

    L = diag + 5.0
    step = max(0.25, R0 / 70.0)
    dense = g
    far = np.geomspace(1.7 * R0 + 2 * step, L, 12)
    ticks = np.unique(np.concatenate([-far[::-1], dense, far]))
    X, Y = np.meshgrid(ticks, ticks, indexing='ij')
    nx = len(ticks)
    H = hf(np.stack([X.ravel(), Y.ravel()], axis=1)).reshape(nx, nx)
    ztop = L
    bot = np.stack([X, Y, H], axis=-1).reshape(-1, 3)
    top = np.stack([X, Y, np.full_like(H, ztop)], axis=-1).reshape(-1, 3)
    V = np.vstack([bot, top])
    idx = np.arange(nx * nx).reshape(nx, nx)
    a, b_, c_, d_ = idx[:-1, :-1].ravel(), idx[1:, :-1].ravel(), idx[1:, 1:].ravel(), idx[:-1, 1:].ravel()
    off = nx * nx
    F = [np.stack([a, c_, b_], 1), np.stack([a, d_, c_], 1),                 # bottom, facing -z
         np.stack([a + off, b_ + off, c_ + off], 1), np.stack([a + off, c_ + off, d_ + off], 1)]
    ring = np.concatenate([idx[:, 0], idx[-1, 1:], idx[-2::-1, -1], idx[0, -2:0:-1]])   # counter clockwise
    r1 = np.roll(ring, -1)
    F += [np.stack([ring, r1, r1 + off], 1), np.stack([ring, r1 + off, ring + off], 1)]
    F = np.vstack(F)
    Vw = V @ Fr.T + c
    hs = mf.Manifold(mf.Mesh(vert_properties=np.ascontiguousarray(Vw, np.float32),
                             tri_verts=np.ascontiguousarray(F, np.uint32)))
    if hs.status() != mf.Error.NoError or hs.volume() <= 0:
        F2 = F[:, ::-1].copy()
        hs = mf.Manifold(mf.Mesh(vert_properties=np.ascontiguousarray(Vw, np.float32),
                                 tri_verts=np.ascontiguousarray(F2, np.uint32)))
    dev = float(np.abs(hf(Q[:, :2]) - Q[:, 2]).max())     # smoothed border to the cut surface
    inside = np.linalg.norm(np.stack([X.ravel(), Y.ravel()], 1), axis=1) < 0.9 * R0
    curv = float(np.ptp(H.ravel()[inside])) if inside.any() else 0.0
    return hs, hf, dict(desvio=dev, curvatura=curv, zsec=float(H.ravel()[inside].max()) + 0.3 if inside.any() else 0.02,
                        tol=float(np.abs(H).max()) + 0.1)


def _enclosed(R, rid, separated=()):
    """Triangles of the area plus the islands it encloses (a spot left unpainted, eyes painted
    in a face but not separated): they go with the part instead of leaving spikes in it."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    mine = R.of == rid
    n = len(mine)
    rest = ~mine
    rows, cols = [], []
    for k in range(3):
        o = R.nb[:, k]
        ok = rest & (o >= 0) & rest[np.maximum(o, 0)]
        rows.append(np.where(ok)[0])
        cols.append(o[ok])
    G = coo_matrix((np.ones(sum(len(r) for r in rows), np.int8), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n))
    nc, comp = connected_components(G, directed=False)
    comp = np.where(rest, comp, -1)
    carea = np.bincount(comp[rest], weights=R.area[rest], minlength=nc)
    big = int(np.argmax(carea))
    lim = min(0.3 * R.list[rid]['area'], 60.0)
    add = rest & (comp != big) & (carea[np.maximum(comp, 0)] < lim)
    if separated:
        add &= ~np.isin(R.of, list(separated))
    return mine | add


def _taubin(V, Fc, it=15, lam=0.5, mu=-0.53):
    """Alisa a malha do marching cubes sem encolher (Taubin): tira a escadinha dos voxels."""
    from scipy.sparse import coo_matrix
    n = len(V)
    e = np.concatenate([Fc[:, [0, 1]], Fc[:, [1, 2]], Fc[:, [2, 0]]])
    e = np.concatenate([e, e[:, ::-1]])
    A = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n)).tocsr()
    A.data[:] = 1.0
    deg = np.asarray(A.sum(1)).ravel()
    deg[deg == 0] = 1
    V = V.astype(np.float64)
    for _ in range(it):
        for f in (lam, mu):
            V = V + f * ((A @ V) / deg[:, None] - V)
    return V


def _volume_cutter(R, mine, bounds, step, sigma, depth=0.0):
    """Solid of the points closer to the painted area than to the rest of the surface (a
    partition of the volume by the painting), smoothed. The interface between two colours
    runs half way between their surfaces, so parts that touch (a hand resting on the leg, a
    braid on the shoulder) separate along the contact by themselves."""
    from scipy.spatial import cKDTree
    from scipy.ndimage import gaussian_filter
    lo, hi = np.asarray(bounds[0], float), np.asarray(bounds[1], float)
    n = np.maximum(np.ceil((hi - lo) / step).astype(int) + 1, 4)
    # surface samples: centre and corners pulled in, so big triangles are covered too
    T = R.T
    samp = np.concatenate([T.mean(1), T[:, 0] * 0.6 + T.mean(1) * 0.4, T[:, 1] * 0.6 + T.mean(1) * 0.4,
                           T[:, 2] * 0.6 + T.mean(1) * 0.4])
    lab = np.tile(mine, 4)
    # distances by the Euclidean distance transform of the surface marked in the grid (fast,
    # linear in the number of cells): one transform for the area, one for the rest
    from scipy.ndimage import distance_transform_edt
    ijk = np.round((samp - lo) / step).astype(int)
    ins = np.all((ijk >= 0) & (ijk < n), axis=1)
    occ_m = np.zeros(n, bool)
    occ_o = np.zeros(n, bool)
    occ_m[tuple(ijk[ins & lab].T)] = True
    occ_o[tuple(ijk[ins & ~lab].T)] = True
    if not occ_o.any():
        occ_o[0, 0, 0] = True
    if not occ_m.any():
        raise ValueError('a área não está dentro da grade')
    dm = distance_transform_edt(~occ_m, sampling=step).ravel()
    do = distance_transform_edt(~occ_o, sampling=step).ravel()
    # perto da divisa, distâncias exatas aos pontos da superfície (não arredondadas para o voxel):
    # a divisa entre as cores sai lisa, sem a escadinha da grade
    band = np.abs(do - dm) < 3.0 * step
    if band.any() and (~lab).any() and lab.any():
        try:
            G = np.stack(np.unravel_index(np.where(band)[0], tuple(n)), -1) * step + lo
            dmx = cKDTree(samp[lab]).query(G, distance_upper_bound=6 * step)[0]
            dox = cKDTree(samp[~lab]).query(G, distance_upper_bound=6 * step)[0]
            ok = np.isfinite(dmx) & np.isfinite(dox)
            bi = np.where(band)[0][ok]
            dm[bi], do[bi] = dmx[ok], dox[ok]
        except Exception:
            pass
    F = (do - dm).reshape(n)
    if depth > 0:
        F = np.minimum(F, (depth - dm).reshape(n))
    if sigma > 0:
        F = gaussian_filter(F, sigma / step)
    F = np.pad(F, 1, constant_values=-1.0)
    try:
        from skimage.measure import marching_cubes
        V, Fc, _, _ = marching_cubes(F, 0.0, spacing=(step, step, step))
        V = _taubin(V, Fc, 15)
        V = V + lo - step
        M = mf.Manifold(mf.Mesh(vert_properties=np.ascontiguousarray(V, np.float32),
                                tri_verts=np.ascontiguousarray(Fc[:, ::-1], np.uint32)))
        if M.status() != mf.Error.NoError or M.volume() <= 0:
            raise ValueError('malha do corte')
        return M
    except Exception:
        from scipy.ndimage import map_coordinates
        o = lo - step

        def f(x, y, z):
            c = np.array([[(x - o[0]) / step], [(y - o[1]) / step], [(z - o[2]) / step]])
            return float(map_coordinates(F, c, order=1, cval=-1.0)[0])
        return mf.Manifold.level_set(f, list(lo - step) + list(hi + step), step)


def no_overlap(piece, parts, tol=0.05):
    """Garantia final de cada corte: a peça e o resto nunca dividem material. Uma parte do resto que
    está inteira dentro da peça (lasca duplicada) sai; uma sobreposição parcial é tirada do resto.
    Devolve (partes, volume tirado)."""
    out, gone = [], 0.0
    try:
        pb = np.array(piece.bounding_box())
    except Exception:
        return list(parts), 0.0
    for q in parts:
        try:
            qb = np.array(q.bounding_box())
            if np.any(qb[3:] < pb[:3]) or np.any(qb[:3] > pb[3:]):
                out.append(q)
                continue
            ov = _vol(E.flat(piece ^ q))
            if ov <= tol:
                out.append(q)
                continue
            vq = _vol(q)
            if ov > 0.5 * vq:
                gone += vq
                continue
            q2 = E.flat(q - piece)
            gone += ov
            out += [x for x in (E.parts(q2, 0.5) or [])]
        except Exception:
            out.append(q)
    return sorted(out, key=lambda q: -_vol(q)), gone


def cut_by_paint(host, R, rid, prm, diag):
    """"Pela pintura": the part is the volume nearest to its painted surface (see
    _volume_cutter). Works for any shape: limbs that touch the body, hair, a face."""
    reg = R.list[rid]
    checks = []
    tris = reg['tris']
    region_pts = R.cen[tris]
    vidx = np.unique(R.f[tris].ravel())
    P = R.v[vidx]
    hb = host.bounding_box()
    ext = P.max(0) - P.min(0)
    margin = max(4.0, 0.35 * float(ext.max()))
    lo = np.maximum(P.min(0) - margin, np.array(hb[:3]) - 1)
    hi = np.minimum(P.max(0) + margin, np.array(hb[3:]) + 1)
    step = float(np.clip(float((hi - lo).max()) / 90.0, 0.3, 0.8))
    sigma = float(prm.get('suavizar') or 0) or max(0.6, 2 * step)
    depth = float(prm.get('espessura') or 0)
    sep = set(prm.get('_aninhar') or ()) - {rid}
    C = prm.get('_cutter')                         # Corte livre: superfície mínima já calculada
    if C is None:
        C = _volume_cutter(R, _enclosed(R, rid, sep), (lo, hi), step, sigma, depth)
    C = E.fill_voids(C)                            # bolha dentro da ferramenta: viraria ilha solta dentro da peça
    a = E.flat(host ^ C)
    comps = E.parts(a, 0.05)
    if not comps:
        return dict(ok=False, checks=[_chk('erro', 'O corte pela pintura não gerou peça: a área é fina demais.')])
    keep, strays = [], []
    for q in comps:
        sc = int((_on_surface(region_pts, tri_array(q)) >= 0).sum())
        (keep if sc > 0.02 * len(region_pts) else strays).append(q)
    if not keep:
        keep = [max(comps, key=lambda q: q.volume())]
        strays = [q for q in comps if q is not keep[0]]
    piece = E.flat(E.union(keep)) if len(keep) > 1 else keep[0]
    body = E.flat(host - C)
    if strays:
        body = E.flat(E.union([body] + strays))
    body_parts = E.parts(body, 0.5)
    hv, pv = _vol(host), _vol(piece)
    if not body_parts and _painted_share(host, R, rid) <= 0.5:
        return dict(ok=False, checks=[_chk('erro', 'O corte levou o modelo inteiro.')])
    keep_rest = bool(prm.get('_livre')) and sum(_vol(b) for b in body_parts) > max(1.0, 1e-4 * hv)
    if pv > 0.6 * hv and not keep_rest:
        # (no Corte livre com "Inverter" a peça é o lado maior; o que sobra, os olhos por exemplo,
        # é uma parte de verdade e não pode sumir: esse caso segue o corte normal)
        if _painted_share(host, R, rid) > 0.5:
            # this part is already all of this colour (an earlier cut left it alone): it is the piece
            checks.append(_chk('ok', 'Esta parte já ficou separada por outro corte: ela inteira é a peça desta cor.'))
            if prm.get('pino', 'nenhum') != 'nenhum':
                checks.append(_chk('aviso', 'Sem pino: esta peça só encosta em outras peças coloridas (cole nelas).'))
            return dict(ok=True, checks=checks, body_parts=[], piece=host, extra=[], axis=reg['normal'],
                        print_T=_print_T_flat(host), planes=[], volume=True)
        return dict(ok=False, checks=[_chk('erro', 'A área pintada é a maior parte do modelo: pinte a outra cor como área e separe ela.')])
    if len(body_parts) > 1:
        checks.append(_chk('aviso', f'O corte deixa o resto do modelo em {len(body_parts)} partes. Todas vão para a exportação.'))
    checks.append(_chk('ok', f'Corte pela pintura: a peça é o volume mais perto da área pintada; as faces de contato '
                             f'seguem a borda, suavizadas em {_fmt(sigma, 1)} mm.'))
    # direction for the exploded view and the print position: from the body to the part
    cb = E.centroid(piece)
    hc = E.centroid(host)
    nrm = reg['normal'] * reg['normal_len'] + (cb - hc) / max(np.linalg.norm(cb - hc), 1e-9) * 0.5
    nrm = nrm / max(np.linalg.norm(nrm), 1e-9)
    # can it be put in place? Each body part it touches must let it slide out in some direction
    # (parts are assembled one after the other, so each contact is checked on its own)
    Tq = tri_array(piece)
    onq = _on_surface(Tq.mean(1), R.T)
    blocked_parts, free_dir = 0, None
    for bp in body_parts:
        tb = tri_array(bp)
        newq = Tq[onq < 0]
        if not len(newq):
            continue
        touch = _on_surface(newq.mean(1), tb, tol=0.05) >= 0
        if touch.sum() < 3:
            continue                                   # this part does not touch the piece
        tn = newq[touch]
        nr_ = -np.cross(tn[:, 1] - tn[:, 0], tn[:, 2] - tn[:, 0]).sum(0)
        cands = [nrm]
        if np.linalg.norm(nr_) > 1e-9:
            cands.insert(0, -nr_ / np.linalg.norm(nr_))
        away = E.centroid(piece) - E.centroid(bp)
        if np.linalg.norm(away) > 1e-9:
            cands.append(away / np.linalg.norm(away))
        cands += [np.array(v, float) for v in ((0, 0, 1), (0, 0, -1), (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0))]
        ok_here = None
        for d in cands:
            hit = 0.0
            for dist in (1.0, 3.0):
                hit = max(hit, _vol(E.flat(piece.translate(list(map(float, d * dist))) ^ bp)))
            if hit < 0.01 * pv + 0.05:
                ok_here = d
                break
        if ok_here is None:
            blocked_parts += 1
        elif free_dir is None or _vol(bp) > 0:
            free_dir = ok_here if free_dir is None else free_dir
    if blocked_parts:
        checks.append(_chk('aviso', 'A peça pode travar ao montar (a face de contato tem rebaixo). Confira na prévia; '
                                    'se travar, divida a pintura em partes ou use "membro".'))
    else:
        if free_dir is not None:
            nrm = free_dir
        checks.append(_chk('ok', 'A peça sai e entra sem travar.'))
    extra = []
    pino = prm.get('pino', 'nenhum')
    if pino in PINOS and pino != 'nenhum':
        r_ = _interface_pin(piece, body_parts, pino, prm, float(prm['folga']), float(prm.get('parede', 1.2)), R, diag)
        checks += r_['checks']
        piece, body_parts = r_['piece'], r_['body_parts']
        extra += r_['extra']
    return dict(ok=not any(x['nivel'] == 'erro' for x in checks), checks=checks, body_parts=body_parts, piece=piece,
                extra=extra, axis=nrm, print_T=_print_T_flat(piece), planes=[], volume=True)


def _interface_pin(piece, body_parts, pino, prm, clr, wall, R, diag):
    """Pin across the contact face between the part and the largest body part it touches:
    that patch of new faces gives the plane; then the same pin as a limb."""
    Tq = tri_array(piece)
    on = _on_surface(Tq.mean(1), R.T)
    newq = Tq[on < 0]
    best = None
    for bp in sorted(body_parts, key=lambda q: -_vol(q)):
        if not len(newq):
            break
        touch = _on_surface(newq.mean(1), tri_array(bp), tol=0.05) >= 0
        if touch.sum() >= 3:
            best = newq[touch]
            break
    if best is None:
        return dict(checks=[_chk('aviso', 'Não achei a face de contato com o corpo para o pino.')], piece=piece,
                    body_parts=body_parts, extra=[])
    t = best
    nr = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    ar = np.linalg.norm(nr, axis=1) / 2
    nn = -(nr.sum(0))                                  # contact faces point out of the part: pin goes in
    nn /= max(np.linalg.norm(nn), 1e-9)
    c = (t.mean(1) * ar[:, None]).sum(0) / ar.sum()
    sd = (t.reshape(-1, 3) - c) @ nn
    hit = lambda xy: np.array([_face_height(piece, c, nn, xy, diag)])
    return _limb_pin(piece, body_parts, pino, prm, clr, wall, c, nn, diag, hf=hit,
                     zsec=float(max(0.02, sd.max() + 0.3)))


def _face_height(M, c, nn, xy, diag):
    """Local height (along nn from c) where M starts, above the point xy of the plane."""
    Fr = _frame(nn)
    xy = np.atleast_2d(xy)[0]
    p0 = c + Fr @ np.array([xy[0], xy[1], -diag])
    hits = M.ray_cast(list(p0), list(c + Fr @ np.array([xy[0], xy[1], diag])))
    if not hits:
        return 0.0
    return float(min(np.dot(np.asarray(h.position) - c, nn) for h in hits))


def _print_T_flat(piece):
    """Print position for a part with curved faces: the face with the most area pointing one
    way goes down (the best of the 6 main directions plus the contact direction)."""
    Tq = tri_array(piece)
    nr = np.cross(Tq[:, 1] - Tq[:, 0], Tq[:, 2] - Tq[:, 0])
    ar = np.linalg.norm(nr, axis=1) / 2
    un = nr / np.maximum(2 * ar[:, None], 1e-12)
    best, bd = -1, None
    for d in np.array([[0, 0, -1], [0, 0, 1], [1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0]], float):
        sc = ar[(un @ d) > 0.97].sum()               # area facing down if d is "down"
        if sc > best:
            best, bd = sc, d
    Fr = _frame(-bd)                                  # -bd becomes +z, so bd faces the bed
    return _inv(_T(Fr, np.zeros(3)))


def cut_plug_auto(host, R, rid, prm, diag):
    """Tampão; se a direção média não serve (algo do modelo na frente, uma mecha de cabelo por cima da
    sobrancelha) e o usuário não inclinou a direção, procura sozinho a direção livre mais perto da
    média, inclinando de 10 em 10 graus até 40."""
    r0 = cut_plug(host, R, rid, prm, diag)
    if r0.get('ok') or float(prm.get('incl_a') or 0) or float(prm.get('incl_b') or 0):
        return r0
    errs = [c for c in r0.get('checks', []) if c['nivel'] == 'erro']
    if not errs or not all(c.get('cod') == 'direcao' for c in errs):
        return r0
    for th in (10, 20, 30, 40):
        for k in range(8):
            ph = math.radians(45 * k)
            p2 = dict(prm, incl_a=th * math.cos(ph), incl_b=th * math.sin(ph))
            try:
                r = cut_plug(host, R, rid, p2, diag)
            except Exception:
                continue
            if r.get('ok'):
                r['checks'] = [_chk('ok', f'Direção de encaixe inclinada {th}° sozinha: na direção média havia parte do modelo na '
                                          'frente da área (uma mecha de cabelo, por exemplo).')] + \
                    [c for c in r.get('checks', [])]
                r['incl'] = (p2['incl_a'], p2['incl_b'])
                return r
    return r0


def _auto_type(R, rid, prm):
    """Automatic choice: a plug when one straight direction reaches the whole area (an eye, a
    badge, a button); otherwise the cut by the painting, which works for any shape."""
    reg = R.list[rid]
    tris = reg['tris']
    n = reg['normal']
    back = R.area[tris][(R.nrm[tris] @ n) < 0.05].sum() / max(reg['area'], 1e-9)
    # relevo raso (sobrancelha, olho, botão: até 4 mm de fundo na direção de encaixe) tem as paredes
    # laterais de lado; elas saem inteiras com a peça, então um pouco de área de lado não impede o
    # tampão. Área funda (o topo inteiro de um modelo) segue a regra de sempre.
    v = np.unique(R.f[tris].ravel())
    raso = float(np.ptp(R.v[v] @ n)) <= 4.0
    # o terceiro valor diz se o tampão veio só da regra do relevo: aí ele só fica se sair sem nenhum aviso
    if reg['normal_len'] > 0.6 and back <= 0.02:
        return 'tampao', 'Automático: tampão embutido (uma direção alcança a área toda).', False
    if reg['normal_len'] > 0.6 and raso and back <= 0.10:
        return 'tampao', 'Automático: tampão embutido (uma direção alcança a área toda).', True
    # relevo pintado com as paredes (o balde pega o topo e os lados da sobrancelha): as paredes de lados
    # opostos se anulam na média e a área parece "dar a volta". A direção vem só do topo do relevo.
    top = (R.nrm[tris] @ n) > 0.5
    if top.any():
        nt = (R.nrm[tris][top] * R.area[tris][top, None]).sum(0)
        ntl = float(np.linalg.norm(nt)) / max(float(R.area[tris][top].sum()), 1e-9)
        if ntl > 0.8:
            n2 = nt / np.linalg.norm(nt)
            # as paredes do relevo ficam fora do corpo (saem com a peça): só conta o que fica na altura da
            # pele, onde o encaixe entra no corpo
            hc = R.cen[tris] @ n2
            base = hc <= hc.min() + 0.4
            back2 = R.area[tris][((R.nrm[tris] @ n2) < -0.05) & base].sum() / max(reg['area'], 1e-9)
            if float(np.ptp(R.v[v] @ n2)) <= 4.0 and back2 <= 0.10:
                return 'tampao', 'Automático: tampão embutido (relevo pintado com as paredes: a direção vem do topo dele).', True
    return 'pintura', 'Automático: corte pela pintura (a área dá a volta ou encosta em outras partes).', False


def _painted_share(M, R, rid):
    """Share of the original surface of M that is painted with area rid."""
    Tq = tri_array(M)
    on = _on_surface(Tq.mean(1), R.T)
    ar = np.linalg.norm(np.cross(Tq[:, 1] - Tq[:, 0], Tq[:, 2] - Tq[:, 0]), axis=1) / 2
    surf = ar[on >= 0].sum()
    return ar[(on >= 0) & (R.of[np.maximum(on, 0)] == rid)].sum() / surf if surf > 0 else 0.0


def cut_limb(host, R, rid, prm, diag, body_others=None):
    """Membro: cut off by one plane per border of the painting, or (corte = 'borda') by a
    smooth surface that follows the painted border."""
    reg = R.list[rid]
    checks = []
    clr = float(prm['folga'])
    wall = float(prm.get('parede', 1.2))
    loops = R.loops(rid)
    loops = [L for L in loops if len(L) >= 3]
    loops.sort(key=lambda L: -len(L))
    tris = reg['tris']
    region_pts = R.cen[tris]
    planes, surfs = [], []
    for L in loops:
        P = R.v[L]
        per = np.linalg.norm(np.diff(np.vstack([P, P[:1]]), axis=0), axis=1).sum()
        if per < 2.0:
            continue
        c, nn, dev = _plane_fit(P)
        if np.dot(reg['centro'] - c, nn) < 0:
            nn = -nn
        planes.append((c, nn, dev))
        surfs.append(border_surface(P, c, nn, diag) if prm.get('corte') == 'borda' else None)
    if not planes:
        return dict(ok=False, checks=[_chk('erro', 'Esta área não tem borda para cortar (pinte só o membro, não o modelo inteiro).')])
    piece = host
    others = []
    for (c, nn, dev), sf in zip(planes, surfs):
        if sf is None:
            a, b = piece.split_by_plane(list(map(float, nn)), float(np.dot(nn, c)))
        else:
            a, b = E.flat(piece ^ sf[0]), E.flat(piece - sf[0])
            dev = sf[2]['desvio']
        comps = E.parts(E.flat(a), 0.02)
        if not comps:
            return dict(ok=False, checks=[_chk('erro', 'O plano de corte não pegou a área pintada.')])
        score = []
        for q in comps:
            hit = _on_surface(region_pts, tri_array(q))
            score.append(int((hit >= 0).sum()))
        best = int(np.argmax(score))
        keep = [q for k, q in enumerate(comps) if score[k] > 0.02 * len(region_pts) or k == best]
        others += [q for k, q in enumerate(comps) if q not in keep]
        # the other side may still hold painted surface (a second border far from this one:
        # its cut runs on through the area): that part stays with the piece
        for q in E.parts(E.flat(b), 0.02):
            if _painted_share(q, R, rid) > 0.5:          # mostly painted: part of the limb
                keep.append(q)
            else:
                others.append(q)
        piece = E.flat(E.union(keep)) if len(keep) > 1 else keep[0]
        if sf is None and dev > 1.5:
            checks.append(_chk('aviso', f'A borda pintada fica até {_fmt(dev)} mm fora do plano de corte: pinte a borda mais reta '
                                        'ou use o corte "seguir a borda pintada".'))
        if sf is not None and sf[2]['curvatura'] > 0.6:
            checks.append(_chk('aviso', f'Face do corte curva ({_fmt(sf[2]["curvatura"])} mm de altura): a parte não fica plana '
                                        'na mesa; imprima com suporte ou use o corte por plano.'))
    piece = E.flat(piece)
    body_parts = E.parts(E.flat(E.union(others)), 0.5) if others else []
    if not body_parts:
        return dict(ok=False, checks=[_chk('erro', 'O corte levou o modelo inteiro: pinte só o membro.')])
    # the planes must take the painted limb, not half of the model
    hv, pv = _vol(host), _vol(piece)
    Tp = tri_array(piece)
    on = _on_surface(Tp.mean(1), R.T)
    ar = np.linalg.norm(np.cross(Tp[:, 1] - Tp[:, 0], Tp[:, 2] - Tp[:, 0]), axis=1) / 2
    surf = ar[on >= 0].sum()
    mine = ar[(on >= 0) & (R.of[np.maximum(on, 0)] == rid)].sum()
    cover = mine / surf if surf > 0 else 0.0
    if pv > 0.5 * hv:
        return dict(ok=False, checks=checks + [_chk('erro', 'O plano de corte levaria a maior parte do modelo: esta área não contorna um membro. '
                                                            'Use "tampão" ou pinte o membro inteiro a partir de onde quer cortar.')])
    if cover < 0.3:
        return dict(ok=False, checks=checks + [_chk('erro', f'O corte leva bem mais do que a área pintada (só {round(cover * 100)}% da parte '
                                                            'cortada está pintada): pinte o membro inteiro a partir de onde quer cortar.')])
    if len(body_parts) > 1:
        checks.append(_chk('aviso', f'O corte deixa o resto do modelo em {len(body_parts)} partes (ex.: a mão depois da manga). '
                                    'Todas vão para a exportação.'))
    pb = piece.bounding_box()
    if min(pb[3] - pb[0], pb[4] - pb[1], pb[5] - pb[2]) < 1.5:
        checks.append(_chk('aviso', 'A parte cortada tem menos de 1,5 mm de espessura: confira se a pintura pegou o membro inteiro.'))
    if any(sf is not None for sf in surfs):
        checks.append(_chk('ok', f'Corte pela borda pintada ({len(planes)} borda(s)), superfície lisa: a borda fica até '
                                 f'{_fmt(max(sf[2]["desvio"] for sf in surfs if sf), 2)} mm do corte.'))
    else:
        checks.append(_chk('ok', f'Corte por {len(planes)} plano(s) que segue(m) a borda pintada (desvio máximo '
                                 f'{_fmt(max(p[2] for p in planes))} mm).'))
    extra = []
    pino = prm.get('pino', 'nenhum')
    if pino in PINOS and pino != 'nenhum':
        for (c, nn, dev), sf in zip(planes, surfs):
            r_ = _limb_pin(piece, body_parts, pino, prm, clr, wall, c, nn, diag,
                           hf=None if sf is None else sf[1], zsec=0.02 if sf is None else sf[2]['zsec'])
            checks += r_['checks']
            piece, body_parts = r_['piece'], r_['body_parts']
            extra += r_['extra']
    c0, n0, _ = planes[0]
    Tw = _T(_frame(n0), c0)
    return dict(ok=not any(x['nivel'] == 'erro' for x in checks), checks=checks, body_parts=body_parts,
                piece=piece, extra=extra, axis=n0, print_T=_inv(Tw),
                planes=[(c, nn, 0.0 if sf is None else sf[2]['tol']) for (c, nn, _d), sf in zip(planes, surfs)])


def _limb_pin(piece, body_parts, pino, prm, clr, wall, c, nn, diag, hf=None, zsec=0.02):
    checks, extra = [], []
    Fr = _frame(nn)
    Tw = _T(Fr, c)
    loc_piece = E.X(piece, _inv(Tw))
    sec = loc_piece.slice(zsec)
    if sec.is_empty():
        return dict(checks=[_chk('aviso', 'Não achei a face do corte para o pino.')], piece=piece, body_parts=body_parts, extra=extra)
    comps = sec.decompose()
    sec = min(comps, key=lambda q: np.hypot((q.bounds()[0] + q.bounds()[2]) / 2, (q.bounds()[1] + q.bounds()[3]) / 2)) if comps else sec
    inr, pole = _inradius(sec)
    want = float(prm.get('pino_mm') or 0) / 2.0
    h = want or min(3.0, max(0.8, 0.3 * inr))
    room = inr - clr * S2 - 1.0
    if room < 0.7:
        return dict(checks=[_chk('aviso', 'A seção do corte é estreita demais para o pino: saiu sem pino.')], piece=piece,
                    body_parts=body_parts, extra=extra)
    h = min(h, room)
    if hf is not None:                     # curved cut: the pin starts where the face is, at the pole
        c = c + nn * float(hf(np.array([[pole[0], pole[1]]]))[0])
        Tw = _T(Fr, c)
    pt = c + Fr @ np.array([pole[0], pole[1], 0.0])
    t_piece = _depth_along(piece, pt + nn * 0.01, nn, diag)
    # the body part on the other side of this plane
    k_body = None
    for k, bp in enumerate(body_parts):
        if E.contains_point(bp, pt - nn * 0.3, 0.1):
            k_body = k
            break
    if k_body is None:
        return dict(checks=[_chk('aviso', 'Não achei a parte do outro lado do corte para o pino.')], piece=piece,
                    body_parts=body_parts, extra=extra)
    bp = body_parts[k_body]
    t_body = _depth_along(bp, pt - nn * 0.01, -nn, diag)
    xy = (pole[0], pole[1])
    W = lambda m: E.X(m, Tw)
    if pino == 'corpo':
        f_ = _fit(h, 5, t_piece - clr * S2 - wall)
        if f_ is None:
            return dict(checks=[_chk('aviso', 'O membro é curto demais para o pino: saiu sem pino.')], piece=piece,
                        body_parts=body_parts, extra=extra)
        h, (L,) = f_
        bp = E.flat(bp + W(_pin(h, -0.8, L, xy)))
        piece = E.flat(piece - W(_hole(h, -0.05, L, clr, xy)))
        checks.append(_chk('ok', f'Pino no corpo: {_fmt(2 * h)} mm de largura, {_fmt(L)} mm dentro da peça.'))
    elif pino == 'trava':
        f_ = _fit(max(h, 1.4), 5, t_piece - clr * S2 - wall)
        if f_ is None or f_[0] < 1.4 or room < 1.4:
            return dict(checks=[_chk('aviso', 'A seção é pequena demais para a trava (pino de 2,8 mm ou mais): saiu sem pino. '
                                              'Use o pino no corpo.')], piece=piece, body_parts=body_parts, extra=extra)
        h, (L,) = f_
        pin, hole = _snap(h, -0.8, L, clr, xy)
        bp = E.flat(bp + W(pin))
        piece = E.flat(piece - W(hole))
        checks.append(_chk('ok', f'Trava de pressão: pino partido com garra ({_fmt(2 * h)} mm), {_fmt(L)} mm dentro da peça.'))
    elif pino == 'peca':
        f_ = _fit(h, 5, t_body - clr * S2 - wall)
        if f_ is None:
            return dict(checks=[_chk('aviso', 'Pouco material no corpo para o pino: saiu sem pino.')], piece=piece,
                        body_parts=body_parts, extra=extra)
        h, (L,) = f_
        piece = E.flat(piece + W(_pin(h, -L, 0.8, xy, tip_top=False, tip_bottom=True)))
        bp = E.flat(bp - W(_hole(h, -L, 0.05, clr, xy, tip_top=False, tip_bottom=True)))
        checks.append(_chk('ok', f'Pino no membro: {_fmt(2 * h)} mm de largura, {_fmt(L)} mm dentro do corpo.'))
    else:
        f_ = _fit(h, 3, t_piece - clr * S2 - wall, t_body - clr * S2 - wall)
        if f_ is None:
            return dict(checks=[_chk('aviso', 'Não há material para a cavilha dos dois lados: saiu sem pino.')], piece=piece,
                        body_parts=body_parts, extra=extra)
        h, (La, Lb) = f_
        z0, z1 = -Lb + clr * S2, La - clr * S2
        hole = W(_hole(h, z0, z1, clr, xy, True, True))
        bp = E.flat(bp - hole)
        piece = E.flat(piece - hole)
        d_loc = _pin(h, z0, z1, xy, True, True)
        extra.append(dict(mesh=W(d_loc), axis=nn))
        checks.append(_chk('ok', f'Cavilha solta de {_fmt(2 * h)} × {_fmt(z1 - z0)} mm.'))
    body_parts = list(body_parts)
    body_parts[k_body] = bp
    return dict(checks=checks, piece=piece, body_parts=body_parts, extra=extra)


# ----------------------------------------------------------------------------- all cuts
def _host_of(pieces, pts):
    best, score = -1, 0
    for k, p in enumerate(pieces):
        s = int((_on_surface(pts, p['T']) >= 0).sum())
        if s > score:
            best, score = k, s
    return best, score


def run(S, paint, configs, progress=None):
    """configs: list of dict(id=region id, separar=True, tipo, profundidade, folga, suavizar,
    pino, pino_mm, incl_a, incl_b). Cuts in order of area (largest first), so an area painted
    inside another (a pupil inside an eye) is cut from the part that holds it."""
    t0 = time.time()
    R = Regions(S, paint)
    bb = S.bounding_box()
    diag = float(np.linalg.norm(np.array(bb[3:]) - np.array(bb[:3]))) + 5.0
    T0 = R.T
    pieces = [dict(mesh=S, base=1, nome='Corpo', tipo='corpo', rid=None, axis=None, print_T=None)]
    pieces[0]['T'] = T0
    sel = []
    for c in configs:
        if not c.get('separar', True):
            continue
        rid = int(c['id'])
        if 0 <= rid < len(R.list):
            prm = dict(DEFAULTS)
            prm.update({k: v for k, v in c.items() if v is not None})
            sel.append((rid, prm))
    sel.sort(key=lambda x: -R.list[x[0]]['area'])
    ids = {rid for rid, _ in sel}
    for _, prm in sel:
        prm['_aninhar'] = ids
    results = {}
    extras = []
    for n_, (rid, prm) in enumerate(sel):
        if progress:
            progress(f'cortando área {n_ + 1} de {len(sel)}')
        reg = R.list[rid]
        hk, sc = _host_of(pieces, R.cen[reg['tris']])
        if hk < 0 or sc < 0.3 * len(reg['tris']):
            results[rid] = dict(ok=False, checks=[_chk('erro', 'A área foi tomada por outro corte (pinte de novo ou desmarque a outra).')])
            continue
        host = pieces[hk]
        auto_msg, relevo = None, False
        if prm['tipo'] == 'auto':
            prm['tipo'], auto_msg, relevo = _auto_type(R, rid, prm)
        try:
            if prm['tipo'] == 'membro':
                r = cut_limb(host['mesh'], R, rid, prm, diag)
            elif prm['tipo'] == 'pintura':
                r = cut_by_paint(host['mesh'], R, rid, prm, diag)
            else:
                r = cut_plug_auto(host['mesh'], R, rid, prm, diag)
                avisos = any(c.get('nivel') != 'ok' for c in r.get('checks', []))
                if auto_msg and (not r.get('ok') or (relevo and avisos)):
                    # automático: o tampão não coube aqui (ou, num relevo, saiu com aviso); fica o corte pela
                    # pintura, que serve para qualquer forma, a não ser que ela saia pior
                    prm2 = dict(prm, tipo='pintura')
                    r2 = cut_by_paint(host['mesh'], R, rid, prm2, diag)
                    av2 = any(c.get('nivel') != 'ok' for c in r2.get('checks', []))
                    if not r.get('ok') or (r2.get('ok') and not av2):
                        prm['tipo'], r = 'pintura', r2
                        auto_msg = 'Automático: corte pela pintura (o tampão não coube nesta área).'
        except Exception as ex:                       # a failed cut never stops the others
            r = dict(ok=False, checks=[_chk('erro', f'O corte falhou: {ex}')])
        if auto_msg:
            r.setdefault('checks', []).insert(0, _chk('ok', auto_msg))
        r['tipo'] = prm['tipo']
        results[rid] = r
        if not r.get('ok'):
            continue
        new_host = r['body_parts'] if prm['tipo'] in ('membro', 'pintura') else E.parts(r['body'], 0.5)
        new_host, _ov = no_overlap(r['piece'], new_host)
        if _ov > 0.05:
            r.setdefault('checks', []).append(_chk('ok', f'Material repetido entre a peça e o resto ({_fmt(_ov, 1)} mm³) foi tirado do resto: '
                                                         'as peças não se sobrepõem.'))
        repl = []
        for k, m in enumerate(new_host):
            repl.append(dict(mesh=m, base=host['base'], nome=host['nome'] + (f' {k + 1}' if len(new_host) > 1 else ''),
                             tipo=host['tipo'], rid=host['rid'], axis=host['axis'], print_T=host['print_T'],
                             T=tri_array(m)))
        # nome da peça (1.58): o que o usuário deu à área, único entre as peças; senão o padrão
        nm_ = ' '.join(str(prm.get('nome') or '').split())[:60]
        usados_ = {p_['nome'] for p_ in pieces}
        if not nm_ or nm_ == 'Corpo':
            nm_ = f"Cor {reg['cor']} · área {rid + 1}"
        elif nm_ in usados_:
            k_ = 2
            while f'{nm_} ({k_})' in usados_:
                k_ += 1
            nm_ = f'{nm_} ({k_})'
        part = dict(mesh=r['piece'], base=reg['cor'], nome=nm_, tipo=prm['tipo'],
                    rid=rid, axis=r['axis'], print_T=r['print_T'], T=tri_array(r['piece']))
        pieces = pieces[:hk] + repl + pieces[hk + 1:] + [part]
        for e in r.get('extra', []):
            extras.append(dict(mesh=e['mesh'], base=1, nome=f"Cavilha · área {rid + 1}", tipo='cavilha',
                               rid=rid, axis=e['axis'], T=tri_array(e['mesh'])))
        # o resultado guarda só os avisos e os planos: a peça e o resto já estão em `pieces` (guardar o corpo
        # inteiro em cada resultado dobrava a memória num projeto com várias áreas)
        for k_ in ('body', 'body_parts', 'piece', 'extra'):
            r.pop(k_, None)
    pieces += extras
    # colours: triangles on the original surface keep their paint; a separated area is the
    # colour of its own part and the base colour of any other part; new faces = base colour
    separated = {rid for rid, r in results.items() if r.get('ok')}
    for p in pieces:
        T = p['T']
        on = _on_surface(T.mean(1), T0)
        col = np.full(len(T), p['base'], np.uint8)
        hit = on >= 0
        src = on[hit]
        c_ = np.asarray(paint, np.uint8)[src].copy()
        rof = R.of[src]
        sep = np.isin(rof, list(separated)) if separated else np.zeros(len(src), bool)
        c_[sep] = np.where(rof[sep] == (p['rid'] if p['rid'] is not None else -2), c_[sep], p['base'])
        if p['tipo'] == 'cavilha':
            c_[:] = p['base']
        col[hit] = c_
        p['paint'] = col
    # mesh kept identical outside the cuts
    k0 = set(_tri_keys(T0))
    k1 = set()
    for p in pieces:
        k1.update(_tri_keys(p['T']))
    kept = len(k0 & k1)
    changed = len(k0) - kept
    zones = [R.list[rid]['centro'] for rid in separated]
    keep = dict(original=len(k0), identicos=kept, mudaram=changed,
                pct=round(100.0 * kept / max(len(k0), 1), 2))
    if changed and separated:
        # where the changed triangles are: must be near a cut
        from scipy.spatial import cKDTree
        lost = np.array([k not in k1 for k in _tri_keys(T0)])
        near_pts = np.concatenate([R.v[np.unique(R.f[R.list[rid]['tris']].ravel())] for rid in separated])
        TL = T0[lost]
        d, _ = cKDTree(near_pts).query(TL.reshape(-1, 3))
        d = d.reshape(-1, 3).min(1)                             # nearest corner of each triangle
        for rid in separated:
            for c_, nn, tol in results[rid].get('planes', []):
                sd = (TL - c_) @ nn
                cross = (sd.min(1) <= 0.01 + tol) & (sd.max(1) >= -0.01 - tol)
                d = np.where(cross, 0.0, np.minimum(d, np.abs(sd).min(1)))   # on a cutting plane
        keep['longe_mm'] = round(float(d.max()), 2) if len(d) else 0.0
    if sum(1 for p in pieces if p.get('tipo') == 'corpo') > 1:
        # flexi que já veio articulado: as cascas que se encaixam continuam uma peça só (freecut._reagrupar_cascas)
        import freecut as _FC
        pieces = _FC._reagrupar_cascas(dict(pieces=pieces), S)['pieces']
    return dict(R=R, pieces=pieces, results=results, mesh=keep, segundos=round(time.time() - t0, 1), zones=zones)


def summary(out):
    """JSON-safe summary for the interface."""
    R = out['R']
    regs = []
    for rid, r in out['results'].items():
        ch = r.get('checks', [])
        luz = 'erro' if any(c['nivel'] == 'erro' for c in ch) else 'aviso' if any(c['nivel'] == 'aviso' for c in ch) else 'ok'
        regs.append(dict(id=rid, ok=bool(r.get('ok')), luz=luz, checks=ch, tipo=r.get('tipo')))
    parts = []
    for i, p in enumerate(out['pieces']):
        bb = p['mesh'].bounding_box()
        # peça do corte pela pele: o eixo é a direção de encaixe (a vista explodida afasta a peça por ele)
        ax = p.get('axis') if p.get('axis') is not None else p.get('_dir')
        parts.append(dict(i=i, nome=p['nome'], tipo=p['tipo'], cor=int(p['base']), rid=p['rid'], livre=p.get('livre'),
                          eixo=None if ax is None else [round(float(x), 4) for x in ax],
                          triangulos=int(len(p['T'])), volume=round(_vol(p['mesh']), 1),
                          tamanho=[round(bb[3] - bb[0], 1), round(bb[4] - bb[1], 1), round(bb[5] - bb[2], 1)]))
    return dict(regioes=regs, partes=parts, malha=out['mesh'], segundos=out['segundos'])


# ----------------------------------------------------------------------------- export
def _code(c):
    c = int(c)
    if c <= 1:
        return '4'
    if c == 2:
        return '8'
    return f'{c - 3:X}C'


def _hexc(s):
    s = str(s or '#cfc8bc').strip()
    return s if s.startswith('#') else '#' + s


def _unique_colours(palette, n):
    """Filament colours, all different: Bambu Studio and OrcaSlicer number the filaments of a
    3MF by its distinct colours, so two equal colours would merge into one filament."""
    out, seen = [], set()
    for i in range(n):
        h = _hexc(palette[i] if i < len(palette) else '#cfc8bc').upper()[:7]
        r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
        while (r, g, b) in seen:
            b = (b + 1) % 256
        seen.add((r, g, b))
        out.append(f'#{r:02X}{g:02X}{b:02X}')
    return out


def write_3mf_objects(objs, palette, title='partes'):
    """One 3MF object per part (the slicer arranges and prints them separately).
    Filament per object: each object points (pid) at the colour of its filament, the standard
    3MF way that Bambu Studio and OrcaSlicer turn into the object's filament; PrusaSlicer reads
    the same from Metadata/Slic3r_PE_model.config. Only triangles of another colour carry a
    paint code, so a one colour part has no painting at all (lighter, cleaner file).
    objs: (name, triangles, colours[, base filament])."""
    ncol = max([len(palette), 1] + [int(np.max(o[2])) if len(o[2]) else 1 for o in objs])
    colours = _unique_colours(palette, ncol)
    out = io.StringIO()
    out.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    out.write('<model unit="millimeter" xml:lang="en-US" '
              'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
              'xmlns:m="http://schemas.microsoft.com/3dmanufacturing/material/2015/02" '
              'xmlns:slic3rpe="http://schemas.slic3r.org/3mf/2017/06">\n')
    out.write(' <metadata name="Application">EFC3D</metadata>\n')
    out.write(f' <metadata name="Title">{_xml(title)}</metadata>\n')
    out.write(' <metadata name="slic3rpe:MmPaintingVersion">1</metadata>\n <resources>\n')
    for i, c in enumerate(colours):                    # filament i+1 = colour group 1000+i
        out.write(f'  <m:colorgroup id="{1000 + i}"><m:color color="{c}FF"/></m:colorgroup>\n')
    ntri = 0
    cfg = ['<?xml version="1.0" encoding="UTF-8"?>', '<config>']
    for k, o in enumerate(objs):
        name, T, C = o[0], o[1], np.asarray(o[2], np.uint8)
        base = int(o[3]) if len(o) > 3 and o[3] else (int(np.bincount(C).argmax()) if len(C) else 1)
        base = max(1, base)
        v, inv = np.unique(np.round(T.reshape(-1, 3), 5), axis=0, return_inverse=True)
        F = inv.reshape(-1, 3)
        out.write(f'  <object id="{k + 1}" type="model" name="{_xml(name)}" pid="{1000 + base - 1}" pindex="0">\n'
                  '   <mesh>\n    <vertices>\n')
        out.write(''.join(f'     <vertex x="{x:.5f}" y="{y:.5f}" z="{z:.5f}"/>\n' for x, y, z in v))
        out.write('    </vertices>\n    <triangles>\n')
        lines = []
        for (a, b, c), col in zip(F, C):
            if int(col) != base:
                cc = _code(max(1, int(col)))
                lines.append(f'     <triangle v1="{a}" v2="{b}" v3="{c}" paint_color="{cc}" slic3rpe:mmu_segmentation="{cc}"/>\n')
            else:
                lines.append(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>\n')
        out.write(''.join(lines))
        out.write('    </triangles>\n   </mesh>\n  </object>\n')
        cfg += [f' <object id="{k + 1}" instances_count="1">',
                f'  <metadata type="object" key="name" value="{_xml(name)}"/>',
                f'  <metadata type="object" key="extruder" value="{base}"/>',
                f'  <volume firstid="0" lastid="{len(F) - 1}">',
                f'   <metadata type="volume" key="name" value="{_xml(name)}"/>',
                '  </volume>', ' </object>']
        ntri += len(F)
    cfg.append('</config>')
    out.write(' </resources>\n <build>\n')
    out.write(''.join(f'  <item objectid="{k + 1}"/>\n' for k in range(len(objs))))
    out.write(' </build>\n</model>\n')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml',
                   '<?xml version="1.0" encoding="UTF-8"?>\n'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
                   '<Default Extension="config" ContentType="text/plain"/>'
                   '</Types>')
        z.writestr('_rels/.rels',
                   '<?xml version="1.0" encoding="UTF-8"?>\n'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
                   'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr('3D/3dmodel.model', out.getvalue())
        z.writestr('Metadata/project_settings.config', json.dumps({'filament_colour': colours}, indent=1))
        z.writestr('Metadata/Slic3r_PE.config', '; extruder_colour = ' + ';'.join(colours) + '\n')
        z.writestr('Metadata/Slic3r_PE_model.config', '\n'.join(cfg) + '\n')
    return buf.getvalue(), ntri


def _xml(t):
    return (str(t).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;'))


def check_3mf_objects(data, n_obj, n_tri):
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        root = ET.fromstring(z.read('3D/3dmodel.model'))
    ns = '{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}'
    return (len(root.findall(f'.//{ns}object')) == n_obj and len(root.findall(f'.//{ns}triangle')) == n_tri)


def _apply(T, M):
    return T @ M[:3, :3].T + M[:3, 3]


def print_layout(pieces):
    """Each part in its print position: the body as it is, plugs and limbs with the flat face
    down, dowels lying down; parts in rows next to the body."""
    out = []
    body_bb = None
    bodies = [p for p in pieces if p['tipo'] == 'corpo']
    # the largest body part stays where it is; other body parts (the legs after a belt, a
    # hand after a sleeve) go in the rows with the other parts, so nothing overlaps
    anchor = max(bodies, key=lambda p: len(p['T'])) if bodies else None
    for p in pieces:
        if p is anchor:
            T = p['T'].copy()
            T[:, :, 2] -= T[:, :, 2].min()
            out.append([p, T])
            lo, hi = T.reshape(-1, 3).min(0), T.reshape(-1, 3).max(0)
            body_bb = (lo, hi) if body_bb is None else (np.minimum(body_bb[0], lo), np.maximum(body_bb[1], hi))
    if body_bb is None:
        body_bb = (np.zeros(3), np.zeros(3))
    x0 = body_bb[1][0] + 8.0
    x, y, row_h = x0, body_bb[0][1], 0.0
    width = max(60.0, body_bb[1][1] - body_bb[0][1])
    rest = [p for p in pieces if p is not anchor]
    for p in rest:
        M = p.get('lay') if p['tipo'] == 'cavilha' else p.get('print_T')
        T = _apply(p['T'] if p['tipo'] != 'cavilha' else _cavilha_local(p), M if M is not None else np.eye(4))
        lo, hi = T.reshape(-1, 3).min(0), T.reshape(-1, 3).max(0)
        sx, sy = hi[0] - lo[0], hi[1] - lo[1]
        if y + sy > body_bb[0][1] + width and y > body_bb[0][1]:
            y = body_bb[0][1]
            x += row_h + 5.0
            row_h = 0.0
        T = T - np.array([lo[0] - x, lo[1] - y, lo[2]])
        y += sy + 5.0
        row_h = max(row_h, sx)
        out.append([p, T])
    return out


def _cavilha_local(p):
    return p['T_local']


def assign_joints(out, joints, S, clearance):
    """Which part each joint sits in (by its centre), and joints that also cut into another
    part (a pocket, a plug, a limb). Returns ({part index: [joint indices]}, warnings)."""
    import editor as ED
    groups, warns = {}, []
    parts = out['pieces']
    for k, jp in enumerate(joints):
        pos = np.asarray(jp.get('pos', [0, 0, 0]), np.float64)
        host = None
        for pi, p in enumerate(parts):
            if p['tipo'] != 'cavilha' and E.contains_point(p['mesh'], pos, 0.3):
                host = pi
                break
        if host is None:                                  # centre in a gap: the nearest part
            best = None
            for pi, p in enumerate(parts):
                if p['tipo'] == 'cavilha':
                    continue
                bb = p['mesh'].bounding_box()
                d = np.linalg.norm(np.maximum(0, np.maximum(np.array(bb[:3]) - pos, pos - np.array(bb[3:]))))
                if best is None or d < best[0]:
                    best = (d, pi)
            host = best[1] if best else 0
            warns.append(f'J{k + 1}: o centro da junta não está dentro de nenhuma parte; foi para "{parts[host]["nome"]}".')
        groups.setdefault(host, []).append(k)
        try:
            Cw, _ = ED.cutter_world(S, jp, clearance)
            for pi, p in enumerate(parts):
                if pi == host:
                    continue
                v = _vol(E.flat(Cw ^ p['mesh']))
                if v > 0.5:
                    warns.append(f'J{k + 1} encosta em "{p["nome"]}" ({v:.0f} mm³): a junta corta um encaixe ou outra peça. '
                                 'Mova a junta ou a área.')
        except Exception:
            pass
    return groups, warns


def main_body(out):
    """The largest body part: the one the joints go on when both are exported."""
    bodies = [p for p in out['pieces'] if p['tipo'] == 'corpo']
    return max(bodies, key=lambda p: _vol(p['mesh'])) if bodies else None


def write_plates(items, folder, name, palette, printer):
    """items: dict(nome, T in print position, paint, base). One 3MF per plate of the printer.
    Returns (files, plates summary, warnings)."""
    import printers as PR
    plates, warns = PR.pack(items, printer)
    d = os.path.join(folder, 'placas')
    os.makedirs(d, exist_ok=True)
    files, info = [], []
    for k, pl in enumerate(plates):
        objs = [(it['nome'], T, it['paint'], it.get('base', 1)) for it, T in pl]
        data, _ = write_3mf_objects(objs, palette, f'{name} placa {k + 1}')
        fn = f'{name}_placa_{k + 1}.3mf'
        with open(os.path.join(d, fn), 'wb') as f:
            f.write(data)
        files.append('placas/' + fn)
        info.append(dict(placa=k + 1, arquivo='placas/' + fn, itens=[it['nome'] for it, _ in pl]))
    return files, info, warns, plates


def rigid(A, B):
    """4x4 rigid transform taking the points A to B (same order), Kabsch."""
    A = np.asarray(A, np.float64).reshape(-1, 3)
    B = np.asarray(B, np.float64).reshape(-1, 3)
    if len(A) > 6000:
        idx = np.linspace(0, len(A) - 1, 6000).astype(int)
        A, B = A[idx], B[idx]
    ca, cb = A.mean(0), B.mean(0)
    H = (A - ca).T @ (B - cb)
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    Rm = Vt.T @ np.diag([1, 1, d]) @ U.T
    M = np.eye(4)
    M[:3, :3] = Rm
    M[:3, 3] = cb - Rm @ ca
    return M


def export(out, folder, name, palette, flexi=None, stl_sub='pecas', printer=None):
    """Write the separated parts. flexi = (triangles, paint) per piece of the articulated body
    when joints were exported too: the main body is replaced by it in the print file."""
    os.makedirs(folder, exist_ok=True)
    stl_dir = os.path.join(folder, stl_sub)
    os.makedirs(stl_dir, exist_ok=True)
    pieces = [dict(p, src=k) for k, p in enumerate(out['pieces'])]
    if flexi is not None:
        # articulated versions replace their parts: flexi = {part index: [(triangles, paint)]}
        if not isinstance(flexi, dict):
            flexi = {out['pieces'].index(main_body(out)): flexi}
        new = []
        for k, p in enumerate(pieces):
            if k in flexi:
                fl = flexi[k]
                new.append(dict(tipo='corpo' if p['tipo'] == 'corpo' else p['tipo'], nome=p['nome'] + ' articulado'
                                if p['tipo'] != 'corpo' else 'Corpo articulado' + (f' {k + 1}' if len(flexi) > 1 else ''),
                                base=p.get('base', 1), rid=p.get('rid'), flexi=True, axis=p.get('axis'),
                                print_T=None, src=k,   # joints print upright: keep the model's orientation
                                T=np.concatenate([t for t, _ in fl]),
                                paint=np.concatenate([np.asarray(c, np.uint8) for _, c in fl])))
            else:
                new.append(p)
        pieces = new
    pieces = [p for p in pieces if len(p['T']) >= 4]   # peça vazia (um corte que não sobrou nada) não vira arquivo
    # dowels: back to their own frame (built along the pin axis), then laid down
    for p in pieces:
        if p['tipo'] == 'cavilha':
            c = p['T'].reshape(-1, 3)
            Tw = _T(_frame(p['axis']), c.mean(0))
            p['T_local'] = _apply(p['T'], _inv(Tw))
            p['lay'] = _lay_dowel()
    impressao = _orient_all(pieces)
    lay = print_layout(pieces)
    malha = []
    for it in lay:                                  # a malha de cada STL sai fechada e sem aresta com 3+ faces
        it[1], keep, mk = _weld_safe(it[1])
        if keep is not None:                        # triângulos colapsados na posição de impressão saem da cor
            it[0]['_T0'], it[0]['_P0'] = it[0]['T'], it[0]['paint']     # o montado fica com a malha inteira
            it[0]['T'] = np.asarray(it[0]['T'])[keep]
            it[0]['paint'] = np.asarray(it[0]['paint'])[keep]
        malha.append(dict(nome=it[0]['nome'], **mk))
    files = []
    objs_print, objs_mont = [], []
    # print file: every part already on the bed of the chosen printer, in its print position;
    # the articulated body stays one object (its pieces never move apart); plates that do not
    # fit on the first one sit next to it, to the right
    mesa, nplates = {}, 1
    plates, pwarn = [], []
    if printer is not None:
        items = [dict(nome=p['nome'], T=T, paint=p['paint'], base=p.get('base', 1), src=p.get('src')) for p, T in lay]
        _, plates, pwarn, packed = write_plates(items, folder, name, palette, printer)
        nplates = len(packed)
        world = {p.get('src'): p['T'] for p, _ in lay}
        for k_, pl in enumerate(packed):
            dx = k_ * (printer['x'] + 30.0)
            for it, T in pl:
                Tp = T + np.array([dx, 0.0, 0.0])
                objs_print.append((it['nome'], Tp, it['paint'], it.get('base', 1)))
                mesa[it['src']] = rigid(world[it['src']], Tp).tolist()
    for k, (p, T) in enumerate(lay):
        if printer is None:
            objs_print.append((p['nome'], T, p['paint'], p.get('base', 1)))
        # o montado sai da malha na posição do modelo (os triângulos que colapsaram só na posição de
        # impressão continuam inteiros aqui) e passa pelo mesmo conserto
        T0, P0 = p.get('_T0', p['T']), p.get('_P0', p['paint'])
        Tm, km, _ = _weld_safe(T0)
        objs_mont.append((p['nome'], Tm, np.asarray(P0)[km] if km is not None else P0, p.get('base', 1)))
        if p.get('flexi'):
            continue                                  # its pieces are written by the joint export
        slug = (f'{k:02d}_corpo' if p['tipo'] == 'corpo' else
                f"{k:02d}_cor{p['base']}_{p['tipo']}" + (f"_area{p['rid'] + 1}" if p.get('rid') is not None else '')
                + (f"_corte{p['livre'] + 1}" if p.get('livre') is not None else ''))
        fn = os.path.join(stl_dir, f'{slug}.stl')
        with open(fn, 'wb') as f:
            f.write(_stl(T))
        files.append(os.path.join(stl_sub, os.path.basename(fn)))
    title = name + (' (tudo para imprimir)' if flexi is not None else ' (partes para imprimir)')
    data, ntri = write_3mf_objects(objs_print, palette, title)
    ok = check_3mf_objects(data, len(objs_print), ntri)
    f3 = f'{name}_tudo.3mf' if flexi is not None else f'{name}_partes.3mf'
    with open(os.path.join(folder, f3), 'wb') as f:
        f.write(data)
    fm = None
    if flexi is None:
        data_m, _ = write_3mf_objects(objs_mont, palette, name + ' (montado)')
        fm = f'{name}_montado.3mf'
        with open(os.path.join(folder, fm), 'wb') as f:
            f.write(data_m)
    rep = _report(out, name, files, f3, fm, flexi is not None, impressao)
    ruins = [m_ for m_ in malha if not m_['ok']]
    rep += ('\nMalha dos arquivos: ' + ('todas as peças fechadas, sem arestas com 3 ou mais faces e sem triângulos degenerados.\n'
            if not ruins else 'atenção: ' + '; '.join(f"{m_['nome']} ({m_['abertas']} abertas, {m_['multiplas']} múltiplas)" for m_ in ruins) + '.\n'))
    fl = 'LEIA_pecas_por_cor.txt' if flexi is not None else 'LEIA.txt'
    import i18n
    with open(os.path.join(folder, fl), 'w', encoding='utf-8') as f:
        f.write(i18n.tr_text(rep))                 # no idioma escolhido na tela
    return dict(ok=ok, pasta=folder, arquivo3mf=f3, montado=fm, stls=files, data3mf=data, placas=plates, avisos_placa=pwarn,
                mesa=mesa, n_placas=nplates, impressao=impressao, malha=malha)


def _weld32(V):
    """Vértices iguais em float32 (como o fatiador lê o STL) viram o mesmo índice. Igual a
    np.unique(V, axis=0, return_inverse=True), só que bem mais rápido (ordena os 12 bytes de cada
    vértice; +0.0 junta -0.0 com 0.0, como a comparação de números faz). Devolve (U, inv)."""
    V = np.ascontiguousarray(np.asarray(V, np.float32).reshape(-1, 3) + np.float32(0.0))
    key = V.view(np.dtype((np.void, 12))).ravel()
    _, first, inv = np.unique(key, return_index=True, return_inverse=True)
    return V[first], inv.reshape(-1)


def mesh_errors(T):
    """Erros da malha como o fatiador vê o STL (vértices em float32 iguais viram o mesmo ponto):
    (arestas abertas, arestas com 3 ou mais faces, triângulos degenerados)."""
    U, inv = _weld32(T)
    F = inv.reshape(-1, 3).astype(np.int64)
    deg = (F[:, 0] == F[:, 1]) | (F[:, 1] == F[:, 2]) | (F[:, 0] == F[:, 2])
    Fg = F[~deg]
    E_ = np.sort(np.concatenate([Fg[:, [0, 1]], Fg[:, [1, 2]], Fg[:, [2, 0]]]), axis=1)
    _, cnt = np.unique(E_[:, 0] * (len(U) + 1) + E_[:, 1], return_counts=True)
    return int((cnt == 1).sum()), int((cnt > 2).sum()), int(deg.sum())


_SNAP_Q = 2.0 ** -17


def _grid_snap(T):
    T = np.asarray(T, np.float64)
    return np.round(T / _SNAP_Q) * _SNAP_Q


def _mesh_rank(e):
    """Qual malha é pior para o fatiador: borda aberta (furo, o fatiador acusa e pode imprimir errado),
    depois aresta com 3+ faces, depois triângulo degenerado (área zero: o fatiador ignora). Antes a
    escolha somava tudo, e 12 bordas abertas ganhavam de 13 triângulos degenerados."""
    return (int(e[0]), int(e[1]), int(e[2]))


def _weld_safe(T):
    """Ao gravar em float32 dois vértices muito próximos podem virar um só e criar uma aresta com 4
    faces (o Bambu Studio acusa erro). Desloca a peça alguns milésimos de mm na mesa até a malha sair
    limpa. Devolve (T, dict(abertas, multiplas, degenerados, ok))."""
    # grade fixa de 2^-17 mm (mais fina que o float32 a 256 mm): dois vértices que são o mesmo ponto a
    # menos de 1e-13 mm viram exatamente o mesmo número. Sem isso, perto de z = 0 (a peça apoiada na
    # mesa) o float32 tem resolução sobrando e separa de novo o que era um ponto só: borda aberta
    T = _grid_snap(T)
    e0 = mesh_errors(T)
    best = (T, e0)
    keep = None
    # deslocar só ajuda quando vértices diferentes viram um só em float32; num contato de verdade (o
    # mesmo ponto já em float64) não ajuda e fica só o conserto da topologia
    colapso = False
    if any(e0):
        V64 = np.ascontiguousarray(T.reshape(-1, 3) + 0.0)
        n64 = len(np.unique(V64.view(np.dtype((np.void, 24))).ravel()))
        colapso = n64 != len(_weld32(T)[0])
    if colapso:
        for k in range(1, 9):
            d = np.array([0.0007 * k, 0.0011 * k, 0.0])
            e = mesh_errors(T + d)
            if _mesh_rank(e) < _mesh_rank(best[1]):
                best = (T + d, e)
            if not any(e):
                break
    if any(best[1]):
        # candidatos: tirar os triângulos que colapsaram (dois vértices iguais em float32), separar
        # as superfícies que se tocam num ponto, ou os dois; fica o que deixar a malha mais limpa
        Tb = best[0]
        F = _weld32(Tb)[1].reshape(-1, 3)
        deg = (F[:, 0] == F[:, 1]) | (F[:, 1] == F[:, 2]) | (F[:, 0] == F[:, 2])
        # (gera um candidato por vez e para no primeiro que sai limpo)
        def cands():
            try:
                Tr = _resolve_pinches(Tb)
                yield Tr, None
                yield _resolve_pinches(Tr, alt=True), None
            except Exception:
                traceback.print_exc()
            if deg.any():
                Td = Tb[~deg]
                yield Td, ~deg
                try:
                    yield _resolve_pinches(Td), ~deg
                except Exception:
                    traceback.print_exc()
                yield _split_pinches(Td), ~deg
            yield _split_pinches(Tb), None
        for Tc, kc in cands():
            e = mesh_errors(Tc)
            if _mesh_rank(e) < _mesh_rank(best[1]):
                best, keep = (Tc, e), kc
            if not any(best[1]):
                break
    a, m, g = best[1]
    return best[0], keep, dict(abertas=a, multiplas=m, degenerados=g, ok=not (a or m or g))


def _resolve_pinches(T, eps=0.003, alt=False):
    """Duas superfícies do mesmo sólido que se tocam numa aresta (mecha encostada na testa, braço no
    corpo, cortados bem no contato) viram, no STL, uma aresta com 4 faces. Aqui a topologia é refeita:
    em volta de cada aresta assim as faces são ordenadas pelo ângulo e cada uma é pareada com a vizinha
    que fecha material com ela (orientações opostas, sólido dentro da cunha). Com isso cada vértice do
    contato se divide nos leques de cada superfície, e cada leque recua eps mm para dentro pela própria
    normal: as superfícies se afastam 2·eps (muito abaixo do que uma impressora resolve). A ordem dos
    triângulos não muda (a cor de cada um segue igual). Serve para qualquer etapa e qualquer modelo.
    alt=True usa o outro pareamento válido (segunda passada, para arestas de triângulos minúsculos em que
    o teste da cunha erra)."""
    T = np.array(T, np.float64)
    U, inv = _weld32(T)
    U = U.astype(np.float64)
    F = inv.reshape(-1, 3)
    nf = len(F)
    if nf == 0:
        return T
    a_ = np.concatenate([F[:, 0], F[:, 1], F[:, 2]])
    b_ = np.concatenate([F[:, 1], F[:, 2], F[:, 0]])
    ef = np.tile(np.arange(nf), 3)
    lo, hi = np.minimum(a_, b_), np.maximum(a_, b_)
    key = lo.astype(np.int64) * (len(U) + 1) + hi
    uk, ie, cnt = np.unique(key, return_inverse=True, return_counts=True)
    ie = ie.reshape(-1)
    bad = np.where(cnt > 2)[0]
    if not len(bad):
        return T
    fn = np.cross(U[F[:, 1]] - U[F[:, 0]], U[F[:, 2]] - U[F[:, 0]])          # normal x 2·área
    order = np.argsort(ie, kind='stable')
    start = np.concatenate([[0], np.cumsum(cnt)])
    partner = {}                                       # (aresta, face) -> face do outro lado
    badset = set(bad.tolist())
    first = order[start[bad]]
    bverts = np.unique(np.concatenate([lo[first], hi[first]]))
    for e in bad:
        rows = order[start[e]:start[e + 1]]
        fs = ef[rows]
        va, vb = lo[rows[0]], hi[rows[0]]
        d = U[vb] - U[va]
        dn = np.linalg.norm(d)
        if dn < 1e-12 or len(fs) % 2:
            continue
        d /= dn
        third = np.array([[x for x in F[f] if x != va and x != vb][0] if len(set(F[f])) == 3 else F[f][0] for f in fs])
        r = U[third] - U[va]
        r -= np.outer(r @ d, d)
        e1 = r[0] / max(np.linalg.norm(r[0]), 1e-12)
        e2 = np.cross(d, e1)
        ang = np.arctan2(r @ e2, r @ e1)
        srt = np.argsort(ang)
        fs, ang = fs[srt], ang[srt]
        rws = rows[srt]
        s = np.where(a_[rws] == va, 1, -1)              # sentido da aresta em cada face
        m = len(fs)
        best_p = None
        for sh in (0, 1):
            pairs = [((sh + 2 * i) % m, (sh + 2 * i + 1) % m) for i in range(m // 2)]
            if any(s[i] == s[j] for i, j in pairs):
                continue
            # o sólido fica dentro da cunha entre as duas: a normal da primeira aponta para fora da cunha
            ok = 0
            for i, j in pairs:
                t = -np.sin(ang[i]) * e1 + np.cos(ang[i]) * e2
                ok += int(fn[fs[i]] @ t < 0)
            if best_p is None or (ok < best_p[0] if alt else ok > best_p[0]):
                best_p = (ok, pairs)
        if best_p is None:
            continue
        for i, j in best_p[1]:
            partner[(e, fs[i])] = fs[j]
            partner[(e, fs[j])] = fs[i]
    # faces em volta de cada vértice do contato, separadas em leques
    vf_order = np.argsort(F.ravel(), kind='stable')
    vf_sorted = F.ravel()[vf_order]
    for v in bverts:
        i0, i1 = np.searchsorted(vf_sorted, [v, v + 1])
        fs = np.unique(vf_order[i0:i1] // 3)
        if len(fs) < 2:
            continue
        idx = {int(f): k for k, f in enumerate(fs)}
        par = list(range(len(fs)))

        def find(x):
            while par[x] != x:
                par[x] = par[par[x]]
                x = par[x]
            return x
        for f in fs:
            for j in range(3):
                e = ie[j * nf + f]
                if v != lo[j * nf + f] and v != hi[j * nf + f]:
                    continue
                if e in badset:
                    g = partner.get((e, f))
                else:
                    rows = order[start[e]:start[e + 1]]
                    g = next((int(ef[q]) for q in rows if ef[q] != f), None) if len(rows) == 2 else None
                if g is not None and int(g) in idx:
                    par[find(idx[int(f)])] = find(idx[int(g)])
        groups = {}
        for f in fs:
            groups.setdefault(find(idx[int(f)]), []).append(int(f))
        if len(groups) < 2:
            continue
        for fl in groups.values():
            n_ = fn[fl].sum(0)
            ln = np.linalg.norm(n_)
            if ln < 1e-12:
                continue
            p_ = U[v] - eps * n_ / ln
            for f in fl:
                for j in range(3):
                    if F[f, j] == v:
                        T[f, j] = p_
    return T


def _split_pinches(T, eps=0.002):
    T = np.array(T, np.float64)
    V = np.asarray(T, np.float32).reshape(-1, 3)
    _, inv = np.unique(V, axis=0, return_inverse=True)
    F = inv.reshape(-1, 3)
    E_ = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1)
    ue, ie, cnt = np.unique(E_, axis=0, return_inverse=True, return_counts=True)
    ie = ie.reshape(-1)
    bad_e = cnt > 2
    if not bad_e.any():
        return T
    nf = len(F)
    eface = np.tile(np.arange(nf), 3)
    # triângulos de cada aresta e de cada vértice por índice ordenado (antes era um laço sobre a malha
    # inteira por vértice: num corpo grande com defeitos levava minutos; o resultado é o mesmo)
    e_ord = np.argsort(ie, kind='stable')
    e_st = np.searchsorted(ie[e_ord], np.arange(len(ue) + 1))
    v_ord = np.argsort(F.ravel(), kind='stable')
    v_st = np.searchsorted(F.ravel()[v_ord], np.arange(int(F.max()) + 2))

    class _GP:
        def get(self, e_id, dflt):
            if bad_e[e_id]:
                return dflt
            return list(eface[e_ord[e_st[e_id]:e_st[e_id + 1]]])
    good_pairs = _GP()
    verts = np.unique(ue[bad_e].ravel())
    for v in verts:
        fs = np.unique(v_ord[v_st[v]:v_st[v + 1]] // 3)
        if len(fs) < 2:
            continue
        idx = {f: i for i, f in enumerate(fs)}
        par = list(range(len(fs)))

        def find(x):
            while par[x] != x:
                par[x] = par[par[x]]
                x = par[x]
            return x
        for f in fs:                                 # liga triângulos pelas arestas normais que passam por v
            for j in range(3):
                e_id = ie[j * nf + f]
                if bad_e[e_id] or v not in ue[e_id]:
                    continue
                for g in good_pairs.get(e_id, []):
                    if g in idx:
                        par[find(idx[f])] = find(idx[g])
        groups = {}
        for f in fs:
            groups.setdefault(find(idx[f]), []).append(f)
        if len(groups) < 2:
            continue
        for gi, fl in enumerate(sorted(groups.values(), key=len)[:-1]):
            fl = np.array(fl)
            c = T[fl].reshape(-1, 3).mean(0)
            for f in fl:
                for j in range(3):
                    if F[f, j] == v:
                        d = c - T[f, j]
                        n_ = np.linalg.norm(d)
                        if n_ > 1e-9:
                            T[f, j] = T[f, j] + d / n_ * eps * (gi + 1)
    return T


def _orient_all(pieces):
    """Posição na mesa de cada peça (orienta.py): menos suporte, mais apoio, encaixe de pé. O corpo
    principal e as partes articuladas ficam como no modelo; deles só sai o relatório."""
    import orienta as OR
    bodies = [p for p in pieces if p['tipo'] == 'corpo']
    anchor = max(bodies, key=lambda p: len(p['T'])) if bodies else None
    rep = []
    for p in pieces:
        if p['tipo'] == 'cavilha':
            continue
        try:
            if p is anchor or p.get('flexi') or p.get('conjunto'):   # flexi articulado: imprime como no modelo
                e = OR.evaluate(p['T'], np.eye(4) if p.get('print_T') is None else p['print_T'])
                mudou = False
            else:
                M, e, mudou = OR.best(p['T'], p.get('print_T'), p.get('axis'))
                if mudou:
                    p['print_T'] = M
        except Exception:
            continue
        rep.append(dict(nome=p['nome'], suporte_cm2=round(e['suporte'] / 100.0, 1), contato_cm2=round(e['contato'] / 100.0, 1),
                        altura=round(e['altura'], 1), brim=bool(OR.brim(e)), mudou=bool(mudou), fixa=p is anchor or bool(p.get('flexi')) or bool(p.get('conjunto'))))
    return rep


def _stl(T):
    import struct
    T = np.asarray(T, np.float64)
    n = len(T)
    nrm = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    ln = np.linalg.norm(nrm, axis=1, keepdims=True)
    ln[ln == 0] = 1
    rec = np.zeros(n, dtype=[('n', '<f4', 3), ('v', '<f4', 9), ('a', '<u2')])
    rec['n'] = nrm / ln
    rec['v'] = T.reshape(n, 9)
    return b'EFC3D: partes'.ljust(80, b' ') + struct.pack('<I', n) + rec.tobytes()


def _report(out, name, files, f3, fm, com_juntas=False, impressao=None):
    s = summary(out)
    L = [f'EFC3D: partes separadas por cor de "{name}"', '']
    if com_juntas:
        L += [f'{f3}: o corpo articulado (juntas) e as partes cortadas, prontos para imprimir, cada um no seu filamento.',
              'pecas/: as peças do corpo articulado. pecas_por_cor/: um STL por parte cortada, na posição de impressão.', '']
    else:
        L += [f'{f3}: todas as partes deitadas na posição de impressão, cada uma no seu filamento.',
              f'{fm}: as partes montadas, para conferir.', 'pecas/: um STL por parte, já na posição de impressão.', '']
    for p in s['partes']:
        L.append(f"- {p['nome']} ({p['tipo']}): {p['tamanho'][0]} × {p['tamanho'][1]} × {p['tamanho'][2]} mm")
    L.append('')
    for r in s['regioes']:
        L.append(f"Área {r['id'] + 1}: {'ok' if r['ok'] else 'não cortada'}")
        for c in r['checks']:
            L.append(f"   [{c['nivel']}] {c['texto']}")
    if impressao:
        L += ['', 'Na mesa (posição de impressão, PLA, balanço acima de 45° pede suporte):']
        for o in impressao:
            sup = 'sem suporte' if o['suporte_cm2'] < 0.5 else f"suporte em cerca de {str(o['suporte_cm2']).replace('.', ',')} cm²"
            L.append(f"- {o['nome']}: {sup}; apoio na mesa {str(o['contato_cm2']).replace('.', ',')} cm²"
                     + ('; use brim (aba) nesta peça' if o['brim'] else '')
                     + (' (posição escolhida para menos suporte)' if o['mudou'] else '')
                     + (' (fica de pé como no modelo)' if o['fixa'] else ''))
    m = s['malha']
    L += ['', f"Malha: {m['pct']}% dos triângulos originais ficaram idênticos; {m['mudaram']} mudaram, só na área dos cortes."]
    L += ['', 'Montagem: tampões entram retos no encaixe; com folga de 0,3 mm, use cola (CA ou epóxi).',
          'Para encaixe por pressão sem cola, teste folgas de 0,10 a 0,15 mm na sua impressora.']
    return '\n'.join(L) + '\n'
