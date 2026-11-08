# EFC3D: encaixe das peças (1.48 beta).
#
# Módulo à parte do motor de corte. Uma divisa certa para a vista (a mecha de cabelo na testa) pode deixar
# as duas peças travadas uma na outra: a pele da testa continua por baixo da mecha e o cabelo abraça esse
# trecho por fora, então não há direção em que uma peça saia reta da outra (como num molde sem ângulo de
# saída). Este módulo:
#   analisar(out)            -> cada par de peças que se encostam: a direção em que uma sai da outra com
#                               menos trava, e quanto trava (0 = encaixa reto)
#   corrigir(out, pares)     -> nos pares pedidos, tira da peça certa o volume que trava (o que fica na
#                               sombra da outra, na direção de encaixe), com a folga: as duas peças passam a
#                               encaixar retas. Só muda o que está escondido por baixo da outra peça.
import math
import traceback

import numpy as np
import manifold3d as mf

import engine as E
from split import _frame, _vol, _chk, _fmt, tri_array

FOLGA = 0.4            # folga na direção de encaixe (peça removível)
CELULA = 0.5           # grade da busca da direção (mm)
CELULA_FINA = 0.25     # grade da correção (mm)


def _amostras(T, area_pt, rng=7):
    a = np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1) / 2
    k = np.maximum(1, np.ceil(a / area_pt)).astype(np.int64)
    idx = np.repeat(np.arange(len(T)), k)
    g = np.random.default_rng(rng)
    r1, r2 = np.sqrt(g.random(len(idx))), g.random(len(idx))
    return T[idx, 0] * (1 - r1)[:, None] + T[idx, 1] * (r1 * (1 - r2))[:, None] + T[idx, 2] * (r1 * r2)[:, None]


def _direcoes(n=400):
    """Direções espalhadas na esfera (espiral de Fibonacci)."""
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    th = math.pi * (1 + 5 ** 0.5) * i
    return np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], 1)


def _colunas(PA, PB, d, cel, lo=None, shape=None):
    """Na direção d (a peça A sai no sentido +d, a B fica): para cada coluna da grade no plano de d, a
    altura mais baixa de A e a mais alta de B. Trava onde B passa por cima de A na mesma coluna."""
    R = _frame(d)
    qa, qb = PA @ R, PB @ R
    if lo is None:
        lo = np.minimum(qa[:, :2].min(0), qb[:, :2].min(0)) - cel
        hi = np.maximum(qa[:, :2].max(0), qb[:, :2].max(0)) + cel
        shape = tuple(np.ceil((hi - lo) / cel).astype(int) + 1)
    ia = np.floor((qa[:, :2] - lo) / cel).astype(int)
    ib = np.floor((qb[:, :2] - lo) / cel).astype(int)
    ia = np.clip(ia, 0, np.array(shape) - 1)
    ib = np.clip(ib, 0, np.array(shape) - 1)
    minA = np.full(shape, np.inf)
    maxB = np.full(shape, -np.inf)
    np.minimum.at(minA, (ia[:, 0], ia[:, 1]), qa[:, 2])
    np.maximum.at(maxB, (ib[:, 0], ib[:, 1]), qb[:, 2])
    return R, lo, shape, minA, maxB


