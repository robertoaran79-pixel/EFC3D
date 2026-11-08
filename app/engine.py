"""EFC3D (Easy Flexy and Cuts 3D) geometry engine.

Turns a solid STL into print-in-place articulated pieces.
All geometry runs on manifold3d (exact, watertight booleans).
Units: millimetres. Z is up, the print bed is z = 0.
"""
import io
import math
import os
import struct
import time

import numpy as np
import manifold3d as mf

DEFAULT_CLEARANCE = 0.4
LIM_VOLUME = 93.0      # % of the original volume that must survive
LIM_SILHUETA = 2.0     # max % of silhouette area lost in any view
DEBUG = False
LIM_JUNTA_SIL = 1.0    # max % of silhouette one joint may remove (what you see)
VIEWS = dict(topo=np.eye(4),
             lado=np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1.0]]),
             frente=np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1.0]]))


def _outer(cs):
    keep = []
    for p in cs.to_polygons():
        p = np.asarray(p)
        if len(p) > 2 and 0.5 * np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1]) > 0:
            keep.append(p)
    return mf.CrossSection(keep) if keep else mf.CrossSection()


def visible_loss(before, after, dz=0.5, box=None):
    """Volume of the OUTSIDE shape that was lost (mm3): notches and dents you can see.
    Works layer by layer: the pieces are merged, seams up to 0.4 mm are closed and hidden
    voids (socket, keel slot, collar gap) are filled, then compared with the original."""
    if box is not None:
        before = [flat(m ^ box) for m in before]
        after = [flat(m ^ box) for m in after]
        before = [m for m in before if not m.is_empty()]
        if not before:
            return 0.0
    lo = min(m.bounding_box()[2] for m in before)
    hi = max(m.bounding_box()[5] for m in before)
    lost = 0.0
    for z in np.arange(lo + dz / 2, hi, dz):
        b = None
        for m in before:
            q = m.slice(z)
            b = q if b is None else b + q
        u = None
        for m in after:
            q = m.slice(z)
            u = q if u is None else u + q
        if b is None or b.is_empty():
            continue
        if u is None or u.is_empty():
            lost += b.area() * dz
            continue
        u = _outer(u.offset(0.35, mf.JoinType.Round).offset(-0.35, mf.JoinType.Round))
        lost += max(b.area() - (b ^ u).area(), 0.0) * dz
    return lost


def silhouettes(ms):
    out = {}
    for name, M in VIEWS.items():
        cs = None
        for p in ms:
            q = X(p, M).project()
            cs = q if cs is None else cs + q
        out[name] = cs.area() if cs is not None else 0.0
    return out


# ----------------------------------------------------------------------------
# STL input / output
# ----------------------------------------------------------------------------
def _fix_winding(f):
    """Make all triangles face the same way (AI generators often flip some of them).
    Breadth-first walk over neighbouring triangles: a neighbour that runs a shared edge in
    the same direction is flipped. Returns new faces, or None if the surface is not a
    clean closed surface (an edge shared by other than two triangles)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import breadth_first_order, connected_components
    n = len(f)
    he = f[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2).astype(np.int64)
    fid = np.repeat(np.arange(n), 3)
    lo, hi = he.min(1), he.max(1)
    key = lo * (int(f.max()) + 1) + hi
    order = np.argsort(key, kind='stable')
    ks = key[order]
    if len(ks) % 2 or np.any(ks[0::2] != ks[1::2]) or (len(ks) > 2 and np.any(ks[2::2] == ks[1:-1:2])):
        return None
    a, b = order[0::2], order[1::2]
    same = (he[a, 0] == he[b, 0])                     # same direction -> inconsistent pair
    fa, fb = fid[a], fid[b]
    G = coo_matrix((np.ones(len(fa)), (fa, fb)), shape=(n, n)).tocsr()
    G = G + G.T
    pk = np.minimum(fa, fb) * n + np.maximum(fa, fb)
    po = np.argsort(pk)
    pk_s, same_s = pk[po], same[po]
    flip = np.zeros(n, dtype=bool)
    ncomp, lab = connected_components(G, directed=False)
    for c in range(ncomp):
        start = int(np.argmax(lab == c))
        ordr, pred = breadth_first_order(G, start, directed=False, return_predecessors=True)
        par = pred[ordr[1:]]
        kk = np.minimum(par, ordr[1:]) * n + np.maximum(par, ordr[1:])
        inc = same_s[np.searchsorted(pk_s, kk)]
        fl = flip
        for node, p_, i_ in zip(ordr[1:].tolist(), par.tolist(), inc.tolist()):
            fl[node] = fl[p_] ^ i_
    out = f.copy()
    out[flip] = out[flip][:, ::-1]
    return out


def _patch_folds(v, f, rings=1):
    """Cut out tiny folded patches (neighbouring triangles facing opposite ways) and close
    each hole with a fan around its centre. Returns (v, f)."""
    he = f[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2)
    key = he[:, 0] * (len(v) + 1) + he[:, 1]
    _, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
    bad = np.zeros(len(f), dtype=bool)
    bad[np.unique(np.where(cnt[inv] > 1)[0] // 3)] = True
    if not bad.any():
        return v, f
    for _ in range(rings):
        vb = np.unique(f[bad])
        bad |= np.isin(f, vb).any(1)
    f = f[~bad]
    # boundary half-edges (no twin)
    he = f[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2)
    fw = he[:, 0] * (len(v) + 1) + he[:, 1]
    bw = he[:, 1] * (len(v) + 1) + he[:, 0]
    border = he[~np.isin(fw, bw)]
    nxt = {}
    for a, b in border.tolist():
        nxt.setdefault(b, []).append(a)          # walk the hole the opposite way
    used = set()
    newf, newv = [], [v]
    nv = len(v)
    for a0, b0 in border.tolist():
        if (a0, b0) in used:
            continue
        loop = [b0, a0]
        used.add((a0, b0))
        cur = a0
        ok = True
        for _ in range(10000):
            cand = [c for c in nxt.get(cur, []) if (c, cur) not in used]
            if not cand:
                ok = False
                break
            c = cand[0]
            used.add((c, cur))
            if c == loop[0]:
                break
            loop.append(c)
            cur = c
        if not ok or len(loop) < 3:
            continue
        cen = v[loop].mean(0)
        newv.append(cen[None, :])
        for i in range(len(loop)):
            newf.append([loop[i], loop[(i + 1) % len(loop)], nv])
        nv += 1
    if newf:
        f = np.vstack([f, np.array(newf, dtype=f.dtype)])
        v = np.vstack(newv)
    return v, f


def _tri_to_manifold(tris):
    """tris: (n,3,3) float array -> watertight Manifold (vertices merged, winding repaired)."""
    tris = np.asarray(tris, dtype=np.float64)
    verts = tris.reshape(-1, 3)
    # merge identical vertices (STL repeats them per triangle)
    q = np.round(verts / 1e-6 / max(1e-9, float(np.abs(verts).max()))).astype(np.int64)
    _, idx, inv = np.unique(q, axis=0, return_index=True, return_inverse=True)
    v = verts[idx].astype(np.float32)
    f = inv.reshape(-1, 3).astype(np.uint32)
    keep = (f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])
    f = f[keep]
    m = mf.Manifold(mf.Mesh(vert_properties=v, tri_verts=f))
    if m.status() != mf.Error.NoError:
        mesh = mf.Mesh(vert_properties=v, tri_verts=f)
        mesh.merge()
        m = mf.Manifold(mesh)
    if m.status() != mf.Error.NoError:
        g = _fix_winding(f.astype(np.int64))
        vv = v.astype(np.float64)
        if g is not None:
            for rings in (0, 1, 2):
                if rings:
                    vv, g = _patch_folds(vv, g, rings)
                m = mf.Manifold(mf.Mesh(vert_properties=vv.astype(np.float32), tri_verts=g.astype(np.uint32)))
                if m.status() == mf.Error.NoError:
                    break
            if m.status() == mf.Error.NoError and m.volume() < 0:
                m = mf.Manifold(mf.Mesh(vert_properties=vv.astype(np.float32), tri_verts=g[:, ::-1].astype(np.uint32).copy()))
    return m


MAX_TRIS = 250000


QUAL_MM = 0.005          # desvio máximo ao tirar triângulos repetidos: 0,005 mm, 1/10 do menor detalhe que a impressora faz


def lighten(m):
    """Tira só os triângulos que não mudam a forma (planos repetidos), com desvio de no máximo
    QUAL_MM no tamanho real. Antes o modelo era reduzido a 250 mil triângulos a qualquer custo e
    perdia até 0,13 mm de detalhe (rosto, dedos, relevo); agora a qualidade de impressão vem primeiro."""
    bb = m.bounding_box()
    hmax = max(bb[3] - bb[0], bb[4] - bb[1])
    h = bb[5] - bb[2]
    s = 1.0 if hmax >= 5.0 else 120.0 / max(hmax, h, 1e-9)    # arquivo sem unidade vira 120 mm
    out = m.simplify(QUAL_MM / s)
    return out if out.num_tri() > 0 and not out.is_empty() else m


def read_stl(data: bytes, simplify=False):
    """Read binary or ASCII STL bytes -> Manifold (raises ValueError if not closed).
    simplify: só ao abrir um modelo novo (tira triângulos repetidos, desvio de até QUAL_MM).
    Projeto, peças de corte e arquivos internos são lidos exatamente como estão."""
    tris = None
    if len(data) >= 84:
        n = struct.unpack('<I', data[80:84])[0]
        if 84 + n * 50 == len(data):
            rec = np.frombuffer(data, dtype=np.uint8, offset=84, count=n * 50).reshape(n, 50)
            tris = rec[:, 12:48].copy().view('<f4').reshape(n, 3, 3)
    if tris is None:
        txt = data.decode('utf-8', 'ignore')
        nums = []
        for line in txt.splitlines():
            line = line.strip()
            if line.startswith('vertex'):
                nums.append([float(x) for x in line.split()[1:4]])
        if not nums or len(nums) % 3:
            raise ValueError('Arquivo STL ilegivel.')
        tris = np.array(nums).reshape(-1, 3, 3)
    m = _tri_to_manifold(tris)
    LAST_REPAIR.clear()
    if m.status() != mf.Error.NoError or m.is_empty():
        m = _repair_fallback(tris)          # only for files the normal reading cannot close
    if m.status() != mf.Error.NoError or m.is_empty():
        raise ValueError('A malha tem furos ou faces soltas que o reparo automatico nao fecha. '
                         'Feche os furos antes (ex.: Meshmixer, Blender 3D Print Toolbox).')
    return lighten(m) if simplify else m


LAST_REPAIR = []     # what the last-resort repair did to the last file read (shown to the user)


def _repair_fallback(tris):
    """Local repair of the few defects AI exporters leave (pinched edges, duplicated
    triangles, small holes), then the normal reading again."""
    import repair as RP
    tris = np.asarray(tris, dtype=np.float64)
    verts = tris.reshape(-1, 3)
    q = np.round(verts / 1e-6 / max(1e-9, float(np.abs(verts).max()))).astype(np.int64)
    _, idx, inv = np.unique(q, axis=0, return_index=True, return_inverse=True)
    v, f, log = RP.repair(verts[idx], inv.reshape(-1, 3).astype(np.int64))
    # o reparo pode deixar uma aresta presa ao fechar dois furos que se tocam: repete, com um
    # anel maior em volta, até não sobrar aresta com mais de duas faces (no máximo 4 vezes)
    for rings in (3, 4, 5, 6):
        e = np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
        _, cnt = np.unique(e, axis=0, return_counts=True)
        if not (cnt != 2).any():
            break
        v, f, log2 = RP.repair(v, f, rings=rings)
        log += log2
    m = _tri_to_manifold(v[f])
    if m.status() == mf.Error.NoError and not m.is_empty():
        LAST_REPAIR.extend(['malha reparada'] + log)
    return m


def write_stl(manifolds) -> bytes:
    """Binary STL of one or more Manifolds."""
    if isinstance(manifolds, mf.Manifold):
        manifolds = [manifolds]
    tris = []
    for m in manifolds:
        me = m.to_mesh()
        v = np.asarray(me.vert_properties)[:, :3]
        f = np.asarray(me.tri_verts)
        tris.append(v[f])
    t = np.concatenate(tris) if tris else np.zeros((0, 3, 3))
    n = len(t)
    nrm = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    ln = np.linalg.norm(nrm, axis=1, keepdims=True)
    ln[ln == 0] = 1
    nrm = nrm / ln
    rec = np.zeros(n, dtype=[('n', '<f4', 3), ('v', '<f4', 9), ('a', '<u2')])
    rec['n'] = nrm
    rec['v'] = t.reshape(n, 9)
    out = io.BytesIO()
    out.write(b'EFC3D'.ljust(80, b' '))
    out.write(struct.pack('<I', n))
    out.write(rec.tobytes())
    return out.getvalue()


def mesh_arrays(m):
    me = m.to_mesh()
    return np.asarray(me.vert_properties)[:, :3].astype(np.float32), np.asarray(me.tri_verts).astype(np.uint32)


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def BOX(x0, x1, y0, y1, z0, z1):
    return mf.Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def flat(m):
    """Evaluate the lazy CSG tree (keeps memory and time bounded)."""
    return mf.Manifold(m.to_mesh())


def union(lst):
    lst = [x for x in lst if x is not None and not x.is_empty()]
    if not lst:
        return mf.Manifold()
    if len(lst) == 1:
        return lst[0]
    return mf.Manifold.batch_boolean(lst, mf.OpType.Add)


def rot_z(deg):
    a = math.radians(deg)
    R = np.eye(4)
    R[:2, :2] = [[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]]
    return R


def rot_x(deg):
    a = math.radians(deg)
    R = np.eye(4)
    R[1:3, 1:3] = [[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]]
    return R


def X(m, T):
    return m.transform(np.asarray(T, dtype=np.float64)[:3, :4])


def centroid(m):
    v, f = mesh_arrays(m)
    v = v.astype(np.float64)
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    vol = np.einsum('ij,ij->i', a, np.cross(b, c)) / 6.0
    tot = vol.sum()
    if abs(tot) < 1e-12:
        return v.mean(0)
    return ((a + b + c) / 4.0 * vol[:, None]).sum(0) / tot


def parts(m, min_vol=0.5):
    """Split into connected pieces (faster and leaner than Manifold.decompose when a cut
    leaves hundreds of dust specks). Pieces under min_vol mm3 are dropped."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    v, f = mesh_arrays(m)
    if len(f) == 0:
        return []
    nv = len(v)
    rows = np.concatenate([f[:, 0], f[:, 1]]).astype(np.int64)
    cols = np.concatenate([f[:, 1], f[:, 2]]).astype(np.int64)
    G = coo_matrix((np.ones(len(rows), dtype=np.int8), (rows, cols)), shape=(nv, nv))
    ncomp, lab = connected_components(G, directed=False)
    if ncomp == 1:
        return [m] if m.volume() >= min_vol else []
    froot = lab[f[:, 0]]
    vd = v.astype(np.float64)
    tv = np.einsum('ij,ij->i', vd[f[:, 0]], np.cross(vd[f[:, 1]], vd[f[:, 2]])) / 6.0
    vols = np.bincount(froot, weights=tv, minlength=ncomp)
    out, boxes = [], []
    for r in np.where(vols >= min_vol)[0]:
        ff = f[froot == r]
        used, inv = np.unique(ff, return_inverse=True)
        vu = v[used]
        mesh = mf.Mesh(vert_properties=np.ascontiguousarray(vu, dtype=np.float32),
                       tri_verts=np.ascontiguousarray(inv.reshape(-1, 3), dtype=np.uint32))
        out.append(mf.Manifold(mesh))
        boxes.append((vu.min(0), vu.max(0), float(vols[r])))
    if len(out) > 1 and (vols < -min(min_vol, 0.05)).any():
        # há um vazio fechado dentro de uma parte (a casca de dentro tem volume negativo). Cada parte
        # sai como sólido cheio, sem o vazio; uma ilha que estava DENTRO do vazio ficaria dentro do
        # sólido cheio, duas vezes o mesmo material (uma lasca solta dentro da peça). Ela fica com
        # a parte que a envolve.
        order = sorted(range(len(out)), key=lambda i: -boxes[i][2])
        drop = set()
        for a, i in enumerate(order):
            lo_i, hi_i, _ = boxes[i]
            for j in order[a + 1:]:
                if j in drop:
                    continue
                lo_j, hi_j, vj = boxes[j]
                if np.any(lo_j < lo_i - 1e-6) or np.any(hi_j > hi_i + 1e-6):
                    continue
                try:
                    if (out[i] ^ out[j]).volume() > 0.9 * vj:
                        drop.add(j)
                except Exception:
                    pass
        out = [m for k, m in enumerate(out) if k not in drop]
    return out


def fill_voids(m):
    """O mesmo sólido sem vazios fechados por dentro (bolhas). Uma bolha numa ferramenta de corte
    deixaria uma ilha solta do outro lado do corte, dentro da peça."""
    try:
        v, f = mesh_arrays(m)
        if len(f) == 0:
            return m
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components
        nv = len(v)
        rows = np.concatenate([f[:, 0], f[:, 1]]).astype(np.int64)
        cols = np.concatenate([f[:, 1], f[:, 2]]).astype(np.int64)
        ncomp, lab = connected_components(coo_matrix((np.ones(len(rows), dtype=np.int8), (rows, cols)), shape=(nv, nv)),
                                          directed=False)
        if ncomp == 1:
            return m
        vd = v.astype(np.float64)
        tv = np.einsum('ij,ij->i', vd[f[:, 0]], np.cross(vd[f[:, 1]], vd[f[:, 2]])) / 6.0
        if not (np.bincount(lab[f[:, 0]], weights=tv, minlength=ncomp) < 0).any():
            return m
        ps = parts(m, 0.0)
        return flat(union(ps)) if len(ps) > 1 else (ps[0] if ps else m)
    except Exception:
        return m


def contains_point(m, p, r=0.15):
    probe = BOX(p[0] - r, p[0] + r, p[1] - r, p[1] + r, p[2] - r, p[2] + r)
    return (m ^ probe).volume() > (2 * r) ** 3 * 0.25


def revolve_cs(cs, seg=72):
    """Revolve a CrossSection (x = radius >= 0, y = height) around local Z."""
    half = cs ^ mf.CrossSection.square([1000, 2000]).translate([0, -1000])
    if half.is_empty():
        return mf.Manifold()
    return mf.Manifold.revolve(half, seg)


