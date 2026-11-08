"""Automatic articulation planner.

Reads the model the way a flexi designer would:
  * top silhouette -> trunk (head, body, tail) and limbs (paws that stick out)
  * trunk cut into thin slices along its length -> where it is thick, where it narrows
  * body joints (chain) go where the trunk narrows (neck, waist, tail base), as many as fit
  * limb joints (open/close hinge) go where each paw leaves the trunk
Everything the user would otherwise have to guess (type, size, height, direction, spacing)
is decided here.
"""
import math

import numpy as np
import manifold3d as mf

import engine as E

RND = mf.JoinType.Round


def _largest(cs):
    comps = cs.decompose()
    return max(comps, key=lambda c: c.area()) if comps else cs


def _poly_list(cs):
    return [np.asarray(p).round(3).tolist() for p in cs.to_polygons()]


def _verts(cs):
    pts = [np.asarray(p) for p in cs.to_polygons() if len(p)]
    return np.concatenate(pts) if pts else np.zeros((0, 2))


def _frame(origin, angle):
    T = E.rot_z(angle)
    T[:3, 3] = [origin[0], origin[1], 0.0]
    return T


def _prism(cs, zlo=-500.0, zhi=500.0):
    return cs.extrude(zhi - zlo).translate([0, 0, zlo])


def analyze(m):
    """Split the silhouette into trunk and limbs and measure the trunk along its length."""
    P = E._outer(m.project())
    b = P.bounds()
    W = max(b[2] - b[0], b[3] - b[1])
    core = None
    for k in (0.12, 0.10, 0.08, 0.15):
        r = k * W
        c = P.offset(-r, RND).offset(r, RND)
        if not c.is_empty():
            core = _largest(c)
            break
    if core is None:
        core = P
    limbs = [q for q in (P - core.offset(0.6, RND)).decompose() if q.area() > max(12.0, 0.004 * P.area())]
    # main axis of the trunk
    v = _verts(core)
    cen = v.mean(0)
    w, V = np.linalg.eigh(np.cov((v - cen).T))
    ax = V[:, int(np.argmax(w))]
    # a protrusion that continues the trunk (tail, snout) is part of the body, not a limb:
    # it leaves the trunk near the middle line, at one end; legs leave it from the sides
    perp = np.array([ax[1], -ax[0]])
    xs = (v - cen) @ perp
    half_w = max(1.0, float(np.max(np.abs(xs))))
    ts_core = (v - cen) @ ax
    keep = []
    for q in limbs:
        root = q ^ core.offset(2.0, RND)
        if root.is_empty():
            keep.append(q)
            continue
        rb = root.bounds()
        rc = np.array([(rb[0] + rb[2]) / 2, (rb[1] + rb[3]) / 2])
        xr = float((rc - cen) @ perp)
        tr = float((rc - cen) @ ax)
        at_end = tr > 0.6 * ts_core.max() or tr < 0.6 * ts_core.min()
        if abs(xr) < 0.3 * half_w and at_end:
            core = core + q.offset(0.7, RND)
        else:
            keep.append(q)
    limbs = keep
    core = _largest(core)
    angle = math.degrees(math.atan2(-ax[0], ax[1]))          # joint convention: dir = (-sin a, cos a)
    bb = m.bounding_box()
    trunk = E.flat(m ^ _prism(core.offset(0.4, RND), bb[2] - 1, bb[5] + 1))
    prof = _profile(trunk, cen, angle)
    # the head is the heavier end: chain links point away from it
    n = len(prof['t'])
    if n > 4:
        k = max(1, int(0.4 * n))
        if np.max(prof['area'][-k:]) > np.max(prof['area'][:k]):
            angle += 180.0
            prof = _profile(trunk, cen, angle)
    return dict(P=P, core=core, limbs=limbs, origin=cen, angle=angle, trunk=trunk, prof=prof, W=W, m=m)


