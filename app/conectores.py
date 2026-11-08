# EFC3D: conectores manuais (1.46).
#
# Módulo separado do motor de corte. Um corte com "Conector manual" passa pelo motor como uma navalha só
# (o caminho "Só colar", sem soquete), e este módulo põe os conectores nas peças prontas, onde o usuário
# escolher: pino com lado plano, pino redondo, cavilha solta ou furo para ímã, com posição, giro, diâmetro,
# profundidade e lado. Editar um conector não refaz nenhum corte: só as duas peças da junta mudam.
#
#   juntas(out, livres)        -> as faces de cada corte manual (com a sugestão de conector)
#   conferir(out, juntas, cs)  -> cada conector encostado na face e conferido (parede, folga, peça maciça)
#   aplicar(out, juntas, cs)   -> out com os pinos e furos nas peças (e as cavilhas como peças novas)
import math
import traceback

import numpy as np
import manifold3d as mf

import engine as E
import split as SPL
from split import _frame, _T, _vol, _chk, _fmt, tri_array

TIPOS = ('pino', 'redondo', 'cavilha', 'ima', 'nenhum')
PAREDE = 1.2           # parede mínima em volta do furo
FOLGA = 0.4            # folga padrão do pino no furo (raio)
FOLGA_IMA = 0.2        # o ímã é colado no furo: folga menor
_CH = 0.4              # chanfro da ponta do pino


# ------------------------------------------------------------------ cortes
def normalizar(livres):
    """Corte com conector manual: no motor ele é uma navalha (encaixe 'colar', sem soquete). Dois cortes com
    o mesmo nome (projeto antigo, um corte recriado) ganham nomes diferentes: as peças e as juntas são
    achadas pelo nome."""
    if not livres:
        return livres
    out, usados = [], set()
    for c in livres:
        nm = c.get('nome') or 'Corte'
        if nm in usados:
            k = 2
            while f'{nm} ({k})' in usados:
                k += 1
            c = dict(c, nome=f'{nm} ({k})')
        usados.add(c.get('nome') or 'Corte')
        if c.get('encaixe') == 'manual' or c.get('manual'):
            c = dict(c, encaixe='colar', soquete=False, anel_plano=False, manual=True)
        out.append(c)
    return out


def tem_manual(livres):
    return any(c.get('manual') or c.get('encaixe') == 'manual' for c in (livres or []))


# ------------------------------------------------------------------ faces das juntas
def _amostras(T, area_pt):
    """Pontos espalhados na superfície dos triângulos T (n,3,3), cerca de um a cada area_pt mm²."""
    a = np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1) / 2
    k = np.maximum(1, np.ceil(a / area_pt)).astype(np.int64)
    idx = np.repeat(np.arange(len(T)), k)
    rng = np.random.default_rng(7)
    r1, r2 = rng.random(len(idx)), rng.random(len(idx))
    s = np.sqrt(r1)
    w0, w1, w2 = 1 - s, s * (1 - r2), s * r2
    P = T[idx, 0] * w0[:, None] + T[idx, 1] * w1[:, None] + T[idx, 2] * w2[:, None]
    return P


def _crop(T, lo, hi):
    c = T.mean(1)
    m = np.all((c >= lo) & (c <= hi), axis=1)
    return T[m]


def _comps(P, r):
    from scipy.spatial import cKDTree
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    pr = cKDTree(P).query_pairs(r, output_type='ndarray')
    n = len(P)
    if not len(pr):
        return np.arange(n)
    g = coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(n, n))
    return connected_components(g, directed=False)[1]


def _face2d(P, c, R, cell=0.2):
    """A face vista de frente (no plano da junta): grade com a distância de cada célula até a borda."""
    from scipy.ndimage import binary_closing, binary_fill_holes, distance_transform_edt
    q = (P - c) @ R[:, :2]
    lo = q.min(0) - 3 * cell
    ij = np.floor((q - lo) / cell).astype(int)
    sh = ij.max(0) + 4
    g = np.zeros(sh, bool)
    g[ij[:, 0], ij[:, 1]] = True
    g = binary_fill_holes(binary_closing(g, iterations=3))
    d = distance_transform_edt(g) * cell
    return dict(lo=lo, cell=cell, d=d)


