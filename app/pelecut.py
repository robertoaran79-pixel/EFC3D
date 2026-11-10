# EFC3D 1.48 beta: corte livre pela pele.
#
# A pele de cada peça é a malha original, dividida exatamente na linha desenhada (navalha pelas arestas). Cada
# lado é fechado por dentro com uma tampa, que é a mesma superfície para as duas peças (com a folga no meio). A
# tampa é construída sobre a direção de encaixe da peça (sugerida pelo app ou escolhida pelo usuário), presa na
# linha, e fica sempre dentro do sólido e longe da pele: a forma de fora não muda (P9 da especificação). O pino
# vem do módulo de conectores (1.46), no eixo da direção de encaixe.
#
# Ligado por padrão na 1.48 beta. Um corte que este motor não consegue fazer cai no motor anterior, com aviso.
import math
import os
import time
import traceback

import numpy as np
import manifold3d as M
from scipy.spatial import cKDTree

import engine as E
import split as SPL

try:
    import shapely                                   # noqa: F401
    DISPONIVEL = True
except Exception:                                    # sem shapely (instalação antiga): fica o motor anterior
    DISPONIVEL = False

LIGADO = os.environ.get('FLEXI_MOTOR', 'pele') == 'pele'
EXTRA = [0.0]
# laços de contato do último corte dividido (cacho apoiado na pele, longe da linha): chave = vértices do laço
CONTATO = {}
CEL = 0.4


def _mk(V, F):
    return M.Manifold(M.Mesh(vert_properties=np.ascontiguousarray(V, np.float32), tri_verts=np.ascontiguousarray(F, np.uint32)))


def _vf(m):
    mg = m.to_mesh()
    return np.asarray(mg.vert_properties, np.float64)[:, :3], np.asarray(mg.tri_verts, np.int64)


def frame(d):
    d = np.asarray(d, float); d = d / np.linalg.norm(d)
    a = np.array([1.0, 0, 0]) if abs(d[0]) < 0.9 else np.array([0, 1.0, 0])
    u = np.cross(d, a); u /= np.linalg.norm(u); v = np.cross(d, u)
    return np.array([u, v, d])


def fib(n):
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n); th = np.pi * (1 + 5 ** 0.5) * i
    return np.c_[np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)]