def _profile(trunk, cen, angle, step=1.0):
    T = _frame(cen, angle)
    Ti = np.linalg.inv(T)
    L = E.X(trunk, Ti)
    lb = L.bounding_box()
    Q = E.X(L, E.rot_x(-90))                                   # local y -> -z (slice plane)
    ts, area, hgt, zc, xc, zlo, zhi = [], [], [], [], [], [], []
    for t in np.arange(lb[1] + 0.5, lb[4] - 0.4, step):
        cs = Q.slice(-t)
        if cs.is_empty():
            continue
        c = _largest(cs)
        bx = c.bounds()
        ts.append(t)
        area.append(cs.area())
        hgt.append(bx[3] - bx[1])
        zc.append((bx[3] + bx[1]) / 2)
        xc.append((bx[0] + bx[2]) / 2)
        zlo.append(bx[1])
        zhi.append(bx[3])
    return dict(t=np.array(ts), area=np.array(area), h=np.array(hgt), zc=np.array(zc), xc=np.array(xc),
                zlo=np.array(zlo), zhi=np.array(zhi), ymin=lb[1], ymax=lb[4])


def _smooth(a, k=2):
    if len(a) < 2 * k + 1:
        return a
    ker = np.ones(2 * k + 1) / (2 * k + 1)
    return np.convolve(np.pad(a, k, mode='edge'), ker, mode='valid')


def _world(an, x_local, t):
    T = _frame(an['origin'], an['angle'])
    p = T @ np.array([x_local, t, 0.0, 1.0])
    return float(p[0]), float(p[1])


def _local_t(an, x, y):
    T = _frame(an['origin'], an['angle'])
    p = np.linalg.inv(T) @ np.array([x, y, 0.0, 1.0])
    return float(p[1]), float(p[0])


def limb_roots(an):
    """For every limb: where it leaves the trunk, which way it points, its zone."""
    out = []
    for limb in an['limbs']:
        root = limb ^ an['core'].offset(2.0, RND)
        if root.is_empty():
            continue
        rb = root.bounds()
        rc = np.array([(rb[0] + rb[2]) / 2, (rb[1] + rb[3]) / 2])
        v = _verts(limb)
        if not len(v):
            continue
        dist = np.linalg.norm(v - rc, axis=1)
        tip = v[int(np.argmax(dist))]
        L = float(dist.max())
        if L < 6.0:
            continue
        d = (tip - rc) / L
        # the stretch of trunk this limb is glued to (no body seam may cross it)
        corners = np.array([[rb[0], rb[1]], [rb[2], rb[1]], [rb[0], rb[3]], [rb[2], rb[3]]])
        ts = [_local_t(an, *p)[0] for p in corners]
        out.append(dict(limb=limb, root=rc, tip=tip, dir=d, length=L, t_range=(min(ts), max(ts))))
    return out


def chain_ok(an, t, size, clearance, budget):
    """Can a chain joint sit at position t along the trunk? Returns the joint or None."""
    pr = an['prof']
    i = int(np.argmin(np.abs(pr['t'] - t)))
    x, y = _world(an, pr['xc'][i], pr['t'][i])
    j = dict(type='corrente', x=x, y=y, angle=an['angle'], size=size, clearance=clearance,
             yaw=25.0, pitch=15.0, orcamento=budget)
    try:
        j = E.auto_fill(an['trunk'], j)
        if E.BODY_JOINT == 'cutter':
            sc, dz, geo = E.cutter_plan(an['trunk'], j)
            p = dict(s=sc, **geo)
        else:
            p = E.chain_plan(an['trunk'], j)
    except E.SkinBreak:
        return None
    except Exception:
        return None
    j['_t'] = float(pr['t'][i])
    if E.BODY_JOINT == 'cutter':
        # the loops reach half the cutter depth into each side: the next joint must start
        # beyond this one's loops plus its own
        j['_reach'] = E.FJM_D * min(p['s'], E.BODY_SN) + 1.0
    else:
        j['_reach'] = p['Ya'] + p['r'] + p['ce'] + E.WALL
    j['_plan'] = p
    j['papel'] = 'corpo'
    return j


