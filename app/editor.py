"""EFC3D (Easy Flexy and Cuts 3D): joint editor engine.

Every joint is a proven cutter (a negative volume) from the library, placed by the user:
position, rotation on three axes, scale per axis (locked or free), cut limits per side (they
trim only the cutter's plate, never its loops), and an optional "cut inside the border" mask.
The clearance in mm is kept whatever the scale. Each joint can be previewed on its own region
in seconds, with a traffic light of checks; the full cut, the mesh quality tests and the export
work on all joints together.

Local frame of a cutter: origin at the loops centre, +Y = seam normal (from piece A to piece
B), +Z = up as the cutter's designer printed it, X across.
"""
import json
import math
import os
import time
import itertools

import numpy as np
import manifold3d as mf

import engine as E

HERE = os.path.dirname(os.path.abspath(__file__))
LIB_DIR = os.path.join(HERE, 'cutters', 'lib')
import pastas as PST
USER_DIR = os.path.join(PST.DADOS, 'cutters')
CORE_MARGIN = 0.8          # the loops region (never trimmed) is the measured core plus this
DEFAULT_WALL = 0.8

_MESH = {}
_META = None


# ----------------------------------------------------------------------------- library
# 1.50: as peças de corte de terceiros (FJM, Projectcutter v1 a v3, flexicutter) saíram do app. Cada uma tem a
# junta própria (RLA) feita no lugar dela, com as mesmas funções; projeto antigo que usava a de terceiros abre
# com a junta própria correspondente.
ANTIGAS = {'fjm': 'rla_arco', 'pc3': 'rla_arco_baixo', 'flexicutter': 'rla_arco_grande', 'pc1': 'rla_concha',
           'pc2': 'rla_concha_compacta'}
PADRAO = 'rla_arco'


class _Biblioteca(dict):
    """Biblioteca de peças de corte; o id antigo de terceiros vira a junta própria que a substitui."""
    def __missing__(self, k):
        if k in ANTIGAS and ANTIGAS[k] in self:
            return self[ANTIGAS[k]]
        raise KeyError(k)


def canon(cid):
    """Id da peça de corte que o app usa (o de terceiros vira o da junta própria)."""
    if cid in library() and cid not in ANTIGAS:
        return cid
    return ANTIGAS.get(cid, cid if cid in library() else PADRAO)


def library():
    global _META
    if _META is None:
        meta = json.load(open(os.path.join(LIB_DIR, 'biblioteca.json'), encoding='utf-8'))
        for k in meta:
            meta[k]['origem'] = 'biblioteca'
        try:
            if os.path.exists(os.path.join(USER_DIR, 'biblioteca.json')):
                um = json.load(open(os.path.join(USER_DIR, 'biblioteca.json'), encoding='utf-8'))
                for k, v in um.items():
                    v['origem'] = 'sua'
                    meta[k] = v
        except Exception:
            pass
        _META = _Biblioteca(meta)
    return _META


def _reload():
    global _META
    _META = None
    return library()


def cutter_mesh(cid):
    cid = canon(cid)
    if cid not in _MESH:
        m = library()[cid]
        d = USER_DIR if m.get('origem') == 'sua' else LIB_DIR
        _MESH[cid] = E.read_stl(open(os.path.join(d, m['arquivo']), 'rb').read())
    return _MESH[cid]


def cutter_stl_bytes(cid):
    cid = canon(cid)
    m = library()[cid]
    d = USER_DIR if m.get('origem') == 'sua' else LIB_DIR
    return open(os.path.join(d, m['arquivo']), 'rb').read()


def _slice_axis(M, ax, t):
    R = {0: np.array([[0, 0, 1, 0], [0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 1.0]]),
         1: np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1.0]]), 2: np.eye(4)}[ax]
    return E.X(M, R).slice(t)


def normalize_cutter(C):
    """Find the seam plate (the thickest flat layer of the cutter), put it on local y = 0, the
    loops centre on the origin, keep the designer's up axis as z. Returns (mesh, meta)."""
    if C.num_tri() > 20000:
        C = E.flat(C.simplify(0.005))
    b = np.array(C.bounding_box())
    best = None
    for ax in (0, 1, 2):
        ts = np.linspace(b[ax] + 0.02, b[ax + 3] - 0.02, 300)
        a = np.array([_slice_axis(C, ax, t).area() for t in ts])
        k = int(np.argmax(a))
        score = a[k] / max(np.median(a), 1e-6)
        if best is None or score > best[0]:
            best = (score, ax, ts, a, k)
    _, ax, ts, a, k = best
    thr = 0.6 * a[k]
    i0 = i1 = k
    while i0 > 0 and a[i0 - 1] > thr:
        i0 -= 1
    while i1 < len(a) - 1 and a[i1 + 1] > thr:
        i1 += 1
    p0, p1 = ts[i0], ts[i1]
    th = p1 - p0
    pc = (p0 + p1) / 2
    up = 2 if ax != 2 else 1
    ac = [i for i in (0, 1, 2) if i not in (ax, up)][0]
    names = {0: 'x', 1: 'y', 2: 'z'}
    boxes = []
    for t in (p0 - 1.2, p1 + 1.2):
        cs = _slice_axis(C, ax, t)
        if not cs.is_empty():
            boxes.append(cs.bounds())
    # slice coordinates for each normal axis: ax=0 -> (z, y); ax=1 -> (x, z); ax=2 -> (x, y)
    coord = {0: ('z', 'y'), 1: ('x', 'z'), 2: ('x', 'y')}[ax]

    def rng(name):
        i = coord.index(name)
        return (min(bb[i] for bb in boxes), max(bb[i + 2] for bb in boxes))
    if boxes:
        ra, ru = rng(names[ac]), rng(names[up])
    else:
        ra, ru = (b[ac], b[ac + 3]), (b[up], b[up + 3])
    cen = np.zeros(3)
    cen[ax] = pc
    cen[ac] = (ra[0] + ra[1]) / 2
    cen[up] = (ru[0] + ru[1]) / 2
    T = np.zeros((4, 4))
    T[3, 3] = 1
    T[0, ac] = 1
    T[1, ax] = 1
    T[2, up] = 1
    if np.linalg.det(T[:3, :3]) < 0:
        T[0, ac] = -1
    T[:3, 3] = -T[:3, :3] @ cen
    Cl = E.X(C, T)
    cb = np.array(Cl.bounding_box())
    core = [(ra[1] - ra[0]) / 2, (cb[4] - cb[1]) / 2, (ru[1] - ru[0]) / 2]
    blk = E.BOX(-core[0] - 1.2, core[0] + 1.2, cb[1] - 1, cb[4] + 1, -core[2] - 1.2, core[2] + 1.2)
    ps = sorted(E.parts(E.flat(blk - Cl), 0.05), key=lambda q: -q.volume())
    gap = ps[0].min_gap(ps[1], 3.0) if len(ps) > 1 else None
    meta = dict(placa=round(th, 3), folga=round(gap, 3) if gap else None,
                nucleo_meio=[round(v, 2) for v in core], caixa=[round(v, 2) for v in cb.tolist()],
                tris=Cl.num_tri(), partes_teste=len(ps), aneis_fechados=[p.genus() for p in ps[:2]])
    return Cl, meta