def poly_cs(pts):
    pts = np.asarray(pts, dtype=np.float64)
    # positive orientation
    x, y = pts[:, 0], pts[:, 1]
    if 0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y) < 0:
        pts = pts[::-1]
    return mf.CrossSection([pts])


def joint_frame(j):
    """4x4 local->world. Local +Y = joint direction (towards the moving piece B), +Z up."""
    T = rot_z(j['angle'])
    T[:3, 3] = [j['x'], j['y'], j['z']]
    return T


def direction(j):
    a = math.radians(j['angle'])
    return np.array([-math.sin(a), math.cos(a), 0.0])


# ----------------------------------------------------------------------------
# automatic joint parameters
# ----------------------------------------------------------------------------
def top_height(m, x, y):
    hits = m.ray_cast([x, y, 1000.0], [x, y, -1000.0])
    return max((h.position[2] for h in hits), default=0.0) if hits else 0.0


def section_half_width(m, j, z):
    """Half width of the CONTINUOUS material around the joint point, measured across
    the joint direction at height z (first exit on each side, so legs or other parts
    further away are not counted)."""
    d = direction(j)
    perp = np.array([d[1], -d[0], 0.0])
    c = np.array([j['x'], j['y'], z])
    best = 0.0
    for s in (perp, -perp):
        hits = m.ray_cast(c.tolist(), (c + s * 500).tolist())
        if hits:
            best = max(best, min(float(np.linalg.norm(np.array(h.position) - c)) for h in hits))
    return best if best > 0 else 5.0


def _side_exits(m, c, perp):
    out = []
    for s in (perp, -perp):
        hits = m.ray_cast(c.tolist(), (c + s * 500).tolist())
        out.append(min(float(np.linalg.norm(np.array(h.position) - c)) for h in hits) if hits else 0.0)
    return out


def auto_fill(m, j):
    j = dict(j)
    if j.get('centrar', True) and j.get('z') in (None, '', 'auto'):
        # slide the joint sideways to the middle of the limb/body, so the hidden pin has
        # the same wall on both sides (the user clicks roughly, the engine centres)
        R = float(j['size'])
        d = direction(j)
        perp = np.array([d[1], -d[0], 0.0])
        for _ in range(2):
            h = top_height(m, j['x'], j['y'])
            zc = max(0.6, h * 0.45)
            off = []
            for t in (0.0, R + 2.4, 2 * R + 4.0):
                c = np.array([j['x'], j['y'], zc]) + d * t
                a, b = _side_exits(m, c, perp)
                if a > 0 and b > 0:
                    off.append((a - b) / 2)
            if not off:
                break
            o = float(np.clip(np.median(off), -5, 5))
            j['x'] = round(float(j['x']) + perp[0] * o, 2)
            j['y'] = round(float(j['y']) + perp[1] * o, 2)
    if j.get('z') in (None, '', 'auto'):
        h = top_height(m, j['x'], j['y'])
        R = float(j['size'])
        if j.get('type') == 'corrente':
            # chain: the link is centred in the height of the body at that spot
            j['z'] = round((h + bottom_height(m, j['x'], j['y'])) / 2, 2)
        elif j.get('type') == 'dobradica':
            # limbs: middle of the thinnest stretch the pin and its neck travel through
            d = direction(j)
            tops = [top_height(m, j['x'] + d[0] * t, j['y'] + d[1] * t) for t in np.linspace(0, 2 * R + 6, 6)]
            tops = [t for t in tops if t > 0] or [h]
            j['z'] = round(max(R + 1.4, min(tops) * 0.5), 2)
        else:
            j['z'] = round(max(R * 1.6 + 1.0, min(h * 0.45, h - R * 1.9 - 1.5)), 2)
    if j.get('width') in (None, '', 'auto'):
        # measure where the moving piece starts (just past the pin), not at the pivot,
        # so a leg joint measures the leg and not the body that holds the socket
        R = float(j['size'])
        d = direction(j)
        jb = dict(j)
        jb['x'] = j['x'] + d[0] * (R + 2.4)
        jb['y'] = j['y'] + d[1] * (R + 2.4)
        w = max(section_half_width(m, jb, j['z']), section_half_width(m, jb, max(0.6, j['z'] * 0.4)))
        j['width'] = round(w + 2.0, 2)
    return j


# ----------------------------------------------------------------------------
# joint cutters
# ----------------------------------------------------------------------------
_DIRS26 = [np.array(v, float) / np.linalg.norm(v) for v in
           [(a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1) if (a, b, c) != (0, 0, 0)]]


def _grow_safe(m, r):
    """Grow that reaches at least r in every direction (26 directions, worst case cos ~0.88)."""
    r = r / 0.87
    return flat(union([m] + [m.translate((d * r).tolist()) for d in _DIRS26]))


def _offset_smooth(m, r):
    """Smooth outward offset by r. Falls back to the fast approximate grow for big meshes."""
    c = m.simplify(0.06)
    if c.num_tri() > 30000:
        return _grow(c, r).simplify(0.03)
    try:
        return flat(c.minkowski_sum(mf.Manifold.sphere(r, 12))).simplify(0.02)
    except Exception:
        return _grow(c, r).simplify(0.03)


def _grow(m, r):
    return flat(union([m] + [m.translate((d * r).tolist()) for d in _DIRS]))


def on_skin(bit, S):
    """True when a loose bit reaches the outside of the model (losing it would leave a hole).
    Bits buried inside are just part of the hidden mechanism void and can be dropped."""
    bb = bit.bounding_box()
    Sl = flat(S ^ BOX(bb[0] - 1, bb[3] + 1, bb[1] - 1, bb[4] + 1, bb[2] - 1, bb[5] + 1))
    b = bit.simplify(0.02) if bit.num_tri() > 4000 else bit
    # nudging the bit outwards in any direction pokes out of the model only if it is on the skin
    for d in _DIRS:
        if (b.translate((d * 0.3).tolist()) - Sl).volume() > 0.01:
            return True
    return False


MIN_WALL = 1.2      # thinnest wall a piece may keep near a seam (mm): ~3 nozzle lines


def _zone_local(j, T):
    """The region this joint may cut, in its local frame (None = anywhere)."""
    z = j.get('zona')
    if z is None:
        return None
    return X(z.extrude(2000).translate([0, 0, -1000]), np.linalg.inv(T))


TRIM_OPENING = False
CUT_BAND = 1.3   # the thin-wall trim only acts this close to a cut (the skin elsewhere is never touched)


def _smooth_cut(slabs):
    """Layer slabs removed from one hanging bit would leave a saw-tooth edge. Each cluster of
    slabs is replaced by its convex hull (a clean flat cut), unless the hull is much bigger."""
    raw = flat(union(slabs))
    out = []
    for c in parts(raw, 0.0):
        h = c.hull()
        out.append(h if h.volume() <= 3.0 * c.volume() + 4.0 else c)
    return flat(union(out)) if out else raw


def trim_thin(piece, T, box_local, protect=None, t=MIN_WALL / 2, dz=0.25, S=None):
    """Clean a piece near a seam, layer by layer from the bed up, the way it will print:
      * flaps and knife edges thinner than MIN_WALL are removed;
      * anything the cut left floating (a layer region with nothing of the same piece under
        it) is removed too, up to where it joins supported material, so no island is left.
    Regions cut by the box border are kept (they are held up outside the box)."""
    Ti = np.linalg.inv(T)
    L = flat(X(piece, Ti) ^ box_local)
    if L.is_empty():
        return piece, 0.0
    SL = flat(X(S, Ti) ^ box_local) if S is not None else None
    bb = L.bounding_box()
    bx = box_local.bounding_box()
    bits = []
    prev = None
    for z in np.arange(bb[2] + dz / 2, bb[5], dz):
        cs = L.slice(z)
        # where this layer was cut (material of the original that this piece lost), widened a
        # little: only there may slivers be trimmed. Fine details of the original skin stay.
        band = None
        if SL is not None:
            lost = SL.slice(z) - cs
            band = lost.offset(CUT_BAND, mf.JoinType.Round) if not lost.is_empty() else mf.CrossSection()
        if cs.is_empty():
            prev = None
            continue
        # no layer-by-layer thinning: it carved one-layer grooves into the skin over the
        # hidden cavities. Only what the cut left hanging in the air is removed here.
        work = cs if not TRIM_OPENING else cs.offset(-t, mf.JoinType.Round).offset(t, mf.JoinType.Round) ^ cs
        if prev is not None:
            sup = prev.offset(dz + 0.05, mf.JoinType.Round)
            keep = []
            for c in work.decompose():
                cb = c.bounds()
                at_edge = (cb[0] <= bx[0] + 0.3 or cb[2] >= bx[3] - 0.3 or cb[1] <= bx[1] + 0.3 or cb[3] >= bx[4] - 0.3)
                if at_edge or (c ^ sup).area() > 0.02:
                    keep.append(c)
            work = mf.CrossSection.batch_boolean(keep, mf.OpType.Add) if keep else mf.CrossSection()
        gone = cs - work
        for c in gone.decompose():
            if band is not None and (band.is_empty() or (c ^ band).area() < 0.01):
                continue          # untouched skin of the original model: keep it exactly
            if c.area() > 0.05:
                bits.append(c.offset(0.05, mf.JoinType.Round).extrude(dz + 0.02).translate([0, 0, z - dz / 2 - 0.01]))
        prev = work if band is None else (cs - mf.CrossSection.batch_boolean(
            [c for c in gone.decompose() if not band.is_empty() and (c ^ band).area() >= 0.01] or [mf.CrossSection()],
            mf.OpType.Add))
    if not bits:
        return piece, 0.0
    cut = flat(X(_smooth_cut(bits), T))
    if protect is not None and not protect.is_empty():
        cut = flat(cut - protect)
    if cut.is_empty():
        return piece, 0.0
    out = flat(piece - cut)
    ps = sorted(parts(out, 0.5), key=lambda q: -q.volume())
    removed = piece.volume() - (ps[0].volume() if ps else 0)
    return (ps[0] if ps else piece), removed


def _split(S, j, Zb, sweep, yb, W, Lb, region, poses, domeA):
    """Two phases.
    1. Separate the pieces with only the thin static cuts (0.4 mm shell around the collar,
       0.4 mm slab at the seam, the hidden pin and socket). The moving piece B is whatever
       real material ends up on its side, so nothing is guessed from a box.
    2. Carve from the fixed piece A only the space B's real material sweeps when it turns.
    Parts of A that this carve would isolate are protected instead (they stay whole; the
    report then shows the reduced range), so the mesh never breaks into chips."""
    T = joint_frame(j)
    Ti = np.linalg.inv(T)
    K = X(BOX(-W - 3, W + 3, -(yb + 3), yb + Lb * 0.5, -500, 500), T)
    inK = parts(flat(S ^ K), 1.0)
    c = T[:3, 3].tolist()
    prot_l = mf.Manifold()
    if len(inK) > 1 and any(contains_point(p, c, 0.3) for p in inK):
        others = [p for p in inK if not contains_point(p, c, 0.3)]
        prot_l = _grow(flat(X(union(others), Ti)), 1.0)
        sweep = flat(sweep - prot_l)
    Zl = _zone_local(j, T)
    if Zl is not None:
        sweep = flat(sweep ^ Zl)
        Zb = Zb ^ Zl
        region = region ^ Zl
    Zb = flat(Zb)
    Rmax = math.hypot(W + j['clearance'], yb + 1.0) + 1.5

    def phase1(sw):
        Gc = flat(sw ^ BOX(-500, 500, -500, yb + Lb * 0.5, -500, 500))
        Gnear = flat(sw ^ BOX(-500, 500, -500, yb + 1.0, -500, 500) ^ mf.Manifold.sphere(Rmax, 64))
        Gnear = flat(Gnear - Zb)
        cut = flat(S - flat(X(Gc, T)))
        fr = [cc for cc in parts(cut, 1.0) if (Ti @ np.r_[centroid(cc), 1.0])[1] < 0]
        fr.sort(key=lambda q: -q.volume())
        Bm = flat(flat(S - flat(union(fr))) - flat(X(Gnear, T)))
        bc = sorted(parts(Bm, 0.5), key=lambda q: -q.volume())
        return fr, (bc[0] if bc else mf.Manifold()), bc[1:]

    front, B, frags = phase1(sweep)
    # bits buried inside the body are only void: drop them; bits on the skin must stay
    front = front[:1] + [q for q in front[1:] if on_skin(q, S)]
    frags = [q for q in frags if on_skin(q, S)]
    loose = front[1:] + frags
    if loose and front and not B.is_empty():
        # isolated bits: let them stay attached to the piece they touch
        f2, B2, fr2 = phase1(flat(sweep - _grow(flat(X(union(loose), Ti)), 1.0)))
        if f2 and not B2.is_empty() and B2.volume() > 0.5 * B.volume() and len(f2[1:] + fr2) < len(loose):
            front, B, frags = f2[:1] + [q for q in f2[1:] if on_skin(q, S)], B2, [q for q in fr2 if on_skin(q, S)]
    if B.is_empty() or not front:
        return front, mf.Manifold(), []
    # phase 2: real sweep of B
    chunk = flat(X(B, Ti) ^ region)
    if chunk.is_empty():
        return front, B, frags
    cl = j['clearance'] + 0.08
    # true offset (Minkowski with a small ball): the translated-copies grow left a saw-tooth
    # surface wherever this carve shows on the outside
    dil = _offset_smooth(chunk, cl)
    real = mf.Manifold()
    for i in range(0, len(poses), 8):
        real = flat(union([real] + [X(dil, P) for P in poses[i:i + 8]]))
    real = flat(real - domeA - prot_l)
    if j.get('estilo') == 'plana':
        # flat joint: carve only right at the arc seam. Carving the flank further away left
        # visible notches; there the range is reduced instead (the report shows the real range)
        rc_ = float(j['gola']) + 1.2
        real = flat(real ^ mf.Manifold.cylinder(2000, rc_, rc_, 96).translate([0, 0, -1000]))
    A0 = front[0]
    for _ in range(3):
        A = parts(flat(A0 - flat(X(real, T))), 0.5)
        A.sort(key=lambda q: -q.volume())
        if os.environ.get('FLEXI_DEBUG'):
            print('split phase2 parts', len(A), [round(q.volume(), 1) for q in A[:8]])
        A = A[:1] + [q for q in A[1:] if on_skin(q, S)]
        if len(A) <= 1:
            break
        # protect the isolated chunks (convex hull grown 1 mm: cheap and bounded in memory)
        real = flat(real - union([_grow(X(q, Ti).hull(), 1.0) for q in A[1:]]))
    box = BOX(-W - 4, W + 4, -yb - 4, yb + Lb * 0.5, -500, 500)
    # never trim around the pin, socket and keel: their thin parts are designed that way
    pr_ = float(j.get('_pin_r', 3.0)) + 1.5
    if j.get('_keep') is not None:
        keep = flat(X(j['_keep'], T))
    else:
        keep = flat(X(mf.Manifold.cylinder(1000, pr_, pr_, 48).translate([0, 0, -500])
                      + BOX(-pr_, pr_, -pr_, yb + 1.5, -500, 500), T))
    # the room B needs to turn is a union of many poses: on the skin that reads as a jagged
    # star. Each visible bite becomes its convex hull: one clean scoop.
    A[0] = _clean_bites(A0, A[0], S, keep)
    A0t, _ = trim_thin(A[0], T, box, protect=keep, S=S)
    Bt, _ = trim_thin(B, T, box, protect=keep, S=S)
    return [A0t] + A[1:] + front[1:], Bt, frags


def _clean_bites(before, after, S, keep):
    bites = parts(flat(before - after), 0.05)
    hulls = []
    for b in bites:
        if not on_skin(b, S):
            continue
        h = b.hull()
        if os.environ.get('FLEXI_DEBUG'):
            print('bite', round(b.volume(), 2), 'hull', round(h.volume(), 2))
        if h.volume() <= 2.5 * b.volume() + 3.0:
            hulls.append(h)
    if not hulls:
        return after
    cut = flat(flat(union(hulls)) - keep)
    out = sorted(parts(flat(after - cut), 0.5), key=lambda q: -q.volume())
    if not out or out[0].volume() < after.volume() - 25.0:
        return after
    return out[0]


def collar_radius(S, j):
    """Radius of the collar (gola). The collar is a surface of revolution around the pivot
    that contains the whole cross section at the cut: the fixed piece keeps a dome, the
    moving piece wraps around it, and the outside skin only gets a thin seam."""
    if j.get('gola') not in (None, '', 'auto'):
        return float(j['gola'])
    T = joint_frame(j)
    c, ex, ey, ez = T[:3, 3], T[:3, 0], T[:3, 1], T[:3, 2]
    if j['type'] == 'dobradica':
        # vertical cylinder: horizontal reach of the moving part around the axis
        best = float(j['width']) - 2.0
    else:
        best = 0.0
        for dy in (-1.0, 0.0, 1.0):
            o = c + ey * dy
            for a in np.radians(np.arange(0, 360, 15)):
                v = ex * math.cos(a) + ez * math.sin(a)
                hits = S.ray_cast(o.tolist(), (o + v * 300).tolist())
                if hits:
                    d = min(float(np.linalg.norm(np.array(h.position) - o)) for h in hits)
                    best = max(best, math.hypot(d, dy))
    pin = float(j['size']) + j['clearance'] + 2.0
    return round(max(best + 0.6, pin), 2)


def _dome_profile(R):
    """Sphere with 45 degree cones top and bottom (prints without supports)."""
    ang = np.radians(np.linspace(-45, 45, 30))
    pts = [(0, -R * math.sqrt(2))] + [(R * math.cos(a), R * math.sin(a)) for a in ang] + [(0, R * math.sqrt(2))]
    return poly_cs(pts)


_DIRS = [np.array(v, float) / np.linalg.norm(v) for v in
         [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1),
          (1, 1, 1), (1, 1, -1), (1, -1, 1), (1, -1, -1), (-1, 1, 1), (-1, 1, -1), (-1, -1, 1), (-1, -1, -1)]]


class SkinBreak(Exception):
    pass


WALL = 0.8   # minimum wall between the hidden pin/socket and the outside skin (mm)


