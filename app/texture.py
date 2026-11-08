"""EFC3D: models with colour (GLB, glTF, OBJ with texture) and automatic painting.

AI generators (Meshy, Tripo, Rodin...) deliver the model with a texture. Here the colour of
each triangle is read from the texture (or vertex colours), the colours are grouped into N
filaments (k-means in Lab, weighted by area) and the specks are cleaned, so the painting is
ready and only needs touch ups.
"""
import io
import os
import tempfile
import zipfile

import numpy as np

COLOR_EXT = ('.glb', '.gltf', '.obj', '.zip')


def is_colored_file(name):
    return os.path.splitext(name.lower())[1] in COLOR_EXT


# ----------------------------------------------------------------------------- reading
def _face_colors(mesh):
    """RGB 0..1 per face of a trimesh mesh: texture (4 samples per face), vertex colours, or
    the material colour."""
    n = len(mesh.faces)
    vis = mesh.visual
    try:
        if getattr(vis, 'kind', None) == 'texture' and vis.uv is not None:
            mat = vis.material
            img = getattr(mat, 'baseColorTexture', None) or getattr(mat, 'image', None)
            fac = np.ones(4)
            bcf = getattr(mat, 'baseColorFactor', None)
            if bcf is not None:
                fac = np.asarray(bcf, np.float64).ravel()[:4]
                if fac.max() > 1.0:
                    fac = fac / 255.0
            if img is not None:
                im = np.asarray(img.convert('RGB'), np.float64) / 255.0
                H, W = im.shape[:2]
                uv = np.asarray(vis.uv, np.float64)
                fuv = uv[mesh.faces]                                  # (n,3,2)
                samples = np.concatenate([fuv, fuv.mean(1, keepdims=True)], axis=1)   # 3 corners + centre
                # corners pulled a little towards the centre: no bleeding from the next island
                samples[:, :3] = samples[:, :3] * 0.7 + samples[:, 3:4] * 0.3
                u = np.mod(samples[..., 0], 1.0)
                v = np.mod(samples[..., 1], 1.0)
                x = np.clip((u * (W - 1)).round().astype(int), 0, W - 1)
                y = np.clip(((1 - v) * (H - 1)).round().astype(int), 0, H - 1)
                rgb = im[y, x].mean(1)
                return np.clip(rgb * fac[:3], 0, 1)
            return np.tile(fac[:3], (n, 1))
        vc = getattr(vis, 'vertex_colors', None)
        if vc is not None and len(vc) == len(mesh.vertices):
            vc = np.asarray(vc, np.float64)[:, :3] / 255.0
            return vc[mesh.faces].mean(1)
        fc = getattr(vis, 'face_colors', None)
        if fc is not None and len(fc) == n:
            return np.asarray(fc, np.float64)[:, :3] / 255.0
    except Exception:
        pass
    return None


def read_colored(data, name):
    """Returns (triangles (n,3,3) in mm-ish units, Z up; colours (n,3) or None; log)."""
    import trimesh
    ext = os.path.splitext(name.lower())[1]
    log = []
    with tempfile.TemporaryDirectory() as tmp:
        if ext == '.zip':
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for info in z.infolist():
                    p = os.path.normpath(os.path.join(tmp, info.filename))
                    if not p.startswith(tmp) or info.is_dir():
                        continue
                    os.makedirs(os.path.dirname(p), exist_ok=True)
                    with open(p, 'wb') as f:
                        f.write(z.read(info))
            found = [os.path.join(r, f) for r, _, fs in os.walk(tmp) for f in fs
                     if f.lower().endswith(('.glb', '.gltf', '.obj'))]
            if not found:
                raise ValueError('O .zip não tem modelo (.glb, .gltf ou .obj).')
            path = sorted(found, key=lambda q: (not q.lower().endswith('.glb'), q))[0]
            ext = os.path.splitext(path.lower())[1]
            log.append('lido do .zip: ' + os.path.basename(path))
        else:
            path = os.path.join(tmp, 'modelo' + ext)
            with open(path, 'wb') as f:
                f.write(data)
        scene = trimesh.load(path, force='scene', process=False)
        meshes = scene.dump(concatenate=False) if hasattr(scene, 'dump') else [scene]
    tris, cols, any_col = [], [], False
    for m in meshes:
        if not hasattr(m, 'faces') or len(m.faces) == 0:
            continue
        T = np.asarray(m.vertices, np.float64)[np.asarray(m.faces)]
        c = _face_colors(m)
        if c is None:
            c = np.full((len(T), 3), 0.8)
        else:
            any_col = True
        tris.append(T)
        cols.append(c)
    if not tris:
        raise ValueError('Não achei triângulos neste arquivo.')
    T = np.concatenate(tris)
    C = np.concatenate(cols) if any_col else None
    # glTF is Y up (and so are the OBJ files of the AI generators): turn to Z up like an STL
    T = np.stack([T[..., 0], -T[..., 2], T[..., 1]], axis=-1)
    log.append(f'{len(T)} triângulos' + (', cores da textura lidas' if C is not None else ', sem cores'))
    return T, C, log