def import_cutter(data, name):
    """User's own cutter (STL bytes): normalized and kept in ~/EFC3D/cutters."""
    C = E.read_stl(data)
    Cl, meta = normalize_cutter(C)
    os.makedirs(USER_DIR, exist_ok=True)
    cid = 'sua_' + time.strftime('%Y%m%d_%H%M%S')
    meta.update(nome=(name or 'Peça de corte própria')[:60], arquivo=cid + '.stl')
    open(os.path.join(USER_DIR, cid + '.stl'), 'wb').write(E.write_stl(Cl))
    path = os.path.join(USER_DIR, 'biblioteca.json')
    um = {}
    if os.path.exists(path):
        try:
            um = json.load(open(path, encoding='utf-8'))
        except Exception:
            um = {}
    um[cid] = meta
    tmp = path + '.tmp'
    json.dump(um, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    _reload()
    return cid, meta


# ----------------------------------------------------------------------------- transforms
def rot_xyz(rx, ry, rz):
    """Rotation matrix (4x4) for angles in degrees, applied X then Y then Z (same order as the
    viewer's Euler 'XYZ' convention: R = Rx * Ry * Rz)."""
    a, b, c = (math.radians(v) for v in (rx, ry, rz))
    Rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    Ry = np.array([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]])
    Rz = np.array([[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]])
    M = np.eye(4)
    M[:3, :3] = Rx @ Ry @ Rz
    return M


def frame(jp):
    T = rot_xyz(*jp.get('rot', [0, 0, 0]))
    T[:3, 3] = jp['pos']
    return T


def _grow(M, d, quick=False):
    """Fast outward growth by about d (union of copies shifted in 26 directions, 1.08 x d so the
    spots between directions also get d; quick = 14 directions, 1.15 x d). Only used on hidden
    or test geometry: the real clearance is measured after every cut."""
    if d <= 0:
        return M
    vs = [v for v in itertools.product((-1, 0, 1), repeat=3) if any(v)]
    if quick:
        vs = [v for v in vs if sum(map(abs, v)) in (1, 3)]
    dirs = [np.array(v, float) / np.linalg.norm(v) for v in vs]
    g = (1.15 if quick else 1.08) * d
    return E.flat(E.union([M] + [M.translate((v * g).tolist()) for v in dirs]))


def cutter_local(jp, clearance, extra=0.0, mask=None):
    """The cutter in its local frame, scaled, grown so the clearance never drops below
    `clearance` (plus `extra`). With a border mask (local frame) the plate is extended as a flat
    sheet of the same thickness over the whole local part and trimmed to the mask, so the seam
    always crosses the part completely whatever the scale. Side limits trim only the plate.
    Returns (cutter, loops box)."""
    meta = library()[jp['tipo']]
    C = cutter_mesh(jp['tipo'])
    s = [float(v) for v in jp['escala']]
    sx = -s[0] if jp.get('espelho') else s[0]     # mirrored copy of a joint: the cutter is mirrored too
    Cs = E.X(C, np.diag([sx, s[1], s[2], 1.0]))
    core = np.array(meta['nucleo_meio']) * np.array(s) + CORE_MARGIN
    corebox = E.BOX(-core[0], core[0], -core[1], core[1], -core[2], core[2])
    loops = E.flat(Cs ^ corebox)
    plate = E.flat(Cs - corebox)
    if mask is not None:
        h = meta['placa'] * s[1] / 2
        sheet = E.flat(E.BOX(-300, 300, -h, h, -300, 300) - corebox)
        plate = E.flat(E.flat(plate + sheet) ^ mask)
    lim = jp.get('limites')
    if lim:
        # [x-, x+, y-, y+, z-, z+] in mm from the joint centre; None = no limit
        L = [(-1e3 if v is None else -abs(float(v))) if i % 2 == 0 else (1e3 if v is None else abs(float(v)))
             for i, v in enumerate(lim)]
        plate = E.flat(plate ^ E.BOX(L[0], L[1], L[2], L[3], L[4], L[5]))
    cut = E.flat(loops + plate)
    native = meta.get('folga') or 0.3
    d = max(0.0, (clearance - native * min(s)) / 2) + extra
    if d > 0:
        cut = _grow(cut, d)
    return cut, corebox


def border_mask(S, jp, margin=0.5):
    """Region (local frame) a cut may touch with "cut inside the border": the piece of section,
    at the seam plane and just before/after it, that holds the joint centre. Parts that only
    cross the plane are outside it; parts glued to it there are inside (they are cut too)."""
    T = frame(jp)
    meta = library()[jp['tipo']]
    hy = meta['placa'] * float(jp['escala'][1]) / 2 + 0.6
    secs = []
    for yq in (-hy, 0.0, hy):
        Tq = T.copy()
        Tq[:3, 3] = (T @ [0, yq, 0, 1])[:3]
        sq = E._section_local(S, Tq)
        if sq is not None:
            secs.append(sq)
    if not secs:
        return None
    cs = secs[0]
    for sq in secs[1:]:
        cs = cs + sq
    cs = cs.offset(margin, mf.JoinType.Round)
    pr = cs.extrude(400.0).translate([0, 0, -200.0])
    return E.flat(E.X(pr, np.linalg.inv(E.rot_x(-90))))


_CW = {}
_CW_KEYS = ('tipo', 'pos', 'rot', 'escala', 'borda', 'limites', 'espelho')


def cutter_world(S, jp, clearance, extra=0.0):
    """The cutter placed in the model (world frame), cached. Returns (cutter, loops box)."""
    key = (json.dumps({k: jp.get(k) for k in _CW_KEYS}, sort_keys=True), round(clearance, 4), round(extra, 4),
           (S.num_tri(), round(S.volume(), 2)) if S is not None else None)
    if key not in _CW:
        if len(_CW) > 96:
            _CW.pop(next(iter(_CW)))
        _CW[key] = _cutter_world(S, jp, clearance, extra)
    return _CW[key]


def _cutter_world(S, jp, clearance, extra=0.0):
    T = frame(jp)
    mask = border_mask(S, jp) if (jp.get('borda', True) and S is not None) else None
    cut, corebox = cutter_local(jp, clearance, extra, mask)
    return E.flat(E.X(cut, T)), E.flat(E.X(corebox, T))


# ----------------------------------------------------------------------------- suggestions
_ROT = {}


def _pick(cs):
    for comp in cs.decompose():
        if (comp ^ mf.CrossSection.square([0.4, 0.4]).translate([-0.2, -0.2])).area() > 0.01:
            return comp
    return None


def _sections_along(S, T, ys):
    """Local sections of the part at offsets ys along the seam normal: one transform of the
    model per frame (cached), then plain slices."""
    key = (S.num_tri(), round(S.volume(), 1), tuple(np.round(T[:3, :].ravel(), 4)))
    M = _ROT.get(key)
    if M is None:
        if len(_ROT) > 24:
            _ROT.pop(next(iter(_ROT)))
        M = E.flat(E.X(S, E.rot_x(-90) @ np.linalg.inv(T)))
        _ROT[key] = M
    return [_pick(M.slice(-float(yq))) for yq in ys]


_LOOPSLICE = {}
_US = (-1.0, -0.8, -0.6, -0.45, -0.3, -0.24, 0.24, 0.3, 0.45, 0.6, 0.8, 1.0)


def loop_slices(tipo):
    """Slices of the cutter's loops (unscaled) across its depth, in section coordinates
    (x across, y = local z). Used to fit the scale: each slice must stay inside the part."""
    if tipo not in _LOOPSLICE:
        meta = library()[tipo]
        C = cutter_mesh(tipo)
        h = meta['placa'] / 2 + 0.05
        loops = E.flat(C - E.BOX(-500, 500, -h, h, -500, 500))   # everything off the flat plate
        R = E.rot_x(-90)
        out = []
        for u in _US:
            q = u * meta['nucleo_meio'][1]
            out.append(E.X(loops, R).slice(-q))
        _LOOPSLICE[tipo] = out
    return _LOOPSLICE[tipo]