def hinge_ok(an, t, clearance, size=2.0):
    """Thin stretch of trunk (tail): a side-to-side hinge instead of a chain link."""
    pr = an['prof']
    i = int(np.argmin(np.abs(pr['t'] - t)))
    # the flat bed joint only needs head + gap + roof; the old mid-height pin needed twice that
    # pin + socket: double cone of radius size, clearance and wall above and below
    if pr['h'][i] < 2 * (size + clearance * 1.42 + E.WALL) + 1.0:
        return None
    x, y = _world(an, pr['xc'][i], pr['t'][i])
    j = dict(type='dobradica', x=x, y=y, angle=an['angle'], size=size, clearance=clearance, yaw=25.0, pitch=0.0)
    try:
        j = E.auto_fill(an['trunk'], j)
    except Exception:
        return None
    half = float(j['width']) - 2.0
    if half < size + 2.5:
        return None
    # a stretch that floats above the bed (raised tail) stays fixed: the moving part must stand on the bed
    if E.bottom_height(an['trunk'], j['x'], j['y']) > an['trunk'].bounding_box()[2] + 0.5:
        return None
    j['_t'] = float(pr['t'][i])
    j['_reach'] = max(half + 0.6, size + clearance + 2.0) + 1.0
    j['papel'] = 'corpo'
    return j


def plan(an, clearance=0.4, budget=0.0, size=1.2):
    """Full automatic joint plan: body joints along the trunk (chain where it is tall
    enough, side-to-side hinge where it is thin, like a tail) + one hinge per limb."""
    pr = an['prof']
    joints = []
    if len(pr['t']) < 6:
        return joints, ['O modelo e pequeno demais para planejar juntas.']
    notes = []
    roots = limb_roots(an)
    blocked = [(r['t_range'][0] - 2.5, r['t_range'][1] + 2.5) for r in roots]
    A = _smooth(pr['area'], 2)
    t = pr['t']
    n = len(t)
    # head: biggest section in the first part; neck: first narrowing after it
    k = max(2, int(0.45 * n))
    ih = int(np.argmax(A[:k]))
    start = None
    for i in range(ih + 1, n - 1):
        if A[i] <= A[i - 1] and A[i] <= A[i + 1]:
            start = i
            break
    if start is None:
        start = min(n - 1, ih + 3)

    def free(tt):
        return all(not (lo <= tt <= hi) for lo, hi in blocked)

    def best_in(lo, hi):
        """Best spot in [lo, hi]: the narrowest section that takes a chain link; failing
        that, one that takes a side-to-side hinge."""
        idx = [i for i in range(n) if lo <= t[i] <= hi and free(t[i])]
        idx.sort(key=lambda i: A[i])
        for i in idx[:10]:
            for s in (size, size * 0.85):
                j = chain_ok(an, t[i], s, clearance, budget)
                if j:
                    return j
        for i in idx[:10]:
            j = hinge_ok(an, t[i], clearance)
            if j:
                return j
        return None

    seg = 9.0                                   # shortest segment worth having (mm)
    j = best_in(t[start] - 4, t[start] + 4) or best_in(t[start], t[start] + 14)
    tail_end = t[-1] - seg
    while j is not None and j['_t'] < tail_end:
        joints.append(j)
        gap = max(seg, j['_reach'] + 3.0)
        lo = j['_t'] + gap
        j = None
        w0 = lo
        while j is None and w0 < tail_end:          # walk forward window by window
            j = best_in(w0, w0 + 4.0)
            w0 += 4.0
    for r in roots:
        joints += [deepen_shoulder(an, q) for q in limb_joints(r, clearance)]
    return joints, notes