def _check_skin(S, j, inner):
    """Raise SkinBreak if the hidden pin, socket or neck would come through the skin."""
    T = joint_frame(j)
    g = flat(X(flat(union([inner] + [inner.translate((d * WALL).tolist()) for d in _DIRS])), T))
    if '_floor' in j:                         # flat joint: the bottom is open on the bed by design
        gb = g.bounding_box()
        g = flat(g ^ BOX(gb[0] - 1, gb[3] + 1, gb[1] - 1, gb[4] + 1, float(j['_floor']) + 0.05, gb[5] + 1))
        if g.is_empty():
            return
    gb = g.bounding_box()
    Sl = flat(S ^ BOX(gb[0] - 2, gb[3] + 2, gb[1] - 2, gb[4] + 2, gb[2] - 2, gb[5] + 2))
    bad = 0.0
    for p in parts(flat(g - Sl), 0.02):
        bb = p.bounding_box()
        cx, cy = (bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2
        hits = Sl.ray_cast([cx, cy, -1000.0], [cx, cy, 1000.0])
        bottom = min((h.position[2] for h in hits), default=None)
        low = bottom + 2.0 if bottom is not None else 0.0
        if '_floor' in j:                      # flat joint: the lower band is underside
            low = max(low, float(j['_floor']) + float(j.get('_band', 2.0)))
        elif '_fin_top' in j:                  # keel slot: the opening under the fin is underside
            low = max(low, float(j['_fin_top']) + WALL + 0.2)
        elif '_pin_r' in j:                    # keel slot: anything below the pin is underside
            low = max(low, float(j['z']) - float(j['_pin_r']) + 0.2)
        if bottom is not None and bb[2] < bottom + 0.3 and bb[5] <= low and not j.get('_no_under'):
            continue            # opening on the underside, where the keel meets the bed
        bad += p.volume()
        if os.environ.get('FLEXI_SKIN_DEBUG'):
            print('  skin break part vol %.2f bb %s low %.2f bottom %s' % (p.volume(), [round(v, 1) for v in bb], low, None if bottom is None else round(bottom, 2)))
    if bad > 0.3:
        raise SkinBreak(bad)


FLAT_MIN_R = 2.0


def flat_ok(S, j, zmin):
    """The flat limb joint lies on the bed: the body must touch the bed around the pivot."""
    R0 = max(float(j['size']), FLAT_MIN_R)
    R = R0 - flat_dims(R0)[0] + 0.4          # the foot of the head must stand on the bed
    x, y = float(j['x']), float(j['y'])
    pts = [(x, y)] + [(x + R * math.cos(a), y + R * math.sin(a)) for a in np.radians(np.arange(0, 360, 45))]
    return all(bottom_height(S, px, py) <= zmin + 0.45 for px, py in pts)


def flat_dims(R):
    hc = min(1.4, 0.55 * R)          # 45 degree skirt: the head is wider on top (cannot drop out)
    v = 0.3
    ch = min(0.8, 0.35 * R)          # 45 degree chamfer on top: short bridge for the roof
    zt = hc + v + ch
    n = float(np.clip(2 * R - 2.0, 2.0, 3.2))   # neck width
    return hc, v, ch, zt, n


def flat_need(R, clr):
    """Body thickness the flat joint needs (head + gap + roof)."""
    return flat_dims(R)[3] + clr + WALL + 0.2


def flat_hinge_cut(S, j, zmin, zmax):
    """Flat limb joint (Komodo style): a T shaped tongue of the limb lies on the bed under a
    thin roof of the body. The disc head has a 45 degree skirt (wider on top) and a 45 degree
    chamfer, so nothing hangs in the air and the head cannot leave up, down or outwards.
    The seam is an arc around the pivot (vertical axis). Opens and closes only."""
    CLR = j['clearance']
    R = float(j['size'])
    th = float(j['yaw'])
    j['z'] = float(zmin)
    j['_floor'] = float(zmin)
    j['estilo'] = 'plana'
    hc, v, ch, zt, n = flat_dims(R)
    hn = hc + v
    Rc = max(float(j['gola']), R + 2 * CLR + 0.9)
    # the arc must span the whole width at the pivot line, or the flanks beside it get a
    # straight cut across (that read as a jagged notch on a tapering tail)
    hw = 0.0
    top = top_height(S, j['x'], j['y'])
    for zz in np.linspace(zmin + 0.4, max(zmin + 0.5, top - 0.4), 6):
        for dy in (0.0, -1.0):
            q = dict(j, x=j['x'] - direction(j)[0] * dy * -1, y=j['y'] - direction(j)[1] * dy * -1)
            hw = max(hw, section_half_width(S, q, zz))
    if hw < 30 and j.get('papel') != 'membro':      # body/tail: the arc spans the full width
        Rc = max(Rc, hw + 0.6)
    j['gola'] = round(Rc, 2)
    W = max(float(j['width']), Rc + 1.0)
    yb = Rc
    Lb = max(2 * W, Rc + W)
    z0, z1 = -1.0, zmax - zmin + 1.0
    # cut height: the top of the limb along the whole seam arc (first surface above the bed,
    # so a head or body hanging over the paw is not cut), never a flat cap through a slope
    T0 = joint_frame(j)
    tops = []
    for rr in (Rc - 0.8, Rc + 0.4, Rc + 1.5):
        for a in np.radians(np.arange(-80, 81, 10)):
            p = T0 @ np.array([rr * math.sin(a), rr * math.cos(a), 0.5, 1.0])
            hits = S.ray_cast([p[0], p[1], zmin + 0.5], [p[0], p[1], zmin + 500.0])
            if hits:
                tops.append(min(h.position[2] for h in hits))
    if tops:
        z1 = min(z1, max(tops) - zmin + 0.8)
    z1 = max(z1, zt + CLR + WALL + 0.4)
    H = z1 - z0
    prof = poly_cs([(0, 0), (R - hc, 0), (R, hc), (R, hn), (R - ch, zt), (0, zt)])
    head = revolve_cs(prof, 64)
    cav = revolve_cs(prof.offset(CLR, mf.JoinType.Miter, 3.0), 64)
    cav = flat(cav + mf.Manifold.cylinder(1.6, R - hc + CLR, R - hc + CLR, 64).translate([0, 0, -1.5]))
    neck = BOX(-n / 2, n / 2, 0, yb + 1, 0, hn)
    neck_o = BOX(-n / 2 - CLR, n / 2 + CLR, 0, yb + 1, z0 - 1, hn + CLR)
    pin_o = flat(cav + neck_o)
    domeB = mf.Manifold.cylinder(H, Rc, Rc, 96).translate([0, 0, z0])
    domeA = mf.Manifold.cylinder(H + 2, Rc - CLR, Rc - CLR, 96).translate([0, 0, z0 - 1])
    Zb = head + neck + (BOX(-W, W, 0, Lb, z0, z1) - domeB)
    angs = np.arange(-th, th + 0.01, 5.0)
    j['_pin_r'] = R + CLR
    j['_band'] = hn + CLR + WALL + 0.3   # the tongue slot may open on the underside of a rounded paw
    # only the roof over the head and the tongue itself are kept from the thin-wall trim;
    # below the roof, bits the cavity left hanging (rounded paw underside) are trimmed away
    rr = R + CLR + WALL + 0.6
    j['_keep'] = (mf.Manifold.cylinder(H + 2, rr, rr, 48).translate([0, 0, hn + CLR])
                  + BOX(-n / 2 - CLR - WALL, n / 2 + CLR + WALL, 0, yb, hn + CLR, z1 + 1)
                  + mf.Manifold.cylinder(zt + 0.2, R, R, 48).translate([0, 0, -0.5])
                  + BOX(-n / 2, n / 2, 0, yb + 1, -0.5, hn))
    _check_skin(S, j, flat(union([X(pin_o, rot_z(a)) for a in angs])) ^ BOX(-50, 50, -50, yb - 0.5, -50, 50))
    shell = (mf.Manifold.cylinder(H, Rc + CLR, Rc + CLR, 96).translate([0, 0, z0]) - domeA) \
        ^ BOX(-W - CLR, W + CLR, -CLR, Lb, z0, z1)
    slab = BOX(-W - CLR, W + CLR, -CLR, 0.0, z0, z1) - domeA
    ymax = (W + 2) * math.sin(math.radians(th)) + 2.0
    region = BOX(-W - 1, W + 1, 0, ymax, z0, z1) - domeB
    sw = flat(union([X(pin_o, rot_z(a)) for a in angs] + [shell, slab]))
    front, B, frags = _split(S, j, Zb, sw, yb, W, Lb, region, [rot_z(a) for a in np.arange(-th, th + 0.01, 1.25)], domeA)
    return front, B, frags, dict(socket_r=R + CLR, yb=yb, flat=True)


def hinge_cut(S, j, zmin, zmax):
    """Vertical-axis print-in-place hinge (keyhole neck + double-cone pin) inside a
    cylindrical collar. Side to side only. Uses the flat bed joint whenever the limb
    touches the bed (thin limbs fit, nothing in the air)."""
    # the flat bed joint held only by a 45 degree skirt came loose after printing: it is no
    # longer chosen automatically. Pin + socket locks in every direction.
    if j.get('estilo') == 'plana':
        return flat_hinge_cut(S, j, zmin, zmax)
    j['estilo'] = 'pino'
    j.pop('_floor', None)
    # the pin must have a floor of the socket under it (or the paw drops out downwards) and a
    # roof over it: put it at mid height and refuse where the part is too low for both
    _Rk = float(j['size'])
    _e = j['clearance'] * math.sqrt(2)
    zbot = bottom_height(S, j['x'], j['y'])
    dv_ = direction(j)
    tops_ = [top_height(S, j['x'] + dv_[0] * t_, j['y'] + dv_[1] * t_) for t_ in (0.0, _Rk, 2 * _Rk)]
    tops_ = [t_ for t_ in tops_ if t_ > zbot] or [zbot]
    ztop = min(tops_)
    # below the pin only its shoulders need material of the socket under them (the stem goes
    # down to the bed): shoulder height = Rk - stem half width
    _n = max(1.2, 0.6 * _Rk)
    lo_ = zbot + (_Rk - _n / 2) + _e + 0.8
    hi_ = ztop - _Rk - _e - WALL - 0.2
    if hi_ < lo_:
        raise SkinBreak(10.0 + (lo_ - hi_))
    j['z'] = round(min(max(lo_, (zbot + ztop) / 2.0), hi_), 2)
    CLR = j['clearance']
    Rk = float(j['size'])
    W = float(j['width'])
    th = float(j['yaw'])
    zc = j['z']
    e = CLR * math.sqrt(2)
    n, hn = max(1.2, 0.6 * Rk), 1.0 * Rk
    j['_pin_r'] = Rk + e
    Rc = max(float(j['gola']), Rk + e + CLR + WALL + 0.6)
    if j.get('papel') != 'membro':
        # body/tail: the arc spans the full width at the pivot line (no straight cut beside it)
        hw = 0.0
        top = top_height(S, j['x'], j['y'])
        dv0 = direction(j)
        for zz in np.linspace(zmin + 0.4, max(zmin + 0.5, top - 0.4), 6):
            for dy in (0.0, -1.0):
                q = dict(j, x=j['x'] + dv0[0] * dy, y=j['y'] + dv0[1] * dy)
                hw = max(hw, section_half_width(S, q, zz))
        if hw < 30:
            Rc = max(Rc, hw + 0.6)
    j['gola'] = round(Rc, 2)
    W = max(W, Rc + 1.0)
    yb = Rc
    Lb = max(2 * W, Rc + W)
    z0, z1 = zmin - zc - 1.0, zmax - zc + 1.0
    # a limb hinge only cuts up to the top of the limb (not the cheek or body above it)
    d = direction(j)
    pb = np.array([j['x'], j['y'], zc]) + d * (Rk + 2.4)
    hits = S.ray_cast(pb.tolist(), (pb + np.array([0, 0, 500.0])).tolist())
    if hits:
        ztop = min(h.position[2] for h in hits)
        z1 = min(z1, ztop - zc + 0.6)
    z1 = max(z1, Rk + 1.5)
    H = z1 - z0
    domeB = mf.Manifold.cylinder(H, Rc, Rc, 96).translate([0, 0, z0])
    domeA = mf.Manifold.cylinder(H + 2, Rc - CLR, Rc - CLR, 96).translate([0, 0, z0 - 1])
    dia = revolve_cs(poly_cs([(0, -Rk), (Rk, 0), (0, Rk)]))
    dia_o = revolve_cs(poly_cs([(0, -Rk - e), (Rk + e, 0), (0, Rk + e)]))
    # keel: the pin stands on a vertical fin that goes down to the bed, so nothing of the
    # moving piece starts in mid air (no floating island, no support)
    # the fin only rises into the lower cone of the pin: the slot it needs in the socket stays
    # low (an opening on the underside) and the socket keeps its full cones above and below
    fin_top = -0.3 * Rk
    j['_fin_top'] = zc + fin_top + CLR
    Zb = dia + BOX(-n / 2, n / 2, -n / 2, yb + 1, z0, fin_top) + (BOX(-W, W, 0, Lb, z0, z1) - domeB)
    pin_o = flat(dia_o + BOX(-n / 2 - CLR, n / 2 + CLR, -n / 2 - CLR, yb + 1, z0 - 1, fin_top + CLR))
    angs = np.arange(-th, th + 0.01, 5.0)
    _check_skin(S, j, flat(union([X(pin_o, rot_z(a)) for a in angs])) ^ BOX(-50, 50, -50, yb - 0.5, -50, 50))
    shell = (mf.Manifold.cylinder(H, Rc + CLR, Rc + CLR, 96).translate([0, 0, z0]) - domeA) \
        ^ BOX(-W - CLR, W + CLR, -CLR, Lb, z0, z1)
    slab = BOX(-W - CLR, W + CLR, -CLR, 0.0, z0, z1) - domeA
    ymax = (W + 2) * math.sin(math.radians(th)) + 2.0
    region = BOX(-W - 1, W + 1, 0, ymax, z0, z1) - domeB
    sw = flat(union([X(pin_o, rot_z(a)) for a in angs] + [shell, slab]))
    front, B, frags = _split(S, j, Zb, sw, yb, W, Lb, region, [rot_z(a) for a in np.arange(-th, th + 0.01, 1.25)], domeA)
    return front, B, frags, dict(socket_r=Rk + e, yb=yb)


def _ball_profile(R):
    ang = np.radians(np.linspace(-45, 90, 40))
    pts = [(0, -R * math.sqrt(2))] + [(R * math.cos(a), R * math.sin(a)) for a in ang]
    return poly_cs(pts)


def ball_cut(S, j, zmin, zmax):
    """Ball joint: side to side AND up/down, inside a spherical collar. Ball has a 45 deg
    cone underside, the socket has a 45 deg cone roof, so it prints without supports."""
    CLR = j['clearance']
    Rb = float(j['size'])
    W = float(j['width'])
    yaw, pitch = float(j['yaw']), float(j['pitch'])
    zc = j['z']
    rn = 0.42 * Rb
    Ro = Rb + CLR
    Rs = float(j['gola'])
    W = max(W, Rs + 1.0)
    yb = Rs
    Lb = max(2 * W, Rs + W)
    z0, z1 = zmin - zc - 1.0, zmax - zc + 1.0
    Ry = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1.0]])   # cylinder +Z -> +Y
    ball = revolve_cs(_ball_profile(Rb))
    # keel: ball and neck stand on a vertical fin down to the bed (no floating island)
    neck = X(mf.Manifold.cylinder(yb + 1, rn, rn, 32), Ry) + BOX(-rn, rn, -rn, yb + 1, z0, 0)
    neck_o = flat(X(mf.Manifold.cylinder(yb + 1, rn + CLR, rn + CLR, 32), Ry)
                  + BOX(-rn - CLR, rn + CLR, -rn - CLR, yb + 1, z0 - 1, 0))
    domeB = revolve_cs(_dome_profile(Rs), 96)
    pv = [-pitch, 0.0, pitch] if pitch else [0.0]
    dA = revolve_cs(_dome_profile(Rs).offset(-CLR, mf.JoinType.Miter), 96)
    domeA = dA
    for p in pv:
        if p:
            domeA = domeA ^ X(dA, rot_x(p))
    domeA = flat(domeA)
    Zb = ball + neck + (BOX(-W, W, 0, Lb, z0, z1) - domeB)
    # socket = profile swept through +-pitch, revolved (superset of every tilt)
    prof = _ball_profile(Rb).offset(CLR, mf.JoinType.Miter)
    full = prof + prof.mirror([1, 0])
    env = union_cs([full.rotate(a) for a in np.linspace(-pitch, pitch, 7)])
    sock = revolve_cs(env)
    zt = Ro * math.sqrt(2) * (math.cos(math.radians(pitch)) + math.sin(math.radians(pitch)))
    roof = revolve_cs(poly_cs([(0, 0), (Ro, 0), (Ro, max(zt - Ro, 0.01)), (0, zt)]))
    yv = np.arange(-yaw, yaw + 0.01, 5.0)
    neck_s = flat(union([mf.Manifold.batch_hull([X(neck_o, rot_z(a) @ rot_x(p)) for p in pv]) for a in yv]))
    if pitch:
        # tilting the neck leaves a sloped ceiling in the fixed piece, which the slicer would
        # support. Lift it to one flat ceiling (a bridge, anchored all round, no support) and
        # keep the socket roof around the ball so it stays locked.
        Zt = neck_s.bounding_box()[5]
        rect = mf.CrossSection.square([2 * (rn + CLR), yb + 1 + rn + CLR]).translate([-(rn + CLR), -(rn + CLR)])
        foot = (union_cs([rect.rotate(a) for a in np.arange(-yaw, yaw + 0.01, 2.5)])
                - mf.CrossSection.circle(Ro + 1.0, 64)) \
            ^ mf.CrossSection.square([200, 200]).translate([-100, 0])
        if not foot.is_empty():
            neck_s = flat(neck_s + foot.extrude(Zt))
    _check_skin(S, j, flat(union([sock, roof, neck_s])) ^ BOX(-50, 50, -50, yb - 0.5, -50, 50))
    boxo = BOX(-W - CLR, W + CLR, -CLR, Lb, z0, z1)
    dB = revolve_cs(_dome_profile(Rs + CLR), 96)
    env_B = union([X(dB, rot_x(p)) for p in pv])
    shell = (boxo - domeA) ^ env_B
    slab = BOX(-W - CLR, W + CLR, -CLR, 0.0, z0, z1) - domeA
    poses = [rot_z(a) @ rot_x(p) for a in yv for p in pv]
    reach = max(W, z1, -z0) + 2
    ymax = reach * math.sin(math.radians(max(yaw, pitch))) + 2.0
    region = BOX(-W - 1, W + 1, 0, ymax, z0, z1) - domeB
    sw = flat(union([sock, neck_s, flat(shell), flat(slab), roof]))
    front, B, frags = _split(S, j, Zb, sw, yb, W, Lb, region, poses, domeA)
    return front, B, frags, dict(socket_r=Ro, yb=yb)



