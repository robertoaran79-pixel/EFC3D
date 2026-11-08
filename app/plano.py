"""EFC3D: corte plano, como o do OrcaSlicer e do Bambu Studio.

Um plano (posição e inclinação em qualquer direção) atravessa as peças que cruza e divide cada
uma em duas: a parte de cima (do lado da normal) e a de baixo. As faces do corte são planas e
encostam uma na outra (sem folga), prontas para apoiar na mesa. Conectores opcionais em cada parte
cortada: pino fixo (losango), trava de pressão, pino na peça de cima ou cavilha solta.

Fica separado do Corte livre: o corte livre só pega a parte indicada; o plano corta tudo que cruza.
"""
import numpy as np

import engine as E
import split as SPL
from split import _frame, _T, _inv, _vol, _chk, _fmt, _limb_pin, tri_array

CONECTORES = {'nenhum': None, 'losango': 'corpo', 'trava': 'trava', 'peca': 'peca', 'cavilha': 'cavilha'}


def normal_of(cut):
    pl = cut.get('plano') or {}
    n = np.asarray(pl.get('n') or [0, 0, 1], np.float64)
    if np.linalg.norm(n) < 1e-9:
        n = np.array([0.0, 0.0, 1.0])
    return n / np.linalg.norm(n), np.asarray(pl.get('p') or [0, 0, 0], np.float64)


def _crosses(m, n, p):
    b = np.array(m.bounding_box())
    cs = np.array([[x, y, z] for x in (b[0], b[3]) for y in (b[1], b[4]) for z in (b[2], b[5])])
    d = (cs - p) @ n
    return d.min() < -1e-6 and d.max() > 1e-6