def first_top(m, x, y, z0=0.15):
    """Height of the first surface met going up from the bed (the limb's own top, not a
    head or body hanging above it)."""
    hits = m.ray_cast([x, y, z0], [x, y, 1000.0])
    zs = sorted(h.position[2] for h in hits) if hits else []
    return zs[0] if zs else 0.0


def deepen_shoulder(an, j):
    """The top view often swallows the start of a leg into the body outline (big chibi head
    or chest, rounded outline). Walk from the planned shoulder towards the body while the
    leg keeps its width and height, and put the pivot near where it really meets the body,
    so the whole leg moves and not only the paw."""
    if j.get('parte') != 'ombro' or an.get('m') is None:
        return j
    m = an['m']
    d = E.direction(j)
    x0, y0 = j['x'], j['y']
    zb = m.bounding_box()[2]
    try:
        hw0 = E.section_half_width(m, j, zb + 1.5)
    except Exception:
        return j
    top0 = first_top(m, x0, y0, zb + 0.15)
    if top0 <= zb + 1.0:
        return j
    last = 0.0
    for t in np.arange(-1.0, -16.01, -1.0):
        x, y = x0 + d[0] * t, y0 + d[1] * t
        hw = E.section_half_width(m, dict(j, x=x, y=y), zb + 1.5)
        top = first_top(m, x, y, zb + 0.15)
        if hw > 1.35 * hw0 + 0.5 or top > 1.3 * (top0 - zb) + zb:
            break
        last = t
    t_ = last + 2.0
    if t_ <= -2.0:
        j = dict(j, x=float(x0 + d[0] * t_), y=float(y0 + d[1] * t_), raiz=[float(x0), float(y0)])
    return j


LIMB_PIVOT = 1.5        # shoulder pivot this far into the limb from where it leaves the body
ELBOW_MIN_LEN = 30.0    # limbs at least this long also get an elbow (the paw beyond must stay a real piece)


def limb_joints(r, clearance=0.4):
    """Flat bed joints for one limb: shoulder, and an elbow when the limb is long."""
    d = r['dir']
    ang = math.degrees(math.atan2(-d[0], d[1]))
    out = []
    ts = [LIMB_PIVOT]
    if r['length'] >= ELBOW_MIN_LEN:
        ts.append(max(13.5, 0.5 * r['length']))
    for i, t_ in enumerate(ts):
        piv = r['root'] + d * t_
        out.append(dict(type='dobradica', x=float(piv[0]), y=float(piv[1]), angle=ang, size=2.6,
                        yaw=25.0, pitch=0.0, clearance=clearance, papel='membro',
                        parte='ombro' if i == 0 else 'cotovelo'))
    return out


def zones(an):
    """2D regions (world XY) each kind of joint may cut: chain joints only the trunk,
    limb joints only their own limb (plus room for the pin)."""
    return dict(trunk=an['core'].offset(0.4, RND), limbs=[l.offset(0.5, RND) for l in an['limbs']])


def _smooth_zone(z, r=1.5):
    """Zone outlines come from the silhouette (many tiny jagged segments). Wherever a cut
    stops at the zone border that jag would show on the skin, so the outline is rounded."""
    if z is None or z.is_empty():
        return z
    z = z.offset(r, RND).offset(-2 * r, RND).offset(r, RND)
    return z.simplify(0.05)


def zone_for(an, j):
    return _smooth_zone(_zone_for(an, j))