# ----------------------------------------------------------------------------
# chain joint (corrente): two interlocked links, prints without supports
# ----------------------------------------------------------------------------
BODY_JOINT = os.environ.get('FLEXI_BODY', 'cutter')   # 'cutter' (FJM loops) or 'elo' (old chain)
TAN_LINK = math.tan(math.radians(40))   # link legs rise at 40 deg (slicers support below 30)


def bottom_height(m, x, y):
    hits = m.ray_cast([x, y, -1000.0], [x, y, 1000.0])
    return min((h.position[2] for h in hits), default=0.0) if hits else 0.0


def _oct_pts(c, r):
    c = np.asarray(c, dtype=float)
    return [c + np.array(v, dtype=float) for v in
            ((r, 0, 0), (-r, 0, 0), (0, r, 0), (0, -r, 0), (0, 0, r), (0, 0, -r))]


def _hullp(pts):
    return mf.Manifold.hull_points([[float(a), float(b), float(c)] for a, b, c in pts])


def _wave_cs(Wc, a, y0, y1, ext=4.0, n=48):
    """2D strip (top view) between y0+f(x) and y1+f(x); f is an S across the body."""
    xs = np.linspace(-Wc, Wc, n)
    f = a * np.sin(np.pi * xs / Wc)
    xs = np.r_[-Wc - ext, xs, Wc + ext]
    f = np.r_[0.0, f, 0.0]
    pts = [(x, y0 + v) for x, v in zip(xs, f)] + [(x, y1 + v) for x, v in zip(xs[::-1], f[::-1])]
    return poly_cs(pts)


def chain_plan(S, j):
    """Sizes of the chain joint at this spot. Returns a dict or raises SkinBreak."""
    CLR = j['clearance']
    r = float(j['size'])
    T = joint_frame(j)
    # cross section of the body at the seam (local x across, local z up)
    cs = X(S, rot_x(-90) @ np.linalg.inv(T)).slice(0.0)
    sec = None
    for comp in cs.decompose():
        if (comp ^ mf.CrossSection.square([0.4, 0.4]).translate([-0.2, -0.2])).area() > 0.01:
            sec = comp
            break
    if sec is None:
        raise SkinBreak(1.0)
    bx = sec.bounds()
    w = max(-bx[0], bx[2], 2.0)
    zb, zt = bx[1], bx[3]
    g = CLR
    ce = CLR * math.sqrt(3)          # clearance measured with octahedra (>= CLR everywhere)
    e = max(0.8, 0.6 * r)            # how deep the link roots go into the fixed piece
    b = max(1.6, r)                  # thickness of the bar of the moving piece inside the link
    yaw, pitch = float(j['yaw']), float(j['pitch'])
    sp = math.sin(math.radians(pitch))
    s_need = max(w * math.sin(math.radians(yaw)), zt * sp, -zb * sp) + 0.3
    if r + ce + WALL > w:
        raise SkinBreak(r + ce + WALL - w)
    t = TAN_LINK
    hb = 0.9                         # half height of the bar at its front edge
    K = g + b + (hb + r + ce) / t    # link reach without slack
    half = r + ce + 1.0
    s = s_need
    for _ in range(3):
        # height available above and below the link centre, across the width the link uses
        col = sec ^ mf.CrossSection.square([2.0 * half, 400]).translate([-half, -200])
        cb = col.bounds() if not col.is_empty() else bx
        hh = min(cb[3], -cb[1])
        # vertical reach of the link space: legs + tube + clearance + slack + tilt + wall
        room = hh - r - ce - WALL - 0.3 - (K + e) * t
        s_max = room / t
        if s_max < 0.6:
            raise SkinBreak(0.6 - s_max)
        s = min(s_need, s_max, float(j.get('_s_cap', 1e9)))
        Ya = K + s
        sx = min(Ya * math.sin(math.radians(yaw)), max(0.0, w - r - ce - WALL - 0.5))
        half = r + ce + sx + 1.0
    sz = 0.3
    Wc = w + 2.0
    amp = min(0.18 * Wc, 0.45 * s, 3.0)
    # bending that the slack alone gives; the rest can come from a thin V opening in the
    # seam, paid from the shape budget (volume the user allows to lose)
    hmax = max(zt, -zb, 1.0)
    by = math.degrees(math.asin(min(1.0, max(0.0, s - 0.3) / w)))
    bp = math.degrees(math.asin(min(1.0, max(0.0, s - 0.3) / hmax)))
    dyaw, dpitch = max(0.0, yaw - by), max(0.0, pitch - bp)
    mx = mz = 0.0
    n = 40
    for i in range(n):
        x0 = bx[0] + (bx[2] - bx[0]) * i / n
        x1 = bx[0] + (bx[2] - bx[0]) * (i + 1) / n
        a = (sec ^ mf.CrossSection.square([x1 - x0, 400]).translate([x0, -200])).area()
        mx += abs((x0 + x1) / 2) * a
        z0_ = bx[1] + (bx[3] - bx[1]) * i / n
        z1_ = bx[1] + (bx[3] - bx[1]) * (i + 1) / n
        a = (sec ^ mf.CrossSection.square([400, z1_ - z0_]).translate([-200, z0_])).area()
        mz += abs((z0_ + z1_) / 2) * a
    need = math.tan(math.radians(dyaw)) * mx + math.tan(math.radians(dpitch)) * mz
    budget = float(j.get('orcamento') or 0.0)
    k = 1.0 if need <= budget or need <= 0 else budget / need
    vy = math.degrees(math.atan(k * math.tan(math.radians(dyaw))))
    vp = math.degrees(math.atan(k * math.tan(math.radians(dpitch))))
    return dict(r=r, w=w, zt=zt, zb=zb, g=g, ce=ce, e=e, b=b, s=s, s_need=s_need, Ya=Ya,
                sx=sx, sz=sz, Wc=Wc, amp=amp, v_lado=vy, v_cima=vp,
                giro_folga=[by, bp], giro_previsto=[min(yaw, by + vy), min(pitch, bp + vp)])


def chain_cut(S, j, zmin, zmax):
    """Try the chain joint; if its hidden link space would touch the skin, shrink the slack
    (less bend from the link, the V seam pays the rest) before giving up."""
    last = None
    for cap in (None, 0.7, 0.45, 0.25):
        q = dict(j)
        if cap is not None:
            base_s = chain_plan(S, dict(j))['s']
            q['_s_cap'] = max(0.6, base_s * cap)
        try:
            out = _chain_cut(S, q, zmin, zmax)
            j.update({k: v for k, v in q.items() if k.startswith('_')})
            return out
        except SkinBreak as ex:
            last = ex
    raise last


def _chain_cut(S, j, zmin, zmax):
    """Chain joint. The fixed piece A grows a pointed link (45 degree legs, octahedral tube)
    that reaches into the moving piece B and loops around a bar of B. The two pieces are
    separated by a thin S-shaped seam. B can pull away by the slack s, which is what lets it
    bend: it pivots on the inner edge of the seam. Every surface is 45 degrees or steeper,
    or a short bridge, so nothing needs support."""
    P = chain_plan(S, j)
    r, g, ce, e, s, Ya, sx, sz, Wc, amp = (P[k] for k in ('r', 'g', 'ce', 'e', 's', 'Ya', 'sx', 'sz', 'Wc', 'amp'))
    zc = j['z']
    z0, z1 = zmin - zc - 1.0, zmax - zc + 1.0
    T = joint_frame(j)
    Ti = np.linalg.inv(T)
    hz = (Ya + e) * TAN_LINK
    P0, P1, P2 = (0, -e, -hz), (0, Ya, 0), (0, -e, hz)
    link = flat(_hullp(_oct_pts(P0, r) + _oct_pts(P1, r)) + _hullp(_oct_pts(P1, r) + _oct_pts(P2, r)))
    # space the link needs inside B: every position it takes while B pulls away (0..s),
    # shifts sideways and tilts (slack), grown by the clearance. D has 45 degree faces only.
    shifts = []
    for dx in (-sx, sx):
        for dy, dz in ((0, 0), (-s, 0), (-s / 2, sz), (-s / 2, -sz)):
            shifts.append(np.array([dx, dy, dz]))
    cav = []
    for A_, B_ in ((P0, P1), (P1, P2)):
        base_pts = _oct_pts(A_, r + ce) + _oct_pts(B_, r + ce)
        cav.append(_hullp([p + t for p in base_pts for t in shifts]))
    cav = flat(union(cav))
    tv, tp = math.tan(math.radians(P['v_lado'])), math.tan(math.radians(P['v_cima']))
    g = g * math.sqrt(1.0 + (P['amp'] * math.pi / Wc) ** 2)   # keep 0.4 mm square to the S
    H = z1 - z0 + 2
    # B starts after the S seam; a thin V (if the budget pays for it) opens towards the sides
    # and towards top and bottom, which is what lets B tip further than the slack alone
    xs = np.linspace(-Wc - 4, Wc + 4, 97)
    f = np.where(np.abs(xs) <= Wc, P['amp'] * np.sin(np.pi * np.clip(xs, -Wc, Wc) / Wc), 0.0)
    topB = poly_cs([(x, v + g + tv * abs(x)) for x, v in zip(xs, f)] + [(xs[-1], 500), (xs[0], 500)])
    zs = np.linspace(z0 - 1, z1 + 1, 61)
    sideB2 = poly_cs([(g + tp * abs(z), z) for z in zs] + [(500, zs[-1]), (500, zs[0])])
    L = 2 * (Wc + 10)
    sideB = X(sideB2.extrude(L), np.array([[0, 0, 1, -L / 2], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1.0]]))
    Bhalf = flat(topB.extrude(H).translate([0, 0, z0 - 1]) ^ sideB)
    Ahalf = poly_cs([(x, v) for x, v in zip(xs, f)] + [(xs[-1], -500), (xs[0], -500)]).extrude(H).translate([0, 0, z0 - 1])
    ymax = g + tv * (Wc + 4) + tp * max(abs(z0), abs(z1)) + P['amp'] + 1.0
    zone = BOX(-Wc - 4, Wc + 4, -P['amp'] - 1.0, ymax, z0 - 1, z1 + 1)
    gap = flat(zone - Ahalf - Bhalf)
    cav = flat(cav ^ Bhalf)
    _check_skin(S, j, flat(link + cav))
    # protect other parts that pass through the cutting zone
    K = X(BOX(-Wc - 4, Wc + 4, -(e + r + 3), Ya + r + 4, -500, 500), T)
    inK = parts(flat(S ^ K), 1.0)
    cpt = T[:3, 3].tolist()
    prot = mf.Manifold()
    if len(inK) > 1:
        holder = [p for p in inK if contains_point(p, cpt, 0.3) or contains_point(p, (T @ [0, -1.5, 0, 1])[:3].tolist(), 0.3)]
        others = [p for p in inK if not any(p is h for h in holder)]
        if others:
            prot = _grow(flat(X(union(others), Ti)), 1.0)
    Zl = _zone_local(j, T)
    if Zl is not None:
        gap = flat(gap ^ Zl)
        cav = flat(cav ^ Zl)
    cutter = flat(flat(gap + cav) - prot)
    cut = flat(S - flat(X(cutter, T)))
    front, back = [], []
    for cc in parts(cut, 1.0):
        (front if (Ti @ np.r_[centroid(cc), 1.0])[1] < 0 else back).append(cc)
    front.sort(key=lambda q: -q.volume())
    back.sort(key=lambda q: -q.volume())
    front = front[:1] + [q for q in front[1:] if on_skin(q, S)]
    back = back[:1] + [q for q in back[1:] if on_skin(q, S)]
    if not front or not back:
        return front, mf.Manifold(), [], {}
    box = BOX(-Wc - 4, Wc + 4, -(e + r + 4), Ya + r + 5, -500, 500)
    keep = flat(X(_grow(link, 0.6), T))
    A0, _ = trim_thin(front[0], T, box, protect=keep, S=S)
    keepB = flat(X(BOX(-(r + ce + sx + 1.5), r + ce + sx + 1.5, -1.0, Ya + r + 1.5,
                       -(hz + r + 1.5), hz + r + 1.5), T))
    Bt, _ = trim_thin(back[0], T, box, protect=keepB, S=S)
    back = [Bt] + back[1:]
    A = flat(A0 + X(link, T))
    info = dict(socket_r=r + 1.0, yb=Ya, slack=round(s, 2), Ya=Ya, v=[P['v_lado'], P['v_cima']],
                probeA=(T @ [0, -min(2.5, e + r), 0, 1])[:3].tolist(),
                probeB=(T @ [0, g + P['b'] / 2, 0, 1])[:3].tolist(),
                plan={k: (round(v, 2) if isinstance(v, float) else v) for k, v in P.items()})
    return [A] + front[1:], back[0], back[1:], info


# ----------------------------------------------------------------------------
# body joint from a proven flexi cutter (FlexiJointMaker negative)
# ----------------------------------------------------------------------------
# The cutter is a negative volume: a flat seam plate with two interlocked loops crossing it,
# one owned by each side. In its own file: plate normal = +X (x 4.08..6.85), loops core
# 13.8 wide (Y) x 12.6 high (Z), clearance 0.52 mm, plate a disc of radius ~17.
FJM_PX = (4.08, 6.85)
FJM_CEN = np.array([(4.08 + 6.85) / 2, -1.0, 12.85])
FJM_W, FJM_H, FJM_D, FJM_CLR, FJM_DISC = 13.8, 12.6, 13.1, 0.52, 16.5
FJM_MIN_S = 0.75        # below this the loops get thinner than ~2.3 mm: not strong enough
FJM_MAX_S = 1.6
BODY_MASK = True       # body cuts follow the border of the section that holds the joint
BODY_SN = 1.6          # max scale along the seam normal (no cap: the seam width is what lets the body bend)
CUT_WALL = 1.6          # skin around the hidden loops
_FJM = {}


def _fjm_local():
    """Cutter in joint-local units (scale 1): plate normal = local +Y, centred on the origin.
    Returns (full cutter, loops only). 1.50: the third-party FJM negative left the app; the own joint made in
    its place (Arco, RLA) is used, already in the library frame (seam plate on y = 0)."""
    if 'c' not in _FJM:
        import json
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cutters', 'lib')
        meta = json.load(open(os.path.join(d, 'biblioteca.json'), encoding='utf-8'))['rla_arco']
        C = read_stl(open(os.path.join(d, meta['arquivo']), 'rb').read())
        th = float(meta['placa'])
        loops = flat(C - BOX(-100, 100, -th / 2 - 0.02, th / 2 + 0.02, -100, 100))
        _FJM['c'], _FJM['l'], _FJM['th'] = C, loops, th
    return _FJM['c'], _FJM['l'], _FJM['th']


def _section_local(S, T):
    cs = X(S, rot_x(-90) @ np.linalg.inv(T)).slice(0.0)
    for comp in cs.decompose():
        if (comp ^ mf.CrossSection.square([0.4, 0.4]).translate([-0.2, -0.2])).area() > 0.01:
            return comp
    return None


def cutter_plan(S, j):
    """Scale and height of the cutter here. Section coords: x across, y = local z (up).
    Returns (s, dz) with dz the centre height relative to j['z'], or raises SkinBreak."""
    T = joint_frame(j)
    sec = _section_local(S, T)
    if sec is None:
        raise SkinBreak(1.0)
    bx = sec.bounds()
    w = max(-bx[0], bx[2])
    s = FJM_MAX_S
    dz = 0.0
    for _ in range(4):
        half = FJM_W * s / 2 + CUT_WALL
        # the loops reach D/2 into each side: the body must be tall and wide enough over that
        # whole length, not only at the seam
        secs = [sec]
        for yq in (-FJM_D * min(s, BODY_SN) / 2, -FJM_D * min(s, BODY_SN) / 4, FJM_D * min(s, BODY_SN) / 4, FJM_D * min(s, BODY_SN) / 2):
            Tq = T.copy()
            Tq[:3, 3] = (T @ [0, yq, 0, 1])[:3]
            sq = _section_local(S, Tq)
            if sq is None:
                raise SkinBreak(1.0)
            secs.append(sq)
        zt, zb = 1e9, -1e9
        for sq in secs:
            w = min(w, max(-sq.bounds()[0], sq.bounds()[2])) if sq is not sec else w
            for xq in np.linspace(-half, half, 7):
                strip = sq ^ mf.CrossSection.square([0.3, 400]).translate([xq - 0.15, -200])
                if strip.is_empty():
                    continue            # wider than the body here: the width limit below shrinks it
                b_ = strip.bounds()
                zt, zb = min(zt, b_[3]), max(zb, b_[1])
        s_h = (zt - zb - 2 * CUT_WALL) / FJM_H
        s_w = (2 * w - 2 * CUT_WALL) / FJM_W
        s_new = min(FJM_MAX_S, s_h, s_w)
        dz = (zt + zb) / 2
        if abs(s_new - s) < 0.02:
            s = s_new
            break
        s = s_new
    if s < FJM_MIN_S:
        raise SkinBreak(FJM_MIN_S - s)
    return s, dz, dict(w=w, zt=bx[3], zb=bx[1])


def cutter_cut(S, j, zmin, zmax):
    """Body joint with the FJM cutter: A and B each own one loop, interlocked through a flat
    seam. Same return as _chain_cut: (front pieces, B, other back pieces, info)."""
    C0, L0, th0 = _fjm_local()
    s, dz, geo = cutter_plan(S, j)
    last = None
    for f_ in (1.0, 0.92, 0.85):
        sc = s * f_
        if sc < FJM_MIN_S:
            break
        try:
            return _cutter_cut(S, dict(j), j, sc, dz, geo, C0, L0, th0)
        except SkinBreak as ex:
            last = ex
    raise last or SkinBreak(1.0)