def _dist_borda(f, q):
    """Distância até a borda da face no ponto q (coordenadas no plano); 0 fora da face."""
    ij = np.floor((np.asarray(q) - f['lo']) / f['cell']).astype(int)
    if np.any(ij < 0) or ij[0] >= f['d'].shape[0] or ij[1] >= f['d'].shape[1]:
        return 0.0
    return float(f['d'][ij[0], ij[1]])


def juntas(out, livres):
    """As faces de cada corte manual: uma por vizinha (a peça do outro lado da linha). Cada uma traz o
    plano da face, o raio livre e a sugestão de conector."""
    from scipy.spatial import cKDTree
    pieces = out['pieces']
    res = []
    todas = [(c.get('nome') or f'Corte {i + 1}', [np.asarray(L, np.float64) for L in (c.get('linhas') or []) if len(L) >= 3])
             for i, c in enumerate(livres or [])]
    manuais = {c.get('nome') or f'Corte {i + 1}' for i, c in enumerate(livres or []) if c.get('manual') or c.get('encaixe') == 'manual'}
    for ci, c in enumerate(livres or []):
        if not (c.get('manual') or c.get('encaixe') == 'manual'):
            continue
        nome = c.get('nome') or f'Corte {ci + 1}'
        gap = float(c.get('folga') or 0.2)
        linhas = [np.asarray(L, np.float64) for L in (c.get('linhas') or []) if len(L) >= 3]
        mine = [k for k, p in enumerate(pieces) if p.get('nome') == nome and p.get('tipo') != 'cavilha']
        n_j = 0
        for ka in mine:
            Ta = np.asarray(pieces[ka]['T'], np.float64)
            lo, hi = Ta.reshape(-1, 3).min(0) - 1.0, Ta.reshape(-1, 3).max(0) + 1.0
            Pa = _amostras(Ta, 0.06)
            cand = []
            for kb, pb in enumerate(pieces):
                if kb == ka or pb.get('tipo') == 'cavilha':
                    continue
                Tb = _crop(np.asarray(pb['T'], np.float64), lo, hi)
                if not len(Tb):
                    continue
                Pb = _amostras(Tb, 0.03)
                d, j = cKDTree(Pb).query(Pa, distance_upper_bound=gap + 0.2)
                near = np.isfinite(d)
                if near.sum() < 30:
                    continue
                cand.append((kb, Pa[near], Pb[j[near]]))
            for kb, A, B in cand:
                lab = _comps(A, 0.7)
                for g in np.unique(lab):
                    m = lab == g
                    if m.sum() < 30:
                        continue
                    A_, B_ = A[m], B[m]
                    if linhas:
                        # a face deste corte: a borda dela corre ao longo da linha (pelo menos um quarto dela)
                        tr = cKDTree(A_)
                        share = max(float(np.mean(tr.query(L, distance_upper_bound=1.5)[0] < 1.5)) for L in linhas)
                        if share < 0.25:
                            continue
                        # dois cortes próximos (cabeça e pescoço): a face é do corte cuja linha passa mais junto
                        # da borda dela; se for de um corte automático, não é junta de conector manual
                        best, dbest = None, np.inf
                        for nm_, Ls_ in todas:
                            for L_ in Ls_:
                                dd = float(np.median(tr.query(L_)[0]))
                                if dd < dbest:
                                    best, dbest = nm_, dd
                        if best not in manuais:
                            continue
                    else:
                        best = nome
                    pa, pb = pieces[ka]['nome'], pieces[kb]['nome']
                    cc0 = A_.mean(0)
                    if any({j_['peca'], j_['vizinha']} == {pa, pb} and np.linalg.norm(j_['_c'] - cc0) < 3.0 for j_ in res):
                        continue                         # a mesma face vista do outro lado
                    cc = A_.mean(0)
                    w, V = np.linalg.eigh(np.cov((A_ - cc).T))
                    n = V[:, 0]
                    if float(np.mean((B_ - A_) @ n)) < 0:
                        n = -n
                    dd_ = pieces[ka].get('_dir')
                    if dd_ is not None:                  # corte pela pele (1.48): o pino entra na direção de encaixe
                        dd_ = np.asarray(dd_, np.float64)
                        n = dd_ if float(dd_ @ n) >= 0 else -dd_
                        curva = True
                    else:
                        curva = False
                    R = _frame(n)
                    f = _face2d(A_, cc, R)
                    k = np.unravel_index(np.argmax(f['d']), f['d'].shape)
                    q = f['lo'] + (np.array(k) + 0.5) * f['cell']
                    p0 = cc + R[:, :2] @ q
                    p0 = A_[cKDTree(A_).query(p0)[1]]
                    rin = float(f['d'].max())
                    n_j += 1
                    jid = f'{best}|{pieces[ka]["nome"]}|{pieces[kb]["nome"]}|{n_j}'
                    res.append(dict(id=jid, corte=best, peca=pieces[ka]['nome'], vizinha=pieces[kb]['nome'],
                                    centro=[round(float(x), 3) for x in p0], normal=[round(float(x), 5) for x in n],
                                    raio_livre=round(rin, 2), area=round(float(m.sum()) * 0.06, 1),
                                    folga_faces=gap, desvio=round(float(np.sqrt(max(w[0], 0.0))), 3),
                                    _A=A_, _B=B_, _f=f, _c=cc, _R=R, _ka=ka, _kb=kb, curva=curva))
    for j in res:
        j['sugestao'] = sugerir(j, out)
    _ajustar(out, res)
    return res