def fit_scale(S, jp, wall=DEFAULT_WALL, max_ratio=1.6, s_max=2.5):
    """Largest loops that keep `wall` of skin all along their depth: the cutter's own loops,
    sliced across the depth, must stay inside the part's sections at the same depths. Locked:
    one scale. Free: width and height on their own (ratio up to max_ratio), depth = the
    smaller. Also picks the best centre height. Returns (escala, dz) or (None, 0)."""
    meta = library()[jp['tipo']]
    cy = meta['nucleo_meio'][1]
    T = frame(jp)
    locked = jp.get('cadeado', True)
    sl = loop_slices(jp['tipo'])
    cache = {}

    def secs(sy):
        k = round(sy, 2)
        if k not in cache:
            ss = _sections_along(S, T, [u * cy * sy for u in _US])
            cache[k] = None if any(q is None for q in ss) else [q.offset(-wall - 0.15, mf.JoinType.Round) for q in ss]
        return cache[k]

    def fits(sx, sz, dz):
        inn = secs(min(sx, sz))
        if not inn:
            return False
        for c, q in zip(sl, inn):
            if c.is_empty():
                continue
            if (c.scale([sx, sz]).translate([0, dz]) - q).area() > 1e-3:
                return False
        return True
    sec0 = E._section_local(S, T)
    if sec0 is None:
        return None, 0.0
    bx = sec0.bounds()
    dzs = np.linspace(bx[1] + wall, bx[3] - wall, 9)
    best = None
    grid = np.round(np.arange(0.2, s_max + 1e-6, 0.05), 3)
    if locked:
        for dz in dzs:
            lo, hi = 0, len(grid) - 1
            if not fits(grid[0], grid[0], dz):
                continue
            while lo < hi:
                m = (lo + hi + 1) // 2
                if fits(grid[m], grid[m], dz):
                    lo = m
                else:
                    hi = m - 1
            g = grid[lo]
            if best is None or g > best[0][0]:
                best = ([g, g, g], dz)
    else:
        for dz in dzs:
            for sz in grid:
                if not fits(0.2, sz, dz):
                    break
                lo, hi = 0, len(grid) - 1
                while lo < hi:
                    m = (lo + hi + 1) // 2
                    if grid[m] <= sz * max_ratio and fits(grid[m], sz, dz):
                        lo = m
                    else:
                        hi = m - 1
                sx = grid[lo]
                if sx < sz / max_ratio:
                    continue
                vol = sx * sz * min(sx, sz)
                # strength comes from the smallest axis: maximize it first, then the size
                key = (round(min(sx, sz), 2), vol)
                if best is None or key > best[2]:
                    best = ([sx, min(sx, sz), sz], dz, key)
    if best is None:
        return None, 0.0
    return [float(v) for v in best[0]], float(best[1])


def section_limits(S, jp, pad=1.0):
    """Side limits (mm from the centre) that keep the plate on the local part: its section at
    the seam plus pad. Front and back are free (the plate is thin)."""
    T = frame(jp)
    sec = E._section_local(S, T)
    if sec is None:
        return None
    b = sec.bounds()
    return [round(-b[0] + pad, 2), round(b[2] + pad, 2), None, None, round(-b[1] + pad, 2), round(b[3] + pad, 2)]


def angle_candidates(S, x, y, z, n=3):
    """Vertical seam planes through the point with the smallest local sections (they cut
    across a leg, a tail or the body), up to n of them at least 20 degrees apart."""
    found = []
    for a in range(0, 180, 6):
        sec = E._section_local(S, frame(dict(pos=[x, y, z], rot=[0, 0, a])))
        if sec is not None:
            found.append((sec.area(), a))
    found.sort()
    out = []
    for ar, a in found:
        if all(min(abs(a - b), 180 - abs(a - b)) >= 20 for _, b in out):
            out.append((ar, a))
        if len(out) >= n:
            break
    return out


def orient(S, x, y, z, a):
    """Normal pointing to the side holding less of the model (towards the tip)."""
    T = frame(dict(pos=[x, y, z], rot=[0, 0, a]))
    nrm = T[:3, 1]
    side = E.flat(S ^ E._halfspace(nrm, float(nrm @ np.array([x, y, z]))))
    return float(a - 180.0) if side.volume() > 0.5 * S.volume() else float(a)


def auto_angle(S, x, y, z=None):
    if z is None:
        z = (E.bottom_height(S, x, y) + E.top_height(S, x, y)) / 2
    c = angle_candidates(S, x, y, z, 1)
    return orient(S, x, y, z, c[0][1]) if c else 0.0