def section_mask(S, T, ys, margin=0.8, core_only=True):
    """3D region, in the joint's local frame, that a body cut may touch: at each local y in ys
    the model is sliced by the plane of the seam and only the piece of section that holds the
    joint point is kept (parts that merely cross the same plane, like a paw under the head, are
    left alone; parts glued to it at that spot belong to the same piece of section and are cut
    with it). The pieces are joined, grown by `margin` and swept over the y range."""
    secs = []
    for yq in ys:
        Tq = T.copy()
        Tq[:3, 3] = (T @ [0, yq, 0, 1])[:3]
        sq = _section_local(S, Tq)
        if sq is not None:
            secs.append(sq)
    if not secs:
        return None
    cs = secs[0]
    for sq in secs[1:]:
        cs = cs + sq
    if core_only:
        # keep the body, drop thin lobes stuck to it in this section (a leg or paw that leaves
        # the body right here): an opening with a radius set by the section's own size
        b = cs.bounds()
        r = max(1.5, 0.22 * min(b[2] - b[0], b[3] - b[1]))
        op = cs.offset(-r, mf.JoinType.Round).offset(r, mf.JoinType.Round)
        if not op.is_empty():
            best = None
            for comp in op.decompose():
                if (comp ^ mf.CrossSection.square([0.4, 0.4]).translate([-0.2, -0.2])).area() > 0.01:
                    best = comp
            if best is None:
                best = max(op.decompose(), key=lambda c_: c_.area())
            cs = best
    cs = cs.offset(margin, mf.JoinType.Round)
    y0, y1 = min(ys) - 50.0, max(ys) + 50.0
    # section coordinates: the slice is taken in X(S, rot_x(-90) @ inv(T)) at z = 0
    pr = cs.extrude(y1 - y0).translate([0, 0, y0])
    return X(pr, np.linalg.inv(rot_x(-90)))


def _cutter_cut(S, q, j, s, dz, geo, C0, L0, th0):
    q['z'] = float(q['z']) + dz
    T = joint_frame(q)
    Ti = np.linalg.inv(T)
    CLR = float(q['clearance'])
    sn = min(s, BODY_SN)          # seam thickness and loop depth stay moderate on big loops
    Sc = np.diag([s, sn, s, 1.0])
    cut_l = X(C0, Sc)
    loops = X(L0, Sc)
    th = th0 * sn
    d_off = max(0.0, (CLR + 0.04 - FJM_CLR * min(s, sn)) / 2)
    # the hidden loops must keep CUT_WALL of skin around them (underside openings on the bed
    # are allowed by _check_skin like for the pins)
    q2 = dict(q, _no_under=True)
    _check_skin(S, q2, flat(_offset_smooth(loops, d_off + CUT_WALL - WALL)))
    # seam outside the cutter's own plate: a flat slab of the plate thickness, opening into a
    # thin V towards the sides and top/bottom when the shape budget pays for it
    sec = _section_local(S, T)
    bx = sec.bounds()
    w = max(-bx[0], bx[2], 2.0)
    hmax = max(bx[3], -bx[1], 1.0)
    mx = mz = 0.0
    n = 30
    for i in range(n):
        x0 = bx[0] + (bx[2] - bx[0]) * i / n
        x1 = bx[0] + (bx[2] - bx[0]) * (i + 1) / n
        a = (sec ^ mf.CrossSection.square([x1 - x0, 400]).translate([x0, -200])).area()
        mx += abs((x0 + x1) / 2) * a
        z0_ = bx[1] + (bx[3] - bx[1]) * i / n
        z1_ = bx[1] + (bx[3] - bx[1]) * (i + 1) / n
        a = (sec ^ mf.CrossSection.square([400, z1_ - z0_]).translate([-200, z0_])).area()
        mz += abs((z0_ + z1_) / 2) * a
    yaw, pitch = float(q['yaw']), float(q['pitch'])
    by = math.degrees(math.atan(th / w))
    bp = math.degrees(math.atan(th / hmax))
    dyaw, dpitch = max(0.0, yaw - by), max(0.0, pitch - bp)
    need = math.tan(math.radians(dyaw)) * mx + math.tan(math.radians(dpitch)) * mz
    budget = float(q.get('orcamento') or 0.0)
    k = 1.0 if need <= budget or need <= 0 else budget / need
    tv = k * math.tan(math.radians(dyaw))
    tp = k * math.tan(math.radians(dpitch))
    R_ = 200.0
    xs = np.linspace(-R_, R_, 9)
    zs = np.linspace(-R_, R_, 9)
    # B face of the seam: y = th/2 + tv|x| + tp|z| (a pyramid, cut from 4 half spaces)
    yb = th / 2
    Bside = BOX(-R_, R_, -R_, R_, -R_, R_)
    for sx_ in (1, -1):
        for sz_ in (1, -1):
            # plane y = yb + tv*sx_*x + tp*sz_*z ; keep y above it
            nvec = np.array([-tv * sx_, 1.0, -tp * sz_])
            nn = nvec / np.linalg.norm(nvec)
            off = yb / np.linalg.norm(nvec)
            Bside = flat(Bside ^ _halfspace(nn, off))
    Aside = BOX(-R_, R_, -R_, -th / 2, -R_, R_)
    seam = flat(BOX(-R_, R_, -th / 2 - 0.01, R_, -R_, R_) - Bside - Aside)
    disc = X(mf.Manifold.cylinder(60, FJM_DISC * s, FJM_DISC * s, 96).translate([0, 0, -30]), rot_x(90))
    cutter = flat(cut_l + flat(seam - disc))
    if d_off > 0:
        cutter = flat(_offset_smooth(cutter, d_off))
    # the cut follows the border of the part being split: only the piece of section that holds
    # the joint (and whatever is glued to it there) is cut; the old top view zone sliced paws
    # that pass under the head
    hdm = FJM_D * sn / 2
    mask = section_mask(S, T, (-hdm - 2.0, -hdm, 0.0, hdm, hdm + 2.0)) if BODY_MASK else None
    if mask is not None:
        cutter = flat(cutter ^ mask)
    else:
        Zl = _zone_local(q, T)
        if Zl is not None:
            cutter = flat(cutter ^ Zl)
    # other parts passing through the cutting zone (a leg next to the body) stay whole
    reach = FJM_D * sn / 2 + 3
    K = X(BOX(-w - 4, w + 4, -reach, reach, -500, 500), T)
    inK = parts(flat(S ^ K), 1.0)
    cpt = T[:3, 3].tolist()
    if len(inK) > 1:
        holder = [p for p in inK if contains_point(p, cpt, 0.3)]
        others = [p for p in inK if not any(p is h for h in holder)]
        if others:
            cutter = flat(cutter - _grow(flat(X(union(others), Ti)), 1.0))
    cut = flat(S - flat(X(cutter, T)))
    front, back = [], []
    for cc in parts(cut, 1.0):
        (front if (Ti @ np.r_[centroid(cc), 1.0])[1] < 0 else back).append(cc)
    front.sort(key=lambda p_: -p_.volume())
    back.sort(key=lambda p_: -p_.volume())
    front = front[:1] + [p_ for p_ in front[1:] if on_skin(p_, S)]
    back = back[:1] + [p_ for p_ in back[1:] if on_skin(p_, S)]
    if not front or not back:
        return front, mf.Manifold(), [], {}
    A, B = front[0], back[0]
    # probes: a point of each piece next to the seam
    pA = pB = None
    for yq in (FJM_D * sn / 2 + 1.2, FJM_D * sn / 2 + 2.5, th / 2 + 0.8):
        for xq in (0.0, FJM_W * s / 2 + 0.8, -FJM_W * s / 2 - 0.8):
            a_ = (T @ [xq, -yq, 0, 1])[:3].tolist()
            b_ = (T @ [xq, yq, 0, 1])[:3].tolist()
            if pA is None and contains_point(A, a_, 0.3):
                pA = a_
            if pB is None and contains_point(B, b_, 0.3):
                pB = b_
    if pA is None or pB is None:
        raise SkinBreak(0.5)
    # free pull of B before the loops catch (the slack of the chain)
    dvec = T[:3, 1]
    lo, hi = 0.0, 4.0
    if (B.translate((dvec * hi).tolist()) ^ A).volume() <= 0.05:
        raise SkinBreak(1.0)          # loops do not hold
    while hi - lo > 0.1:
        mid = (lo + hi) / 2
        if (B.translate((dvec * mid).tolist()) ^ A).volume() > 0.05:
            hi = mid
        else:
            lo = mid
    slack = round(lo, 2)
    j['z'] = q['z']
    j['_escala_cutter'] = round(s, 2)
    gy = min(yaw, math.degrees(math.atan(th / w)) + math.degrees(math.atan(tv)))
    gp = min(pitch, math.degrees(math.atan(th / hmax)) + math.degrees(math.atan(tp)))
    plan = dict(r=CUT_WALL, ce=0.0, w=w, zt=bx[3], zb=bx[1], s=s, sn=sn, giro_previsto=[gy, gp],
                v_lado=math.degrees(math.atan(tv)), v_cima=math.degrees(math.atan(tp)))
    info = dict(socket_r=FJM_W * s / 2, yb=FJM_D * sn / 2, slack=slack, Ya=FJM_D * sn / 2,
                v=[plan['v_lado'], plan['v_cima']], probeA=pA, probeB=pB, plan=plan)
    return [A] + front[1:], B, back[1:], info


LIMB_JOINT = os.environ.get('FLEXI_LIMB', 'elo')   # 'elo' (FJM loops lying on the bed) or 'pino'
LIMB_WALL = 0.8         # skin over the loops in a limb
LIMB_WALL_MIN = 0.6     # only where 0.8 does not fit (reported per joint)
LIMB_TIME = 240.0       # seconds the loop search may take for one limb; after that it stays fixed (reported)
LIMB_MIN_S = 0.36       # below this the loops get thinner than ~1.2 mm


def _first_top(m, x, y, z0):
    hits = m.ray_cast([float(x), float(y), z0], [float(x), float(y), 1000.0])
    zs = sorted(h.position[2] for h in hits) if hits else []
    return zs[0] if zs else z0


def limb_elo_cut(S, j, zmin, zmax):
    """Limb joint from the same proven loops (FlexiJointMaker), scaled per axis to fit the
    limb and set low: the lower half of the loops is cut off by the bed, so each loop is an
    arch standing on the bed (prints without support). A flat seam crosses the limb at the
    pivot; the limb turns side to side about the vertical axis through the loops.
    Searches size, position along the limb and to each side for the biggest loops that keep
    their skin."""
    C0, L0, th0 = _fjm_local()
    d = direction(j)
    perp = np.array([d[1], -d[0], 0.0])
    zbot = bottom_height(S, j['x'], j['y'])
    hw = min(section_half_width(S, j, zbot + h_) for h_ in (1.0, 2.0, 3.0))
    sx0 = min(1.0, (2 * hw - 2 * LIMB_WALL) / (2 * ELO_HW))
    last = None
    j['_t0'] = time.time()
    for wall in (LIMB_WALL, LIMB_WALL_MIN):
        try:
            return _limb_elo_search(S, j, zmin, C0, L0, th0, d, perp, zbot, hw, wall)
        except SkinBreak as ex:
            last = ex
    raise last


def _limb_elo_search(S, j, zmin, C0, L0, th0, d, perp, zbot, hw, wall):
    closed = LIMB_SOLA == 'fechada'
    HW_, HH_ = (ELO_HW0, ELO_HH0) if closed else (ELO_HW, ELO_HH)
    sx0 = min(1.0, (2 * hw - 2 * wall) / (2 * HW_))
    last = None
    _LIMB_CACHE.clear()
    for f_ in (1.0, 0.9, 0.8, 0.7):
        s_x = sx0 * f_
        if s_x < LIMB_MIN_S:
            break
        hd = FJM_D * s_x / 2
        for ty in (0.0, 1.5, -1.5, 3.0, -3.0):
            for dx in (0.0, 1.0, -1.0, 2.0, -2.0):
                if time.time() - float(j.get('_t0', time.time())) > LIMB_TIME:
                    raise SkinBreak(9.0)        # time budget spent: this limb stays fixed (reported)
                c = np.array([j['x'], j['y'], 0.0]) + d * ty + perp * dx
                tops = []
                for ax_ in (-0.4, 0, 0.4):        # the arch top is narrow; its sides are checked by the skin test
                    for ay_ in (-1, -0.5, 0, 0.5, 1):
                        p_ = c + perp * ax_ * (HW_ * s_x) + d * ay_ * hd
                        tops.append(_first_top(S, p_[0], p_[1], zbot + 0.15))
                tops = [t_ for t_ in tops if t_ > zbot + 1.0] or [zbot]
                top = min(tops)
                # the bed must cut the loops at least ELO_BED below their centre (higher, one
                # loop loses its anchor and the limb pulls out)
                if closed:
                    # closed sole: the loops sit whole inside the limb, with skin under them too
                    # (the cavity also grows by the clearance offset, top and bottom)
                    d_est = max(0.0, (float(j['clearance']) + 0.05 - FJM_CLR * min(s_x, s_x * 1.15)) / 2)
                    s_z = (top - zbot - 2 * wall - 0.1 - 2 * d_est) / (2 * HH_)
                    d_est = max(0.0, (float(j['clearance']) + 0.05 - FJM_CLR * min(s_x, max(s_z, 0.01))) / 2)
                    s_z = min(s_x * 1.15, (top - zbot - 2 * wall - 0.1 - 2 * d_est) / (2 * HH_))
                else:
                    s_z = min(s_x * 1.15, (top - wall - zbot) / (ELO_HH + ELO_BED))
                if s_z < LIMB_MIN_S:
                    last = SkinBreak(LIMB_MIN_S - s_z)
                    continue
                s_z = math.floor(s_z * 50) / 50.0          # steps of 0.02 (cache the offsets)
                d_o = max(0.0, (float(j['clearance']) + 0.05 - FJM_CLR * min(s_x, s_z)) / 2)
                zc = top - wall - s_z * HH_ if not closed else zbot + wall + d_o + 0.05 + s_z * HH_
                if closed and zc + s_z * HH_ + d_o + wall > top + 0.01:
                    last = SkinBreak(0.3)
                    continue
                # the arches stand on the bed: under the whole loop footprint the limb must
                # really lie on the bed (a raised or rounded wrist would leave a loop hanging
                # open, or showing from below)
                if not closed and any(bottom_height(S, *(c + perp * ax_ * (HW_ * s_x) + d * ay_ * hd)[:2]) > zmin + 0.3
                       for ax_ in (-0.6, 0, 0.6) for ay_ in (-0.7, 0, 0.7)):
                    last = SkinBreak(0.5)
                    continue
                ztops = [_first_top(S, *(c + perp * a_ * hw)[:2], zbot + 0.15) for a_ in (-0.5, 0, 0.5)]
                # the seam only crosses the limb itself (as wide as the limb at this spot), never
                # a slice of the body beside it
                qc = dict(j, x=float(c[0]), y=float(c[1]))
                hwc = max(section_half_width(S, qc, zbot + h_) for h_ in (0.6, 1.5, max(0.7, min(tops) - zbot - 1.0)))
                jj = dict(j, x=float(c[0]), y=float(c[1]), _seam_top=max(ztops) + 0.6, _bed_z=zmin, _wall=wall,
                          _seam_hw=min(hwc, hw + 3.0) + 0.6)
                try:
                    r_ = _limb_elo(S, jj, s_x, s_z, zc, zbot, C0, L0, th0)
                    j.update({k_: jj[k_] for k_ in ('x', 'y', 'z', 'estilo', '_escala_elo', '_seam_top', '_seam_hw', '_bed_z', '_wall') if k_ in jj})
                    j['_parede_elo'] = wall
                    if ty or dx:
                        j['_elo_desloc'] = [ty, dx]
                    return r_
                except SkinBreak as ex:
                    last = ex
    raise last or SkinBreak(1.0)


_LIMB_CACHE = {}
# limb loops are the cutter turned 90 deg about the seam normal: then the bed may cut them
# closer to the centre and both loops stay anchored (tested in all directions)
ELO_ROT = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1.0]])
ELO_HW, ELO_HH = 6.28, 6.91       # half width (local x) and half height (z) of the turned loops
ELO_HW0, ELO_HH0 = 6.91, 6.28     # the same, not turned (used with the closed sole: lower)
LIMB_SOLA = os.environ.get('FLEXI_SOLA', 'fechada')   # 'fechada': loops whole inside the limb, sole closed; 'aberta': arches on the bed (v3.5)
ELO_BED = 3.1                     # the bed cuts the loops this far below the centre or lower (cutter units): from 3.0 down both loops stay closed rings (genus test); above that the paw loop opens into a hook


def _limb_grown(core, loops, s_x, s_z, d):
    """The scaled cutter and its loops grown by the clearance offset d (Minkowski, slow): made
    once per size and kept for the rest of the session."""
    if d <= 0:
        return core, loops
    key = (round(s_x, 4), round(s_z, 4), round(d, 4))
    if key not in _GROWN:
        _GROWN[key] = (flat(_offset_smooth(core, d)), flat(_offset_smooth(loops, d)))
    return _GROWN[key]


_GROWN = {}