def _raster(T, R, lo, shape, cel):
    """Alturas (mín e máx) onde a reta de cada centro de célula, na direção de R[:, 2], cruza a malha T:
    exato nos centros (sem o erro de amostrar pontos numa face inclinada)."""
    Q = T @ R                                         # (n,3,3) no referencial da direção
    zmin = np.full(shape, np.inf)
    zmax = np.full(shape, -np.inf)
    xy = Q[:, :, :2]
    bmin = np.floor((xy.min(1) - lo) / cel - 0.5).astype(int) + 1
    bmax = np.floor((xy.max(1) - lo) / cel - 0.5).astype(int)
    span = np.maximum(bmax - bmin + 1, 0)
    ok = (span[:, 0] > 0) & (span[:, 1] > 0)
    sz = np.maximum(span[:, 0], span[:, 1])
    k = 1
    while True:
        sel = np.where(ok & (sz <= k) & (sz > k // 2 if k > 1 else True))[0]
        if len(sel):
            oi, oj = np.meshgrid(np.arange(k), np.arange(k), indexing='ij')
            oi, oj = oi.ravel(), oj.ravel()
            for c0 in range(0, len(sel), max(1, 400000 // (k * k))):
                ss = sel[c0:c0 + max(1, 400000 // (k * k))]
                I = bmin[ss, 0][:, None] + oi[None]
                J = bmin[ss, 1][:, None] + oj[None]
                px = lo[0] + (I + 0.5) * cel
                py = lo[1] + (J + 0.5) * cel
                a_, b_, c_ = Q[ss, 0][:, None], Q[ss, 1][:, None], Q[ss, 2][:, None]
                v0x, v0y = b_[..., 0] - a_[..., 0], b_[..., 1] - a_[..., 1]
                v1x, v1y = c_[..., 0] - a_[..., 0], c_[..., 1] - a_[..., 1]
                v2x, v2y = px - a_[..., 0], py - a_[..., 1]
                den = v0x * v1y - v1x * v0y
                with np.errstate(divide='ignore', invalid='ignore'):
                    u = (v2x * v1y - v1x * v2y) / den
                    v = (v0x * v2y - v2x * v0y) / den
                inside = (np.abs(den) > 1e-12) & (u >= 0) & (v >= 0) & (u + v <= 1) & \
                    (I < shape[0]) & (J < shape[1]) & (I >= 0) & (J >= 0)
                z = a_[..., 2] + u * (b_[..., 2] - a_[..., 2]) + v * (c_[..., 2] - a_[..., 2])
                ii, jj, zz = I[inside], J[inside], z[inside]
                np.minimum.at(zmin, (ii, jj), zz)
                np.maximum.at(zmax, (ii, jj), zz)
        if k >= sz[ok].max(initial=1):
            break
        k *= 2
    return zmin, zmax


def _colunas_exatas(TA, TB, d, cel, lo=None, shape=None):
    R = _frame(d)
    if lo is None:
        qa = TA.reshape(-1, 3) @ R
        qb = TB.reshape(-1, 3) @ R
        lo = np.minimum(qa[:, :2].min(0), qb[:, :2].min(0)) - cel
        hi = np.maximum(qa[:, :2].max(0), qb[:, :2].max(0)) + cel
        shape = tuple(np.ceil((hi - lo) / cel).astype(int) + 1)
    minA, _ = _raster(TA, R, lo, shape, cel)
    _, maxB = _raster(TB, R, lo, shape, cel)
    return R, lo, shape, minA, maxB


def _trava(minA, maxB, cel, margem=0.05):
    sob = maxB - minA - margem
    sob = np.where(np.isfinite(sob), sob, 0.0)
    m = sob > 0
    return float(sob[m].sum() * cel * cel), m


def _pares(out, gap_max=0.35, min_area=4.0):
    """Pares de peças que se encostam (a face do corte de uma diante da da outra)."""
    from scipy.spatial import cKDTree
    ps = out['pieces']
    S = [(_amostras(np.asarray(p['T'], np.float64), 0.25), np.asarray(p['T'], np.float64).reshape(-1, 3)) for p in ps]
    res = []
    for i in range(len(ps)):
        for j in range(i + 1, len(ps)):
            if ps[i].get('tipo') == 'cavilha' or ps[j].get('tipo') == 'cavilha':
                continue
            Pi, Vi = S[i]
            Pj, Vj = S[j]
            lo = np.maximum(Vi.min(0), Vj.min(0)) - 1.0
            hi = np.minimum(Vi.max(0), Vj.max(0)) + 1.0
            if np.any(lo > hi):
                continue
            mi = np.all((Pi >= lo) & (Pi <= hi), 1)
            mj = np.all((Pj >= lo) & (Pj <= hi), 1)
            if mi.sum() < 20 or mj.sum() < 20:
                continue
            d, _ = cKDTree(Pj[mj]).query(Pi[mi], distance_upper_bound=gap_max)
            area = float(np.isfinite(d).sum()) * 0.25
            if area >= min_area:
                res.append((i, j, area))
    return res


def analisar(out, n_dir=200):
    """Cada par de peças que se encostam: a melhor direção de encaixe e quanto trava nela."""
    ps = out['pieces']
    pares = _pares(out)
    amos = {}

    def pts(k):
        if k not in amos:
            amos[k] = _amostras(np.asarray(ps[k]['T'], np.float64), 0.5, rng=k + 1)
        return amos[k]
    D = _direcoes(n_dir)
    res = []
    for i, j, area in pares:
        # a peça menor é a que sai (o rosto sai do cabelo, o braço sai do corpo)
        a, b = (i, j) if _vol(ps[i]['mesh']) <= _vol(ps[j]['mesh']) else (j, i)
        PA, PB = pts(a), pts(b)
        best = None
        for d in D:
            _, _, _, mA, mB = _colunas(PA, PB, d, CELULA)
            v, _m = _trava(mA, mB, CELULA)
            if best is None or v < best[0]:
                best = (v, d)
        # refina em volta da melhor
        v0, d0 = best
        R0 = _frame(d0)
        for ang in (8.0, 4.0, 2.0):
            t = math.radians(ang)
            for ax in (R0[:, 0], R0[:, 1], -R0[:, 0], -R0[:, 1]):
                d1 = d0 * math.cos(t) + ax * math.sin(t)
                d1 /= np.linalg.norm(d1)
                _, _, _, mA, mB = _colunas(PA, PB, d1, CELULA)
                v1, _m = _trava(mA, mB, CELULA)
                if v1 < v0:
                    v0, d0 = v1, d1
        res.append(dict(id=f'{ps[a]["nome"]}|{ps[b]["nome"]}', sai=ps[a]['nome'], fica=ps[b]['nome'], _a=a, _b=b,
                        area=round(area, 1), direcao=[round(float(x), 4) for x in d0], trava_mm3=round(v0, 1),
                        luz='ok' if v0 < 1.0 else 'aviso'))
    for r in res:
        r['texto'] = _texto(r)
    return res


def _onde(d):
    d = np.asarray(d)
    nomes = [((0, 0, 1), 'de cima'), ((0, 0, -1), 'de baixo'), ((0, -1, 0), 'pela frente'), ((0, 1, 0), 'por trás'),
             ((1, 0, 0), 'pela direita'), ((-1, 0, 0), 'pela esquerda')]
    v, nm = max(((float(np.dot(d, np.array(u))), t) for u, t in nomes))
    return nm


def _texto(r):
    if r['luz'] == 'ok':
        return f'"{r["sai"]}" encaixa reto em "{r["fica"]}" (sai {_onde(r["direcao"])}).'
    return (f'"{r["sai"]}" não sai reto de "{r["fica"]}": mesmo na melhor direção ({_onde(r["direcao"])}) as peças travam '
            f'({_fmt(r["trava_mm3"], 0)} mm³ de uma por trás da outra). Use "Corrigir o encaixe" ou corte a parte que trava.')


def publico(rs):
    return [{k: v for k, v in r.items() if not k.startswith('_')} for r in rs]


def _colunas_solido(R, lo, cel, mask, z0, z1):
    """Sólido feito das colunas marcadas, cada uma de z0 a z1 (no referencial R da direção)."""
    ii, jj = np.where(mask)
    if not len(ii):
        return mf.Manifold()
    boxes = []
    for i, j in zip(ii, jj):
        a, b = float(z0[i, j]), float(z1[i, j])
        if not (b > a):
            continue
        boxes.append(mf.Manifold.cube([cel, cel, b - a]).translate([lo[0] + i * cel, lo[1] + j * cel, a]))
    if not boxes:
        return mf.Manifold()
    M = E.flat(mf.Manifold.batch_boolean(boxes, mf.OpType.Add))
    T = np.eye(4)
    T[:3, :3] = R
    return E.X(M, T)


def corrigir(out, pares_ids, analise=None, folga=FOLGA):
    """Nos pares pedidos, a peça que sai passa a sair reta: tira da peça certa o que trava, com a folga."""
    from split import _on_surface
    an = analise if analise is not None else analisar(out)
    por_id = {r['id']: r for r in an}
    pieces = list(out['pieces'])
    notas = []
    for pid in pares_ids:
        r = por_id.get(pid)
        if r is None or r['luz'] == 'ok':
            continue
        a, b = r['_a'], r['_b']
        A, B = pieces[a], pieces[b]
        PA = _amostras(np.asarray(A['T'], np.float64), 0.06, 11)
        PB = _amostras(np.asarray(B['T'], np.float64), 0.06, 12)
        d = np.asarray(r['direcao'], np.float64)
        R, lo, shape, minA, maxB = _colunas(PA, PB, d, CELULA_FINA)
        _v, m = _trava(minA, maxB, CELULA_FINA)
        if not m.any():
            continue
        # a amostra pode faltar numa coluna: a trava se estende uma célula para os lados (com as alturas vizinhas)
        from scipy.ndimage import binary_dilation, minimum_filter, maximum_filter
        m = binary_dilation(m, iterations=1)
        minA = np.where(np.isfinite(minA), minA, np.inf)
        minA = minimum_filter(np.where(np.isfinite(minA), minA, 1e9), size=3)
        maxB = maximum_filter(np.where(np.isfinite(maxB), maxB, -1e9), size=3)
        m &= (minA < 1e8) & (maxB > -1e8)
        # duas saídas: tirar de A o que está abaixo do topo de B, ou tirar de B o que está acima da base de A
        cutA = _colunas_solido(R, lo, CELULA_FINA, m, minA - 1.0, maxB + folga)
        cutB = _colunas_solido(R, lo, CELULA_FINA, m, minA - folga, maxB + 1.0)
        try:
            ra, rb = E.flat(A['mesh'] ^ cutA), E.flat(B['mesh'] ^ cutB)
            va, vb = _vol(ra), _vol(rb)
        except Exception:
            traceback.print_exc()
            continue
        k, cut, vtir = (a, cutA, va) if va <= vb else (b, cutB, vb)
        P = pieces[k]
        M2 = E.flat(P['mesh'] - cut)
        ps_ = sorted(E.parts(M2, 0.0), key=lambda q: -_vol(q))
        n0 = len(E.parts(P['mesh'], 0.0))
        if len(ps_) > n0:
            solto = sum(_vol(q) for q in ps_[n0:])
            M2 = E.flat(E.union(ps_[:n0])) if n0 > 1 else ps_[0]
        else:
            solto = 0.0
        from freecut import _paint_from
        T, col = _paint_from(np.asarray(P['T']), np.asarray(P['paint']), M2, P['base'])
        pieces[k] = dict(P, mesh=M2, T=T, paint=col)
        PA2 = _amostras(np.asarray(pieces[a]['T'], np.float64), 0.06, 13)
        PB2 = _amostras(np.asarray(pieces[b]['T'], np.float64), 0.06, 14)
        _, _, _, mA2, mB2 = _colunas(PA2, PB2, d, CELULA)
        resto, _m2 = _trava(mA2, mB2, CELULA)
        notas.append(dict(id=pid, peca=P['nome'], tirado_mm3=round(vtir + solto, 1), resto_mm3=round(resto, 1),
                          texto=f'Encaixe corrigido: "{A["nome"]}" sai reto de "{B["nome"]}" ({_onde(d)}). Saíram {_fmt(vtir + solto, 0)} mm³ '
                                f'de "{P["nome"]}", na parte escondida pela outra peça, com folga de {_fmt(folga, 2)} mm.'))
    o2 = dict(out)
    o2['pieces'] = pieces
    o2['encaixes'] = notas
    return o2