def _ajustar(out, js):
    """A sugestão já sai conferida: diminui profundidade e diâmetro até não ter erro nem aviso (ou chegar
    ao mínimo, e então fica sem conector)."""
    for _ in range(14):
        cs = [j['sugestao'] for j in js]
        res, _g = conferir(out, js, cs)
        ruins = [i for i, r in enumerate(res) if r['luz'] != 'ok' and cs[i]['tipo'] != 'nenhum']
        if not ruins:
            return
        for i in ruins:
            c = cs[i]
            if res[i].get('_borda'):
                c['d'] = round(c['d'] - 0.5, 1)
            elif c['h'] > 2.0:
                c['h'] = round(max(2.0, c['h'] - 1.0), 1)
            else:
                c['d'] = round(c['d'] - 0.5, 1)
            if c['d'] < 2.0:
                c['tipo'], c['d'] = 'nenhum', 2.0


def publico(js):
    return [{k: v for k, v in j.items() if not k.startswith('_')} for j in js]


def _profundo(M, O, D, rmax=40.0):
    """Quanto cabe de material de M a partir de O, no sentido D (o primeiro ponto onde o raio sai)."""
    from freecut import _ray_hits
    T = tri_array(M)
    lo, hi = O - rmax, O + rmax
    T = _crop(T, lo, hi)
    if not len(T):
        return 0.0
    t = _ray_hits(np.asarray([O], np.float64), np.asarray([D], np.float64), T)[0]
    return float(min(t, rmax))


def sugerir(j, out):
    """Conector sugerido: pino com lado plano no ponto mais longe da borda da face, o maior diâmetro que
    deixa 1,2 mm de parede, na peça do corte; o furo na vizinha."""
    rin = j['raio_livre']
    d = float(np.clip(math.floor(2 * (rin - FOLGA - PAREDE - 0.3) * 2) / 2, 0.0, 10.0))   # passos de 0,5 mm
    pieces = out['pieces']
    p0, n = np.asarray(j['centro']), np.asarray(j['normal'])
    # o pino fica na peça menor e o furo na maior (mais material em volta do furo)
    lado = 'peca' if _vol(pieces[j['_ka']]['mesh']) <= _vol(pieces[j['_kb']]['mesh']) else 'vizinha'
    try:
        dB = _profundo(pieces[j['_kb']]['mesh'], p0 + n * (j['folga_faces'] + 0.05), n)
        dA = _profundo(pieces[j['_ka']]['mesh'], p0 - n * 0.05, -n)
    except Exception:
        traceback.print_exc()
        dB = dA = 6.0
    d_outro, d_dono = (dB, dA) if lado == 'peca' else (dA, dB)
    h = float(np.clip(min(1.5 * max(d, 2.0), d_outro - FOLGA - PAREDE), 0.0, 12.0))
    h2 = float(np.clip(min(h, d_dono - PAREDE), 0.0, 12.0))
    tipo = 'pino' if d >= 2.0 and h >= 2.0 else 'nenhum'
    return dict(junta=j['id'], tipo=tipo, d=round(max(d, 2.0), 1), h=round(max(h, 2.0), 1), h2=round(max(h2, 2.0), 1),
                giro=0.0, lado=lado, ponto=list(j['centro']), folga=FOLGA, eixo='face')


