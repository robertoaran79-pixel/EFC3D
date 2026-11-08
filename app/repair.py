"""EFC3D: last-resort mesh repair for AI generated files.

Only used when the normal reading fails (engine.read_stl): files that already open are not
touched. Typical AI / Assimp exports have a handful of defects in millions of triangles:
  - an edge shared by more than two triangles (two sheets pinched together, a stray triangle)
  - duplicated triangles
  - holes left by the exporter
The fix is local: the triangles around each defect are removed and the holes are closed with
a fan around their centre. Everything else stays exactly as it was.
"""
import numpy as np


def _edges(f):
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    return e, np.repeat(np.arange(len(f))[None, :], 3, axis=0).ravel()


def _key(e, nv):
    s = np.sort(e, axis=1)
    return s[:, 0] * nv + s[:, 1]


def remove_duplicates(f):
    """Identical triangles: keep one; a pair facing opposite ways (zero thickness) goes."""
    s = np.sort(f, axis=1)
    _, inv, cnt = np.unique(s, axis=0, return_inverse=True, return_counts=True)
    inv = inv.ravel()
    keep = np.ones(len(f), bool)
    dup = np.where(cnt[inv] > 1)[0]
    seen = {}
    for t in dup.tolist():
        g = int(inv[t])
        seen.setdefault(g, []).append(t)
    for g, ts in seen.items():
        keep[ts[1:]] = False
    return f[keep], int((~keep).sum())


def bad_faces(f, nv):
    """Triangles on edges used by more than two triangles."""
    e, fid = _edges(f)
    k = _key(e, nv)
    u, inv, c = np.unique(k, return_inverse=True, return_counts=True)
    badk = c[inv] > 2
    return np.unique(fid[badk])


def _boundary_loops(f, nv):
    """Directed boundary edges chained into loops (edges used by one triangle only)."""
    e, _ = _edges(f)
    k = _key(e, nv)
    u, inv, c = np.unique(k, return_inverse=True, return_counts=True)
    b = e[c[inv] == 1]
    nxt = {}
    for a, bb in b.tolist():
        nxt.setdefault(a, []).append(bb)
    loops = []
    while nxt:
        s0 = next(iter(nxt))
        loop, cur = [s0], s0
        for _ in range(100000):
            lst = nxt.get(cur)
            if not lst:
                break
            y = lst.pop()
            if not lst:
                del nxt[cur]
            if y == s0:
                break
            loop.append(y)
            cur = y
        if len(loop) >= 3:
            loops.append(loop)
    return loops


def fill_holes(v, f, max_edges=400):
    """Close each hole with a fan around its centre (holes up to max_edges edges)."""
    nv = len(v)
    loops = _boundary_loops(f, nv)
    nv_list, nf = [v], [f]
    nxt = nv
    filled = 0
    for L in loops:
        if len(L) > max_edges:
            continue
        c = v[L].mean(0)
        nv_list.append(c[None, :])
        Ln = np.array(L + [L[0]])
        # boundary edges run a->b on the existing triangles; the patch runs them b->a
        tri = np.stack([Ln[1:], Ln[:-1], np.full(len(L), nxt)], axis=1)
        nf.append(tri)
        nxt += 1
        filled += 1
    return np.vstack(nv_list), np.vstack(nf), filled


def repair(v, f, rings=2):
    """Returns (v, f, log). v float64 (n,3), f int64 (m,3) with merged vertices."""
    log = []
    f = f[(f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])]
    f, nd = remove_duplicates(f)
    if nd:
        log.append(f'{nd} triângulo(s) duplicado(s) removido(s)')
    nv = len(v)
    bad = bad_faces(f, nv)
    if len(bad):
        # remove the triangles on the pinched edges and a ring around them, so the hole has a
        # clean border; then close it
        rm = np.zeros(len(f), bool)
        rm[bad] = True
        for _ in range(rings):
            vs = np.unique(f[rm].ravel())
            rm |= np.isin(f, vs).any(1)
        log.append(f'{len(bad)} triângulo(s) em arestas compartilhadas por mais de duas faces; '
                   f'{int(rm.sum())} triângulo(s) refeitos em volta')
        f = f[~rm]
    v, f, nh = fill_holes(v, f)
    if nh:
        log.append(f'{nh} furo(s) fechado(s)')
    # vertices no longer used
    used, inv = np.unique(f.ravel(), return_inverse=True)
    v = v[used]
    f = inv.reshape(-1, 3)
    return v, f, log