def apply_plane(i, cut, pieces, diag, paint_from):
    """Corta as peças com o plano. Devolve (resultado, peças novas)."""
    nome = cut.get('nome') or f'Plano {i + 1}'
    n, p = normal_of(cut)
    alvo = cut.get('alvo') or 'tudo'
    con = cut.get('conector') if cut.get('conector') in CONECTORES else 'nenhum'
    clr = float(np.clip(float(cut.get('folga_pino') or 0.4), 0.05, 1.0))
    pino_mm = float(cut.get('pino_mm') or 0)
    wall = 1.2
    Tw = _T(_frame(n), p)
    checks = []
    out, n_cut, n_pin, n_sem = [], 0, 0, 0
    n_lasca, v_lasca = 0, 0.0
    n_lam, v_lam = 0, 0.0
    try:
        import freecut as _FC
        k3 = _FC._CUR_K[0] ** 3
    except Exception:
        k3 = 1.0
    alvo_k = None
    if alvo == 'peca':
        # só a peça onde está o centro do plano (o pescoço depois do cabelo): as outras ficam inteiras
        for k_, h_ in enumerate(pieces):
            if h_.get('tipo') != 'cavilha' and _crosses(h_['mesh'], n, p) and E.contains_point(h_['mesh'], p, 0.15):
                alvo_k = k_
                break
        if alvo_k is None:
            return dict(i=i, nome=nome, ok=False, plano=True, checks=[_chk('erro', 'O centro do plano não está dentro de nenhuma peça: '
                                                                               'arraste o plano até a parte que quer cortar.')]), pieces
    for k_, host in enumerate(pieces):
        m = host['mesh']
        if host.get('tipo') == 'cavilha' or (alvo == 'corpo' and host.get('tipo') != 'corpo') or \
                (alvo_k is not None and k_ != alvo_k) or not _crosses(m, n, p):
            out.append(host)
            continue
        loc = E.X(m, _inv(Tw))
        up_l, dn_l = loc.split_by_plane([0.0, 0.0, 1.0], 0.0)
        vu_, vd_ = _vol(up_l), _vol(dn_l)
        if vu_ < 0.5 or vd_ < 0.5:
            out.append(host)
            continue
        if min(vu_, vd_) <= 2.0 * k3 and min(vu_, vd_) < 0.02 * max(vu_, vd_):
            # o plano só raspa a ponta da peça: a lasca solta não imprime; a peça fica inteira do lado maior
            big_l = up_l if vu_ > vd_ else dn_l
            bm = E.flat(E.X(big_l, Tw))
            T_, col_ = paint_from(host['T'], host['paint'], bm, host['base'])
            out.append(dict(host, mesh=bm, T=T_, paint=col_))
            n_lasca += 1
            v_lasca += min(vu_, vd_)
            continue
        up, dn = E.flat(E.X(up_l, Tw)), E.flat(E.X(dn_l, Tw))
        n_cut += 1
        extra = []
        if CONECTORES[con]:
            sec = loc.slice(0.0)
            comps = sorted(sec.decompose() if not sec.is_empty() else [], key=lambda q: -q.area())
            for cs in comps:
                if cs.area() < 3.0:
                    continue
                inr, pole = SPL._inradius(cs)
                c = p + _frame(n) @ np.array([pole[0], pole[1], 0.0])
                ups = E.parts(up, 0.5) or [up]
                dns = E.parts(dn, 0.5) or [dn]
                # a parte de cima e a de baixo que tocam esta seção
                ku = min(range(len(ups)), key=lambda k: abs(float(np.dot(np.asarray(E.centroid(ups[k])) - c, n))) +
                         float(np.linalg.norm(np.asarray(E.centroid(ups[k])) - c)))
                rest_up = [u for k, u in enumerate(ups) if k != ku]
                try:
                    rp = _limb_pin(ups[ku], dns, CONECTORES[con], dict(pino_mm=pino_mm), clr, wall, c, n, diag, hf=None, zsec=0.05)
                except Exception as ex:
                    rp = dict(checks=[_chk('aviso', f'O conector falhou ({ex}).')], piece=ups[ku], body_parts=dns, extra=[])
                if any(x['nivel'] == 'ok' for x in rp['checks']):
                    n_pin += 1
                    up = E.flat(E.union([rp['piece']] + rest_up)) if rest_up else rp['piece']
                    bp = [b for b in rp['body_parts'] if _vol(b) >= 0.5]
                    dn = E.flat(E.union(bp)) if len(bp) > 1 else (bp[0] if bp else dn)
                    extra += rp.get('extra', [])
                else:
                    n_sem += 1
        # cada lado pode ter várias partes (o plano corta as duas pernas)
        baixo = sorted(E.parts(dn, 0.5) or [dn], key=lambda q: -_vol(q))
        cima = sorted(E.parts(up, 0.5) or [up], key=lambda q: -_vol(q))
        # lascas de 2 mm³ ou menos (a ponta de um dente que o plano raspou): não imprimem soltas
        big = max([_vol(q) for q in baixo + cima] or [0.0])
        tiny = [q for q in baixo[1:] + cima[1:] if _vol(q) <= 2.0 * k3 and _vol(q) < 0.001 * big]
        if tiny:
            baixo = [q for q in baixo if not any(q is t for t in tiny)]
            cima = [q for q in cima if not any(q is t for t in tiny)]
            n_lasca += len(tiny)
            v_lasca += sum(_vol(t) for t in tiny)
        # lâminas finas (menos de 0,6 mm: o plano raspou o queixo) não imprimem soltas: vão para a peça do
        # outro lado em que encostam (o queixo fica com a cabeça)
        def fina(q):
            b_ = np.array(q.bounding_box())
            return float(np.min(b_[3:] - b_[:3])) < 0.6 * (k3 ** (1 / 3))
        for lado, outro in ((baixo, cima), (cima, baixo)):
            for q in [q for q in lado[1:] if fina(q) and _vol(q) < 0.02 * big]:
                for j_, o_ in enumerate(outro):
                    u_ = E.flat(E.union([o_, q]))
                    if len(E.parts(u_, 0.5) or [u_]) == 1:
                        outro[j_] = u_
                        lado.remove(q)
                        n_lam += 1
                        v_lam += _vol(q)
                        break
        base_nome = host['nome']
        for side, parts, nn in (('baixo', baixo, -n), ('cima', cima, n)):
            for k, pm in enumerate(parts):
                T, col = paint_from(host['T'], host['paint'], pm, host['base'])
                pT = _inv(_T(_frame(nn), p))           # a face do corte vai para a mesa
                nm = f'{base_nome} ({side}' + (f' {k + 1}' if len(parts) > 1 else '') + ')'
                keep = side == 'baixo' and k == 0         # a parte de baixo maior continua sendo a peça original
                d = dict(host, mesh=pm, T=T, paint=col, nome=nm, tipo=host['tipo'] if keep else 'livre',
                         axis=None if keep else nn.copy(),
                         print_T=(host.get('print_T') if host['tipo'] == 'corpo' else pT) if keep else pT, livre=i)
                out.append(d)
        for e in extra:
            T = tri_array(e['mesh'])
            out.append(dict(mesh=e['mesh'], base=host['base'], nome=f'Cavilha · {nome}', tipo='cavilha', rid=None,
                            axis=e['axis'], print_T=None, T=T, paint=np.full(len(T), host['base'], np.uint8), livre=i))
    if not n_cut:
        return dict(i=i, nome=nome, ok=False, plano=True, checks=[_chk('erro', 'O plano não atravessa nenhuma peça: mude a altura ou o ângulo.')]), pieces
    ang = float(np.degrees(np.arccos(np.clip(abs(n[2]), 0, 1))))
    checks.append(_chk('ok', f'O plano cortou {n_cut} peça(s) em duas, com faces planas (inclinação {_fmt(ang, 0)}° da mesa). '
                             'Cada face do corte vai para a mesa na impressão.'))
    if n_lasca:
        checks.append(_chk('ok', f'{n_lasca} lasca(s) de até 2 mm³ que o plano soltou (pontas raspadas) foram descartadas '
                                 f'({_fmt(v_lasca, 1)} mm³ no total): soltas, não imprimem.'))
    if n_lam:
        checks.append(_chk('ok', f'{n_lam} lâmina(s) fina(s) que o plano raspou (menos de 0,6 mm, não imprimem) foram para a peça '
                                 f'vizinha em que encostam ({_fmt(v_lam, 1)} mm³).'))
    if CONECTORES[con]:
        if n_pin:
            checks.append(_chk('ok', f'{n_pin} conector(es) no meio das partes cortadas, folga de {_fmt(clr, 2)} mm.'))
        if n_sem:
            checks.append(_chk('aviso', f'{n_sem} parte(s) cortada(s) sem conector: a seção é pequena demais. Cole as faces '
                                        'ou use um conector menor (pino em mm).'))
    else:
        checks.append(_chk('ok', 'Sem conector: as faces encostam planas, é só colar.'))
    return dict(i=i, nome=nome, ok=True, plano=True, checks=checks, encaixe=con), out