def _limb_elo(S, j, s_x, s_z, zc, zbot, C0, L0, th0):
    q = dict(j, z=zc)
    T = joint_frame(q)
    Ti = np.linalg.inv(T)
    CLR = float(q['clearance'])
    Sc = np.diag([s_x, s_x, s_z, 1.0])
    Ro_ = np.eye(4) if LIMB_SOLA == 'fechada' else ELO_ROT
    core = X(C0, Sc @ Ro_)
    loops = X(L0, Sc @ Ro_)
    th = th0 * s_x
    smin = min(s_x, s_z)
    d_off = max(0.0, (CLR + 0.05 - FJM_CLR * smin) / 2)
    # nothing below the bed, nothing above the limb
    bed = BOX(-200, 200, -200, 200, zbot - zc, float(j.get('_seam_top', zc + 200)) - zc)
    # loops keep LIMB_WALL of skin above and on the sides (below is the bed: open on purpose)
    bed_z = float(j.get('_bed_z', zbot))
    above = BOX(-200, 200, -200, 200, bed_z - zc + (0.05 if LIMB_SOLA != 'fechada' else -50.0), 200)
    key = (round(s_x, 4), round(s_z, 4), float(j.get('_wall', LIMB_WALL)))
    if key not in _LIMB_CACHE:
        _LIMB_CACHE[key] = flat(_offset_smooth(loops, d_off + float(j.get('_wall', LIMB_WALL))))
    g = flat(_LIMB_CACHE[key] ^ above)
    gw = flat(X(g, T))
    gb = gw.bounding_box()
    Sl = flat(S ^ BOX(gb[0] - 1, gb[3] + 1, gb[1] - 1, gb[4] + 1, gb[2] - 1, gb[5] + 1))
    out_ = 0.0
    for p_ in parts(flat(gw - Sl), 0.02):
        bb_ = p_.bounding_box()
        # a sliver at the very bottom edge of the flank (rounded foot of the limb) is allowed
        out_ += p_.volume()
    if out_ > 0.3:
        if os.environ.get('FLEXI_SKIN_DEBUG'):
            for p_ in parts(flat(gw - Sl), 0.05):
                print('  limb skin out', round(p_.volume(), 2), np.round(p_.bounding_box(), 1), 's', round(s_x, 2), round(s_z, 2), 'zc', round(zc, 2))
        raise SkinBreak(out_)
    # seam: the cutter's own plate inside its disc, a flat slab outside it (only across the
    # limb), opening into a small V at the limb flanks for the rest of the turn
    W = float(q.get('width') or 10.0) + 6.0
    yaw = float(q['yaw'])
    HWo_ = ELO_HW0 if LIMB_SOLA == 'fechada' else ELO_HW
    hw = max(1.0, HWo_ * s_x)
    wl = max(hw + 0.5, float(q.get('width') or hw))
    tv = max(0.0, math.tan(math.radians(yaw)) - th / max(wl, 1.0))
    dd = d_off          # the whole cutter used to be grown by d_off at the end (18 s each try):
                        # now each part is made already grown (cached), same shape
    pts = [(-W, th / 2 + dd + tv * (W - hw)), (-hw, th / 2 + dd), (hw, th / 2 + dd), (W, th / 2 + dd + tv * (W - hw)),
           (W, -th / 2 - dd), (-W, -th / 2 - dd)]
    seam = poly_cs(pts).extrude(400).translate([0, 0, -200])
    seam = flat(X(seam, rot_x(0)) )
    # (poly is in local x-y, extruded along z)
    disc = X(mf.Manifold.cylinder(60, FJM_DISC * s_x, FJM_DISC * s_x, 96).translate([0, 0, -30]), rot_x(90))
    disc = X(disc, np.diag([1.0, 1.0, s_z / s_x, 1.0]))
    seam = flat(seam - disc)
    # the cutter's own plate (a disc around the loops) is clipped like the seam: inside the
    # limb only. Unclipped it sliced a flat slot into the body beside the limb.
    core_g, loops_g = _limb_grown(core, loops, s_x, s_z, dd)
    seam = flat(seam + flat(core_g ^ BOX(-200, 200, -th / 2 - dd - 0.02, th / 2 + dd + 0.02, -200, 200)))
    zl = q.get('zona_membro')
    if zl is not None:
        zg = zl.offset(dd, mf.JoinType.Round) if dd > 0 else zl
        seam = flat(seam ^ X(zg.extrude(2000).translate([0, 0, -1000]), Ti))
    if q.get('_seam_hw') is not None:
        sh_ = float(q['_seam_hw']) + dd
        seam = flat(seam ^ BOX(-sh_, sh_, -50, 50, -200, 200))
    zq = q.get('zona')
    if zq is not None:
        zg2 = zq.offset(dd, mf.JoinType.Round) if dd > 0 else zq
        seam = flat(seam ^ X(zg2.extrude(2000).translate([0, 0, -1000]), Ti))   # the loops are never clipped
    bed_g = BOX(-200, 200, -200, 200, zbot - zc - dd, float(j.get('_seam_top', zc + 200)) - zc + dd)
    cutter = flat(flat(loops_g + seam) ^ bed_g)
    cut = flat(S - flat(X(cutter, T)))
    front, back = [], []
    for cc in parts(cut, 1.0):
        (front if (Ti @ np.r_[centroid(cc), 1.0])[1] < 0 else back).append(cc)
    front.sort(key=lambda p_: -p_.volume())
    back.sort(key=lambda p_: -p_.volume())
    front = front[:1] + [p_ for p_ in front[1:] if on_skin(p_, S)]
    back = back[:1] + [p_ for p_ in back[1:] if on_skin(p_, S)]
    if not front or not back:
        raise SkinBreak(0.5)          # the seam did not separate the limb here: try elsewhere
    A, B = front[0], back[0]
    pA = pB = None
    hd = FJM_D * s_x / 2
    for yq in (hd + 1.0, hd + 2.0, hd + 3.5):
        for xq in (0.0, 1.5, -1.5):
            for zq in (0.0, -0.5 * (zc - zbot), 0.5):
                a_ = (T @ [xq, -yq, zq, 1])[:3].tolist()
                b_ = (T @ [xq, yq, zq, 1])[:3].tolist()
                if pA is None and contains_point(A, a_, 0.3):
                    pA = a_
                if pB is None and contains_point(B, b_, 0.3):
                    pB = b_
    if pA is None or pB is None:
        raise SkinBreak(0.5)
    # pull the limb straight out in every direction (not into the bed): it must catch on
    # solid material within 10 mm, a graze does not count
    cw = T[:3, 3]
    Aloc = flat(A ^ BOX(cw[0] - 25, cw[0] + 25, cw[1] - 25, cw[1] + 25, -500, 500))
    if not elo_holds(Aloc, B):
        raise SkinBreak(0.4)
    # both loops must be closed (each piece keeps a hole through it at the joint): an open
    # hook may still catch in a test but breaks or slips in the hand
    box_l = X(BOX(-(HWo_ * s_x + 4), HWo_ * s_x + 4, -(hd + 4), hd + 4, -200, 200), T)
    if flat(A ^ box_l).genus() < 1 or flat(B ^ box_l).genus() < 1:
        raise SkinBreak(0.45)
    j['z'] = zc
    j['estilo'] = 'elo'
    j['_escala_elo'] = [round(s_x, 2), round(s_z, 2)]
    return [A] + front[1:], B, back[1:], dict(socket_r=hd, yb=hd, probeA=pA, probeB=pB)


def elo_holds(A, B, reach=10.0, hit=0.5):
    """True when B, pulled straight in any of the 26 directions (downwards too: once off the
    bed nothing holds the paw from below), meets A (overlap > hit mm3) within reach mm."""
    import itertools as _it
    for v_ in _it.product((-1, 0, 1), repeat=3):
        if not any(v_):
            continue
        dv_ = np.array(v_, float) / np.linalg.norm(v_)
        if not any((B.translate((dv_ * t_).tolist()) ^ A).volume() > hit
                   for t_ in np.arange(0.5, reach + 0.01, 0.5)):
            return False
    return True


def _halfspace(nn, off, R=400.0):
    """Solid {p : p.nn >= off} clipped to a big box."""
    nn = np.asarray(nn, float)
    z = nn
    xa = np.cross(z, [0, 0, 1.0]) if abs(z[2]) < 0.9 else np.cross(z, [1.0, 0, 0])
    xa /= np.linalg.norm(xa)
    ya = np.cross(z, xa)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2] = xa, ya, z
    M[:3, 3] = z * off
    return X(BOX(-R, R, -R, R, 0, 2 * R), M)


def union_cs(lst):
    out = lst[0]
    for c in lst[1:]:
        out = out + c
    return out


# ----------------------------------------------------------------------------
# preparation
# ----------------------------------------------------------------------------
def prepare(m, opts):
    """opts: length_mm (longest horizontal side), center (bool), flatten_mm, simplify_mm, mirror ('none'|'+x'|'-x')."""
    log = []
    bb = m.bounding_box()
    ext = np.array(bb[3:]) - np.array(bb[:3])
    L = float(opts.get('length_mm') or 0)
    if L > 0:
        s = L / max(ext[0], ext[1])
        m = m.scale([s, s, s])
        log.append(f'escala x{s:.3f}')
    if opts.get('center', True):
        bb = m.bounding_box()
        m = m.translate([-(bb[0] + bb[3]) / 2, -(bb[1] + bb[4]) / 2, -bb[2]])
    mir = opts.get('mirror', 'none')
    if mir in ('+x', '-x'):
        keep = BOX(0, 1000, -1000, 1000, -1000, 1000) if mir == '+x' else BOX(-1000, 0, -1000, 1000, -1000, 1000)
        h = m ^ keep
        m = flat(h + h.mirror([1, 0, 0]))
        log.append(f'simetria pelo lado {mir}')
    fl = float(opts.get('flatten_mm') or 0)
    if fl > 0:
        m = flat((m ^ BOX(-1000, 1000, -1000, 1000, fl, 1000)).translate([0, 0, -fl]))
        log.append(f'base achatada {fl} mm')
    sm = float(opts.get('simplify_mm') or 0)
    if sm > 0:
        n0 = m.num_tri()
        # depois de um corte (a base achatada) o Manifold não junta triângulos de origens
        # diferentes: as_original() libera a simplificação para a malha toda
        m = flat(m).as_original().simplify(sm)
        log.append(f'triangulos {n0} -> {m.num_tri()}')
    return flat(m), log


# ----------------------------------------------------------------------------
# generation
# ----------------------------------------------------------------------------
def _tris_in(M, lo, hi):
    v, f = mesh_arrays(M)
    t = v[f].astype(np.float64)
    if lo is not None:
        tl, th = t.min(1), t.max(1)
        t = t[np.all((th >= lo) & (tl <= hi), axis=1)]
    return t


def _edge_len(t):
    return np.max(np.stack([np.linalg.norm(t[:, 1] - t[:, 0], axis=1),
                            np.linalg.norm(t[:, 2] - t[:, 1], axis=1),
                            np.linalg.norm(t[:, 0] - t[:, 2], axis=1)]), axis=0)


def _dense(t, step=0.22):
    """Barycentric grid on every triangle, no surface point farther than `step` from a sample."""
    if len(t) == 0:
        return np.zeros((0, 3))
    k = np.clip(np.ceil(_edge_len(t) / step), 1, 80).astype(int)
    out = []
    for kk in np.unique(k):
        tt = t[k == kk]
        ab = np.array([(i / kk, j / kk) for i in range(kk + 1) for j in range(kk + 1 - i)])
        w0 = 1 - ab[:, 0] - ab[:, 1]
        P = (tt[:, None, 0] * w0[None, :, None] + tt[:, None, 1] * ab[None, :, 0, None]
             + tt[:, None, 2] * ab[None, :, 1, None])
        out.append(P.reshape(-1, 3))
    return np.concatenate(out)


def _surface_samples(M, lo=None, hi=None, n=None, step=0.22):
    return _dense(_tris_in(M, lo, hi), step)


def _close_pairs(A, B, reach, pad=1.0):
    """Dense samples of A and B only where the two surfaces come within `reach` of each other
    (coarse test on triangle centroids first, so big pieces stay fast)."""
    from scipy.spatial import cKDTree
    ba, bb = np.array(A.bounding_box()), np.array(B.bounding_box())
    lo = np.maximum(ba[:3], bb[:3]) - pad
    hi = np.minimum(ba[3:], bb[3:]) + pad
    if np.any(lo > hi):
        return None, None
    ta, tb = _tris_in(A, lo, hi), _tris_in(B, lo, hi)
    if not len(ta) or not len(tb):
        return None, None
    ea, eb = _edge_len(ta), _edge_len(tb)
    ca, cb = ta.mean(1), tb.mean(1)
    ma, mb = float(min(ea.max(), 40.0)), float(min(eb.max(), 40.0))
    da, _ = cKDTree(cb).query(ca, distance_upper_bound=reach + ma + mb + 0.5)
    db, _ = cKDTree(ca).query(cb, distance_upper_bound=reach + ma + mb + 0.5)
    ka = da < reach + ea + mb + 0.2
    kb = db < reach + eb + ma + 0.2
    if not ka.any() or not kb.any():
        return None, None
    return _dense(ta[ka]), _dense(tb[kb])


def enforce_gap(A, B, clr):
    """Safety net: wherever two pieces ended up closer than the clearance, shave the second
    one there so the print never fuses. Returns the corrected B and how many spots."""
    from scipy.spatial import cKDTree
    try:
        if A.min_gap(B, clr + 0.1) >= clr - 0.02:      # exact and fast: nothing to fix
            return B, 0
    except Exception:
        pass
    pa, pb = _close_pairs(A, B, clr + 0.1)
    if pa is None or not len(pa) or not len(pb):
        return B, 0
    # samples are ~0.2 mm apart: anything measured below clr + 0.1 may truly be below clr
    lim = clr + 0.1
    d, _ = cKDTree(pb).query(pa, distance_upper_bound=lim)
    d2, _ = cKDTree(pa).query(pb, distance_upper_bound=lim)
    close = np.concatenate([pa[d < lim], pb[d2 < lim]])
    if not len(close):
        return B, 0
    # group the close spots into 6 mm cells and shave each cell once
    cells = {}
    for p in close:
        cells.setdefault(tuple(np.floor(p / 6.0).astype(int)), []).append(p)
    spots = []
    cut = []
    for key, pts in cells.items():
        pts = np.array(pts)
        lo_, hi_ = pts.min(0) - 1.5, pts.max(0) + 1.5
        spots.append(pts.mean(0))
        box = BOX(lo_[0], hi_[0], lo_[1], hi_[1], lo_[2], hi_[2])
        big = BOX(lo_[0] - 1, hi_[0] + 1, lo_[1] - 1, hi_[1] + 1, lo_[2] - 1, hi_[2] + 1)
        loc = flat(A ^ big)
        if not loc.is_empty():
            cut.append(flat(_offset_smooth(loc, clr + 0.1) ^ box))
    if not cut:
        return B, 0
    if os.environ.get('FLEXI_DEBUG'):
        print('enforce_gap: cells', len(cut), 'close pts', len(close))
    out = flat(B - flat(union(cut)))
    ps = sorted(parts(out, 0.5), key=lambda q: -q.volume())
    # never let the safety net break a piece: if shaving splits it or eats it, keep it whole
    if not ps or ps[0].volume() < 0.97 * B.volume() or any(q.volume() > 2.0 for q in ps[1:]):
        if os.environ.get('FLEXI_DEBUG'):
            print('enforce_gap: shave refused', B.volume(), [round(q.volume(), 1) for q in ps[:4]])
        return B, 0
    return ps[0], len(spots)