# ------------------------------------------------------------------ geometria de um conector
def _perfil(tipo, r, n=48):
    c = mf.CrossSection.circle(r, n)
    if tipo == 'pino':                                  # lado plano a 0,6 r do centro: trava o giro
        c = c ^ mf.CrossSection.square([4 * r, 4 * r], True).translate([-2 * r + 0.6 * r, 0.0])
    return c


def _barra(prof, z0, z1, ch0=0.0, ch1=0.0, r=1.0):
    """Extrusão do perfil de z0 a z1, com chanfro opcional nas pontas."""
    parts = []
    a, b = z0 + ch0, z1 - ch1
    e0, e1 = (0.02 if ch0 > 0 else 0.0), (0.02 if ch1 > 0 else 0.0)     # sobreposição: as partes se fundem
    parts.append(mf.Manifold.extrude(prof, (b + e1) - (a - e0)).translate([0, 0, a - e0]))
    if ch1 > 0:
        s = (r - ch1) / r
        parts.append(mf.Manifold.extrude(prof, ch1, 0, 0.0, [s, s]).translate([0, 0, b]))
    if ch0 > 0:
        s = (r - ch0) / r
        parts.append(mf.Manifold.extrude(prof.scale([s, s]), ch0, 0, 0.0, [1 / s, 1 / s]).translate([0, 0, z0]))
    return E.union(parts)


def _geo(j, cn):
    """Sólidos do conector no espaço do modelo: dict(dono, outro, pino, furo_outro, furo_dono, cavilha,
    parede_outro, parede_dono, Tw). O eixo aponta do dono para o outro lado."""
    tipo = cn.get('tipo', 'pino')
    d = float(np.clip(float(cn.get('d') or 3.0), 1.0, 30.0))
    h = float(np.clip(float(cn.get('h') or 4.0), 0.5, 40.0))
    h2 = float(np.clip(float(cn.get('h2') or h), 0.5, 40.0))
    clr = float(np.clip(float(cn.get('folga') if cn.get('folga') is not None else (FOLGA_IMA if tipo == 'ima' else FOLGA)), 0.0, 1.5))
    gap = float(j['folga_faces'])
    n = np.asarray(j['normal'], np.float64)
    p = np.asarray(cn.get('ponto') or j['centro'], np.float64)
    pino_na_peca = cn.get('lado', 'peca') != 'vizinha'
    a = n if pino_na_peca else -n
    zO = 0.0 if pino_na_peca else -gap                  # face do dono e face do outro no eixo a
    zQ = zO + gap
    if cn.get('eixo') == 'vertical' and abs(a[2]) > 0.2:
        # eixo na vertical da mesa (a peça imprime de pé, sem pino deitado): a distância entre as faces
        # cresce com a inclinação da face
        a2 = np.array([0.0, 0.0, 1.0 if a[2] > 0 else -1.0])
        k = 1.0 / abs(float(a @ a2))
        zO, zQ, a = zO * k, zQ * k, a2
    R = _frame(a)
    g = math.radians(float(cn.get('giro') or 0.0))
    Rz = np.array([[math.cos(g), -math.sin(g), 0], [math.sin(g), math.cos(g), 0], [0, 0, 1.0]])
    Tw = _T(R @ Rz, p)
    r = d / 2
    out = dict(dono=j['_ka'] if pino_na_peca else j['_kb'], outro=j['_kb'] if pino_na_peca else j['_ka'],
               Tw=Tw, d=d, h=h, h2=h2, clr=clr, tipo=tipo)
    rw = r + clr + PAREDE
    ch = min(_CH, 0.3 * r)
    if tipo in ('pino', 'redondo'):
        prof = _perfil(tipo, r)
        # o pino nasce 1 mm dentro do dono (a peça é maciça ali: basta para fundir) e entra h no outro
        # face curva (corte pela pele, 1.48): o pino nasce mais fundo no dono e o furo começa antes da face,
        # para o pino nunca ficar entre as faces fora do furo
        dz = (1.5 if j.get('curva') else 0.0) if cn.get('_dz') is None else float(cn['_dz'])
        out['pino'] = E.X(_barra(prof, zO - 1.0 - dz, zQ + h, 0.0, ch, r), Tw)
        # a raiz do pino, do lado do dono: precisa ficar dentro dele (peça fina na junta: a raiz sairia do
        # outro lado da peça, para dentro da vizinha)
        out['raiz'] = E.X(_barra(mf.CrossSection.circle(r, 48), zO - 1.0 - dz, zO - 0.3), Tw)
        out['dz'] = dz
        out['furo_outro'] = E.X(_barra(prof.offset(clr, mf.JoinType.Round, 2.0, 32), zQ - 0.3 - dz, zQ + h + clr), Tw)
        out['base_dono'] = E.X(_barra(mf.CrossSection.circle(r, 48), zO - 1.0, zO - 0.3), Tw)
        out['parede_outro'] = E.X(_barra(mf.CrossSection.circle(rw, 48), zQ + 0.6, zQ + h + clr + PAREDE), Tw)
        out['nucleo_outro'] = E.X(_barra(mf.CrossSection.circle(r + clr, 48), zQ + 0.6, zQ + h + clr), Tw)
    elif tipo in ('cavilha', 'ima'):
        prof = mf.CrossSection.circle(r + clr, 48)
        fo = h + (clr if tipo == 'cavilha' else 0.2)
        fd = h2 + (clr if tipo == 'cavilha' else 0.2)
        out['furo_outro'] = E.X(_barra(prof, zQ - 0.3, zQ + fo), Tw)
        out['furo_dono'] = E.X(_barra(prof, zO - fd, zO + 0.3), Tw)
        out['parede_outro'] = E.X(_barra(mf.CrossSection.circle(rw, 48), zQ + 0.6, zQ + fo + PAREDE), Tw)
        out['parede_dono'] = E.X(_barra(mf.CrossSection.circle(rw, 48), zO - fd - PAREDE, zO - 0.6), Tw)
        out['nucleo_outro'] = E.X(_barra(prof, zQ + 0.6, zQ + fo), Tw)
        out['nucleo_dono'] = E.X(_barra(prof, zO - fd, zO - 0.6), Tw)
        if tipo == 'cavilha':
            out['cavilha'] = E.X(_barra(mf.CrossSection.circle(r, 48), zO - h2, zQ + h, ch, ch, r), Tw)
    out['eixo'] = a
    return out