def to_stl_bytes(T):
    import struct
    n = len(T)
    nrm = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    ln = np.linalg.norm(nrm, axis=1, keepdims=True)
    ln[ln == 0] = 1
    rec = np.zeros(n, dtype=[('n', '<f4', 3), ('v', '<f4', 9), ('a', '<u2')])
    rec['n'] = nrm / ln
    rec['v'] = T.reshape(n, 9)
    return b'EFC3D'.ljust(80, b' ') + struct.pack('<I', n) + rec.tobytes()


def transfer_rgb(src_T, src_rgb, dst_T):
    """Colour of each dst triangle from the nearest src triangle, after normalising both to
    their boxes (the model was centred, scaled and simplified in between)."""
    from scipy.spatial import cKDTree

    def norm(t):
        c = t.reshape(-1, 3)
        lo, hi = c.min(0), c.max(0)
        return (t.mean(1) - lo) / np.maximum(hi - lo, 1e-9)
    _, i = cKDTree(norm(src_T)).query(norm(dst_T))
    return np.asarray(src_rgb)[i]


# ----------------------------------------------------------------------------- colours
def _lab(rgb):
    c = np.where(rgb > 0.04045, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])], axis=1)


def _kmeans(X, w, k, iters=30, seed=7):
    rng = np.random.default_rng(seed)
    p = w / w.sum()
    C = [X[rng.choice(len(X), p=p)]]
    for _ in range(1, k):                                # k-means++ start
        d = np.min(((X[:, None, :] - np.array(C)[None]) ** 2).sum(2), axis=1)
        q = d * w
        C.append(X[rng.choice(len(X), p=q / q.sum())] if q.sum() > 0 else X[rng.integers(len(X))])
    C = np.array(C)
    for _ in range(iters):
        lab = np.argmin(((X[:, None, :] - C[None]) ** 2).sum(2), axis=1)
        newC = np.array([np.average(X[lab == j], axis=0, weights=w[lab == j]) if (lab == j).any() else C[j] for j in range(k)])
        if np.allclose(newC, C, atol=1e-3):
            break
        C = newC
    err = float((w * ((X - C[lab]) ** 2).sum(1)).sum() / w.sum())
    return C, lab, err