def _zone_for(an, j):
    if j.get('papel') == 'corpo' or (j.get('type') == 'corrente' and j.get('papel') is None):
        # the whole body outline except the limbs (bumps outside the smoothed trunk must be
        # cut too, or the two segments stay glued there)
        lim = [l.offset(0.3, RND) for l in an['limbs']]
        z = an['P'].offset(1.0, RND)
        for l in lim:
            z = z - l
        return z
    p = np.array([j['x'], j['y']])
    best, bd = None, 1e9
    for l in an['limbs']:
        v = _verts(l)
        if not len(v):
            continue
        dd = float(np.min(np.linalg.norm(v - p, axis=1)))
        if (l ^ mf.CrossSection.circle(0.5, 12).translate(p.tolist())).area() > 0:
            dd = 0.0
        if dd < bd:
            best, bd = l, dd
    if best is None or bd > 12:
        return None
    pin = mf.CrossSection.circle(float(j['size']) + 5.0, 48).translate(p.tolist())
    z = best.offset(0.5, RND)
    if j.get('raiz') is not None and an.get('m') is not None:
        # shoulder moved into the body outline: the stretch of leg from the outline to the
        # pivot belongs to the leg zone too (as wide as the leg there)
        r0 = np.array(j['raiz'], float)
        hw = E.section_half_width(an['m'], dict(j, x=float(r0[0]), y=float(r0[1])), an['m'].bounding_box()[2] + 1.5)
        rr = hw + 0.8
        z = z + (mf.CrossSection.circle(rr, 32).translate(r0.tolist()) +
                 mf.CrossSection.circle(rr, 32).translate(p.tolist())).hull()
    return z + pin


def snap(an, x, y, joints, clearance=0.4, budget=0.0):
    """User clicked (x, y) in "add joint" mode: add ONE new joint right there, of the kind that
    fits the spot (body loops, thin-body hinge, or limb loops). The joints already there are
    never moved or removed; if the new one is close to one of them the message says so (the
    generator then reports it if they really collide). Returns (new joint or None, message)."""
    p = np.array([x, y])
    dot = mf.CrossSection.circle(0.5, 12).translate([x, y])
    inside_core = (an['core'] ^ dot).area() > 0
    newj = None
    if not inside_core:
        for r in limb_roots(an):
            if (r['limb'].offset(1.0, RND) ^ dot).area() > 0:
                d = r['dir']
                ang = math.degrees(math.atan2(-d[0], d[1]))
                newj = dict(type='dobradica', x=float(x), y=float(y), angle=ang, size=2.6, yaw=25.0, pitch=0.0,
                            clearance=clearance, papel='membro', parte='extra')
                break
        if newj is None:
            return None, 'Clique no corpo, no rabo ou numa pata.'
        kind = 'Junta de pata'
    else:
        tc, _ = _local_t(an, x, y)
        for s in (1.4, 1.2, 1.0):
            newj = chain_ok(an, tc, s, clearance, budget)
            if newj:
                break
        kind = 'Junta de corpo (elos)'
        if newj is None:
            newj = hinge_ok(an, tc, clearance)
            kind = 'Junta de corpo fino (abre e fecha)'
        if newj is None:
            m = an.get('m')
            if m is not None:
                zb = m.bounding_box()[2]
                b = E.bottom_height(m, x, y) - zb
                if b > 0.5:
                    return None, (f'Nesse ponto a peça não encosta na mesa (fica {b:.1f} mm acima). A parte que '
                                  f'giraria começaria no ar e pediria suporte, então não dá junta aqui. '
                                  f'Tente onde ela apoia na mesa.')
            return None, ('Nesse ponto não cabe junta que prenda: a parte é fina ou baixa demais. '
                          'Tente mais perto do corpo.')
    # warn (never remove) when another joint is close
    near = []
    for k, q in enumerate(joints):
        dd = float(np.hypot(float(q['x']) - newj['x'], float(q['y']) - newj['y']))
        if dd < 10.0:
            near.append((dd, k))
    msg = f'{kind} adicionada.'
    if near:
        dd, k = min(near)
        msg += (f' Ficou a {dd:.0f} mm da J{k + 1}: se as duas não couberem juntas, ao gerar o programa avisa '
                f'e pula uma delas. Arraste para afastar se quiser.')
    return newj, msg