def suggest_at(S, x, y, angle_deg=None, tipo=PADRAO, wall=DEFAULT_WALL, cadeado=None, others=(),
               angle_hint=None, slide=(2.0,)):
    """Starting placement for a joint clicked at (x, y): seam normal along angle_deg (planner
    convention: direction (-sin a, cos a)), loops fitted to the part along their whole length
    (free scale when it fits clearly better than locked), centre at the best height, limits
    from the section."""
    moved = 0.0
    if angle_deg is None:
        # try the best few seam directions here, then slide a little along the part to the
        # spot where the strongest loops fit (only while the section stays the same part)
        z0 = (E.bottom_height(S, x, y) + E.top_height(S, x, y)) / 2
        cands = angle_candidates(S, x, y, z0, 3)
        if angle_hint is not None:
            h = float(angle_hint) % 180
            if all(min(abs(h - b), 180 - abs(h - b)) >= 10 for _, b in cands):
                cands.append((1e9, h))

        def probe(px, py, a):
            zb_, zt_ = E.bottom_height(S, px, py), E.top_height(S, px, py)
            q = dict(tipo=tipo, pos=[px, py, (zb_ + zt_) / 2], rot=[0, 0, a], escala=[1, 1, 1], cadeado=True)
            sec = E._section_local(S, frame(q))
            s_, _ = fit_scale(S, q, 0.6)
            return (s_[0] if s_ else 0.0), (sec.area() if sec is not None else 1e9)
        cyy = (library()[tipo]['caixa'][4] - library()[tipo]['caixa'][1]) / 2   # half the depth the joint takes along the normal

        def clear_of_others(px, py, s_):
            # never slide into the loops of a joint that is already there
            for o in others:
                so = float(max(o['escala']))
                if math.hypot(px - o['pos'][0], py - o['pos'][1]) < cyy * (s_ + so) + 1.5:
                    return False
            return True
        # natural seam (smallest section) first; other directions and small slides along the
        # part only when the natural spot cannot hold strong loops and they clearly can
        opts = []
        for k, (ar, a) in enumerate(cands):
            sc, ar_here = probe(x, y, a)
            opts.append((sc, k, 0.0, a, x, y))
            if k == 0 and sc >= 0.5:
                break
            nrm = np.array([-math.sin(math.radians(a)), math.cos(math.radians(a))])
            for off in [o * sg for o in slide for sg in (-1.0, 1.0)]:
                px, py = (np.array([x, y]) + nrm * off).tolist()
                sc2, ar2 = probe(px, py, a)
                if ar2 < 1.6 * ar_here and clear_of_others(px, py, sc2):
                    opts.append((sc2, k, abs(off), a, px, py))
        if not opts:
            angle_deg = 0.0
        else:
            nat = opts[0]
            top = max(o[0] for o in opts)
            if nat[0] >= 0.5 or top < nat[0] + 0.1:
                pick = nat
            else:
                pick = min([o for o in opts if o[0] >= top - 0.05], key=lambda o: (o[1], o[2]))
            if pick[2]:
                moved = pick[2]
            x, y = pick[4], pick[5]
            angle_deg = orient(S, x, y, z0, pick[3])
    zb = E.bottom_height(S, x, y)
    zt = E.top_height(S, x, y)
    zc = zb + (zt - zb) / 2
    jp = dict(tipo=tipo, pos=[float(x), float(y), float(zc)], rot=[0.0, 0.0, float(angle_deg)],
              escala=[1.0, 1.0, 1.0], cadeado=True, borda=True, limites=None)
    STRONG = 0.5          # FJM like cutters: below about half size the hooks get thinner than 1 mm
    best = None
    used_wall = wall
    for w in (wall, 0.6, 0.45):
        sl, dzl = fit_scale(S, dict(jp, cadeado=True), w)
        if sl and (best is None or min(sl) > min(best[0]) + 0.04):
            best = (sl, dzl, True)
            used_wall = w
        if best and min(best[0]) >= STRONG:
            break
    if cadeado is not True:
        # free scale: wider across the part when that fits clearly more, same strength
        sf, dzf = fit_scale(S, dict(jp, cadeado=False), used_wall)
        if sf and (cadeado is False or best is None or
                   (min(sf) >= min(best[0]) - 1e-6 and sf[0] * sf[1] * sf[2] > 1.25 * best[0][0] ** 3)):
            best = (sf, dzf, False)
    if best is None:
        best = (None, 0.0, True)
    s_, dz, lk = best
    if s_ is None:
        s_, dz = [0.4, 0.4, 0.4], 0.0
        jp['aviso'] = 'A parte é fina demais aqui para os elos com pele de %.1f mm.' % wall
    # a joint already close by: make this one thinner along the seam normal (open lock) so the
    # loops of the two never touch, instead of cutting into each other
    cyy = (library()[tipo]['caixa'][4] - library()[tipo]['caixa'][1]) / 2   # half the depth the joint takes along the normal
    for o in others:
        d = math.hypot(x - o['pos'][0], y - o['pos'][1])
        cap = (d - 1.0) / cyy - float(o['escala'][1])
        if 0 < d < 40 and cap < s_[1]:
            s_ = [s_[0], max(0.2, round(cap - 0.025, 2)), s_[2]]
            lk = False
            jp['aviso'] = (f'Junta próxima de outra ({d:.0f} mm): afinei a espessura dos elos para '
                           f'{s_[1]:.2f} para não encostar nela.')
    jp['escala'] = [round(v, 3) for v in s_]
    jp['cadeado'] = lk
    jp['pos'][2] = float(zc + dz)
    jp['limites'] = section_limits(S, jp)
    if moved:
        jp['movida_mm'] = round(abs(moved), 1)
    return jp


def suggest_all(an, S, tipo=PADRAO, clearance=0.4):
    """Joints from the automatic plan, as editor joints (a starting point the user adjusts)."""
    import planner as PL
    J, _ = PL.plan(an, clearance)
    out = []
    core = an.get('core')
    for q in J:
        x, y = float(q['x']), float(q['y'])
        if q.get('papel') == 'membro' and core is not None:
            # a limb joint must sit on the limb itself, not where the leg is merged into the
            # body: otherwise its seam crosses the whole body section and cuts the flank off
            a = math.radians(float(q['angle']))
            d = np.array([-math.sin(a), math.cos(a)])
            grown = core.offset(4.0, mf.JoinType.Round)
            for _ in range(14):
                dot = mf.CrossSection.circle(0.5, 12).translate([x, y])
                if (grown ^ dot).area() <= 0:
                    break
                x, y = x + d[0], y + d[1]
        jp = suggest_at(S, x, y, None, tipo, others=out,
                        angle_hint=float(q['angle']), slide=(2.0, 4.0))
        jp['nome'] = 'Corpo' if q.get('papel') != 'membro' else 'Pata'
        out.append(jp)
    return out


# ----------------------------------------------------------------------------- checks
def erode(P, r):
    """P with its surface moved inwards by about r."""
    b = np.array(P.bounding_box())
    m = 1.2 * r + 0.05
    bx = E.BOX(b[0] - m, b[3] + m, b[1] - m, b[4] + m, b[2] - m, b[5] + m)
    return E.flat(P - _grow(E.flat(bx - P), r, quick=True))


_STRENGTH = {}
_STRENGTH_FILE = os.path.join(PST.DADOS, 'cache_forca.json')


def strength(tipo, escala, clearance, espelho=False):
    """1.0 / 0.7 / None: thickness class of the hooks and loops of this cutter at this scale
    and clearance. Cut in a plain block; the two pieces must still hold each other after every
    surface of both is eaten by r. Cached in memory and on disk."""
    key = f"{tipo}|{','.join(f'{float(v):.3f}' for v in escala)}|{clearance:.3f}"
    if not _STRENGTH:
        _STRENGTH['_'] = None
        for f in (os.path.join(LIB_DIR, 'cache_forca.json'), _STRENGTH_FILE):
            try:
                _STRENGTH.update(json.load(open(f, encoding='utf-8')))
            except Exception:
                pass
    if key in _STRENGTH:
        return _STRENGTH[key]
    meta = library()[tipo]
    s = np.array([float(v) for v in escala])
    kh = np.array(meta['nucleo_meio']) * s + CORE_MARGIN
    jp = dict(tipo=tipo, pos=[0.0, 0.0, 0.0], rot=[0.0, 0.0, 0.0], escala=list(s), borda=False, limites=None)
    cut, _ = cutter_local(jp, clearance)
    blk = E.BOX(-kh[0] - 0.7, kh[0] + 0.7, -kh[1] - 1.5, kh[1] + 1.5, -kh[2] - 0.7, kh[2] + 0.7)
    ps = sorted(E.parts(E.flat(blk - cut), 0.05), key=lambda q: -q.volume())
    res = None
    if len(ps) >= 2:
        A = [p for p in ps if E.centroid(p)[1] < 0]
        B = [p for p in ps if E.centroid(p)[1] >= 0]
        if A and B:
            A, B = A[0], B[0]
            reach = 2 * float(kh.max()) + 1.5
            if holds(A, B, reach=reach, first=[0, 1, 0]):
                for r in (0.5, 0.35):
                    if holds(erode(A, r), erode(B, r), reach=reach + 2 * r, first=[0, 1, 0]):
                        res = 2 * r
                        break
    _STRENGTH[key] = res
    try:
        os.makedirs(os.path.dirname(_STRENGTH_FILE), exist_ok=True)
        tmp = _STRENGTH_FILE + '.tmp'
        json.dump({k: v for k, v in _STRENGTH.items() if k != '_'}, open(tmp, 'w', encoding='utf-8'))
        os.replace(tmp, _STRENGTH_FILE)
    except Exception:
        pass
    return res


