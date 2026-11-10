"""EFC3D: Corte livre (módulo novo da v1.6).

O usuário desenha uma linha fechada sobre a superfície (em volta de um braço, de uma perna, da
cabeça) e o app corta ali, só dentro da linha: não é um plano infinito como no fatiador, então
não corta o outro braço que cruza o mesmo plano. A face do corte segue a linha desenhada
(superfície lisa, harmônica) ou é um plano local de melhor ajuste.

Encaixes: só colar (folga pequena), pino redondo que gira, pino que gira com trava (clique),
pino fixo em losango, trava de pressão, pino na peça e cavilha solta.

O módulo só lê o modelo e devolve peças; não mexe nas juntas nem no "Separar por cor". Ele
reaproveita funções do split.py sem alterá-las.
"""
import base64
import math
import sys
import time
import traceback
import re

import numpy as np
import manifold3d as mf

import engine as E
import split as SPL
from split import (_frame, _T, _inv, _vol, _chk, _fmt, _plane_fit, _smooth_loop3, border_surface,
                   _limb_pin, _on_surface, tri_array, _inradius, _depth_along, _fit, S2)

import os as _os
_DBG = bool(_os.environ.get('FLEXI_DBG'))

DEF = dict(forma='curva', encaixe='colar', folga=0.2, folga_pino=0.4, pino_mm=0.0, inverter=False, parede=1.2)
ENCAIXES = ('colar', 'redondo', 'giratorio', 'losango', 'trava', 'peca', 'cavilha')
NOMES = dict(colar='só colar', redondo='pino redondo (gira)', giratorio='pino que gira com trava',
             losango='pino fixo', trava='trava de pressão', peca='pino na peça', cavilha='cavilha solta')
GIRA = ('redondo', 'giratorio')


# ----------------------------------------------------------------------------- geometria
def _clean_loop(P):
    P = np.asarray(P, np.float64).reshape(-1, 3)
    if len(P) < 3:
        return None
    keep = np.ones(len(P), bool)
    keep[1:] = np.linalg.norm(np.diff(P, axis=0), axis=1) > 1e-4
    P = P[keep]
    if len(P) > 3 and np.linalg.norm(P[0] - P[-1]) < 1e-4:
        P = P[:-1]
    if len(P) < 3:
        return None
    per = float(np.linalg.norm(np.diff(np.vstack([P, P[:1]]), axis=0), axis=1).sum())
    return P if per >= 2.0 else None


def _inside(poly, pts):
    """Pontos 2D dentro do polígono (regra par e ímpar). Rotina em C do scikit-image (dezenas de
    vezes mais rápida); a versão em numpy fica de reserva."""
    try:
        from skimage.measure import points_in_poly
        pts = np.asarray(pts, np.float64)
        if not len(pts):
            return np.zeros(0, bool)
        return points_in_poly(pts, np.asarray(poly, np.float64))
    except Exception:
        pass
    x, y = pts[:, 0][:, None], pts[:, 1][:, None]
    x0, y0 = poly[:, 0][None, :], poly[:, 1][None, :]
    x1, y1 = np.roll(poly[:, 0], -1)[None, :], np.roll(poly[:, 1], -1)[None, :]
    cond = (y0 > y) != (y1 > y)
    with np.errstate(divide='ignore', invalid='ignore'):
        xi = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
    return (cond & (x < xi)).sum(1) % 2 == 1


def _heightbox(ticks_x, ticks_y, H, gap):
    """Sólido fechado entre H - gap/2 e H + gap/2 sobre a grade (coordenadas locais)."""
    X, Y = np.meshgrid(ticks_x, ticks_y, indexing='ij')
    nx, ny = X.shape
    bot = np.stack([X, Y, H - gap / 2], axis=-1).reshape(-1, 3)
    top = np.stack([X, Y, H + gap / 2], axis=-1).reshape(-1, 3)
    V = np.vstack([bot, top])
    idx = np.arange(nx * ny).reshape(nx, ny)
    a, b, c, d = idx[:-1, :-1].ravel(), idx[1:, :-1].ravel(), idx[1:, 1:].ravel(), idx[:-1, 1:].ravel()
    off = nx * ny
    F = [np.stack([a, c, b], 1), np.stack([a, d, c], 1),
         np.stack([a + off, b + off, c + off], 1), np.stack([a + off, c + off, d + off], 1)]
    ring = np.concatenate([idx[:, 0], idx[-1, 1:], idx[-2::-1, -1], idx[0, -2:0:-1]])
    r1 = np.roll(ring, -1)
    F += [np.stack([ring, r1, r1 + off], 1), np.stack([ring, r1 + off, ring + off], 1)]
    F = np.vstack(F)
    for FF in (F, F[:, ::-1].copy()):
        m = mf.Manifold(mf.Mesh(vert_properties=np.ascontiguousarray(V, np.float32),
                                tri_verts=np.ascontiguousarray(FF, np.uint32)))
        if m.status() == mf.Error.NoError and m.volume() > 0:
            return m
    return m


class Line:
    """Uma linha desenhada: superfície do corte, fatia fina (a folga) e pontos de teste."""

    def __init__(self, P, forma, gap, diag, centro_modelo):
        self.P = P
        c, nn, dev = _plane_fit(P)
        if np.dot(centro_modelo - c, nn) > 0:          # o resto do modelo fica do lado -nn
            nn = -nn
        self.dev = dev
        self.forma = forma
        self.gap = gap
        self.diag = diag
        self._build(c, nn)

    def _build(self, c, nn):
        self.c, self.nn = c, nn
        self.Fr = _frame(nn)
        if self.forma == 'plano':
            self.hf = lambda xy: np.zeros(len(np.atleast_2d(xy)))
            self.info = dict(desvio=self.dev, curvatura=0.0, zsec=0.02, tol=0.1)
        else:
            _, self.hf, self.info = border_surface(self.P, c, nn, self.diag)
        Q = _smooth_loop3((self.P - c) @ self.Fr, 0.8)
        self.Q2 = Q[:, :2]
        self.R0 = float(np.linalg.norm(self.Q2, axis=1).max())
        if self.forma == 'misto':
            # plano no miolo e, a até 1,5 mm da linha, a superfície que segue a linha: a face fica plana onde
            # o pino entra e fecha o contato junto da borda (o pescoço colado no queixo, o braço na axila)
            from scipy.spatial import cKDTree
            hc, Qp = self.hf, self.Q2
            Qd = np.vstack([Qp[k] + (Qp[(k + 1) % len(Qp)] - Qp[k]) * t for k in range(len(Qp)) for t in np.linspace(0, 1, 8, endpoint=False)])
            kd, b = cKDTree(Qd), 1.5 * _CUR_K[0]

            def hm(xy):
                xy = np.atleast_2d(xy)
                d = kd.query(xy)[0]
                w = np.where(_inside(Qp, xy), np.clip(1.0 - d / b, 0.0, 1.0), 1.0)
                return hc(xy) * (w * w * (3.0 - 2.0 * w))
            self.hf = hm

    def flip(self):
        self._build(self.c, -self.nn)

    def slab(self):
        """Fatia fina (espessura = folga) que passa pela linha e só vai até um pouco além dela."""
        margin = 1.5 + (2.0 * self.dev if self.forma == 'plano' else 0.0)
        cs = mf.CrossSection([self.Q2.tolist()], mf.FillRule.NonZero)
        if cs.is_empty() or cs.area() < 0.5:
            raise ValueError('A linha não envolve uma área: desenhe em volta da parte, fechando a volta.')
        reg = cs.offset(margin, mf.JoinType.Round, 2.0, 32)
        b = reg.bounds()
        ext = max(b[2] - b[0], b[3] - b[1])
        step = float(np.clip(ext / 140.0, 0.12, 0.6))
        tx = np.arange(b[0] - step, b[2] + 2 * step, step)
        ty = np.arange(b[1] - step, b[3] + 2 * step, step)
        X, Y = np.meshgrid(tx, ty, indexing='ij')
        H = self.hf(np.stack([X.ravel(), Y.ravel()], 1)).reshape(X.shape)
        box = _heightbox(tx, ty, H, self.gap)
        zs = float(np.abs(H).max()) + self.gap + 2.0
        prism = mf.Manifold.extrude(reg, 2 * zs).translate([0.0, 0.0, -zs])
        loc = E.flat(box ^ prism)
        return E.X(loc, _T(self.Fr, self.c))

    def inside_loop(self, V):
        """Algum ponto (mundo) cai dentro da linha (vista de cima da face do corte)?"""
        L = (np.asarray(V, np.float64) - self.c) @ self.Fr
        cs = mf.CrossSection([self.Q2.tolist()], mf.FillRule.NonZero).offset(-0.3, mf.JoinType.Round, 2.0, 16)
        polys = cs.to_polygons() if not cs.is_empty() else [self.Q2.tolist()]
        ins = np.zeros(len(L), bool)
        for pl in polys:
            ins ^= _inside(np.asarray(pl, np.float64), L[:, :2])
        return bool(ins.any())

    def probes(self, side, n=36):
        """Pontos de teste dentro da linha, logo acima (+1) ou abaixo (-1) da face do corte."""
        cs = mf.CrossSection([self.Q2.tolist()], mf.FillRule.NonZero).offset(-0.4, mf.JoinType.Round, 2.0, 16)
        if cs.is_empty():
            cs = mf.CrossSection([self.Q2.tolist()], mf.FillRule.NonZero)
        b = cs.bounds()
        g = np.linspace(0, 1, 15)
        pts = np.stack(np.meshgrid(b[0] + g * (b[2] - b[0]), b[1] + g * (b[3] - b[1]), indexing='ij'), -1).reshape(-1, 2)
        polys = cs.to_polygons()
        ins = np.zeros(len(pts), bool)
        for pl in polys:
            ins ^= _inside(np.asarray(pl, np.float64), pts)
        pts = pts[ins]
        if len(pts) > n:
            pts = pts[np.linspace(0, len(pts) - 1, n).astype(int)]
        z = self.hf(pts) + side * (self.gap / 2 + 0.5)
        L = np.column_stack([pts, z])
        return L @ self.Fr.T + self.c


def _who(parts, pts):
    """Quantos pontos de teste caem dentro de cada parte."""
    cnt = np.zeros(len(parts), int)
    for p in pts:
        for k, m in enumerate(parts):
            if E.contains_point(m, p, 0.12):
                cnt[k] += 1
                break
    return cnt


# ----------------------------------------------------------------------------- pinos redondos
def _round(r, z0, z1, tip=True, seg=40):
    """Cilindro ao longo de z (local), com ponta a 45 graus (imprime sem suporte deitado)."""
    t = min(r, max(0.0, (z1 - z0) - 0.2)) if tip else 0.0
    body = mf.Manifold.cylinder(max(0.05, z1 - z0 - t), r, r, seg).translate([0.0, 0.0, z0])
    if t > 0:
        body = body + mf.Manifold.cylinder(t, r, max(0.05, r - t), seg).translate([0.0, 0.0, z1 - t])
    return body


def _round_click(r, z0, z1, c, seg=40):
    """Pino redondo que gira e não sai: anel com rampas a 45 graus perto da ponta e fenda para
    as duas metades fecharem ao entrar. Furo com a câmara onde o anel encaixa."""
    b = min(0.4, max(0.25, 0.2 * r))
    zb = z1 - r - b - 0.4
    ring = lambda rr, h, z, rt=None: mf.Manifold.cylinder(h, rr, rt if rt is not None else rr, seg).translate([0.0, 0.0, z])
    pin = _round(r, z0, z1)
    pin = E.flat(pin + ring(r, b, zb - b, r + b) + ring(r + b, b, zb, r))
    w = 2 * b + 0.3
    zs = z0 + 0.45 * (z1 - z0)
    slot = E.BOX(-w / 2, w / 2, -2 * r - 2, 2 * r + 2, zs, z1 + 1)
    pin = E.flat(pin - slot)
    k = c * 1.1
    hole = _round(r + c, z0, z1 + c)
    hole = E.flat(hole + ring(r + k, b + k, zb - b - k, r + b + k) + ring(r + b + k, b + k, zb, r + k))
    return pin, hole


def _round_pin(piece, body_parts, kind, clr, wall, c, nn, diag, hf, zsec, want_mm):
    """Pino redondo no corpo e furo na peça, no meio da seção do corte."""
    checks = []
    Fr = _frame(nn)
    Tw = _T(Fr, c)
    sec = E.X(piece, _inv(Tw)).slice(zsec)
    if sec.is_empty():
        return dict(checks=[_chk('aviso', 'Não achei a face do corte para o pino: saiu sem pino.')], piece=piece, body_parts=body_parts)
    comps = sec.decompose()
    if comps:
        sec = min(comps, key=lambda q: np.hypot((q.bounds()[0] + q.bounds()[2]) / 2, (q.bounds()[1] + q.bounds()[3]) / 2))
    inr, pole = _inradius(sec)
    r = (want_mm / 2.0) if want_mm else min(3.0, max(0.8, 0.3 * inr))
    room = inr - clr - 1.0
    if room < 0.7:
        return dict(checks=[_chk('aviso', 'A seção do corte é estreita demais para o pino: saiu sem pino.')], piece=piece, body_parts=body_parts)
    r = min(r, room)
    if hf is not None:
        c = c + nn * float(np.atleast_1d(hf(np.array([[pole[0], pole[1]]])))[0])
        Tw = _T(Fr, c)
    pt = c + Fr @ np.array([pole[0], pole[1], 0.0])
    t_piece = _depth_along(piece, pt + nn * 0.01, nn, diag)
    k_body = None
    for k, bp in enumerate(body_parts):
        if E.contains_point(bp, pt - nn * 0.3, 0.1):
            k_body = k
            break
    if k_body is None:
        return dict(checks=[_chk('aviso', 'Não achei a parte do outro lado do corte para o pino.')], piece=piece, body_parts=body_parts)
    L = min(5.0 * r, t_piece - clr - wall)
    if kind == 'giratorio':
        rg = max(r, 1.4)
        Lg = min(5.0 * rg, t_piece - clr - wall)
        if rg > room or Lg < 2.5 * rg:
            checks.append(_chk('aviso', 'Pouco material para o pino com trava (precisa de 2,8 mm de largura e profundidade): '
                                        'saiu o pino redondo simples.'))
            kind = 'redondo'
        else:
            r, L = rg, Lg
    if L < r + 0.4:
        return dict(checks=[_chk('aviso', 'A peça é curta demais para o pino: saiu sem pino.')], piece=piece, body_parts=body_parts)
    xy = np.array([pole[0], pole[1], 0.0])
    W = lambda m: E.X(m.translate(list(map(float, xy))), Tw)
    bp = body_parts[k_body]
    if kind == 'giratorio':
        pin, hole = _round_click(r, -0.8, L, clr)
        msg = (f'Pino redondo com trava: {_fmt(2 * r)} mm, {_fmt(L)} mm dentro da peça, folga {_fmt(clr, 2)} mm. '
               'Encaixa com um clique e gira sem soltar.')
    else:
        pin, hole = _round(r, -0.8, L), _round(r + clr, -0.05, L + clr)
        msg = f'Pino redondo: {_fmt(2 * r)} mm, {_fmt(L)} mm dentro da peça, folga {_fmt(clr, 2)} mm: a peça gira no pino.'
    bp = E.flat(bp + W(pin))
    piece = E.flat(piece - W(hole))
    body_parts = list(body_parts)
    body_parts[k_body] = bp
    checks.append(_chk('ok', msg))
    return dict(checks=checks, piece=piece, body_parts=body_parts)


# ----------------------------------------------------------------------------- área marcada (pincel e balde)
def decode_mask(b64, n):
    """Bits (1 por triângulo do modelo aberto, o menos significativo primeiro) -> bool (n,)."""
    try:
        raw = np.frombuffer(base64.b64decode(b64 or ''), np.uint8)
    except Exception:
        return None
    bits = np.unpackbits(raw, bitorder='little')
    if len(bits) < n:
        return None
    return bits[:n].astype(bool)


def encode_mask(m):
    return base64.b64encode(np.packbits(np.asarray(m, np.uint8), bitorder='little').tobytes()).decode('ascii')


def _components(sel, nb):
    """Componentes ligadas dos triângulos sel (bool) pelas arestas."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    n = len(sel)
    t = np.repeat(np.arange(n), 3)
    u = nb.reshape(-1)
    ok = (u >= 0) & sel[t] & sel[np.maximum(u, 0)]
    g = coo_matrix((np.ones(int(ok.sum())), (t[ok], u[ok])), shape=(n, n))
    _, lab = connected_components(g, directed=False)
    lab = np.where(sel, lab, -1)
    return lab


def mask_lines(S, mask, topo=None):
    """Bordas da área marcada como linhas fechadas (pontos no mundo) + pontos da peça + avisos.
    Limpa a marcação antes: manchas soltas do pincel saem e buracos pequenos são preenchidos."""
    v, f, nb = topo if topo is not None else SPL._topology(S)
    # corte em sequência: triângulos de outras peças (já separadas) não são buraco nem borda; a costura
    # com elas não vira linha de corte nova
    off, nb0 = _HT_OFF.get(id(nb), (None, None))
    T = v[f]
    area = np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1) / 2
    m = np.asarray(mask, bool).copy()
    if off is not None:
        m &= ~off
    msgs = []
    if not m.any():
        return [], None, msgs, m
    lab = _components(m, nb)
    ids, inv = np.unique(lab[m], return_inverse=True)
    ar = np.bincount(inv, weights=area[m])
    keep = ar >= max(1.0, 0.02 * ar.max())
    if (~keep).any():
        drop = np.isin(lab, ids[~keep])
        m[drop] = False
        msgs.append(f'{int((~keep).sum())} mancha(s) solta(s) da marcação foram ignoradas.')
    un = ~m if off is None else (~m & ~off)
    lab_u = _components(un, nb)
    idu, invu = np.unique(lab_u[un], return_inverse=True)
    aru = np.bincount(invu, weights=area[un])
    if len(idu) > 1:
        big = int(np.argmax(aru))
        fill = [k for k in range(len(idu)) if k != big and aru[k] < 0.3 * area[m].sum()]
        if fill:
            m[np.isin(lab_u, idu[fill])] = True
            msgs.append(f'{len(fill)} buraco(s) pequeno(s) dentro da marcação foram preenchidos.')
    if m.all() or (off is not None and (m | off).all()):
        return [], None, msgs + ['A marcação cobre o modelo inteiro.'], m
    # bordas: arestas entre um triângulo marcado e um não marcado, encadeadas em voltas
    tris = np.where(m)[0]
    nxt = {}
    for k in range(3):
        if off is None:
            o = nb[tris, k]
            out = (o < 0) | ~m[np.maximum(o, 0)]
        else:
            o = nb0[tris, k]                          # vizinho original: borda só contra a mesma peça
            out = (o < 0) | (~m[np.maximum(o, 0)] & ~off[np.maximum(o, 0)])
        for x, y in zip(f[tris[out], k].tolist(), f[tris[out], (k + 1) % 3].tolist()):
            nxt.setdefault(x, []).append(y)
    loops = []
    while nxt:
        start = next(iter(nxt))
        loop, cur = [start], start
        closed = False
        for _ in range(10 ** 7):
            lst = nxt.get(cur)
            if not lst:
                break
            y = lst.pop()
            if not lst:
                del nxt[cur]
            if y == start:
                closed = True
                break
            loop.append(y)
            cur = y
        if off is not None and not closed:
            continue                                  # trecho que termina na costura de outra peça: não é linha
        P = v[np.array(loop)]
        if len(P) >= 4 and np.linalg.norm(np.diff(np.vstack([P, P[:1]]), axis=0), axis=1).sum() >= 2.0:
            loops.append(P)
    cen = T[m].mean(1)
    if len(cen) > 400:
        cen = cen[np.linspace(0, len(cen) - 1, 400).astype(int)]
    return loops, cen, msgs, m


_VINCO = _os.environ.get('FLEXI_VINCO', '0') == '1'      # em teste: desligado
_VINCO_ETA = float(_os.environ.get('FLEXI_VINCO_ETA', '0.1'))
_MFL_CACHE = {}
_HT_CACHE = {}
_HT_OFF = {}


def _host_topo(topo, S, host_mesh):
    """A topologia da superfície original restrita aos triângulos que estão na peça que vai ser
    cortada: os de outras peças (já separadas por um corte anterior) ficam sem vizinhos. Na primeira
    peça (o modelo inteiro) volta a topologia original, sem mudar nada."""
    key = (id(topo[1]), id(host_mesh), int(host_mesh.num_tri()))
    if key in _HT_CACHE:
        return _HT_CACHE[key]
    cen = tri_array(S).mean(1)
    on = _on_surface(cen, tri_array(host_mesh), tol=0.05) >= 0
    if on.mean() > 0.995:
        out = topo
    else:
        v, f, nb = topo
        nb2 = np.array(nb, copy=True)
        nb2[~on] = -1
        m = nb2 >= 0
        nb2[m & ~on[np.maximum(nb2, 0)]] = -1
        out = (v, f, nb2)
        _HT_OFF[id(nb2)] = (~on, nb)                  # triângulos de outras peças e a vizinhança original
        if _DBG:
            print('host_topo:', int(on.sum()), 'de', len(on), 'triângulos do modelo nesta peça', flush=True)
    if len(_HT_CACHE) > 8:
        _HT_CACHE.clear()
        _HT_OFF.clear()
    _HT_CACHE[key] = out
    return out


def mask_from_lines(S, loops, topo, diag, centro, inverter=False):
    """Mesma conta com as mesmas linhas e a mesma malha (o corte pede a área 2 ou 3 vezes):
    guarda o resultado. Numa malha de milhões de triângulos cada conta leva segundos."""
    try:
        key = (id(topo[0]), len(topo[0]), hash(np.asarray(topo[0])[::max(1, len(topo[0]) // 64)].tobytes()),
               int((np.asarray(topo[2]) < 0).sum()), b''.join(np.ascontiguousarray(np.asarray(L, np.float64)).tobytes() for L in loops),
               float(diag), tuple(np.round(np.asarray(centro, np.float64), 6)), bool(inverter))
    except Exception:
        key = None
    if key is not None and key in _MFL_CACHE:
        r = _MFL_CACHE[key]
        return None if r is None else (r[0].copy(), r[1], None if r[2] is None else np.array(r[2]))
    r = _mask_from_lines(S, loops, topo, diag, centro, inverter)
    off = _HT_OFF.get(id(topo[2]))
    if r is not None and off is not None:
        r = (r[0] & ~off[0],) + tuple(r[1:])          # triângulos de outras peças nunca entram na área
    if key is not None:
        if len(_MFL_CACHE) > 6:
            _MFL_CACHE.clear()
        _MFL_CACHE[key] = None if r is None else (r[0].copy(), r[1], None if r[2] is None else np.array(r[2]))
    return r


def _mask_from_lines(S, loops, topo, diag, centro, inverter=False):
    """Área da peça a partir das linhas desenhadas, pela superfície: as linhas viram barreira e
    um corte mínimo no grafo dos triângulos separa o lado da peça do lado do corpo. Se a parte
    encosta no corpo também em outro ponto que a linha não pegou (o cabelo apoiado na gola),
    esse corte mínimo fecha a separação ali, pela menor borda.
    Devolve (máscara, comprimento da borda extra em mm, centro da borda extra) ou None."""
    from scipy.spatial import cKDTree
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import maximum_flow, breadth_first_order
    v, f, nb = topo
    T = v[f]
    n = len(f)
    cen = T.mean(1)
    area = np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1) / 2
    el = np.stack([np.linalg.norm(v[f[:, k]] - v[f[:, (k + 1) % 3]], axis=1) for k in range(3)], 1)
    me = float(np.median(el))
    dense, owner = [], []
    for i, L in enumerate(loops):
        Q = np.vstack([L, L[:1]])
        for a_, b_ in zip(Q[:-1], Q[1:]):
            k = max(1, int(np.ceil(np.linalg.norm(b_ - a_) / 0.25)))
            dense.append(a_ + (b_ - a_) * (np.arange(k)[:, None] / k))
            owner += [i] * k
    dense = np.vstack(dense)
    owner = np.array(owner)
    d, j = cKDTree(dense).query(cen)
    bw = max(0.3, 0.7 * me)
    barrier = d < bw
    zone = d < 3 * bw + 1.0
    near = zone & ~barrier
    # lado de cada triângulo perto da linha: esquerda ou direita do traço, sobre a superfície
    # (tangente da linha x normal do triângulo). Vale para linha em volta do pescoço e para
    # linha deitada no peito em volta de uma trança.
    starts = np.r_[0, np.cumsum(np.bincount(owner, minlength=len(loops)))]
    jj = j[zone]
    o_ = owner[jj]
    ln_ = starts[o_ + 1] - starts[o_]
    loc = jj - starts[o_]
    nxt = starts[o_] + (loc + 1) % ln_
    prv = starts[o_] + (loc - 1) % ln_
    tg = dense[nxt] - dense[prv]
    nrm = np.cross(T[zone, 1] - T[zone, 0], T[zone, 2] - T[zone, 0])
    side = np.zeros(n)
    side[zone] = np.einsum('ij,ij->i', cen[zone] - dense[jj], np.cross(tg, nrm))
    ok = ~barrier
    # vinco côncavo (onde uma parte encosta na outra: o braço entrando na manga, a franja na testa)
    # custa pouco para o corte mínimo: a borda extra segue o vinco e não atravessa a roupa
    fn = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    fn = fn / np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)
    rows, cols, cap = [], [], []
    for k in range(3):
        o = nb[:, k]
        e = ok & (o >= 0) & ok[np.maximum(o, 0)]
        ie, oe = np.where(e)[0], o[e]
        cosa = np.clip(np.einsum('ij,ij->i', fn[ie], fn[oe]), -1, 1)
        ang = np.degrees(np.arccos(cosa))
        concave = np.einsum('ij,ij->i', cen[oe] - cen[ie], fn[ie]) > 0
        if _VINCO:
            # vinco forte (Easy Mesh Cutting): quanto mais fechado o vinco côncavo, mais barato, já a partir de
            # poucos graus; o encontro do cabelo com a camiseta ou com a testa é sempre um vinco assim
            w = np.where(concave, 1.0 / (1.0 + np.radians(ang) / _VINCO_ETA), 1.0)
        else:
            w = np.where(concave, 1.0 - 0.9 * np.clip((ang - 25.0) / 45.0, 0, 1), 1.0)
        rows.append(ie)
        cols.append(oe)
        cap.append(np.maximum(1, np.round(el[e, k] * 100 * w)).astype(np.int32))
    rows, cols, cap = np.concatenate(rows), np.concatenate(cols), np.concatenate(cap)
    BIG = 1 << 26
    s_, t_ = n, n + 1
    # sementes só na superfície em que a linha está: uma face perto da linha mas virada para o outro
    # lado (o lado de dentro da manga, a 1 mm do braço) não decide o lado da peça
    seed = near.copy()
    if barrier.any() and near.any():
        bi = np.where(barrier)[0]
        _, kb = cKDTree(cen[bi]).query(cen[near])
        seed[np.where(near)[0]] = np.einsum('ij,ij->i', fn[near], fn[bi[kb]]) > 0.3
    L = [seed & (owner[j] == q) & (side > 0) for q in range(len(loops))]
    R = [seed & (owner[j] == q) & (side < 0) for q in range(len(loops))]
    nl = len(loops)
    combos = [tuple((c >> q) & 1 for q in range(nl)) for c in range(1 << max(0, nl - 1))] if nl <= 7 else [tuple([0] * nl)]
    best = None
    for cb in combos:
        src = np.zeros(n, bool)
        snk = np.zeros(n, bool)
        for q in range(nl):
            a_, b_ = (L[q], R[q]) if cb[q] == 0 else (R[q], L[q])
            src |= a_
            snk |= b_
        both = src & snk
        src &= ~both
        snk &= ~both
        if not src.any() or not snk.any():
            continue
        G = csr_matrix((np.r_[cap, np.full(int(src.sum()), BIG, np.int32), np.full(int(snk.sum()), BIG, np.int32)],
                        (np.r_[rows, np.full(int(src.sum()), s_), np.where(snk)[0]],
                         np.r_[cols, np.where(src)[0], np.full(int(snk.sum()), t_)])), shape=(n + 2, n + 2))
        res = maximum_flow(G, s_, t_, method='dinic')
        if best is None or res.flow_value < best[0]:
            best = (res.flow_value, G, res, cb)
    if best is None:
        return None
    _, G, res, cb = best
    sign = np.zeros(n)
    for q in range(nl):
        sel = zone & (owner[j] == q)
        sign[sel] = side[sel] if cb[q] == 0 else -side[sel]
    Rz = (G - res.flow).tocsr()
    Rz.data = (Rz.data > 0).astype(np.int8)
    Rz.eliminate_zeros()
    reach = breadth_first_order(Rz, s_, directed=True, return_predecessors=False)
    m = np.zeros(n + 2, bool)
    m[reach] = True
    m = m[:n] & ok
    m |= barrier & (sign > 0)
    # borda extra: arestas do corte longe das linhas
    xl, xc = 0.0, None
    far = d > 3 * bw + 1.0
    pts, lens = [], []
    for k in range(3):
        o = nb[:, k]
        e = m & (o >= 0) & ~m[np.maximum(o, 0)] & far & far[np.maximum(o, 0)]
        if e.any():
            pa, pb = v[f[e, k]], v[f[e, (k + 1) % 3]]
            pts.append((pa + pb) / 2)
            lens.append(np.linalg.norm(pb - pa, axis=1))
    if pts:
        P, Ls = np.vstack(pts), np.concatenate(lens)
        xl = float(Ls.sum())
        xc = (P * Ls[:, None]).sum(0) / max(xl, 1e-9)
    if area[m].sum() > 0.5 * area.sum():                 # a peça é, por padrão, o lado menor
        m = ~m & ~(barrier & (sign > 0)) | (barrier & (sign < 0))
    if not inverter:
        m = _refine_outlines(m, loops, T, cen, diag, centro, nb)
        m = _bridge_small(m, barrier, nb, cen, area)
    else:
        m = ~m
    return m, xl, xc


def _bridge_small(m, barrier, nb, cen, area, gap=1.2):
    """Linha que passou por cima de uma parte fina (o laço no fim da trança) separa a ponta na
    superfície: pedaços pequenos da peça a menos de gap mm do pedaço principal são religados pela
    faixa da linha entre eles, para a ponta não sair solta."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree
    idx = np.where(m)[0]
    if not len(idx):
        return m
    loc = np.full(len(m), -1)
    loc[idx] = np.arange(len(idx))
    r_, c_ = [], []
    for k in range(3):
        o = nb[idx, k]
        okk = (o >= 0) & m[np.maximum(o, 0)]
        r_.append(loc[idx[okk]])
        c_.append(loc[o[okk]])
    g = coo_matrix((np.ones(sum(len(x) for x in r_)), (np.concatenate(r_), np.concatenate(c_))), shape=(len(idx), len(idx)))
    nc, lab = connected_components(g, directed=False)
    if nc < 2:
        return m
    ar = np.bincount(lab, weights=area[idx])
    main = int(np.argmax(ar))
    tmain = cKDTree(cen[idx[lab == main]])
    bar = np.where(barrier & ~m)[0]
    if not len(bar):
        return m
    m = m.copy()
    dmain, _ = tmain.query(cen[bar])
    for k in range(nc):
        if k == main or ar[k] < 1.0 or ar[k] > 0.3 * ar[main]:
            continue
        tk = cKDTree(cen[idx[lab == k]])
        dk, _ = tk.query(cen[bar])
        if dk.min() > gap:
            continue
        add = bar[(dk <= gap) & (dmain <= gap)]
        if len(add):
            m[add] = True
    return m


def _n_comp(mask, nb):
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    idx = np.where(mask)[0]
    if not len(idx):
        return 0
    loc = np.full(len(mask), -1)
    loc[idx] = np.arange(len(idx))
    r_, c_ = [], []
    for k in range(3):
        o = nb[idx, k]
        okk = (o >= 0) & mask[np.maximum(o, 0)]
        r_.append(loc[idx[okk]])
        c_.append(loc[o[okk]])
    g = coo_matrix((np.ones(sum(len(x) for x in r_)), (np.concatenate(r_), np.concatenate(c_))), shape=(len(idx), len(idx)))
    nc, lab = connected_components(g, directed=False)
    ar = np.bincount(lab)
    return int((ar >= 20).sum())


def _loop_compact(ln):
    """4πA/P² do contorno (envoltória) da linha vista de frente: pescoço ≈ 0,96; contorno de uma
    trança deitada no peito ≈ 0,6."""
    cs = mf.CrossSection([ln.Q2.tolist()], mf.FillRule.NonZero)
    hull = cs.hull()
    if hull.is_empty():
        return 0.0
    hp = np.asarray(hull.to_polygons()[0], np.float64)
    per = float(np.linalg.norm(np.diff(np.vstack([hp, hp[:1]]), axis=0), axis=1).sum())
    return 4 * np.pi * hull.area() / max(per * per, 1e-9)


def _refine_outlines(m, loops, T, cen, diag, centro, nb, tol=0.45):
    """Linha que contorna uma parte deitada sobre o corpo (trança no peito), desenhada com folga:
    a superfície do corpo que ficou dentro da linha (o kimono em volta da trança) não é da peça.
    A linha está sobre o corpo, então a superfície lisa que passa por ela é o corpo por baixo; o que
    está colado nela (até tol mm) volta para o corpo e a peça fica só com o que sobe dela."""
    m = m.copy()
    TN = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    TN /= np.maximum(np.linalg.norm(TN, axis=1), 1e-12)[:, None]
    for L in loops:
        try:
            ln = Line(np.asarray(L, np.float64), 'curva', 0.2, diag, centro)
        except Exception:
            continue
        if _loop_compact(ln) >= SOQUETE_COMPACTO:
            continue                                   # volta em torno de uma parte (pescoço): nada a refinar
        loc = (cen - ln.c) @ ln.Fr
        box = (np.abs(loc[:, 0]) <= ln.R0 + 1) & (np.abs(loc[:, 1]) <= ln.R0 + 1)
        idx = np.where(box)[0]
        if not len(idx):
            continue
        big = mf.CrossSection([ln.Q2.tolist()], mf.FillRule.NonZero).offset(1.0, mf.JoinType.Round, 2.0, 16)
        ins = np.zeros(len(idx), bool)
        for pl in big.to_polygons():
            ins ^= _inside(np.asarray(pl, np.float64), loc[idx, :2])
        idx = idx[ins]
        if not len(idx):
            continue
        h = loc[idx, 2] - ln.hf(loc[idx, :2])
        pm = m[idx]
        if pm.sum() < 10:
            continue
        sgn = np.sign(np.median(h[pm])) or 1.0
        from scipy.spatial import cKDTree
        Lw = np.asarray(L, np.float64)
        trL = cKDTree(Lw)
        dl, _ = trL.query(cen[idx])
        # a base local (o kimono) é o plano que passa pelos pontos da linha mais perto de cada
        # triângulo (a linha está toda sobre o kimono, dos dois lados da trança). O que está colado
        # nesse plano e deitado como ele é kimono; o que sobe ou fica de pé (os gomos) é trança.
        hb, bn = _base_height(Lw, cen[idx], sgn * ln.nn)
        Ti = T[idx]
        tn = np.cross(Ti[:, 1] - Ti[:, 0], Ti[:, 2] - Ti[:, 0])
        tn /= np.maximum(np.linalg.norm(tn, axis=1), 1e-12)[:, None]
        lying = np.einsum('ni,ni->n', tn, bn) > np.cos(np.radians(35))
        for t_ in (tol, 0.6 * tol):
            flat = np.zeros(len(m), bool)
            flat[idx[pm & (sgn * h < t_) & (hb < t_) & lying]] = True
            # só a faixa lisa que encosta na linha (o kimono que a linha pegou com folga), andando
            # de triângulo em triângulo; o que sobe (a trança) para a busca
            seed = idx[pm & (sgn * h < t_) & (hb < t_) & lying & (dl < 1.5)]
            got = np.zeros(len(m), bool)
            got[seed] = True
            front = seed
            # anda só por superfície que continua lisa: no vinco entre o kimono e a trança a normal
            # vira de repente e a busca para (não come a lateral da trança)
            while len(front):
                nx = nb[front]
                ok = nx >= 0
                nxs = np.maximum(nx, 0)
                smooth = np.einsum('ni,nki->nk', TN[front], TN[nxs]) > np.cos(np.radians(28))
                ok &= smooth & flat[nxs] & ~got[nxs]
                nxt = np.unique(nxs[ok])
                got[nxt] = True
                front = nxt
            if not got.any():
                break
            m2 = m.copy()
            m2[got] = False
            if _n_comp(m2, nb) <= _n_comp(m, nb):        # não pode partir a peça (a trança fina no meio)
                m = m2
                break
    return m


def _voxelize(M, xs, ys, zs):
    """Quais pontos da grade estão dentro do sólido M (fatias em z). Cada fatia é preenchida por
    linhas (onde as bordas cruzam cada linha da grade), com a mesma regra par e ímpar de antes:
    rápido também em malhas de milhões de triângulos, cujas fatias têm milhares de vértices."""
    xs = np.asarray(xs, np.float64)
    ys = np.asarray(ys, np.float64)
    inside = np.zeros((len(xs), len(ys), len(zs)), bool)
    for k, z in enumerate(zs):
        cs = M.slice(float(z))
        if cs.is_empty():
            continue
        inside[:, :, k] = _fill_slice(cs.to_polygons(), xs, ys)
    return inside


def _fill_slice(polys, xs, ys):
    """Grade (len(xs), len(ys)): ponto dentro dos polígonos (par e ímpar, como points_in_poly)."""
    out = np.zeros((len(xs), len(ys)), bool)
    ed = []
    for pl in polys:
        pl = np.asarray(pl, np.float64)
        if len(pl) < 3:
            continue
        ed.append(np.column_stack([pl, np.roll(pl, -1, axis=0)]))
    if not ed:
        return out
    ed = np.concatenate(ed)
    x0, y0, x1, y1 = ed.T
    ymin, ymax = np.minimum(y0, y1), np.maximum(y0, y1)
    jlo = np.searchsorted(ys, ymin, 'left')       # linhas com ymin <= y < ymax
    jhi = np.searchsorted(ys, ymax, 'left')
    cnt = np.maximum(jhi - jlo, 0)
    if not cnt.sum():
        return out
    e = np.repeat(np.arange(len(ed)), cnt)
    j = np.repeat(jlo, cnt) + (np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt))
    y = ys[j]
    xi = x0[e] + (y - y0[e]) * (x1[e] - x0[e]) / (y1[e] - y0[e])
    order = np.lexsort((xi, j))
    j, xi = j[order], xi[order]
    starts = np.searchsorted(j, np.arange(len(ys)), 'left')
    ends = np.searchsorted(j, np.arange(len(ys)), 'right')
    for r in np.where(ends > starts)[0]:
        row = xi[starts[r]:ends[r]]
        right = len(row) - np.searchsorted(row, xs, 'right')     # cruzamentos à direita (x < xi)
        out[:, r] = (right % 2) == 1
    return out


SOQUETE_COMPACTO = 0.8        # 4πA/P² do contorno (envoltória) da linha vista de frente: pescoço ≈ 0,96; contorno de trança deitada ≈ 0,6


def _want_mask(S, loops, cut, mclean, topo_box, diag, centro, host, piece):
    """Que superfície a marcação (ou as linhas) manda para a peça, orientada pelo corte já feito."""
    try:
        if mclean is not None and mclean.any():
            return ~mclean if cut.get('inverter') else mclean
        if not loops:
            return None
        if topo_box[0] is None:
            topo_box[0] = SPL._topology(S)
        fm = mask_from_lines(S, loops, topo_box[0], diag, centro, bool(cut.get('inverter')))
        if fm is None or not fm[0].any():
            return None
        want = fm[0]
        from scipy.spatial import cKDTree
        cw = tri_array(S).mean(1)
        dlw, _ = cKDTree(np.concatenate(loops)).query(cw, distance_upper_bound=6.0)
        qw = np.where(np.isfinite(dlw))[0]
        qw = qw[_on_surface(cw[qw], tri_array(host), tol=0.05) >= 0]
        if not len(qw):
            return None
        onw = _on_surface(cw[qw], tri_array(piece), tol=0.05) >= 0
        if (want[qw] == onw).sum() < (want[qw] != onw).sum():
            want = ~want
        return want
    except Exception:
        traceback.print_exc()
        return None


def _flat_ring(piece, body, host, sel, axes, gap, wall, Pg, piece0):
    """Anel plano (opção do corte com soquete): a face da junta em volta do soquete, que segue a
    linha e ondula, vira um plano perpendicular ao eixo do encaixe nas duas peças. Assim o corpo
    pode apoiar na mesa por esse anel e a peça encosta reta nele. Só o anel entre a pele e o
    soquete muda: o soquete, o fundo e o resto das peças ficam como estavam. Na pele a divisa
    passa a ser a reta do plano (até a metade da ondulação da linha para cada lado).
    Devolve (piece, body, info) ou None se não der para fazer com segurança."""
    J = mf.JoinType.Round
    k = _CUR_K[0]
    out_off = 1.0 * k                                  # o anel passa um pouco da linha para pegar a pele
    infos = []
    P, B = piece, list(body)
    for _, ln, L in sel:
        ax, Fa, Qa = axes[id(ln)]
        c0 = ln.c
        s = 1.0 if float((np.asarray(E.centroid(piece0)) - c0) @ ax) >= 0 else -1.0
        a = ax * s                                     # aponta para o lado da peça
        R = _frame(a)
        Q = ((L - c0) @ R)
        tL = Q[:, 2]
        Q2 = _smooth_loop3(Q, 0.8)[:, :2]
        cs = mf.CrossSection([Q2.tolist()], mf.FillRule.NonZero)
        if cs.is_empty():
            continue
        dmax = 2.0 * float(np.sqrt(cs.area() / np.pi))
        spread = float(np.ptp(tL))
        if spread > 0.6 * dmax:                         # a linha sobe demais (contorno do rosto): plano não faz sentido
            infos.append(('longe', spread))
            continue
        tl = float(np.median(tL))
        t0, t1 = float(tL.min()) - 3.0 * k, float(tL.max()) + 3.0 * k
        Tw = _T(R, c0)

        def ring(o_out, o_in, z0, z1):
            co = cs.offset(o_out, J, 2.0, 32)
            ci = cs.offset(-o_in, J, 2.0, 32)
            rg = co - ci if not ci.is_empty() else co
            if rg.is_empty() or z1 <= z0:
                return None
            return E.X(mf.Manifold.extrude(rg, z1 - z0).translate([0.0, 0.0, z0]), Tw)

        A_lo = ring(out_off, wall, t0, tl + gap / 2)          # lado do corpo (abaixo do plano)
        A_hi = ring(out_off, wall, tl - gap / 2, t1)          # lado da peça
        Ab_lo = ring(out_off - gap, wall - gap, t0, tl - gap / 2)
        Ap_hi = ring(out_off, wall, tl + gap / 2, t1)
        if any(x is None for x in (A_lo, A_hi, Ab_lo, Ap_hi)):
            continue
        P = E.flat(E.flat(P - A_lo) + E.flat(host ^ Ap_hi))
        add_b = E.flat(E.flat(host ^ Ab_lo) - Pg)
        B = [E.flat(b - A_hi) for b in B]
        B = E.parts(E.flat(E.union([b for b in B if _vol(b) > 0.0] + [add_b])), 0.5)
        infos.append(('ok', spread / 2.0))
    if not any(x[0] == 'ok' for x in infos):
        return None
    return P, B, infos


_NAVALHA = __import__('os').environ.get('FLEXI_NAVALHA', '1') != '0'
# 1.47: a navalha sai só de perto da pele que iria para o lado errado (antes saía da linha inteira e a borda
# ficava toda na grade, 1 a 2 mm fora da linha: a faixa de pele lisa na borda da mecha)
_NAVALHA_LOCAL = __import__('os').environ.get('FLEXI_NAVALHA_LOCAL', '0') == '1'
# junta num plano na borda visível quando a linha passa por baixo da roupa (1.34.1): desligado na 1.34.2,
# porque o plano reto deixava pele visível na camiseta (a divisa da pintura não é reta)
_PLANO_COBERTO = __import__('os').environ.get('FLEXI_PLANO_COBERTO', '0') == '1'


def _ray_hits(O, D, T):
    """Distância até a primeira face da malha T (n,3,3) ao longo de cada raio (O + t D); inf se não bate."""
    v0, e1, e2 = T[:, 0], T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
    chunk = int(np.clip(1.5e6 // max(len(T), 1), 1, 64))         # memória limitada em malhas finas
    out = np.full(len(O), np.inf)
    for i in range(0, len(O), chunk):
        o, d = O[i:i + chunk, None, :], D[i:i + chunk, None, :]
        p = np.cross(d, e2[None])
        det = np.einsum('rtk,tk->rt', p, e1)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        tv = o - v0[None]
        u = np.einsum('rtk,rtk->rt', tv, p) * inv
        q = np.cross(tv, e1[None])
        v = np.einsum('rtk,rtk->rt', np.broadcast_to(d, q.shape), q) * inv
        t = np.einsum('rtk,tk->rt', q, e2) * inv
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-6)
        out[i:i + chunk] = np.where(hit, t, np.inf).min(1)
    return out


def _hidden_plane(L, ax, ST, depth):
    """A linha às vezes passa por baixo da roupa (do lado de fora do braço a ferramenta segue o vinco e
    entra debaixo da manga). Devolve a altura (no eixo do encaixe, que aponta para a peça) do ponto
    VISÍVEL da linha mais para dentro do corpo, e quanto ele fica abaixo do trecho coberto; ou None se
    a linha está toda à vista."""
    from scipy.spatial import cKDTree
    k = _CUR_K[0]
    L = np.asarray(L, np.float64)
    lb, hb = L.min(0) - 5.0, L.max(0) + 5.0
    c = ST.mean(1)
    near = np.where(np.all((c >= lb) & (c <= hb), 1))[0]
    if len(near) < 3 or len(L) < 40:
        return None
    Tc = ST[near]
    _, j = cKDTree(c[near]).query(L)
    Tn = Tc[j]
    nrm = np.cross(Tn[:, 1] - Tn[:, 0], Tn[:, 2] - Tn[:, 0])
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
    # coberta: a roupa passa logo por cima, a menos de 1,6 mm pela normal (raio contra a malha original)
    cov = _ray_hits(L + nrm * 0.05 * k, nrm, Tc) < 1.6 * k
    # normal ruidosa no vinco: um ponto solto no meio de um trecho coberto não conta (maioria em 19 pontos)
    w = 9
    ext = np.concatenate([cov[-w:], cov, cov[:w]]).astype(float)
    cov = np.convolve(ext, np.ones(2 * w + 1) / (2 * w + 1), 'same')[w:-w] > 0.5
    vis = ~cov
    t = L @ ax
    if _DBG:
        print('hidden_plane:', int(cov.sum()), 'de', len(L), 'pontos cobertos', flush=True)
    if vis.sum() < 0.2 * len(L) or cov.sum() < 3:
        return None
    tp = float(t[vis].min())
    dh = tp - float(t.min())
    if dh < 0.5 * k or dh > 3.0 * depth:
        return None
    return tp, dh


def _trim_hidden(piece, body, Pm, Pg, sel, axes, planes, gap, depth, jit=0.0):
    """Com a linha passando por baixo da roupa, a peça leva a pele escondida até lá e em volta do encaixe
    sobra uma aba subindo dentro da manga. A junta fecha no plano de _hidden_plane (de frente para o eixo
    do encaixe): o que a peça tem além do plano, fora do encaixe, volta para o corpo com a folga. Só sai
    material da peça (a roupa nunca vai para a peça). Devolve (peça, corpo, volume devolvido, dh) ou None."""
    k = _CUR_K[0]
    P, B = piece, list(body)
    tot, dmax = 0.0, 0.0
    for _, ln, L in sel:
        if id(ln) not in planes:
            continue
        ax, Fa, Qa = axes[id(ln)]
        tp, dh = planes[id(ln)]
        cs = mf.CrossSection([Qa.tolist()], mf.FillRule.NonZero)
        if cs.is_empty():
            continue
        co = cs.offset(3.0 * k, mf.JoinType.Round, 2.0, 32)
        zl = tp - float(ln.c @ ax) + jit                 # altura do plano no referencial (Fa, ln.c)
        z0 = zl - dh - depth - 12.0 * k
        Tw = _T(Fa, ln.c)
        dj = [0.7 * jit, 0.4 * jit, z0]                  # deslocamento mínimo se o plano tocar a malha numa aresta
        slab_p = E.X(mf.Manifold.extrude(co, zl - z0).translate(dj), Tw)
        slab_b = E.X(mf.Manifold.extrude(co, zl - gap - z0).translate(dj), Tw)
        aba = E.flat(E.flat(P ^ slab_b) - Pg)
        va = _vol(aba)
        if va < 0.3 * k ** 3:
            continue
        if va > 0.15 * _vol(P):
            return None
        P2 = E.flat(E.flat(P - slab_p) + E.flat(P ^ Pm))
        n1 = len(E.parts(P, 1.0 * k ** 3) or [P])
        pp = [q for q in (E.parts(P2, 0.01 * k ** 3) or [P2]) if _vol(q) >= 1.0 * k ** 3]
        if len(pp) > n1 or not pp:
            return None
        P2 = pp[0] if len(pp) == 1 else E.flat(E.union(pp))
        done = False
        for jb, bp in enumerate(B):
            u = E.flat(E.union([bp, aba]))
            if len(E.parts(u, 0.5) or [u]) <= len(E.parts(bp, 0.5) or [bp]):
                if (P2 ^ u).volume() > 0.01 * k ** 3:
                    return None
                B[jb] = u
                done = True
                break
        if not done:
            return None
        P = P2
        tot += va
        dmax = max(dmax, dh)
        if _DBG:
            print('trim_hidden: aba', round(va, 1), 'mm3 volta para o corpo; plano', round(dh, 1), 'mm abaixo do trecho coberto', flush=True)
    if tot <= 0:
        return None
    return P, B, tot, dmax


def _band(ln, lo_off, hi_off, margin=3.0):
    """Sólido entre a face do corte + lo_off e + hi_off (no referencial da linha), sobre a área da linha."""
    cs = mf.CrossSection([ln.Q2.tolist()], mf.FillRule.NonZero).offset(margin, mf.JoinType.Round, 2.0, 32)
    b = cs.bounds()
    ext = max(b[2] - b[0], b[3] - b[1])
    stp = float(np.clip(ext / 160.0, 0.08 * _CUR_K[0], 0.5))
    tx = np.arange(b[0] - stp, b[2] + 2 * stp, stp)
    ty = np.arange(b[1] - stp, b[3] + 2 * stp, stp)
    X, Y = np.meshgrid(tx, ty, indexing='ij')
    H = ln.hf(np.stack([X.ravel(), Y.ravel()], 1)).reshape(X.shape)
    box = _heightbox(tx, ty, H + (lo_off + hi_off) / 2.0, hi_off - lo_off)
    return E.X(box, _T(ln.Fr, ln.c))


def _socket_exact(sel, axes, info, depth, gap, wall_s, wall, sm_all, gw, step, lo, planes=None):
    """Encaixe e cavidade exatos (navalha): paredes retas (o contorno da linha recuado, extrudado no eixo
    do encaixe) e fundo exato (plano, ou acompanhando a face do corte). Onde a pele de fora do corpo
    passa perto (a raiz da perna), o encaixe é aparado ali para manter a parede mínima; no resto as
    faces ficam exatas. Devolve (encaixe, cavidade) ou None."""
    k = _CUR_K[0]
    allow_p = allow_g = None
    if np.any(gw < 0):
        # região permitida: a 'wall' mm ou mais da pele de fora (a grade só onde ela aperta)
        def mc(Fv):
            return _mc_manifold(np.pad(Fv.astype(np.float32), 1, constant_values=-10.0), step, lo, 4, 'parede do soquete')
        allow_p = mc(np.minimum(gw, 10.0))
        allow_g = mc(np.minimum(gw + gap, 10.0))
    plugs, cavs = [], []
    for _, ln, L in sel:
        ax, Fa, Qa = axes[id(ln)]
        zb, curva, spread = info[id(ln)]
        cs = mf.CrossSection([Qa.tolist()], mf.FillRule.NonZero)
        ci = cs.offset(-wall_s, mf.JoinType.Round, 2.0, 64)
        cg = cs.offset(-wall_s + gap, mf.JoinType.Round, 2.0, 64)
        if ci.is_empty() or ci.area() < 1.0 * k * k:
            return None
        ztop = zb + spread + depth + 6.0 * k
        pz0 = zb if not curva else zb - spread - 2.0 * k   # fundo curvo: quem corta é a faixa
        gz0 = pz0 - gap
        Tw = _T(Fa, ln.c)
        pr_p = E.X(mf.Manifold.extrude(ci, ztop - pz0).translate([0.0, 0.0, pz0]), Tw)
        pr_g = E.X(mf.Manifold.extrude(cg, ztop - gz0).translate([0.0, 0.0, gz0]), Tw)
        big = spread + depth + 10.0 * k
        pl = (planes or {}).get(id(ln))
        if pl is not None:
            # junta num plano (a linha passa por baixo da roupa): o encaixe sai reto do plano, fundo plano
            zl = pl[0] - float(ln.c @ ax)
            P = E.X(mf.Manifold.extrude(ci, zl + 0.6 - pz0).translate([0.0, 0.0, pz0]), Tw)
            G = E.X(mf.Manifold.extrude(cg, zl + 0.6 + gap - gz0).translate([0.0, 0.0, gz0]), Tw)
        else:
            if curva:
                bp, bg = _band(ln, -depth, 0.6), _band(ln, -depth - gap, 0.6 + gap)
            else:
                bp, bg = _band(ln, -big, 0.6), _band(ln, -big, 0.6 + gap)
            P = E.flat(pr_p ^ bp)
            G = E.flat(pr_g ^ bg)
        if allow_p is not None:
            P = E.flat(P ^ allow_p)
            G = E.flat(G ^ allow_g)
        if P.is_empty() or G.is_empty():
            return None
        plugs.append(P)
        cavs.append(G)
    return (E.flat(E.union(plugs)) if len(plugs) > 1 else plugs[0],
            E.flat(E.union(cavs)) if len(cavs) > 1 else cavs[0])


# encaixe padrão (como numa peça feita à mão): pino com um lado plano no centro da seção, no eixo da
# parte, e furo com folga no corpo. FLEXI_SOQUETE_SECAO=1 volta ao encaixe que ocupava a seção inteira.
_PINO_PADRAO = _os.environ.get('FLEXI_SOQUETE_SECAO', '0') != '1'
_PLANO_AUTO = _os.environ.get('FLEXI_PLANO_AUTO', '1') != '0'
_CASCA = _os.environ.get('FLEXI_CASCA', '1') != '0'
_PLANO_MISTO = _os.environ.get('FLEXI_PLANO_MISTO', '1') != '0'      # 1.45: linha plana + contato que segue o vinco
_PLANO_TOL = _os.environ.get('FLEXI_PLANO_TOL', '0') == '1'      # em teste: a conferência aceita a borda no plano automático
_CONF_PELE = _os.environ.get('FLEXI_CONF_PELE', '1') != '0'      # 1.45: a conferência só conta a pele do modelo
_MODEL_T = [None]
_PINO_FACE = _os.environ.get('FLEXI_PINO_FACE', '1') != '0'      # 1.45: pino perpendicular à face plana
_PLANO_BORDA = _os.environ.get('FLEXI_PLANO_BORDA', '1') != '0'      # 1.45: plano no miolo e borda que segue a linha
_CASCA_EIXO = _os.environ.get('FLEXI_CASCA_EIXO', '0') == '1'      # em teste: junta escondida também no eixo da linha
_PLANO_PECA = _os.environ.get('FLEXI_PLANO_PECA', '1') != '0'      # 1.45: plano automático também num corte numa peça
_LAMINA_TODA = _os.environ.get('FLEXI_LAMINA_TODA', '0') == '1'      # experimental: desligado


def _peg_profile(rp, n=48):
    """Pino visto de frente: círculo de raio rp com um lado plano (a 0,6 rp do centro) que trava o giro."""
    c = mf.CrossSection.circle(rp, n)
    return c ^ mf.CrossSection.square([4 * rp, 4 * rp], True).translate([-2 * rp + 0.6 * rp, 0.0])


def _part_axis(host, c, ax0, L):
    """Eixo da parte alongada no ponto c (pescoço, perna, rabo, alça): a direção, até 35 graus da
    linha, em que a seção da parte em c é a menor. Uma linha desenhada torta não entorta o pino.
    De pé na mesa (vertical) quando fica a menos de 20 graus dela."""
    ax0 = np.asarray(ax0, np.float64) / max(np.linalg.norm(ax0), 1e-12)
    Lc = np.asarray(L, np.float64) - c
    R0 = float(np.median(np.linalg.norm(Lc - np.outer(Lc @ ax0, ax0), axis=1)))

    def area(d):
        Fd = _frame(d)
        cs = E.X(host, _inv(SPL._T(Fd, c))).slice(0.0)
        if cs.is_empty():
            return np.inf
        disc = mf.CrossSection.circle(2.0 * R0 + 1.0, 32)          # só a parte em volta da linha
        cs = cs ^ disc
        parts = [q for q in cs.decompose() if q.area() > 0]
        if not parts:
            return np.inf
        # a componente que contém o centro (a parte cortada), não uma vizinha que entrou no disco
        own = [q for q in parts if _inside(np.asarray(q.to_polygons()[0], np.float64), np.zeros((1, 2)))[0]]
        return min(q.area() for q in (own or parts))
    best, ab = ax0, area(ax0)
    if not np.isfinite(ab):
        return ax0
    F0 = _frame(ax0)
    for t in (12, 24, 35):
        for k in range(8):
            ph = 2 * np.pi * k / 8
            d = np.cos(np.radians(t)) * ax0 + np.sin(np.radians(t)) * (np.cos(ph) * F0[:, 0] + np.sin(ph) * F0[:, 1])
            a = area(d)
            if a < ab * 0.995:
                best, ab = d, a
    # refina em volta da melhor direção
    for t in (6, 3):
        Fb = _frame(best)
        for k in range(8):
            ph = 2 * np.pi * k / 8
            d = np.cos(np.radians(t)) * best + np.sin(np.radians(t)) * (np.cos(ph) * Fb[:, 0] + np.sin(ph) * Fb[:, 1])
            a = area(d)
            if a < ab * 0.995:
                best, ab = d / np.linalg.norm(d), a
    if float(best @ ax0) < 0:
        best = -best
    if abs(best[2]) >= np.cos(np.radians(20)):
        best = np.array([0.0, 0.0, np.sign(best[2])])
    return best


def _peg_socket(r, host, sel, axes, depth, gap, clr, wall, invert=None):
    """Pino padrão em cada linha selecionada: (r novo, avisos) ou None se não couber em nenhuma.
    O pino sai da face do corte da peça, no eixo da parte (de pé na mesa quando o eixo está a menos de
    20 graus da vertical), no centro da seção; o corpo recebe o furo com a folga do pino. Seção fina:
    sem pino naquela linha (fica a face do corte).
    invert (mm): o pino é do corpo (a parte do meio entre dois cortes próximos), ancorado 'invert' mm abaixo
    da face, e entra 'depth' mm na peça, que recebe o furo."""
    K = _CUR_K[0]
    piece, body_parts = r['piece'], list(r['body_parts'])
    adds, subs, infos, falhas = [], [], [], []
    for _, ln, L in sel:
        a0 = np.asarray(axes[id(ln)][0], np.float64)
        ax = _part_axis(host, ln.c, a0, L)
        if _PINO_FACE and (r.get('_plano_auto') or r.get('_plano_linha')):
            # face plana (ou plana no miolo): entre o eixo da parte e a perpendicular da face, o pino fica no
            # que está mais perto da vertical (até 25 graus): a peça apoia de pé na outra, como o pescoço que
            # sustenta a cabeça. Longe da vertical (braço, perna deitada) vale o eixo da parte
            fn = ln.nn * (1.0 if float(np.dot(ln.nn, ax)) >= 0 else -1.0)
            vz = lambda v: float(np.degrees(np.arccos(min(1.0, abs(float(v[2])) / max(np.linalg.norm(v), 1e-12)))))
            if vz(fn) <= 25.0 and vz(fn) < vz(ax):
                ax = fn
        Fa = _frame(ax)
        Tw = SPL._T(Fa, ln.c)
        Ti = _inv(Tw)
        hl = E.X(host, Ti)
        # face do corte em volta do pino: a altura dela no eixo
        gx = np.linspace(ln.Q2[:, 0].min(), ln.Q2[:, 0].max(), 25)
        gy = np.linspace(ln.Q2[:, 1].min(), ln.Q2[:, 1].max(), 25)
        gq = np.stack(np.meshgrid(gx, gy, indexing='ij'), -1).reshape(-1, 2)
        gq = np.vstack([gq[_inside(ln.Q2, gq)], ln.Q2])
        Wb = ln.c + np.column_stack([gq, ln.hf(gq)]) @ ln.Fr.T
        zf = (Wb - ln.c) @ ax
        zmin, zmax = float(zf.min()) - gap / 2, float(zf.max()) + gap / 2
        Qa = ((np.asarray(L, np.float64) - ln.c) @ Fa)[:, :2]
        try:
            lim = mf.CrossSection([Qa.tolist()], mf.FillRule.NonZero).offset(1.0 * K, mf.JoinType.Round, 2.0, 32)
        except Exception:
            lim = None
        # seção do corpo da face até o fundo do furo (mais a parede): o pino cabe em todas
        sec = None
        zs_ = np.linspace(zmin - 0.2 * K, zmin - depth - wall, 6) if invert is None else np.linspace(zmax + 0.2 * K, zmax + depth + wall, 6)
        for z in zs_:
            cz = hl.slice(float(z))
            if lim is not None:
                cz = cz ^ lim
            sec = cz if sec is None else (sec ^ cz)
            if sec.is_empty():
                break
        if sec is None or sec.is_empty():
            falhas.append('_vazia')
            continue
        sec = max(sec.decompose(), key=lambda q: q.area())
        inr = float(_inradius(sec)[0])
        if inr > 12.0 * K:
            falhas.append('_larga')                    # seção larga (cintura, tronco): fica o encaixe pela seção
            continue
        avail = sec.offset(-(wall + clr), mf.JoinType.Round, 2.0, 32)
        if avail.is_empty():
            falhas.append('_fina')
            continue
        rmax, ctr = _inradius(avail)
        rpin = min(float(rmax), 0.5 * inr)
        if rpin < 0.9 * K:
            falhas.append('_fina')
            continue
        prof = _peg_profile(rpin)
        # pino: da face até 'depth' para dentro do corpo, ponta com chanfro de 0,4 mm
        ch = min(0.4 * K, 0.3 * rpin)
        if invert is None:
            z_tip = zmin - depth
            top = zmax + min(1.5 * K, 0.5 * depth)
            peg = mf.Manifold.extrude(prof, top - (z_tip + ch)).translate([0, 0, z_tip + ch])
            tip = mf.Manifold.extrude(prof.scale([(rpin - ch) / rpin] * 2), ch, 0, 0.0, [rpin / (rpin - ch)] * 2).translate([0, 0, z_tip])
            bore = mf.Manifold.extrude(prof.offset(clr, mf.JoinType.Round, 2.0, 32), top + gap - (z_tip - clr)).translate([0, 0, z_tip - clr])
        else:
            # pino do corpo para cima: base 'invert' abaixo da face, ponta 'depth' acima dela
            z_base, z_tip = zmin - float(invert), zmax + depth
            peg = mf.Manifold.extrude(prof, (z_tip - ch) - z_base).translate([0, 0, z_base])
            tip = mf.Manifold.extrude(prof, ch, 0, 0.0, [(rpin - ch) / rpin] * 2).translate([0, 0, z_tip - ch])
            bore = mf.Manifold.extrude(prof.offset(clr, mf.JoinType.Round, 2.0, 32), (z_tip + clr) - (zmin - gap)).translate([0, 0, zmin - gap])
        peg = (peg + tip).translate([float(ctr[0]), float(ctr[1]), 0.0])
        bore = bore.translate([float(ctr[0]), float(ctr[1]), 0.0])
        adds.append(E.X(peg, Tw))
        subs.append(E.X(bore, Tw))
        infos.append((2 * rpin, depth))
    if not adds or '_larga' in falhas:
        return None
    P_add, P_sub = E.union(adds), E.union(subs)
    if invert is None:
        piece2 = E.flat(piece + E.flat(P_add ^ host))     # o pino só existe dentro do modelo
        if len(E.parts(piece2, 0.3)) > len(E.parts(piece, 0.3)):
            return None
        body2 = []
        for bp in body_parts:
            body2 += E.parts(E.flat(bp - P_sub), 0.5)
        body2 = sorted([b for b in body2 if _vol(b) >= 1.0], key=lambda q: -_vol(q))
        if len(body2) > len(body_parts):
            return None                                   # o furo partiu o corpo: sem pino
        # o furo não pode abrir na pele de fora: o volume tirado do corpo é o do furo abaixo da face
        if sum(_vol(b) for b in body_parts) - sum(_vol(b) for b in body2) <= 0:
            return None
    else:
        p_in = E.flat(P_add ^ host)
        # o pino vai para a parte do corpo onde ele está ancorado (a do meio)
        k_ = max(range(len(body_parts)), key=lambda k: _vol(body_parts[k] ^ p_in))
        if _vol(body_parts[k_] ^ p_in) <= 0:
            return None
        body2 = list(body_parts)
        body2[k_] = E.flat(body2[k_] + p_in)
        piece2 = E.flat(piece - P_sub)
        if len(E.parts(piece2, 0.5)) > len(E.parts(piece, 0.5)) or _vol(piece) - _vol(piece2) <= 0:
            return None
    notas = []
    d_txt = ', '.join(f'{_fmt(d, 1)} mm' for d, _ in infos)
    onde = 'no corpo' if invert is None else 'na peça (o pino é da parte do meio)'
    notas.append(_chk('ok', f'Soquete: pino padrão de {d_txt} de diâmetro no centro da seção, entra {_fmt(infos[0][1], 1)} mm {onde}, '
                            f'com folga de {_fmt(clr, 2)} mm. O lado plano do pino trava o giro; a peça fica alinhada ao eixo da parte.'))
    if falhas.count('_fina'):
        notas.append(_chk('aviso', f'{falhas.count("_fina")} linha(s) passam numa parte fina demais para pino: ali a peça fica só com a face do corte (cole).'))
    return dict(r, piece=piece2, body_parts=body2), notas


def socket_cut(r, host, loops, cut, diag, centro, enc, S=None, want=None):
    """"Peça entra no corpo": a peça cresce para dentro do corpo, abaixo de onde ela já está, até a
    profundidade escolhida, e o corpo fica com a cavidade (soquete). Assim a pele dentro da linha vai
    toda com a peça (não sobra pescoço na gola).
    Regras para não estragar o corpo:
      - só nas linhas que dão a volta numa parte (pescoço, pulso); uma linha que contorna uma parte
        deitada sobre o corpo (trança no peito) não ganha soquete, senão cavaria o peito;
      - o soquete fica dentro da linha e a pelo menos uma parede de distância da superfície de fora
        do corpo (a gola, as costas): ele nunca abre buraco no corpo."""
    from scipy.ndimage import distance_transform_edt, gaussian_filter, binary_dilation
    from skimage.measure import marching_cubes
    depth = float(np.clip(float(cut.get('soquete_mm') or 4.0), 1.0, 30.0))
    gap = float(np.clip(float(cut.get('folga') or 0.2), 0.05, 2.0))
    clr = float(np.clip(float(cut.get('folga_pino') or 0.4), 0.05, 1.0))
    wall = float(cut.get("parede", 1.2))
    # com anel plano a parede do soquete na boca é mais grossa (2 mm reais): é ela que vira o anel
    # de apoio; a parede por fora do corpo e o teste de parte fina continuam com 'wall'
    wall_s = max(wall, 2.0 * _CUR_K[0]) if cut.get('anel_plano') else wall
    piece, body_parts = r['piece'], list(r['body_parts'])
    sel, skipped, thin = [], 0, 0
    for L in loops:
        L = np.asarray(L, np.float64)
        try:
            ln = Line(L, 'plano', gap, diag, centro)
        except Exception:
            continue
        cs = mf.CrossSection([ln.Q2.tolist()], mf.FillRule.NonZero)
        if cs.is_empty() or cs.area() < 0.5:
            continue
        hull = cs.hull()                                  # contorno sem os dentes da linha
        hp = np.asarray(hull.to_polygons()[0], np.float64) if not hull.is_empty() else ln.Q2
        per = float(np.linalg.norm(np.diff(np.vstack([hp, hp[:1]]), axis=0), axis=1).sum())
        if 4 * np.pi * hull.area() / max(per * per, 1e-9) < SOQUETE_COMPACTO:
            skipped += 1
            continue
        pp = _who([piece], ln.probes(+1))[0]
        pm = _who([piece], ln.probes(-1))[0]
        if pm > pp:
            ln.flip()
        try:
            inr = float(_inradius(cs)[0])
        except Exception:
            inr = 99.0
        if inr < wall + 0.8 * _CUR_K[0]:              # parte fina (pulso achatado): o soquete viraria uma lâmina
            thin += 1
            continue
        try:                                          # a face do corte é a superfície lisa pela linha (a lâmina)
            lc = Line(L, 'curva', gap, diag, centro)
            if float(np.dot(lc.nn, ln.nn)) < 0:
                lc.flip()
            ln = lc
        except Exception:
            pass
        sel.append((cs.area(), ln, L))
    notes = []
    if skipped:
        notes.append(_chk('ok', f'{skipped} linha(s) contornam uma parte deitada sobre o corpo (uma trança no peito): ali não há '
                                'soquete, para não cavar o corpo.'))
    # eixo do encaixe: na vertical da mesa quando a linha não está muito inclinada. Assim o soquete, o
    # pino e o fundo da peça ficam de pé na impressão (sem pino deitado nem parede pendurada).
    axes = {}
    Zup = np.array([0.0, 0.0, 1.0])
    sel2 = []
    for item in sel:
        _, ln, L = item
        cz = float(ln.nn @ Zup)
        ax = Zup * np.sign(cz) if abs(cz) >= np.cos(np.radians(50)) else ln.nn      # (o pino padrão acha o próprio eixo)
        if ax is not ln.nn:
            gx = np.linspace(ln.Q2[:, 0].min(), ln.Q2[:, 0].max(), 15)
            gy = np.linspace(ln.Q2[:, 1].min(), ln.Q2[:, 1].max(), 15)
            gq = np.stack(np.meshgrid(gx, gy, indexing='ij'), -1).reshape(-1, 2)
            gq = np.vstack([gq[_inside(ln.Q2, gq)], ln.Q2])
            Wb = ln.c + np.column_stack([gq, ln.hf(gq)]) @ ln.Fr.T
            if float(np.ptp(Wb @ Zup)) > 3 * depth:      # a face do corte sobe muito (o contorno do rosto): eixo da linha
                ax = ln.nn
        Fa = _frame(ax)
        Qa = _smooth_loop3((L - ln.c) @ Fa, 0.8)[:, :2]
        try:
            inr_a = float(_inradius(mf.CrossSection([Qa.tolist()], mf.FillRule.NonZero))[0])
        except Exception:
            inr_a = 99.0
        if inr_a < wall + 0.8 * _CUR_K[0]:
            thin += 1
            continue
        axes[id(ln)] = (ax, Fa, Qa)
        sel2.append(item)
    sel = sel2
    # outra linha de corte logo abaixo, dentro do soquete (o pescoço curto entre a cabeça e o corpo): o
    # soquete fica raso o bastante para sobrar um fundo de uma parede; se nem um soquete raso couber,
    # aquela peça fica só com a face do corte
    outras = cut.get("_outras") or []
    if outras and sel:
        Po = np.vstack(outras)
        room = np.inf
        for _, ln, L in sel:
            ax, Fa, Qa = axes[id(ln)]
            loc = (Po - ln.c) @ Fa
            dn = -loc[:, 2]                            # quanto o ponto está para dentro do corpo
            # a menos de 1,8 mm não há peça do meio que dure (lasca): vale o encaixe normal, como na 1.42
            near = (dn > 1.8 * _CUR_K[0]) & (dn < depth + wall + gap + 2.0 * _CUR_K[0])
            if near.any():
                # a outra linha também dá a volta na parte: os pontos dela ficam no contorno, não dentro
                try:
                    Qd = mf.CrossSection([Qa.tolist()], mf.FillRule.NonZero).offset(wall + 1.0 * _CUR_K[0], mf.JoinType.Round, 2.0, 32)
                    Qd = max((np.asarray(q_, np.float64) for q_ in Qd.to_polygons()), key=lambda q_: abs(SPL._poly_area(q_)))
                except Exception:
                    Qd = Qa
                ins = _inside(Qd, loc[near, :2])
                if ins.any():
                    room = min(room, float(dn[near][ins].min()))
        if np.isfinite(room) and room - depth < wall + gap:
            d2 = room - wall - gap
            if d2 < 1.0 * _CUR_K[0]:
                if _PINO_PADRAO and enc == 'colar' and room >= 1.8 * _CUR_K[0]:     # parte do meio com corpo para ancorar o pino
                    # a peça do meio é fina: o pino sai dela para dentro da peça (o furo fica na peça), e a peça do
                    # meio continua maciça
                    try:
                        rp = _peg_socket(r, host, sel, axes, depth, gap, clr, wall, invert=min(1.5 * _CUR_K[0], room - 0.5 * _CUR_K[0]))
                    except Exception:
                        traceback.print_exc()
                        rp = None
                    if rp is not None:
                        return rp[0], notes + [_chk('ok', f'A linha de outro corte passa a {_fmt(room, 1)} mm, logo abaixo: o pino saiu da '
                                                          'parte do meio para dentro da peça, e a parte do meio ficou maciça.')] + rp[1]
                notes.append(_chk('aviso', f'A linha de outro corte passa a {_fmt(room, 1)} mm, logo abaixo: não cabe soquete sem deixar a '
                                           'peça do meio oca. Ali a peça fica só com a face do corte (cole); para ter soquete, afaste as linhas.'))
                return r, notes
            notes.append(_chk('aviso', f'A linha de outro corte passa a {_fmt(room, 1)} mm, logo abaixo: o soquete ficou com {_fmt(d2, 1)} mm '
                                       f'(em vez de {_fmt(depth, 1)}) para a peça do meio não sair oca (fundo de {_fmt(wall, 1)} mm).'))
            depth = d2
    if thin:
        notes.append(_chk('aviso', f'{thin} linha(s) passam numa parte fina demais para soquete (menos de '
                                   f'{_fmt(2 * (wall + 0.8 * _CUR_K[0]))} mm de largura): ali a peça fica só com a face do corte, sem entrar no corpo.'))
    if not sel:
        return r, notes
    if _PINO_PADRAO and enc == 'colar':
        # encaixe de colar: o pino padrão é o encaixe. Trava e pino próprios continuam com o soquete pela seção
        try:
            rp = _peg_socket(r, host, sel, axes, depth, gap, clr, wall)
        except Exception:
            traceback.print_exc()
            rp = None
        if rp is not None:
            return rp[0], notes + rp[1]
        # o pino padrão não coube: fica o encaixe pela seção (como antes)
    P = np.vstack([x[2] for x in sel])
    hb = host.bounding_box()
    lo = np.maximum(P.min(0) - depth - 4.0, np.array(hb[:3]) - 1.0)
    hi = np.minimum(P.max(0) + depth + 4.0, np.array(hb[3:]) + 1.0)
    ext = hi - lo
    step = float(np.clip(ext.max() / 120.0, 0.2 * min(1.0, _CUR_K[0] / 0.6), 0.5))   # modelo ampliado: grade mais fina (malha lisa no tamanho real)
    step = max(step, float((np.prod(ext) / 2.5e6) ** (1 / 3)))
    xs, ys, zs = [lo[k] + step * np.arange(int(np.ceil(ext[k] / step)) + 1) for k in range(3)]
    n = (len(xs), len(ys), len(zs))
    from scipy.spatial import cKDTree
    trees = []
    for _, ln, L in sel:
        Lloc = (L - ln.c) @ ln.Fr
        trees.append((ln, cKDTree(Lloc[:, :2]), Lloc[:, 2]))

    def above_line(X):
        """Pontos dentro da linha (vista de frente) e acima da costura: a parte da peça que o corte deixou no corpo."""
        out = np.zeros(len(X), bool)
        for ln, tr, zl in trees:
            loc = (X - ln.c) @ ln.Fr
            ins = _inside(ln.Q2, loc[:, :2])
            if ins.any():
                _, k = tr.query(loc[ins, :2])
                sub = np.where(ins)[0]
                out[sub[loc[ins, 2] >= zl[k] - 0.3]] = True
        return out
    ins_host = _voxelize(host, xs, ys, zs)
    # superfície de fora do corpo: triângulos das partes do corpo que estão na superfície original
    ST = tri_array(S) if S is not None else tri_array(host)
    occ = np.zeros(n, bool)
    sm_all = []
    for bp in body_parts:
        BT = tri_array(bp)
        c = BT.mean(1)
        box = np.all((c >= lo - 1) & (c <= hi + 1), axis=1)
        if not box.any():
            continue
        BT, c = BT[box], c[box]
        on = _on_surface(c, ST, tol=0.05) >= 0
        sm = np.concatenate([c[on]] + [BT[on, k] * 0.6 + c[on] * 0.4 for k in range(3)])
        if len(sm) > 300000:
            # malha fina (sem perda de qualidade): milhões de pontos de pele; um por célula de um
            # terço da grade basta para medir a parede e deixa a conta rápida
            _, ui = np.unique(np.floor((sm - lo) / (step / 3.0)).astype(np.int64), axis=0, return_index=True)
            sm = sm[np.sort(ui)]
        if want is not None:
            # a pele que a linha manda para a peça não conta como parede do corpo; o resto (a barra da
            # calça logo acima da linha, por exemplo) conta, e o soquete nunca a fura
            from scipy.spatial import cKDTree
            STc = ST.mean(1)
            near_i = np.where(np.all((STc >= lo - 2) & (STc <= hi + 2), 1))[0]
            if len(near_i):
                _, nk = cKDTree(STc[near_i]).query(sm)
                sm = sm[~np.asarray(want, bool)[near_i[nk]]]
        else:
            sm = sm[~above_line(sm)]      # a pele dentro da linha é da peça: não conta como parede do corpo
        sm_all.append(sm)
        ijk = np.round((sm - lo) / step).astype(int)
        ok = np.all((ijk >= 0) & (ijk < np.array(n)), axis=1)
        occ[tuple(ijk[ok].T)] = True
    # Soquete por distâncias exatas (não por voxels): paredes retas ao longo da linha, fundo paralelo
    # à face do corte e folga exata. Fica 'wall' mm para dentro da linha e longe da superfície de fora.
    sd_host = distance_transform_edt(ins_host, sampling=step) - distance_transform_edt(~ins_host, sampling=step)
    sd_host = gaussian_filter(np.clip(sd_host, -20, 20), 1.0)
    G = np.stack(np.meshgrid(xs, ys, zs, indexing='ij'), -1)
    Gf = G.reshape(-1, 3)
    F = np.full(len(Gf), -10.0)
    curved = [0]
    sock_info = {}
    # linha que passa por baixo da roupa: a junta fecha num plano na borda visível e o encaixe sai reto
    # desse plano, com fundo plano (navalha)
    planes = {}
    if _PLANO_COBERTO and _NAVALHA and r.get('_refeito_vol'):   # experimental (desligado): mexia na divisa da cor
        for _, ln, L in sel:
            try:
                hp = _hidden_plane(L, axes[id(ln)][0], ST, depth)
            except Exception:
                traceback.print_exc()
                hp = None
            if hp is not None:
                planes[id(ln)] = hp
    for _, ln, L in sel:
        ax, Fa, Qa = axes[id(ln)]
        loc = (Gf - ln.c) @ ln.Fr
        h = loc[:, 2] - ln.hf(loc[:, :2])
        la = (Gf - ln.c) @ Fa                          # no eixo do encaixe (de pé na mesa, se der)
        # fundo plano (perpendicular ao eixo), a 'depth' mm do ponto mais fundo da face do corte
        gx = np.linspace(ln.Q2[:, 0].min(), ln.Q2[:, 0].max(), 25)
        gy = np.linspace(ln.Q2[:, 1].min(), ln.Q2[:, 1].max(), 25)
        gq = np.stack(np.meshgrid(gx, gy, indexing='ij'), -1).reshape(-1, 2)
        gq = np.vstack([gq[_inside(ln.Q2, gq)], ln.Q2])
        Wb = ln.c + np.column_stack([gq, ln.hf(gq)]) @ ln.Fr.T
        zb = float(((Wb - ln.c) @ ax).min()) - depth
        pl = planes.get(id(ln))
        if pl is not None:
            zl = pl[0] - float(ln.c @ ax)              # plano da junta (no referencial Fa, ln.c)
            zb = zl - depth
            h = la[:, 2] - zl                          # o plano faz o papel da face do corte
        Ra = float(np.linalg.norm(Qa, axis=1).max())
        near = (la[:, 2] >= zb - gap - 4 * step) & (h <= 0.6 + gap + 4 * step) & \
               (np.abs(la[:, 0]) <= Ra + 2) & (np.abs(la[:, 1]) <= Ra + 2)
        sd = np.full(len(Gf), -10.0)
        sd[near] = _poly_sd(Qa, la[near, :2])
        spread = float(np.ptp((Wb - ln.c) @ ax)) if pl is None else 0.0
        sock_info[id(ln)] = (zb, spread > depth + 1.0 * _CUR_K[0], spread)
        if pl is not None:
            bot = la[:, 2] - zb                        # sai reto do plano da junta, fundo plano
        elif spread <= depth + 1.0 * _CUR_K[0]:
            bot = la[:, 2] - zb                        # face quase plana: fundo plano, de pé na mesa
        else:
            # face do corte inclinada ou curva (a linha do cabelo desce da testa até a nuca): com fundo
            # plano o encaixe virava uma cunha da altura da linha inteira e deixava o corpo oco. O
            # fundo acompanha a face, sempre 'depth' mm abaixo dela.
            bot = h + depth
            curved[0] += 1
        Fk = _smin(_smin(sd - wall_s, bot, 0.5), 0.6 - h, 0.3)   # cantos do fundo arredondados (0,5 mm)
        F = np.maximum(F, np.where(near, Fk, -10.0))
    F = F.reshape(n)
    # parede até a superfície de fora: distância exata aos pontos da superfície (não pelos voxels)
    gw = np.full(n, 10.0)
    sm_all = np.concatenate(sm_all) if sm_all else np.zeros((0, 3))
    if len(sm_all):
        from scipy.spatial import cKDTree
        cnd = np.where(F > -(wall + 1.5))
        dq, _ = cKDTree(sm_all).query(G[cnd], distance_upper_bound=wall + 6.0)
        gw[cnd] = np.where(np.isfinite(dq), dq, wall + 6.0) - wall
    F = _smin(F, _smin(gw, sd_host - 0.3, 0.5), 0.5)
    plug = F > 0
    if plug.sum() < 8:
        return r, notes + [_chk('aviso', 'Não coube soquete aqui (o corpo em volta é fino demais): a peça ficou com a face do corte normal.')]

    def solid(Fv):
        Fp = np.pad(Fv.astype(np.float32), 1, constant_values=-10.0)
        return _mc_manifold(Fp, step, lo, 4, 'malha do soquete')
    # soquete "navalha": paredes retas e fundo exatos (contorno da linha recuado, extrudado no eixo do
    # encaixe, cortado pela face do corte), sem a grade de voxels. A grade continua só para conferir a
    # parede até a pele de fora; se a forma exata não couber, fica a forma pela grade (como antes).
    exact = None
    if _NAVALHA:
        try:
            exact = _socket_exact(sel, axes, sock_info, depth, gap, wall_s, wall, sm_all, gw, step, lo, planes)
        except Exception:
            traceback.print_exc()
            exact = None
    n_before = len(body_parts)

    def assemble(Pm, Pg):
        piece2 = E.flat(piece + E.flat(host ^ Pm))
        if len(E.parts(piece2, 0.3)) > max(1, len(E.parts(piece, 0.3))):
            return None                              # o soquete não encosta na peça
        body2 = []
        for bp in body_parts:
            body2 += E.parts(E.flat(bp - Pg), 0.5)
        body2 = sorted([b for b in body2 if _vol(b) >= 1.0], key=lambda q: -_vol(q))
        # lascas que o soquete soltou do corpo junto da costura (entre a linha e o corte) vão com a peça
        big_v = _vol(body2[0]) if body2 else 0.0
        small = [b for b in body2[1:] if _vol(b) < max(30.0, 0.02 * _vol(piece2)) and _vol(b) < 0.05 * big_v] if len(body2) > n_before else []
        if small:
            piece2 = E.flat(E.union([piece2] + small))
            body2 = [b for b in body2 if not any(b is q for q in small)]
        return piece2, body2, Pg, Pm

    def defeitos(res):
        # arestas com 3 ou mais faces como o fatiador vê o arquivo (paredes exatas que tocam a pele numa aresta)
        n_ = 0
        for m_ in [res[0]] + list(res[1]):
            T_ = SPL.tri_array(m_)
            if any(SPL.mesh_errors(T_)):
                n_ += sum(v for k_, v in SPL._weld_safe(T_)[2].items() if k_ != 'ok')
        return n_

    res = None
    if exact is not None:
        try:
            res = assemble(*exact)
            if res is not None and defeitos(res):
                # a forma exata encostou na pele exatamente numa aresta: desloca 3 milésimos de mm e tenta de novo
                d_ = [0.0031, 0.0017, 0.0023]
                rj = assemble(exact[0].translate(d_), exact[1].translate(d_))
                if rj is not None and defeitos(rj) < defeitos(res):
                    res = rj
                    if _DBG: print('navalha: deslocada')
            if res is not None and defeitos(res):
                # a forma exata deixou a malha com defeito: fica a forma pela grade se ela sair melhor
                rv = assemble(solid(F), solid(F + gap))
                if rv is not None and defeitos(rv) < defeitos(res):
                    res = rv
                    if _DBG: print('navalha: grade')
        except Exception:
            traceback.print_exc()
            res = None
    if res is None:
        res = assemble(solid(F), solid(F + gap))
    if res is None:
        # o soquete não encosta na peça (peça minúscula ou a linha não envolve uma parte): sem soquete
        return r, notes + [_chk('aviso', 'O soquete não ficou preso à peça aqui: a peça ficou com a face do corte normal.')]
    piece2, body2, Pg, Pm_ = res
    hid_chk = []
    if _NAVALHA:
        try:
            th = None
            if planes:
                Lp = np.vstack([x[2] for x in sel if id(x[1]) in planes])
                jlo, jhi = Lp.min(0) - depth - 4.0, Lp.max(0) + depth + 4.0

                def defeitos_raw(res):
                    # o mesmo conserto da exportação, só nos triângulos em volta da junta (rápido): arestas com
                    # 3 ou mais faces e triângulos degenerados (as bordas do recorte não contam)
                    n_ = 0
                    for m_ in [res[0]] + list(res[1]):
                        T_ = SPL.tri_array(m_)
                        cc = T_.mean(1)
                        T_ = T_[np.all((cc >= jlo) & (cc <= jhi), 1)]
                        if len(T_):
                            e_ = SPL._weld_safe(T_)[2]
                            n_ += e_['multiplas'] + e_['degenerados']
                    return n_
                d0 = defeitos_raw((piece2, body2))
                for jit in (0.0, 0.0031, -0.0047):
                    tj = _trim_hidden(piece2, body2, Pm_, Pg, sel, axes, planes, gap, depth, jit)
                    if tj is None:
                        break
                    if defeitos_raw((tj[0], tj[1])) <= d0:
                        th = tj
                        break
                    if _DBG:
                        print('trim_hidden: malha com defeito, desloca', jit, flush=True)
        except Exception:
            traceback.print_exc()
            th = None
        if th is not None:
            piece2, body2, vh, dh = th
            hid_chk.append(_chk('ok', f'A linha passa por baixo da roupa num trecho: a pele escondida ali ({_fmt(vh, 1)} mm³) ficou no corpo '
                                      f'e a junta fecha num plano na altura da borda visível (até {_fmt(dh, 1)} mm abaixo do trecho coberto '
                                      'da linha). A peça sai sem aba.'))
    ring_chk = []
    if cut.get('anel_plano'):
        try:
            fr = _flat_ring(piece2, body2, host, sel, axes, gap, wall_s, Pg, piece)
        except Exception as ex:
            traceback.print_exc()
            fr = None
        ok_ring = False
        if fr is not None:
            P3, B3, infos = fr
            B3 = sorted([b for b in B3 if _vol(b) >= 1.0], key=lambda q: -_vol(q))
            v0 = _vol(piece2) + sum(_vol(b) for b in body2)
            v1 = _vol(P3) + sum(_vol(b) for b in B3)
            # segurança: nada some, a peça continua inteira e o corpo não se parte
            if (len(E.parts(P3, 0.3)) <= len(E.parts(piece2, 0.3)) and len(B3) <= len(body2) and B3
                    and abs(v1 - v0) <= 0.02 * v0):
                piece2, body2, ok_ring = P3, B3, True
                dev = max(x[1] for x in infos if x[0] == 'ok')
                ring_chk.append(_chk('ok', 'Anel plano: a junta em volta do soquete ficou plana nas duas peças, de frente para o eixo '
                                           'do encaixe. O corpo pode apoiar na mesa por esse anel. Na pele, a divisa virou a reta do plano '
                                           f'(até {_fmt(dev, 1)} mm acima ou abaixo da linha desenhada).'))
        if not ok_ring:
            longe = fr is None or any(x[0] == 'longe' for x in (fr[2] if fr else []))
            ring_chk.append(_chk('aviso', 'Anel plano não aplicado: ' + ('a linha sobe e desce demais para um plano (contorno do rosto, por exemplo).'
                                                                          if longe and fr is None else 'o plano mexeria em partes que não são da junta.')
                                 + ' A junta ficou seguindo a linha.'))
    if curved[0]:
        notes = notes + [_chk('ok', 'A face do corte sobe e desce (linha inclinada): o fundo do soquete acompanha a face, '
                                    f'{_fmt(depth)} mm abaixo dela, e o corpo não fica oco.')]
    checks = notes + hid_chk + ring_chk + [_chk('ok', f'Soquete: a peça entra até {_fmt(depth)} mm no corpo, dentro da linha, com folga de {_fmt(gap, 2)} mm. '
                                 f'O corpo mantém pelo menos {_fmt(wall)} mm de parede por fora: a cavidade não aparece.')]
    if len(body2) > n_before:
        checks.append(_chk('aviso', f'O soquete deixou o corpo em {len(body2)} partes. Diminua a profundidade do soquete.'))
    r = dict(r, piece=piece2, body_parts=body2)
    ax_m = axes[id(max(sel, key=lambda x: x[0])[1])][0]
    r['axis'] = ax_m.copy()                          # a peça sai pelo eixo do encaixe (prévia afastada e montagem)
    if abs(ax_m[2]) > 0.99:
        r['print_T'] = None                          # encaixe de pé: imprime na posição do modelo (fundo do encaixe ou sola na mesa)
    if enc in ('losango', 'trava', 'peca', 'cavilha') and body2:
        _, ln, L = max(sel, key=lambda x: x[0])
        axn = axes[id(ln)][0]
        pv = G[plug]
        ctr = (L.mean(0))
        dist = np.linalg.norm((pv - ctr) - np.outer((pv - ctr) @ axn, axn), axis=1)
        core = pv[dist <= max(step * 2, np.percentile(dist, 30))]
        hb_ = core @ axn
        bottom = core[hb_ <= np.percentile(hb_, 10)].mean(0)
        g_real = gap                                   # folga exata (soquete por distâncias)
        c = bottom - axn * g_real
        pino = {'losango': 'corpo', 'trava': 'trava', 'peca': 'peca', 'cavilha': 'cavilha'}[enc]
        rp = _limb_pin(piece2, body2, pino, dict(pino_mm=cut.get('pino_mm') or 0), clr, wall, c, axn, diag,
                       hf=None, zsec=g_real + step)
        if not any(x['nivel'] == 'ok' for x in rp['checks']):
            # o pino nasce onde a face da peça realmente está, no polo da seção
            nn_ = axn
            hit = (lambda c_, n_: (lambda xy: np.array([SPL._face_height(piece2, c_, n_, xy, diag)])))(bottom, nn_)
            for zs in (step, 2 * step, 3 * step):
                rp2 = _limb_pin(piece2, body2, pino, dict(pino_mm=cut.get('pino_mm') or 0), clr, wall, bottom, nn_, diag,
                                hf=hit, zsec=zs)
                if any(x['nivel'] == 'ok' for x in rp2['checks']):
                    rp = rp2
                    break
        if any(x['nivel'] == 'ok' for x in rp['checks']):
            for x in rp['checks']:
                if x['nivel'] == 'ok':
                    x['texto'] = 'Pino no fundo do soquete: ' + x['texto']
            checks += rp['checks']
            r = dict(r, piece=rp['piece'], body_parts=rp['body_parts'], extra=r.get('extra', []) + rp.get('extra', []))
        else:
            checks.append(_chk('aviso', 'O pino não coube no fundo do soquete (a parte é fina demais aqui): a peça fica encaixada só '
                                        'pelo soquete. Para ter pino, corte numa parte mais grossa.'))
    elif enc != 'colar':
        checks.append(_chk('aviso', 'Com soquete o pino que gira não funciona (as paredes travam): a peça fica só encaixada.'))
    return r, checks


def _dump_fail(cut, checks):
    """Guarda o último corte que falhou em ~/EFC3D/ultimo_corte_falho.json, para diagnóstico."""
    try:
        import json, os
        d = os.path.join(os.path.expanduser('~'), 'EFC3D')
        os.makedirs(d, exist_ok=True)
        c = {k: (v.tolist() if hasattr(v, 'tolist') else v) for k, v in cut.items()}
        with open(os.path.join(d, 'ultimo_corte_falho.json'), 'w', encoding='utf-8') as f:
            json.dump(dict(quando=time.strftime('%Y-%m-%d %H:%M:%S'), corte=c, verificacao=checks), f, ensure_ascii=False)
    except Exception:
        pass


def _auto_plano(cut, loops):
    """O corte vai usar o plano automático? (forma automática, sem giro, e cada linha perto de um plano)"""
    enc = cut.get('encaixe') if cut.get('encaixe') in ENCAIXES else 'colar'
    fm = cut.get('forma') or DEF['forma']
    if not _PLANO_AUTO or enc in GIRA or fm == 'plano' or (fm == 'curva' and cut.get('forma_fixa')):
        return False
    if (cut.get('peca') or '_host_k' in cut) and not _PLANO_PECA:
        return False                      # corte numa peça já recortada: segue a linha, como antes
    ls = [_clean_loop(L) for L in loops or []]
    ls = [L for L in ls if L is not None]
    return bool(ls) and all(d <= lim for d, lim in (_plane_dev_rel(L) for L in ls))


def _plane_dev_rel(L):
    """(desvio da linha ao melhor plano, limite para a face ser plana): 10% da largura da parte na linha,
    entre 0,6 e 1 mm no tamanho real."""
    L = np.asarray(L, np.float64)
    c, nn, dev = _plane_fit(L)
    d = L - c
    d -= np.outer(d @ nn, nn)
    diam = 2.0 * float(np.median(np.linalg.norm(d, axis=1)))
    # nunca mais de 1 mm: a borda na pele fica a no máximo isso da linha desenhada
    return float(dev), min(max(0.6 * _CUR_K[0], 0.10 * diam), 1.0 * _CUR_K[0])


def _where(p, centro):
    """Descrição curta de um ponto do modelo para o aviso."""
    dx, dy = float(p[0] - centro[0]), float(p[1] - centro[1])
    lado = ('atrás' if dy > 0 else 'na frente') if abs(dy) >= abs(dx) else ('do lado +X' if dx > 0 else 'do lado -X')
    return f'{lado}, na altura Z ≈ {_fmt(float(p[2]), 0)} mm'


# ----------------------------------------------------------------------------- um corte
def casca_cut(host, cut, diag, centro_modelo):
    """Junta escondida debaixo de uma camada de cima (o braço que entra na manga, a perna na barra da calça,
    o pescoço na gola, a pata no pelo): a parte que sai continua por baixo da camada como um encaixe com a
    seção da própria parte e fundo plano, e a camada de cima fica inteira no corpo. A emenda visível é o
    vinco natural onde a parte entra na camada, como numa peça feita à mão. Só uma linha por corte.
    Devolve o mesmo dict de cut_one, ou None quando não serve (aí segue o corte de sempre)."""
    loops = [L for L in (_clean_loop(x) for x in (cut.get('linhas') or [])) if L is not None]
    if len(loops) != 1:
        return None
    L = loops[0]
    K = _CUR_K[0]
    if _os.environ.get('FLEXI_DUMP'):
        g_ = host.to_mesh()
        np.savez(_os.path.join(_os.environ['FLEXI_DUMP'], f"host_{cut.get('nome')}.npz".replace(' ', '_')),
                 v=np.asarray(g_.vert_properties)[:, :3], f=np.asarray(g_.tri_verts), L=L, centro=centro_modelo, diag=diag, k=K)
    gap = float(np.clip(float(cut.get('folga') or 0.2), 0.05, 2.0))
    depth = float(np.clip(float(cut.get('soquete_mm') or 4.0), 2.0, 30.0))
    c, nn0, _ = _plane_fit(L)
    hb = np.array(host.bounding_box())
    big = float(np.linalg.norm(hb[3:] - hb[:3])) + 10.0
    best = None
    cands = []
    for sgn in (1.0, -1.0):
        cands.append(_part_axis(host, c, sgn * nn0, L))
        if _CASCA_EIXO:
            cands.append(sgn * nn0)                  # também o eixo da própria linha (a face do corte no plano dela)
    for ax in cands:
        Fa = _frame(ax)
        Tw = SPL._T(Fa, c)
        loc = (L - c) @ Fa
        zl = loc[:, 2]
        try:
            cs = mf.CrossSection([loc[:, :2].tolist()], mf.FillRule.NonZero)
        except Exception:
            return None
        if cs.is_empty() or cs.area() < 1.0 * K * K:
            return None
        zmax, z_h = float(zl.max()) + 0.5 * K, float(zl.min()) - depth
        # o encaixe é a seção da parte com 0,2 mm a mais: as paredes não coincidem com a pele (sem lascas) e,
        # por baixo da camada, levam só 0,2 mm da face de dentro dela
        cs0 = cs
        cs = cs0.offset(0.2 * K, mf.JoinType.Round, 2.0, 32)
        prism = mf.Manifold.extrude(cs, zmax - z_h).translate([0, 0, z_h])
        top = mf.Manifold.cube([2 * big, 2 * big, big]).translate([-big, -big, zmax])
        Pw, Tp = E.X(prism, Tw), E.X(top, Tw)
        raw = E.parts(E.flat(host ^ (Pw + Tp)), 0.3)
        # só o que encosta no encaixe é a peça (o resto acima do plano, longe dali, é do corpo)
        own = [q for q in raw if _vol(q ^ E.X(mf.Manifold.extrude(cs, 0.6 * K).translate([0, 0, zmax - 0.5 * K]), Tw)) > 0]
        if not own:
            continue
        piece = E.flat(E.union(own)) if len(own) > 1 else own[0]
        pv = _vol(piece)
        if pv <= 0 or pv > 0.5 * _vol(host):
            continue
        csg = cs.offset(gap, mf.JoinType.Round, 2.0, 32)
        prism_g = E.X(mf.Manifold.extrude(csg, zmax - z_h + gap).translate([0, 0, z_h - gap]), Tw)
        pb = np.array(piece.bounding_box())
        boxp = mf.Manifold.cube((pb[3:] - pb[:3] + 2.0).tolist()).translate((pb[:3] - 1.0).tolist())
        body = E.flat(host - prism_g - (Tp ^ boxp))
        body_parts = sorted([q for q in E.parts(body, 0.5) if _vol(q) >= 1.0], key=lambda q: -_vol(q))
        if not body_parts:
            continue
        if _CONF_PELE and len(body_parts) > 1:
            continue                                  # a junta escondida não pode soltar pedaços do corpo
        # nada some: o que sai do corpo é a peça mais a folga em volta do encaixe
        perdido = _vol(host) - pv - sum(_vol(q) for q in body_parts)
        folga_v = gap * (cs.area() + float(np.linalg.norm(np.diff(np.vstack([loc[:, :2], loc[:1, :2]]), axis=0), axis=1).sum()) * (zmax - z_h)) * 1.5
        if perdido > folga_v + 0.02 * pv:
            continue
        cand = dict(piece=piece, body_parts=body_parts, ax=ax, Tw=Tw, pv=pv, depth=float(zl.min()) - z_h)
        if best is None or pv < best['pv']:
            best = cand
    if best is None:
        return None
    checks = [_chk('ok', f'Junta escondida: a parte continua {_fmt(best["depth"], 1)} mm por baixo da camada de cima (a barra da manga, '
                         f'a gola) como encaixe com fundo plano, e a camada fica inteira no corpo. Folga {_fmt(gap, 2)} mm.'),
              _chk('ok', f'Peça separada: {_fmt(best["pv"], 0)} mm³ ({round(100 * best["pv"] / max(_vol(host), 1e-9))}% da parte).')]
    return dict(ok=True, checks=checks, piece=best['piece'], body_parts=best['body_parts'], extra=[], axis=best['ax'],
                print_T=_inv(best['Tw']), forma='casca', encaixe='colar', _casca=True)


def cut_one(host, cut, diag, centro_modelo, peca_pts=None):
    """host: Manifold da parte onde a linha está. cut: dict(linhas=[[x,y,z]...], opções).
    Devolve dict(ok, checks, piece, body_parts, extra, axis, print_T)."""
    prm = dict(DEF)
    prm.update({k: v for k, v in cut.items() if v is not None})
    enc = prm['encaixe'] if prm['encaixe'] in ENCAIXES else 'colar'
    forma = 'plano' if enc in GIRA else ('plano' if prm['forma'] == 'plano' else 'curva')
    gap = float(np.clip(float(prm['folga']), 0.05, 2.0))
    clr = float(np.clip(float(prm['folga_pino']), 0.05, 1.0))
    checks = []
    if enc in GIRA and prm['forma'] != 'plano':
        checks.append(_chk('ok', 'Para a peça girar, a face do corte é plana (melhor plano pela linha).'))
    if enc in GIRA and len(cut.get('linhas') or []) > 1:
        checks.append(_chk('aviso', 'A peça gira só em volta do pino da linha 1: nas outras linhas (uma trança, uma mão) as partes '
                                    'podem bater ao girar. Confira na prévia ou use um encaixe fixo.'))
    loops = [_clean_loop(L) for L in cut.get('linhas') or []]
    loops = [L for L in loops if L is not None]
    if not loops:
        return dict(ok=False, checks=[_chk('erro', 'Desenhe uma linha fechada em volta da parte que vai sair.')])
    plano_auto = False
    plano_dev = 0.0
    if _PLANO_AUTO and enc not in GIRA and prm['forma'] != 'plano' and not (prm['forma'] == 'curva' and prm.get('forma_fixa')) \
            and (_PLANO_PECA or (not prm.get('peca') and '_host_k' not in cut)):
        # automático: se cada linha fica perto de um plano (até 10% da largura da parte), a face do corte
        # é esse plano, como numa peça feita à mão: emenda reta, encaixe firme e face plana para a mesa
        dv = [_plane_dev_rel(L) for L in loops]
        if all(d <= lim for d, lim in dv):
            forma = 'plano'
            plano_auto = True
            plano_dev = max(d for d, _ in dv)
            checks.append(dict(_chk('ok', f'Face do corte plana: a linha fica a até {_fmt(max(d for d, _ in dv), 1)} mm de um plano, então a '
                                          'emenda é reta e o encaixe fica firme. Para seguir a linha exatamente, escolha "Seguir a linha".'), _plano=True))
    planos = prm.get('_planos')
    if _PLANO_MISTO and planos is not None and len(planos) == len(loops) and forma == 'curva' and any(planos):
        # a linha desenhada é plana e as linhas extras (o contato que ela não pegava) seguem o vinco:
        # cada linha com a forma dela
        lines = [Line(L, ('misto' if _PLANO_BORDA else 'plano') if pl else 'curva', gap, diag, centro_modelo) for L, pl in zip(loops, planos)]
        plano_auto = True
        plano_dev = max(_plane_dev_rel(L)[0] for L, pl in zip(loops, planos) if pl)
    else:
        lines = [Line(L, forma, gap, diag, centro_modelo) for L in loops]
    for ln in lines:
        if forma == 'plano' and ln.dev > 2.0:
            checks.append(_chk('aviso', f'A linha fica até {_fmt(ln.dev)} mm fora do plano: o corte plano pode não pegar a volta toda. '
                                        'Use "Seguir a linha" ou desenhe a linha mais reta.'))
    # a fatia corta só o que a linha envolve: se ela passar perto de outra parte (a outra perna,
    # uma trança), o que foi raspado dessa outra parte volta para o lugar
    slab = E.union([ln.slab() for ln in lines])
    rest = E.flat(host - slab)
    plates = E.parts(E.flat(host ^ slab), 1e-6)
    stray = [q for q in plates if not any(ln.inside_loop(E.mesh_arrays(q)[0]) for ln in lines)]
    if len(stray) == len(plates):
        return dict(ok=False, checks=checks + [_chk('erro', 'A linha não passa pelo modelo: desenhe sobre a superfície da parte.')])
    if stray:
        rest = E.flat(rest + E.union(stray))
    comps = E.parts(rest, 0.02)
    if len(comps) < 2 and _PLANO_BORDA and forma == 'plano' and plano_auto:
        # o plano pela linha não separa (a parte está colada em outra junto da linha): plano no miolo e a
        # borda seguindo a linha
        lines = [Line(L, 'misto', gap, diag, centro_modelo) for L in loops]
        slab = E.union([ln.slab() for ln in lines])
        rest = E.flat(host - slab)
        plates = E.parts(E.flat(host ^ slab), 1e-6)
        stray = [q for q in plates if not any(ln.inside_loop(E.mesh_arrays(q)[0]) for ln in lines)]
        if stray and len(stray) < len(plates):
            rest = E.flat(rest + E.union(stray))
        comps = E.parts(rest, 0.02)
        if len(comps) >= 2:
            forma = 'misto'
            checks = [x for x in checks if not x.get('_plano')]
            checks.append(_chk('ok', 'Face do corte plana no miolo (onde fica o pino); junto da linha ela acompanha a pele, porque '
                                     'ali a parte encosta em outra.'))
    if len(comps) < 2:
        return dict(ok=False, checks=checks + [_chk('erro', 'A linha não separou nada: a parte continua presa em outro ponto '
                                                             '(por exemplo, a mão encostada na perna). Adicione outra linha a este '
                                                             'corte nesse ponto, ou confira se a linha dá a volta inteira.')])
    if peca_pts is not None and len(peca_pts):
        # área marcada: a peça é o que foi marcado (sem adivinhar o lado)
        hits = np.array([int((_on_surface(peca_pts, tri_array(q)) >= 0).sum()) for q in comps])
        if hits.max() == 0:
            return dict(ok=False, checks=checks + [_chk('erro', 'Não achei a área marcada depois do corte: marque de novo.')])
        sel = [k for k in range(len(comps)) if hits[k] >= max(1, 0.2 * hits.max())]
        rest_k = [k for k in range(len(comps)) if k not in sel]
        if not rest_k:
            return dict(ok=False, checks=checks + [_chk('erro', 'A marcação não separou nada: a parte continua presa em outro ponto. '
                                                                 'Marque até onde ela encosta ou desenhe uma linha nesse ponto.')])
        if prm.get('inverter'):
            sel, rest_k = rest_k, sel
        piece = E.flat(E.union([comps[k] for k in sel])) if len(sel) > 1 else comps[sel[0]]
        tiny = [comps[k] for k in rest_k if _vol(comps[k]) < 1.0]
        body_parts = sorted([comps[k] for k in rest_k if _vol(comps[k]) >= 1.0], key=lambda q: -_vol(q))
        loose = body_parts[1:]
        if not body_parts:
            return dict(ok=False, checks=checks + [_chk('erro', 'A área marcada não separa uma parte: marque a parte inteira, dando a volta '
                                                                 'nela (gire a vista com o botão direito), ou desenhe uma linha em volta dela.')])
    else:
        # lado da peça: pela primeira linha; "inverter" troca
        ln0 = lines[0]
        plus, minus = _who(comps, ln0.probes(+1)), _who(comps, ln0.probes(-1))
        if plus.sum() == 0 and minus.sum() == 0:
            return dict(ok=False, checks=checks + [_chk('erro', 'A linha não passa pelo modelo: desenhe sobre a superfície da parte.')])
        kp, km = int(np.argmax(plus)), int(np.argmax(minus))
        if kp == km:
            return dict(ok=False, checks=checks + [_chk('erro', 'Os dois lados da linha continuam ligados: a parte está presa em outro '
                                                                 'ponto. Adicione outra linha a este corte nesse ponto.')])
        if _vol(comps[kp]) > _vol(comps[km]):                 # a peça é, por padrão, o lado menor
            kp, km = km, kp
        if prm.get('inverter'):
            kp, km = km, kp
        piece = comps[kp]
        tiny = [q for k, q in enumerate(comps) if k not in (kp, km) and _vol(q) < 1.0]
        loose = [q for k, q in enumerate(comps) if k not in (kp, km) and _vol(q) >= 1.0]
        body_parts = [comps[km]] + loose
    if tiny:
        checks.append(_chk('aviso', f'{len(tiny)} farelo(s) menores que 1 mm³ ficaram soltos perto da linha e foram descartados.'))
    if loose:
        checks.append(_chk('aviso', f'O corte soltou {len(loose)} parte(s) a mais (a fatia do corte passou perto de outra parte). '
                                    'Elas vão para a exportação: confira na prévia.'))
    hv, pv = _vol(host), _vol(piece)
    checks.append(_chk('ok', f'Peça separada: {_fmt(pv, 0)} mm³ ({round(100 * pv / max(hv, 1e-9))}% da parte), '
                             f'folga entre as faces {_fmt(gap, 2)} mm.'))
    if pv > 0.5 * hv and peca_pts is None:
        checks.append(_chk('aviso', 'A peça ficou com mais da metade da parte: se era o outro lado, marque "Inverter o lado".'))
    if any(ln.forma == 'curva' for ln in lines):
        cv = max(ln.info.get('curvatura', 0.0) for ln in lines if ln.forma == 'curva')
        if cv > 0.6:
            checks.append(_chk('aviso', f'Face do corte curva ({_fmt(cv)} mm de altura): ela não fica plana na mesa; '
                                        'imprima a peça com suporte ou use a forma "Plano".'))
    # orientação de cada linha: nn aponta para a peça
    for ln in lines:
        pp = _who([piece], ln.probes(+1))[0]
        pm = _who([piece], ln.probes(-1))[0]
        if pm > pp:
            ln.flip()
    extra = []
    wall = float(prm.get('parede', 1.2))
    if enc != 'colar':
        for n_ln, ln in enumerate(lines):
            zsec = (ln.info['zsec'] if ln.forma != 'plano' else 0.02) + gap / 2
            hf = None if ln.forma == 'plano' else ln.hf
            if enc in GIRA:
                r_ = _round_pin(piece, body_parts, enc, clr, wall, ln.c, ln.nn, diag, hf, zsec, float(prm.get('pino_mm') or 0))
                r_.setdefault('extra', [])
            else:
                pino = {'losango': 'corpo', 'trava': 'trava', 'peca': 'peca', 'cavilha': 'cavilha'}[enc]
                r_ = _limb_pin(piece, body_parts, pino, dict(pino_mm=prm.get('pino_mm') or 0), clr, wall,
                               ln.c, ln.nn, diag, hf=hf, zsec=zsec)
            if len(lines) > 1:                  # várias linhas: diz de qual linha é cada pino
                for x in r_['checks']:
                    x['texto'] = f'Linha {n_ln + 1}: ' + (x['texto'] if 'estreita' not in x['texto'] else
                                                         'seção estreita para pino; ali a peça fica só colada.')
            checks += r_['checks']
            piece, body_parts = r_['piece'], r_['body_parts']
            extra += r_.get('extra', [])
    else:
        checks.append(_chk('ok', 'Sem pino: as faces encaixam e é só colar (CA ou epóxi).'))
    Tw = _T(lines[0].Fr, lines[0].c)
    ok = not any(x['nivel'] == 'erro' for x in checks)
    return dict(ok=ok, checks=checks, piece=E.flat(piece), body_parts=body_parts, extra=extra,
                axis=lines[0].nn, print_T=_inv(Tw), forma=forma, encaixe=enc, _plano_auto=plano_auto, _plano_dev=plano_dev)


# ----------------------------------------------------------------------------- área marcada: corte pelo volume
def _patch_pin(piece, body_parts, enc, prm, clr, wall, R, diag, prefer=None):
    """Pino num contato entre a peça e o corpo: o mais perto das linhas desenhadas (prefer), senão o
    maior (o pescoço, e não as pontas das tranças). Se ali não couber, tenta os outros contatos."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree
    Tq = tri_array(piece)
    newq = Tq[_on_surface(Tq.mean(1), R.T) < 0]
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
                    body_parts=body_parts, extra=[], patches=0)
    cen = best.mean(1)
    pairs = cKDTree(cen).query_pairs(1.2, output_type='ndarray')
    n = len(cen)
    g = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n)) if len(pairs) else coo_matrix((n, n))
    _, lab = connected_components(g, directed=False)
    nr = np.cross(best[:, 1] - best[:, 0], best[:, 2] - best[:, 0])
    ar = np.linalg.norm(nr, axis=1) / 2
    tot = np.bincount(lab, weights=ar)
    patches = int((tot > 0.05 * tot.max()).sum())
    cand = [k for k in range(len(tot)) if tot[k] >= 0.1 * tot.max()]
    if prefer is not None and len(prefer):
        tree = cKDTree(np.asarray(prefer, np.float64))
        cand.sort(key=lambda k: float(np.median(tree.query(best[lab == k].mean(1))[0])))
    else:
        cand.sort(key=lambda k: -tot[k])
    r_ = None
    for big in cand[:4]:
        t, nrk, ark = best[lab == big], nr[lab == big], ar[lab == big]
        nn = -(nrk.sum(0))
        if np.linalg.norm(nn) < 1e-9:
            continue
        nn /= np.linalg.norm(nn)
        c = (t.mean(1) * ark[:, None]).sum(0) / ark.sum()
        sd = (t.reshape(-1, 3) - c) @ nn
        hit = (lambda c_, n_: (lambda xy: np.array([SPL._face_height(piece, c_, n_, xy, diag)])))(c, nn)
        zsec = float(max(0.02, sd.max() + 0.3))
        if enc in GIRA:
            r_ = _round_pin(piece, body_parts, enc, clr, wall, c, nn, diag, hit, zsec, float(prm.get('pino_mm') or 0))
            r_.setdefault('extra', [])
        else:
            pino = {'losango': 'corpo', 'trava': 'trava', 'peca': 'peca', 'cavilha': 'cavilha'}[enc]
            r_ = _limb_pin(piece, body_parts, pino, dict(pino_mm=prm.get('pino_mm') or 0), clr, wall, c, nn, diag, hf=hit, zsec=zsec)
        if any(x['nivel'] == 'ok' for x in r_['checks']):
            break
    if r_ is None:
        return dict(checks=[_chk('aviso', 'Não achei a face de contato com o corpo para o pino.')], piece=piece,
                    body_parts=body_parts, extra=[], patches=patches)
    r_['patches'] = patches
    return r_


def _border_band(R, mask, w=1.0):
    """Triângulos marcados a até w mm da borda (o lado de dentro da borda)."""
    from scipy.spatial import cKDTree
    band = np.zeros(len(mask), bool)
    for k in range(3):
        o = R.nb[:, k]
        band |= mask & (o >= 0) & ~mask[np.maximum(o, 0)]
    rest = ~mask
    if rest.any() and mask.any():
        pts = np.concatenate([R.T[rest].reshape(-1, 3), R.cen[rest]])
        d, _ = cKDTree(pts).query(R.cen[mask], distance_upper_bound=w)
        band[np.where(mask)[0][np.isfinite(d)]] = True
    return band


def _taubin(V, Fc, it=25, lam=0.5, mu=-0.53):
    """Alisa a malha do marching cubes (Taubin: não encolhe). Tira a escadinha dos voxels para o
    corte parecer feito por uma lâmina, não serrilhado."""
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


def _mc_manifold(F, step, lo, smooth=25, what='malha do corte'):
    from skimage.measure import marching_cubes
    V, Fc, _, _ = marching_cubes(F, 0.0, spacing=(step, step, step))
    if smooth:
        V = _taubin(V, Fc, smooth)
    V = V + lo - step
    M = mf.Manifold(mf.Mesh(vert_properties=np.ascontiguousarray(V, np.float32), tri_verts=np.ascontiguousarray(Fc[:, ::-1], np.uint32)))
    if M.status() != mf.Error.NoError or M.volume() <= 0:
        raise ValueError(what)
    return M


_BANDA_SIM = _os.environ.get('FLEXI_BANDA_SIM', '0') == '1'
BANDA_CORTE = 0.5             # faixa livre junto da linha: o corte segue a linha (e não corta os gomos da trança)


def _smin(a, b, k):
    """Mínimo suave de duas distâncias: o canto vira um arredondado de raio ~k (sem dentes na malha)."""
    hh = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - hh) + a * hh - k * hh * (1 - hh)


def _poly_sd(Q2, xy, chunk=20000):
    """Distância (mm) com sinal de pontos 2D até o contorno: positiva dentro."""
    from scipy.spatial import cKDTree
    Q2 = np.asarray(Q2, np.float64)
    seg = np.vstack([Q2, Q2[:1]])
    dens = [seg[:-1]]
    for t in (0.25, 0.5, 0.75):
        dens.append(seg[:-1] * (1 - t) + seg[1:] * t)
    d, _ = cKDTree(np.concatenate(dens)).query(xy)
    lo, hi = Q2.min(0), Q2.max(0)
    box = np.all((xy >= lo) & (xy <= hi), 1)
    ins = np.zeros(len(xy), bool)
    ib = np.where(box)[0]
    for k in range(0, len(ib), chunk):
        j = ib[k:k + chunk]
        ins[j] = _inside(Q2, xy[j])
    return np.where(ins, d, -d)


def _blade_lines(loops, diag, centro):
    """Linhas que dão a volta numa parte (pescoço, pulso): ali o corte é uma lâmina, a superfície
    lisa que passa pela linha, e não a película achada nos voxels."""
    out = []
    for L in loops or []:
        L = np.asarray(L, np.float64)
        try:
            ln = Line(L, 'curva', 0.2, diag, centro)
        except Exception:
            continue
        out.append((ln, L, _loop_compact(ln) >= SOQUETE_COMPACTO))
    return out


_CAMADA = _os.environ.get('FLEXI_CAMADA', '0') == '1'      # experimental: desligado


def _camadas(R, mask, inside, dm, do, step, lo, n):
    """Pele prolongada dos dois lados (superfície implícita por mínimos quadrados móveis, IMLS: cada ponto
    da pele com a sua normal vira um plano local, e os planos dos vizinhos se misturam com pesos gaussianos).
    Devolve (voxels baratos para o corte, zona, valor contínuo da face do corte na zona) ou None."""
    from scipy.spatial import cKDTree
    K = _CUR_K[0]
    G = np.stack(np.meshgrid(*[lo[k] + step * np.arange(n[k]) for k in range(3)], indexing='ij'), -1)
    zone = inside & (dm > 1.5 * step) & (do > 1.5 * step) & (np.minimum(dm, do) < 6.0 * K)
    if zone.sum() < 20:
        return None
    Q = G[zone]
    hi = lo + step * (np.array(n) - 1)
    h = max(1.5 * step, 1.0 * K)

    def imls(sel):
        c = R.cen[sel]
        nn = R.nrm[sel]
        box = np.all((c >= lo - 6.0) & (c <= hi + 6.0), 1)
        c, nn = c[box], nn[box]
        if len(c) < 10:
            return None
        if len(c) > 250000:
            k_ = np.linspace(0, len(c) - 1, 250000).astype(int)
            c, nn = c[k_], nn[k_]
        d, j = cKDTree(c).query(Q, k=min(10, len(c)))
        w = np.exp(-(d / h) ** 2)
        f = (w * np.einsum('qkj,qkj->qk', Q[:, None, :] - c[j], nn[j])).sum(1)
        return f / np.maximum(w.sum(1), 1e-12), d[:, 0]
    fm = imls(mask)
    fo = imls(~mask)
    if fm is None or fo is None:
        return None
    (f_m, d_m), (f_o, d_o) = fm, fo
    # só vale perto da pele de onde ela vem (até 6 mm): longe, o prolongamento deixa de ser confiável
    ok_m = d_m < 6.0 * K
    ok_o = d_o < 6.0 * K
    cheap_q = (ok_m & (np.abs(f_m) < 0.75 * step)) | (ok_o & (np.abs(f_o) < 0.75 * step))
    cheap = np.zeros(n, bool)
    cheap[zone] = cheap_q
    # valor contínuo da face: a pele prolongada mais perto (lado da peça positivo)
    use_m = ok_m & (~ok_o | (np.abs(f_m) <= np.abs(f_o)))
    Lc = np.where(use_m, -f_m, f_o) / step
    near = (ok_m | ok_o) & (np.minimum(np.where(ok_m, np.abs(f_m), np.inf), np.where(ok_o, np.abs(f_o), np.inf)) < 2.0 * step)
    z2 = np.zeros(n, bool)
    zi = np.argwhere(zone)
    z2[tuple(zi[near].T)] = True
    if _DBG:
        print('camadas: zona', int(zone.sum()), 'barata', int(cheap.sum()), flush=True)
    return cheap, z2, np.clip(Lc[near], -1.0, 1.0).astype(np.float32)


def _mincut_cutter(host, R, mask, max_vox=1_600_000, lines=None):
    """Sólido da peça pela superfície mínima que passa pela borda marcada (uma película de
    sabão presa na borda): corte mínimo num grid de voxels do volume. Perto da superfície
    marcada é peça, perto da não marcada é corpo; no meio, o app escolhe a menor área de corte.
    Assim a peça para na borda (sem tampão para dentro do corpo e sem levar a roupa) e as
    partes deitadas no corpo (tranças no peito) se separam pela faixa de contato."""
    from scipy.ndimage import distance_transform_edt, gaussian_filter
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import maximum_flow, breadth_first_order
    from skimage.measure import marching_cubes
    P = R.T[mask].reshape(-1, 3)
    hb = host.bounding_box()
    lo = np.maximum(P.min(0) - 5.0, np.array(hb[:3]) - 1.0)
    hi = np.minimum(P.max(0) + 5.0, np.array(hb[3:]) + 1.0)
    ext = hi - lo
    if np.any(ext <= 0):
        return None                                  # a marcação está fora deste sólido
    step = float(np.clip(ext.max() / 110.0, 0.3, 0.7))
    step = max(step, float((np.prod(ext) / max_vox) ** (1 / 3)))
    if _os.environ.get('FLEXI_GRADE_PASSO'):
        step = float(_os.environ['FLEXI_GRADE_PASSO'])
    n = np.ceil(ext / step).astype(int) + 1
    xs, ys, zs = [lo[k] + step * np.arange(n[k]) for k in range(3)]
    inside = np.zeros(n, bool)
    XY = np.stack(np.meshgrid(xs, ys, indexing='ij'), -1).reshape(-1, 2)
    for k, z in enumerate(zs):
        cs = host.slice(float(z))
        if cs.is_empty():
            continue
        ins = np.zeros(len(XY), bool)
        for pl in cs.to_polygons():
            pl = np.asarray(pl, np.float64)
            bx = (XY[:, 0] >= pl[:, 0].min()) & (XY[:, 0] <= pl[:, 0].max()) & (XY[:, 1] >= pl[:, 1].min()) & (XY[:, 1] <= pl[:, 1].max())
            if bx.any():
                ins[bx] ^= _inside(pl, XY[bx])
        inside[:, :, k] = ins.reshape(n[0], n[1])
    if inside.sum() < 50:
        raise ValueError('grade vazia')
    band = _border_band(R, mask, float(_os.environ.get('FLEXI_BANDA', BANDA_CORTE)))
    ub = np.zeros(len(mask), bool)
    for k in range(3):
        o = R.nb[:, k]
        ub |= ~mask & (o >= 0) & mask[np.maximum(o, 0)]
    if _BANDA_SIM:
        # a faixa livre dos dois lados da borda, da mesma largura: o corte fica centrado na linha (com a faixa
        # só do lado de dentro, a superfície mínima corria para dentro e a peça perdia 0,5 a 1,5 mm de pele na
        # borda: a faixa de testa lisa na borda da mecha)
        ub |= _border_band(R, ~mask, float(_os.environ.get('FLEXI_BANDA', BANDA_CORTE)))

    def occ(sel):
        Tt = R.T[sel]
        c = Tt.mean(1)
        samp = np.concatenate([c, Tt[:, 0] * 0.6 + c * 0.4, Tt[:, 1] * 0.6 + c * 0.4, Tt[:, 2] * 0.6 + c * 0.4])
        ijk = np.round((samp - lo) / step).astype(int)
        ok = np.all((ijk >= 0) & (ijk < n), 1)
        g = np.zeros(n, bool)
        g[tuple(ijk[ok].T)] = True
        return g
    om, oo = occ(mask & ~band), occ(~mask & ~ub)
    if not om.any():
        raise ValueError('área marcada fina demais')
    dm = distance_transform_edt(~om, sampling=step)
    do = distance_transform_edt(~oo, sampling=step) if oo.any() else np.full(n, 1e9)
    near = 1.6 * step
    # junto da superfície, cada voxel é do lado da superfície mais perto (numa trança fina deitada
    # no peito os dois lados estão perto: vale o mais perto, senão o corte atravessaria a trança)
    src = inside & (dm <= near) & (dm < do - 0.5 * step)
    snk = inside & (do <= near) & (do < dm - 0.5 * step)
    edge = np.zeros(n, bool)
    edge[[0, -1], :, :] = True
    edge[:, [0, -1], :] = True
    edge[:, :, [0, -1]] = True
    snk |= inside & edge & ~src                      # o corpo continua além da caixa
    nid = -np.ones(n, np.int64)
    ii = np.where(inside.ravel())[0]
    nid.ravel()[ii] = np.arange(len(ii))
    N = len(ii)
    s_, t_ = N, N + 1
    # camadas: onde uma parte está apoiada sobre a outra (a franja na testa, o laço no cabelo), a pele de
    # cada lado continua por baixo da outra como uma superfície lisa (a pele prolongada). O corte mínimo
    # fica barato ao longo dela, então a junta passa pela pele escondida e não em degraus pelo meio
    cam = None
    if _CAMADA:
        try:
            cam = _camadas(R, mask, inside, dm, do, step, lo, n)
        except Exception:
            traceback.print_exc()
            cam = None
    wv = np.full(N, 10, np.int32)
    if cam is not None:
        wv[nid[cam[0]]] = 2
    rows, cols, cap = [], [], []
    for ax in range(3):
        a = [slice(None)] * 3
        b = [slice(None)] * 3
        a[ax], b[ax] = slice(0, -1), slice(1, None)
        A, B = nid[tuple(a)], nid[tuple(b)]
        ok = (A >= 0) & (B >= 0)
        A, B = A[ok], B[ok]
        rows += [A, B]
        cols += [B, A]
        cw = np.minimum(wv[A], wv[B])
        cap += [cw, cw]
    BIG = 1 << 24
    sv, tv = nid[src], nid[snk]
    rows += [np.full(len(sv), s_), tv]
    cols += [sv, np.full(len(tv), t_)]
    cap += [np.full(len(sv), BIG, np.int32), np.full(len(tv), BIG, np.int32)]
    G = csr_matrix((np.concatenate(cap), (np.concatenate(rows), np.concatenate(cols))), shape=(N + 2, N + 2))
    res = maximum_flow(G, s_, t_, method='dinic')
    Rz = (G - res.flow).tocsr()
    Rz.data = (Rz.data > 0).astype(np.int8)
    Rz.eliminate_zeros()
    reach = breadth_first_order(Rz, s_, directed=True, return_predecessors=False)
    lab = np.zeros(N + 2, bool)
    lab[reach] = True
    L = np.clip((do - dm) / step, -1.0, 1.0).astype(np.float32)    # fora do sólido: só para a borda ficar lisa
    L.ravel()[ii] = np.where(lab[:N], 1.0, -1.0)
    if cam is not None:
        # junto da pele prolongada, a face do corte vai para a posição exata dela (sem os degraus da grade)
        _, zone, Lc = cam
        Lz = L[zone]
        agree = np.sign(Lc) == np.sign(Lz)
        Lz[agree] = Lc[agree]
        L[zone] = Lz
    # pontas que o corte mínimo soltou da peça por uma parte fina (o laço no fim da trança, onde a
    # linha passa rente): religa pelo caminho mais curto dentro do sólido, se for curto (até 2 mm)
    from scipy.ndimage import label as _cc
    P = inside & (L > 0)
    lb, ncomp = _cc(P)
    if ncomp > 1:
        sz = np.bincount(lb.ravel())
        sz[0] = 0
        main = int(np.argmax(sz))
        dmain = distance_transform_edt(lb != main, sampling=step)
        for k in [int(x) for x in np.argsort(-sz)[1:7]]:
            if sz[k] == 0 or sz[k] > 0.3 * sz[main]:
                continue
            dk = distance_transform_edt(lb != k, sampling=step)
            gapk = float(dmain[lb == k].min())
            if gapk > 2.0:
                continue
            bridge = inside & (dmain + dk <= gapk + 1.5 * step) & (dmain <= gapk + step)
            L[bridge] = 1.0
    L = gaussian_filter(L, 1.0)
    # junto da superfície, a borda do corte vai para a posição exata entre a área marcada e a não
    # marcada (abaixo do tamanho do voxel): a borda segue a linha, sem dentes de serra
    try:
        from scipy.spatial import cKDTree
        shell = inside & (np.minimum(dm, do) <= 2.5 * step) & (np.abs(do - dm) < 3.0 * step)
        if shell.any() and oo.any():
            def samples(sel):
                Tt = R.T[sel]
                c = Tt.mean(1)
                return np.concatenate([c] + [Tt[:, j] * 0.5 + c * 0.5 for j in range(3)])
            q = np.stack([g[shell] for g in np.meshgrid(xs, ys, zs, indexing='ij')], -1)
            dmx = cKDTree(samples(mask)).query(q, distance_upper_bound=4 * step)[0]
            dox = cKDTree(samples(~mask)).query(q, distance_upper_bound=4 * step)[0]
            dmx[~np.isfinite(dmx)] = 4 * step
            dox[~np.isfinite(dox)] = 4 * step
            Fx = np.clip((dox - dmx) / step, -1.0, 1.0)
            Lc = L[shell]
            agree = (np.sign(Fx) == np.sign(Lc)) & (np.abs(Fx) > 1e-3)
            Lc[agree] = Fx[agree]
            L[shell] = Lc
    except Exception:
        traceback.print_exc()
    # na volta do pescoço o corte é a lâmina: a superfície lisa que passa pela linha
    for ln, Lp, compacta in lines or []:
        try:
            if compacta:
                _blade(L, inside, ln, Lp, R, mask, xs, ys, zs, lo, step, np.minimum(dm, do))
            else:
                _footprint(L, inside, ln, Lp, R, mask, xs, ys, zs, lo, step, dm, do)
        except Exception:
            traceback.print_exc()
    L = np.pad(L, 1, constant_values=-1.0)
    return _mc_manifold(L, step, lo, 30)



def _base_plane(Lw, Q, k=20):
    """Plano local do corpo por baixo de uma parte deitada: o plano dos pontos da linha mais perto
    (a linha contorna a parte por cima do corpo, dos dois lados). Devolve (ponto, normal) por ponto."""
    from scipy.spatial import cKDTree
    k = min(k, len(Lw))
    _, nb = cKDTree(Lw).query(Q, k=k)
    Pk = Lw[nb]
    mu = Pk.mean(1)
    C = np.einsum('nki,nkj->nij', Pk - mu[:, None], Pk - mu[:, None])
    _, ev = np.linalg.eigh(C)
    return mu, ev[:, :, 0]


def _base_height(Lw, Q, ref, k=40, ridge=1e-2):
    """Altura de cada ponto Q acima do corpo por baixo de uma parte deitada. O corpo por baixo é
    estimado pelos pontos da linha mais perto (ela contorna a parte, sobre o corpo): plano local com
    curvatura (quadrática), para seguir o ombro ou o peito sem deixar degrau. ref: lado de fora."""
    from scipy.spatial import cKDTree
    k = min(k, len(Lw))
    dd, nb = cKDTree(Lw).query(Q, k=k)
    Pk = Lw[nb]
    mu = Pk.mean(1)
    C = np.einsum('nki,nkj->nij', Pk - mu[:, None], Pk - mu[:, None])
    _, ev = np.linalg.eigh(C)
    bn = ev[:, :, 0] * np.where((ev[:, :, 0] @ ref) < 0, -1.0, 1.0)[:, None]
    e1, e2 = ev[:, :, 2], ev[:, :, 1]
    D = Pk - mu[:, None]
    u, v, w = np.einsum('nki,ni->nk', D, e1), np.einsum('nki,ni->nk', D, e2), np.einsum('nki,ni->nk', D, bn)
    sc = np.maximum(np.sqrt((u * u + v * v).mean(1)), 1e-6)[:, None]
    u, v = u / sc, v / sc
    A = np.stack([np.ones_like(u), u, v, u * u, u * v, v * v], -1)
    wt = np.exp(-(dd / np.maximum(dd[:, -1:], 1e-6)) ** 2 * 2.0)
    AtA = np.einsum('nki,nk,nkj->nij', A, wt, A) + ridge * np.diag([0, 0, 0, 1, 1, 1.0])[None] + 1e-9 * np.eye(6)[None]
    Atb = np.einsum('nki,nk,nk->ni', A, wt, w)
    co = np.linalg.solve(AtA, Atb[..., None])[..., 0]
    dq = Q - mu
    uq, vq = np.einsum('ni,ni->n', dq, e1) / sc[:, 0], np.einsum('ni,ni->n', dq, e2) / sc[:, 0]
    base = co[:, 0] + co[:, 1] * uq + co[:, 2] * vq + co[:, 3] * uq * uq + co[:, 4] * uq * vq + co[:, 5] * vq * vq
    return np.einsum('ni,ni->n', dq, bn) - base, bn


def _footprint(L, inside, ln, Lp, R, mask, xs, ys, zs, lo, step, dm, do, below=1.5, above=8.0, lift=0.0):
    """Parte deitada sobre o corpo (trança no ombro, rabo, mão na perna): dentro da linha, o que está
    acima da superfície do corpo por baixo dela é da peça e o que está abaixo é do corpo. A separação
    segue o corpo por baixo (o kimono), e não a menor área: a trança sai inteira e o corpo não é cavado."""
    Lw = np.asarray(Lp, np.float64)
    r = ln.R0 + above + 2.0
    i0 = np.maximum(np.floor((ln.c - r - lo) / step).astype(int), 0)
    i1 = np.minimum(np.ceil((ln.c + r - lo) / step).astype(int) + 1, np.array(L.shape))
    if np.any(i1 <= i0):
        return
    sl = tuple(slice(a, b) for a, b in zip(i0, i1))
    X = np.stack(np.meshgrid(xs[sl[0]], ys[sl[1]], zs[sl[2]], indexing='ij'), -1).reshape(-1, 3)
    ins = inside[sl].ravel()
    loc = (X - ln.c) @ ln.Fr
    sd = np.full(len(X), -1e9)
    cand = ins & (np.abs(loc[:, 0]) <= ln.R0 + 1) & (np.abs(loc[:, 1]) <= ln.R0 + 1)
    sd[cand] = _poly_sd(ln.Q2, loc[cand, :2])
    reg = cand & (sd >= -0.5)
    if not reg.any():
        return
    # lado de fora do corpo: para onde a área marcada sobe
    cen = R.T[mask].mean(1)
    near = np.linalg.norm(cen - ln.c, axis=1) <= ln.R0 + 2.0
    if near.sum() < 5:
        return
    hm, _ = _base_height(Lw, cen[near], ln.nn)
    sgn = np.sign(np.median(hm)) or 1.0
    ir = np.where(reg)[0]
    hb, _ = _base_height(Lw, X[ir], sgn * ln.nn)
    use = (hb >= -below) & (hb <= above)
    sub = L[sl].ravel().copy()
    sub[ir[use]] = np.clip((hb[use] - lift) / step, -1.0, 1.0)
    L[sl] = sub.reshape(L[sl].shape)


def _blade(L, inside, ln, Lp, R, mask, xs, ys, zs, lo, step, dsurf=None, band=3.0):
    from scipy.spatial import cKDTree
    from scipy.ndimage import label as _cc
    r = ln.R0 + band + 2.0
    i0 = np.maximum(np.floor((ln.c - r - lo) / step).astype(int), 0)
    i1 = np.minimum(np.ceil((ln.c + r - lo) / step).astype(int) + 1, np.array(L.shape))
    if np.any(i1 <= i0):
        return
    sl = tuple(slice(a, b) for a, b in zip(i0, i1))
    X = np.stack(np.meshgrid(xs[sl[0]], ys[sl[1]], zs[sl[2]], indexing='ij'), -1)
    sh = X.shape[:3]
    loc = (X.reshape(-1, 3) - ln.c) @ ln.Fr
    h = loc[:, 2] - ln.hf(loc[:, :2])
    near = np.abs(h) <= band
    sd = np.full(len(loc), -1e9)
    sd[near] = _poly_sd(ln.Q2, loc[near, :2])
    # lado da peça: a área marcada perto da linha
    cen = R.T[mask].mean(1)
    lc = (cen - ln.c) @ ln.Fr
    ok = (np.linalg.norm(cen - ln.c, axis=1) <= ln.R0 + 3.0)
    if ok.sum() < 5:
        return
    hm = lc[ok, 2] - ln.hf(lc[ok, :2])
    sgn = np.sign(np.median(hm)) or 1.0
    if _LAMINA_TODA:
        # dentro da linha (vista de frente, a mais de 1 mm dela) manda a lâmina em qualquer altura: o que fica
        # debaixo de uma peça apoiada (o cabelo sob o laço) é do corpo, e a peça para na superfície lisa que
        # passa pela linha. Perto da linha e fora dela vale a marcação, como antes (orelha, mecha)
        fundo = np.zeros(len(loc), bool)
        fundo[near] = sd[near] >= 1.0
        near_all = np.abs(h) <= max(band, 2.0 * ln.R0 + 4.0)
        extra = (~near) & near_all
        if extra.any():
            sd[extra] = _poly_sd(ln.Q2, loc[extra, :2])
            fundo[extra] = sd[extra] >= 1.0
        near = near | (extra & fundo)
    reg = (near & (sd >= -0.2)).reshape(sh) & inside[sl]
    if dsurf is not None:
        # junto da superfície manda a marcação (uma orelha que a lâmina cortaria ao meio fica inteira
        # do lado em que a linha a deixou); a lâmina vale por dentro, onde não há o que ver
        if _LAMINA_TODA:
            reg &= (dsurf[sl] > 1.0) | fundo.reshape(sh)
        else:
            reg &= dsurf[sl] > 1.0
    lb, nc = _cc(reg)
    if nc == 0:
        return
    tr = cKDTree(Lp)
    ii = np.where(lb.ravel() > 0)[0]
    dd, _ = tr.query(X.reshape(-1, 3)[ii])
    keep_ids = np.unique(lb.ravel()[ii[dd <= 1.5 * step + 0.5]])
    keep = np.isin(lb, keep_ids[keep_ids > 0])
    sub = L[sl]
    sub[keep] = np.clip(sgn * h.reshape(sh)[keep] / step, -1.0, 1.0)
    L[sl] = sub


def cut_by_mask_volume(host, S, mask, cut, diag, prefer=None, loops=None, centro=None):
    """A peça é o volume mais perto da área marcada (o mesmo método do "pela pintura" do Separar
    por cor). Serve quando a parte encosta no corpo ao longo de uma faixa (trança no ombro e no
    peito, mão na perna): as faces de contato seguem a borda da marcação."""
    prm = dict(DEF)
    prm.update({k: v for k, v in cut.items() if v is not None})
    enc = prm['encaixe'] if prm['encaixe'] in ENCAIXES else 'colar'
    gap = float(np.clip(float(prm['folga']), 0.05, 2.0))
    clr = float(np.clip(float(prm['folga_pino']), 0.05, 1.0))
    paint = np.ones(S.num_tri(), np.uint8)
    paint[np.asarray(mask, bool)] = 2
    R = SPL.Regions(S, paint)
    regs = sorted([k for k, rg in enumerate(R.list) if rg['cor'] == 2], key=lambda k: -R.list[k]['area'])
    if not regs:
        return dict(ok=False, checks=[_chk('erro', 'Não achei a área marcada.')])
    rid = regs[0]
    p2 = dict(SPL.DEFAULTS, tipo='pintura', folga=gap, pino='nenhum', espessura=0.0, suavizar=0.0, _livre=True)
    mk = np.asarray(mask, bool)
    cen_h = centro if centro is not None else np.asarray(E.centroid(host))

    def one(h, k):
        """Corta a área k do sólido h com a grade só dela (fina, como num corte de uma área)."""
        pk = dict(p2)
        mk_k = np.zeros(len(mk), bool)
        mk_k[R.list[k]['tris']] = True
        try:
            lk = loops
            if loops and len(regs) > 1:              # só as linhas desta área: a grade fica do tamanho dela
                P = R.cen[R.list[k]['tris']]
                lo_, hi_ = P.min(0) - 3.0, P.max(0) + 3.0
                lk = [L for L in loops if np.all((np.asarray(L) >= lo_) & (np.asarray(L) <= hi_), axis=1).mean() > 0.5] or None
            bl = _blade_lines(lk, diag, cen_h) if lk else None
            if not _os.environ.get('FLEXI_SEM_CUTTER'):
                pk['_cutter'] = _mincut_cutter(h, R, mk_k if len(regs) > 1 else mk, lines=bl)
        except Exception:
            traceback.print_exc()                    # sem a superfície mínima: divisão pelo volume
        return SPL.cut_by_paint(h, R, k, pk, diag), pk
    r, p2 = one(host, rid)
    if len(regs) > 1 and r.get('ok'):
        # várias áreas na mesma marcação (dois olhos): cada uma é cortada com a própria grade, como
        # se fosse um corte só dela; todas saem como peças deste corte
        pieces_k, bodies = [r['piece']], list(r['body_parts'])
        n_ok = 1
        for k in regs[1:]:
            pts = R.cen[R.list[k]['tris']]
            cnt = [int((SPL._on_surface(pts, tri_array(bq)) >= 0).sum()) for bq in bodies]
            hk = int(np.argmax(cnt)) if cnt and max(cnt) > 0 else -1
            if hk < 0:
                continue                             # a área não está em nenhuma parte do corpo: não corta às cegas
            rk, _ = one(bodies[hk], k)
            if rk.get('ok') and rk.get('body_parts'):
                pieces_k.append(rk['piece'])
                bodies = bodies[:hk] + list(rk['body_parts']) + bodies[hk + 1:]
                n_ok += 1
        r = dict(r, piece=E.flat(E.union(pieces_k)) if len(pieces_k) > 1 else pieces_k[0], body_parts=bodies, n_areas=n_ok)
    mc = p2.get('_cutter') is not None
    if cut.get('_de_linhas'):
        checks = [_chk('ok', 'Cortei pela menor superfície que passa pelas linhas desenhadas; a peça para nelas.' if mc else
                       'Cortei pelo volume mais perto do lado da peça.')]
    else:
        checks = [_chk('ok', 'A borda não separava a parte (ela encosta no corpo em uma faixa): ' +
                   ('cortei pela menor superfície que passa pela borda marcada; a peça para na borda e as faces de contato '
                        'seguem a marcação.' if mc else 'cortei pelo volume mais perto da área marcada; as faces de contato seguem a marcação.'))]
    if len(regs) > 1:
        na = r.get('n_areas', 1)
        checks.append(_chk('ok' if na == len(regs) else 'aviso',
                           f'A marcação tem {len(regs)} áreas separadas: ' + (f'cada uma sai como uma peça deste corte.' if na == len(regs)
                           else f'{na} saíram como peça; as outras não se separaram (faça um corte só para elas).')))
    checks += [x for x in r.get('checks', []) if 'pela pintura' not in x['texto']]
    if not r.get('ok'):
        return dict(ok=False, checks=checks)
    piece, body_parts = r['piece'], r['body_parts']
    if enc != 'colar' and body_parts:
        rp = _patch_pin(piece, body_parts, enc, prm, clr, float(prm.get('parede', 1.2)), R, diag, prefer)
        txt = ('no contato junto da linha' if prefer is not None else 'no maior contato') + \
            (f' (há {rp["patches"]} contatos; nos outros a peça fica só colada)' if rp.get('patches', 0) > 1 else '')
        for x in rp['checks']:
            if x['nivel'] == 'ok':
                x['texto'] = f'Pino {txt}: ' + x['texto']
        checks += rp['checks']
        piece, body_parts = rp['piece'], rp['body_parts']
        r['extra'] = r.get('extra', []) + rp.get('extra', [])
        if enc in GIRA:
            checks.append(_chk('aviso', 'A face do corte não é plana (a peça encosta no corpo ao longo da marcação): ao girar, '
                                        'as partes que encostam podem raspar ou travar. Para girar livre, prefira um encaixe fixo '
                                        'ou deixe essas partes em outro corte.'))
    else:
        checks.append(_chk('ok', 'Sem pino: as faces encaixam e é só colar (CA ou epóxi).'))
    return dict(ok=not any(x['nivel'] == 'erro' for x in checks), checks=checks, piece=piece, body_parts=body_parts,
                extra=r.get('extra', []), axis=r['axis'], print_T=r['print_T'], forma='volume', encaixe=enc)


# ----------------------------------------------------------------------------- todos os cortes
NAVALHA_BORDA = _os.environ.get('FLEXI_NAVALHA_BORDA', '1') != '0'


def _razor_defects(lst):
    """Defeitos de malha como o arquivo sai para o fatiador: a exportação passa cada STL por
    SPL._weld_safe (desloca milésimos de mm e separa superfícies que só se tocam numa aresta); conta o
    que sobra depois disso, nada além."""
    n_ = 0
    for m_ in lst:
        T_ = SPL.tri_array(m_)
        if any(SPL.mesh_errors(T_)):
            n_ += sum(v for k_, v in SPL._weld_safe(T_)[2].items() if k_ != 'ok')
    return n_


def _tris_box(m_, lo, hi):
    T_ = tri_array(m_)
    c_ = T_.mean(1)
    return T_[np.all((c_ >= lo) & (c_ <= hi), 1)]


def _razor_skin_ctx(src, ln, T, host, piece, bodies, reach):
    """A pele em volta da linha e de que lado ela tem de ficar. src = (centros dos triângulos do
    modelo, máscara do lado da peça que as linhas definem: _want_mask). Sem a máscara, vale o lado
    que a grade deu, menos junto da linha (é ali que a navalha corrige a grade)."""
    from scipy.spatial import cKDTree
    k = _CUR_K[0]
    pts3 = np.asarray(ln.P, np.float64)            # a linha desenhada, no mundo
    seg = np.vstack([pts3, pts3[:1]])
    dense = np.concatenate([np.linspace(a, b, max(2, int(np.linalg.norm(b - a) / (0.05 * k)) + 1)) for a, b in zip(seg[:-1], seg[1:])])
    kd = cKDTree(dense)
    if src is not None:
        cw, want, tsz = src
        d3, _ = kd.query(cw, distance_upper_bound=reach)
        sel = np.isfinite(d3)
        pts, w, d3 = cw[sel], np.asarray(want)[sel], d3[sel]
        # triângulo que a linha atravessa: a máscara o põe inteiro de um lado, a navalha corta na linha
        # (o centro dele pode ficar do outro lado sem erro nenhum)
        cross = d3 <= tsz[sel] + 0.05 * k
    else:
        Hc = tri_array(host).mean(1)
        d3, _ = kd.query(Hc, distance_upper_bound=reach)
        sel = np.isfinite(d3)
        pts, w, d3 = Hc[sel], None, d3[sel]
        cross = np.zeros(len(pts), bool)
    if not len(pts):
        return None
    lo, hi = pts.min(0) - 2.0 * k, pts.max(0) + 2.0 * k
    on = _on_surface(pts, _tris_box(host, lo, hi), tol=0.05 * k) >= 0
    pts, d3, cross = pts[on], d3[on], cross[on]
    w = w[on] if w is not None else None
    if not len(pts):
        return None
    onp0 = _on_surface(pts, _tris_box(piece, lo, hi), tol=0.05 * k) >= 0
    Tb = [_tris_box(b_, lo, hi) for b_ in bodies]
    Tb = np.concatenate([t_ for t_ in Tb if len(t_)]) if any(len(t_) for t_ in Tb) else np.zeros((0, 3, 3))
    onb0 = _on_surface(pts, Tb, tol=0.05 * k) >= 0
    exempt = cross
    if w is None:
        w, exempt = onp0.copy(), d3 < 0.7 * k
    lat = SPL._apply(pts, _inv(T))[:, :2]
    return dict(pts=pts, w=w, onp0=onp0, onb0=onb0, lat=lat, lo=lo, hi=hi, exempt=exempt, d3=d3)


def _razor_skin_bad(ctx, piece2, rest):
    """Pontos da pele (no plano da lâmina) que a navalha mandaria para o lado errado."""
    if ctx is None:
        return None
    k = _CUR_K[0]
    pts, lo, hi = ctx['pts'], ctx['lo'], ctx['hi']
    onp1 = _on_surface(pts, _tris_box(piece2, lo, hi), tol=0.05 * k) >= 0
    Tb = [_tris_box(b_, lo, hi) for b_ in rest]
    Tb = np.concatenate([t_ for t_ in Tb if len(t_)]) if any(len(t_) for t_ in Tb) else np.zeros((0, 3, 3))
    onb1 = _on_surface(pts, Tb, tol=0.05 * k) >= 0
    w = ctx['w']
    bad = (w & onb1 & ~ctx['onb0']) | (~w & onp1 & ~ctx['onp0'])
    bad &= ~ctx['exempt']
    ctx['_bad_d3'] = ctx['d3'][bad]
    ctx['_bad_lat'] = ctx['lat'][bad]
    return ctx['pts'][bad]


def _razor_orphans(piece2, rest, piece, bodies, p_add, b_add):
    """A faixa da navalha corta tudo o que passa por ela pela lâmina. Dois tipos de pedaço solto:
    - material que a faixa trouxe (p_add, b_add) e ficou do lado errado da lâmina (mecha que atravessa
      a faixa): volta para o lado em que ele encosta;
    - material que já era daquele lado e a faixa desligou do resto (cortou a ponte): não troca de lado
      (a pele dele é de lá). Volta a lista dos pontos desses pedaços para a faixa sair dali.
    Devolve (piece2, rest, pontos dos pedaços desligados)."""
    def split_extra(m_, n0):
        ps = sorted(E.parts(m_, 0.0), key=lambda q: -q.volume())
        return ps[:max(n0, 1)], ps[max(n0, 1):]
    def touches(c_, m_):
        try:
            return (not m_.is_empty()) and _vol(E.flat(c_ ^ m_)) > 1e-6
        except Exception:
            return False
    def novo(c_, add_):                                # quanto do pedaço veio da faixa
        try:
            return _vol(E.flat(c_ ^ add_)) / max(_vol(c_), 1e-9)
        except Exception:
            return 0.0
    def pts(c_):
        q = np.asarray(c_.to_mesh().vert_properties)[:, :3]
        return q[:: max(1, len(q) // 400)]
    cut_off = []
    n_p = len(E.parts(piece, 0.3))
    n_b = [len(E.parts(b_, 0.3)) for b_ in bodies]
    keep, extra = split_extra(piece2, n_p)
    if extra:
        left = []
        for c_ in extra:
            j_ = next((j for j, b_ in enumerate(rest) if touches(c_, b_)), -1) if novo(c_, p_add) > 0.5 else -1
            if j_ >= 0:
                rest[j_] = E.flat(rest[j_] + c_)
            else:
                left.append(c_)
                if c_.volume() >= 0.05:
                    cut_off.append(pts(c_))
        piece2 = E.flat(E.union(keep + left))
    for j, b_ in enumerate(list(rest)):
        keep, extra = split_extra(b_, n_b[j] if j < len(n_b) else 1)
        if not extra:
            continue
        left = []
        for c_ in extra:
            if novo(c_, b_add) > 0.5 and touches(c_, piece2):
                piece2 = E.flat(piece2 + c_)
            else:
                left.append(c_)
                if c_.volume() >= 0.05:
                    cut_off.append(pts(c_))
        rest[j] = E.flat(E.union(keep + left))
    return piece2, rest, (np.concatenate(cut_off) if cut_off else np.zeros((0, 3)))


def _razor_band(r, host, loops, cut, diag, centro, sock=False, skin_src=None):
    """Borda de navalha num corte feito pela grade de voxels (_mincut_cutter): a face que a grade acha
    é serrilhada no tamanho da grade (0,3 a 0,7 mm) e a borda na pele desvia da linha desenhada. Numa
    faixa estreita em volta de cada linha que dá a volta numa parte (pescoço, pulso), a peça e o corpo
    passam a ser separados pela lâmina lisa que passa pela linha (a mesma do corte simples): a borda na
    pele fica sobre a linha e a face junto dela fica lisa. Mais para dentro continua o que a grade
    achou (é ela que resolve o cabelo por cima da nuca e o queixo encostado na gola). Com soquete, a
    faixa vai da pele até a parede do soquete: dali para dentro o soquete refaz tudo (cavidade e pino),
    também pela lâmina. Se a troca mexer em mais do que a faixa (outra parte entrou nela), fica como
    estava."""
    k = _CUR_K[0]
    gap = float(np.clip(float(cut.get('folga') or 0.2), 0.05, 2.0))
    piece, bodies = r['piece'], list(r['body_parts'])
    if piece is None or not bodies:
        return r, 0
    m_out, hb = 1.0 * k, 2.5 * k
    wall = float(cut.get('parede', 1.2 * k) or 1.2 * k)
    wall_s = max(wall, 2.0 * k) if cut.get('anel_plano') else wall
    m_in = (wall_s + gap + 0.3 * k) if sock else 3.0 * k
    done = 0
    for L in loops:
        L = np.asarray(L, np.float64)
        if len(L) < 6:
            continue
        try:
            lp = Line(L, 'plano', gap, diag, centro)
            cs0 = mf.CrossSection([lp.Q2.tolist()], mf.FillRule.NonZero)
            if cs0.is_empty() or cs0.area() < 0.5:
                continue
            hull = cs0.hull()
            hp = np.asarray(hull.to_polygons()[0], np.float64)
            per = float(np.linalg.norm(np.diff(np.vstack([hp, hp[:1]]), axis=0), axis=1).sum())
            if 4 * np.pi * hull.area() / max(per * per, 1e-9) < SOQUETE_COMPACTO:
                continue                               # contorno de parte deitada (trança no peito): fica a grade
            ln = Line(L, 'curva', gap, diag, centro)
        except Exception:
            continue
        pp = _who([piece], ln.probes(+1))[0]
        pm = _who([piece], ln.probes(-1))[0]
        if pm > pp:
            ln.flip()
            pp, pm = pm, pp
        if pp < 0.6 * max(1, len(ln.probes(+1))):
            continue                                   # a lâmina não separa a peça aqui: fica a grade
        cs = mf.CrossSection([ln.Q2.tolist()], mf.FillRule.NonZero)
        dl = 0.03 * k                                  # sobreposição mínima: nenhuma face de um sólido coincide com a de outro
        def ring(a, b_):
            o_ = cs.offset(a, mf.JoinType.Round, 2.0, 32)
            i_ = cs.offset(-b_, mf.JoinType.Round, 2.0, 32)
            return o_ - i_ if not i_.is_empty() else o_
        A = ring(m_out, m_in)                          # faixa: de m_out fora da linha a m_in dentro
        T = _T(ln.Fr, ln.c)
        per_l = float(np.linalg.norm(np.diff(np.vstack([ln.Q2, ln.Q2[:1]]), axis=0), axis=1).sum())
        lim = per_l * (m_out + m_in) * 1.5 * k
        skin = _razor_skin_ctx(skin_src, ln, T, host, piece, bodies, m_out + m_in + 1.5 * k)

        def attempt(A_):
            """A peça e o corpo com a faixa A_ pela lâmina (None se não der)."""
            Ab_ = A_.offset(dl, mf.JoinType.Round, 2.0, 32)              # a mesma, um pouco maior
            bb = Ab_.bounds()
            ext = max(bb[2] - bb[0], bb[3] - bb[1])
            st = float(np.clip(ext / 140.0, 0.12 * k, 0.4 * k))
            tx = np.arange(bb[0] - st, bb[2] + 2 * st, st)
            ty = np.arange(bb[1] - st, bb[3] + 2 * st, st)
            X, Y = np.meshgrid(tx, ty, indexing='ij')
            H = ln.hf(np.stack([X.ravel(), Y.ravel()], 1)).reshape(X.shape)
            zs = float(np.abs(H).max()) + hb + 2.0

            def slab_(cs_, z0, z1):                    # sólido sobre cs_ entre H+z0 e H+z1 (no mundo)
                pr = mf.Manifold.extrude(cs_, 2 * zs).translate([0.0, 0.0, -zs])
                return E.X(E.flat(_heightbox(tx, ty, H + (z0 + z1) / 2, z1 - z0) ^ pr), T)
            p_rem = slab_(A_, -hb, gap / 2 + dl)       # a peça perde a faixa até logo acima da folga
            p_add = E.flat(host ^ slab_(Ab_, gap / 2, hb + dl))     # e ganha o que o modelo tem acima da lâmina
            b_rem = slab_(A_, -gap / 2 - dl, hb)       # o corpo perde a faixa a partir de logo abaixo da folga
            b_add = E.flat(host ^ slab_(Ab_, -hb - dl, -gap / 2))   # e ganha o que o modelo tem abaixo da lâmina
            if p_rem.is_empty():
                return None
            # quanto troca de lado: só a vizinhança da linha (a grade desvia da linha pouco mais que a grade)
            moved = _vol(E.flat(E.union(bodies) ^ p_add)) + _vol(E.flat(piece ^ b_add))
            if moved > lim:
                if _DBG:
                    print(f'navalha na borda: troca grande demais ({moved:.1f} > {lim:.1f} mm³), fica a grade', flush=True)
                return None
            piece2 = E.flat((piece - p_rem) + p_add)
            rest = [E.flat(b_ - b_rem) for b_ in bodies]
            if len(bodies) == 1:
                rest[0] = E.flat(rest[0] + b_add)
            elif not b_add.is_empty():
                # cada pedaço de baixo da lâmina vai para a parte do corpo mais perto dele
                from scipy.spatial import cKDTree
                bt = [cKDTree(np.asarray(b_.to_mesh().vert_properties)[:, :3]) for b_ in bodies]
                groups = [[] for _ in bodies]
                for c_ in b_add.decompose():
                    q = np.asarray(c_.to_mesh().vert_properties)[:, :3]
                    if not len(q):
                        continue
                    q = q[:: max(1, len(q) // 200)]
                    j_ = int(np.argmin([float(np.median(t_.query(q)[0])) for t_ in bt]))
                    groups[j_].append(c_)
                for j_, g in enumerate(groups):
                    if g:
                        rest[j_] = E.flat(E.union([rest[j_]] + g))
            if _DBG:
                print(f'navalha na borda: linha com {len(ln.Q2)} pontos, troca {moved:.2f} mm³ (limite {lim:.1f}), '
                      f'{len(bodies)} parte(s) do corpo', flush=True)
            piece2, rest, cut_off = _razor_orphans(piece2, rest, piece, bodies, p_add, b_add)
            return piece2, [b_ for b_ in rest if not b_.is_empty()], cut_off

        # a pele de cada lado da linha tem de ficar inteira do lado certo: a lâmina lisa continua além da
        # linha e pode atravessar a pele de novo (mecha encostada, dobra da roupa), abrindo uma fenda que
        # ninguém desenhou. Onde isso acontece a faixa sai dali (disco no plano da lâmina) e fica a grade.
        # a pele de cada lado da linha tem de ficar inteira do lado certo. A lâmina lisa continua além da
        # linha e pode atravessar a pele de novo (mecha encostada, dobra da roupa, a borda da faixa cruzando
        # a pele): isso abriria uma fenda que ninguém desenhou. A navalha só fica onde sai perfeita; senão,
        # aquela linha fica com a grade (que só cruza a pele na linha).
        try:
            res = attempt(A)
        except Exception:
            traceback.print_exc()
            res = None
        A_cur = A
        for rodada in range(4 if _NAVALHA_LOCAL else 1):
            if res is None:
                break
            bad = _razor_skin_bad(skin, res[0], res[1])
            nb = (0 if bad is None else len(bad)) + len(res[2])
            if not nb:
                break
            if _DBG:
                print(f'navalha na borda: {nb} ponto(s) de pele iriam para o lado errado, fica a grade', flush=True)
            lats = []
            if bad is not None and len(bad):
                lats.append(np.asarray(skin['_bad_lat'], np.float64))
            if len(res[2]):
                lats.append(SPL._apply(np.asarray(res[2], np.float64), _inv(T))[:, :2])
            res = None
            if not _NAVALHA_LOCAL or not lats or rodada == 3:
                break
            # a faixa sai só de perto dos pontos errados e dos pedaços soltos (disco no plano da lâmina): no
            # resto da linha a borda fica na linha desenhada, ali fica a grade
            lat = np.concatenate(lats)
            rr = float(m_out + m_in + 1.5 * k)
            q = np.unique(np.round(lat / (0.5 * rr)), axis=0) * (0.5 * rr)
            holes = mf.CrossSection.batch_boolean([mf.CrossSection.circle(rr, 24).translate([float(x), float(y)]) for x, y in q],
                                                 mf.OpType.Add)
            A_cur = A_cur - holes
            if A_cur.is_empty() or A_cur.area() < 0.2 * A.area():
                break
            try:
                res = attempt(A_cur)
            except Exception:
                traceback.print_exc()
                res = None
        if res is None:
            continue
        piece2, rest = res[0], res[1]
        # só fica se não piorar nada: a peça não parte, o corpo continua no mesmo número de partes e a
        # malha das duas sai fechada e sem aresta com 3 faces (como o fatiador lê o arquivo)
        if len(E.parts(piece2, 0.3)) != len(E.parts(piece, 0.3)) or \
                sum(len(E.parts(b_, 0.3)) for b_ in rest) != sum(len(E.parts(b_, 0.3)) for b_ in bodies):
            if _DBG:
                print('navalha na borda: mudou o número de partes, fica a grade', flush=True)
            continue
        if _razor_defects([piece2] + rest) > _razor_defects([piece] + bodies):
            if _DBG:
                print('navalha na borda: malha com defeito, fica a grade', flush=True)
            continue
        piece, bodies = piece2, rest
        done += 1
    if done:
        r = dict(r, piece=piece, body_parts=[b_ for b_ in bodies if not b_.is_empty()])
    return r, done


# ------------------------------------------------------------------ pele exata na borda (1.47)
# O corte pela grade de voxels corta em diagonal o canto côncavo onde uma parte encontra a outra (a mecha e
# a testa) e deixa a borda na pele 0,5 a 1,5 mm para dentro da linha: a faixa de testa lisa na borda da
# mecha. Depois desse corte, a pele de dentro da linha que ficou no corpo, a até 1,5 mm dela, volta para a
# peça pela bissetriz entre a pele da peça e a do corpo (_recut_by_surface com 'perto': grade de 0,2 mm num
# tubo de 3,5 mm em volta da linha). A bissetriz do canto chega no vinco. FLEXI_PELE_EXATA=0 desliga.
_PELE_EXATA = _os.environ.get('FLEXI_PELE_EXATA', '0') == '1'
# aba fina na borda do corte (a lâmina na cintura da calça, a aba no topo do pescoço): o que é mais fino que
# 2 x _LASCA_R junto das faces do corte passa para a peça do lado. 0,4 até a 1.47 (0,8 mm); em teste: 0,6
_LASCA_R = float(_os.environ.get('FLEXI_LASCA_R', '0.4'))
_ABA_ESCONDIDA = _os.environ.get('FLEXI_ABA_ESCONDIDA', '0') == '1'      # em teste
_ABA_PLANO = _os.environ.get('FLEXI_ABA_PLANO', '0') == '1'      # em teste: o plano automático não pode deixar aba


def _pele_fora(r, host, S, loops, topo, diag, centro):
    """Superfície do modelo de fora da linha (a mais de 0,6 mm dela) que foi com a peça, em mm²."""
    from scipy.spatial import cKDTree
    fm = mask_from_lines(S, loops, topo, diag, centro, False)
    if fm is None or not fm[0].any():
        return 0.0
    T = tri_array(S)
    allc = T.mean(1)
    arT = np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1) / 2
    pb = np.array(r['piece'].bounding_box())
    near = np.where(np.all((allc >= pb[:3] - 1.0) & (allc <= pb[3:] + 1.0), 1))[0]
    on_p = np.zeros(len(T), bool)
    on_p[near] = _on_surface(allc[near], tri_array(r['piece']), tol=0.05) >= 0
    side = fm[0]
    if arT[side & on_p].sum() < arT[~side & on_p].sum():
        side = ~side
    dl, _ = cKDTree(np.concatenate(loops)).query(allc, distance_upper_bound=0.6 * _CUR_K[0])
    far = ~np.isfinite(dl)
    return float(arT[~side & on_p & far].sum())


def _aba_vol(r, loops, rr=0.6, perto=3.0):
    """Volume de partes finas (menos de 2 x rr mm) das peças junto da linha: as abas que o corte deixou."""
    from scipy.ndimage import distance_transform_edt
    k = _CUR_K[0]
    P = np.concatenate([np.asarray(L, np.float64) for L in loops])
    lo, hi = P.min(0) - perto * k - 1.0, P.max(0) + perto * k + 1.0
    step = float(max(0.15 * k, (np.prod(hi - lo) / 4.0e6) ** (1 / 3)))
    xs, ys, zs = [lo[i] + step * np.arange(int(np.ceil((hi[i] - lo[i]) / step)) + 1) for i in range(3)]
    n = (len(xs), len(ys), len(zs))
    lg = np.ones(n, bool)
    seg = np.vstack([np.linspace(a_, b_, max(2, int(np.linalg.norm(b_ - a_) / (0.5 * step)) + 1))
                     for L in loops for a_, b_ in zip(np.asarray(L), np.roll(np.asarray(L), -1, 0))])
    ijk = np.round((seg - lo) / step).astype(int)
    ok = np.all((ijk >= 0) & (ijk < np.array(n)), 1)
    lg[tuple(ijk[ok].T)] = False
    near = distance_transform_edt(lg, sampling=step) <= perto * k
    boxm = mf.Manifold.cube(list(hi - lo + 2 * step)).translate(list(lo - step))
    tot = 0.0
    for m_ in [r['piece']] + list(r['body_parts']):
        bb = np.array(m_.bounding_box())
        if np.any(bb[3:] < lo) or np.any(bb[:3] > hi):
            continue
        c_ = E.flat(m_ ^ boxm)
        if c_.is_empty():
            continue
        v = _voxelize(c_, xs, ys, zs)
        core = distance_transform_edt(v, sampling=step) > rr * k
        op = distance_transform_edt(~core, sampling=step) <= rr * k + 0.5 * step
        tot += float((v & ~op & near).sum()) * step ** 3
    return tot


def _host_by_lines(pieces, loops):
    """A parte em que as linhas estão: a mais perto dos pontos desenhados."""
    pts = np.concatenate(loops)
    best, bd = -1, np.inf
    for k, p in enumerate(pieces):
        from scipy.spatial import cKDTree
        d, _ = cKDTree(p['T'].reshape(-1, 3)).query(pts[:: max(1, len(pts) // 60)])
        md = float(np.median(d))
        if md < bd:
            best, bd = k, md
    return best, bd


def _seam_share(pieces, hk, loops, gap):
    """Quanto da linha está na costura entre a peça hk e outra peça já separada (0 a 1)."""
    from scipy.spatial import cKDTree
    pts = np.concatenate(loops)
    pts = pts[:: max(1, len(pts) // 200)]
    lo, hi = pts.min(0) - 4.0, pts.max(0) + 4.0
    tol = gap + 0.6 * _CUR_K[0]

    def near(p):
        V = p['T'].reshape(-1, 3)
        V = V[np.all((V >= lo) & (V <= hi), 1)]
        if len(V) < 3:
            return None
        Tm = p['T'][np.all((p['T'].mean(1) >= lo) & (p['T'].mean(1) <= hi), 1)]
        if len(Tm):
            V = np.concatenate([V, Tm.mean(1), (Tm[:, 0] + Tm[:, 1]) / 2, (Tm[:, 1] + Tm[:, 2]) / 2, (Tm[:, 0] + Tm[:, 2]) / 2])
        d, _ = cKDTree(V).query(pts)
        return d <= tol
    nh = near(pieces[hk])
    if nh is None or nh.mean() < 0.8:
        return 0.0, None
    best, who = 0.0, None
    for k, p in enumerate(pieces):
        if k == hk or p.get('tipo') == 'cavilha':
            continue
        pb = np.array(p['mesh'].bounding_box())
        if np.any(pb[3:] < lo) or np.any(pb[:3] > hi):
            continue
        no = near(p)
        if no is None:
            continue
        sh = float((nh & no).mean())
        if sh > best:
            best, who = sh, p['nome']
    return best, who


def _paint_from(host_T, host_paint, M, base):
    T = tri_array(M)
    on = _on_surface(T.mean(1), host_T)
    col = np.full(len(T), base, np.uint8)
    hit = on >= 0
    col[hit] = np.asarray(host_paint, np.uint8)[on[hit]]
    return T, col


def _separate_loops(cut):
    """Linhas de áreas separadas no mesmo corte (dois olhos, duas sobrancelhas): cada linha longe das
    outras. Devolve as linhas, ou None quando elas formam uma parte só (cabelo pela frente e por trás
    também ficam longe uma da outra: por isso o resultado de cada uma ainda é conferido)."""
    if cut.get('plano') or cut.get('mascara'):
        return None
    loops = [L for L in (_clean_loop(x) for x in (cut.get('linhas') or [])) if L is not None]
    if len(loops) < 2:
        return None
    m = 0.4 * _CUR_K[0]
    bx = [(np.asarray(L).min(0) - m, np.asarray(L).max(0) + m) for L in loops]
    for a in range(len(bx)):
        for b in range(a + 1, len(bx)):
            if np.all(bx[a][1] >= bx[b][0]) and np.all(bx[b][1] >= bx[a][0]):
                return None
    return [list(map(list, np.asarray(x, np.float64))) for x in (cut.get('linhas') or [])]


_HOST_TOPO = [False]


def _piece_at(pieces, ponto, linhas=None):
    """A peça que contém o ponto (um ponto logo abaixo da superfície onde a peça foi escolhida); se
    nenhuma contém, a mais perto dele (até 1 mm). Com as linhas do corte: se a pele da peça achada fica longe
    da linha e a de outra peça passa por ela, vale a outra (1.55: o soquete de um corte anterior pode passar
    logo abaixo da pele onde o ponto foi guardado, e a orelha caía no rosto em vez da cabeça)."""
    from scipy.spatial import cKDTree
    p = np.asarray(ponto, np.float64)
    k = _CUR_K[0]
    for j, pc in enumerate(pieces):
        if pc.get('tipo') == 'cavilha':
            continue
        b = np.array(pc['mesh'].bounding_box())
        if np.all(p >= b[:3] - 0.5) and np.all(p <= b[3:] + 0.5) and E.contains_point(pc['mesh'], p, 0.1 * k):
            if linhas:
                return _piece_pela_linha(pieces, j, linhas, k)
            return j
    best, bd = -1, 1.0 * k
    for j, pc in enumerate(pieces):
        if pc.get('tipo') == 'cavilha':
            continue
        d = float(cKDTree(np.asarray(pc['T']).mean(1)).query(p)[0])
        if d < bd:
            best, bd = j, d
    return best


def _piece_pela_linha(pieces, j, linhas, k):
    """Confere a peça j pela linha: distância mediana da linha à pele de cada peça (vértices da malha). Fica j
    se a linha passa por ela (até 1 mm) ou se nenhuma outra fica claramente mais perto."""
    from scipy.spatial import cKDTree
    L = np.vstack([np.asarray(x, np.float64) for x in linhas if len(x)])
    if not len(L):
        return j
    lo, hi = L.min(0) - 2.0, L.max(0) + 2.0

    def med(pc):
        b = np.array(pc['mesh'].bounding_box())
        if np.any(b[3:] < lo) or np.any(b[:3] > hi):
            return np.inf
        V = np.asarray(pc['mesh'].to_mesh().vert_properties)[:, :3]
        return float(np.median(cKDTree(V).query(L)[0]))
    dj = med(pieces[j])
    if dj <= 1.0 * k:
        return j
    outras = [(med(pc), t) for t, pc in enumerate(pieces) if t != j and pc.get('tipo') != 'cavilha']
    if not outras:
        return j
    d2, t2 = min(outras)
    return t2 if d2 <= 0.5 * dj and d2 <= 1.0 * k else j


def _apply_on_piece(cur, cut, i, S):
    """Corte livre numa peça escolhida: a malha da peça faz o papel do modelo (superfície, lados da linha,
    pele de fora para o soquete)."""
    nome = cut.get('nome') or f'Corte {i + 1}'
    hk = _piece_at(cur['pieces'], cut['peca'].get('ponto') or [0, 0, 0], [L for L in (cut.get('linhas') or []) if len(L) >= 3])
    if hk < 0:
        o = dict(cur)
        o['livres'] = [dict(i=i, nome=nome, ok=False, checks=[_chk('erro', 'A peça deste corte não existe mais (um corte anterior mudou?). '
                                                                         'Escolha a peça de novo e redesenhe a linha.')])]
        return o
    host = cur['pieces'][hk]
    c2 = {k_: v for k_, v in cut.items() if k_ != 'peca'}
    c2['_host_k'] = hk
    pre = []
    if c2.get('mascara'):
        # a área marcada é uma lista de triângulos da malha da peça que a tela recebeu (host_piece):
        # se a peça mudou (um corte anterior foi editado), a lista não serve mais
        if int(c2.get('n') or 0) != int(host['mesh'].num_tri()):
            c2.pop('mascara', None)
            c2.pop('n', None)
            if not [L for L in (c2.get('linhas') or []) if len(L) >= 3]:
                o = dict(cur)
                o['livres'] = [dict(i=i, nome=nome, ok=False, checks=[_chk('erro', 'A peça deste corte mudou depois da marcação (um corte '
                                                                                 'anterior foi editado): a área marcada não serve mais. '
                                                                                 'Edite a marcação de novo.')])]
                return o
            pre.append(_chk('aviso', 'A peça deste corte mudou depois da marcação (um corte anterior foi editado): a área marcada '
                                     'ficou de fora e o corte usou só as linhas. Edite a marcação para marcar de novo.'))
    o = _apply_core(cur, [c2], host['mesh'], None)
    r = o['livres'][0]
    if r.get('ok'):
        r['checks'] = [_chk('ok', f'Corte na peça "{host.get("nome")}": a marcação e os lados dela foram achados na própria peça, '
                                  'inclusive nas faces de corte.')] + pre + r.get('checks', [])
    elif pre:
        r['checks'] = pre + r.get('checks', [])
    return o


def _new_vol(o):
    return sum(_vol(p['mesh']) for p in o['pieces'] if p.get('_novo') and p.get('tipo') != 'cavilha')


def _cut_failed(o, cur):
    """O corte não separou uma peça de verdade: falhou ou só tirou lascas."""
    r = o['livres'][0]
    tot = sum(_vol(p['mesh']) for p in cur['pieces'])
    return (not r.get('ok')) or _new_vol(o) < max(2.0 * _CUR_K[0] ** 3, 0.002 * tot)


def _cut_better(o3, o2, cur):
    """O corte refeito só na peça é melhor: separou uma peça de verdade e o resto não se partiu."""
    if not o3['livres'][0].get('ok') or _cut_failed(o3, cur):
        return False
    resto3 = [p for p in o3['pieces'] if not p.get('_novo')]
    return len(resto3) <= len(cur['pieces']) and _new_vol(o3) > 10.0 * max(_new_vol(o2), 1e-9)


def _pele_ligado(cut):
    """Corte pela pele (1.48 beta): ligado por padrão; o corte pode pedir o motor anterior."""
    if cut.get('motor_antigo'):
        return False
    try:
        import pelecut as PC
        return PC.LIGADO and PC.DISPONIVEL
    except Exception:
        return False


# ---------------------------------------------------------------- cascata de cortes (regra A do Roberto, 06/11/2026)
# Um corte desenhado na peça que outro corte gerou depende dele (o nome da peça é o do corte, ou o do corte e um
# número: "Corte 13 (2)"). O pai roda sempre antes dos dependentes; se o pai não sai, os dependentes não rodam.
def depende(filho, pai):
    """O corte `filho` foi desenhado numa peça que o corte de nome `pai` gerou."""
    pn = str(((filho.get('peca') or {}).get('nome')) or '').strip()
    pai = str(pai or '').strip()
    if not pn or not pai:
        return False
    if pn == pai:
        return True
    return pn.startswith(pai + ' ') and all(ch in '()0123456789 ' for ch in pn[len(pai) + 1:])


def dependentes(nome, cuts):
    """Todos os cortes que dependem do corte `nome`, direta ou indiretamente, na ordem da lista."""
    fila, achados = [nome], []
    while fila:
        n = fila.pop()
        for c in cuts:
            cn = c.get('nome')
            if cn and cn != nome and cn not in achados and depende(c, n):
                achados.append(cn)
                fila.append(cn)
    return [c.get('nome') for c in cuts if c.get('nome') in achados]


def _pai_de(cuts, i):
    """Índice do corte pai do corte i (ou None)."""
    for j, c in enumerate(cuts):
        if j != i and c.get('nome') and depende(cuts[i], c['nome']):
            return j
    return None


def _ordem_dep(cuts, perm):
    """A ordem dada com o pai sempre antes dos dependentes (os outros ficam na mesma ordem)."""
    feitos, saida = set(), []

    def poe(i, pilha):
        if i in feitos or i in pilha:
            return
        p = _pai_de(cuts, i)
        if p is not None:
            poe(p, pilha | {i})
        feitos.add(i)
        saida.append(i)
    for i in perm:
        poe(i, frozenset())
    return saida


def _pai_nao_saiu(cuts, i, res):
    """Nome do corte pai do corte i quando ele não saiu (falhou ou também foi pulado); senão None."""
    j = _pai_de(cuts, i)
    if j is None:
        return None
    nome = cuts[j].get('nome')
    for r in res:
        if r.get('nome') == nome or (r.get('i') == j and not r.get('nome')):
            return None if r.get('ok') else nome
    return None


def _apply_cuts(out, cuts, S, progress=None):
    """Aplica os cortes um a um. Um corte com várias áreas separadas (os dois olhos) é feito como
    vários cortes de uma linha, que dão o mesmo resultado de cortar cada área sozinha; se alguma
    delas não separar uma peça pequena sozinha (as linhas eram de uma parte só), o corte é refeito
    com todas as linhas juntas, como antes."""
    cur = dict(out)
    res = []
    if _CONF_PELE:
        _MODEL_T[0] = tri_array(S)                   # a pele de verdade (as faces de corte de antes não são pele)
    pend = None                                      # corte que caiu no motor anterior: avisa no resultado dele
    for i, cut in enumerate(cuts):
        if pend is not None and pend[0] < len(res):
            res[pend[0]]['checks'] = res[pend[0]].get('checks', []) + [_chk('aviso', f'Feito pelo motor anterior: {pend[1]}.')]
        pend = None
        if progress:
            progress(f'corte {i + 1} de {len(cuts)}')
        pai_fora = _pai_nao_saiu(cuts, i, res) if cut.get('peca') else None
        if pai_fora:
            # o corte foi desenhado na peça de um corte que não saiu: sem a peça, ele não roda (regra A)
            res.append(dict(i=i, nome=cut.get('nome') or f'Corte {i + 1}', ok=False,
                            checks=[_chk('erro', f'Não rodou: este corte foi desenhado na peça do {pai_fora}, que não saiu. '
                                                 f'Resolva o {pai_fora} primeiro.')]))
            continue
        if cut.get('peca') or (cut.get('plano') and (i == 0 or not cuts[i - 1].get('plano'))):
            _snap(i, cur)
        if cut.get('_outras_linhas') is None:
            # as linhas dos outros cortes vão junto: cada corte é feito sozinho (_apply_core com uma lista
            # de um corte) e o soquete precisa saber onde passa a linha vizinha (pescoço curto)
            cut = dict(cut, _outras_linhas=[np.asarray(L['p'] if isinstance(L, dict) else L, np.float64)
                                             for j_, c_ in enumerate(cuts) if j_ != i for L in (c_.get('linhas') or [])
                                             if len(L['p'] if isinstance(L, dict) else L) >= 3])
        # 1.53 beta: forma "Tampão" (paredes retas, o motor do corte por cor). Só quando o usuário escolhe; se não
        # cabe num tampão, o corte não sai e o motivo aparece (nenhum outro motor faz no lugar).
        if cut.get('forma') == 'tampao' and not cut.get('plano'):
            import tampaocut as TC
            bb_ = S.bounding_box()
            diag_ = float(np.linalg.norm(np.array(bb_[3:]) - np.array(bb_[:3])))
            try:
                cur, r = TC.cortar(cur, cut, i, S, diag_, sys.modules[__name__])
            except Exception as ex:
                traceback.print_exc()
                r = dict(i=i, nome=cut.get('nome') or f'Corte {i + 1}', ok=False, forma='tampao',
                         checks=[_chk('erro', f'O tampão falhou neste corte: {ex}')])
            res.append(r)
            continue
        # 1.48 beta: corte pela pele (a forma de fora não muda). Se não der, segue o motor anterior.
        motivo_antigo = None
        if _pele_ligado(cut):
            try:
                import pelecut as PC
                bb_ = S.bounding_box()
                diag_ = float(np.linalg.norm(np.array(bb_[3:]) - np.array(bb_[:3])))
                outras_pc = [np.asarray(L, np.float64) for j_, c_ in enumerate(cuts) if j_ != i
                             for L in (c_.get('linhas') or []) if len(L) >= 3]
                o2, r = PC.cortar(cur, dict(cut, _outras_linhas=outras_pc), i, S, diag_, np.asarray(E.centroid(S), np.float64),
                                  sys.modules[__name__])
            except Exception as ex:
                traceback.print_exc()
                o2, r = None, f'erro: {ex}'
            if o2 is not None:
                res.append(r)
                cur = o2
                continue
            motivo_antigo = r
            pend = (len(res), r)
        if cut.get('peca'):
            # corte numa peça já recortada (o pescoço depois do cabelo): a linha foi desenhada na malha da
            # peça, inclusive nas faces de corte. Os lados da linha e a pele vêm dessa malha, não do
            # modelo original. Só corte marcado assim passa por aqui; os outros seguem como sempre.
            outras_ = [np.asarray(L, np.float64) for j_, c_ in enumerate(cuts) if j_ != i
                       for L in (c_.get('linhas') or []) if len(L) >= 3]
            o2 = _apply_on_piece(cur, dict(cut, _outras_linhas=outras_), i, S)
            for p in o2['pieces']:
                if p.pop('_novo', False):
                    p['livre'] = i
            r = o2['livres'][0]
            r['i'] = i
            res.append(r)
            cur = o2
            continue
        sep = _separate_loops(cut)
        done = None
        if sep:
            try:
                tr = dict(cur)
                parts_res = []
                ok = True
                for j, L in enumerate(sep):
                    vol0 = {id(p['mesh']): _vol(p['mesh']) for p in tr['pieces']}
                    tr = _apply_core(tr, [dict(cut, linhas=[L])], S, None)
                    r = tr['livres'][0]
                    news_all = [p for p in tr['pieces'] if p.pop('_novo', False)]
                    for p in news_all:
                        p['livre'] = i
                    news = [p for p in news_all if p.get('tipo') != 'cavilha']
                    host_v = max(vol0.values()) if vol0 else 1.0
                    if not r.get('ok') or not news or any(_vol(p['mesh']) > 0.35 * host_v for p in news):
                        ok = False
                        break
                    for p in news:
                        p['_sub'] = j
                    parts_res.append(r)
                if ok:
                    # as áreas precisam ser peças separadas de verdade: se uma peça encosta na outra (a
                    # linha do pulso e a de um dedo apoiado na perna cercam a mesma mão), é uma parte só
                    from scipy.spatial import cKDTree
                    subs = [p for p in tr['pieces'] if '_sub' in p]
                    lim = 2.0 * float(cut.get('folga') or 0.2) + 0.3 * _CUR_K[0]
                    pts = [np.asarray(p['mesh'].to_mesh().vert_properties)[:, :3] for p in subs]
                    for a_ in range(len(subs)):
                        for b_ in range(a_ + 1, len(subs)):
                            if subs[a_]['_sub'] != subs[b_]['_sub'] and float(cKDTree(pts[a_]).query(pts[b_], k=1)[0].min()) < lim:
                                ok = False
                    if not ok:
                        for p in subs:
                            p.pop('_sub', None)
                if ok:
                    done = (tr, parts_res)
            except Exception:
                traceback.print_exc()
                done = None
        if done:
            tr, parts_res = done
            mine = [p for p in tr['pieces'] if '_sub' in p]
            for k, p in enumerate(mine):
                p['livre'] = i
                p['nome'] = f"{cut.get('nome') or f'Corte {i + 1}'} ({k + 1})"
                p.pop('_sub', None)
            seen, checks = set(), [_chk('ok', f'{len(sep)} áreas separadas neste corte: cada uma foi cortada sozinha e sai como uma peça.')]
            for r in parts_res:
                for x in r.get('checks', []):
                    if x['texto'] not in seen:
                        seen.add(x['texto'])
                        checks.append(x)
            r0 = dict(parts_res[0], i=i, nome=cut.get('nome') or f'Corte {i + 1}', checks=checks, ok=True)
            for r in parts_res[1:]:
                if r.get('sem_pino'):
                    r0['sem_pino'] = True
            cur = tr
            res.append(r0)
            continue
        o2 = _apply_core(cur, [cut], S, None)
        if len(cur['pieces']) > 1 and _cut_failed(o2, cur):
            # corte em sequência que não separou nada (o pescoço depois do cabelo): a conta do lado da
            # linha via a superfície do modelo inteiro, e uma peça já separada ligava os dois lados.
            # Refaz olhando só a peça que está sendo cortada; fica só se sair uma peça de verdade sem
            # partir o resto. Cortes que já funcionam nem passam por aqui.
            _HOST_TOPO[0] = True
            try:
                o3 = _apply_core(cur, [cut], S, None)
            except Exception:
                traceback.print_exc()
                o3 = None
            finally:
                _HOST_TOPO[0] = False
            if o3 is not None and _cut_better(o3, o2, cur):
                if _DBG:
                    print('corte em sequência: refeito só na peça', flush=True)
                o3['livres'][0]['checks'] = [_chk('ok', 'Corte em sequência: a linha está numa peça que já saiu de um corte anterior; '
                                                        'o lado de cada linha foi achado só nessa peça (as outras peças não contam).')] + \
                    o3['livres'][0].get('checks', [])
                o2 = o3
        for p in o2['pieces']:
            if p.pop('_novo', False):
                p['livre'] = i
        r = o2['livres'][0]
        r['i'] = i
        res.append(r)
        cur = o2
    if pend is not None and pend[0] < len(res):
        res[pend[0]]['checks'] = res[pend[0]].get('checks', []) + [_chk('aviso', f'Feito pelo motor anterior: {pend[1]}.')]
    _snap(len(cuts), cur)                             # a tela desenha os próximos cortes sobre as peças sem soquete
    if any(r.get('_soquete_depois') for r in res):
        cur = _soquetes_pele(cur, cuts, res, S)
    o = dict(cur)
    o['livres'] = res
    return o


def _soquetes_pele(cur, cuts, res, S):
    """1.55: o soquete navalha dos cortes pela pele com "só colar" e soquete, no fim, depois de todos os cortes, junta
    por junta: entre a peça do corte e a peça do outro lado da linha (a menor peça primeiro). Se não couber ou
    partiria uma peça, a junta fica com o pino do módulo de conectores, e o motivo vai no aviso do corte."""
    import pelecut as PC
    from scipy.spatial import cKDTree
    bb = S.bounding_box()
    diag = float(np.linalg.norm(np.array(bb[3:]) - np.array(bb[:3])))
    centro = np.asarray(E.centroid(S), np.float64)
    pcs = list(cur['pieces'])
    por_i = {r.get('i'): r for r in res}
    jobs = []
    regioes = {}
    for r in res:
        d = r.pop('_soquete_depois', None)
        hreg = r.pop('_soquete_regiao', None)
        if d is None:
            continue
        i = r.get('i')
        regioes[i] = hreg
        r['_d_soq'] = d
        for k, p in enumerate(pcs):
            if p.get('livre') == i and p.get('tipo') != 'cavilha':
                jobs.append((_vol(p['mesh']), i, k, d))
    jobs.sort(key=lambda x: (x[0], x[1]))
    feitos = set()
    for _, i, k, d in jobs:
        cut, r = cuts[i], por_i[i]
        p = pcs[k]
        pv = np.asarray(p['mesh'].to_mesh().vert_properties)[:, :3]
        tr = cKDTree(pv)
        lim = float(cut.get('folga') or 0.2) + 0.5 * _CUR_K[0]
        # a costura anda pelas arestas: numa malha grossa ela fica até uma aresta longe da linha
        Lall = [L for L in (_clean_loop(x) for x in _loops_of(cut)) if L is not None]
        if Lall:
            Tp_ = np.asarray(p['T'])
            near = cKDTree(np.vstack(Lall)).query(Tp_.mean(1), distance_upper_bound=3.0 * _CUR_K[0])[0] < np.inf
            if near.any():
                Tn_ = Tp_[near]
                lim += float(np.median(np.linalg.norm(Tn_ - np.roll(Tn_, 1, axis=1), axis=2)))
        loops = [L for L in Lall if float(np.median(tr.query(L)[0])) <= lim]
        if not loops:
            continue                                  # este pedaço da peça não encosta na linha (outro corte o separou)
        P_ = np.vstack(loops)
        cnt = []
        for j, q in enumerate(pcs):
            if j == k or q.get('tipo') == 'cavilha':
                cnt.append(0)
                continue
            qb = np.array(q['mesh'].bounding_box())
            if np.any(qb[3:] < P_.min(0) - 2) or np.any(qb[:3] > P_.max(0) + 2):
                cnt.append(0)
                continue
            qv = np.asarray(q['mesh'].to_mesh().vert_properties)[:, :3]
            cnt.append(int((cKDTree(qv).query(P_)[0] <= lim).sum()))
        j = int(np.argmax(cnt)) if cnt else -1
        nome = r.get('nome') or cut.get('nome') or f'Corte {i + 1}'
        outras = [np.asarray(L, np.float64) for t, c in enumerate(cuts) if t != i for L in (c.get('linhas') or []) if len(L) >= 3]
        rr = None
        if j >= 0 and cnt[j] > 0:
            # região: a peça de onde o corte saiu (sem a folga entre as duas), menos as peças que cortes depois tiraram
            # dela e os soquetes já feitos nas vizinhas; sem ela, as duas peças juntas
            hreg = regioes.get(i)
            if hreg is not None:
                hb = np.array(hreg.bounding_box())
                oth = [q['mesh'] for t, q in enumerate(pcs) if t not in (k, j)
                       and not (np.any(np.array(q['mesh'].bounding_box())[3:] < hb[:3]) or np.any(np.array(q['mesh'].bounding_box())[:3] > hb[3:]))]
                regiao = E.flat(hreg - E.union(oth)) if oth else hreg
            else:
                regiao = E.flat(E.union([p['mesh'], pcs[j]['mesh']]))
            rr = PC.soquete_junta(p['mesh'], pcs[j]['mesh'], regiao, cut, loops, outras, diag, centro, S, sys.modules[__name__])
        if rr is not None and rr[0] is not None:
            npc, nq, extra, sc = rr
            q = pcs[j]
            Tp, cp = _paint_from(p['T'], p['paint'], npc, p['base'])
            Tq, cq = _paint_from(q['T'], q['paint'], nq, q['base'])
            pcs[k] = dict(p, mesh=npc, T=Tp, paint=cp)
            pcs[j] = dict(q, mesh=nq, T=Tq, paint=cq)
            for t, x in enumerate(extra):
                m = x['mesh'] if isinstance(x, dict) else x
                pcs.append(dict(mesh=m, base=p['base'], nome=f'Cavilha · {nome}' + (f' {t + 1}' if t else ''), tipo='cavilha', rid=None,
                                axis=None, print_T=None, T=tri_array(m), paint=np.full(m.num_tri(), p['base'], np.uint8), livre=i))
            r['checks'] = r.get('checks', []) + sc
            feitos.add(i)
            continue
        if i in feitos:
            continue                                  # outro pedaço desta peça já ganhou o soquete
        motivo = rr[1] if rr is not None else 'Sem soquete: a peça do outro lado da linha não foi achada.'
        st = dict(cur, pieces=pcs)
        try:
            st2, ck = PC._conector(st, cut, nome, np.asarray(d, np.float64), 'pino')
        except Exception:
            traceback.print_exc()
            st2, ck = st, []
        pcs = list(st2['pieces'])
        r['checks'] = r.get('checks', []) + [_chk('aviso', motivo)] + ck
        r['sem_pino'] = not any(c['nivel'] == 'ok' for c in ck)
        feitos.add(i)
    # corte cuja linha não encosta mais numa peça só (cortes depois dele dividiram a peça junto da linha): o pino
    for i in sorted(regioes):
        if i in feitos:
            continue
        cut, r = cuts[i], por_i[i]
        nome = r.get('nome') or cut.get('nome') or f'Corte {i + 1}'
        try:
            st2, ck = PC._conector(dict(cur, pieces=pcs), cut, nome, np.asarray(r.get('_d_soq') or [0, 0, 1], np.float64), 'pino')
        except Exception:
            traceback.print_exc()
            st2, ck = dict(cur, pieces=pcs), []
        pcs = list(st2['pieces'])
        r['checks'] = r.get('checks', []) + [_chk('aviso', 'Sem soquete: cortes feitos depois dividiram a peça junto da linha deste corte.')] + ck
        r['sem_pino'] = not any(c['nivel'] == 'ok' for c in ck)
        r.pop('_d_soq', None)
    for r in res:
        r.pop('_d_soq', None)
    return dict(cur, pieces=pcs)


def _apply_core(out, cuts, S, progress=None):
    """Aplica os cortes livres sobre o resultado do "Separar por cor" (out de split.run).
    Cada corte age na parte em que a linha foi desenhada. Devolve out com as peças novas e
    out['livres'] = resultado de cada corte."""
    t0 = time.time()
    bb = S.bounding_box()
    diag = float(np.linalg.norm(np.array(bb[3:]) - np.array(bb[:3]))) + 5.0
    centro = np.array([(bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2, (bb[2] + bb[5]) / 2])
    try:
        centro = np.asarray(E.centroid(S), np.float64)
    except Exception:
        pass
    pieces = list(out['pieces'])
    res = []
    n_ok = 0
    topo = None
    topo_box = [None]
    _HT_CACHE.clear()
    for i, cut in enumerate(cuts):
        if cut.get('plano'):                          # corte plano (seção própria): corta tudo que cruza
            import plano as PL
            if progress:
                progress(f'corte plano {i + 1} de {len(cuts)}')
            try:
                r, pieces = PL.apply_plane(i, cut, pieces, diag, _paint_from)
            except Exception as ex:
                traceback.print_exc()
                r = dict(i=i, nome=cut.get('nome') or f'Plano {i + 1}', ok=False, plano=True,
                         checks=[_chk('erro', f'O corte plano falhou: {ex}')])
            res.append(r)
            n_ok += int(bool(r.get('ok')))
            continue
        nome = cut.get('nome') or f'Corte {i + 1}'
        enc_user = cut.get('encaixe') if cut.get('encaixe') in ENCAIXES else 'colar'
        sock = bool(cut.get('soquete')) and enc_user not in GIRA
        if sock:
            cut = dict(cut, encaixe='colar')           # o pino entra depois, no fundo do soquete
        if progress:
            progress(f'corte livre {i + 1} de {len(cuts)}')
        loops = [L for L in (_clean_loop(x) for x in (cut.get('linhas') or [])) if L is not None]
        pre, peca_pts, mclean = [], None, None
        if cut.get('mascara'):
            mk = decode_mask(cut['mascara'], S.num_tri())
            if mk is None or int(cut.get('n') or S.num_tri()) != S.num_tri():
                res.append(dict(i=i, nome=nome, ok=False, checks=[_chk('erro', 'A área marcada é de outra versão do modelo '
                                                                                '(o tamanho mudou?). Marque de novo.')]))
                continue
            if mk.any():
                if topo is None:
                    topo = SPL._topology(S)
                mloops, peca_pts, msgs, mclean = mask_lines(S, mk, topo)
                pre += [_chk('ok', 'Área marcada: ' + x) if 'ignoradas' in x or 'preenchidos' in x else _chk('erro', x) for x in msgs]
                if any(c['nivel'] == 'erro' for c in pre):
                    res.append(dict(i=i, nome=nome, ok=False, checks=pre))
                    continue
                if not mloops:
                    res.append(dict(i=i, nome=nome, ok=False, checks=pre + [_chk('erro', 'A área marcada não tem borda: marque só a parte que vai sair.')]))
                    continue
                # borda que coincide com uma linha desenhada (o balde parou nela): fica só a linha
                from scipy.spatial import cKDTree
                drawn = cKDTree(np.concatenate(loops)) if loops else None
                novas = []
                for L in (_clean_loop(x) for x in mloops):
                    if L is None:
                        continue
                    if drawn is not None and float(np.median(drawn.query(L)[0])) < 1.5:
                        continue
                    novas.append(L)
                loops += novas
                if novas:
                    pre.append(_chk('ok', f'Área marcada: {len(novas)} borda(s) viram linhas de corte.'))
        if not loops:
            res.append(dict(i=i, nome=nome, ok=False, checks=[_chk('erro', 'Corte sem linha fechada nem área marcada.')]))
            continue
        if cut.get('_host_k') is not None:              # corte numa peça escolhida: a peça já vem decidida
            hk, dist = int(cut['_host_k']), 0.0
        else:
            hk, dist = _host_by_lines(pieces, loops)
        if hk < 0 or dist > 2.5:
            res.append(dict(i=i, nome=nome, ok=False, checks=[_chk('erro', 'A linha não está sobre o modelo (o modelo mudou de '
                                                                            'tamanho ou de lugar?). Desenhe de novo.')]))
            continue
        host = pieces[hk]
        _th = [None]

        def TH():
            # superfície original só dentro da peça que vai ser cortada: num corte em sequência (o
            # pescoço depois do cabelo), uma peça já separada não liga mais um lado da linha ao outro
            nonlocal topo
            if topo is None:
                topo = SPL._topology(S)
            if not _HOST_TOPO[0]:
                return topo
            if _th[0] is None:
                _th[0] = _host_topo(topo, S, host['mesh'])
            return _th[0]
        if mclean is None and len(pieces) > 1 and cut.get('_host_k') is None:
            # a linha está sobre uma separação que já existe (a borda de uma peça por cor ou de um corte
            # anterior): cortar de novo só tiraria uma lasca da costura
            try:
                sh, other = _seam_share(pieces, hk, loops, float(cut.get('folga') or 0.2))
            except Exception:
                traceback.print_exc()
                sh, other = 0.0, None
            if sh >= 0.8:
                res.append(dict(i=i, nome=nome, ok=True, nada=True, checks=pre + [_chk('aviso',
                    f'A linha está sobre uma separação que já existe ("{host["nome"]}" e "{other}" já saem separadas, por '
                    'exemplo pela cor): este corte não foi refeito, para não tirar uma lasca da costura. Se quer o soquete ou o '
                    'pino deste corte nessa junta, desligue a separação da outra (na aba Cores, desmarque "Separar" da área) '
                    'ou apague este corte.')]))
                continue
        try:
            r = cut_one(host['mesh'], dict(cut, linhas=loops), diag, centro, peca_pts)
        except Exception as ex:
            r = dict(ok=False, checks=[_chk('erro', f'O corte falhou: {ex}')])
        if _ABA_PLANO and r.get('ok') and r.get('_plano_auto') and not cut.get('forma_fixa'):
            # o plano automático pode deixar uma aba (a face plana passa além da parede da calça, por baixo da
            # barra da camisa): se a face que segue a linha deixa bem menos aba, fica ela
            try:
                if topo is None:
                    topo = SPL._topology(S)
                a1 = _pele_fora(r, host['mesh'], S, loops, topo, diag, centro)
                if a1 > 1.5 * _CUR_K[0] ** 2:
                    rc = cut_one(host['mesh'], dict(cut, linhas=loops, forma='curva', forma_fixa=True), diag, centro, peca_pts)
                    if rc.get('ok'):
                        a2 = _pele_fora(rc, host['mesh'], S, loops, topo, diag, centro)
                        if _DBG:
                            print('aba do plano:', cut.get('nome'), round(a1, 2), 'seguindo a linha:', round(a2, 2), flush=True)
                        if a2 < 0.5 * a1:
                            rc['checks'] = rc.get('checks', []) + [_chk('ok', f'A face plana levava {_fmt(a1, 0)} mm² de superfície de fora da '
                                                                         'linha (uma aba por baixo de uma barra): a face do corte segue a linha.')]
                            r = rc
            except Exception:
                traceback.print_exc()

        def conferir(r, cut_):
            """A face do corte é uma superfície lisa pela linha: o que sai dela (uma orelha junto da linha)
            pode ficar do lado errado. Confere pela superfície dentro da linha e, se partiu algo, refaz pela
            área da superfície. Devolve (r, se precisou refazer)."""
            nonlocal topo
            fixed = False
            if r.get('ok') and mclean is None and loops and not cut_.get('inverter'):
                try:
                    if topo is None:
                        topo = SPL._topology(S)
                    rc = _recut_by_surface(host, S, loops, TH(), cut_, diag, centro, r)
                    if rc is not None:
                        r, fixed = rc, True
                    rs = _recut_if_stolen(host, S, loops, TH(), cut_, diag, centro, r)
                    if rs is not None:
                        r, fixed = rs, True
                except Exception:
                    traceback.print_exc()
            return r, fixed
        r, fixed = conferir(r, cut)
        if _DBG:
            print('corte', nome, 'auto_plano', _auto_plano(cut, loops), 'plano usado', r.get('_plano_auto'), 'dev', r.get('_plano_dev'),
                  'refeito', fixed, 'ok', r.get('ok'), 'partes', len(r.get('body_parts') or []), 'peça', cut.get('peca') is not None or '_host_k' in cut, flush=True)
        if _auto_plano(cut, loops) and (fixed or not r.get('ok') or len(r.get('body_parts') or []) > 1):
            # o plano automático não serviu aqui (levava pele de fora da linha, como a barra da manga, ou
            # partia o corpo): fica a face que segue a linha, como antes
            rk = None
            if _CASCA and peca_pts is None and len(loops) == 1:
                # a linha está no vinco de uma camada de cima (a barra da manga): junta escondida por baixo dela
                try:
                    rk = casca_cut(host['mesh'], dict(cut, linhas=loops), diag, centro)
                    if rk is not None:
                        if topo is None:
                            topo = SPL._topology(S)
                        if (_recut_by_surface(host, S, loops, TH(), cut, diag, centro, rk) is not None or
                                _recut_if_stolen(host, S, loops, TH(), cut, diag, centro, rk) is not None):
                            rk = None                # também levaria pele do lado errado: não serve
                except Exception:
                    traceback.print_exc()
                    rk = None
            if rk is not None:
                r = rk
            else:
                try:
                    c2 = dict(cut, forma='curva', forma_fixa=True)
                    r2 = cut_one(host['mesh'], dict(c2, linhas=loops), diag, centro, peca_pts)
                    r2, _ = conferir(r2, c2)
                    r, cut = r2, c2                  # daqui em diante, igual ao corte que segue a linha
                except Exception:
                    traceback.print_exc()
        if not r.get('ok') and mclean is not None and mclean.any():
            # a borda da área não separou (ex.: tranças que encostam no peito ao longo do ombro):
            # corta pelo volume mais perto da área marcada, que segue os contatos
            try:
                rv = cut_by_mask_volume(host['mesh'], S, mclean, cut, diag, None, loops, centro)
            except Exception as ex:
                rv = dict(ok=False, checks=[_chk('erro', f'O corte pelo volume também falhou: {ex}')])
            if rv.get('ok'):
                r = rv
            else:
                r = dict(r, checks=r.get('checks', []) + rv.get('checks', []))
        if not r.get('ok') and mclean is None and loops:
            # só linhas e o corte não separou: a parte encosta no corpo em outro ponto que a linha
            # não pegou. A área da peça sai das linhas pela superfície e o corte é completado ali.
            try:
                if topo is None:
                    topo = SPL._topology(S)
                fm = mask_from_lines(S, loops, TH(), diag, centro, bool(cut.get('inverter')))
            except Exception:
                traceback.print_exc()
                fm = None
            if fm is not None and fm[0].any():
                am, xl, xc = fm
                ml2, pp2, _, mc2 = mask_lines(S, am, TH())
                from scipy.spatial import cKDTree
                drawn = cKDTree(np.concatenate(loops))
                novas = [L for L in (_clean_loop(x) for x in ml2) if L is not None and float(np.median(drawn.query(L)[0])) >= 1.5]
                if _os.environ.get('FLEXI_DUMP'):
                    np.savez(_os.path.join(_os.environ['FLEXI_DUMP'], f"mask_{cut.get('nome') or i}.npz".replace(' ', '_')),
                             cen=tri_array(S).mean(1), am=am, k=_CUR_K[0], novas=np.array([np.asarray(L) for L in novas], dtype=object), allow_pickle=True)
                c2 = dict(cut, inverter=False, _de_linhas=True)
                if _PLANO_MISTO and novas and _auto_plano(cut, loops):
                    c2 = dict(c2, forma='curva', forma_fixa=True, _planos=[True] * len(loops) + [False] * len(novas))
                try:
                    r2 = cut_one(host['mesh'], dict(c2, linhas=loops + novas), diag, centro, pp2)
                except Exception:
                    traceback.print_exc()
                    r2 = dict(ok=False, checks=[])
                if _DBG:
                    print('contato:', nome, 'linhas extras', len(novas), 'ok', r2.get('ok'), [x['texto'][:100] for x in r2.get('checks', []) if x['nivel'] != 'ok'], flush=True)
                if not r2.get('ok') and mc2 is not None and mc2.any():
                    try:
                        r2 = cut_by_mask_volume(host['mesh'], S, mc2, c2, diag, np.concatenate(loops), loops, centro)
                    except Exception as ex:
                        r2 = dict(ok=False, checks=[_chk('erro', f'O corte falhou: {ex}')])
                if r2.get('ok'):
                    loops = loops + novas
                    if xc is not None and xl > 3.0:
                        pre.append(_chk('aviso', 'A linha não fechava a separação: a parte também encosta no corpo em outro ponto '
                                                 f'({_where(xc, centro)}), como uma mecha da franja apoiada na testa. Completei o corte ali '
                                                 'pela menor borda, que pode sair irregular; confira na prévia. Para uma borda limpa, '
                                                 'desenhe neste corte uma linha em volta desse contato (ou marque a mecha com o pincel).'))
                    else:
                        pre.append(_chk('ok', 'A face do corte não cabia numa superfície simples pelas linhas (o cabelo cobre o pescoço '
                                              'por trás, por exemplo): achei a peça pelo lado de cada linha.'))
                    r = r2
        if _PINO_FACE and r.get('ok') and loops and _auto_plano(cut, loops):
            r['_plano_linha'] = True                     # a linha cabe num plano (o pino pode sair perpendicular a ele)
        if _DBG:
            print('final', nome, 'forma', r.get('forma'), 'ok', r.get('ok'), 'refeito_vol', r.get('_refeito_vol'), 'plano', r.get('_plano_auto'), flush=True)
        if r.get('ok') and r.get('piece') is not None:
            r['_pv0'] = _vol(r['piece'])                # tamanho da peça antes do soquete (o encaixe não conta)
        if NAVALHA_BORDA and r.get('ok') and r.get('forma') == 'volume' and loops:
            try:
                # de que lado cada triângulo da pele tem de ficar (o mesmo que o soquete usa)
                want_r = _want_mask(S, loops, cut, mclean, [TH()], diag, centro, host['mesh'], r['piece'])
                skin_src = None
                if want_r is not None and len(want_r) == S.num_tri():
                    TS_ = tri_array(S)
                    tsz_ = np.max(np.linalg.norm(TS_ - np.roll(TS_, 1, axis=1), axis=2), axis=1)
                    skin_src = (TS_.mean(1), want_r, tsz_)
                r, nb_ = _razor_band(r, host['mesh'], cut.get('linhas') and [L for L in (_clean_loop(x) for x in cut['linhas']) if L is not None] or loops,
                                     cut, diag, centro, sock, skin_src)
                if nb_:
                    r['checks'] = r.get('checks', []) + [_chk('ok', f'Borda de navalha: junto de {nb_} linha(s) a face do corte segue a lâmina lisa pela linha '
                                                                    'desenhada (a borda na pele fica sobre a linha).')]
                if _PELE_EXATA or cut.get('pele_exata'):
                    # a borda da grade fica a 1 ou 2 mm da linha (a faixa de testa lisa na borda da mecha): a pele de
                    # dentro da linha que ficou no corpo volta para a peça, com o volume mais perto dela
                    outras_ = cut.get('_outras_linhas')
                    if outras_ is None:
                        outras_ = [np.asarray(L, np.float64) for j_, c_ in enumerate(cuts) if j_ != i
                                   for L in (c_.get('linhas') or []) if len(L) >= 3]
                    r2_ = _recut_by_surface(dict(host, _outras=outras_), S, loops, SPL._topology(S) if topo is None else topo, cut, diag,
                                            centro, r, perto=1.5 * _CUR_K[0], want=want_r)
                    if _DBG:
                        print('pele exata:', 'refeita' if r2_ is not None else 'mantida', flush=True)
                    if r2_ is not None:
                        r = r2_
            except Exception:
                traceback.print_exc()
        if sock and r.get('ok') and not r.get('_casca'):
            try:
                want_s = _want_mask(S, loops, cut, mclean, [TH()], diag, centro, host['mesh'], r['piece'])
                # as linhas dos outros cortes: um soquete não pode descer até perto da linha de outro corte
                # (o pescoço curto entre a cabeça e o corpo ficaria um copo oco)
                outras = cut.get('_outras_linhas')
                if outras is None:
                    outras = [np.asarray(L, np.float64) for j_, c_ in enumerate(cuts) if j_ != i
                              for L in (c_.get('linhas') or []) if len(L) >= 3]
                r, sc = socket_cut(r, host['mesh'], loops, dict(cut, encaixe=enc_user, _outras=outras), diag, centro, enc_user, S, want_s)
                r['checks'] = [x for x in r.get('checks', []) if 'Sem pino' not in x['texto']] + sc
                r['encaixe'] = enc_user
            except Exception as ex:
                traceback.print_exc()
                r['checks'] = r.get('checks', []) + [_chk('aviso', f'O soquete falhou ({ex}): a peça ficou com a face do corte normal.')]
        if enc_user != 'colar' and r.get('ok') and any('sem pino' in x['texto'] for x in r.get('checks', [])):
            r['sem_pino'] = True
            r['checks'] = r.get('checks', []) + [_chk('aviso', 'Este corte ficou SEM PINO (a parte é fina demais aqui). Para ter encaixe mesmo assim: '
                                                             'ligue "A peça entra no corpo (soquete)", que encaixa sem pino; ou diminua a '
                                                             '"Folga do pino" (ex.: 0,2 mm); ou troque a trava por "Pino fixo (losango)", '
                                                             'que cabe em partes mais finas.')]
        if r.get('ok'):
            try:
                want = None
                if mclean is not None and mclean.any():
                    want = ~mclean if cut.get('inverter') else mclean
                elif loops:
                    if topo is None:
                        topo = SPL._topology(S)
                    fm_ = mask_from_lines(S, loops, TH(), diag, centro, bool(cut.get('inverter')))
                    if fm_ is not None and fm_[0].any():
                        want = fm_[0]
                        # a área achada pelas linhas pode ser o lado do corpo: fica a orientação que mais concorda
                        from scipy.spatial import cKDTree
                        cw = tri_array(S).mean(1)
                        dlw, _ = cKDTree(np.concatenate(loops)).query(cw, distance_upper_bound=6.0)
                        qw = np.where(np.isfinite(dlw))[0]
                        qw = qw[_on_surface(cw[qw], tri_array(host['mesh']), tol=0.05) >= 0]
                        onw = _on_surface(cw[qw], tri_array(r['piece']), tol=0.05) >= 0
                        if (want[qw] == onw).sum() < (want[qw] != onw).sum():
                            want = ~want
                r, ma = _fix_appendages(r, host['mesh'], S, gap=float(cut.get('folga') or 0.2), want=want, loops=loops)
                if ma > 0:
                    r['checks'] = r.get('checks', []) + [_chk('ok', f'Partes finas junto do corte que ficariam do lado errado (uma orelha com a '
                                                                    f'borda na linha) foram para a peça a que pertencem: {_fmt(ma, 1 if _CUR_K[0] == 1.0 else 4)} mm³.')]
                r, mv = _fix_slivers(r, host['mesh'], S, rmin=_LASCA_R * _CUR_K[0], gap=float(cut.get('folga') or 0.2))   # 0,8 mm reais (o bico)
                if mv > 0:
                    r['checks'] = r.get('checks', []) + [_chk('ok', f'Arestas finas junto do corte (menos de {_fmt(2 * _LASCA_R * _CUR_K[0], 1)} mm, que não '
                                                                    f'imprimem) passaram para a peça do lado: {_fmt(mv, 1 if _CUR_K[0] == 1.0 else 4)} mm³.')]
            except Exception:
                traceback.print_exc()
        r['checks'] = pre + r.get('checks', [])
        r['i'], r['nome'] = i, nome
        if r.get('ok') and r.get('body_parts') is not None:
            r['body_parts'] = [q for q in r['body_parts'] if not q.is_empty() and _vol(q) > 0.05 * _CUR_K[0] ** 3]
            if not r['body_parts']:
                r = dict(i=i, nome=nome, ok=False, checks=pre + [_chk('erro', 'O corte pegou a parte inteira (não sobrou nada do outro '
                                                                       'lado da linha). Confira o lado com "Inverter o lado".')])
        if r.get('ok') and r.get('piece') is not None:
            r.pop('_refeito_vol', None)
            pv_ = r.pop('_pv0', None) or _vol(r['piece'])
            if pv_ < 1.0 * _CUR_K[0] ** 3:
                r = dict(i=i, nome=nome, ok=False, checks=pre + [_chk('erro', f'O corte só tirou uma lasca de {_fmt(pv_, 2)} mm³ '
                                                                       '(a linha está numa costura ou fora da parte?): não virou peça. '
                                                                       'Desenhe a linha em volta da parte que deve sair.')])
        res.append(r)
        if not r.get('ok'):
            _dump_fail(cut, r['checks'])
            continue
        n_ok += 1
        # garantia: a peça e o resto nunca dividem material (lasca duplicada dentro da peça)
        try:
            bps0, ovv = SPL.no_overlap(r['piece'], list(r['body_parts']))
            if ovv > 0.05 * _CUR_K[0] ** 3:
                r['body_parts'] = bps0
                r['checks'] = r.get('checks', []) + [_chk('ok', f'Material repetido entre a peça e o resto ({_fmt(ovv, 1)} mm³) foi '
                                                                 'tirado do resto: as peças não se sobrepõem.')]
                r['checks'] = [x for x in r['checks'] if 'deixa o resto do modelo em' not in x['texto'] or len(bps0) > 1]
        except Exception:
            traceback.print_exc()
        # lascas de 2 mm³ ou menos que o corte soltou do corpo: não imprimem e só atrapalham
        bps = list(r['body_parts'])
        big_bp = max((_vol(q) for q in bps), default=0.0)
        tiny = [q for q in bps if _vol(q) <= 2.0 * _CUR_K[0] ** 3 and _vol(q) < 0.001 * big_bp]
        # farelo maior (até 20 mm³) que sobrou solto no fundo de uma costura completada pela menor borda: um
        # pedaço tão pequeno perto de um corpo grande não vira peça para imprimir; sai com aviso
        farelo = [q for q in bps if not any(q is t for t in tiny) and _vol(q) <= 20.0 * _CUR_K[0] ** 3 and _vol(q) < 0.0001 * big_bp]
        if farelo and len(tiny) + len(farelo) < len(bps):
            r['body_parts'] = [q for q in bps if not any(q is t for t in farelo)]
            bps = list(r['body_parts'])
            r['checks'] = r.get('checks', []) + [_chk('aviso', f'{len(farelo)} farelo(s) pequeno(s) ficaram soltos do corpo junto da costura e '
                                                            f'foram descartados ({_fmt(sum(_vol(t) for t in farelo), 1)} mm³ no total); '
                                                            'confira a costura na prévia.')]
            r['checks'] = [x for x in r['checks'] if 'deixa o resto do modelo em' not in x['texto'] or len(r['body_parts']) > 1]
        if tiny and len(tiny) < len(bps):
            r['body_parts'] = [q for q in bps if not any(q is t for t in tiny)]
            r['checks'] = r.get('checks', []) + [_chk('ok', f'{len(tiny)} lasca(s) de até 2 mm³ que o corte soltou foram descartadas '
                                                         f'({_fmt(sum(_vol(t) for t in tiny), 1)} mm³ no total).')]
            r['checks'] = [x for x in r['checks'] if 'deixa o resto do modelo em' not in x['texto'] or len(r['body_parts']) > 1]
        # pedacinho solto do corpo (até 50 mm³, junto da costura) que encosta na peça: vai com a peça, para
        # não sair um farelo separado na exportação
        try:
            bps = list(r['body_parts'])
            big_bp = max((_vol(q) for q in bps), default=0.0)
            small = [q for q in bps if _vol(q) <= 50.0 * _CUR_K[0] ** 3 and _vol(q) < 0.01 * big_bp]
            if small and len(small) < len(bps):
                from scipy.spatial import cKDTree
                pv = np.asarray(r['piece'].to_mesh().vert_properties)[:, :3]
                tr_ = cKDTree(pv)
                lim_ = float(cut.get('folga') or 0.2) + 0.3 * _CUR_K[0]
                junto = [q for q in small if float(tr_.query(np.asarray(q.to_mesh().vert_properties)[:, :3], k=1)[0].min()) <= lim_]
                if junto:
                    p2_ = E.flat(E.union([r['piece']] + junto))
                    # só se encaixa limpo: a peça continua uma só e sem túneis novos (contato só em pontos)
                    if len(E.parts(p2_, 0.3)) > len(E.parts(r['piece'], 0.3)) or p2_.genus() > r['piece'].genus():
                        junto = []
                if junto:
                    r['piece'] = p2_
                    r['body_parts'] = [q for q in bps if not any(q is t for t in junto)]
                    r['checks'] = r.get('checks', []) + [_chk('ok', f'{len(junto)} pedacinho(s) que o corte soltou do corpo junto da costura '
                                                                 f'({_fmt(sum(_vol(t) for t in junto), 1)} mm³) foram com a peça.')]
                    r['checks'] = [x for x in r['checks'] if 'deixa o resto do modelo em' not in x['texto'] or len(r['body_parts']) > 1]
        except Exception:
            traceback.print_exc()
        repl = []
        for k, m in enumerate(r['body_parts']):
            T, col = _paint_from(host['T'], host['paint'], m, host['base'])
            repl.append(dict(host, mesh=m, T=T, paint=col,
                             nome=host['nome'] + (f' {k + 1}' if len(r['body_parts']) > 1 else '')))
        new = []
        sub = E.parts(r['piece'], 0.5) or [r['piece']]
        for k, pm in enumerate(sub):             # áreas marcadas separadas viram peças separadas
            T, col = _paint_from(host['T'], host['paint'], pm, host['base'])
            new.append(dict(mesh=pm, base=host['base'], nome=nome + (f' ({k + 1})' if len(sub) > 1 else ''), tipo='livre', rid=None,
                            axis=r['axis'], print_T=r['print_T'], T=T, paint=col, livre=i, _novo=True))
        pieces = pieces[:hk] + repl + pieces[hk + 1:] + new
        for e in r.get('extra', []):
            T = tri_array(e['mesh'])
            pieces.append(dict(mesh=e['mesh'], base=host['base'], nome=f'Cavilha · {nome}', tipo='cavilha', rid=None,
                               axis=e['axis'], print_T=None, T=T, paint=np.full(len(T), host['base'], np.uint8), livre=i, _novo=True))
    o2 = dict(out)
    o2['pieces'] = pieces
    o2['livres'] = res
    o2['segundos'] = round(out.get('segundos', 0) + time.time() - t0, 1)
    return o2


def _surface_split(S, mask, piece, bodies):
    """Área da superfície marcada (a peça) que ficou nas partes do corpo."""
    T = tri_array(S)
    TM = T[mask]
    if not len(TM):
        return 0.0, 0.0
    cm = TM.mean(1)
    ar = np.linalg.norm(np.cross(TM[:, 1] - TM[:, 0], TM[:, 2] - TM[:, 0]), axis=1) / 2
    on_b = np.zeros(len(cm), bool)
    for b in bodies:
        on_b |= _on_surface(cm, tri_array(b), tol=0.05) >= 0
    return float(ar[on_b].sum()), float(ar.sum())


def _recut_by_surface(host, S, loops, topo, cut, diag, centro, r, perto=None, want=None):
    """Depois do corte por uma face lisa: o que está dentro da linha na superfície (uma orelha junto
    da linha) e ficou do lado do corpo volta para a peça. Só o volume mais perto dessa superfície que
    da superfície do corpo (a bissetriz), sem soltar partes."""
    from scipy.spatial import cKDTree
    from scipy.ndimage import distance_transform_edt, gaussian_filter
    T = tri_array(S)
    allc = T.mean(1)
    if want is not None and len(want) == len(T):
        fm = (np.asarray(want, bool),)                 # o lado da peça já conhecido (a máscara do corte)
    else:
        fm = mask_from_lines(S, loops, topo, diag, centro, False)
    if fm is None or not fm[0].any():
        if _DBG: print('recut_by_surface: sai 1', flush=True)
        return None
    bodies = list(r['body_parts'])
    # junto da linha só (pele exata): as contas de superfície ficam nos triângulos perto dela
    if perto is not None:
        dlp, _ = cKDTree(np.concatenate([np.asarray(L_, np.float64) for L_ in loops])).query(allc, distance_upper_bound=5.0 * _CUR_K[0])
        qi = np.where(np.isfinite(dlp))[0]
    else:
        qi = np.arange(len(T))
    in_host = np.zeros(len(T), bool)
    in_host[qi] = _on_surface(allc[qi], tri_array(host['mesh']), tol=0.05) >= 0
    on_p = np.zeros(len(T), bool)
    on_p[in_host] = _on_surface(allc[in_host], tri_array(r['piece']), tol=0.05) >= 0
    on_bd = np.zeros(len(T), bool)
    for b in bodies:
        on_bd[in_host] |= _on_surface(allc[in_host], tri_array(b), tol=0.05) >= 0
    arT = np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1) / 2
    side = fm[0] & in_host
    if want is None and arT[side & on_p].sum() < arT[side & on_bd].sum():
        side = ~fm[0] & in_host                       # a área achada é o lado do corpo: a peça é o outro lado
    am = side
    if perto is not None:
        # só a pele junto da linha (a faixa que a grade deixou no corpo); longe dela fica como está
        am = side & (dlp <= perto)
    TM = T[am]
    cm = TM.mean(1)
    ar = arT[am]
    on_b = on_bd[am]
    lost, tot = float(ar[on_b].sum()), float(ar.sum())
    if perto is not None:
        tot = float(arT[fm[0]].sum())
    if _DBG:
        print('recut_by_surface: perdida', round(lost, 1), 'de', round(tot, 1), flush=True)
    if lost <= max(1.5, 0.003 * tot) or lost > 0.25 * tot:
        if _DBG: print('recut_by_surface: sai 2', flush=True)
        return None
    L = TM[on_b]
    # superfície do corpo que não é da peça (para a bissetriz)
    piece, gap = r['piece'], float(cut.get('folga') or 0.2)
    lo = L.reshape(-1, 3).min(0) - 3.0
    hi = L.reshape(-1, 3).max(0) + 3.0
    ext = hi - lo
    step = float(max(0.12, (np.prod(ext) / 2.0e6) ** (1 / 3)))
    if perto is not None:
        step = float(_os.environ.get('FLEXI_PELE_PASSO', '0.2')) * _CUR_K[0]    # só num tubo em volta da linha: grade fina
        step = max(step, float((np.prod(ext) / 1.2e7) ** (1 / 3)))              # memória: no máximo uns 12 milhões de pontos
    xs, ys, zs = [lo[k] + step * np.arange(int(np.ceil(ext[k] / step)) + 1) for k in range(3)]
    n = (len(xs), len(ys), len(zs))
    boxm = mf.Manifold.cube(list(hi - lo + 2 * step)).translate(list(lo - step))
    ib = np.zeros(n, bool)
    BT = []
    for b in bodies:
        bb_ = np.array(b.bounding_box())
        if np.any(bb_[3:] < lo) or np.any(bb_[:3] > hi):
            continue
        cl = E.flat(b ^ boxm)
        if cl.is_empty():
            continue
        if perto is None:
            ib |= _voxelize(cl, xs, ys, zs)
        else:
            ib[0, 0, 0] = True                         # no tubo o campo vale em toda parte: a grade do corpo não serve
        BT.append(tri_array(cl))
    if not ib.any() or not BT:
        if _DBG: print('recut_by_surface: sai 3', flush=True)
        return None
    BT = np.concatenate(BT)
    bc = BT.mean(1)
    orig = _on_surface(bc, T[qi] if perto is not None else T, tol=0.05) >= 0
    # superfície original do corpo que não está dentro da linha
    mark_c = cKDTree(cm)
    dmark, _ = mark_c.query(bc)
    other = BT[orig & (dmark > 0.05)]
    if perto is not None and len(other):
        dlo_, _ = cKDTree(np.concatenate([np.asarray(L_, np.float64) for L_ in loops])).query(other.mean(1), distance_upper_bound=5.0 * _CUR_K[0])
        other = other[np.isfinite(dlo_)]
    smp = lambda TT: np.concatenate([TT.mean(1)] + [TT[:, k] * 0.5 + TT.mean(1) * 0.5 for k in range(3)]) if len(TT) else np.zeros((0, 3))
    NG = int(np.prod(n))

    def Gq(idx):                                      # coordenadas dos pontos da grade (sem montar a grade inteira)
        a_, b_, c_ = np.unravel_index(idx, n)
        return np.stack([xs[a_], ys[b_], zs[c_]], 1)
    ii = np.where(ib.ravel())[0]
    # junto da linha: o lado da peça é toda a pele de dentro da linha ali (a que ficou e a que se perdeu); a
    # bissetriz entre ela e a pele do corpo chega no vinco, sem deixar folga solta entre a peça e o que volta
    Lm = TM if perto is not None else L
    if perto is not None:
        def smp(TT, ap=0.01):                           # pontos espalhados na pele (triângulos grandes também)
            if not len(TT):
                return np.zeros((0, 3))
            a_ = np.linalg.norm(np.cross(TT[:, 1] - TT[:, 0], TT[:, 2] - TT[:, 0]), axis=1) / 2
            k_ = np.minimum(np.maximum(1, np.ceil(a_ / ap)).astype(np.int64), 400)
            ix_ = np.repeat(np.arange(len(TT)), k_)
            rg_ = np.random.default_rng(3)
            r1_, r2_ = np.sqrt(rg_.random(len(ix_))), rg_.random(len(ix_))
            return TT[ix_, 0] * (1 - r1_)[:, None] + TT[ix_, 1] * (r1_ * (1 - r2_))[:, None] + TT[ix_, 2] * (r1_ * r2_)[:, None]
        # o campo também fora do sólido (o suavizado não puxa a borda para longe da pele), só num tubo de
        # 3,5 mm em volta da linha; o sólido corta depois
        lp_ = np.concatenate([np.asarray(L_, np.float64) for L_ in loops])
        seg_ = np.vstack([np.linspace(a_, b_, max(2, int(np.linalg.norm(b_ - a_) / (0.5 * step)) + 1))
                          for L_ in loops for a_, b_ in zip(np.asarray(L_), np.roll(np.asarray(L_), -1, 0))])
        ijk_ = np.round((seg_ - lo) / step).astype(int)
        ok_ = np.all((ijk_ >= 0) & (ijk_ < np.array(n)), 1)
        lg_ = np.ones(n, bool)
        lg_[tuple(ijk_[ok_].T)] = False
        tubo = distance_transform_edt(lg_, sampling=step) <= 3.5 * _CUR_K[0]
        ii = np.where(tubo.ravel())[0]
    dm, _ = cKDTree(smp(Lm)).query(Gq(ii), distance_upper_bound=4.0)
    if len(other):
        do, _ = cKDTree(smp(other)).query(Gq(ii), distance_upper_bound=4.0)
    else:
        do = np.full(len(ii), np.inf)
    dm = np.where(np.isfinite(dm), dm, 4.0)
    do = np.where(np.isfinite(do), do, 4.0)
    F = np.full(NG, -3.0, np.float32 if perto is not None else np.float64)
    F[ii] = np.minimum(do - dm, 2.5 - dm)
    if perto is not None:
        # só onde a pele está do lado errado (mais 1,5 mm): o resto da borda fica como estava
        dL_, _ = cKDTree(smp(L)).query(Gq(ii), distance_upper_bound=4.0)
        dL_ = np.where(np.isfinite(dL_), dL_, 4.0)
        F[ii] = np.minimum(F[ii], 1.5 * _CUR_K[0] - dL_)
    F = gaussian_filter(F.reshape(n), float(_os.environ.get('FLEXI_PELE_SIGMA', '2.6')) if perto is not None else 0.7)
    if perto is not None:
        # só o volume que encosta na peça: o que ficaria solto (pele de dentro da linha longe da peça, debaixo
        # de uma mecha) continua no corpo
        from scipy.ndimage import label as _lbl, binary_dilation as _dil
        lb, nl_ = _lbl(F > 0)
        if nl_:
            cp = E.flat(piece ^ boxm)
            pv = _dil(_voxelize(cp, xs, ys, zs), iterations=2) if not cp.is_empty() else np.zeros(n, bool)
            ok_ = np.unique(lb[pv & (lb > 0)])
            keep = np.isin(lb, ok_)
            keep = _dil(keep, iterations=int(np.ceil(gap / step)) + 2)
            F = np.where(keep, F, -3.0)
    if (F > 0).sum() < 4:
        if _DBG: print('recut_by_surface: sai 4', flush=True)
        return None
    if perto is not None:
        return _pele_trechos(r, host, piece, bodies, F, step, lo, n, gap, lg_, seg_, ijk_, ok_, boxm, cm, ar, lost)
    try:
        sm_ = int(_os.environ.get('FLEXI_PELE_SUAVE', '20')) if perto is not None else 6
        Mv = _mc_manifold(np.pad(F.astype(np.float32), 1, constant_values=-3.0), step, lo, sm_, 'orelha')
        Mg = _mc_manifold(np.pad((F + gap).astype(np.float32), 1, constant_values=-3.0), step, lo, sm_, 'orelha')
        if perto is not None:
            # deslocamento de décimos de mícron: a superfície nova não passa rente a um vértice da pele (aresta
            # de comprimento quase zero, que o fatiador lê como defeito)
            Mv, Mg = Mv.translate([2.3e-4, 1.7e-4, 1.1e-4]), Mg.translate([2.3e-4, 1.7e-4, 1.1e-4])
    except Exception:
        if _DBG: print('recut_by_surface: sai 5', flush=True)
        return None
    hm_ = E.flat(E.flat(host['mesh'] ^ boxm) ^ Mv) if perto is not None else E.flat(host['mesh'] ^ Mv)
    add = E.flat(hm_ - piece)
    if add.is_empty() or _vol(add) < 0.05:
        if _DBG: print('recut_by_surface: sai 6', flush=True)
        return None
    ncomp = lambda ms: sum(len(E.parts(m, 0.05) or [m]) for m in ms)
    # a peça une com o sólido inteiro (que se sobrepõe a ela), não com a diferença: sem faces coincidentes
    p2 = E.flat(piece + (hm_ if perto is not None else add))
    b2 = [E.flat(b - (E.flat(Mg + hm_) if perto is not None else Mg)) for b in bodies]   # sem sobreposição
    if perto is not None:
        # lasca pequena que ficou solta (a pele dali não encosta na peça): sai (menos de 1,5 mm³ no total; devolver
        # ao corpo deixava arestas quase de comprimento zero, que o fatiador lê como defeito)
        n0 = ncomp([piece])
        ps_ = sorted(E.parts(p2, 0.0), key=lambda q: -_vol(q))
        solto = [q for q in ps_[n0:]]
        if solto and sum(_vol(q) for q in solto) <= 1.5 * _CUR_K[0] ** 3:
            p2 = E.flat(E.union(ps_[:n0])) if n0 > 1 else ps_[0]
    b2 = [q for b in b2 for q in (E.parts(b, 0.5) or [])]
    if perto is not None:
        # nenhum furo novo de lado a lado (a gola fina do kimono): o gênero das malhas não pode subir
        def gen(ms):
            g_ = 0
            for m_ in ms:
                me = m_.to_mesh()
                nv_, nf_ = len(me.vert_properties), len(me.tri_verts)
                nc_ = len(E.parts(m_, 0.0) or [m_])
                g_ += (2 * nc_ - (nv_ - nf_ // 2)) // 2
            return g_
        if gen([p2]) > gen([piece]) or gen(b2) > gen(bodies):
            if _DBG:
                print('recut_by_surface: abriria furo, fica como estava', gen([piece]), gen([p2]), gen(bodies), gen(b2), flush=True)
            return None
    if ncomp([p2]) > ncomp([piece]) or len(b2) > len(bodies):
        if _DBG: print('recut_by_surface: sai 7', [round(_vol(m), 2) for m in E.parts(p2, 0.05)][:10], ncomp([piece]), [round(_vol(m), 2) for m in b2][:10], len(bodies), flush=True)
        return None
    lost2 = 0.0
    on2 = np.zeros(len(cm), bool)
    for b in b2:
        on2 |= _on_surface(cm, tri_array(b), tol=0.05) >= 0
    lost2 = float(ar[on2].sum())
    if _DBG:
        print('recut_by_surface: perdida depois', round(lost2, 1), flush=True)
    if lost2 >= 0.7 * lost:
        if _DBG: print('recut_by_surface: sai 8', flush=True)
        return None
    r2 = dict(r, piece=p2, body_parts=sorted(b2, key=lambda q: -_vol(q)))
    r2['checks'] = r.get('checks', []) + [_chk('ok', f'O que está dentro da linha e a face lisa do corte deixaria no corpo (uma orelha '
                                                   f'junto da linha, por exemplo) foi para a peça: {_fmt(_vol(add), 1)} mm³.')]
    return r2


def _malha_info(m_):
    """(partes, gênero) de um sólido: o gênero conta as alças (um furo de lado a lado soma 1)."""
    ps = E.parts(m_, 0.0) or [m_]
    g = 0
    for q in ps:
        me = q.to_mesh()
        g += (2 - (len(me.vert_properties) - len(me.tri_verts) // 2)) // 2
    return len(ps), g


def _pele_trechos(r, host, piece, bodies, F, step, lo, n, gap, lg_, seg_, ijk_, ok_, boxm, cm, ar, lost):
    """Pele exata na borda, por trechos da linha (uns 20 mm cada): cada trecho só entra se não abrir furo nem
    soltar pedaço. Um trecho ruim (uma mecha fina encostada na testa) fica como estava; os outros entram."""
    from scipy.ndimage import distance_transform_edt, binary_dilation
    k = _CUR_K[0]
    # posição de cada ponto da grade ao longo da linha (pelo ponto da linha mais perto)
    ok_ = np.all((ijk_ >= 0) & (ijk_ < np.array(n)), 1)     # (o 'ok_' de fora foi reaproveitado lá)
    sl = np.zeros(len(seg_))
    d_ = np.linalg.norm(np.diff(seg_, axis=0), axis=1)
    sl[1:] = np.cumsum(np.where(d_ < 3 * step, d_, 0.0))
    lgs = np.full(n, -1.0)
    lgs[tuple(ijk_[ok_].T)] = sl[ok_]
    _, ind = distance_transform_edt(lg_, sampling=step, return_indices=True)
    pos = lgs[ind[0], ind[1], ind[2]]
    del ind
    comp = float(_os.environ.get('FLEXI_PELE_TRECHO', '8')) * k
    tid = np.floor(pos / comp).astype(np.int64)
    sm_ = int(_os.environ.get('FLEXI_PELE_SUAVE', '20'))
    hostc = E.flat(host['mesh'] ^ boxm)
    n_p0, g_p0 = _malha_info(piece)
    itens = []
    info_b = [_malha_info(b) for b in bodies]
    ok_n, tot_n = 0, 0
    from scipy.spatial import cKDTree
    outras = [np.asarray(L, np.float64) for L in (host.get('_outras') or []) if len(L) >= 3]
    kd_o = cKDTree(np.concatenate(outras)) if outras else None
    for t in np.unique(tid[F > 0]):
        reg = binary_dilation((tid == t) & (F > -gap - step), iterations=2)
        if not reg.any():
            continue
        idx = np.argwhere(reg)
        if kd_o is not None:
            # a linha de outro corte passa perto (o pescoço logo abaixo da nuca): ali fica como estava, para o outro
            # corte achar a peça como sempre
            q_ = lo + idx[:: max(1, len(idx) // 400)] * step
            if float(kd_o.query(q_)[0].min()) < 5.0 * k:
                continue
        a0 = np.maximum(idx.min(0) - 3, 0)
        a1 = np.minimum(idx.max(0) + 4, np.array(n))
        Fk = np.where(reg, F, -3.0)[a0[0]:a1[0], a0[1]:a1[1], a0[2]:a1[2]].astype(np.float32)
        if (Fk > 0).sum() < 4:
            continue
        tot_n += 1
        lo_k = lo + a0 * step
        try:
            Mv = _mc_manifold(np.pad(Fk, 1, constant_values=-3.0), step, lo_k, sm_, 'orelha').translate([2.3e-4, 1.7e-4, 1.1e-4])
            Mg = _mc_manifold(np.pad(Fk + gap, 1, constant_values=-3.0), step, lo_k, sm_, 'orelha').translate([2.3e-4, 1.7e-4, 1.1e-4])
        except Exception:
            continue
        hm = E.flat(hostc ^ Mv)
        if hm.is_empty():
            continue
        itens.append((t, hm, Mg))

    def tentar(grupo, p_cur, b_cur):
        """A peça e o corpo com estes trechos, ou None se abrir furo ou soltar pedaço."""
        hm = E.flat(mf.Manifold.batch_boolean([x[1] for x in grupo], mf.OpType.Add)) if len(grupo) > 1 else grupo[0][1]
        Mg = E.flat(mf.Manifold.batch_boolean([x[2] for x in grupo], mf.OpType.Add)) if len(grupo) > 1 else grupo[0][2]
        p_try = E.flat(p_cur + hm)
        cut_ = E.flat(Mg + hm)
        b_try = [E.flat(b - cut_) for b in b_cur]
        # pedacinho solto da peça (a pele dali não encosta nela): sai, se for pouco
        ps_ = sorted(E.parts(p_try, 0.0), key=lambda q: -_vol(q))
        if len(ps_) > n_p0 and sum(_vol(q) for q in ps_[n_p0:]) <= 0.5 * k ** 3 * len(grupo):
            p_try = E.flat(E.union(ps_[:n_p0])) if n_p0 > 1 else ps_[0]
        # pontinha solta do corpo (menos de 0,2 mm³ por trecho, uma ponta de fio cortada rente à pele): sai
        b2_ = []
        for b, (nb0, _g) in zip(b_try, info_b):
            qs = sorted(E.parts(b, 0.0), key=lambda q: -_vol(q))
            if len(qs) > nb0 and sum(_vol(q) for q in qs[nb0:]) <= 0.2 * k ** 3 * len(grupo):
                b = E.flat(E.union(qs[:nb0])) if nb0 > 1 else qs[0]
            b2_.append(b)
        np_, gp_ = _malha_info(p_try)
        ib_ = [_malha_info(b) for b in b2_]
        if np_ > n_p0 or gp_ > g_p0 or any(x[0] > y[0] or x[1] > y[1] for x, y in zip(ib_, info_b)):
            return None
        return p_try, b2_

    # todos juntos primeiro; um grupo recusado se divide ao meio até achar o trecho ruim
    estado = [piece, list(bodies), 0]

    def grupo(gs):
        if not gs:
            return
        rr = tentar(gs, estado[0], estado[1])
        if rr is not None:
            estado[0], estado[1], estado[2] = rr[0], rr[1], estado[2] + len(gs)
            return
        if len(gs) == 1:
            return
        m_ = len(gs) // 2
        grupo(gs[:m_])
        grupo(gs[m_:])
    grupo(itens)
    p_cur, b_cur, ok_n = estado
    if not ok_n:
        return None
    lost2 = 0.0
    on2 = np.zeros(len(cm), bool)
    for b in b_cur:
        on2 |= _on_surface(cm, tri_array(b), tol=0.05) >= 0
    lost2 = float(ar[on2].sum())
    if lost2 >= 0.7 * lost:
        return None
    r2 = dict(r, piece=p_cur, body_parts=sorted(b_cur, key=lambda q: -_vol(q)))
    r2['checks'] = r.get('checks', []) + [_chk('ok', f'Pele exata na borda: {_fmt(lost - lost2, 0)} mm² de pele junto da linha voltaram para a '
                                                   'peça (a grade cortava o canto entre as partes; agora a borda chega no vinco).')]
    return r2


def _recut_if_stolen(host, S, loops, topo, cut, diag, centro, r):
    """A face lisa do corte pode levar para a peça superfície que está FORA da linha: a barra da manga
    que cobre o braço logo acima da linha, a gola em volta do pescoço. Quando isso acontece, o corte é
    refeito pelo volume, seguindo a área que a linha fecha na superfície (a borda extra segue o vinco
    onde o braço entra na manga). Fica o resultado que deixa a roupa no corpo sem tirar nada da peça."""
    from scipy.spatial import cKDTree
    fm = mask_from_lines(S, loops, topo, diag, centro, False)
    if fm is None or not fm[0].any():
        return None
    T = tri_array(S)
    allc = T.mean(1)
    arT = np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1) / 2
    k2 = _CUR_K[0] ** 2
    tol = 0.6 * _CUR_K[0]
    if _PLANO_TOL and r.get('_plano_auto'):
        # face plana automática: a borda pode estar até o desvio da linha ao plano (até 1 mm), como a regra
        # do plano automático permite; só o que passa disso é superfície levada de fora da linha
        tol = min(max(tol, float(r.get('_plano_dev') or 0.0) + 0.3 * _CUR_K[0]), 1.3 * _CUR_K[0])
    dl, _ = cKDTree(np.concatenate(loops)).query(allc, distance_upper_bound=tol)
    far = ~np.isfinite(dl)                            # junto da linha a borda pode variar um pouco

    def where(piece):
        pb = np.array(piece.bounding_box())
        near = np.where(np.all((allc >= pb[:3] - 1.0) & (allc <= pb[3:] + 1.0), 1))[0]
        on = np.zeros(len(T), bool)
        on[near] = _on_surface(allc[near], tri_array(piece), tol=0.05) >= 0
        return on
    on_p = where(r['piece'])
    side = fm[0]
    if arT[side & on_p].sum() < arT[~side & on_p].sum():
        side = ~side                                  # a área achada é o lado do corpo: a peça é o outro lado
    if _CONF_PELE and _MODEL_T[0] is not None and len(_MODEL_T[0]) != len(T):
        # numa peça já recortada, as faces de corte de antes (a nuca sob o cabelo) não são pele: não contam
        pele = _on_surface(allc, _MODEL_T[0], tol=0.05) >= 0
        far = far & pele
    stolen = float(arT[~side & on_p & far].sum())
    own = float(arT[side & on_p].sum())
    if stolen <= max(1.5 * k2, 0.01 * own):
        return None
    try:
        rv = cut_by_mask_volume(host['mesh'], S, side, dict(cut, _de_linhas=True), diag, np.concatenate(loops), loops, centro)
    except Exception:
        traceback.print_exc()
        return None
    if not rv.get('ok') or rv.get('piece') is None:
        return None
    on2 = where(rv['piece'])
    stolen2 = float(arT[~side & on2 & far].sum())
    lost2 = float(arT[side & ~on2 & far & on_p].sum())
    n1 = len(E.parts(r['piece'], 1.0 * _CUR_K[0] ** 3) or [r['piece']])
    n2 = len(E.parts(rv['piece'], 1.0 * _CUR_K[0] ** 3) or [rv['piece']])
    if _DBG:
        print('recut_if_stolen: roubada', round(stolen, 1), '->', round(stolen2, 1), 'perdida', round(lost2, 1), 'partes', n1, n2, flush=True)
    if stolen2 > 0.3 * stolen or lost2 > max(1.5 * k2, 0.02 * own) or n2 > n1:
        return None
    rv['checks'] = [_chk('ok', f'A face lisa do corte levava para a peça {_fmt(stolen, 0)} mm² de superfície de fora da linha (a barra '
                               'da manga, por exemplo): o corte foi refeito pelo volume e a roupa ficou no corpo.')] + \
        [x for x in rv.get('checks', []) if 'menor superfície que passa' not in x['texto'] and 'A marcação tem' not in x['texto']]
    rv['_refeito_vol'] = True                         # o soquete confere se a linha passa por baixo da roupa
    return rv


def _fix_appendages(r, host, S, gap=0.2, rmin=1.3, want=None, loops=None):
    """Abas finas que a face do corte separou do lugar delas (uma orelha cuja borda está na linha):
    uma parte fina (menos de 2*rmin) junto do corte que encosta mais na peça do outro lado do que no
    resto da própria peça vai para o outro lado. A orelha fica com o rosto, não com o cabelo."""
    from scipy.ndimage import distance_transform_edt, gaussian_filter, label, binary_dilation
    piece, bodies = r['piece'], list(r['body_parts'])
    if not bodies or want is None or S is None:
        return r, 0.0
    from scipy.spatial import cKDTree
    ST = tri_array(S)
    want = np.asarray(want, bool)
    # antes de tudo: há superfície junto da linha do lado errado? (rápido; quase sempre não há)
    stc = ST.mean(1)
    if loops:
        dl0, _ = cKDTree(np.concatenate(loops)).query(stc, distance_upper_bound=5.0)
        q = np.where(np.isfinite(dl0))[0]
    else:
        q = np.where(want)[0]
    if not len(q):
        return r, 0.0
    hb0 = np.array(host.bounding_box())
    q = q[np.all((stc[q] >= hb0[:3] - 0.5) & (stc[q] <= hb0[3:] + 0.5), 1)]
    if not len(q):
        return r, 0.0
    q = q[_on_surface(stc[q], tri_array(host), tol=0.05) >= 0]
    if not len(q):
        return r, 0.0
    onq = _on_surface(stc[q], tri_array(piece), tol=0.05) >= 0
    arq = np.linalg.norm(np.cross(ST[q, 1] - ST[q, 0], ST[q, 2] - ST[q, 0]), axis=1) / 2
    badq = (want[q] & ~onq) | (~want[q] & onq)
    if loops:
        badq &= dl0[q] > 1.0                               # junto da linha a borda pode variar um pouco
    if arq[badq].sum() < 1.5:
        return r, 0.0
    bc = stc[q[badq]]
    PT = tri_array(piece)
    pc = PT.mean(1)
    inb = np.all((pc >= bc.min(0) - 10.0) & (pc <= bc.max(0) + 10.0), 1)
    PT = PT[inb]
    on = _on_surface(PT.mean(1), ST, tol=0.05) >= 0
    seam = PT[~on]
    if len(seam) < 3:
        return r, 0.0
    lo, hi = bc.min(0) - 8.0, bc.max(0) + 8.0
    hb = np.array(host.bounding_box())
    lo, hi = np.maximum(lo, hb[:3] - 1), np.minimum(hi, hb[3:] + 1)
    ext = hi - lo
    step = float(max(0.15, (np.prod(ext) / 3.0e6) ** (1 / 3)))
    if step > 0.45:
        return r, 0.0
    xs, ys, zs = [lo[k] + step * np.arange(int(np.ceil(ext[k] / step)) + 1) for k in range(3)]
    n = (len(xs), len(ys), len(zs))
    boxm = mf.Manifold.cube(list(hi - lo + 2 * step)).translate(list(lo - step))
    ip = _voxelize(E.flat(piece ^ boxm), xs, ys, zs)
    ib = np.zeros(n, bool)
    for b in bodies:
        bb_ = np.array(b.bounding_box())
        if np.any(bb_[3:] < lo) or np.any(bb_[:3] > hi):
            continue
        ib |= _voxelize(E.flat(b ^ boxm), xs, ys, zs)
    occ = np.zeros(n, bool)
    cc = seam.mean(1)
    ijk = np.round((cc - lo) / step).astype(int)
    ok = np.all((ijk >= 0) & (ijk < np.array(n)), 1)
    occ[tuple(ijk[ok].T)] = True
    near = distance_transform_edt(~occ, sampling=step) <= 1.0
    # partes finas do MODELO (não de cada peça) que o corte atravessa: cada uma vai inteira para o lado
    # que tem mais da superfície dela (a orelha: a frente, maior, é do rosto)
    ih = _voxelize(E.flat(host ^ boxm), xs, ys, zs)      # o modelo inteiro (a fresta do corte não conta)
    core = distance_transform_edt(ih, sampling=step) > rmin
    opened = distance_transform_edt(~core, sampling=step) <= rmin + 0.5 * step
    lb, k = label(ih & ~opened)
    cand = []
    if k:
        sel_t = np.all((ST.mean(1) >= lo) & (ST.mean(1) <= hi), 1)
        Ts = ST[sel_t]
        tc = Ts.mean(1)
        ta = np.linalg.norm(np.cross(Ts[:, 1] - Ts[:, 0], Ts[:, 2] - Ts[:, 0]), axis=1) / 2
        onp = _on_surface(tc, PT, tol=0.05) >= 0
        tij = np.clip(np.round((tc - lo) / step).astype(int), 0, np.array(n) - 1)
        tl = lb[tuple(tij.T)]
        # um triângulo da superfície pode cair num voxel vizinho de fora: procura o rótulo em volta
        miss = tl == 0
        if miss.any():
            for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                q = np.clip(tij[miss] + np.array(d), 0, np.array(n) - 1)
                v = lb[tuple(q.T)]
                put = (tl[miss] == 0) & (v > 0)
                idx = np.where(miss)[0][put]
                tl[idx] = v[put]
        on_host = _on_surface(tc, tri_array(host), tol=0.05) >= 0
        wt = want[np.where(sel_t)[0]] & on_host
        wb = ~want[np.where(sel_t)[0]] & on_host
        ap = np.bincount(tl, weights=ta * wt, minlength=k + 1)       # superfície que deveria ser da peça
        ab = np.bincount(tl, weights=ta * wb, minlength=k + 1)
        bad = (wt & ~onp) | (wb & onp)
        if loops:
            dl_, _ = cKDTree(np.concatenate(loops)).query(tc)
            bad &= (dl_ <= 5.0) & (dl_ > 1.0)              # junto da linha desenhada, fora da borda
        mis = np.bincount(tl, weights=ta * bad, minlength=k + 1)   # e está do outro lado
        for c in range(1, k + 1):
            tot = ap[c] + ab[c]
            if tot < 2.0 or mis[c] < max(1.0, 0.15 * tot):
                continue                                  # o corte já deixou a superfície onde a linha manda
            m = lb == c
            vol = float(m.sum()) * step ** 3
            if vol > 150.0 or not (m & near).any():
                continue
            fp = ap[c] / tot
            if 2.0 * vol / tot > 2 * rmin + 0.6:
                continue                                  # não é aba (pouca superfície para o volume): parede de soquete
            if 0.12 < fp < 0.88:
                # a aba inteira (com a fresta do corte no meio dela) muda de lado
                mm = binary_dilation(m, iterations=2)
                cand.append((mm, 'b' if fp >= 0.5 else 'p', vol))

    def solid(mask, off=0.0):
        sd = distance_transform_edt(mask, sampling=step) - distance_transform_edt(~mask, sampling=step)
        Fv = gaussian_filter(sd, 0.7) + off
        return _mc_manifold(np.pad(Fv.astype(np.float32), 1, constant_values=-10.0), step, lo, 6, 'aba')
    moved = 0.0
    ncomp = lambda ms: sum(len(E.parts(m, 0.05) or [m]) for m in ms)
    try:
        for mask, frm, vol in cand:
            Mv, Mg = solid(mask), solid(mask, gap)
            src = piece if frm == 'p' else E.union(bodies) if len(bodies) > 1 else bodies[0]
            add = E.flat(src ^ Mv)                       # o que muda de lado de verdade
            av = _vol(add) if not add.is_empty() else 0.0
            if av <= 0.05 or av > max(1.0, 0.6 * vol) or av > 25.0:
                continue                                  # mudaria mais do que a aba: não é uma aba solta
            add = E.flat(host ^ Mv)
            if frm == 'p':
                p2, b2 = E.flat(piece - Mg), [E.flat(bodies[0] + add)] + bodies[1:]
            else:
                b2, p2 = [E.flat(b - Mg) for b in bodies], E.flat(piece + add)
            if ncomp([p2]) <= ncomp([piece]) and ncomp(b2) <= ncomp(bodies):
                piece, bodies = p2, b2
                moved += av
    except Exception:
        traceback.print_exc()
        return r, 0.0
    if moved <= 0:
        return r, 0.0
    bodies = sorted([q for b in bodies for q in (E.parts(b, 0.5) or [b])], key=lambda q: -_vol(q))
    return dict(r, piece=piece, body_parts=bodies), moved


def _fix_slivers(r, host, S, rmin=0.4, gap=0.2):
    """Arestas finas junto do corte (abas de pele, pontas em cunha) não imprimem e tiram definição.
    Junto das faces do corte, o que é mais fino que 2*rmin numa peça passa para a peça do lado (a
    abertura morfológica de cada lado), mantendo a folga. Detalhes finos longe do corte não mudam."""
    from scipy.ndimage import distance_transform_edt, gaussian_filter
    piece, bodies = r['piece'], list(r['body_parts'])
    if not bodies:
        return r, 0.0
    ST = tri_array(S) if S is not None else tri_array(host)
    PT = tri_array(piece)
    on = _on_surface(PT.mean(1), ST, tol=0.05) >= 0
    seam = PT[~on].reshape(-1, 3)
    if len(seam) < 3:
        return r, 0.0
    pb = np.array(piece.bounding_box())
    lo = np.maximum(seam.min(0) - 1.5, pb[:3] - 1.5)
    hi = np.minimum(seam.max(0) + 1.5, pb[3:] + 1.5)
    ext = hi - lo
    step = float(max(0.12, (np.prod(ext) / 2.5e6) ** (1 / 3)))
    if step <= 2 * rmin * 0.6:
        return _fix_slivers_box(r, host, piece, bodies, seam, lo, hi, step, rmin, gap, 0.3)
    # costura grande (calça, modelo ampliado): a grade da caixa toda fica grossa demais para medir
    # arestas finas. Mede em blocos pequenos só onde há costura, com a grade fina.
    k3 = _CUR_K[0] ** 3
    st = max(0.12 * _CUR_K[0], 0.5 * rmin)
    mg = 4 * rmin + 2 * st                         # só a faixa junto da costura importa (com folga para a borda do bloco)
    tile = st * (4e5 ** (1 / 3)) - 2 * mg
    if tile <= 4 * rmin:
        return r, 0.0
    cc = seam.reshape(-1, 3, 3).mean(1)
    key = np.floor((cc - lo) / tile).astype(int)
    moved = 0.0
    rr = r
    for kk in np.unique(key, axis=0)[:400]:
        sub = np.all(key == kk, axis=1)
        if sub.sum() < 2:
            continue
        sm = seam.reshape(-1, 3, 3)[sub].reshape(-1, 3)
        tlo = np.maximum(sm.min(0) - mg, pb[:3] - mg)
        thi = np.minimum(sm.max(0) + mg, pb[3:] + mg)
        stp = float(max(st, (np.prod(thi - tlo) / 4e5) ** (1 / 3)))
        if stp > 2 * rmin * 0.6:
            continue
        rr, mv = _fix_slivers_box(rr, host, rr['piece'], list(rr['body_parts']), sm, tlo, thi, stp, rmin, gap, 0.3 * k3)
        moved += mv
    return rr, moved


def _escondida(M, outras, rmin, perto=1.6, frac=0.75):
    """A aba fica escondida pela outra peça na montagem: quase toda a superfície dela tem a outra peça a
    menos de 'perto' mm (ela fica entre as duas, como a lâmina por baixo de uma barra), e é pequena."""
    from scipy.spatial import cKDTree
    k = _CUR_K[0]
    if _vol(M) > 6.0 * k ** 3:
        return False
    P = tri_array(M).mean(1)
    if not len(P):
        return False
    bb = np.array(M.bounding_box())
    lo, hi = bb[:3] - 2.0 * k, bb[3:] + 2.0 * k
    Q = []
    for o in outras:
        T = _tris_box(o, lo, hi)
        if len(T):
            Q.append(np.concatenate([T.mean(1), T.reshape(-1, 3)]))
    if not Q:
        return False
    d, _ = cKDTree(np.concatenate(Q)).query(P, distance_upper_bound=perto * k)
    return bool(np.mean(np.isfinite(d)) >= frac)


def _fix_slivers_box(r, host, piece, bodies, seam, lo, hi, step, rmin, gap, vmin):
    from scipy.ndimage import distance_transform_edt, gaussian_filter
    if not bodies:
        return r, 0.0
    ext = hi - lo
    xs, ys, zs = [lo[k] + step * np.arange(int(np.ceil(ext[k] / step)) + 1) for k in range(3)]
    n = (len(xs), len(ys), len(zs))
    occ = np.zeros(n, bool)
    cc = seam.reshape(-1, 3, 3).mean(1)
    smp = np.concatenate([cc] + [seam.reshape(-1, 3, 3)[:, k] * 0.5 + cc * 0.5 for k in range(3)])
    ijk = np.round((smp - lo) / step).astype(int)
    ok = np.all((ijk >= 0) & (ijk < np.array(n)), 1)
    occ[tuple(ijk[ok].T)] = True
    near = distance_transform_edt(~occ, sampling=step) <= 2 * rmin

    def thin(ins):
        core = distance_transform_edt(ins, sampling=step) > rmin
        opened = distance_transform_edt(~core, sampling=step) <= rmin + 0.5 * step
        return ins & ~opened & near

    boxm = mf.Manifold.cube(list(hi - lo + 2 * step)).translate(list(lo - step))
    ip = _voxelize(E.flat(piece ^ boxm), xs, ys, zs)          # só a caixa da costura (rápido)
    ib = np.zeros(n, bool)
    for b in bodies:
        bb_ = np.array(b.bounding_box())
        if np.any(bb_[3:] < lo) or np.any(bb_[:3] > hi):
            continue
        ib |= _voxelize(E.flat(b ^ boxm), xs, ys, zs)
    sp, sb = thin(ip), thin(ib)

    def solid(mask, off=0.0):
        sd = distance_transform_edt(mask, sampling=step) - distance_transform_edt(~mask, sampling=step)
        Fv = gaussian_filter(sd, 0.8) + off
        if (Fv > 0).sum() < 2:
            return None
        return _mc_manifold(np.pad(Fv.astype(np.float32), 1, constant_values=-10.0), step, lo, 6, 'aresta')
    moved = 0.0
    ncomp = lambda ms: sum(len(E.parts(m, 0.05) or [m]) for m in ms)
    cnt0 = []                                     # partes antes da troca (contadas só quando há o que trocar)

    def n0():
        if not cnt0:
            cnt0.extend([ncomp([piece]), ncomp(bodies)])
        return cnt0
    try:
        if sp.sum() >= 4:
            Mp = solid(sp)
            if Mp is not None and vmin <= Mp.volume() < 0.05 * _vol(piece):       # aba de verdade, não ruído
                np0, nb0 = n0()
                Mpg = solid(sp, gap)
                add = E.flat(host ^ Mp)
                p2 = E.flat(piece - Mpg)
                b2 = [E.flat(bodies[0] + add)] + bodies[1:]
                if ncomp([p2]) <= np0 and ncomp(b2) <= nb0:      # sem soltar lascas
                    piece, bodies = p2, b2
                    moved += Mp.volume()
                elif _ABA_ESCONDIDA and ncomp([p2]) <= np0 and _escondida(Mp, bodies, rmin):
                    # aba fina presa na borda que ficaria solta do outro lado (a lâmina da calça por baixo da
                    # barra da camisa): ela fica coberta pela outra peça na montagem; sai da peça
                    piece = p2
                    moved += Mp.volume()
        if sb.sum() >= 4:
            Mb = solid(sb)
            if Mb is not None and vmin <= Mb.volume() < 0.05 * _vol(bodies[0]):
                np0, nb0 = n0()
                Mbg = solid(sb, gap)
                add = E.flat(host ^ Mb)
                b2 = [E.flat(b - Mbg) for b in bodies]
                p2 = E.flat(piece + add)
                if ncomp([p2]) <= np0 and ncomp(b2) <= nb0:
                    piece, bodies = p2, b2
                    moved += Mb.volume()
                elif _ABA_ESCONDIDA and ncomp(b2) <= nb0 and _escondida(Mb, [piece], rmin):
                    bodies = b2
                    moved += Mb.volume()
    except Exception:
        traceback.print_exc()
        return r, 0.0
    if moved <= 0:
        return r, 0.0
    bodies = sorted([q for b in bodies for q in (E.parts(b, 0.5) or [b])], key=lambda q: -_vol(q))
    return dict(r, piece=piece, body_parts=bodies), moved


# ----------------------------------------------------------------------------- escala
# As regras do corte (distâncias para achar a superfície, faixas junto da linha, grades de voxels)
# foram acertadas em modelos de 60 a 150 mm. Num modelo bem maior elas mudariam o resultado (a
# cabeça, as tranças). Então o corte é feito numa cópia do modelo no tamanho de referência e o
# resultado volta para o tamanho real. As medidas físicas (folgas, parede, soquete, pino) são
# convertidas para que saiam exatas em mm no modelo real.
REF_DIAG = 140.0
_CUR_K = [1.0]                # escala da cópia em uso (as lascas de 2 mm³ são medidas no tamanho real)
FISICOS = ('folga', 'folga_pino', 'pino_mm', 'soquete_mm', 'parede')


def _scale_factor(S):
    bb = np.array(S.bounding_box())
    diag = float(np.linalg.norm(bb[3:] - bb[:3]))
    return REF_DIAG / diag if diag > 1.6 * REF_DIAG else 1.0


def _D(k):
    return np.diag([k, k, k, 1.0])


def _fix_text(t, k, snap=()):
    import re
    inv = 1.0 / k

    def rep(m):
        v = float(m.group(1).replace('.', '').replace(',', '.')) if ',' in m.group(1) else float(m.group(1))
        u = m.group(2)
        f = inv ** 3 if u == 'mm³' else inv ** 2 if u == 'mm²' else inv
        nd = len(m.group(1).split(',')[1]) if ',' in m.group(1) else 0
        x = v * f
        if u == 'mm³' and nd > 1:                            # volume medido com mais casas na cópia
            nd = 1
        if u == 'mm':
            for y in snap:                                   # a folga e o soquete pedidos saem exatos
                if y and abs(x - y) <= 0.06 * y + 0.5 * 10 ** (-nd) / k:
                    x = y
                    break
        return (f'{x:.{nd}f}'.replace('.', ',') if nd else f'{round(x):d}') + ' ' + u
    return re.sub(r'(\d+(?:,\d+)?) ?(mm³|mm²|mm)(?![\w])', rep, t)


def _drop_sheets(M):
    """Tira folhas de espessura zero (pares de triângulos iguais e opostos, presos numa aresta)."""
    mm = M.to_mesh()
    v = np.asarray(mm.vert_properties)[:, :3].astype(np.float64)
    f = np.asarray(mm.tri_verts).astype(np.int64)
    q = np.round(v / 1e-4).astype(np.int64)
    _, vid = np.unique(q, axis=0, return_inverse=True)
    vid = vid.ravel()
    ff = vid[f]
    key = np.sort(ff, axis=1)
    _, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    inv = inv.ravel()
    dup = cnt[inv] >= 2
    if not dup.any():
        return M
    keep = ~dup
    used, newi = np.unique(ff[keep], return_inverse=True)
    pos = np.zeros((vid.max() + 1, 3))
    pos[vid] = v
    m2 = mf.Manifold(mf.Mesh(vert_properties=np.ascontiguousarray(pos[used], np.float32),
                             tri_verts=np.ascontiguousarray(newi.reshape(-1, 3), np.uint32)))
    if m2.status() != mf.Error.NoError or m2.is_empty():
        return M
    return m2


def _clean_pieces(o, before):
    """Malha final de cada peça que um corte mexeu: sem os pares de triângulos de área zero que os
    cortes às vezes deixam presos num vértice (o fatiador acusaria malha aberta)."""
    old = {id(p['mesh']) for p in before}
    for p in o['pieces']:
        if id(p['mesh']) in old or p.get('tipo') == 'cavilha':
            continue
        try:
            m2 = _drop_sheets(p['mesh'].simplify(2e-3))      # 2 µm: nada que a impressora veja
            if m2.status() != mf.Error.NoError or m2.is_empty():
                continue
            if abs(m2.volume() - p['mesh'].volume()) > 1e-3 * max(1.0, abs(p['mesh'].volume())):
                continue
            if p.get('T') is not None and p.get('paint') is not None:
                p['T'], p['paint'] = _paint_from(p['T'], p['paint'], m2, p.get('base', 1))
            else:
                p['T'] = tri_array(m2)
            p['mesh'] = m2
        except Exception:
            traceback.print_exc()
    return o


def _base_check(o):
    """O corpo imprime em pé, na posição do modelo. Se depois dos cortes ele ficar apoiado só em pontas
    finas (cordões, a ponta da faixa) bem abaixo da base de verdade, avisa: assim ele não para em pé."""
    bodies = [p for p in o['pieces'] if p.get('tipo') == 'corpo']
    if not bodies or not o.get('livres'):
        return o
    b = max(bodies, key=lambda p: len(p['T']))
    T = np.asarray(b['T'], np.float64)
    if not len(T):
        return o
    nz = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    ar = np.linalg.norm(nz, axis=1) / 2
    down = nz[:, 2] < -0.7 * np.maximum(np.linalg.norm(nz, axis=1), 1e-12)
    zc = T[:, :, 2].min(1)
    z0 = float(T[:, :, 2].min())
    ext = T.reshape(-1, 3).max(0) - T.reshape(-1, 3).min(0)
    need = 0.03 * float(ext[0] * ext[1])
    for zz in np.arange(z0, z0 + 0.5 * ext[2], max(0.2, 0.002 * ext[2])):
        a = float(ar[down & (zc <= zz + 0.5)].sum())
        if a >= need:
            gap = zz - z0
            if gap > max(2.0, 0.03 * ext[2]):
                last = [r for r in o['livres'] if r.get('ok')]
                if last:
                    last[-1]['checks'] = last[-1].get('checks', []) + [_chk('aviso',
                        f'O corpo, de pé na mesa, fica apoiado em pontas finas (cordões, a ponta da faixa) {_fmt(gap, 1)} mm abaixo da base '
                        'de verdade: ele não para em pé sem suporte. Corte essas pontas junto com a peça de baixo ou imprima com suporte.')]
            break
    return o


# ---------------------------------------------------------------- flexi que já veio articulado
# Um flexi pronto (print in place) chega com várias cascas soltas que se encaixam, separadas só pela
# folga da junta. Depois de um corte, cada parte do corpo virava uma peça própria e a exportação as
# espalhava na mesa (e girava cada uma), desmontando as juntas. Aqui as partes que já eram cascas
# diferentes no modelo original e ficam a menos de GAP_CASCAS mm uma da outra voltam a ser uma peça só,
# na posição do modelo. Partes da mesma casca separadas pelo corte continuam separadas.
GAP_CASCAS = 1.5


def _cascas_idx(S):
    """Índice das cascas do modelo original (árvore dos vértices e o número da casca de cada um)."""
    from scipy.spatial import cKDTree
    shells = E.parts(S, 0.5)
    if len(shells) <= 1:
        return None
    pts, lab = [], []
    for k, sh in enumerate(shells):
        v = E.mesh_arrays(sh)[0]
        pts.append(v); lab.append(np.full(len(v), k))
    return cKDTree(np.vstack(pts)), np.concatenate(lab)


def _casca_de(m, idx):
    """Casca do modelo original de onde a malha veio (a maioria dos vértices que estão na pele original)."""
    tree, lab = idx
    v = E.mesh_arrays(m)[0]
    if len(v) > 4000:
        v = v[np.linspace(0, len(v) - 1, 4000).astype(int)]
    d, i = tree.query(v)
    na = d < 0.05
    ls = lab[i[na]] if na.any() else lab[i[[int(np.argmin(d))]]]
    return int(np.bincount(ls).argmax())


def _encostam(a, b, gap):
    from scipy.spatial import cKDTree
    ba, bb = np.array(a.bounding_box()), np.array(b.bounding_box())
    if np.any(ba[:3] - gap > bb[3:]) or np.any(bb[:3] - gap > ba[3:]):
        return False
    va, vb = E.mesh_arrays(a)[0], E.mesh_arrays(b)[0]
    d, _ = cKDTree(vb).query(va, distance_upper_bound=gap)
    return bool(np.isfinite(d).any())


def _reagrupar_cascas(o, S, cuts=None):
    """Junta de volta as partes do corpo (e as partes 'soltas' de um corte) que eram cascas diferentes
    no modelo e se encaixam: as juntas de um flexi que já veio articulado ficam montadas."""
    try:
        idx = _cascas_idx(S)
    except Exception:
        traceback.print_exc()
        return o
    if idx is None:
        return o
    pcs = list(o['pieces'])
    # casca inteira que o corte nem tocou (longe da linha) não é peça do corte: volta para o corpo. Sem
    # isso, num flexi a pata solta podia sair como "Corte 1 (2)" de um corte no pescoço
    if cuts:
        from scipy.spatial import cKDTree
        for k, p in enumerate(pcs):
            i = p.get('livre')
            if p.get('tipo') in ('corpo', 'cavilha') or i is None or not (0 <= i < len(cuts)):
                continue
            Ls = _loops_of(cuts[i])
            if not Ls or cuts[i].get('mascara'):           # área marcada: a peça pode ir além da linha
                continue
            v = E.mesh_arrays(p['mesh'])[0]
            d, _ = cKDTree(np.vstack(Ls)).query(v)
            if float(d.min()) > 2.0:
                pcs[k] = dict(p, tipo='corpo', nome='Corpo', livre=None)
    corpos = [k for k, p in enumerate(pcs) if p.get('tipo') == 'corpo']
    nomes = {p.get('nome'): k for k, p in enumerate(pcs)}
    soltas = [(k, nomes.get(p['nome'][:-len(' (solta)')])) for k, p in enumerate(pcs)
              if str(p.get('nome', '')).endswith(' (solta)')]
    soltas = [(k, m) for k, m in soltas if m is not None]
    if len(corpos) < 2 and not soltas:
        return o
    lab = {}
    def casca(k):
        if k not in lab:
            lab[k] = _casca_de(pcs[k]['mesh'], idx)
        return lab[k]
    pai = list(range(len(pcs)))
    def raiz(k):
        while pai[k] != k:
            pai[k] = pai[pai[k]]; k = pai[k]
        return k
    for a_ in range(len(corpos)):
        for b_ in range(a_ + 1, len(corpos)):
            i, j = corpos[a_], corpos[b_]
            if raiz(i) != raiz(j) and casca(i) != casca(j) and _encostam(pcs[i]['mesh'], pcs[j]['mesh'], GAP_CASCAS):
                pai[raiz(j)] = raiz(i)
    for k, m in soltas:
        if raiz(k) != raiz(m) and casca(k) != casca(m) and _encostam(pcs[k]['mesh'], pcs[m]['mesh'], GAP_CASCAS):
            pai[raiz(k)] = raiz(m)
    grupos = {}
    for k in range(len(pcs)):
        grupos.setdefault(raiz(k), []).append(k)
    if all(len(g) == 1 for g in grupos.values()) and pcs == list(o['pieces']):
        return o
    novo, feito = [], set()
    for k, p in enumerate(pcs):
        r = raiz(k)
        if r in feito:
            continue
        feito.add(r)
        g = grupos[r]
        if len(g) == 1:
            novo.append(p); continue
        base = max(g, key=lambda q: _vol(pcs[q]['mesh']))
        mesh = E.flat(E.union([pcs[q]['mesh'] for q in g]))
        Ts = [np.asarray(pcs[q]['T']) for q in g if pcs[q].get('T') is not None]
        Ps = [pcs[q].get('paint') for q in g]
        tri = np.concatenate(Ts) if len(Ts) == len(g) else tri_array(mesh)
        tinta = (np.concatenate([np.asarray(x) for x in Ps]) if all(x is not None for x in Ps) and len(Ts) == len(g) else None)
        q_ = dict(pcs[base], mesh=mesh, T=tri, paint=tinta, conjunto=True)
        if not any('paint' in pcs[q] for q in g):
            q_.pop('paint')
        novo.append(q_)
    # os nomes do corpo voltam a ser seguidos (Corpo, Corpo 2, ...)
    cs = [p for p in novo if p.get('tipo') == 'corpo']
    raiz_nome = re.sub(r' \d+$', '', cs[0]['nome']) if cs else 'Corpo'
    for n, p in enumerate(cs):
        p['nome'] = raiz_nome + (f' {n + 1}' if len(cs) > 1 else '')
    return dict(o, pieces=novo)


def apply(out, cuts, S, progress=None, snap_key=None):
    """Aplica os cortes livres e os planos. Num modelo muito maior que o de referência, corta numa
    cópia em escala e devolve no tamanho real (o mesmo resultado em qualquer tamanho).
    snap_key: guarda as peças como estão antes de cada corte numa peça (e no fim), para a tela
    desenhar e marcar sobre exatamente a malha que o corte vai usar (host_piece)."""
    _SNAP_CTX[0] = (snap_key, cuts_sigs(cuts), list(cuts)) if snap_key is not None else None
    try:
        return _base_check(_reagrupar_cascas(_clean_pieces(_apply_scaled(out, cuts, S, progress), out['pieces']), S, cuts))
    finally:
        _SNAP_CTX[0] = None


# ---------------------------------------------------------------- a peça antes de um corte
# Corte numa peça já recortada: a marcação (linha, pincel, balde) é feita na tela sobre a malha da
# peça, e a área marcada é uma lista de triângulos dessa malha. A tela recebe exatamente a malha que
# o corte vai usar: a peça como está antes dele, guardada durante o último apply (ou calculada de
# novo, com o mesmo código). Só guarda referências às malhas (não copia nada).
_SNAP = {}
_SNAP_CTX = [None]


def cuts_sigs(cuts):
    """Assinatura de cada prefixo da lista de cortes: sig[i] identifica cuts[:i]."""
    import hashlib
    import json as _json_
    h = hashlib.sha1(b'cortes')
    out = [h.hexdigest()]
    for c in cuts:
        h.update(_json_.dumps({k: v for k, v in c.items() if not str(k).startswith('_')}, sort_keys=True, default=str).encode())
        out.append(h.hexdigest())
    return out


def _snap(i, cur):
    ctx = _SNAP_CTX[0]
    if ctx is None:
        return
    _SNAP[(ctx[0], ctx[1][i])] = ([dict(mesh=p['mesh'], tipo=p.get('tipo'), nome=p.get('nome'), T=p.get('T')) for p in cur['pieces']], _CUR_K[0])
    while len(_SNAP) > 24:
        _SNAP.pop(next(iter(_SNAP)))


def host_piece(snap_key, before, ponto, pieces=None):
    """(triângulos da peça no tamanho real, nome) da peça em que está o ponto, como ela está depois dos
    cortes `before`; None se essa situação não foi guardada (pieces: as peças sem nenhum corte livre)."""
    if pieces is not None:
        ent = ([dict(mesh=p['mesh'], tipo=p.get('tipo'), nome=p.get('nome'), T=p.get('T')) for p in pieces], 1.0)
    else:
        ent = _SNAP.get((snap_key, cuts_sigs(before)[-1]))
    if ent is None:
        return None
    pcs, k = ent
    k0 = _CUR_K[0]
    _CUR_K[0] = k
    try:
        for pc in pcs:
            if pc.get('T') is None:
                pc['T'] = SPL.tri_array(pc['mesh'])
        j = _piece_at(pcs, [float(v) * k for v in ponto])
    finally:
        _CUR_K[0] = k0
    if j < 0:
        return False
    return SPL.tri_array(pcs[j]['mesh']) / k, pcs[j].get('nome')


# ------------------------------------------------------------- motor 2: cortes independentes da ordem
# Cada corte livre é calculado sozinho sobre o mesmo ponto de partida (depois do corte por cor) e as peças
# são resolvidas juntas por interseção: o resultado depende só das linhas, nunca da ordem em que os cortes
# foram criados. Os encaixes entram no fim, junta por junta. FLEXI_MOTOR2=0 volta ao motor em cadeia.
_MOTOR2 = _os.environ.get('FLEXI_MOTOR2', '0') == '1'
_RE_SEP = re.compile(b'^Pe\xc3\xa7a separada: [0-9.,]+ mm\xc2\xb3 \\([0-9]+% da parte\\)'.decode('utf-8'))


def _loops_of(cut):
    return [np.asarray(L['p'] if isinstance(L, dict) else L, np.float64) for L in (cut.get('linhas') or [])
            if len(L['p'] if isinstance(L, dict) else L) >= 3]


def _run_alone(state, cut, S, outras, inverter=None):
    """O corte sozinho sobre `state`, sem soquete. Devolve dict(r, new, H, host_ids) ou None."""
    c = dict(cut, soquete=False, _outras_linhas=outras)
    if inverter is not None:
        c['inverter'] = inverter
    st = dict(state, pieces=[dict(p, _orig=True) for p in state['pieces']])
    base_ids = {id(p['mesh']) for p in st['pieces']}
    ctx, _SNAP_CTX[0] = _SNAP_CTX[0], None          # as fotos para a tela são do motor 2, não deste corte sozinho
    try:
        o = _apply_cuts(st, [c], S, None)
    except Exception:
        traceback.print_exc()
        return None
    finally:
        _SNAP_CTX[0] = ctx
    # o resultado do corte sozinho guarda o corpo inteiro: só ficam os avisos e o que a tela usa
    r = {k: v for k, v in o['livres'][0].items() if k not in ('piece', 'body_parts', 'extra')}
    new = [p for p in o['pieces'] if not p.get('_orig')]
    H = [p for p in o['pieces'] if p.get('_orig') and id(p['mesh']) not in base_ids]
    kept = {id(p['mesh']) for p in o['pieces'] if p.get('_orig') and id(p['mesh']) in base_ids}
    host_ids = [id(p['mesh']) for p in st['pieces'] if id(p['mesh']) not in kept]
    for p in new + H:
        p.pop('_orig', None)
        p['mesh'] = E.flat(p['mesh'])            # sem a árvore de contas que prende o corpo inteiro na memória
    return dict(r=r, new=new, H=H, host_ids=host_ids)


_T0 = [0.0]


def _mem(tag):
    if _DBG:
        import resource
        try:
            cur = int(open('/proc/self/statm').read().split()[1]) * 4096 // 2 ** 20
        except Exception:
            cur = -1
        try:
            import ctypes

            class _MI(ctypes.Structure):
                _fields_ = [(k, ctypes.c_size_t) for k in ('arena', 'ordblks', 'smblks', 'hblks', 'hblkhd', 'usmblks',
                                                           'fsmblks', 'uordblks', 'fordblks', 'keepcost')]
            lc = ctypes.CDLL('libc.so.6')
            lc.mallinfo2.restype = _MI
            mi = lc.mallinfo2()
            used = (mi.uordblks + mi.hblkhd) // 2 ** 20
        except Exception:
            used = -1
        print('motor2:', tag, round(time.time() - _T0[0]), 's usado', used, 'MB, mem', cur, 'MB, max', resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024, 'MB', flush=True)


def _free_mem():
    """Entre um corte e outro: solta as contas guardadas (refeitas se precisar) e o lixo."""
    import gc
    _MFL_CACHE.clear()
    _HT_CACHE.clear()
    _HT_OFF.clear()
    gc.collect()
    _trim()


def _trim():
    """Devolve ao sistema a memória que o Python e as malhas soltaram (no Linux o alocador segura)."""
    try:
        import ctypes, sys as _sys
        if _sys.platform.startswith('linux'):
            ctypes.CDLL('libc.so.6').malloc_trim(0)
    except Exception:
        pass


def _compact(state, a):
    """Guarda só o que o corte tira do hospedeiro (a peça e a folga em volta), não o corpo inteiro: com
    muitos cortes num modelo grande, vários corpos inteiros na memória estouram."""
    if a is None or not a.get('new') or len(a.get('host_ids') or []) != 1:
        return a
    hm = next((p['mesh'] for p in state['pieces'] if id(p['mesh']) == a['host_ids'][0]), None)
    if hm is None:
        return a
    a['C'] = E.flat(hm - E.union([p['mesh'] for p in a['H']]))
    a['H'] = None
    return a


class _Pk:
    """Malha guardada só com os vértices e triângulos (uma fração da memória de um sólido pronto para
    contas). Volta a ser sólido quando precisa; a conta é a mesma de E.flat, a malha fica igual."""
    __slots__ = ('gl',)

    def __init__(self, m):
        self.gl = m.to_mesh()


def _pk(m):
    return _Pk(m) if isinstance(m, mf.Manifold) else m


def _up(m):
    return mf.Manifold(m.gl) if isinstance(m, _Pk) else m


def _pack(a):
    """Depois de cada corte sozinho: guarda as peças e o que o corte tira em forma compacta."""
    if a is None:
        return a
    for q in a.get('new') or []:
        q['mesh'] = _pk(q['mesh'])
    if a.get('C') is not None:
        a['C'] = _pk(a['C'])
    return a


def _skin_of(S_T, M):
    """Triângulos da pele original que estão na superfície de M."""
    return _on_surface(S_T.mean(1), tri_array(M), tol=0.05) >= 0


def _stage(state, idx, cuts, S, notes):
    """Resolve os cortes `idx` (todos sobre `state`) sem depender da ordem. Devolve o novo state e os resultados."""
    allL = [L for c in cuts for L in _loops_of(c)]
    res, info = {}, {}
    body_acc = {}
    flipped = set()
    for i in idx:
        cut = cuts[i]
        outras = [L for j, c in enumerate(cuts) if j != i for L in _loops_of(c)]
        a = _run_alone(state, cut, S, outras)
        if a is not None and a.get('new') and len(a.get('host_ids') or []) == 1 and a['r'].get('ok'):
            # o corpo final é a interseção dos restos de todos os cortes (conta exata, sem subtrair de volta)
            hid = a['host_ids'][0]
            hu = E.flat(E.union([p['mesh'] for p in a['H']]))
            body_acc[hid] = hu if hid not in body_acc else E.flat(body_acc[hid] ^ hu)
            hu = None
        res[i] = _pack(_compact(state, a))
        a = None
        _free_mem()
        _mem(i)
    ok = [i for i in idx if res[i] is not None and res[i]['r'].get('ok') and res[i]['new'] and len(res[i]['host_ids']) == 1]
    # lado da peça sem depender da ordem: o menor lado contado sem as peças que os outros cortes levam
    S_T = tri_array(S)
    ar = np.linalg.norm(np.cross(S_T[:, 1] - S_T[:, 0], S_T[:, 2] - S_T[:, 0]), axis=1) / 2
    for _round in range(2):
        own = {i: np.any([_skin_of(S_T, _up(p['mesh'])) for p in res[i]['new']], axis=0) for i in ok}
        hostskin = {}
        for i in ok:
            hid = res[i]['host_ids'][0]
            hm = next(p['mesh'] for p in state['pieces'] if id(p['mesh']) == hid)
            if hid not in hostskin:
                hostskin[hid] = _skin_of(S_T, hm)
        flips = []
        for i in ok:
            if cuts[i].get('mascara') or cuts[i].get('peca') or cuts[i].get('plano'):
                continue                       # área marcada: a peça é o que foi marcado
            hid = res[i]['host_ids'][0]
            side_p = own[i]
            side_o = hostskin[hid] & ~own[i]

            def core(side):
                inside = [j for j in ok if j != i and res[j]['host_ids'][0] == hid and own[j].any()
                          and ar[own[j] & side].sum() >= 0.8 * ar[own[j]].sum()]
                # só as maiores (uma peça dentro de outra que também conta não é descontada duas vezes)
                top = [j for j in inside if not any(k != j and ar[own[j] & own[k]].sum() >= 0.8 * ar[own[j]].sum()
                                                    and ar[own[k]].sum() > ar[own[j]].sum() for k in inside)]
                return ar[side].sum() - sum(ar[own[j] & side].sum() for j in top)
            cp, co = core(side_p), core(side_o)
            if cp > 1.2 * co and co > 0:
                flips.append(i)
        if not flips:
            break
        for i in flips:
            outras = [L for j, c in enumerate(cuts) if j != i for L in _loops_of(c)]
            a = _pack(_compact(state, _run_alone(state, cuts[i], S, outras, inverter=not bool(cuts[i].get('inverter')))))
            if a is not None and a['r'].get('ok') and a['new']:
                res[i] = a
                flipped.add(a['host_ids'][0])
                notes.setdefault(i, []).append(_chk('ok', 'Lado da peça escolhido pelo modelo inteiro (sem depender da ordem dos cortes): '
                                                          'a peça é o lado menor sem contar o que outros cortes levam.'))
    _mem('lados')
    # resolução por peça hospedeira: a peça menor (mais específica) manda onde duas se sobrepõem
    vols = {i: sum(_vol(_up(p['mesh'])) for p in res[i]['new']) for i in ok}
    pieces = []
    by_host = {}
    for i in ok:
        by_host.setdefault(res[i]['host_ids'][0], []).append(i)
    _Cu, _Pu = {}, {}

    def Cj(j):                                   # o que o corte j tira, como sólido (refeito uma vez)
        if j not in _Cu:
            _Cu[j] = _up(res[j]['C'])
        return _Cu[j]

    def Pj(j):                                   # as peças do corte j juntas, como sólido
        if j not in _Pu:
            _Pu[j] = E.union([_up(x['mesh']) for x in res[j]['new']])
        return _Pu[j]
    for p in state['pieces']:
        hid = id(p['mesh'])
        if hid not in by_host:
            pieces.append(p)
            continue
        group = sorted(by_host[hid], key=lambda j: (vols[j], j))
        body = p['mesh']
        if hid in body_acc and hid not in flipped:
            body = body_acc[hid]
        else:
            body = E.flat(body - E.union([Cj(j) for j in group]))
        newp = []
        for i in group:
            for q in res[i]['new']:
                m = _up(q['mesh'])
                bb = np.array(m.bounding_box())
                for j in group:
                    if j == i or (vols[j], j) >= (vols[i], i):
                        continue
                    pj = Pj(j)
                    pb = np.array(pj.bounding_box())
                    if np.any(bb[3:] < pb[:3]) or np.any(pb[3:] < bb[:3]):
                        continue
                    if _vol(m ^ pj) <= 0:
                        continue
                    m = E.flat(m - Cj(j))
                if not m.is_empty() and _vol(m) > 0:
                    T, col = _paint_from(p['T'], p['paint'], m, p['base']) if p.get('T') is not None else (tri_array(m), None)
                    newp.append(dict(q, mesh=m, T=T, paint=col if col is not None else q.get('paint'), livre=i))
        bparts = sorted([b for b in E.parts(body, 0.5) if _vol(b) >= 1.0], key=lambda b: -_vol(b))
        for k, b in enumerate(bparts):
            T, col = _paint_from(p['T'], p['paint'], b, p['base']) if p.get('T') is not None else (tri_array(b), p.get('paint'))
            pieces.append(dict(p, mesh=b, T=T, paint=col, nome=p['nome'] + (f' {k + 1}' if len(bparts) > 1 else '')))
        pieces += newp
    _mem('resolução')
    for i in idx:
        if res[i] is None:
            res[i] = dict(r=dict(ok=False, checks=[_chk('erro', 'O corte falhou.')]))
    return dict(state, pieces=pieces), {i: res[i]['r'] for i in idx}


def _crumbs(state, notes):
    """Peças em pedaços: o maior fica; pedacinho que encosta noutra peça vai com ela (sem criar túnel);
    farelo até 20 mm³ é descartado com aviso; pedaço maior vira peça própria."""
    from scipy.spatial import cKDTree
    K = _CUR_K[0]
    pcs = state['pieces']
    out, loose = [], []
    for p in pcs:
        if p.get('tipo') == 'cavilha':
            out.append(p)
            continue
        parts = sorted(E.parts(p['mesh'], 0.3), key=lambda q: -_vol(q))
        if len(parts) <= 1:
            out.append(p)
            continue
        out.append(dict(p, mesh=parts[0]))
        for q in parts[1:]:
            loose.append((p, q))
    for p, q in loose:
        v = _vol(q)
        qv = np.asarray(q.to_mesh().vert_properties)[:, :3]
        best, bd = None, np.inf
        for k, o in enumerate(out):
            ov = np.asarray(o['mesh'].to_mesh().vert_properties)[:, :3]
            d = float(cKDTree(ov).query(qv, k=1)[0].min())
            if d < bd:
                best, bd = k, d
        merged = False
        if best is not None and bd <= 0.35 * K and v <= 0.02 * _vol(out[best]['mesh']):
            m2 = E.flat(E.union([out[best]['mesh'], q]))
            if len(E.parts(m2, 0.3)) == 1 and m2.genus() <= out[best]['mesh'].genus():
                out[best] = dict(out[best], mesh=m2)
                merged = True
        if merged:
            continue
        i = p.get('livre')
        if v <= 20.0 * K ** 3:
            notes.setdefault(i, []).append(_chk('aviso', f'1 farelo pequeno ({_fmt(v, 1)} mm³) ficou solto junto da costura e foi '
                                                          'descartado; confira a costura na prévia.'))
            continue
        out.append(dict(p, mesh=q, nome=p['nome'] + ' (solta)'))
        notes.setdefault(i, []).append(_chk('aviso', f'Uma parte de {_fmt(v, 0)} mm³ ficou solta deste corte e vai como peça própria; confira na prévia.'))
    return dict(state, pieces=out)


def _sockets(state, cuts, S, diag, centro, notes, host0=None):
    """Soquete e pino padrão no fim, junta por junta, entre a peça do corte e a peça do outro lado da linha.
    Ordem fixa: a menor peça primeiro (não depende da ordem dos cortes)."""
    from scipy.spatial import cKDTree
    pcs = list(state['pieces'])
    host = host0 if host0 is not None else E.flat(E.union([p['mesh'] for p in pcs]))   # com as folgas entre as peças
    jobs = []
    for i, cut in enumerate(cuts):
        enc = cut.get('encaixe') if cut.get('encaixe') in ENCAIXES else 'colar'
        if not cut.get('soquete') or enc in GIRA or cut.get('plano') or cut.get('peca'):
            continue
        for k, p in enumerate(pcs):
            if p.get('livre') == i and p.get('tipo') != 'cavilha':
                jobs.append((_vol(p['mesh']), i, k))
    jobs.sort()
    allL = [L for c in cuts for L in _loops_of(c)]
    for _, i, k in jobs:
        cut = cuts[i]
        enc = cut.get('encaixe') if cut.get('encaixe') in ENCAIXES else 'colar'
        p = pcs[k]
        pv = np.asarray(p['mesh'].to_mesh().vert_properties)[:, :3]
        tr = cKDTree(pv)
        lim = float(cut.get('folga') or 0.2) + 0.5 * _CUR_K[0]
        loops = [L for L in (_clean_loop(x) for x in _loops_of(cut)) if L is not None and float(np.median(tr.query(L)[0])) <= lim]
        if not loops:
            continue
        # a peça do outro lado da linha
        cnt = []
        for j, q in enumerate(pcs):
            if j == k or q.get('tipo') == 'cavilha':
                cnt.append(0)
                continue
            qv = np.asarray(q['mesh'].to_mesh().vert_properties)[:, :3]
            d = cKDTree(qv).query(np.vstack(loops), k=1)[0]
            cnt.append(int((d <= lim).sum()))
        j = int(np.argmax(cnt))
        if cnt[j] == 0:
            continue
        # região permitida para o encaixe, só em volta da junta (contas pequenas): o modelo com as folgas,
        # menos as outras peças
        P_ = np.vstack(loops)
        mg = float(cut.get('soquete_mm') or 4.0 * _CUR_K[0]) + 10.0 * _CUR_K[0] + float(np.ptp(P_, axis=0).max())
        lo_, hi_ = P_.min(0) - mg, P_.max(0) + mg
        box = mf.Manifold.cube((hi_ - lo_).tolist()).translate(lo_.tolist())
        others = []
        for t, q in enumerate(pcs):
            if t in (k, j):
                continue
            qb = np.array(q['mesh'].bounding_box())
            if np.any(qb[3:] < lo_) or np.any(qb[:3] > hi_):
                continue
            others.append(q['mesh'] ^ box)
        if host.num_tri() > 300000:
            allowed = E.flat(host ^ box)           # modelo grande: só em volta da junta (memória)
            if others:
                allowed = E.flat(allowed - E.union(others))
        else:
            oth = [q['mesh'] for t, q in enumerate(pcs) if t not in (k, j)]
            allowed = E.flat(host - E.union(oth)) if oth else host
        outras = [L for t, c in enumerate(cuts) if t != i for L in _loops_of(c)]
        r0 = dict(ok=True, checks=[], piece=p['mesh'], body_parts=[pcs[j]['mesh']])
        try:
            r2, sc = socket_cut(r0, allowed, loops, dict(cut, encaixe=enc, _outras=outras), diag, centro, enc, S, None)
        except Exception:
            traceback.print_exc()
            continue
        bp = r2.get('body_parts') or []
        if len(bp) != 1 or len(E.parts(r2['piece'], 0.3)) != 1:
            notes.setdefault(i, []).append(_chk('aviso', 'O encaixe desta junta partiria uma peça: ficou só a face do corte (cole).'))
            continue
        pcs[k] = dict(p, mesh=r2['piece'])
        pcs[j] = dict(pcs[j], mesh=bp[0])
        notes.setdefault(i, []).extend(sc)
        r0 = r2 = allowed = None
        _free_mem()
        _mem(f'encaixe {i}')
    return dict(state, pieces=pcs)


def _apply_global(out, cuts, S, progress=None):
    t0 = time.time()
    _T0[0] = t0
    hb = np.array(S.bounding_box())
    diag = float(np.linalg.norm(hb[3:] - hb[:3]))
    centro = np.asarray(E.centroid(S))
    notes = {}
    livres_idx = [i for i, c in enumerate(cuts) if not c.get('plano')]
    normal = [i for i in livres_idx if not cuts[i].get('peca')]
    peca = [i for i in livres_idx if cuts[i].get('peca')]
    if progress:
        progress('cortes livres: cada um sozinho')
    _snap(0, out)
    st, rs = _stage(out, normal, cuts, S, notes) if normal else (out, {})
    _mem('antes dos farelos')
    st = _crumbs(st, notes)
    _mem('etapa 1')
    if peca:
        for i in peca:
            _snap(i, st)                       # a tela marca os cortes na peça sobre estas peças
        # cortes numa peça: dependem da peça mãe (já resolvida acima). Um depois do outro, numa ordem fixa
        # que não é a da criação (pela posição da linha), cada um com o próprio soquete, como antes
        def chave(i):
            Ls = _loops_of(cuts[i])
            c = np.vstack(Ls).mean(0) if Ls else np.zeros(3)
            return (-round(float(c[2]), 1), round(float(c[0]), 1), round(float(c[1]), 1))
        for i in sorted(peca, key=chave):
            outras = [L for j, c in enumerate(cuts) if j != i for L in _loops_of(c)]
            base_ids = {id(p['mesh']) for p in st['pieces']}
            ctx, _SNAP_CTX[0] = _SNAP_CTX[0], None
            try:
                o = _apply_cuts(dict(st, pieces=[dict(p, _orig=True) for p in st['pieces']]),
                                [dict(cuts[i], _outras_linhas=outras)], S, None)
            except Exception:
                traceback.print_exc()
                o = None
            finally:
                _SNAP_CTX[0] = ctx
            if o is None:
                rs[i] = dict(ok=False, checks=[_chk('erro', 'O corte falhou.')])
                continue
            for p in o['pieces']:
                if not p.pop('_orig', False):
                    p['livre'] = i
                    p['_peca2'] = True
            rs[i] = {k: v for k, v in o['livres'][0].items() if k not in ('piece', 'body_parts', 'extra')}
            st = dict(o)
            o = None
            _free_mem()
        st = _crumbs(st, notes)
    _mem('etapa 2')
    _free_mem()
    if progress:
        progress('encaixes')
    st = _sockets(st, cuts, S, diag, centro, notes, E.flat(E.union([p['mesh'] for p in out['pieces']])))
    # planos (módulo Plano): como antes, um depois do outro, depois dos cortes livres
    planos = [i for i, c in enumerate(cuts) if c.get('plano')]
    if planos:
        ctx, _SNAP_CTX[0] = _SNAP_CTX[0], None
        try:
            o = _apply_cuts(st, [cuts[i] for i in planos], S, None)
        finally:
            _SNAP_CTX[0] = ctx
        for i in planos:
            _snap(i, st)
        for p in o['pieces']:
            if p.get('livre') is not None and id(p['mesh']) not in {id(q['mesh']) for q in st['pieces']}:
                p['livre'] = planos[p['livre']] if p['livre'] < len(planos) else p['livre']
        for k, r in enumerate(o['livres']):
            rs[planos[k]] = dict(r, i=planos[k])
        st = dict(o)
    res = []
    for i, c in enumerate(cuts):
        r = dict(rs.get(i) or dict(ok=False, checks=[_chk('erro', 'O corte não foi feito.')]))
        r['i'], r['nome'] = i, c.get('nome') or f'Corte {i + 1}'
        ch = list(r.get('checks', [])) + notes.get(i, [])
        if any(x['texto'].startswith('Soquete:') for x in ch):
            ch = [x for x in ch if 'Sem pino' not in x['texto']]
        vf = sum(_vol(p['mesh']) for p in st['pieces'] if p.get('livre') == i)
        for x in ch:
            if x['texto'].startswith('Peça separada:') and vf > 0:
                x = x
                x['texto'] = re.sub(_RE_SEP, f'Peça separada: {_fmt(vf, 0)} mm³', x['texto'])
        r['checks'] = ch
        res.append(r)
    _snap(len(cuts), st)
    o = dict(st)
    o['livres'] = res
    o['segundos'] = round(out.get('segundos', 0) + time.time() - t0, 1)
    return o


# ------------------------------------------------------------- ordem dos cortes (sem depender da criação)
# Os cortes são aplicados um depois do outro, e o resultado de dois cortes que se cruzam depende de qual
# vem primeiro. Por isso a ordem não é a da lista (a ordem em que foram criados): sai das próprias
# linhas. Primeiro os cortes livres no modelo, da parte maior para a menor (como quem corta à mão: a parte
# grande sai inteira e depois os detalhes dela; o lado menor de cada corte continua sendo a peça). Depois
# os cortes numa peça, também da maior para a menor (a peça mãe antes da filha cortada dentro dela); os
# planos no fim (cortam tudo que cruzam). Apagar e recriar um corte, ou criar os cortes em outra ordem,
# dá as mesmas peças. FLEXI_ORDEM=0 volta à ordem da lista.
_ORDEM = _os.environ.get('FLEXI_ORDEM', '1') != '0'


def _cut_size(S, c, ctx):
    """Área da pele do lado da peça (mm²), no modelo inteiro. Sem área pelas linhas: a do círculo de
    mesmo perímetro, para a ordem continuar estável."""
    loops = _loops_of(c)
    if c.get('mascara') and not c.get('peca'):
        n = int(c.get('n') or ctx['nt'])
        m = decode_mask(c['mascara'], n)
        if m is not None and len(m) == ctx['nt']:
            return float(ctx['ar'][m].sum())
    if loops:
        try:
            if ctx.get('topo') is None:
                ctx['topo'] = SPL._topology(S)
            fm = mask_from_lines(S, loops, ctx['topo'], ctx['diag'], ctx['centro'], bool(c.get('inverter')))
            if fm is not None and fm[0].any():
                if not c.get('peca'):
                    ctx.setdefault('masks', {})[id(c)] = fm[0]
                else:
                    ctx.setdefault('pmasks', {})[id(c)] = fm[0]
                return float(ctx['ar'][fm[0]].sum())
        except Exception:
            traceback.print_exc()
        per = sum(float(np.linalg.norm(np.diff(np.vstack([L, L[:1]]), axis=0), axis=1).sum()) for L in loops)
        return per * per / (4.0 * math.pi)
    return 0.0


def _ordem_peca(ordem, cuts, S, ctx):
    """Cortes numa peça: a ordem pela área (ordem), mas se a linha de um cai na área que o outro leva (no modelo
    inteiro), o feito antes na lista roda antes. Ordenação topológica que, entre os livres, segue a ordem pela área."""
    if len(ordem) < 2 or not ctx.get('pmasks'):
        return ordem
    from scipy.spatial import cKDTree
    pm = ctx['pmasks']
    tr = cKDTree(ctx['cen_S'])
    linha = {}
    for i in ordem:
        Ls = _loops_of(cuts[i])
        if Ls:
            _, j = tr.query(np.vstack(Ls))
            linha[i] = j

    def dentro(a, b):                                   # a linha de a cai na área de b
        m = pm.get(id(cuts[b]))
        return m is not None and a in linha and float(m[linha[a]].mean()) > 0.5
    antes = {i: set() for i in ordem}                   # antes[j]: cortes que precisam rodar antes de j
    for a in ordem:
        for b in ordem:
            if a < b and (dentro(a, b) or dentro(b, a)):
                antes[b].add(a)
    pos = {i: k for k, i in enumerate(ordem)}
    feito, saida = set(), []
    while len(saida) < len(ordem):
        livres = [i for i in ordem if i not in feito and antes[i] <= feito]
        if not livres:                                  # ciclo (não deve acontecer): o resto pela área
            livres = [i for i in ordem if i not in feito]
        i = min(livres, key=lambda x: pos[x])
        saida.append(i); feito.add(i)
    return saida


def _canon_perm(cuts, S):
    """Ordem em que os cortes são aplicados (índices da lista), só pelas linhas e marcações."""
    import json as _js
    n = len(cuts)
    livre = [i for i in range(n) if not cuts[i].get('plano') and not cuts[i].get('peca')]
    peca = [i for i in range(n) if not cuts[i].get('plano') and cuts[i].get('peca')]
    plano = [i for i in range(n) if cuts[i].get('plano')]

    def sig(c):
        return _js.dumps({k: v for k, v in c.items() if not str(k).startswith('_') and k != 'nome'}, sort_keys=True, default=str)

    def cen(c):
        loops = _loops_of(c)
        if loops:
            return tuple(np.round(np.vstack(loops).mean(0), 2).tolist())
        if c.get('peca') and c['peca'].get('ponto') is not None:
            return tuple(np.round(np.asarray(c['peca']['ponto'], float), 2).tolist())
        return (0.0, 0.0, 0.0)
    ctx = {}
    if len(livre) > 1 or len(peca) > 1:
        T = tri_array(S)
        bb = S.bounding_box()
        centro = np.array([(bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2, (bb[2] + bb[5]) / 2])
        try:
            centro = np.asarray(E.centroid(S), np.float64)
        except Exception:
            pass
        ctx = dict(nt=len(T), cen_S=T.mean(1), ar=np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1) / 2,
                   diag=float(np.linalg.norm(np.array(bb[3:]) - np.array(bb[:3]))) + 5.0, centro=centro, topo=None)

    def order(ix, sinal):  # sinal -1: maior primeiro
        if len(ix) < 2:
            return list(ix)
        # área arredondada (1 mm²): a mesma linha redesenhada quase igual cai no mesmo lugar
        key = {i: (sinal * round(_cut_size(S, cuts[i], ctx)), cen(cuts[i]), sig(cuts[i])) for i in ix}
        return sorted(ix, key=lambda i: key[i])
    plano = sorted(plano, key=lambda i: sig(cuts[i])) if len(plano) > 1 else plano
    # no modelo, a parte maior primeiro; numa peça também (a peça mãe antes da filha), com uma exceção (1.55): dois
    # cortes numa peça que se sobrepõem (a linha de um cai na área que o outro leva) ficam na ordem em que foram
    # feitos, porque o de depois foi desenhado sobre a peça já cortada pelo de antes. Pela área, a bota feita depois
    # rodava antes da barra da calça e tomava a linha dela (Corte 20 e 25 do Papai Noel).
    perm = order(livre, -1) + _ordem_peca(order(peca, -1), cuts, S, ctx) + plano
    masks = {i: ctx['masks'][id(cuts[i])] for i in range(n) if id(cuts[i]) in ctx.get('masks', {})}
    return perm, masks, ctx.get('cen_S')


# ------------------------------------------------------------- linha que gruda no vinco (em teste)
# A linha desenhada à mão passa perto, mas não exatamente, de onde uma parte encontra a outra (o cabelo e a
# testa). Quem modela à mão corta no vinco côncavo entre as duas. Numa faixa de poucos mm em volta da linha,
# um corte mínimo no grafo dos triângulos escolhe a borda: barata no vinco côncavo, mais cara longe da linha
# (sem vinco, a borda fica na linha). A linha nova é a borda achada. FLEXI_SNAP=1 liga.
_SNAP_LINHA = _os.environ.get('FLEXI_SNAP', '0') == '1'
_SNAP_ANG = math.radians(float(_os.environ.get('FLEXI_SNAP_ANG', '35')))    # ângulo mínimo do vinco
_SNAP_MIN = float(_os.environ.get('FLEXI_SNAP_MIN', '0.5'))                 # parte da borda nova no vinco
_SNAP_GANHO = float(_os.environ.get('FLEXI_SNAP_GANHO', '0.25'))            # quanto mais que a linha desenhada
_SNAP_INFO = [None]


def _snap_loops(S, topo, loops, m0, r=3.0, eta=0.05, alpha=1.0):
    """Linhas no vinco mais perto da linha desenhada (até r mm dela). Devolve as linhas novas ou None."""
    from scipy.spatial import cKDTree
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import maximum_flow, breadth_first_order
    v, f, nb = topo
    T = v[f]
    c = T.mean(1)
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    P = np.vstack([np.vstack([L[k] + (L[(k + 1) % len(L)] - L[k]) * t for k in range(len(L))
                              for t in np.linspace(0, 1, 6, endpoint=False)]) for L in loops])
    dl = cKDTree(P).query(c)[0]
    band = dl < r
    if band.sum() < 50:
        return None
    N = len(f)
    nbm = np.maximum(nb, 0)
    i = np.repeat(np.arange(N), 3)
    j = nb.ravel()
    k = np.tile(np.arange(3), N)
    ok = (j >= 0) & band[i] & band[np.maximum(j, 0)]
    i, j, k = i[ok], j[ok], k[ok]
    L_ = np.linalg.norm(v[f[i, k]] - v[f[i, (k + 1) % 3]], axis=1)
    th = np.arccos(np.clip(np.einsum('ij,ij->i', n[i], n[j]), -1, 1))
    conc = np.einsum('ij,ij->i', c[j] - c[i], n[i]) > 1e-9
    w = L_ * (1.0 + alpha * (0.5 * (dl[i] + dl[j])) / r) / (1.0 + np.where(conc, th / eta, 0.0))
    fora = ~band
    src = band & m0 & ((dl > 0.8 * r) | np.any(fora[nbm] & m0[nbm] & (nb >= 0), axis=1))
    snk = band & ~m0 & ((dl > 0.8 * r) | np.any(fora[nbm] & ~m0[nbm] & (nb >= 0), axis=1))
    if not src.any() or not snk.any():
        return None
    s_, t_ = N, N + 1
    big = 1 << 26
    rows = np.concatenate([i, np.full(int(src.sum()), s_), np.where(snk)[0]])
    cols = np.concatenate([j, np.where(src)[0], np.full(int(snk.sum()), t_)])
    cap = np.concatenate([np.maximum(1, np.round(w * 1000)), np.full(int(src.sum()), big), np.full(int(snk.sum()), big)]).astype(np.int32)
    M = csr_matrix((cap, (rows, cols)), shape=(N + 2, N + 2))
    fl = maximum_flow(M, s_, t_, method='dinic')
    Rr = M - fl.flow
    Rr.data = np.maximum(Rr.data, 0)
    Rr.eliminate_zeros()
    reach = np.zeros(N + 2, bool)
    reach[breadth_first_order(Rr, s_, directed=True, return_predecessors=False)] = True
    m1 = m0.copy()
    m1[band] = reach[:N][band]
    if (m1 != m0).sum() == 0:
        return None
    # só onde há vinco de verdade: a borda nova tem de correr num vinco côncavo marcado (a mecha encontra a
    # testa) na maior parte do comprimento, e bem mais que a borda da linha desenhada. Sem vinco (pulso liso,
    # pescoço de cilindro) a linha desenhada fica como está.
    vinco = conc & (th > _SNAP_ANG)
    bn = m1[i] != m1[j]
    bo = m0[i] != m0[j]
    sh_n = float(L_[bn & vinco].sum() / max(L_[bn].sum(), 1e-9))
    sh_o = float(L_[bo & vinco].sum() / max(L_[bo].sum(), 1e-9))
    _SNAP_INFO[0] = (round(sh_o, 2), round(sh_n, 2))
    if sh_n < _SNAP_MIN or sh_n - sh_o < _SNAP_GANHO:
        return None
    ml, _, _, _ = mask_lines(S, m1, topo)
    drawn = cKDTree(P)
    novas = [L for L in (_clean_loop(x) for x in ml) if L is not None]
    novas = [L for L in novas if float(np.median(drawn.query(L)[0])) <= r]
    if len(novas) != len(loops):
        return None
    # cada linha nova tem de ficar inteira perto da desenhada (sem pular para outra parte)
    for L in novas:
        if float(np.percentile(drawn.query(L)[0], 95)) > r + 0.5:
            return None
    return [np.asarray(L, np.float64) for L in novas]


def _snap_cuts(cuts, S):
    """Aplica _snap_loops nos cortes livres no modelo (não nos planos, nas áreas marcadas nem nos cortes
    numa peça). Devolve a lista de cortes, com as linhas trocadas onde deu certo."""
    if not _SNAP_LINHA:
        return cuts
    topo = None
    hb = S.bounding_box()
    diag = float(np.linalg.norm(np.array(hb[3:]) - np.array(hb[:3]))) + 5.0
    centro = np.asarray(E.centroid(S), np.float64)
    out = []
    for c in cuts:
        loops = _loops_of(c)
        if c.get('plano') or c.get('peca') or c.get('mascara') or not loops:
            out.append(c)
            continue
        try:
            if topo is None:
                topo = SPL._topology(S)
            fm = mask_from_lines(S, loops, topo, diag, centro, bool(c.get('inverter')))
            novas = _snap_loops(S, topo, loops, fm[0], r=3.0 * _CUR_K[0]) if fm is not None else None
        except Exception:
            traceback.print_exc()
            novas = None
        if _DBG:
            print('linha no vinco:', c.get('nome'), 'trocada' if novas else 'mantida', 'vinco antes/depois', _SNAP_INFO[0], flush=True)
        _SNAP_INFO[0] = None
        out.append(dict(c, linhas=[L.tolist() for L in novas]) if novas else c)
    return out


def _apply_ordered(out, cuts, S, progress=None):
    """O motor em cadeia (ou o motor 2, se ligado) na ordem que sai das linhas; o resultado volta com os
    índices da lista original (a tela liga cada peça e cada aviso ao corte dela)."""
    if _MOTOR2:
        return _apply_global(out, cuts, S, progress)
    cuts = _snap_cuts(cuts, S)
    if len(cuts) < 2:
        return _apply_cuts(out, cuts, S, progress)
    if not _ORDEM:
        perm, masks, cenS = list(range(len(cuts))), {}, None
    else:
        try:
            perm, masks, cenS = _canon_perm(cuts, S)
        except Exception:
            traceback.print_exc()
            perm, masks, cenS = list(range(len(cuts))), {}, None
    perm = _ordem_dep(cuts, perm)                    # o pai sempre antes dos dependentes (regra A)
    if _DBG:
        print('ordem dos cortes:', [cuts[k].get('nome') for k in perm], flush=True)
    if perm == list(range(len(cuts))):
        return _apply_cuts(out, cuts, S, progress)
    cs = []
    for k in perm:
        c = dict(cuts[k])
        if not c.get('nome'):
            c['nome'] = (f'Plano {k + 1}' if c.get('plano') else f'Corte {k + 1}')
        cs.append(c)
    ctx = _SNAP_CTX[0]
    if ctx is not None and len(ctx) > 2:
        orig = ctx[2]
        _SNAP_CTX[0] = (ctx[0], cuts_sigs([orig[k] for k in perm]), [orig[k] for k in perm])
    try:
        o = _apply_cuts(out, cs, S, progress)
    finally:
        if ctx is not None and len(ctx) > 2:
            fim = _SNAP.get((ctx[0], _SNAP_CTX[0][1][-1]))
            _SNAP_CTX[0] = ctx
            if fim is not None:
                _SNAP[(ctx[0], ctx[1][-1])] = fim     # a lista como a tela tem: o mesmo estado final
    lv = [None] * len(cuts)
    extra = []
    for r in o.get('livres', []):
        pos = r.get('i', -1)
        if 0 <= pos < len(perm):
            r['i'] = perm[pos]
            lv[perm[pos]] = r
        else:
            extra.append(r)
    o['livres'] = [r for r in lv if r is not None] + extra
    for p in o['pieces']:
        if p.get('livre') is not None and 0 <= p['livre'] < len(perm):
            p['livre'] = perm[p['livre']]
    try:
        _fix_nested_names(o, cuts, perm, masks, cenS)
    except Exception:
        traceback.print_exc()
    o['pieces'] = sorted(o['pieces'], key=lambda p: (p.get('livre') is not None, p.get('livre') if p.get('livre') is not None else 0))
    return o


def _fix_nested_names(o, cuts, perm, masks, cenS):
    """Dois cortes um dentro do outro (a cabeça e o pescoço logo abaixo): o maior é aplicado primeiro e o
    menor corta a peça dele. A peça é o lado menor dessa peça, que pode ser a do meio (o pescoço) e não a da
    ponta (a cabeça): aí a peça com o nome do corte maior nem encosta na linha dele. A forma das peças e as
    juntas não mudam: só o nome (e o corte a que cada peça pertence) volta para o corte certo."""
    if cenS is None or len(masks) < 2:
        return
    pos = {k: j for j, k in enumerate(perm)}
    ids = sorted(masks, key=lambda k: pos[k])

    def main(k):
        ps = [p for p in o['pieces'] if p.get('livre') == k and p.get('tipo') != 'cavilha']
        return max(ps, key=lambda p: _vol(p['mesh'])) if ps else None
    for a in ids:
        for b in ids:
            if pos[b] >= pos[a]:
                continue
            ma, mb = masks[a], masks[b]
            if ma.sum() == 0 or (ma & mb).sum() < 0.9 * ma.sum():
                continue                             # o menor não está dentro do maior
            pa, pb = main(a), main(b)
            if pa is None or pb is None:
                continue
            # a peça do corte maior tem de encostar na linha dele (a junta com o corpo); se só a outra encosta,
            # os nomes estão trocados
            from scipy.spatial import cKDTree
            Lb = np.vstack(_loops_of(cuts[b]))
            lim = float(cuts[b].get('folga') or 0.2) + 1.5 * _CUR_K[0]

            def toca(pm):
                v = np.asarray(pm['mesh'].to_mesh().vert_properties)[:, :3]
                return float((cKDTree(v).query(Lb)[0] <= lim).mean())
            ta, tb = toca(pa), toca(pb)
            if tb < 0.3 and ta > 0.7:
                if _DBG:
                    print('nomes trocados:', cuts[a].get('nome'), '<->', cuts[b].get('nome'), round(ta, 2), round(tb, 2), flush=True)
                for k_ in ('nome', 'livre'):
                    pa[k_], pb[k_] = pb.get(k_), pa.get(k_)



def _apply_scaled(out, cuts, S, progress=None):
    k = _scale_factor(S)
    if abs(k - 1.0) < 1e-9:
        return _apply_ordered(out, cuts, S, progress)
    Sk = S.scale([k, k, k])
    pcs = []
    for p in out['pieces']:
        q = dict(p)
        q['mesh'] = p['mesh'].scale([k, k, k])
        if p.get('T') is not None:
            q['T'] = np.asarray(p['T']) * k
        if p.get('print_T') is not None:
            q['print_T'] = _D(k) @ np.asarray(p['print_T']) @ _D(1.0 / k)     # posição de impressão na cópia em escala
        pcs.append(q)
    outk = dict(out, pieces=pcs)
    cutsk = []
    for c in cuts:
        c2 = dict(c)
        c2['linhas'] = [[[v * k for v in q] for q in (L['p'] if isinstance(L, dict) else L)] for L in (c.get('linhas') or [])]
        for f in FISICOS:
            if c.get(f) not in (None, '', 0):
                try:
                    c2[f] = float(c[f]) * k
                except Exception:
                    pass
        if c.get('soquete') and c.get('soquete_mm') in (None, '', 0):
            c2['soquete_mm'] = 4.0 * k
        if c.get('folga') in (None, ''):
            c2['folga'] = DEF.get('folga', 0.2) * k
        if c.get('folga_pino') in (None, ''):
            c2['folga_pino'] = DEF.get('folga_pino', 0.4) * k
        c2.setdefault('parede', 1.2)
        if c.get('parede') in (None, ''):
            c2['parede'] = 1.2 * k
        if c.get('plano'):
            pl = dict(c['plano'])
            pl['p'] = [v * k for v in (pl.get('p') or [0, 0, 0])]
            c2['plano'] = pl
        if c.get('peca') and c['peca'].get('ponto') is not None:
            c2['peca'] = dict(c['peca'], ponto=[v * k for v in c['peca']['ponto']])
        cutsk.append(c2)
    _CUR_K[0] = k
    try:
        rk = _apply_ordered(outk, cutsk, Sk, progress)
    finally:
        _CUR_K[0] = 1.0
    ik = 1.0 / k
    back = []
    for p in rk['pieces']:
        q = dict(p)
        q['mesh'] = p['mesh'].scale([ik, ik, ik])
        if p.get('T') is not None:
            q['T'] = np.asarray(p['T']) * ik
        if p.get('print_T') is not None:
            q['print_T'] = _D(1.0 / k) @ np.asarray(p['print_T']) @ _D(k)     # de volta: gira igual, translada no tamanho real
        back.append(q)
    rk['pieces'] = back
    for r in rk.get('livres', []):
        c0 = cuts[r['i']] if 0 <= r.get('i', -1) < len(cuts) else {}
        snap = [float(c0.get(f) or 0) for f in FISICOS] + [1.2, 4.0, 0.2, 0.4, 0.8, 2.0]
        r['checks'] = [dict(x, texto=_fix_text(x['texto'], k, snap)) for x in r.get('checks', [])]
        for key in ('piece', 'body_parts', 'extra'):
            r.pop(key, None)
    return rk


def summary(out):
    """Resumo JSON dos cortes livres e das peças."""
    regs = []
    for r in out.get('livres', []):
        ch = r.get('checks', [])
        luz = 'erro' if any(c['nivel'] == 'erro' for c in ch) else 'aviso' if any(c['nivel'] == 'aviso' for c in ch) else 'ok'
        regs.append(dict(i=r['i'], nome=r['nome'], ok=bool(r.get('ok')), luz=luz, checks=ch,
                         forma=r.get('forma'), encaixe=r.get('encaixe'), sem_pino=bool(r.get('sem_pino')), plano=bool(r.get('plano')),
                         dir=r.get('dir')))
    return regs