def _fora(M, S):
    """Volume de S fora de M (mm³)."""
    if S is None or S.is_empty():
        return 0.0
    return max(0.0, _vol(S) - _vol(M ^ S))


# ------------------------------------------------------------------ conferência
def _snap(j, cn):
    """O ponto vai para a face da junta (o ponto da face mais perto do clique)."""
    from scipy.spatial import cKDTree
    p = np.asarray(cn.get('ponto') or j['centro'], np.float64)
    k = cKDTree(j['_A']).query(p)[1]
    return [round(float(x), 3) for x in j['_A'][k]]


def conferir(out, js, conectores):
    """Cada conector: o ponto encostado na face, e a conferência (texto e nível)."""
    por_id = {j['id']: j for j in js}
    pieces = out['pieces']
    res, gs = [], []
    for cn in conectores or []:
        j = por_id.get(cn.get('junta'))
        if j is None:
            res.append(dict(cn, luz='erro', checks=[_chk('erro', 'A junta deste conector não existe mais (o corte mudou). Remova o conector.')]))
            gs.append(None)
            continue
        cn = dict(cn, ponto=_snap(j, cn))
        checks = []
        if cn.get('tipo') not in TIPOS:
            cn['tipo'] = 'pino'
        if cn['tipo'] == 'nenhum':
            checks.append(_chk('ok', 'Sem conector: as faces encostam e é só colar (CA ou epóxi).'))
            res.append(dict(cn, luz='ok', checks=checks))
            gs.append(None)
            continue
        try:
            g = _geo(j, cn)
        except Exception as ex:
            traceback.print_exc()
            res.append(dict(cn, luz='erro', checks=[_chk('erro', f'Não consegui montar o conector: {ex}')]))
            gs.append(None)
            continue
        Mo, Md = pieces[g['outro']]['mesh'], pieces[g['dono']]['mesh']
        no, nd = pieces[g['outro']]['nome'], pieces[g['dono']]['nome']
        if 'raiz' in g and _fora(Md, g['raiz']) > 0.02 * max(_vol(g['raiz']), 1e-9) and g['dz'] > 0:
            # raiz mais rasa (1 mm, como na face plana) antes de desistir do pino
            cn = dict(cn, _dz=0.0)
            g = _geo(j, cn)
        gs.append(g)
        r = g['d'] / 2
        if 'raiz' in g:
            fr = _fora(Md, g['raiz'])
            if fr > 0.02 * max(_vol(g['raiz']), 1e-9):
                checks.append(_chk('erro', f'O pino sai de "{nd}" pelo outro lado ({_fmt(fr, 1)} mm³ para fora da pele): '
                                           'a peça é fina demais na junta. Mova o conector ou use outro tipo.'))
        # borda da face: a boca do furo precisa de parede até a pele
        q = (np.asarray(cn['ponto']) - j['_c']) @ j['_R'][:, :2]
        db = _dist_borda(j['_f'], q)
        borda = False
        livre = db - r - g['clr']
        if livre < PAREDE:
            borda = True
        if livre < 0.2:
            checks.append(_chk('erro', f'O conector passa da borda da face (sobra {_fmt(max(livre, 0), 1)} mm até a pele). '
                                        'Mova para o meio da face ou diminua o diâmetro.'))
        elif livre < PAREDE:
            checks.append(_chk('aviso', f'Parede de {_fmt(livre, 1)} mm entre o furo e a pele, na face (mínimo {_fmt(PAREDE, 1)} mm). '
                                         'Mova para o meio da face ou diminua o diâmetro.'))
        # o furo do outro lado: dentro da peça, com parede em volta e no fundo
        for lado, M, nm, nuc, par in (('outro', Mo, no, 'nucleo_outro', 'parede_outro'), ('dono', Md, nd, 'nucleo_dono', 'parede_dono')):
            if nuc not in g:
                continue
            fo = _fora(M, g[nuc])
            fp = _fora(M, g[par]) if par in g else 0.0
            vn = max(_vol(g[nuc]), 1e-9)
            if fo > 0.02 * vn:
                if lado == 'dono' and g['tipo'] in ('pino', 'redondo'):
                    checks.append(_chk('erro', f'O pino sai de "{nm}" ({_fmt(fo, 1)} mm³ para fora da pele). '
                                               'Diminua a profundidade ou mova o conector.'))
                else:
                    checks.append(_chk('erro', f'O furo sai de "{nm}" ({_fmt(fo, 1)} mm³ para fora da pele). '
                                               'Diminua a profundidade ou mova o conector.'))
            elif par in g and fp > 0.03 * _vol(g[par]):
                checks.append(_chk('aviso', f'Parede fina em volta do furo em "{nm}" (menos de {_fmt(PAREDE, 1)} mm em algum ponto). '
                                            'Diminua a profundidade ou o diâmetro.'))
        if g['d'] < 2.0 and g['tipo'] in ('pino', 'redondo', 'cavilha'):
            checks.append(_chk('aviso', f'Pino de {_fmt(g["d"], 1)} mm é fino e quebra fácil: use 2 mm ou mais.'))
        if not any(x['nivel'] != 'ok' for x in checks):
            txt = {'pino': f'Pino de {_fmt(g["d"], 1)} mm com lado plano (não gira), {_fmt(g["h"], 1)} mm para dentro de "{no}", '
                           f'folga {_fmt(g["clr"], 2)} mm. Cole ou deixe encaixado.',
                   'redondo': f'Pino redondo de {_fmt(g["d"], 1)} mm (a peça gira), {_fmt(g["h"], 1)} mm para dentro de "{no}", '
                              f'folga {_fmt(g["clr"], 2)} mm.',
                   'cavilha': f'Cavilha solta de {_fmt(g["d"], 1)} mm: furo de {_fmt(g["h2"], 1)} mm em "{nd}" e de {_fmt(g["h"], 1)} mm '
                              f'em "{no}", folga {_fmt(g["clr"], 2)} mm. A cavilha sai como peça.',
                   'ima': f'Furo para ímã de {_fmt(g["d"], 1)} × {_fmt(g["h"], 1)} mm em "{no}" e de {_fmt(g["d"], 1)} × {_fmt(g["h2"], 1)} mm '
                          f'em "{nd}", folga {_fmt(g["clr"], 2)} mm. Cole os ímãs com a polaridade certa.'}[g['tipo']]
            checks.append(_chk('ok', txt))
        res.append(dict(cn, checks=checks, _borda=borda))
    # dois conectores na mesma peça: os furos não podem se encontrar (a peça do meio fica maciça)
    vol_ = {}
    for i, g in enumerate(gs):
        if g is None:
            continue
        for lado in ('outro', 'dono'):
            key = 'parede_' + lado
            if key in g:
                vol_.setdefault(g[lado], []).append((i, g[key], True))
            elif lado == 'dono' and 'base_dono' in g:
                vol_.setdefault(g[lado], []).append((i, g['base_dono'], False))
    for k, lst in vol_.items():
        for a in range(len(lst)):
            for b in range(a + 1, len(lst)):
                ia, Ma, fa = lst[a]
                ib, Mb, fb = lst[b]
                if (fa or fb) and _vol(Ma ^ Mb) > 0.05:      # dois pinos que se tocam: material maciço, tudo bem
                    t = _chk('aviso', f'Dois conectores se encontram dentro de "{pieces[k]["nome"]}": a peça fica com parede fina '
                                      'entre eles. Afaste um deles ou diminua a profundidade.')
                    for i in (ia, ib):
                        res[i]['checks'] = [x for x in res[i]['checks'] if x['nivel'] != 'ok'] + [t]
    for x in res:
        x['luz'] = 'erro' if any(c['nivel'] == 'erro' for c in x['checks']) else \
            'aviso' if any(c['nivel'] == 'aviso' for c in x['checks']) else 'ok'
    return res, gs