def ring_bar(rings):
    """Thickness class of the rings (1.0, 0.7 or None = thinner): each ring must keep its hole
    (genus) after its surface is eroded by r."""
    if not rings:
        return None
    kb = np.array(E.union(rings).bounding_box())
    bx = E.BOX(kb[0] - 0.8, kb[3] + 0.8, kb[1] - 0.8, kb[4] + 0.8, kb[2] - 0.8, kb[5] + 0.8)
    for r in (0.5, 0.35):
        if all(E.flat(R - _grow(E.flat(bx - R), r, quick=True)).genus() >= 1 for R in rings):
            return 2 * r
    return None


def holds(A, B, reach=10.0, step=0.2, hit=0.02, first=None):
    """True when B, pulled straight in any of the 26 directions (down too: off the bed nothing
    holds a paw from below), hits A within reach mm. Small steps so thin loops cannot jump
    through each other between two tests. `first`: the seam normal, tried first (the likeliest
    way out), so a failure is found quickly."""
    dirs = [np.array(v_, float) / np.linalg.norm(v_) for v_ in itertools.product((-1, 0, 1), repeat=3) if any(v_)]
    if first is not None:
        f = np.asarray(first, float)
        dirs.sort(key=lambda d: -abs(float(d @ f)))
    for dv_ in dirs:
        if not any((B.translate((dv_ * t_).tolist()) ^ A).volume() > hit
                   for t_ in np.arange(step, reach + 1e-6, step)):
            return False
    return True


def _side(T, p):
    return float((np.linalg.inv(T) @ np.r_[p, 1.0])[1])


def _local_pieces(S, Cw, T, box):
    Sl = E.flat(S ^ box)
    cut = E.flat(Sl - Cw)
    ps = E.parts(cut, 0.5)
    # side of each piece = where most of its volume is (a ball or anchor reaching far into the
    # other side would fool a centre test)
    nrm = T[:3, 1]
    neg = E._halfspace(-nrm, -float(nrm @ T[:3, 3]))
    sides = [(E.flat(p ^ neg).volume() > 0.5 * p.volume()) for p in ps]
    A = [p for p, a in zip(ps, sides) if a]
    B = [p for p, a in zip(ps, sides) if not a]
    A.sort(key=lambda q: -q.volume())
    B.sort(key=lambda q: -q.volume())
    return Sl, (A[0] if A else None), (B[0] if B else None), ps


def check_joint(S, jp, clearance, others=(), base_islands=None):
    """Cut only around this joint and grade it. Returns (checks, A local, B local, cutter)."""
    t0 = time.time()
    T = frame(jp)
    meta = library()[jp['tipo']]
    Cw, Kw = cutter_world(S, jp, clearance)
    cb = np.array(Cw.bounding_box())
    pad = 3.0
    sb = np.array(S.bounding_box())
    # region around the joint, as deep on piece A's side as on B's (some joints reach far
    # into one side only)
    lb = np.array(E.X(Cw, np.linalg.inv(T)).bounding_box())
    yy = max(abs(lb[1]), abs(lb[4])) + pad
    corners = np.array([[x, y, z, 1.0] for x in (lb[0] - pad, lb[3] + pad) for y in (-yy, yy) for z in (lb[2] - pad, lb[5] + pad)])
    wc = (T @ corners.T).T[:, :3]
    lo, hi = np.minimum(wc.min(0), cb[:3] - pad), np.maximum(wc.max(0), cb[3:] + pad)
    box = E.BOX(lo[0], hi[0], lo[1], hi[1], sb[2] - 1.0, hi[2])
    Sl, A, B, ps = _local_pieces(S, Cw, T, box)
    checks = []

    tm = {}
    t1 = [time.time()]

    def add(key, nivel, texto, valor=None):
        checks.append(dict(item=key, nivel=nivel, texto=texto, valor=valor))
        tm[key] = round(time.time() - t1[0], 2)
        t1[0] = time.time()
    if A is None or B is None:
        add('separa', 'erro', 'O corte não separa a peça aqui: aumente a escala ou os limites, ou mova a junta.')
        return dict(checks=checks, segundos=round(time.time() - t0, 1)), A, B, Cw
    add('separa', 'ok', 'O corte separa as duas peças.')
    # clearance really obtained; if short, grow a little more once
    g = A.min_gap(B, clearance + 0.15)
    if g < clearance - 0.01:
        Cw, Kw = cutter_world(S, jp, clearance, extra=(clearance - g) / 2 + 0.02)
        Sl, A, B, ps = _local_pieces(S, Cw, T, box)
        g = A.min_gap(B, clearance + 0.15) if (A is not None and B is not None) else 0.0
    if A is None or B is None:
        add('folga', 'erro', 'Ao garantir a folga o corte deixou de separar a peça.')
        return dict(checks=checks, segundos=round(time.time() - t0, 1)), A, B, Cw
    add('folga', 'ok' if g >= clearance - 0.01 else 'erro', f'Folga real {g:.2f} mm (pedida {clearance:.2f} mm).', round(g, 3))
    # loops closed: each side keeps a ring at the joint
    Kb = E.flat(Kw)
    def _genus(P):
        return max([q.genus() for q in E.flat(P ^ Kb).decompose() if q.volume() > 0.05] or [0])
    ga, gb = _genus(A), _genus(B)
    captiva = meta.get('mecanismo', 'elos') != 'elos'
    if captiva:
        # ball or anchor held inside a cavity: there is no ring; "held in 26 directions" below
        # is the test that matters
        ga = gb = 1
        add('elos', 'ok', 'Encaixe interno (sem elos): a retenção é conferida pelo teste de direções.')
    elif ga >= 1 and gb >= 1:
        add('elos', 'ok', 'Elos fechados nas duas peças.')
    else:
        add('elos', 'erro', 'Elo aberto: ' + ('peça A ' if ga < 1 else '') + ('peça B' if gb < 1 else '') +
            '. Afaste a junta da mesa ou da borda, ou aumente a escala.')
    # locked: pulled in 26 directions B must catch on A. Only the loops region matters: linked
    # rings cannot get out without crossing each other.
    kh = np.array(meta['nucleo_meio']) * np.array([float(v) for v in jp['escala']]) + CORE_MARGIN
    Aloc = E.flat(A ^ E.X(E.BOX(-kh[0] - 1.2, kh[0] + 1.2, -kh[1] - 1.2, kh[1] + 1.2, -kh[2] - 1.2, kh[2] + 1.2), T))
    Bloc = E.flat(B ^ E.X(E.BOX(-kh[0] - 0.6, kh[0] + 0.6, -kh[1] - 0.6, kh[1] + 0.6, -kh[2] - 0.6, kh[2] + 0.6), T))
    reach = 2 * float(kh.max()) + 1.2
    held = holds(Aloc, Bloc, reach=reach, first=T[:3, 1])
    add('presa', 'ok' if held else 'erro', 'Peça presa em todas as direções.' if held else 'A peça escapa em alguma direção: elos não se prendem.')
    # strength: the hooks and loops this cutter makes at this scale and clearance (tested in a
    # plain block, cached: the skin around them is checked separately below)
    if held:
        bar = strength(jp['tipo'], jp['escala'], clearance, bool(jp.get('espelho')))
        if bar is not None and bar >= 1.0:
            add('forca', 'ok', f'Elos e ganchos com pelo menos {bar:.1f} mm de espessura.', bar)
        elif bar is not None:
            add('forca', 'aviso', f'Elos finos (cerca de {bar:.1f} mm): podem quebrar ao abrir. Aumente a escala se couber.', bar)
        else:
            add('forca', 'erro', 'Elos ou ganchos mais finos que 0,7 mm: vão quebrar ou soltar. Aumente a escala ou use outra peça de corte.', 0.0)
    # skin around the loops cavity
    # skin over the loops: distance from what the cutter removes off its plate (the loops
    # cavities) to the outside of the model
    sc = [float(v) for v in jp['escala']]
    grow_d = max(0.0, (clearance - (meta.get('folga') or 0.3) * min(sc)) / 2)
    th = meta['placa'] * sc[1] / 2 + grow_d + 0.2
    slab = E.flat(E.X(E.BOX(-500, 500, -th, th, -500, 500), T))
    domes = [c for c in E.flat(E.flat(Cw ^ Kb) - slab).decompose() if c.volume() > 0.05]
    pele = None
    if domes:
        outside = E.flat(E.flat(box) - S)
        pele = float(min(c.min_gap(outside, 1.0) for c in domes))
    if pele is None:
        add('pele', 'ok', 'Elos sem cavidade escondida perto da pele.')
    elif pele >= 0.75:
        add('pele', 'ok', ('Pele em volta dos elos com 1 mm ou mais.' if pele >= 0.999 else f'Pele mínima em volta dos elos {pele:.2f} mm.'), round(pele, 2))
    elif pele >= 0.4:
        add('pele', 'aviso', f'Pele fina em volta dos elos: {pele:.2f} mm. Pode marcar a superfície.', round(pele, 2))
    else:
        add('pele', 'erro', f'Os elos chegam à superfície (pele {pele:.2f} mm): vão aparecer ou furar.', round(pele, 2))
    # parts starting in mid air near the joint (new ones only)
    known = base_islands if base_islands is not None else E.islands(S)
    new = []
    for P_ in (A, B):
        for q in E.islands(P_):
            if q['z'] > 0.35 and not any(abs(q['x'] - k['x']) < 3 and abs(q['y'] - k['y']) < 3 and abs(q['z'] - k['z']) < 1.0 for k in known):
                new.append(q)
    if new:
        add('ar', 'aviso', f'{len(new)} ponto(s) começando no ar perto da junta: pedem suporte ou ponte.', len(new))
    else:
        add('ar', 'ok', 'Nada começa no ar por causa desta junta.')
    # cutting other parts (when the border mask is off) and overlap with other joints
    if not jp.get('borda', True):
        mask = border_mask(S, jp)
        if mask is not None:
            plate = E.flat(E.flat(Cw - Kb) ^ Sl)
            fora = E.flat(plate - E.X(mask, T)).volume()
            if fora > 1.0:
                add('borda', 'aviso', f'O corte pega outras partes além da borda ({fora:.0f} mm³). Ligue "Corte dentro da borda" ou reduza os limites.')
    sob = []
    for k, oj in others:
        try:
            Co, _ = cutter_world(S, oj, clearance)
        except Exception:
            continue
        ob = np.array(Co.bounding_box())
        if np.any(ob[:3] > cb[3:]) or np.any(cb[:3] > ob[3:]):
            continue
        if E.flat(Co ^ Cw).volume() > 0.1:
            sob.append(k)
    if sob:
        add('sobrepoe', 'erro', 'Sobrepõe a(s) junta(s) ' + ', '.join(f'J{k + 1}' for k in sob) + '. Afaste ou reduza.')
    else:
        add('sobrepoe', 'ok', 'Não encosta em outra junta.')
    return dict(checks=checks, segundos=round(time.time() - t0, 1), tempos=tm), A, B, Cw