def generate(base, joints, clearance=DEFAULT_CLEARANCE, progress=None, limits=None, zone_fn=None):
    t0 = time.time()
    pieces = [base]
    base_sil = silhouettes([base])
    base_vol = base.volume()
    target = float((limits or {}).get('volume') or LIM_VOLUME)
    budget = max(0.3, (100.0 - target) / max(1, len(joints)))
    n_chain = sum(1 for q in joints if q.get('type') == 'corrente')
    # the V seams may spend part of the allowed outside loss (calibrated: the real visible
    # loss of a V is about twice its first-order estimate, and seams/keels take the rest)
    chain_budget = 0.4 * (100.0 - target) / 100.0 * base.volume() / max(1, n_chain)
    edges = []
    warnings = []
    used = []
    done = set()
    # limbs first: then the spine collars only measure the body, not the legs
    # limbs first (so body joints measure the body, not the legs), then the body joints in
    # the order given (head to tail)
    # body joints first (head to tail), then the limbs: the flat limb joints are small and
    # local, the chain links need the whole body section
    order = sorted(range(len(joints)), key=lambda i: 1 if (joints[i].get('papel') == 'membro' or
                   (joints[i].get('papel') is None and joints[i].get('type') == 'dobradica')) else 0)
    # where every joint will sit (to share the space between neighbours)
    spots = {}
    for i in order:
        q = dict(joints[i])
        for key in ('x', 'y', 'angle', 'size'):
            q[key] = float(q[key])
        q.setdefault('type', 'esferica')
        try:
            q = auto_fill(base, q)
            spots[i] = (np.array([q['x'], q['y'], q['z']]), q['size'])
        except Exception:
            pass
    for k in order:
        done.add(k)
        j = dict(joints[k])
        j.setdefault('clearance', clearance)
        if j.get('clearance') in (None, ''):
            j['clearance'] = clearance
        j['clearance'] = float(j['clearance'])
        j['angle'] = float(j['angle'])
        j['x'], j['y'] = float(j['x']), float(j['y'])
        j['size'] = float(j['size'])
        j['yaw'] = float(j.get('yaw', 25))
        j['pitch'] = float(j.get('pitch', 15))
        # which piece holds this joint?
        probe = [j['x'], j['y'], (float(j['z']) if j.get('z') not in (None, '', 'auto') else 3.0)]
        idx = None
        for i, p in enumerate(pieces):
            if contains_point(p, probe, 0.5):
                idx = i
                break
        if idx is None:
            warnings.append(f'Junta {k + 1}: o ponto nao esta dentro de nenhuma peca; ignorada.')
            continue
        S = pieces[idx]
        j = auto_fill(S, j)
        manual_gola = j.get('gola') not in (None, '', 'auto')
        is_chain = j['type'] == 'corrente'
        if is_chain:
            # adaptive: what the joints already done really cost comes off the shape budget, and
            # the limbs get a small reserve, so the total stays at the shape the user asked for
            spent = sum(float(u.get('perda_visivel_pct') or 0) for u in used)
            left_chain = sum(1 for i in order if i not in done and joints[i].get('type') == 'corrente') + 1
            left_limb = sum(1 for i in order if i not in done and joints[i].get('type') != 'corrente')
            rem = (100.0 - target) - spent - 0.25 * left_limb - 1.0 * left_chain   # ~1% per seam
            j['orcamento'] = max(0.0, min(chain_budget, 0.5 * rem / 100.0 * base.volume() / left_chain))
        j['gola'] = collar_radius(S, j) if not is_chain else 0.0
        cpt = np.array([j['x'], j['y'], j['z']])
        gmin = round(j['size'] + j['clearance'] + 2.0, 2)
        # automatic collar: as big as the body (invisible seam) but never reaching the next
        # joint ahead; when it has to shrink, the part of the body outside it gets a small notch
        if not manual_gola and not is_chain:
            d = direction(j)
            gauto = j['gola']
            for i, (p_, sz) in spots.items():
                if i == k or i in done:
                    continue
                v = p_ - cpt
                if float(v @ d) < -sz:           # behind this joint: stays in the fixed piece
                    continue
                j['gola'] = min(j['gola'], float(np.linalg.norm(v)) - sz - 2.0)
            j['gola'] = round(max(j['gola'], gmin), 2)
            if j['gola'] < gauto - 0.5:
                j['gola_reduzida'] = True
        ahead = None
        for u in used:
            uc = np.array([u['x'], u['y'], u['z']])
            v = cpt - uc
            dist = float(np.linalg.norm(v))
            if j.get('papel') == 'membro' and u.get('type') == 'corrente' and u.get('_escala_cutter'):
                # a limb beside a body joint: only the body loops' own width matters
                du = direction(u)
                lateral = abs(float(v[0] * du[1] - v[1] * du[0]))
                if lateral > FJM_W * float(u['_escala_cutter']) / 2 + 3.0:
                    continue
            room = u['gola'] + (j['size'] * 1.6 + 0.8 if is_chain else j['size'] + 1.0)
            if float(v @ direction(u)) >= -j['size'] and dist < room:
                ahead = (u, dist)
                break
        if ahead:
            u, dist = ahead
            need = (u['gola'] + j['size'] * 1.6 + 0.8) if is_chain else (u['size'] + u['clearance'] + 2.0 + j['size'] + 2.0)
            warnings.append(f"Junta {k + 1} ignorada: esta a {dist:.1f} mm da Junta {u['n']}. Juntas desse tamanho "
                            f"precisam de pelo menos {need:.0f} mm entre si. Afaste as juntas.")
            continue
        vol_before = S.volume()
        bb = S.bounding_box()
        flat_ = j['type'] == 'dobradica' and j.get('estilo') == 'plana' and flat_ok(S, j, bb[2])
        if flat_:
            j['estilo'] = 'plana'
            j['size'] = round(min(j['size'], 3.0, max(FLAT_MIN_R, float(j['gola']) - 2 * j['clearance'] - 0.9)), 2)
        elif j['type'] == 'dobradica' and LIMB_JOINT == 'elo' and j.get('papel') == 'membro':
            j['estilo'] = 'elo'
        elif j['type'] == 'dobradica':
            j['estilo'] = 'pino'
            # start from a pin that fits the limb's thickness (fewer failed tries)
            dv = direction(j)
            tops = [top_height(S, j['x'] + dv[0] * t_, j['y'] + dv[1] * t_) for t_ in (0, 2, 4, 6)]
            tops = [t_ for t_ in tops if t_ > 0] or [j['z'] * 2]
            e_ = j['clearance'] * math.sqrt(2)
            # height is checked by the cut itself (it places the pin at mid height); here only
            # the width limits the pin
            cap = 0.75 * (float(j['width']) - 2.0)
            if cap < j['size']:
                j['size'] = round(max(1.5, cap), 2)
        size0, yaw0, pitch0 = j['size'], j['yaw'], j['pitch']

        def attempt():
            prev = None
            for f_ in (((1.0,) if BODY_JOINT == 'cutter' else (1.0, 0.85, 0.7, 0.6)) if is_chain else ((1.0,) if j.get('estilo') == 'elo' else (1.0, 0.85, 0.7))):
                j['size'] = round(size0 * f_, 2)
                if j['size'] < (0.9 if is_chain else (FLAT_MIN_R if j.get('estilo') == 'plana' else 1.5)):
                    break
                try:
                    if j['type'] == 'corrente':
                        if BODY_JOINT == 'cutter':
                            return cutter_cut(S, j, bb[2], bb[5])
                        return chain_cut(S, j, bb[2], bb[5])
                    if j['type'] == 'dobradica':
                        if LIMB_JOINT == 'elo' and j.get('papel') == 'membro':
                            return limb_elo_cut(S, j, bb[2], bb[5])
                        return hinge_cut(S, j, bb[2], bb[5])
                    return ball_cut(S, j, bb[2], bb[5])
                except SkinBreak as ex:
                    v_ = float(ex.args[0]) if ex.args else 0.0
                    if prev is not None and v_ > 0.8 * prev:
                        break                 # shrinking does not help here: try another spot
                    prev = v_
                    continue
            return None

        def _vdbg(why):
            if os.environ.get('FLEXI_VALID_DEBUG'):
                print('  valid falhou:', why, flush=True)

        def valid(r):
            if r is None or r[1].is_empty() or not r[0]:
                _vdbg('if r is None or r[1].is_empty() or not r[0]:')
                return False
            if r[1].volume() < 120.0:                  # a crumb is not a moving part
                _vdbg('if r[1].volume() < 120.0:                  # a crumb is not a moving p')
                return False
            if r[1].slice(bb[2] + 0.15).area() < 3.0:   # the moving piece must stand on the bed
                _vdbg('if r[1].slice(bb[2] + 0.15).area() < 3.0:   # the moving piece must st')
                return False
            # the two pieces may never share material (a failed cut can leave a shell of one
            # inside the other)
            mainA = max(r[0], key=lambda f: f.volume())
            if (r[1] ^ mainA).volume() > 0.05:
                _vdbg('if (r[1] ^ mainA).volume() > 0.05:')
                return False
            if sum(f.volume() for f in r[0]) + r[1].volume() > S.volume() + 0.5:
                _vdbg('if sum(f.volume() for f in r[0]) + r[1].volume() > S.volume() + 0.5:')
                return False
            # what lies well ahead of the joint (inside its zone) must have gone to the moving
            # piece: a cut that only peels a shell off the seam is not a joint
            Tj = joint_frame(j)
            reach = max(float(j.get('gola') or 0.0), 11.0) + 2.0
            ahead = flat(S ^ X(BOX(-400, 400, reach, 400, -400, 400), Tj))
            Zl_ = _zone_local(j, Tj)
            if Zl_ is not None:
                ahead = flat(ahead ^ X(Zl_, Tj))
            va = ahead.volume()
            if va > 20.0 and (ahead ^ r[1]).volume() < 0.9 * va:
                _vdbg('if va > 20.0 and (ahead ^ r[1]).volume() < 0.9 * va:')
                return False
            if not is_chain:
                # the pin must really hold: lifting the body 2 mm (or pushing the paw up) has to
                # meet solid material, never just a sliver
                A0_ = [f for f in r[0] if f.volume() > 50][:1]
                if A0_:
                    if j.get('estilo') == 'elo':
                        # interlocked loops have some play: they must catch within 5 mm
                        dn = max((r[1].translate([0, 0, -t_]) ^ A0_[0]).volume() for t_ in (1.5, 3.0, 5.0))
                        up = max((r[1].translate([0, 0, t_]) ^ A0_[0]).volume() for t_ in (1.5, 3.0, 5.0))
                    else:
                        dn = (r[1].translate([0, 0, -2.0]) ^ A0_[0]).volume()
                        up = (r[1].translate([0, 0, 2.0]) ^ A0_[0]).volume()
                    if min(dn, up) < (0.5 if j.get('estilo') == 'elo' else 2.0):
                        _vdbg("if min(dn, up) < (0.5 if j.get('estilo') == 'elo' else 2.0):")
                        return False
            return len([f for f in r[0] if f.volume() > 50]) == 1 and not [f for f in r[2] if f.volume() > 50]

        # if the spot does not work, slide the joint a little along its direction and retry,
        # instead of giving up (the user should not have to hunt for a valid spot)
        x0, y0, dvec = j['x'], j['y'], direction(j)
        res = None
        if j.get('estilo') == 'elo':
            # the loop search already slides the joint; a moved shoulder may still fall back
            # to where the leg leaves the outline
            shifts_ = (0,)
            if j.get('raiz') is not None:
                shifts_ = (0, round(float(np.linalg.norm(np.array(j['raiz'], float) - np.array([x0, y0]))), 2))
        else:
            shifts_ = (0, 2, -2, 4, -4, 6) if is_chain else (0, 2, -2, 4, -4, -6)
        for sh in shifts_:
            j['x'], j['y'] = x0 + dvec[0] * sh, y0 + dvec[1] * sh
            if sh:
                q = auto_fill(S, dict(j, z=None, width=None))
                j.update(x=q['x'], y=q['y'], z=q['z'], width=q['width'])
            if zone_fn is not None:
                j['zona'] = zone_fn(j)
                if j.get('papel') == 'membro':
                    j['zona_membro'] = zone_fn(dict(j, size=-4.99))   # the limb alone (no pin room)
            r_ = attempt()
            if valid(r_):
                res = r_
                if sh:
                    j['movida_mm'] = sh
                break
            if res is None:
                res = r_
        if res is not None and not valid(res) and j.get('movida_mm') is None:
            j['x'], j['y'] = x0, y0
        if res is not None and not valid(res) and not is_chain and res[1].volume() >= 120.0 \
                and res[1].slice(bb[2] + 0.15).area() >= 3.0:
            warnings.append(f'Junta {k + 1} ficou de fora: em nenhum ponto testado o pino fica preso de verdade '
                            f'(a parte é baixa demais ali). Essa parte fica fixa, para não soltar depois de impressa.')
            continue
        if res is not None and not res[1].is_empty() and res[1].slice(bb[2] + 0.15).area() < 3.0:
            warnings.append(f'Junta {k + 1} ficou de fora: a parte que giraria não encosta na mesa '
                            f'(ficaria solta no ar e pediria suporte). Essa parte fica fixa.')
            continue
        if res is not None and not res[1].is_empty() and res[1].volume() < 120.0:
            warnings.append(f'Junta {k + 1} ficou de fora: sobraria só uma ponta pequena para girar. Essa parte fica fixa.')
            continue
        if j.get('movida_mm'):
            warnings.append(f"Junta {k + 1}: deslocada {abs(j['movida_mm'])} mm para um ponto onde o corte fica limpo.")
        # shape budget: each joint may take its share of the allowed outside loss. When a
        # smaller collar (to fit the neighbours) would cut a visible notch, the turning range
        # is reduced automatically instead.
        for _ in range(0 if (is_chain or j.get('estilo') == 'elo') else 2):
            if res is None or res[1].is_empty() or not res[0]:
                break
            vis = 100.0 * visible_loss([S], res[0] + [res[1]]) / base_vol
            j['perda_visivel_pct'] = round(vis, 2)
            if vis <= budget or j['yaw'] <= 8:
                break
            f = max(0.35, min(0.85, (budget / vis) ** 0.5))
            j['yaw'] = max(8.0, round(j['yaw'] * f))
            if j['type'] != 'dobradica':
                j['pitch'] = max(5.0, round(j['pitch'] * f))
            res = attempt()
        if res is not None and (j['yaw'] != yaw0 or j['pitch'] != pitch0):
            j['giro_ajustado'] = dict(lado=[yaw0, j['yaw']], cima=[pitch0, j['pitch']])
            warnings.append(f"Junta {k + 1}: giro ajustado de ±{yaw0:.0f}° para ±{j['yaw']:.0f}° nos lados"
                            + (f" e de ±{pitch0:.0f}° para ±{j['pitch']:.0f}° para cima/baixo" if j['type'] != 'dobradica' else '')
                            + " para manter a forma (a gola teve de ser menor para caber as juntas vizinhas).")
        if res is None:
            if is_chain:
                warnings.append(f'Junta {k + 1} ignorada: o corpo e fino demais ali para caber os elos '
                                f'com parede de {CUT_WALL} mm (precisa de uns 13 mm de altura e 14 mm de largura). '
                                f'Leve a junta para uma parte mais grossa.')
            elif j.get('estilo') == 'elo':
                warnings.append(f'Junta {k + 1} ficou fixa: a pata é pequena demais para elos fechados por dentro '
                                f'com pele de {LIMB_WALL_MIN} mm em volta (testados vários tamanhos e posições). '
                                f'Em um modelo maior ela cabe.')
            else:
                warnings.append(f'Junta {k + 1} ignorada: o pino/bola furaria a pele (parede menor que {WALL} mm), '
                                f'mesmo reduzido. Leve a junta para uma parte mais grossa ou centralize a altura.')
            continue
        if j['size'] != size0:
            warnings.append(f"Junta {k + 1}: {'elo' if is_chain else 'pino/bola'} reduzido de {size0} para {j['size']} mm "
                            f"para caber no corpo.")
        front, B, frags, info = res
        if B.is_empty() or not front:
            warnings.append(f'Junta {k + 1} ignorada: o corte nao separou a peca. Aumente a largura do corte ou mude a posicao.')
            continue
        main_front = [f for f in front if f.volume() > 50]
        loose = [f for f in frags if f.volume() > 50]
        if len(main_front) != 1 or loose:
            warnings.append(f'Junta {k + 1} ficou de fora: em todos os pontos testados perto dela o corte soltaria um pedaco '
                            f'(normalmente uma pata colada em outra parte). Essa parte fica fixa.')
            continue
        chips = [f.volume() for f in front if f.volume() <= 50] + [f.volume() for f in frags]
        front = main_front
        if sum(chips) > 0.5:
            warnings.append(f'Junta {k + 1}: {len(chips)} lasca(s) de {sum(chips):.1f} mm3 no total removida(s) na costura.')
        rr = max(float(j.get('width') or 10), float(j.get('gola') or 0)) + 14.0
        vbox = BOX(j['x'] - rr, j['x'] + rr, j['y'] - rr, j['y'] + rr, -1000, 1000)
        j['perda_visivel_pct'] = round(100.0 * visible_loss([S], front + [B], box=vbox) / base_vol, 2)
        kept = sum(f.volume() for f in front) + B.volume()
        j['perda_pct'] = round(100.0 * (vol_before - kept) / max(base.volume(), 1e-9), 2)
        s0, s1 = silhouettes([S]), silhouettes(front + [B])
        j['silhueta_pct'] = round(max(100.0 * max(s0[v] - s1[v], 0) / base_sil[v] for v in VIEWS), 2)
        j['n'] = k + 1
        pieces[idx] = flat(front[0])
        for extra in front[1:]:
            pieces.append(flat(extra))
        pieces.append(flat(B))
        d = direction(j)
        c = np.array([j['x'], j['y'], j['z']])
        if is_chain:
            pl = info['plan']
            j['gola'] = round(info['Ya'] + pl['r'] + pl['ce'] + WALL, 2)   # reach ahead (spacing)
            if BODY_JOINT == 'cutter':
                j['gola'] = round(2 * info['Ya'] + 1.0, 2)   # own loops ahead + the next one's behind
            j['folga_elo'] = info['slack']
            gy, gp = pl['giro_previsto']
            if gy < j['yaw'] - 1 or gp < j['pitch'] - 1:
                warnings.append(f"Junta {k + 1}: com a forma preservada pedida, esta junta dobra cerca de ±{gy:.0f}° para os lados "
                                f"e ±{gp:.0f}° para cima/baixo (pediu ±{j['yaw']:.0f}° e ±{j['pitch']:.0f}°). "
                                f"Baixe a forma mínima para dobrar mais, ou afaste a junta para uma parte mais alta.")
            edges.append(dict(joint=k, type='corrente', frame=joint_frame(j).tolist(),
                              probeB=info['probeB'], probeA=info['probeA'],
                              yaw=j['yaw'], pitch=j['pitch'], slack=info['slack'],
                              w=pl['w'], zt=pl['zt'], zb=pl['zb'],
                              cutter_th=(FJM_PX[1] - FJM_PX[0]) * pl.get('sn', pl['s']) if BODY_JOINT == 'cutter' else None))
        else:
            up = np.array([0, 0, 1.0 if info.get('flat') else 0.0])
            edges.append(dict(joint=k, type=j['type'], frame=joint_frame(j).tolist(),
                              probeB=info.get('probeB', (c + up).tolist()),
                              probeA=info.get('probeA', (c - d * (info['socket_r'] + 1.0) + up).tolist()), estilo=j.get('estilo'),
                              yaw=j['yaw'], pitch=j['pitch'] if j['type'] != 'dobradica' else 0.0))
        if j.get('_parede_elo') is not None and j['_parede_elo'] < LIMB_WALL:
            warnings.append(f"Junta {k + 1}: a pata é estreita; os elos ficaram com parede de {j['_parede_elo']} mm "
                            f"(o normal é {LIMB_WALL} mm). Confira essa pata no fatiador.")
        used.append(j)
        if progress:
            progress(f'junta {k + 1}/{len(joints)} pronta ({time.time() - t0:.0f} s)')
    # remove zero-thickness sheets that boolean cuts can leave on coplanar faces (they are
    # invisible but count as surfaces touching the neighbour piece)
    pieces = [flat(p.simplify(0.001)) for p in pieces]
    # nothing may start in mid air: shave the tiny bits the cuts left hanging
    known = islands(base)
    for i in range(len(pieces)):
        pieces[i], rv = fix_islands(pieces[i], known)
        if os.environ.get('FLEXI_DEBUG') and rv:
            print('fix_islands piece', i, 'removed', round(rv, 2))
    # safety net: no two pieces closer than the clearance anywhere
    for _ in range(3):
        fixed = 0
        for a in range(len(pieces)):
            for b in range(a + 1, len(pieces)):
                nb, k_ = enforce_gap(pieces[a], pieces[b], clearance)
                if k_:
                    pieces[b] = nb
                    fixed += k_
        if not fixed:
            break
    # every piece must be exactly one solid: zero-volume sheets and specks left by the boolean
    # cuts would show up in the slicer as floating bits
    for i in range(len(pieces)):
        ps = sorted(parts(pieces[i], 0.0), key=lambda q: -q.volume())
        if len(ps) > 1:
            if os.environ.get('FLEXI_DEBUG'):
                print('piece', i, 'dropped specks', [round(q.volume(), 3) for q in ps[1:6]], len(ps) - 1)
            pieces[i] = ps[0]
    # map edge probes to final pieces
    for e in edges:
        for key, pkey in (('a', 'probeA'), ('b', 'probeB')):
            e[key] = None
            p = np.array(e[pkey])
            for r in (0.15, 0.4, 0.8):
                for i, pc in enumerate(pieces):
                    if contains_point(pc, p, r):
                        e[key] = i
                        break
                if e[key] is not None:
                    break
        if e['a'] is None or e['b'] is None or e['a'] == e['b']:
            warnings.append(f"Junta {e['joint'] + 1}: nao consegui identificar as duas pecas ligadas.")
    return dict(pieces=pieces, edges=edges, joints=used, warnings=warnings, clearance=clearance,
                seconds=round(time.time() - t0, 1))


# ----------------------------------------------------------------------------
# validation
# ----------------------------------------------------------------------------
def _moving_set(n, edges, e_skip):
    adj = {i: set() for i in range(n)}
    for e in edges:
        if e is e_skip or e['a'] is None or e['b'] is None:
            continue
        adj[e['a']].add(e['b'])
        adj[e['b']].add(e['a'])
    seen, stack = {e_skip['b']}, [e_skip['b']]
    while stack:
        u = stack.pop()
        for v in adj[u]:
            if v not in seen and v != e_skip['a']:
                seen.add(v)
                stack.append(v)
    return seen


def gap_verified(A, B, clr):
    """min_gap, but a reading below the clearance is checked against real material: boolean
    cuts can leave zero-thickness sheets that min_gap sees and the printer never prints."""
    from scipy.spatial import cKDTree
    g = gap_estimate(A, B)
    if g >= clr - 0.02:
        return g
    pa, pb = _close_pairs(A, B, clr)
    if pa is None or not len(pa):
        return g
    d, _ = cKDTree(pb).query(pa, distance_upper_bound=clr + 0.1)
    close = pa[d < clr + 0.1]
    cells = {}
    for q in close:
        cells.setdefault(tuple(np.floor(q / 6.0).astype(int)), []).append(q)
    for pts in cells.values():
        pts = np.array(pts)
        lo_, hi_ = pts.min(0) - 1.5, pts.max(0) + 1.5
        box = BOX(lo_[0], hi_[0], lo_[1], hi_[1], lo_[2], hi_[2])
        big = BOX(lo_[0] - 1, hi_[0] + 1, lo_[1] - 1, hi_[1] + 1, lo_[2] - 1, hi_[2] + 1)
        loc = flat(A ^ big)
        if loc.is_empty():
            continue
        if (flat(_grow_safe(loc, clr - 0.04) ^ box) ^ B).volume() > 1e-3:
            return g                      # real material closer than the clearance
    return max(g, clr - 0.02)


