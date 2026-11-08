"""EFC3D: mesh colours (painting) and colour export.

Paint = one filament number per triangle of the base model (1 = base filament, unpainted),
in the triangle order of the base model as the viewer receives it (base.stl). Every time the
geometry is rebuilt (exact height bands, joint cuts, project reopened) the colours follow the
surface: each new triangle takes the colour of the original triangle it lies on.

Export: 3MF with the per-triangle filament assignment Bambu Studio, OrcaSlicer and PrusaSlicer
read (paint_color / slic3rpe:mmu_segmentation), plus OBJ + MTL with one material per colour.
"""
import io
import json
import struct
import zipfile

import numpy as np

import engine as E


# ----------------------------------------------------------------------------- triangles
def tri_array(M):
    """(n, 3, 3) triangles of a Manifold, in the same order write_stl writes them."""
    me = M.to_mesh()
    v = np.asarray(me.vert_properties)[:, :3].astype(np.float64)
    f = np.asarray(me.tri_verts)
    return v[f]


def stl_tris(data):
    """(n, 3, 3) triangles of a binary STL, in file order."""
    n = struct.unpack('<I', data[80:84])[0]
    rec = np.frombuffer(data[84:84 + 50 * n], dtype=[('n', '<f4', 3), ('v', '<f4', 9), ('a', '<u2')])
    return rec['v'].reshape(n, 3, 3).astype(np.float64)


def transfer(src, src_paint, dst, k=16):
    """Colour of each dst triangle = colour of the src triangle its centre lies on (nearest
    src triangle centre when it lies on none, e.g. the inside faces of a seam)."""
    from scipy.spatial import cKDTree
    src_paint = np.asarray(src_paint, dtype=np.uint8)
    if len(dst) == 0:
        return np.zeros(0, np.uint8)
    if len(src) == 0:
        return np.ones(len(dst), np.uint8)
    cs = src.mean(1)
    cd = dst.mean(1)
    k = int(min(k, len(src)))
    tree = cKDTree(cs)
    out = np.empty(len(dst), np.uint8)
    step = 60000                                   # em blocos: 2 milhões de triângulos cabem na memória
    for s0 in range(0, len(cd), step):
        out[s0:s0 + step] = _transfer_chunk(src, src_paint, tree, cd[s0:s0 + step], k)
    return out


def _transfer_chunk(src, src_paint, tree, cd, k):
    _, idx = tree.query(cd, k=k)
    if k == 1:
        idx = idx[:, None]
    t = src[idx]                                   # (m, k, 3, 3)
    a, b, c = t[:, :, 0], t[:, :, 1], t[:, :, 2]
    p = cd[:, None, :]
    n = np.cross(b - a, c - a)
    nn = np.linalg.norm(n, axis=2)
    nn[nn == 0] = 1e-12
    dist = np.abs(((p - a) * n).sum(2)) / nn
    # barycentric inside test
    v0, v1, v2 = b - a, c - a, p - a
    d00 = (v0 * v0).sum(2); d01 = (v0 * v1).sum(2); d11 = (v1 * v1).sum(2)
    d20 = (v2 * v0).sum(2); d21 = (v2 * v1).sum(2)
    den = d00 * d11 - d01 * d01
    den[den == 0] = 1e-12
    vv = (d11 * d20 - d01 * d21) / den
    ww = (d00 * d21 - d01 * d20) / den
    uu = 1 - vv - ww
    tol = 1e-3
    ok = (dist < 2e-3) & (uu >= -tol) & (vv >= -tol) & (ww >= -tol)
    pick = np.where(ok.any(1), ok.argmax(1), 0)
    return src_paint[idx[np.arange(len(cd)), pick]]


def transfer_scaled(src, src_paint, dst):
    """Approximate transfer when the model was resized or moved (preparing): both meshes are
    normalised to their bounding boxes, then each triangle takes its nearest colour."""
    from scipy.spatial import cKDTree

    def norm(t):
        c = t.reshape(-1, 3)
        lo, hi = c.min(0), c.max(0)
        return (t.mean(1) - lo) / np.maximum(hi - lo, 1e-9)
    _, i = cKDTree(norm(src)).query(norm(dst))
    return np.asarray(src_paint, np.uint8)[i]


# ----------------------------------------------------------------------------- bands
def refine_bands(S, zs):
    """Split the surface along horizontal planes so a height band has an exact edge."""
    b = S.bounding_box()
    for z in sorted(set(round(float(v), 4) for v in zs)):
        if b[2] + 1e-3 < z < b[5] - 1e-3:
            top, bot = S.split_by_plane([0.0, 0.0, 1.0], z)
            if not top.is_empty() and not bot.is_empty():
                S = E.flat(top + bot)
    return S