def light(checks):
    lv = [c['nivel'] for c in checks]
    return 'erro' if 'erro' in lv else ('aviso' if 'aviso' in lv else 'ok')


# ----------------------------------------------------------------------------- full cut
def clean(p):
    """Drop zero area slivers the booleans leave (collapse only edges shorter than 1 micron:
    the shape and resolution stay the same)."""
    q = E.flat(p.simplify(0.001))
    return q if q.status() == mf.Error.NoError and abs(q.volume() - p.volume()) < 1e-3 * p.volume() else p

def cut_all(S, joints, clearance, progress=None):
    """Cut all joints. Returns pieces, per joint checks, the joint graph and messages."""
    t0 = time.time()
    base_isl = E.islands(S)
    res, cutters = [], []
    for k, jp in enumerate(joints):
        others = [(i, o) for i, o in enumerate(joints) if i != k]
        r, A, B, Cw = check_joint(S, jp, clearance, others, base_isl)
        r['luz'] = light(r['checks'])
        res.append(r)
        cutters.append(Cw)
        if progress:
            progress(f'junta {k + 1}/{len(joints)} verificada')
    if progress:
        progress('cortando o modelo inteiro')
    allc = E.flat(E.union(cutters)) if cutters else mf.Manifold()
    cut = E.flat(S - allc) if cutters else S
    ps = sorted(E.parts(cut, 0.0), key=lambda q: -q.volume())
    pieces = [clean(p) for p in ps if p.volume() >= 5.0]
    lascas = [p for p in ps if p.volume() < 5.0]
    # graph: which pieces each joint connects (probe points just off the seam, inside A and B)
    edges = []
    for k, jp in enumerate(joints):
        T = frame(jp)
        meta = library()[jp['tipo']]
        dy = meta['nucleo_meio'][1] * float(jp['escala'][1]) + 1.5
        a = b = None
        for sgn in (-1, 1):
            for r_ in (dy, dy + 2, dy + 4):
                for dz in (0.0, -1.0, 1.0):
                    p = (T @ [0, sgn * r_, dz, 1])[:3]
                    for i, pc in enumerate(pieces):
                        if E.contains_point(pc, p.tolist(), 0.2):
                            if sgn < 0 and a is None:
                                a = i
                            if sgn > 0 and b is None:
                                b = i
        edges.append(dict(junta=k, a=a, b=b, frame=T.tolist()))
        if a is None or b is None or a == b:
            res[k]['checks'].append(dict(item='grafo', nivel='erro', texto='No modelo inteiro esta junta não separa duas peças (as peças continuam ligadas por outro lugar).'))
            res[k]['luz'] = 'erro'
    return dict(pieces=pieces, juntas=res, edges=edges, lascas=[round(p.volume(), 2) for p in lascas],
                segundos=round(time.time() - t0, 1))