# ------------------------------------------------------------------ aplicar nas peças
def aplicar(out, js, conectores):
    """out com os conectores nas peças. Um conector com erro não entra (a peça fica como estava)."""
    from freecut import _paint_from
    res, gs = conferir(out, js, conectores)
    pieces = list(out['pieces'])
    add, sub, extra = {}, {}, []
    for cn, g in zip(res, gs):
        if g is None or cn['luz'] == 'erro':
            continue
        if 'pino' in g:
            add.setdefault(g['dono'], []).append(g['pino'])
        if 'furo_outro' in g:
            sub.setdefault(g['outro'], []).append(g['furo_outro'])
        if 'furo_dono' in g:
            sub.setdefault(g['dono'], []).append(g['furo_dono'])
        if 'cavilha' in g:
            dono = pieces[g['dono']]
            T = tri_array(g['cavilha'])
            extra.append(dict(mesh=g['cavilha'], base=dono['base'], nome=f'Cavilha · {dono["nome"]}', tipo='cavilha', rid=None,
                              axis=[float(x) for x in g['eixo']], print_T=None, T=T, paint=np.full(len(T), dono['base'], np.uint8),
                              livre=dono.get('livre')))
    for k in sorted(set(add) | set(sub)):
        p = pieces[k]
        M = p['mesh']
        if k in add:
            M = E.flat(M + E.union(add[k]))
        if k in sub:
            M = E.flat(M - E.union(sub[k]))
        n0 = len(E.parts(p['mesh'], 0.3))
        if len(E.parts(M, 0.3)) > n0:
            # o conector partiu a peça: ela fica sem os conectores
            for x, g in zip(res, gs):
                if g is not None and k in (g['dono'], g['outro']) and x['luz'] != 'erro':
                    x['checks'] = [_chk('erro', f'O conector partiria "{p["nome"]}" em duas: ele não foi aplicado. '
                                                'Diminua a profundidade ou mova o conector.')]
                    x['luz'] = 'erro'
            continue
        T, col = _paint_from(np.asarray(p['T']), np.asarray(p['paint']), M, p['base'])
        pieces[k] = dict(p, mesh=M, T=T, paint=col)
    o2 = dict(out)
    o2['pieces'] = pieces + extra
    o2['conectores'] = [{k_: v for k_, v in x.items()} for x in res]
    return o2