def cluster(rgb, area, k=None, kmax=8):
    """Group the colours into k filaments (k=None: chosen by the elbow of the error).
    Returns (label per triangle 0..k-1 ordered by area, palette hex, k)."""
    rgb = np.clip(np.asarray(rgb, np.float64), 0, 1)
    X = _lab(rgb)
    w = np.maximum(np.asarray(area, np.float64), 1e-9)
    rng = np.random.default_rng(3)
    m = min(len(X), 40000)
    sel = rng.choice(len(X), m, replace=False, p=w / w.sum()) if len(X) > m else np.arange(len(X))
    Xs, ws = X[sel], np.ones(len(sel))
    # many small clusters first, then the closest ones merge: shading of one colour joins up,
    # while a small area of a really different colour (an eye, a belt) stays its own filament
    C0, lab0, _ = _kmeans(Xs, ws, min(14, max(2, len(np.unique(Xs.round(0), axis=0)))))
    cw = np.bincount(lab0, minlength=len(C0)).astype(float)
    cents = [C0[j] for j in range(len(C0)) if cw[j] > 0]
    wts = [cw[j] for j in range(len(C0)) if cw[j] > 0]
    tot = sum(wts)

    tiny = 0.005 if k is None else 0.001           # share below which a cluster is speckle or edge blend

    def merge_once():
        best = None
        for i in range(len(cents)):
            for j in range(i + 1, len(cents)):
                d = float(np.sqrt(((cents[i] - cents[j]) ** 2).sum()))
                # tiny clusters merge first (they are speckle, not a colour)
                if min(wts[i], wts[j]) / tot < tiny:
                    d *= 0.01
                if best is None or d < best[0]:
                    best = (d, i, j)
        d, i, j = best
        w = wts[i] + wts[j]
        cents[i] = (cents[i] * wts[i] + cents[j] * wts[j]) / w
        wts[i] = w
        del cents[j], wts[j]
        return d

    if k is None:
        while len(cents) > 2:
            dmin = min(float(np.sqrt(((cents[i] - cents[j]) ** 2).sum())) * (0.01 if min(wts[i], wts[j]) / tot < tiny else 1)
                       for i in range(len(cents)) for j in range(i + 1, len(cents)))
            if dmin >= 18 or len(cents) <= 2:
                break
            merge_once()
        k = min(len(cents), kmax)
        while len(cents) > k:
            merge_once()
    else:
        k = int(max(1, min(16, k, len(cents))))
        while len(cents) > k:
            merge_once()
    C = np.array(cents)
    lab = np.argmin(((X[:, None, :] - C[None]) ** 2).sum(2), axis=1)
    order = np.argsort([-w[lab == j].sum() for j in range(k)])
    remap = np.empty(k, int)
    remap[order] = np.arange(k)
    lab = remap[lab]
    pal = []
    for j in order:
        msk = lab == remap[j]
        c = np.average(rgb[msk], axis=0, weights=w[msk]) if msk.any() else np.array([0.8, 0.8, 0.8])
        pal.append('#%02x%02x%02x' % tuple(int(round(v * 255)) for v in c))
    return lab, pal, k


def clean(labels, nb, area, min_area=2.0, passes=2):
    """Remove the salt and pepper of a texture: majority of the neighbours (2 passes), then
    groups smaller than min_area mm2 join the colour around them."""
    lab = labels.copy()
    n = len(lab)
    for _ in range(passes):
        L = lab[np.maximum(nb, 0)]
        L[nb < 0] = -1
        two = (L[:, 0] == L[:, 1]) | (L[:, 0] == L[:, 2])
        cand = np.where(two, L[:, 0], L[:, 1])
        agree = (L == cand[:, None]).sum(1) >= 2
        ch = agree & (cand != lab) & (cand >= 0)
        lab[ch] = cand[ch]
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    rows, cols = [], []
    for k in range(3):
        o = nb[:, k]
        ok = (o >= 0) & (lab[np.maximum(o, 0)] == lab)
        rows.append(np.arange(n)[ok])
        cols.append(o[ok])
    G = coo_matrix((np.ones(sum(len(r) for r in rows), np.int8), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n))
    nc, comp = connected_components(G, directed=False)
    carea = np.bincount(comp, weights=area, minlength=nc)
    small = carea[comp] < min_area
    for _ in range(6):                                   # grow the big colours into the small specks
        if not small.any():
            break
        L = lab[np.maximum(nb, 0)]
        S_ = small[np.maximum(nb, 0)] | (nb < 0)
        done = np.zeros(n, bool)
        for k in range(3):
            take = small & ~done & ~S_[:, k]
            lab[take] = L[take, k]
            done |= take
        small &= ~done
    return lab
