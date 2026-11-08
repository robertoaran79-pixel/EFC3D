"""EFC3D: printers (bed size) and plates.

Every export checks the parts against the bed of the chosen printer and spreads them over as
many plates as needed: one 3MF per plate, each part already in its print position and inside
the bed. A part bigger than the bed is reported (and gets a plate of its own anyway).
"""
import numpy as np

# name, bed x, bed y, max height (mm)
PRINTERS = {
    'a1mini': ('Bambu Lab A1 mini', 180, 180, 180),
    'a1': ('Bambu Lab A1', 256, 256, 256),
    'p1s': ('Bambu Lab P1S / P1P / X1C', 256, 256, 256),
    'h2d': ('Bambu Lab H2D', 350, 320, 325),
    'mk4': ('Prusa MK4 / MK4S', 250, 210, 220),
    'ender3': ('Creality Ender 3 V2 / V3', 220, 220, 250),
    'k1': ('Creality K1 / K1C', 220, 220, 250),
    'k2': ('Creality K2', 260, 260, 260),
    'k2pro': ('Creality K2 Pro', 300, 300, 300),
    'k2plus': ('Creality K2 Plus', 350, 350, 350),
}
DEFAULT = 'a1'
MARGIN = 5.0          # from the bed edge
GAP = 5.0             # between parts


def get(pid, custom=None):
    if pid == 'custom' and custom:
        x, y, z = (float(custom.get(k, 0) or 0) for k in ('x', 'y', 'z'))
        if x > 20 and y > 20 and z > 20:
            return dict(id='custom', nome=f'Personalizada {x:g} × {y:g} × {z:g} mm', x=x, y=y, z=z)
    n, x, y, z = PRINTERS.get(pid) or PRINTERS[DEFAULT]
    return dict(id=pid if pid in PRINTERS else DEFAULT, nome=n, x=x, y=y, z=z)


def listing():
    return [dict(id=k, nome=v[0], x=v[1], y=v[2], z=v[3]) for k, v in PRINTERS.items()]


def _rot90(T, c):
    out = T.copy()
    x, y = T[..., 0] - c[0], T[..., 1] - c[1]
    out[..., 0] = c[0] - y
    out[..., 1] = c[1] + x
    return out


def pack(items, printer):
    """items: list of dict(nome, T (n,3,3) in print position), plus any extra keys.
    Returns (plates, warnings): plates = list of lists of (item, T placed on the bed)."""
    W, D, H = printer['x'] - 2 * MARGIN, printer['y'] - 2 * MARGIN, printer['z']
    warns = []
    prepared = []
    for it in items:
        T = np.asarray(it['T'], np.float64)
        lo, hi = T.reshape(-1, 3).min(0), T.reshape(-1, 3).max(0)
        sx, sy, sz = hi - lo
        T = T - lo                                     # corner at the origin, on the bed
        rot = False
        fits = sx <= W and sy <= D
        if not fits and sy <= W and sx <= D:           # turned 90 degrees it fits
            T = _rot90(T, (0, 0, 0))
            l2 = T.reshape(-1, 3).min(0)
            T = T - l2
            sx, sy = sy, sx
            rot, fits = True, True
        big = (not fits) or sz > H
        if big:
            warns.append(f"{it['nome']}: {sx:.0f} × {sy:.0f} × {sz:.0f} mm não cabe na {printer['nome']} "
                         f"({printer['x']:g} × {printer['y']:g} × {printer['z']:g} mm). Reduza o tamanho (aba Modelo) "
                         'ou corte em mais partes.')
        prepared.append(dict(it=it, T=T, sx=sx, sy=sy, big=big, rot=rot))
    # biggest first, shelves (rows) on each plate
    prepared.sort(key=lambda p: -(p['sx'] * p['sy']))
    plates = []                                        # each: dict(rows=[...], items=[])
    for p in prepared:
        placed = False
        if not p['big']:
            for pl in plates:
                if pl.get('big'):
                    continue
                pos = _place(pl, p, W, D)
                if pos is not None:
                    pl['items'].append((p, pos))
                    placed = True
                    break
        if not placed:
            pl = dict(rows=[], items=[], big=p['big'])
            pos = _place(pl, p, max(W, p['sx']), max(D, p['sy']))
            pl['items'].append((p, pos))
            plates.append(pl)
    out = []
    for pl in plates:
        lst = []
        for p, (x, y) in pl['items']:
            T = p['T'] + np.array([MARGIN + x, MARGIN + y, 0.0])
            lst.append((p['it'], T))
        out.append(lst)
    return out, warns


def _place(pl, p, W, D):
    """Shelf packing: a row is as deep as its first part; parts go left to right."""
    for row in pl['rows']:
        if row['x'] + p['sx'] <= W + 1e-6 and p['sy'] <= row['h'] + 1e-6:
            pos = (row['x'], row['y'])
            row['x'] += p['sx'] + GAP
            return pos
    y = sum(r['h'] + GAP for r in pl['rows'])
    if y + p['sy'] <= D + 1e-6 and p['sx'] <= W + 1e-6:
        pl['rows'].append(dict(y=y, h=p['sy'], x=p['sx'] + GAP))
        return (0.0, y)
    return None