# ----------------------------------------------------------------------------- export
def code(c):
    """Per-triangle filament code used by PrusaSlicer, Bambu Studio and OrcaSlicer:
    filament 1 = "4", 2 = "8", 3 = "0C", 4 = "1C", ... 18 = "FC"."""
    c = int(c)
    if c <= 1:
        return '4'
    if c == 2:
        return '8'
    return f'{c - 3:X}C'


def _hex(rgb):
    s = str(rgb or '#cfc8bc').strip()
    return s if s.startswith('#') else '#' + s


def write_3mf(tris_list, paint_list, palette, title='modelo'):
    """One object with every piece (they print together, in place), per-triangle filament,
    filament colours in the metadata. Returns the file bytes."""
    verts, faces, cols = [], [], []
    off = 0
    for t, p in zip(tris_list, paint_list):
        v, inv = np.unique(np.round(t.reshape(-1, 3), 5), axis=0, return_inverse=True)
        verts.append(v)
        faces.append(inv.reshape(-1, 3) + off)
        cols.append(np.asarray(p, np.uint8))
        off += len(v)
    V = np.concatenate(verts) if verts else np.zeros((0, 3))
    F = np.concatenate(faces) if faces else np.zeros((0, 3), int)
    C = np.concatenate(cols) if cols else np.zeros(0, np.uint8)
    out = io.StringIO()
    out.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    out.write('<model unit="millimeter" xml:lang="en-US" '
              'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
              'xmlns:slic3rpe="http://schemas.slic3r.org/3mf/2017/06">\n')
    out.write(' <metadata name="Application">EFC3D</metadata>\n')
    out.write(f' <metadata name="Title">{title}</metadata>\n')
    out.write(' <metadata name="slic3rpe:MmPaintingVersion">1</metadata>\n')
    out.write(' <resources>\n  <object id="1" type="model">\n   <mesh>\n    <vertices>\n')
    out.write(''.join(f'     <vertex x="{x:.5f}" y="{y:.5f}" z="{z:.5f}"/>\n' for x, y, z in V))
    out.write('    </vertices>\n    <triangles>\n')
    lines = []
    for (a, b, c), col in zip(F, C):
        if col > 1:
            cc = code(col)
            lines.append(f'     <triangle v1="{a}" v2="{b}" v3="{c}" paint_color="{cc}" slic3rpe:mmu_segmentation="{cc}"/>\n')
        else:
            lines.append(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>\n')
    out.write(''.join(lines))
    out.write('    </triangles>\n   </mesh>\n  </object>\n </resources>\n'
              ' <build>\n  <item objectid="1"/>\n </build>\n</model>\n')
    ncol = max(int(C.max()) if len(C) else 1, len(palette), 1)
    colours = [_hex(palette[i] if i < len(palette) else '#cfc8bc') for i in range(ncol)]
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
        # filament colours: Bambu Studio / OrcaSlicer read this file, PrusaSlicer the second one
        z.writestr('Metadata/project_settings.config', json.dumps({'filament_colour': colours}, indent=1))
        z.writestr('Metadata/Slic3r_PE.config', '; extruder_colour = ' + ';'.join(colours) + '\n')
    return buf.getvalue(), dict(triangulos=int(len(F)), pintados=int((C > 1).sum()), cores=colours)


def check_3mf(data, n_expected):
    """Re-read the 3MF: XML valid and triangle count right."""
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        root = ET.fromstring(z.read('3D/3dmodel.model'))
    ns = '{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}'
    n = len(root.findall(f'.//{ns}triangle'))
    return n == n_expected, n


def write_obj(tris_list, paint_list, palette, name='modelo'):
    """OBJ + MTL, one material per colour (OrcaSlicer and Bambu Studio map them to filaments
    when importing a coloured OBJ). Returns (obj text, mtl text)."""
    T = np.concatenate(tris_list) if tris_list else np.zeros((0, 3, 3))
    C = np.concatenate([np.asarray(p, np.uint8) for p in paint_list]) if paint_list else np.zeros(0, np.uint8)
    v, inv = np.unique(np.round(T.reshape(-1, 3), 5), axis=0, return_inverse=True)
    F = inv.reshape(-1, 3) + 1
    o = io.StringIO()
    o.write(f'# EFC3D\nmtllib {name}.mtl\no {name}\n')
    o.write(''.join(f'v {x:.5f} {y:.5f} {z:.5f}\n' for x, y, z in v))
    for col in sorted(set(C.tolist()) or {1}):
        o.write(f'usemtl cor_{col}\n')
        o.write(''.join(f'f {a} {b} {c}\n' for a, b, c in F[C == col]))
    m = io.StringIO()
    for col in sorted(set(C.tolist()) or {1}):
        h = _hex(palette[col - 1] if 0 < col <= len(palette) else '#cfc8bc').lstrip('#')
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        m.write(f'newmtl cor_{col}\nKd {r:.4f} {g:.4f} {b:.4f}\nKa 0 0 0\nKs 0 0 0\nd 1\nillum 1\n\n')
    return o.getvalue(), m.getvalue()