# ----------------------------------------------------------------------------- mesh quality
def mesh_quality(S, pieces, joints, clearance, stl_bytes=None, lascas_vol=0.0):
    """The 8 export tests. Returns (all_ok, list of results)."""
    import trimesh
    import warnings
    warnings.filterwarnings('ignore', category=RuntimeWarning)
    out = []

    def add(n, ok, texto):
        out.append(dict(teste=n, ok=bool(ok), texto=texto))
    tri = []
    for p in pieces:
        v, f = E.mesh_arrays(p)
        tri.append(trimesh.Trimesh(v.astype(np.float64), f, process=False))
    wt = all(t.is_watertight for t in tri)
    add(1, wt, 'Todas as peças fechadas, sem furos.' if wt else 'Há peça com furo ou borda aberta.')
    wind = all(t.is_winding_consistent and p.volume() > 0 for t, p in zip(tri, pieces))
    add(2, wind, 'Faces orientadas para fora.' if wind else 'Há faces invertidas.')
    st = all(p.status() == mf.Error.NoError for p in pieces)
    add(3, st, 'Sem auto interseção (malha validada pelo motor Manifold).' if st else 'O motor encontrou malha inválida.')
    deg = 0
    for t in tri:
        deg += int(np.sum(t.area_faces < 1e-10))
    add(4, deg == 0, 'Sem triângulos degenerados nem faces de espessura zero.' if deg == 0 else f'{deg} triângulo(s) degenerado(s).')
    solo = [len(E.parts(p, 0.0)) for p in pieces]
    add(5, all(n == 1 for n in solo), 'Cada peça é um único sólido.' if all(n == 1 for n in solo) else 'Há peça com mais de um sólido (lasca).')
    # 6: skin intact outside the joints: the only material the cut may remove is the material
    # inside the cutters (volume balance), and no bit of the model may be dropped
    Cs = [cutter_world(S, jp, clearance)[0] for jp in joints]
    dentro = E.flat(S ^ E.union(Cs)).volume() if Cs else 0.0
    sobra = S.volume() - dentro - sum(p.volume() for p in pieces)
    ok6 = abs(sobra) < max(0.5, 2e-4 * S.volume()) and lascas_vol < 1.0
    add(6, ok6, 'Pele intacta fora das juntas.' if ok6 else
        f'O corte mudou o modelo fora das juntas (diferença {sobra:.1f} mm³, lascas {lascas_vol:.1f} mm³).')
    tn = sum(p.num_tri() for p in pieces)
    add(7, tn >= 0.95 * S.num_tri(), f'Resolução preservada ({tn} triângulos, original {S.num_tri()}).')
    # 8: re-read the exported file
    ok8, txt8 = True, 'Arquivo relido e conferido.'
    if stl_bytes is not None:
        m = trimesh.load(trimesh.util.wrap_as_stream(stl_bytes), file_type='stl', process=False)
        m.merge_vertices(digits_vertex=5)
        bodies = m.split(only_watertight=False)
        vols = sorted([abs(b.volume) for b in bodies if abs(b.volume) > 1.0], reverse=True)
        pv = sorted([p.volume() for p in pieces], reverse=True)
        if len(vols) != len(pv):
            ok8, txt8 = False, f'O arquivo relido tem {len(vols)} corpos; esperado {len(pv)}.'
        elif any(abs(a - b) > 0.005 * max(b, 1) for a, b in zip(vols, pv)):
            ok8, txt8 = False, 'Volume das peças no arquivo relido difere do calculado.'
    add(8, ok8, txt8)
    return all(r['ok'] for r in out), out


# ----------------------------------------------------------------------------- coupon
def make_coupon(jp, clearances=(0.20, 0.25, 0.30, 0.35, 0.40, 0.50), progress=None):
    """Calibration coupon with the chosen cutter and scale: one block + paw per clearance, the
    joint identical in all samples, n dimples on sample n. Returns (pieces, report)."""
    meta = library()[jp['tipo']]
    s = np.array([float(v) for v in jp['escala']])
    core = np.array(meta['nucleo_meio']) * s
    wall = 1.2
    hw, hh, hd = core[0] + wall + 0.6, core[2] + wall + 0.6, core[1] + 1.5
    H = 2 * hh
    pieces, rep = [], []
    for n, c in enumerate(clearances, 1):
        ox = (n - 1) * (2 * hw + 10)
        block = E._rounded_box(ox - hw - 3, ox + hw + 3, -hd - 8, 0.0, 0, H + 1.0, 1.0) if hasattr(E, '_rounded_box') else E.BOX(ox - hw - 3, ox + hw + 3, -hd - 8, 0.0, 0, H + 1.0)
        paw = E._rounded_box(ox - hw, ox + hw, -2.0, hd + 10, 0, H, 1.0) if hasattr(E, '_rounded_box') else E.BOX(ox - hw, ox + hw, -2.0, hd + 10, 0, H)
        dim = E.union([mf.Manifold.cylinder(2, 0.8, 0.8, 24).translate([ox - hw + 1.5 + 2.2 * k, -hd - 5, H + 1.0 - 0.6]) for k in range(n)])
        Sm = E.flat(E.flat(block + paw) - dim)
        j = dict(jp, pos=[ox, 0.0, H / 2], rot=[0.0, 0.0, 0.0], borda=False, limites=None)
        r, A, B, Cw = check_joint(Sm, j, float(c))
        if A is None or B is None:
            rep.append(dict(amostra=n, furinhos=n, folga_programa=c, ok=False))
            continue
        cut = E.flat(Sm - Cw)
        ps = sorted(E.parts(cut, 1.0), key=lambda q: -q.volume())
        pieces += ps[:2]
        fr = [x for x in r['checks'] if x['item'] == 'folga']
        rep.append(dict(amostra=n, furinhos=n, folga_programa=c, folga_real=fr[0]['valor'] if fr else None,
                        presa=all(x['nivel'] != 'erro' for x in r['checks'])))
        if progress:
            progress(f'amostra {n}/{len(clearances)}')
    return pieces, dict(amostras=rep, peca=meta['nome'], escala=list(map(float, s)))


# ----------------------------------------------------------------------------- project / export
PROJ_VERSION = 4


def project_dict(base_stl_bytes, joints, clearance, nome='modelo', extra=None):
    import base64
    d = dict(flexi_studio=PROJ_VERSION, nome=nome, folga=clearance, juntas=joints,
             base_stl=base64.b64encode(base_stl_bytes).decode('ascii'))
    lib = library()
    used = {j['tipo'] for j in joints}
    # user cutters travel inside the project so it reopens on another Mac
    d['pecas_de_corte'] = {cid: dict(meta=lib[cid], stl=base64.b64encode(cutter_stl_bytes(cid)).decode('ascii'))
                           for cid in used if lib.get(cid, {}).get('origem') == 'sua'}
    if extra:
        d.update(extra)
    return d