def gap_estimate(A, B, pad=1.0, n=4):
    """Smallest distance between two pieces, from dense surface samples near each other
    (Manifold.min_gap can report 0 for pieces that do not touch)."""
    from scipy.spatial import cKDTree
    try:
        g = float(A.min_gap(B, 2.0))
        if g > 0.005:
            return min(g, 2.0)
    except Exception:
        pass
    # min_gap may report 0 for pieces that only nearly touch: measure from samples
    pa, pb = _close_pairs(A, B, 2.0, pad)
    if pa is None or len(pa) == 0 or len(pb) == 0:
        return 2.0
    d, _ = cKDTree(pb).query(pa, distance_upper_bound=2.0)
    d2, _ = cKDTree(pa).query(pb, distance_upper_bound=2.0)
    return float(min(2.0, d.min(), d2.min()))


def islands(p, layer=0.2):
    """Places where a piece starts in mid air (needs support in the slicer).
    Slices the piece layer by layer; a region with nothing of the same piece under it
    (allowing 45 degrees) is an island."""
    bb = p.bounding_box()
    out = []
    prev = p.slice(bb[2] + layer * 0.5)
    z = bb[2] + layer * 1.5
    while z < bb[5]:
        cur = p.slice(z)
        if not cur.is_empty():
            sup = prev.offset(layer + 0.05, mf.JoinType.Round) if not prev.is_empty() else prev
            for comp in cur.decompose():
                a = comp.area()
                if a < 0.25:          # thinner than a nozzle line: the slicer drops it anyway
                    continue
                if sup.is_empty() or (comp ^ sup).area() < 0.02:
                    b = comp.bounds()
                    out.append(dict(x=round((b[0] + b[2]) / 2, 1), y=round((b[1] + b[3]) / 2, 1), z=round(z, 1)))
        prev = cur
        z += layer
    return out


def fix_islands(p, known=(), layer=0.2):
    """Remove small bits the cuts left hanging in the air (they would need support). Works
    layer by layer in a small box around each island, so whatever sits on the removed bit is
    removed too until the rest is supported again. Islands of the original model are kept."""
    removed_total = 0.0
    for _ in range(3):
        isl = [q for q in islands(p, layer) if not any(
            abs(q['x'] - k['x']) < 6 and abs(q['y'] - k['y']) < 6 and abs(q['z'] - k['z']) < 1.5 for k in known)]
        if not isl:
            break
        cuts = []
        for q in isl:
            x, y, z0 = q['x'], q['y'], q['z']
            bx = (x - 7, x + 7, y - 7, y + 7)
            box2 = mf.CrossSection.square([14, 14]).translate([x - 7, y - 7])
            edge = box2 - box2.offset(-0.3, mf.JoinType.Miter)
            loc = flat(p ^ BOX(bx[0], bx[1], bx[2], bx[3], z0 - 1.0, z0 + 4.0))
            # same layer grid as islands(), so what it calls an island is what gets removed
            step = layer
            zb = p.bounding_box()[2]
            k0 = max(0, int(math.floor((z0 - 0.45 - zb) / layer - 1.5)))
            z = zb + layer * (1.5 + k0)
            hist = [loc.slice(z - 2 * step), loc.slice(z - step)]
            calm = 0
            while z < z0 + 4.0:
                cur = loc.slice(z)
                if cur.is_empty():
                    break
                prev = hist[-1]
                sup = prev.offset(layer + 0.05, mf.JoinType.Round) if not prev.is_empty() else prev
                kept = mf.CrossSection()
                rm = []
                for c in cur.decompose():
                    if (not sup.is_empty() and (c ^ sup).area() >= 0.02) or (c ^ edge).area() > 0:
                        kept = kept + c
                    else:
                        rm.append(c)
                calm = 0 if rm else calm + 1
                if calm > 3 and z > z0 + 0.3:
                    break
                for c in rm:
                    cuts.append(c.offset(0.05, mf.JoinType.Round).extrude(step + 0.02).translate([0, 0, z - step / 2 - 0.01]))
                hist.append(kept)
                z += step
        if not cuts:
            break
        out = flat(p - _smooth_cut(cuts))
        ps = sorted(parts(out, 0.5), key=lambda q: -q.volume())
        if not ps or ps[0].volume() < p.volume() - 30:
            break
        removed_total += p.volume() - ps[0].volume()
        p = ps[0]
    return p, removed_total


def _validate_chain(P, e, T, Ti, D, Up):
    """A chain joint has no fixed pivot: B pulls away by the slack and tips over the inner
    edge of the seam. For each direction try pivots on that edge and find the real range."""
    w, zt, zb, s = e['w'], e['zt'], e['zb'], e['slack']
    hits = lambda M: (X(D, M) ^ Up).volume() > 0.05

    def pose(axis, ang, piv):
        Tp = np.eye(4)
        Tp[:3, 3] = piv
        R = rot_z(ang) if axis == 'z' else rot_x(ang)
        return T @ Tp @ R @ np.linalg.inv(Tp) @ Ti

    def search(axis, sign, limit, pivots):
        best, bp = 0.0, pivots[0]
        for piv in pivots:
            lo, hi = 0.0, float(limit)
            if not hits(pose(axis, sign * hi, piv)):
                return hi, piv
            while hi - lo > 1.0:
                mid = (lo + hi) / 2
                if hits(pose(axis, sign * mid, piv)):
                    hi = mid
                else:
                    lo = mid
            if lo > best:
                best, bp = lo, piv
        return round(best, 0), bp

    yaw, pitch = e['yaw'], e['pitch']
    real, piv = {}, {}
    th = e.get('cutter_th')
    if th:
        # interlocked loops: B turns about the loops in the middle of the seam (it slides a
        # little forward on them), the flat seam closes at the edges
        pv = [[0, 0, 0], [0, th / 2, 0], [0, th, 0]]
        real['lado_esq'], piv['lado_esq'] = search('z', 1, yaw, pv)
        real['lado_dir'], piv['lado_dir'] = search('z', -1, yaw, pv)
        if pitch:
            real['cima'], piv['cima'] = search('x', 1, pitch, pv)
            real['baixo'], piv['baixo'] = search('x', -1, pitch, pv)
    else:
        real['lado_esq'], piv['lado_esq'] = search('z', 1, yaw, [[-w, 0, 0], [-0.6 * w, 0, 0]])
        real['lado_dir'], piv['lado_dir'] = search('z', -1, yaw, [[w, 0, 0], [0.6 * w, 0, 0]])
        if pitch:
            real['cima'], piv['cima'] = search('x', 1, pitch, [[0, 0, zt], [0, 0, 0.6 * zt]])
            real['baixo'], piv['baixo'] = search('x', -1, pitch, [[0, 0, zb], [0, 0, 0.6 * zb]])
    d = T[:3, 1]
    pull = (P[e['b']].translate((d * (s + 2.5)).tolist()) ^ P[e['a']]).volume()
    free_pull = (P[e['b']].translate((d * max(0.0, s - 0.6)).tolist()) ^ P[e['a']]).volume()
    trava = pull > 0.05
    e['pivots'] = {k: [float(x) for x in v] for k, v in piv.items()}
    ok = all(real[k] >= (yaw if k.startswith('lado') else pitch) - 1 for k in real)
    return dict(junta=e['joint'] + 1, tipo='corrente', pecas=[e['a'], e['b']], giro_lado=yaw,
                giro_cima=pitch, movimento_livre=ok, giro_real=real, colisoes=[], trava=trava,
                folga_elo=s, estica_livre=free_pull <= 0.05, pivots=e['pivots'])


def validate(base, result, limits=None):
    lim = dict(volume=LIM_VOLUME, silhueta=LIM_SILHUETA, junta=LIM_JUNTA_SIL)
    lim.update({k: float(v) for k, v in (limits or {}).items() if v not in (None, '')})
    P = result['pieces']
    edges = result['edges']
    rep = dict(pecas=[], juntas=[], pares=[], resumo={})
    vol0 = base.volume()
    tot = 0
    known_isl = islands(base)
    clr_v = float(result.get('clearance') or DEFAULT_CLEARANCE)
    for i, p in enumerate(P):
        v, f = mesh_arrays(p)
        tri = v[f].astype(np.float64)
        nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        area = np.linalg.norm(nrm, axis=1) / 2
        nz = nrm[:, 2] / np.maximum(np.linalg.norm(nrm, axis=1), 1e-12)
        zc = tri[:, :, 2].mean(1)
        ov = (nz < -0.72) & (zc > 0.3)
        bed = p.slice(0.15).area()
        vol = p.volume()
        tot += vol
        isl_all = [q for q in islands(p) if q['z'] > 0.35]
        isl = [q for q in isl_all if not any(abs(q['x'] - k['x']) < 6 and abs(q['y'] - k['y']) < 6
                                             and abs(q['z'] - k['z']) < 1.5 for k in known_isl)]
        rep['pecas'].append(dict(id=i, volume=round(vol, 1), balanco_mm2=round(float(area[ov].sum()), 1),
                                 ilhas=len(isl), ilhas_pos=isl[:6], ilhas_modelo=len(isl_all) - len(isl),
                                 contato_mesa_mm2=round(bed, 1), componentes=len(parts(p, 0.0))))
    # pairwise
    bbs = [p.bounding_box() for p in P]
    for a in range(len(P)):
        for b in range(a + 1, len(P)):
            A, B = bbs[a], bbs[b]
            if any(A[k] > B[k + 3] + 1.5 or B[k] > A[k + 3] + 1.5 for k in range(3)):
                continue
            ov = (P[a] ^ P[b]).volume()
            gap = gap_verified(P[a], P[b], clr_v) if ov < 1e-6 else 0.0
            rep['pares'].append(dict(a=a, b=b, sobreposicao=round(ov, 3), folga_min=round(gap, 3)))
    # joints
    for e in edges:
        if e['a'] is None or e['b'] is None or e['a'] == e['b']:
            continue
        T = np.array(e['frame'])
        Ti = np.linalg.inv(T)
        mov = _moving_set(len(P), edges, e)
        D = union([P[i] for i in mov])
        Up = union([P[i] for i in range(len(P)) if i not in mov])
        if e['type'] == 'corrente':
            rep['juntas'].append(_validate_chain(P, e, T, Ti, D, Up))
            continue
        bad = []
        yaw, pitch = e['yaw'], e['pitch']
        for a in (-yaw, -yaw / 2, 0, yaw / 2, yaw):
            for p in ((-pitch, 0, pitch) if pitch else (0,)):
                M = T @ rot_z(a) @ rot_x(p) @ Ti
                v = (X(D, M) ^ Up).volume()
                if v > 0.05:
                    bad.append(dict(lado=a, cima=p, vol=round(v, 2)))
        d = T[:3, 1]
        z = T[:3, 2]
        path = []
        for lz in (0.0, 1.5):
            for dd in (1, 2, 3, 4, 5):
                path.append(round((P[e['b']].translate((d * dd + z * lz).tolist()) ^ P[e['a']]).volume(), 2))
        vert = [round((P[e['b']].translate((z * s_).tolist()) ^ P[e['a']]).volume(), 2) for s_ in (2.0, -2.0)]
        trava = min(path[1:4] + path[6:9]) > 0.05 and min(vert) > 0.5
        if e.get('estilo') == 'elo':
            # small interlocked loops: the limb is free to move a little, so test it the hard
            # way, pulling it straight in every direction (not into the bed) until it hits
            import itertools as _it
            trava = elo_holds(P[e['a']], P[e['b']])

        # real free range (search each direction, 1 degree resolution)
        def free(axis, sign, limit):
            lo, hi = 0.0, float(limit)
            M = T @ (rot_z(sign * hi) if axis == 'z' else rot_x(sign * hi)) @ Ti
            if (X(D, M) ^ Up).volume() <= 0.05:
                return hi
            while hi - lo > 1.0:
                mid = (lo + hi) / 2
                M = T @ (rot_z(sign * mid) if axis == 'z' else rot_x(sign * mid)) @ Ti
                if (X(D, M) ^ Up).volume() <= 0.05:
                    lo = mid
                else:
                    hi = mid
            return round(lo, 0)
        real = dict(lado_esq=free('z', 1, yaw), lado_dir=free('z', -1, yaw))
        if pitch:
            real.update(cima=free('x', -1, pitch), baixo=free('x', 1, pitch))
        rep['juntas'].append(dict(junta=e['joint'] + 1, tipo=e['type'], estilo=e.get('estilo'), pecas=[e['a'], e['b']],
                                  giro_lado=yaw, giro_cima=pitch, movimento_livre=not bad,
                                  giro_real=real, colisoes=bad, trava=trava, puxar=path, puxar_vertical=vert))
    # cuteness check: how much of the original volume and silhouette survived
    fof = dict(limite_volume_pct=lim['volume'], limite_junta_silhueta_pct=lim['junta'], limite_silhueta_pct=lim['silhueta'])
    vol_total = round(100 * tot / vol0, 1) if vol0 else 0
    vols = round(100 - 100 * visible_loss([base], P) / vol0, 1) if vol0 else 0
    per = [dict(junta=j.get('n'), perda_pct=j.get('perda_pct', 0), silhueta_pct=j.get('silhueta_pct', 0),
                gola=j.get('gola'), gola_reduzida=bool(j.get('gola_reduzida')),
                perda_visivel_pct=j.get('perda_visivel_pct', 0), giro_ajustado=j.get('giro_ajustado'))
           for j in sorted(result['joints'], key=lambda q: q.get('n', 0))]
    s0, s1 = silhouettes([base]), silhouettes(P)
    sil = {v: (round(100 * max(s0[v] - s1[v], 0) / s0[v], 2) if s0[v] else 0) for v in VIEWS}
    fof.update(volume_pct=vols, volume_total_pct=vol_total, juntas=per, silhueta_perdida_pct=sil,
               ok_volume=vols >= lim['volume'],
               ok_juntas=all(x['silhueta_pct'] <= lim['junta'] for x in per),
               ok_silhueta=all(v <= lim['silhueta'] for v in sil.values()))
    fof['ok'] = fof['ok_volume']      # the only criterion; the rest is reported for information
    rep['fofura'] = fof
    rep['resumo'] = dict(volume_preservado_pct=round(100 * tot / vol0, 1) if vol0 else 0,
                         sobreposicoes=sum(1 for p in rep['pares'] if p['sobreposicao'] > 0.01),
                         folga_minima=min([p['folga_min'] for p in rep['pares'] if p['sobreposicao'] <= 0.01] or [0]),
                         juntas_ok=sum(1 for j in rep['juntas'] if j['trava'] and
                                       min((j.get('giro_real') or {'x': 0}).values()) >= 8),
                         juntas_faixa_toda=sum(1 for j in rep['juntas'] if j['movimento_livre'] and j['trava']),
                         juntas_total=len(rep['juntas']))
    return rep


# ----------------------------------------------------------------------------
# calibration coupon: the same limb joint at several clearances
# ----------------------------------------------------------------------------
CUPOM_FOLGAS = (0.20, 0.25, 0.30, 0.35, 0.40, 0.50)


def _rounded_box(x0, x1, y0, y1, z0, z1, r):
    core = BOX(x0 + r, x1 - r, y0 + r, y1 - r, z0 + r, z1 - r)
    m = flat(_offset_smooth(core, r))
    return flat(m ^ BOX(x0 - 1, x1 + 1, y0 - 1, y1 + 1, z0, z1 + 1))     # flat bottom on the bed


def make_coupon(folgas=CUPOM_FOLGAS, paw_h=8.0, paw_w=11.0, progress=None):
    """One sample per clearance: a block (body) and a paw joined by the limb joint exactly as
    the generator makes it. Every sample has the same loops (size, height, wall); only the
    clearance changes. Sample n has n dimples on top of the block. Returns the pieces (two per
    sample, in print position) and a report with the clearance really measured."""
    C0, L0, th0 = _fjm_local()

    def sample(n):
        ox = (n - 1) * 24.0
        block = _rounded_box(ox - 9, ox + 9, -9, 9, 0, paw_h + 1.5, 1.5)
        paw = _rounded_box(ox - paw_w / 2, ox + paw_w / 2, 6, 24, 0, paw_h, 1.5)
        dimples = union([mf.Manifold.cylinder(2, 0.9, 0.9, 24).translate([ox - 6 + 3 * k, -5, paw_h + 1.5 - 0.6])
                         for k in range(n)])
        return flat(flat(block + paw) - dimples), ox

    # the loops are chosen once, for the largest clearance (the one that needs most room)
    S, ox = sample(len(folgas))
    j0 = dict(type='dobradica', papel='membro', estilo='elo', x=ox, y=11.0, z=None, angle=0.0, size=2.6,
              clearance=float(max(folgas)), yaw=25.0, pitch=0.0)
    j0 = auto_fill(S, j0)
    j0['gola'] = collar_radius(S, j0)
    bb = S.bounding_box()
    limb_elo_cut(S, j0, bb[2], bb[5])            # raises SkinBreak if even this does not fit
    s_x, s_z = j0['_escala_elo']
    pieces, rep = [], []
    for n, c in enumerate(folgas, 1):
        S, ox = sample(n)
        jj = dict(j0, x=j0['x'] - (len(folgas) - n) * 24.0, clearance=float(c))
        try:
            front, B, frags, info = _limb_elo(S, jj, s_x, s_z, float(j0['z']), 0.0, C0, L0, th0)
        except SkinBreak:
            rep.append(dict(amostra=n, furinhos=n, folga_programa=c, ok=False, motivo='a junta não coube nesta amostra'))
            continue
        A = front[0]
        g = gap_verified(A, B, float(c))
        ok = elo_holds(A, B) and A.genus() >= 1 and B.genus() >= 1 and not islands(A) and not islands(B)
        pieces += [A, B]
        rep.append(dict(amostra=n, furinhos=n, folga_programa=c, folga_real=round(g, 3), presa=bool(ok)))
        if progress:
            progress(f'amostra {n}/{len(folgas)} pronta')
    return pieces, dict(amostras=rep, escala_elos=[s_x, s_z], parede=j0.get('_parede_elo'),
                        altura_pata=paw_h, largura_pata=paw_w)