def colunas(T, R, cel, lo=None, shape=None):
    """Toques exatos da reta de cada centro de célula (direção R[2]) com cada triângulo."""
    Q = T @ R.T
    xy = Q[:, :, :2]
    if lo is None:
        lo = xy.reshape(-1, 2).min(0) - 3 * cel
        shape = tuple((np.ptp(xy.reshape(-1, 2), 0) / cel).astype(int) + 7)
    bmin = np.floor((xy.min(1) - lo) / cel - 0.5).astype(int) + 1
    bmax = np.floor((xy.max(1) - lo) / cel - 0.5).astype(int)
    span = np.maximum(bmax - bmin + 1, 0); ok = (span[:, 0] > 0) & (span[:, 1] > 0); sz = np.maximum(span[:, 0], span[:, 1])
    C, Z, TT = [], [], []
    k = 1
    mx = sz[ok].max(initial=1)
    while True:
        sel = np.where(ok & (sz <= k) & ((sz > k // 2) if k > 1 else True))[0]
        if len(sel):
            oi, oj = np.meshgrid(np.arange(k), np.arange(k), indexing='ij'); oi, oj = oi.ravel(), oj.ravel()
            step = max(1, 300000 // (k * k))
            for c0 in range(0, len(sel), step):
                ss = sel[c0:c0 + step]
                I = bmin[ss, 0][:, None] + oi; J = bmin[ss, 1][:, None] + oj
                px = lo[0] + (I + 0.5) * cel; py = lo[1] + (J + 0.5) * cel
                a_, b_, c_ = Q[ss, 0][:, None], Q[ss, 1][:, None], Q[ss, 2][:, None]
                v0x, v0y = b_[..., 0] - a_[..., 0], b_[..., 1] - a_[..., 1]
                v1x, v1y = c_[..., 0] - a_[..., 0], c_[..., 1] - a_[..., 1]
                v2x, v2y = px - a_[..., 0], py - a_[..., 1]
                den = v0x * v1y - v1x * v0y
                with np.errstate(all='ignore'):
                    u = (v2x * v1y - v1x * v2y) / den; v = (v0x * v2y - v2x * v0y) / den
                    ins = (np.abs(den) > 1e-14) & (u >= 0) & (v >= 0) & (u + v <= 1) & (I >= 0) & (J >= 0) & (I < shape[0]) & (J < shape[1])
                    zz = a_[..., 2] + u * (b_[..., 2] - a_[..., 2]) + v * (c_[..., 2] - a_[..., 2])
                C.append((I * shape[1] + J)[ins]); Z.append(zz[ins]); TT.append(np.broadcast_to(ss[:, None], I.shape)[ins])
        if k >= mx:
            break
        k *= 2
    C = np.concatenate(C); Z = np.concatenate(Z); TT = np.concatenate(TT)
    o = np.lexsort((Z, C))
    return C[o], Z[o], TT[o], lo, shape


def linha_celulas(lp, R, lo, shape, cel, tol=0.3):
    """Células por onde a linha passa (projetada em d) e a profundidade dela; dobra = trecho em que a linha
    passa duas vezes pela mesma coluna com profundidades diferentes (a face não pode passar pelos dois)."""
    Q = lp @ R.T
    I = np.floor((Q[:, 0] - lo[0]) / cel).astype(int); J = np.floor((Q[:, 1] - lo[1]) / cel).astype(int)
    ok = (I >= 0) & (J >= 0) & (I < shape[0]) & (J < shape[1])
    c = (I * shape[1] + J)[ok]; z = Q[ok, 2]
    o = np.argsort(c); c, z = c[o], z[o]
    st = np.r_[0, np.where(np.diff(c))[0] + 1]; en = np.r_[st[1:], len(c)]
    zmin = np.minimum.reduceat(z, st); zmax = np.maximum.reduceat(z, st); zm = np.add.reduceat(z, st) / (en - st)
    cel_ = c[st]; boa = (zmax - zmin) <= tol
    return cel_[boa], zm[boa], float(((~boa) * (en - st)).sum())


def _densa(loops, passo=0.1):
    out = []
    for L in loops:
        L = np.asarray(L, float); P = np.vstack([L, L[:1]])
        for a_, b_ in zip(P[:-1], P[1:]):
            n = max(1, int(np.linalg.norm(b_ - a_) / passo))
            out.append(a_ + (b_ - a_) * np.linspace(0, 1, n, endpoint=False)[:, None])
    return np.vstack(out)


def normal_linha(lp):
    c = lp - lp.mean(0)
    w, v = np.linalg.eigh(c.T @ c)
    return v[:, 0]


def membrana(lc, lz, lb, ub, shape, it=30):
    """Face do corte = membrana mais lisa presa na linha (como uma película de sabão na linha); só onde a
    peça obriga (pele de um lado ou do outro) ela é empurrada, e só ali. Assim um corte de linha plana
    sai plano e a face não 'incha' por causa de uma parte vizinha."""
    from scipy.sparse import coo_matrix, diags
    from scipy.sparse.linalg import spsolve
    nx, ny = shape; N = nx * ny; idx = np.arange(N).reshape(nx, ny)
    I = np.r_[idx[:-1, :].ravel(), idx[1:, :].ravel(), idx[:, :-1].ravel(), idx[:, 1:].ravel()]
    J = np.r_[idx[1:, :].ravel(), idx[:-1, :].ravel(), idx[:, 1:].ravel(), idx[:, :-1].ravel()]
    W = coo_matrix((np.ones(len(I)), (I, J)), shape=(N, N)).tocsr()
    deg = np.asarray(W.sum(1)).ravel()
    fix = np.zeros(N, bool); fix[lc] = True
    val = np.zeros(N); val[lc] = lz
    Lm = (diags(deg) - W).tolil()
    rows = np.where(fix)[0]
    Lm = Lm.tocsr(); Lm = diags((~fix).astype(float)) @ Lm + diags(fix.astype(float))
    h = spsolve(Lm.tocsc(), np.where(fix, val, 0.0)).reshape(shape)
    L_ = lb.reshape(shape); H_ = ub.reshape(shape)
    bad = L_ > H_
    with np.errstate(invalid='ignore'):               # limites infinitos (sem limite) dão NaN só onde bad é falso
        m_ = (L_ + H_) / 2
    L_ = np.where(bad, m_, L_); H_ = np.where(bad, m_, H_)
    h = np.minimum(np.maximum(h, L_), H_)
    for _ in range(it):                              # só alisa a quina onde a película foi empurrada
        p = np.pad(h, 1, mode='edge'); g = (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]) / 4
        g = np.where(fix.reshape(shape), h, g)
        h = np.minimum(np.maximum(g, L_), H_)
    return h


REFINO = os.environ.get('FLEXI_REFINO_LINHA', '0') == '1'


def refinar_perto_da_linha(V, F, lp, r=1.5, lmax=1.0, rodadas=8):
    """1.50: triângulos compridos perto da linha (a sola plana da tartaruga tem arestas de 20 mm) não deixam a navalha
    seguir a linha: o caminho de arestas desvia e a sola inteira da pata fica com o corpo (uma lâmina de 0,13 mm). Aqui
    as arestas mais longas que `lmax` que passam a até `r` da linha são divididas ao meio, nos dois triângulos que as
    usam (a malha continua fechada e a superfície é exatamente a mesma). Devolve (V, F, quantas arestas)."""
    from scipy.spatial import cKDTree
    kd = cKDTree(lp)
    total = 0
    for _ in range(rodadas):
        Ed = np.vstack([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
        Es = np.sort(Ed, 1)
        u, inv = np.unique(Es, axis=0, return_inverse=True)
        inv = inv.ravel()
        L = np.linalg.norm(V[u[:, 0]] - V[u[:, 1]], axis=1)
        cand = np.where(L > lmax)[0]
        if not len(cand):
            break
        # distância da aresta à linha: amostras ao longo da aresta (passo de até 0,5 mm)
        n = np.clip(np.ceil(L[cand] / 0.5).astype(int), 2, 200)
        perto = np.zeros(len(cand), bool)
        for nn in np.unique(n):
            sel = np.where(n == nn)[0]
            t = np.linspace(0, 1, nn)[None, :, None]
            P = V[u[cand[sel], 0]][:, None] + (V[u[cand[sel], 1]] - V[u[cand[sel], 0]])[:, None] * t
            d = kd.query(P.reshape(-1, 3), distance_upper_bound=r)[0].reshape(len(sel), nn)
            perto[sel] = np.isfinite(d).any(1)
        marca = np.zeros(len(u), bool)
        marca[cand[perto]] = True
        if not marca.any():
            break
        total += int(marca.sum())
        mid = np.full(len(u), -1, np.int64)
        idm = np.where(marca)[0]
        mid[idm] = len(V) + np.arange(len(idm))
        V = np.vstack([V, (V[u[idm, 0]] + V[u[idm, 1]]) / 2])
        nF = len(F)
        m = mid[inv].reshape(3, nF).T                 # ponto do meio de cada aresta do triângulo (ou -1)
        a, b, c = F[:, 0], F[:, 1], F[:, 2]
        k = (m >= 0).sum(1)
        novos = [F[k == 0]]
        # um lado dividido: gira o triângulo para o lado dividido ser (a, b)
        for e in range(3):
            s_ = (k == 1) & (m[:, e] >= 0)
            if s_.any():
                ff = np.roll(F[s_], -e, axis=1); mm = m[s_, e]
                novos += [np.c_[ff[:, 0], mm, ff[:, 2]], np.c_[mm, ff[:, 1], ff[:, 2]]]
        # dois lados: o lado inteiro é (c, a) depois de girar
        for e in range(3):
            s_ = (k == 2) & (m[:, (e + 2) % 3] < 0)
            if s_.any():
                ff = np.roll(F[s_], -e, axis=1); m01 = m[s_, e]; m12 = m[s_, (e + 1) % 3]
                novos += [np.c_[m01, ff[:, 1], m12], np.c_[ff[:, 0], m01, m12], np.c_[ff[:, 0], m12, ff[:, 2]]]
        s3 = k == 3
        if s3.any():
            m01, m12, m20 = m[s3, 0], m[s3, 1], m[s3, 2]
            novos += [np.c_[a[s3], m01, m20], np.c_[m01, b[s3], m12], np.c_[m20, m12, c[s3]], np.c_[m01, m12, m20]]
        F = np.vstack(novos)
    return V, F, total


def _dividir_navalha(V, F, loops, A):
    """Navalha pelas arestas da malha: cada linha vira um caminho fechado de arestas que passa pelos pontos
    desenhados (o caminho mais curto entre um ponto e o seguinte). As arestas do caminho são a navalha: os
    triângulos se separam ali e nada mais muda na pele. Cada parte fica com o lado que a área desenhada
    indica. Devolve (triângulos da peça, triângulos do corpo, número de partes, comprimento do caminho)."""
    from scipy.spatial import cKDTree
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra, connected_components
    Ed = np.vstack([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    Es = np.sort(Ed, 1)
    u, inv = np.unique(Es, axis=0, return_inverse=True)
    w = np.linalg.norm(V[u[:, 0]] - V[u[:, 1]], axis=1)
    G = coo_matrix((np.r_[w, w], (np.r_[u[:, 0], u[:, 1]], np.r_[u[:, 1], u[:, 0]])), shape=(len(V), len(V))).tocsr()
    kd = cKDTree(V)
    corte = set(); comp = 0.0
    for L in loops:
        _, ids = kd.query(np.asarray(L, float))
        ids = [int(x) for k, x in enumerate(ids) if k == 0 or x != ids[k - 1]]
        if ids[0] == ids[-1]:
            ids = ids[:-1]
        for a, b in zip(ids, ids[1:] + ids[:1]):
            if a == b:
                continue
            lim = 4.0 * float(np.linalg.norm(V[a] - V[b])) + 1.0
            dist, pred = dijkstra(G, indices=a, limit=lim, return_predecessors=True)
            if not np.isfinite(dist[b]):
                continue
            x = b
            while x != a:
                y = int(pred[x]); corte.add((int(min(x, y)), int(max(x, y)))); comp += float(np.linalg.norm(V[x] - V[y])); x = y
    key_u = u[:, 0].astype(np.int64) * len(V) + u[:, 1]
    ck = np.array([a * len(V) + b for a, b in corte], np.int64)
    eh_corte = np.isin(key_u, ck)
    # triângulos vizinhos pelas arestas que não são navalha
    tri_of = np.tile(np.arange(len(F)), 3)
    o = np.argsort(inv); inv_s = inv[o]; t_s = tri_of[o]
    st = np.r_[0, np.where(np.diff(inv_s))[0] + 1]
    pares = []
    for k in (0,):
        pass
    a_ = t_s[st]; b_ = t_s[np.minimum(st + 1, len(t_s) - 1)]
    ed_id = inv_s[st]
    par = np.r_[np.diff(st), len(t_s) - st[-1]] == 2
    # onde a linha não fecha a área (o cabelo fundido na gola), a borda extra da área desenhada (o corte
    # mínimo do app) também vira navalha, só longe da linha
    lp_all = np.vstack([np.asarray(L, float) for L in loops])
    dv, _ = cKDTree(lp_all).query(V)
    ea, eb = u[ed_id, 0], u[ed_id, 1]
    extra = par & (A[a_] != A[b_]) & (dv[ea] > 1.5) & (dv[eb] > 1.5)
    EXTRA[0] = float(np.linalg.norm(V[ea[extra]] - V[eb[extra]], axis=1).sum())
    okp = par & ~eh_corte[ed_id] & ~extra
    Gt = coo_matrix((np.ones(okp.sum()), (a_[okp], b_[okp])), shape=(len(F), len(F)))
    nc, lab = connected_components(Gt, directed=False)
    fa = np.bincount(lab, weights=A.astype(float), minlength=nc); ft = np.bincount(lab, minlength=nc)
    ladoA = (fa / np.maximum(ft, 1)) > 0.5
    # ilhas pequenas (até 3 mm², ruído da área desenhada) ficam com o lado da parte vizinha maior
    T_ = V[F]; ar = np.linalg.norm(np.cross(T_[:, 1] - T_[:, 0], T_[:, 2] - T_[:, 0]), axis=1) / 2
    ca = np.bincount(lab, weights=ar, minlength=nc)
    viz_a, viz_b = lab[a_[par]], lab[b_[par]]
    for c in np.where(ca < 3.0)[0]:
        nb = np.r_[viz_b[viz_a == c], viz_a[viz_b == c]]; nb = nb[nb != c]
        if len(nb):
            big = nb[np.argmax(ca[nb])]; ladoA[c] = ladoA[big]
    selA = ladoA[lab]
    return F[selA], F[~selA], nc, comp


def dividir_por_arestas(V, F, loops, A):
    """A navalha pela linha e, quando ela sozinha não separa a pele (um cacho fundido no rosto encosta na testa
    perto da linha), a divisão pela borda da área com a distância medida pela pele."""
    CONTATO.clear()
    At, Bt, nc, comp = _dividir_navalha(V, F, loops, A)
    if len(At) or not np.asarray(A).any():
        return At, Bt, nc, comp
    return _dividir_pela_pele(V, F, loops, np.asarray(A, bool), comp)


def _dividir_pela_pele(V, F, loops, A, comp, lim=1.5):
    """1.49: a navalha não separou a pele. A borda da área desenhada vira costura extra onde ela está a mais de
    1,5 mm da navalha medindo pela pele (Dijkstra a partir dos vértices da navalha), e não em linha reta: o lado
    de baixo de um cacho que encosta na testa fica perto da linha em linha reta e longe dela pela pele. Os laços
    da peça que não seguem a linha são contatos (o cacho apoiado na pele) e recebem a tampa de contato."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra, connected_components
    Ed = np.vstack([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]); Es = np.sort(Ed, 1)
    u, inv = np.unique(Es, axis=0, return_inverse=True); inv = inv.ravel()
    w = np.linalg.norm(V[u[:, 0]] - V[u[:, 1]], axis=1)
    G = coo_matrix((np.r_[w, w], (np.r_[u[:, 0], u[:, 1]], np.r_[u[:, 1], u[:, 0]])), shape=(len(V), len(V))).tocsr()
    kd = cKDTree(V); corte = set()
    for L in loops:
        _, ids = kd.query(np.asarray(L, float))
        ids = [int(x) for k, x in enumerate(ids) if k == 0 or x != ids[k - 1]]
        if ids[0] == ids[-1]:
            ids = ids[:-1]
        for a, b in zip(ids, ids[1:] + ids[:1]):
            if a == b:
                continue
            dist, pred = dijkstra(G, indices=a, limit=4.0 * float(np.linalg.norm(V[a] - V[b])) + 1.0, return_predecessors=True)
            if not np.isfinite(dist[b]):
                continue
            x = b
            while x != a:
                y = int(pred[x]); corte.add((min(x, y), max(x, y))); x = y
    if not corte:
        return F[:0], F, 1, comp
    nv = np.unique(np.array(list(corte)).ravel())
    dg = dijkstra(G, indices=nv, min_only=True, limit=lim + 1.0)
    key_u = u[:, 0].astype(np.int64) * len(V) + u[:, 1]
    ck = np.array([a * len(V) + b for a, b in corte], np.int64); eh = np.isin(key_u, ck)
    tri_of = np.tile(np.arange(len(F)), 3); oo = np.argsort(inv); iv = inv[oo]; ts = tri_of[oo]
    st = np.r_[0, np.where(np.diff(iv))[0] + 1]
    a_ = ts[st]; b_ = ts[np.minimum(st + 1, len(ts) - 1)]; ed = iv[st]
    par = np.r_[np.diff(st), len(ts) - st[-1]] == 2
    ea, eb = u[ed, 0], u[ed, 1]
    extra = par & (A[a_] != A[b_]) & (dg[ea] > lim) & (dg[eb] > lim)
    EXTRA[0] = float(np.linalg.norm(V[ea[extra]] - V[eb[extra]], axis=1).sum())
    okp = par & ~eh[ed] & ~extra
    nc, lab = connected_components(coo_matrix((np.ones(okp.sum()), (a_[okp], b_[okp])), shape=(len(F), len(F))), directed=False)
    fa = np.bincount(lab, weights=A.astype(float), minlength=nc); ft = np.bincount(lab, minlength=nc)
    ladoA = (fa / np.maximum(ft, 1)) > 0.5
    T_ = V[F]; ar = np.linalg.norm(np.cross(T_[:, 1] - T_[:, 0], T_[:, 2] - T_[:, 0]), axis=1) / 2
    ca = np.bincount(lab, weights=ar, minlength=nc)
    va, vb = lab[a_[par]], lab[b_[par]]
    for c in np.where(ca < 3.0)[0]:
        nb = np.r_[vb[va == c], va[vb == c]]; nb = nb[nb != c]
        if len(nb):
            ladoA[c] = ladoA[nb[np.argmax(ca[nb])]]
    sel = ladoA[lab]
    At = F[sel]; Bt = F[~sel]
    kdl = cKDTree(np.vstack([np.asarray(L, float) for L in loops]))
    for la in lacos_borda(At):
        dl = kdl.query(V[la])[0]
        if np.mean(dl < 0.3) < 0.1:
            CONTATO[frozenset(int(x) for x in la)] = dict(V=V, At=At, Bt=Bt)
    return At, Bt, nc, comp


def lacos_borda(T):
    """Laços de borda (arestas usadas uma vez), em ordem, orientados como a borda dos triângulos."""
    Ed = np.vstack([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
    k = np.sort(Ed, 1)
    u, inv, cnt = np.unique(k, axis=0, return_inverse=True, return_counts=True)
    bd = Ed[cnt[inv] == 1]
    nxt = {}
    for a, b in bd:
        nxt.setdefault(int(a), []).append(int(b))
    usados = set(); lacos = []
    for a0 in list(nxt):
        if a0 in usados:
            continue
        laco = [a0]; usados.add(a0); a = a0
        while True:
            bs = [b for b in nxt.get(a, []) if b not in usados or (b == a0 and len(laco) > 2)]
            if not bs:
                break
            b = bs[0]
            if b == a0:
                break
            laco.append(b); usados.add(b); a = b
        lacos.append(np.array(laco))
    return lacos


def altura(T, A, d, cel, area, lp):
    """Mesma conta da prova anterior: limites de cada coluna e membrana presa na linha."""
    a = analisar(T, A, d, cel, area)
    C, Z, L, st, grp, pos, lastB, shape = a['C'], a['Z'], a['L'], a['st'], a['grp'], a['pos'], a['lastB'], a['shape']
    n = shape[0] * shape[1]
    lb = np.full(n, -np.inf); ub = np.full(n, np.inf)
    cell = C[st]
    lastB = lastB.copy()
    okA = L & (pos > lastB[grp])
    firstA = np.full(len(st), len(C)); np.minimum.at(firstA, grp[okA], pos[okA])
    # 1.49, coluna presa: a peça sai e depois vem outra parte na frente, sem a peça depois dela. O último resto
    # da coluna inteira põe a tampa na frente da outra parte; ali vale o resto logo antes da primeira saída da peça
    temA = np.zeros(len(st), bool); temA[grp[L]] = True
    presa = temA & (firstA >= len(C))
    if presa.any():
        fA = np.full(len(st), len(C)); np.minimum.at(fA, grp[L], pos[L])
        antes = ~L & (pos < fA[grp])
        lB2 = np.full(len(st), -1); np.maximum.at(lB2, grp[antes], pos[antes])
        # resto colado atrás da pele da peça (menos de 1 mm): sem limite de baixo ali, só o de cima
        gB = np.where(lB2 >= 0, Z[np.minimum(fA, len(C) - 1)] - Z[np.maximum(lB2, 0)], np.inf)
        lB2 = np.where(presa & (gB < 1.0), -1, lB2)
        lastB = np.where(presa, lB2, lastB); firstA = np.where(presa, fA, firstA)
    has_b = lastB >= 0
    lb[cell[has_b]] = Z[lastB[has_b]]
    has_a = firstA < len(C)
    ub[cell[has_a]] = Z[firstA[has_a]]
    lc, lz, _ = linha_celulas(lp, a['R'], a['lo'], shape, cel)
    gap = ub - lb
    m = np.where(np.isfinite(gap), np.minimum(0.8, gap / 3), 0.8)          # tampa longe da pele (até 0,8 mm)
    lb2, ub2 = lb + m, ub - m
    lb2[lc] = lz - 0.01; ub2[lc] = lz + 0.01
    h = membrana(lc, lz, lb2, ub2, shape)
    return h, a


def _interp(h, lo, cel, uv):
    gx = (uv[:, 0] - lo[0]) / cel - 0.5; gy = (uv[:, 1] - lo[1]) / cel - 0.5
    i0 = np.clip(np.floor(gx).astype(int), 0, h.shape[0] - 2); j0 = np.clip(np.floor(gy).astype(int), 0, h.shape[1] - 2)
    fx = np.clip(gx - i0, 0, 1); fy = np.clip(gy - j0, 0, 1)
    return (h[i0, j0] * (1 - fx) * (1 - fy) + h[i0 + 1, j0] * fx * (1 - fy) + h[i0, j0 + 1] * (1 - fx) * fy + h[i0 + 1, j0 + 1] * fx * fy)


def tampa(Vall, laco, R, h, lo, cel, passo):
    """Triangula o laço projetado em d (sem ponto novo na borda) e sobe os pontos de dentro até a membrana."""
    from shapely.geometry import Polygon
    info = CONTATO.get(frozenset(int(x) for x in laco))
    if info is not None:
        return tampa_contato(Vall, np.asarray(laco), R, info)
    P3 = Vall[laco]; Q = P3 @ R.T
    uv = Q[:, :2]
    pg = Polygon(uv)
    if not pg.is_valid or pg.area < 1e-6:
        return None, 'o laço da linha se dobra visto da direção de saída'
    n = len(uv)
    seg = np.c_[np.arange(n), (np.arange(n) + 1) % n]
    tri = _triangular(uv, passo)
    if tri is None:
        return None, 'triangulação da tampa falhou'
    TV = tri['vertices']; TT = tri['triangles']
    if len(TV) < n or not np.allclose(TV[:n], uv):
        return None, 'a triangulação mudou a borda'
    inner = TV[n:]
    z = _interp(h, lo, cel, inner) if len(inner) else np.zeros(0)
    Pin = np.c_[inner, z] @ R if len(inner) else np.zeros((0, 3))
    return dict(tris=TT, n_borda=n, inner_uv=inner, inner_z=z, P_in=Pin, area=pg.area), None


def tampa_contato(Vall, laco, R, info, passo=0.3):
    """1.49: tampa de um laço de contato (um cacho apoiado na pele, longe da linha): a superfície do próprio
    contato (plano médio do laço), não a face de dentro da peça, que passaria por dentro da cabeça e achataria o
    cacho. A folga anda pela normal do contato, para o lado da peça (ver montar)."""
    P = Vall[laco]; c = P.mean(0)
    _, Ev = np.linalg.eigh(np.cov((P - c).T)); e1, e2, nr = Ev[:, 2], Ev[:, 1], Ev[:, 0]
    V = info['V']; ca = V[info['At']].mean(1); cb = V[info['Bt']].mean(1)
    da = np.linalg.norm(ca - c, axis=1) < 3.0; db = np.linalg.norm(cb - c, axis=1) < 3.0
    if da.any() and db.any() and np.dot(ca[da].mean(0) - cb[db].mean(0), nr) < 0:
        nr = -nr
    uv = np.c_[(P - c) @ e1, (P - c) @ e2]
    tri = _triangular(uv, passo)
    if tri is None:
        return None, 'triangulação da tampa de contato falhou'
    TV = tri['vertices']; TT = tri['triangles']; n = len(uv); inner = TV[n:]
    zb = (P - c) @ nr
    if len(inner):
        dd = np.linalg.norm(inner[:, None, :] - uv[None, :, :], axis=2) + 1e-6; wgt = 1 / dd ** 2
        zi = (wgt * zb[None, :]).sum(1) / wgt.sum(1)
        P3 = c + inner[:, 0:1] * e1 + inner[:, 1:2] * e2 + zi[:, None] * nr
    else:
        P3 = np.zeros((0, 3))
    Q = P3 @ R.T
    return dict(tris=TT, n_borda=n, inner_uv=Q[:, :2], inner_z=Q[:, 2], P3c=P3, P3=P3, area=0.0, contato=True, nrm=nr), None


def tampa_parede(Vall, laco, R, h, lo, cel, passo, recuo=0.3):
    """Tampa quando o laço se dobra visto da direção (a linha corre ao longo de d, como nas costeletas):
    o miolo é o gráfico da membrana sobre a área do laço recuada 0,3 mm, e uma faixa liga a linha a esse
    miolo. Onde a linha corre ao longo de d, a faixa fica de pé, paralela a d: parede reta que não trava."""
    from shapely.geometry import Polygon, Point
    from shapely.validation import make_valid
    from shapely.geometry.polygon import orient
    lac = np.asarray(laco)
    uv = (Vall[lac] @ R.T)[:, :2]
    sa = 0.5 * np.sum(uv[:, 0] * np.roll(uv[:, 1], -1) - np.roll(uv[:, 0], -1) * uv[:, 1])
    if sa < 0:
        lac = lac[::-1]; uv = uv[::-1]
    g = make_valid(Polygon(uv))
    ps = [x for x in getattr(g, 'geoms', [g]) if x.geom_type == 'Polygon']
    if not ps:
        return None, 'o laço não forma área vista da direção'
    big = max(ps, key=lambda x: x.area)
    pg = big.buffer(-recuo)
    for rc in (recuo / 3, recuo / 10):
        if not pg.is_empty and pg.area > 1e-4:
            break
        pg = big.buffer(-rc)
    if pg.is_empty or pg.area <= 1e-4:
        return None, 'o laço é estreito demais visto da direção'
    pg = max([x for x in getattr(pg, 'geoms', [pg]) if x.geom_type == 'Polygon'], key=lambda x: x.area)
    pg = orient(Polygon(pg.exterior), 1.0)
    ext = pg.exterior; Lr = ext.length
    m = max(12, int(Lr / (passo * 0.7)))
    ring = np.array([ext.interpolate(t).coords[0] for t in np.linspace(0, Lr, m, endpoint=False)])
    seg = np.c_[np.arange(m), (np.arange(m) + 1) % m]
    tri = _triangular(ring, passo) or _triangular_restrita(ring)
    if tri is None:
        return None, 'triangulação da tampa falhou'
    TV = tri['vertices']; TT = tri['triangles']
    if len(TV) < m or not np.allclose(TV[:m], ring):
        return None, 'a triangulação mudou a borda do miolo'
    # parâmetro de cada ponto da linha ao longo do miolo, em ordem
    n = len(lac)
    t = np.array([ext.project(Point(p)) for p in uv])
    k0 = int(np.argmin(t)); order = np.r_[np.arange(k0, n), np.arange(0, k0)]
    tt = t[order].copy()
    for k in range(1, n):                                   # desenrola e impede voltar
        while tt[k] < tt[k - 1] - Lr / 2:
            tt[k] += Lr
        tt[k] = max(tt[k], tt[k - 1])
    r = np.linspace(0, Lr, m, endpoint=False)
    j0 = int(np.searchsorted(r, tt[0] % Lr)) % m
    rj = np.r_[np.arange(j0, m), np.arange(0, j0)]
    rr = (r[rj] - tt[0]) % Lr + tt[0]
    # costura em zíper: i anda na linha, j no miolo
    Lid = lambda i: int(order[i % n])                      # índice local do ponto da linha
    Rid = lambda j: n + int(rj[j % m])                     # índice local do ponto do miolo
    tris = []; i = j = 0
    tl = np.r_[tt, tt[0] + Lr]; tr_ = np.r_[rr, rr[0] + Lr]
    while i < n or j < m:
        av_l = i < n and (j >= m or tl[i + 1] <= tr_[j + 1])
        if av_l:
            tris.append([Lid(i), Lid(i + 1), Rid(j)]); i += 1
        else:
            tris.append([Lid(i), Rid(j + 1), Rid(j)]); j += 1
    strip = np.array(tris)
    inner = TV; z = _interp(h, lo, cel, inner)
    tl_all = np.vstack([strip, TT + n])
    return dict(tris=tl_all, laco=lac, inner_uv=inner, inner_z=z, area=pg.area, parede=True), None


def _tem_aresta(T, a, b):
    """True se algum triângulo tem a aresta a->b nesse sentido, False se b->a, None se nenhuma."""
    for k in range(3):
        m = (T[:, k] == a) & (T[:, (k + 1) % 3] == b)
        if m.any():
            return True
        m = (T[:, k] == b) & (T[:, (k + 1) % 3] == a)
        if m.any():
            return False
    return None


def _dentro(P, a, cel):
    """Ponto dentro do sólido: na coluna dele (direção d), o número de toques na pele abaixo do ponto é ímpar."""
    Q = P @ a['R'].T
    I = np.floor((Q[:, 0] - a['lo'][0]) / cel).astype(int); J = np.floor((Q[:, 1] - a['lo'][1]) / cel).astype(int)
    ok = (I >= 0) & (J >= 0) & (I < a['shape'][0]) & (J < a['shape'][1])
    cell = np.where(ok, I * a['shape'][1] + J, -1)
    C, Z, st = a['C'], a['Z'], a['st']
    cu = C[st]; en = np.r_[st[1:], len(C)]
    k = np.searchsorted(cu, cell); k = np.clip(k, 0, len(cu) - 1)
    tem = ok & (cu[k] == cell)
    res = np.zeros(len(P), bool)
    for q in np.where(tem)[0]:
        zs = Z[st[k[q]]:en[k[q]]]
        res[q] = (np.searchsorted(zs, Q[q, 2]) % 2) == 1
    return res


def montar(Vall, pele_tris, tampas, lacos, R, lado, folga):
    """Peça = pele (triângulos originais divididos) + tampa de cada laço, com metade da folga para dentro dela."""
    Vs = [Vall]; Ts = [pele_tris]; off = len(Vall)
    for tp, laco in zip(tampas, lacos):
        laco = tp.get('laco', laco)
        if tp.get('contato'):                          # tampa de contato: a folga pela normal do contato
            Pin = tp['P3c'] + (lado * folga / 2) * tp['nrm']
        elif tp.get('P3') is not None:                  # tampa acomodada dentro da peça (3D)
            Pin = tp['P3'] + (lado * folga / 2) * R[2]
        else:
            z = tp['inner_z'] + lado * folga / 2
            Pin = np.c_[tp['inner_uv'], z] @ R
        mapa = np.r_[laco, off + np.arange(len(Pin))]
        tt = mapa[tp['tris']]
        # a tampa percorre a borda no sentido contrário ao da pele (senão a malha não fecha)
        a0, b0 = int(laco[0]), int(laco[1])
        pele_tem = _tem_aresta(pele_tris, a0, b0)
        tampa_tem = _tem_aresta(tt, a0, b0)
        if pele_tem == tampa_tem:
            tt = tt[:, ::-1]
        Ts.append(tt)
        Vs.append(Pin); off += len(Pin)
    V = np.vstack(Vs); T = np.vstack(Ts)
    usados = np.unique(T); re = -np.ones(len(V), int); re[usados] = np.arange(len(usados))
    V2, T2 = V[usados], re[T]
    m = _mk(V2, T2)
    if m.status() != M.Error.NoError:
        return None, f'malha não fechou ({m.status().name})'
    if m.volume() < 0:
        m = _mk(V2, T2[:, ::-1])
    return m, None


def _triangular(uv, passo):
    """Triangulação da área do laço (borda uv em ordem, sem ponto novo na borda) com pontos de dentro numa
    grade. Devolve dict(vertices, triangles) com os n primeiros vértices = a borda, ou None."""
    from shapely.geometry import Polygon
    from shapely import contains_xy, distance, points
    from scipy.spatial import Delaunay
    uv = np.asarray(uv, float); n = len(uv)
    pg = Polygon(uv)
    if not pg.is_valid or pg.area <= 0:
        return None
    lo, hi = uv.min(0), uv.max(0)
    xs = np.arange(lo[0] + passo / 2, hi[0], passo); ys = np.arange(lo[1] + passo / 2, hi[1], passo)
    if len(xs) and len(ys):
        X, Y = np.meshgrid(xs, ys, indexing='ij'); X, Y = X.ravel(), Y.ravel()
        ok = contains_xy(pg, X, Y)
        X, Y = X[ok], Y[ok]
        if len(X):
            dd = distance(points(np.c_[X, Y]), pg.exterior)
            keep = dd > 0.6 * passo
            X, Y = X[keep], Y[keep]
        inner = np.c_[X, Y]
    else:
        inner = np.zeros((0, 2))
    borda = {(min(k, (k + 1) % n), max(k, (k + 1) % n)) for k in range(n)}
    for _ in range(8):
        P = np.vstack([uv, inner])
        try:
            tri = Delaunay(P, qhull_options='QJ' if len(P) < 4 else 'Qbb Qc').simplices
        except Exception:
            return None
        c = P[tri].mean(1)
        tri = tri[contains_xy(pg, c[:, 0], c[:, 1])]
        ed = {}
        for t in tri:
            for k in range(3):
                a_, b_ = int(t[k]), int(t[(k + 1) % 3]); e_ = (min(a_, b_), max(a_, b_)); ed[e_] = ed.get(e_, 0) + 1
        # 1.49: borda com exatamente um triângulo e nenhuma aresta em três ou mais (num polígono com cintura a
        # Delaunay liga os dois lados e a malha não fecha)
        falta = [e for e in borda if ed.get(e, 0) != 1] + [e for e, c_ in ed.items() if c_ > 2]
        if not falta:
            a2 = P[tri]; sa = (a2[:, 1, 0] - a2[:, 0, 0]) * (a2[:, 2, 1] - a2[:, 0, 1]) - (a2[:, 2, 0] - a2[:, 0, 0]) * (a2[:, 1, 1] - a2[:, 0, 1])
            tri = np.where((sa < 0)[:, None], tri[:, ::-1], tri)
            return dict(vertices=P, triangles=tri)
        if not len(inner):
            return None
        tira = np.zeros(len(inner), bool)
        for a_, b_ in falta:
            m_ = (P[a_] + P[b_]) / 2; L_ = np.linalg.norm(P[a_] - P[b_])
            tira |= np.linalg.norm(inner - m_, axis=1) < max(1.2 * L_, passo)
        inner = inner[~tira]
    return None


def _triangular_restrita(uv):
    """1.49: triangulação de Delaunay restrita à borda, sem ponto novo (shapely.constrained_delaunay_triangles),
    para o miolo da tampa de parede quando a de grade não fecha (polígono estrangulado)."""
    from shapely.geometry import Polygon
    from shapely import constrained_delaunay_triangles
    uv = np.asarray(uv, float)
    pg = Polygon(uv)
    if not pg.is_valid or pg.area <= 0:
        return None
    idx = {(round(float(p[0]), 9), round(float(p[1]), 9)): k for k, p in enumerate(uv)}
    tris = []
    for t in constrained_delaunay_triangles(pg).geoms:
        try:
            tris.append([idx[(round(x, 9), round(y, 9))] for x, y in list(t.exterior.coords)[:3]])
        except KeyError:
            return None
    tri = np.array(tris, int)
    a2 = uv[tri]; sa = (a2[:, 1, 0] - a2[:, 0, 0]) * (a2[:, 2, 1] - a2[:, 0, 1]) - (a2[:, 2, 0] - a2[:, 0, 0]) * (a2[:, 1, 1] - a2[:, 0, 1])
    tri = np.where((sa < 0)[:, None], tri[:, ::-1], tri)
    E_ = np.vstack([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
    if (np.unique(np.sort(E_, 1), axis=0, return_counts=True)[1] > 2).any():
        return None
    return dict(vertices=uv, triangles=tri)


def analisar(T, A, d, cel, area, cen=None):
    """A peça (lado A) sai em +d. Só os triângulos na coluna da área da peça contam (mais rápido)."""
    R = frame(d)
    if cen is None:
        cen = T.mean(1)
    Qc = cen @ R.T
    a_lo = Qc[A, :2].min(0) - 3.0; a_hi = Qc[A, :2].max(0) + 3.0
    sel = np.where(np.all((Qc[:, :2] >= a_lo) & (Qc[:, :2] <= a_hi), 1))[0]
    T2, A2 = T[sel], A[sel]
    C, Z, TT, lo, shape = colunas(T2, R, cel)
    L = A2[TT]
    st = np.r_[0, np.where(np.diff(C))[0] + 1]
    grp = np.repeat(np.arange(len(st)), np.diff(np.r_[st, len(C)]))
    pos = np.arange(len(C))
    lastB = np.full(len(st), -1); np.maximum.at(lastB, grp[~L], pos[~L])
    bad = L & (pos < lastB[grp])
    tr = np.zeros(len(T), bool); tr[sel[TT[bad]]] = True
    return dict(R=R, C=C, Z=Z, TT=TT, L=L, st=st, grp=grp, pos=pos, lastB=lastB, lo=lo, shape=shape,
                trava=tr, area=float(area[tr].sum()))


def _nota(T, A, d, cel, area, lp, nl, lacos, cen):
    from shapely.geometry import Polygon
    a = analisar(T, A, d, cel, area, cen)
    _, _, dobra = linha_celulas(lp, a['R'], a['lo'], a['shape'], cel)
    pen = 2.0 * (1 - abs(float(np.dot(d, nl))))
    for L in lacos:
        if not Polygon((L @ a['R'].T)[:, :2]).is_valid:
            pen += 1000.0
            break
    return a['area'] + 0.1 * dobra + pen, a['area']


def escolher_direcao(T, A, area, lp, lacos):
    """Direção de saída sugerida: a que menos trava, sem dobrar a linha vista dela, e perto da normal da linha."""
    cen = T.mean(1)
    nl = normal_linha(lp)
    D = np.vstack([fib(40), nl, -nl])
    sc = np.array([_nota(T, A, d, 1.6, area, lp, nl, lacos, cen)[0] for d in D])
    best = None
    for d0 in D[np.argsort(sc)[:2]]:
        for dd in [d0] + [d0 + 0.13 * x for x in fib(8)]:
            dd = dd / np.linalg.norm(dd)
            s, a = _nota(T, A, dd, 0.8, area, lp, nl, lacos, cen)
            if best is None or s < best[0] - 1e-6:
                best = (s, dd, a)
    return best[1], best[2], best[0]


class _Pele:
    """Ponto mais perto na pele (aproximado por amostras densas dos triângulos perto da tampa) e a normal."""
    def __init__(self, V, F, lo, hi):
        T = V[F]
        sel = np.all((T.max(1) >= lo) & (T.min(1) <= hi), 1)
        T = T[sel]
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        w = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1], [1 / 3, 1 / 3, 1 / 3], [.5, .5, 0], [0, .5, .5], [.5, 0, .5]])
        self.P = np.einsum('kj,ijx->ikx', w, T).reshape(-1, 3)
        self.N = np.repeat(n, len(w), 0)
        self.kd = cKDTree(self.P)

    def perto(self, Q):
        d, i = self.kd.query(Q)
        return self.P[i], d, self.N[i]


def refinar(tp, laco, Vall, R, lmax=1.0, perto=0.8, rodadas=4):
    """1.49: divide os triângulos da tampa com aresta de mais de 1 mm em 3D. A tampa é triangulada na projeção
    ao longo da direção de saída; onde a pele corre quase paralela a ela (têmporas), o passo de 0,6 mm vira
    aresta de 3 a 4 mm em 3D e a corda passa rente à pele. As arestas da borda (pele) ficam, e nada muda a menos
    de 0,8 mm da linha (ali a tampa encontra a pele de qualquer jeito)."""
    lac = np.asarray(tp.get('laco', laco)); n = len(lac)
    P = np.c_[tp['inner_uv'], tp['inner_z']] @ R
    T = np.asarray(tp['tris']).copy()
    kd = cKDTree(Vall[lac]); novos = 0
    for _ in range(rodadas):
        X = np.vstack([Vall[lac], P])
        E_ = np.vstack([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
        u, inv = np.unique(np.sort(E_, 1), axis=0, return_inverse=True); inv = inv.ravel()
        L = np.linalg.norm(X[u[:, 0]] - X[u[:, 1]], axis=1)
        marca = (L > lmax) & ~((u[:, 0] < n) & (u[:, 1] < n))
        if marca.any():
            marca &= kd.query((X[u[:, 0]] + X[u[:, 1]]) / 2)[0] >= perto
        if not marca.any():
            break
        mid = -np.ones(len(u), int); k = np.where(marca)[0]; mid[k] = len(X) + np.arange(len(k))
        P = np.vstack([P, (X[u[k, 0]] + X[u[k, 1]]) / 2]); novos += len(k)
        out = []
        for t, (ab, bc, ca) in zip(T, mid[inv].reshape(3, -1).T):
            a, b, c = t
            s_ = int(ab >= 0) + int(bc >= 0) + int(ca >= 0)
            if s_ == 0: out.append(t)
            elif s_ == 3: out += [[a, ab, ca], [ab, b, bc], [ca, bc, c], [ab, bc, ca]]
            elif s_ == 1:
                if ab >= 0: out += [[a, ab, c], [ab, b, c]]
                elif bc >= 0: out += [[a, b, bc], [a, bc, c]]
                else: out += [[a, b, ca], [ca, b, c]]
            else:
                if ab < 0: out += [[a, b, bc], [a, bc, ca], [ca, bc, c]]
                elif bc < 0: out += [[a, ab, ca], [ab, b, c], [ab, c, ca]]
                else: out += [[a, ab, bc], [a, bc, c], [ab, b, bc]]
        T = np.asarray(out, int)
    if novos:
        Q = P @ R.T
        tp['tris'] = T; tp['inner_uv'] = Q[:, :2]; tp['inner_z'] = Q[:, 2]; tp.pop('P_in', None)
    return novos


def acomodar(tp, laco, Vall, pele, R, folga, a, cel, it=12, alvo_mm=1.0):
    """A tampa fica dentro do sólido e a pelo menos 1 mm da pele (perto da linha a exigência cai até 0,3 mm,
    porque ali a tampa encontra a pele). O ponto anda ao longo da direção de saída (a peça continua saindo
    reta); só onde a pele corre ao longo da direção ele anda para dentro pela normal."""
    from scipy.sparse import coo_matrix
    if tp.get('contato'):                              # a tampa de contato já é a superfície do contato
        return 0
    if not tp.get('parede'):
        refinar(tp, laco, Vall, R)
    lac = np.asarray(tp.get('laco', laco)); n = len(lac)
    P = np.c_[tp['inner_uv'], tp['inner_z']] @ R
    if not len(P):
        tp['P3'] = P
        return 0
    d = R[2]
    tri = tp['tris']
    E_ = np.vstack([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
    nloc = n + len(P)
    W = coo_matrix((np.ones(2 * len(E_)), (np.r_[E_[:, 0], E_[:, 1]], np.r_[E_[:, 1], E_[:, 0]])), shape=(nloc, nloc)).tocsr()
    W.data[:] = 1.0
    deg = np.asarray(W.sum(1)).ravel()
    kdl = cKDTree(Vall[lac]); dl, _ = kdl.query(P)
    alvo = np.clip(0.3 + (dl - 0.5) * 0.5, 0.3, alvo_mm) + folga / 2
    movidos = 0
    for _ in range(it):
        cp, dist, nrm = pele.perto(P)
        # 1.49: a distância à linha conta também a partir do pé na pele (a régua mede a parede a partir da pele;
        # onde a tampa corre rasante, perto da linha pela tampa é longe dela pela pele)
        alvo = np.clip(0.3 + (np.maximum(dl, kdl.query(cp)[0]) - 0.5) * 0.5, 0.3, alvo_mm) + folga / 2
        dentro = _dentro(P, a, cel)
        sd = np.where(dentro, dist, -dist)
        ruim = sd < alvo
        if not ruim.any():
            break
        movidos = max(movidos, int(ruim.sum()))
        nin = -nrm
        c = nin @ d
        falta = (alvo - sd)[ruim]
        ok = np.abs(c[ruim]) > 0.25
        mov = np.zeros((int(ruim.sum()), 3))
        mov[ok] = (np.sign(c[ruim][ok]) * np.minimum(falta[ok] / np.abs(c[ruim][ok]), 3.0))[:, None] * d
        mov[~ok] = falta[~ok][:, None] * nin[ruim][~ok]
        P[ruim] += mov
        allP = np.vstack([Vall[lac], P])
        media = (W @ allP) / np.maximum(deg, 1)[:, None]
        P = 0.7 * P + 0.3 * media[n:]
    if ALISAR_TAMPA:
        P = _alisar(P, Vall[lac], W, deg, n, pele, a, cel, kdl, folga, alvo_mm)
    tp['P3'] = P
    return movidos


ALISAR_TAMPA = os.environ.get('FLEXI_ALISAR_TAMPA', '1') == '1'
SOQUETE_NO_FIM = os.environ.get('FLEXI_SOQUETE_PELE', '1') == '1'


def _alisar(P, B, W, deg, n, pele, a, cel, kdl, folga, alvo_mm, it=25):
    """1.55: tira os dentes da tampa. O empurrão do acomodar anda até 3 mm por rodada pela direção de saída onde a
    pele corre quase paralela a ela, e a média de 30% não puxa de volta um ponto isolado: fica um espinho na faixa
    junto da costura. Aqui cada ponto vai para a média dos vizinhos (a borda na pele fica parada) e o passo só vale
    se o ponto continua dentro do sólido, à distância pedida da pele; senão fica onde estava."""
    dl = kdl.query(P)[0]
    for _ in range(it):
        allP = np.vstack([B, P])
        media = ((W @ allP) / np.maximum(deg, 1)[:, None])[n:]
        sel = np.where(np.linalg.norm(media - P, axis=1) > 0.1)[0]     # só o que sai da média (os dentes)
        if not len(sel):
            break
        Q = 0.5 * P[sel] + 0.5 * media[sel]
        cp, dist, _ = pele.perto(Q)
        alvo = np.clip(0.3 + (np.maximum(dl[sel], kdl.query(cp)[0]) - 0.5) * 0.5, 0.3, alvo_mm) + folga / 2
        ok = _dentro(Q, a, cel) & (dist >= alvo - 0.02)
        if not ok.any():
            break
        P = P.copy()
        P[sel[ok]] = Q[ok]
    return P


# ------------------------------------------------------------------ direção
def vetor(az, el):
    """az 0 = frente (-y), 90 = direita (+x), 180 = trás, 270 = esquerda; el 90 = para cima, -90 = para baixo."""
    a, e = math.radians(float(az)), math.radians(float(el))
    return np.array([math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)])


def angulos(d):
    d = np.asarray(d, float) / np.linalg.norm(d)
    el = math.degrees(math.asin(max(-1.0, min(1.0, d[2]))))
    az = math.degrees(math.atan2(d[0], -d[1])) % 360.0
    return round(az), round(el)


def _texto_dir(d):
    az, el = angulos(d)
    nomes = {0: 'para a frente', 90: 'para a direita', 180: 'para trás', 270: 'para a esquerda'}
    if el >= 75:
        return 'para cima'
    if el <= -75:
        return 'para baixo'
    k = min(nomes, key=lambda x: min(abs(az - x), 360 - abs(az - x)))
    base = nomes[k]
    if el >= 20:
        return f'para cima e {base} ({el}° de inclinação)'
    if el <= -20:
        return f'para baixo e {base} ({-el}° de inclinação)'
    return base


def _chk(nivel, texto):
    return dict(nivel=nivel, texto=texto)


# ------------------------------------------------------------------ o corte
def cortar(cur, cut, i, S, diag, centro, FC):
    """Um corte livre pela pele. Devolve (out novo, resultado) ou (None, motivo) para o motor anterior fazer."""
    t0 = time.time()
    nome = cut.get('nome') or f'Corte {i + 1}'
    enc = cut.get('encaixe') or 'colar'
    if enc in ('redondo', 'giratorio'):
        return None, 'peça que gira precisa de face plana'
    if cut.get('plano'):
        return None, 'corte plano'
    loops = [L for L in (FC._clean_loop(x) for x in (cut.get('linhas') or [])) if L is not None]
    pieces = list(cur['pieces'])
    mk_host = None
    if cut.get('mascara'):
        return None, 'área marcada com pincel ou balde (este motor usa a linha)'
    if not loops:
        return None, 'sem linha'
    cand = [k for k, p in enumerate(pieces) if p.get('tipo') != 'cavilha']
    if cut.get('peca') and cut['peca'].get('ponto') is not None:
        hk = FC._piece_at(pieces, cut['peca']['ponto'], loops)
        if hk < 0:
            return None, 'a peça do corte não foi achada'
    else:
        k_, _ = FC._host_by_lines([pieces[k] for k in cand], loops); hk = cand[k_]
    host = pieces[hk]; hm = host['mesh']
    if REFINO:
        # triângulos compridos perto da linha (base plana) são divididos antes da navalha; malha fina fica igual
        Vh0, Fh0 = _vf(hm)
        Vr, Fr, nr_ = refinar_perto_da_linha(Vh0, Fh0, _densa(loops, 0.25))
        if nr_:
            hm = _mk(Vr, Fr)
    mm = FC.mask_from_lines(hm, loops, SPL._topology(hm), diag, centro, bool(cut.get('inverter')))
    if mm is None or not np.asarray(mm[0]).any():
        return None, 'a linha não fecha uma área na peça'
    A = np.asarray(mm[0], bool)
    Vh, Fh = _vf(hm); T = Vh[Fh]
    area = np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1) / 2
    dens = [_densa([L]) for L in loops]
    lp = np.vstack(dens); lid = np.concatenate([np.full(len(x), k) for k, x in enumerate(dens)])
    folga = float(cut.get('folga') or 0.2)
    checks = []
    dr = cut.get('direcao') or {}
    if dr.get('modo') == 'manual':
        d = vetor(dr.get('az', 0), dr.get('el', 0))
        if dr.get('quem') == 'resto':
            d = -d
        trava = analisar(T, A, d, 0.8, area)['area']
        sug = False
    else:
        d, trava, nota = escolher_direcao(T, A, area, lp, dens)
        sug = True
    At, Bt, nc, comp = dividir_por_arestas(Vh, Fh, loops, A)
    lacos = lacos_borda(At)
    if not lacos:
        return None, 'a linha não separou a pele'
    h, a = altura(T, A, d, CEL, area, lp)
    tampas, ok_l = [], []
    for laco in lacos:
        tp, err = tampa(Vh, laco, a['R'], h, a['lo'], CEL, passo=0.6)
        if tp is None:
            tp, err = tampa_parede(Vh, laco, a['R'], h, a['lo'], CEL, passo=0.6)
        if tp is None:
            return None, f'tampa: {err}'
        tampas.append(tp); ok_l.append(laco)
    lo = Vh.min(0); hi = Vh.max(0)
    allc = [np.c_[tp['inner_uv'], tp['inner_z']] @ a['R'] for tp in tampas if len(tp['inner_uv'])]
    if allc:
        cc = np.vstack(allc); lo = cc.min(0) - 3.0; hi = cc.max(0) + 3.0
    pele = _Pele(Vh, Fh, lo, hi)
    for tp, laco in zip(tampas, ok_l):
        acomodar(tp, laco, Vh, pele, a['R'], folga, a, CEL)
    pa, e1 = montar(Vh, At, tampas, ok_l, a['R'], +1, folga)
    pb, e2 = montar(Vh, Bt, tampas, ok_l, a['R'], -1, folga)
    if pa is None or pb is None:
        return None, f'a peça não fechou ({e1 or e2})'
    pk = [p for p in pa.decompose() if p.volume() > 0.5] or [pa]
    rk = [p for p in pb.decompose() if p.volume() > 0.5] or [pb]
    repl = []
    for k, m in enumerate(rk):
        Tt, col = FC._paint_from(host['T'], host['paint'], m, host['base'])
        repl.append(dict(host, mesh=m, T=Tt, paint=col, nome=host['nome'] + (f' {k + 1}' if len(rk) > 1 else ''),
                         _dirs=list(host.get('_dirs', [])) + [(-d).tolist()]))
    new = []
    for k, m in enumerate(pk):
        Tn, coln = FC._paint_from(host['T'], host['paint'], m, host['base'])
        new.append(dict(mesh=m, base=host['base'], nome=nome + (f' ({k + 1})' if len(pk) > 1 else ''), tipo='livre', rid=None,
                        axis=None, print_T=None, T=Tn, paint=coln, livre=i, _dir=d.tolist(), _dirs=[d.tolist()]))
    pieces = pieces[:hk] + repl + pieces[hk + 1:] + new
    az, el = angulos(d)
    checks.append(_chk('ok', f'Corte pela pele (1.48 beta): a pele das peças é a do modelo, dividida na linha; a face de dentro é nova.'))
    checks.append(_chk('ok', f'Direção de encaixe {"sugerida" if sug else "escolhida"}: a peça sai {_texto_dir(d)} '
                             f'(azimute {az}°, elevação {el}°). Para mudar, use "Direção de encaixe" nas opções do corte.'))
    if trava > 1.0:
        checks.append(_chk('aviso', f'Nessa direção, {trava:.1f} mm² de pele ficam presos atrás da outra peça (cabelo fundido na pele, '
                                    'por exemplo). A peça pode precisar de um empurrão ou de outra direção.'))
    if EXTRA[0] > 15.0:
        checks.append(_chk('aviso', f'A linha não fechava a área sozinha: {EXTRA[0]:.0f} mm de costura extra onde as partes estão fundidas.'))
    if len(pk) > 1:
        checks.append(_chk('aviso', f'A peça saiu em {len(pk)} partes.'))
    o2 = dict(cur); o2['pieces'] = pieces
    # pino na direção de encaixe (módulo de conectores)
    pin = {'colar': 'pino' if cut.get('soquete') else None, 'losango': 'pino', 'trava': 'pino', 'peca': 'pino', 'cavilha': 'cavilha'}.get(enc)
    depois = False
    if enc == 'colar' and cut.get('soquete') and len(pk) == 1 and len(rk) == 1 and SOQUETE_NO_FIM:
        # 1.55: "só colar" com soquete volta a ter o soquete navalha do motor anterior (a peça entra no corpo, paredes
        # retas e fundo exatos, pino padrão no fundo). Ele é feito no fim, depois de todos os cortes (freecut.
        # _soquetes_pele): um soquete feito agora poria o miolo da peça dentro da peça vizinha, e um corte desenhado
        # depois nela cortaria o miolo junto. Se não couber, fica o pino do módulo de conectores.
        depois = True
        pin = None
    if pin:
        o2, ck = _conector(o2, cut, nome, d, pin)
        checks += ck
    r = dict(i=i, nome=nome, ok=True, checks=checks, forma='pele', encaixe=enc, sem_pino=not pin and not depois,
             dir=dict(az=az, el=el, sugerida=sug), _s=round(time.time() - t0, 1))
    if depois:
        r['_soquete_depois'] = d.tolist()
        r['_soquete_regiao'] = hm                    # a peça antes do corte: a região sem a folga no meio
    return o2, r


def _pele_da_peca(S, pk):
    """Que triângulos do modelo são pele da peça pk (o lado da linha que vai com ela): os que estão na superfície
    dela. Com isso o soquete mede a parede só contra a pele do corpo; sem, um teste de lado pela linha confunde a pele
    perto de uma linha curva e o soquete chega perto demais da pele do vizinho (judô, Corte 7)."""
    ST = SPL.tri_array(S)
    c = ST.mean(1)
    b = np.array(pk.bounding_box())
    want = np.zeros(len(ST), bool)
    perto = np.where(np.all((c >= b[:3] - 0.5) & (c <= b[3:] + 0.5), axis=1))[0]
    if len(perto):
        want[perto] = SPL._on_surface(c[perto], SPL.tri_array(pk), tol=0.05) >= 0
    return want


def soquete_junta(pk, pj, regiao, cut, loops, outras, diag, centro, S, FC):
    """Soquete navalha (freecut.socket_cut) entre a peça pk (a do corte) e a peça pj (a do outro lado da linha), dentro
    da região (as duas peças juntas, com a folga entre elas: o soquete nunca entra noutra peça). Devolve
    (peça nova, pj nova, extras, checks) ou (None, motivo) se não coube ou partiria uma peça (aí fica o pino)."""
    try:
        r0 = dict(ok=True, checks=[], piece=pk, body_parts=[pj])
        r2, sc = FC.socket_cut(r0, regiao, loops, dict(cut, encaixe='colar', _outras=outras), diag, centro, 'colar', S,
                               _pele_da_peca(S, pk))
        if r2.get('piece') is pk:
            avs = [c['texto'] for c in sc if c['nivel'] != 'ok']
            return None, avs[0] if avs else 'O soquete não coube nesta junta.'
        bp = r2.get('body_parts') or []
        if (len(bp) != 1 or len(r2['piece'].decompose()) != 1 or r2['piece'].volume() < 0.5
                or len(bp[0].decompose()) != len(pj.decompose())):
            return None, 'O soquete partiria uma das peças nesta junta: ficou sem soquete.'
        if r2['piece'].genus() > pk.genus() or bp[0].genus() > pj.genus():
            # a parede do soquete furou a peça de lado a lado (um anel em volta do soquete, numa costura ondulada)
            return None, 'O soquete furaria a peça de lado a lado nesta junta: ficou sem soquete.'
        return r2['piece'], bp[0], list(r2.get('extra') or []), [c for c in sc if 'Sem pino' not in c['texto']]
    except Exception:
        traceback.print_exc()
        return None, 'O soquete falhou nesta junta: ficou sem soquete.'


def _conector(o2, cut, nome, d, tipo):
    """Pino sugerido pelo módulo de conectores, com o eixo na direção de encaixe. Se o furo partiria a outra
    peça (ou o pino ficaria sem furo), fica sem pino, com aviso."""
    try:
        import conectores as CN
        js = CN.juntas(o2, [dict(cut, manual=True, nome=nome)])
        if not js:
            return o2, [_chk('aviso', 'Sem pino: a face da junta não foi achada.')]
        for j in js:
            n0 = np.asarray(j['normal'], float)
            n = d if float(np.dot(d, n0)) >= 0 else -d
            j['normal'] = [float(x) for x in n]
            j['_R'] = CN._frame(n)
            j['sugestao'] = CN.sugerir(j, o2)
            j['sugestao']['tipo'] = tipo if j['sugestao']['tipo'] != 'nenhum' else 'nenhum'
        CN._ajustar(o2, js)
        cs = [j['sugestao'] for j in js]
        o3 = CN.aplicar(o2, js, cs)
        ck = []
        for j, c, x in zip(js, cs, o3.get('conectores', [])):
            ka, kb = j['_ka'], j['_kb']
            if c['tipo'] == 'nenhum' or x.get('luz') == 'erro':
                ck.append(_chk('aviso', 'Sem pino nesta junta: não cabe com parede de 1,2 mm.'))
                continue
            sob = (o3['pieces'][ka]['mesh'] ^ o3['pieces'][kb]['mesh']).volume()
            if sob > 0.05:
                o3 = dict(o3); o3['pieces'] = list(o3['pieces'])
                o3['pieces'][ka] = o2['pieces'][ka]; o3['pieces'][kb] = o2['pieces'][kb]
                ck.append(_chk('aviso', 'Sem pino nesta junta: o furo partiria a outra peça.'))
                continue
            ck.append(_chk('ok', f'Pino de {c["d"]} mm × {c["h"]} mm na direção de encaixe, folga {c.get("folga", 0.4)} mm.'))
        o3.pop('conectores', None)
        return o3, ck
    except Exception:
        traceback.print_exc()
        return o2, [_chk('aviso', 'Sem pino: o conector falhou neste corte.')]