def open_project(d):
    """Returns (base stl bytes, joints, clearance, nome). Installs user cutters it carries."""
    import base64
    if int(d.get('flexi_studio', 0)) < 4:
        raise ValueError('Projeto de versão antiga (antes da v4): abra o STL e posicione as juntas de novo.')
    for cid, v in (d.get('pecas_de_corte') or {}).items():
        if cid not in library():
            os.makedirs(USER_DIR, exist_ok=True)
            meta = dict(v['meta'])
            meta.pop('origem', None)
            open(os.path.join(USER_DIR, meta['arquivo']), 'wb').write(base64.b64decode(v['stl']))
            path = os.path.join(USER_DIR, 'biblioteca.json')
            um = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}
            um[cid] = meta
            json.dump(um, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            _reload()
    juntas = []
    for j in (d.get('juntas') or []):
        t0 = j.get('tipo') or PADRAO
        j2 = dict(j, tipo=canon(t0))
        if t0 in ANTIGAS:
            j2['_antiga'] = t0                           # a escala é refeita para a junta própria (ajustar_antigas)
        juntas.append(j2)
    return base64.b64decode(d['base_stl']), juntas, float(d.get('folga', 0.4)), d.get('nome', 'modelo')


NOMES_ANTIGAS = {'fjm': 'FJM', 'pc1': 'Projectcutter v1', 'pc2': 'Projectcutter v2', 'pc3': 'Projectcutter v3',
                 'flexicutter': 'flexicutter'}


def ajustar_antigas(S, joints):
    """Juntas de um projeto antigo que usavam peça de corte de terceiros: viram a junta própria correspondente no
    mesmo lugar e no mesmo giro, com a escala refeita para os elos dela caberem na peça (as medidas são outras).
    Devolve (juntas, avisos)."""
    out, avisos = [], []
    for k, j in enumerate(joints):
        antiga = j.pop('_antiga', None)
        if antiga:
            # a junta própria que fica com os elos maiores (em mm) ali: a correspondente ou o Arco Baixo, que é
            # a mais baixa (cabe melhor em pata fina)
            melhor = None
            for t in dict.fromkeys([j['tipo'], 'rla_arco_baixo']):
                if t not in library():
                    continue
                q = dict(j, tipo=t)
                best = None
                for w in (DEFAULT_WALL, 0.6, 0.45):
                    try:
                        sl, dz = fit_scale(S, q, w)
                    except Exception:
                        sl, dz = None, 0.0
                    if sl and (best is None or min(sl) > min(best[0]) + 0.04):
                        best = (sl, dz)
                    if best and min(best[0]) >= 0.5:
                        break
                if best:
                    mm_ = min(best[0]) * min(library()[t]['nucleo_meio'])
                    if melhor is None or mm_ > melhor[0] + 0.05:
                        melhor = (mm_, t, best)
            if melhor:
                _, t, best = melhor
                j['tipo'] = t
                j['escala'] = [round(float(v), 3) for v in best[0]]
                j['pos'] = [j['pos'][0], j['pos'][1], float(j['pos'][2]) + float(best[1])]
            avisos.append(f"Junta J{k + 1}: a peça de corte {NOMES_ANTIGAS.get(antiga, antiga)} (de terceiros) saiu do app; "
                          f"no lugar dela entrou a {library()[j['tipo']]['nome']}, no mesmo lugar, com a escala ajustada. Confira a junta.")
        out.append(j)
    return out, avisos


def export(S, base_stl_bytes, joints, clearance, outdir, nome='modelo', force=False, progress=None,
           paint=None, palette=None):
    """Full cut + 8 mesh tests + files. Red joints do not block (force=True after the user
    confirms); a failed mesh test always blocks. Returns a summary dict."""
    t0 = time.time()
    R = cut_all(S, joints, clearance, progress)
    pieces = R['pieces']
    vermelhas = [k for k, r in enumerate(R['juntas']) if r['luz'] == 'erro']
    if vermelhas and not force:
        return dict(ok=False, precisa_confirmar=True, vermelhas=vermelhas, juntas=R['juntas'],
                    segundos=round(time.time() - t0, 1))
    if progress:
        progress('conferindo a malha')
    combined = E.write_stl(pieces)
    ok, testes = mesh_quality(S, pieces, joints, clearance, combined, sum(R['lascas']))
    if not ok:
        return dict(ok=False, bloqueado=True, testes=testes, juntas=R['juntas'], segundos=round(time.time() - t0, 1))
    os.makedirs(outdir, exist_ok=True)
    safe = ''.join(c if c.isalnum() or c in '-_' else '_' for c in nome) or 'modelo'
    # cada arquivo sai sem aresta com 3+ faces, como o fatiador lê (duas superfícies que se tocam numa
    # aresta são separadas alguns milésimos de mm: split._weld_safe), o mesmo reparo do corte por cores
    import split as SPL
    tl = [SPL._weld_safe(SPL.tri_array(p))[0] for p in pieces]
    open(os.path.join(outdir, f'{safe}_flexi.stl'), 'wb').write(SPL._stl(np.concatenate(tl)))
    pdir = os.path.join(outdir, 'pecas')
    os.makedirs(pdir, exist_ok=True)
    for i, t in enumerate(tl, 1):
        open(os.path.join(pdir, f'peca_{i:02d}.stl'), 'wb').write(SPL._stl(t))
    proj = project_dict(base_stl_bytes, joints, clearance, nome, paint_extra(paint, palette))
    json.dump(proj, open(os.path.join(outdir, f'{safe}.flexiproj'), 'w', encoding='utf-8'))
    # 3MF always (pieces together, in place); with the paint when the model is painted
    import paint as PT
    pintado = paint is not None and len(paint) == S.num_tri() and (np.asarray(paint) > 1).any()
    if pintado:
        if progress:
            progress('levando as cores para as peças')
        base_t = PT.tri_array(S)
        pl = [PT.transfer(base_t, paint, t) for t in tl]
    else:
        pl = [np.ones(len(t), np.uint8) for t in tl]
    pal = list(palette or [])
    data3, info3 = PT.write_3mf(tl, pl, pal, nome)
    ok3, n3 = PT.check_3mf(data3, sum(len(t) for t in tl))
    nome3 = f'{safe}_cores.3mf' if pintado else f'{safe}_flexi.3mf'
    open(os.path.join(outdir, nome3), 'wb').write(data3)
    cores = None
    if pintado:
        obj, mtl = PT.write_obj(tl, pl, pal, f'{safe}_cores')
        open(os.path.join(outdir, f'{safe}_cores.obj'), 'w', encoding='utf-8').write(obj)
        open(os.path.join(outdir, f'{safe}_cores.mtl'), 'w', encoding='utf-8').write(mtl)
        used = sorted(set(int(c) for c in np.concatenate(pl)))
        cores = dict(arquivo3mf=nome3, conferido=bool(ok3), triangulos=n3,
                     filamentos=used, cores=[info3['cores'][c - 1] for c in used])
    lines = [f'EFC3D: relatório de {nome}', time.strftime('%d/%m/%Y %H:%M'), '',
             f'Folga escolhida: {clearance:.2f} mm', f'Peças: {len(pieces)}', f'Juntas: {len(joints)}', '']
    for k, (jp, r) in enumerate(zip(joints, R['juntas'])):
        lines.append(f"J{k + 1} {jp.get('nome', '')} [{ {'ok': 'VERDE', 'aviso': 'AMARELO', 'erro': 'VERMELHO'}[r['luz']] }] "
                     f"peça {library()[jp['tipo']]['nome']}, escala {jp['escala']}, rotação {jp['rot']}")
        for c in r['checks']:
            if c['nivel'] != 'ok':
                lines.append(f"   {c['nivel']}: {c['texto']}")
    lines += ['', 'Testes de malha:'] + [f"  {t['teste']}. {'OK' if t['ok'] else 'FALHOU'}: {t['texto']}" for t in testes]
    if R['lascas']:
        lines.append(f"Lascas removidas (menores que 5 mm³): {len(R['lascas'])}")
    if vermelhas:
        lines.append('Exportado com juntas vermelhas confirmadas por você: ' + ', '.join(f'J{k + 1}' for k in vermelhas))
    if cores:
        lines += ['', f"Cores: {cores['arquivo3mf']} ({'conferido' if cores['conferido'] else 'FALHOU na releitura'}), "
                  f"filamentos usados: " + ', '.join(f"{f} ({c})" for f, c in zip(cores['filamentos'], cores['cores']))]
    import i18n
    open(os.path.join(outdir, 'relatorio.txt'), 'w', encoding='utf-8').write(i18n.tr_text('\n'.join(lines)))
    return dict(ok=True, pasta=outdir, pecas=len(pieces), testes=testes, juntas=R['juntas'],
                edges=R['edges'], vermelhas=vermelhas, cores=cores, arquivo3mf=nome3, conferido3mf=bool(ok3),
                pintado=bool(pintado), segundos=round(time.time() - t0, 1),
                _pieces=pieces, _piece_paint=pl, _3mf=data3)


def paint_extra(paint, palette):
    """Project fields for the colours (paint in base.stl triangle order)."""
    import base64
    out = {}
    if palette:
        out['paleta'] = list(palette)
    if paint is not None and (np.asarray(paint) > 1).any():
        out['pintura'] = base64.b64encode(np.asarray(paint, np.uint8).tobytes()).decode('ascii')
    return out
