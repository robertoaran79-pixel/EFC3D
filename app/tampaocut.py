# EFC3D 1.53 beta: corte livre com tampão (paredes retas).
#
# O corte livre ganha a forma "Tampão": a área dentro da linha (ou marcada com pincel ou balde) sai como o tampão do
# corte por cor, um prisma reto na direção de encaixe, do topo da área até 2 mm abaixo do ponto mais baixo dela. A
# peça fica com a pele original por fora, paredes retas e fundo plano; o corpo fica com o bolso, com a folga constante
# entre os dois (0,3 mm por padrão). Com linha, a costura cai exatamente na linha desenhada; com área marcada, a borda
# é suavizada como no corte por cor.
#
# O motor é o mesmo do corte por cor (split.cut_plug_auto); nada dos outros caminhos do corte livre muda. Um corte que
# não cabe num tampão (nenhuma direção enxerga a área inteira, como num braço) dá erro com o motivo e não é feito por
# outro motor: o usuário escolhe outra forma.
import base64
import time
import traceback

import numpy as np
from scipy.spatial import cKDTree

import engine as E
import split as SPL

PROFUNDIDADE = 2.0
FOLGA = 0.3
# encaixe do corte livre -> pino do tampão
PINO = {'colar': 'nenhum', 'losango': 'corpo', 'trava': 'trava', 'peca': 'peca', 'cavilha': 'cavilha'}


def _chk(nivel, texto):
    return dict(nivel=nivel, texto=texto)


# os avisos do tampão falam da pintura e de controles do corte por cor (profundidade, inclinação, "membro"); no corte
# livre a área é a da linha e a profundidade é fixa. Cada aviso é refeito inteiro (as traduções são por frase).
def _texto_livre(t):
    import re
    m = re.match(r'(\d+)% da área fica de costas para a direção de encaixe e o tampão levaria pele', t)
    if m:
        return (f'{m.group(1)}% da área fica de costas para a direção de encaixe e o tampão levaria pele de fora da linha: '
                'um tampão não sai aqui. Use outra forma de corte.')
    m = re.match(r'Borda lisa: a pintura foi suavizada em (.+) mm ao longo da borda', t)
    if m:
        return f'Borda lisa: a área marcada foi suavizada em {m.group(1)} mm ao longo da borda.'
    m = re.match(r'Parede atrás do encaixe com menos de (.+) mm em (\d+)% da área', t)
    if m:
        return f'Parede atrás do encaixe com menos de {m.group(1)} mm em {m.group(2)}% da área.'
    fixos = {
        'Relevo: as paredes laterais da área saem inteiras com a peça (nenhuma pele sem pintura vai junto).':
            'Relevo: as paredes laterais da área saem inteiras com a peça (nenhuma pele de fora da linha vai junto).',
        'A direção de encaixe atravessa outra parte do modelo: incline a direção ou reduza a profundidade.':
            'A direção de encaixe atravessa outra parte do modelo.',
        'Há parte do modelo na frente da área, na direção de encaixe: a peça não sai reto. Incline a direção.':
            'Há parte do modelo na frente da área, na direção de encaixe: a peça não sai reto.',
        'O encaixe atravessa o modelo e divide o corpo: reduza a profundidade.':
            'O bolso do tampão atravessa o modelo e divide o corpo.',
        'A borda suavizada ficou pequena demais: diminua "Suavizar borda".': 'A área é pequena demais para um tampão.',
        'O corte não gerou peça: confira a profundidade.': 'O tampão não gerou peça.',
    }
    return fixos.get(t, t)


def _falha(i, nome, checks):
    return dict(i=i, nome=nome, ok=False, checks=checks, forma='tampao')


def cortar(cur, cut, i, S, diag, FC):
    """Um corte livre com tampão. Devolve (out novo, resultado). Se não der, devolve o out de entrada e o resultado
    com o erro (o corte não sai; o usuário escolhe outra forma)."""
    t0 = time.time()
    nome = cut.get('nome') or f'Corte {i + 1}'
    enc = cut.get('encaixe') or 'colar'
    if enc not in PINO:
        return cur, _falha(i, nome, [_chk('erro', 'O tampão encaixa reto e não gira: escolha o encaixe "só colar", pino fixo, trava, '
                                                  'pino na peça ou cavilha, ou outra forma de corte.')])
    loops = [L for L in (FC._clean_loop(x) for x in (cut.get('linhas') or [])) if L is not None]
    pieces = list(cur['pieces'])
    cand = [k for k, p in enumerate(pieces) if p.get('tipo') != 'cavilha']
    mk = None
    if cut.get('mascara'):
        n_ = int(cut.get('n') or 0)
        mk = FC.decode_mask(cut['mascara'], n_ or S.num_tri())
    # peça onde o corte foi desenhado
    if cut.get('peca') and cut['peca'].get('ponto') is not None:
        hk = FC._piece_at(pieces, cut['peca']['ponto'], loops)
        if hk < 0:
            return cur, _falha(i, nome, [_chk('erro', 'A peça deste corte não existe mais (um corte anterior mudou?). Escolha a peça de novo.')])
    elif loops:
        k_, _ = FC._host_by_lines([pieces[k] for k in cand], loops)
        hk = cand[k_]
    elif mk is not None and mk.any():
        T0 = SPL.tri_array(S)
        hk, sc = SPL._host_of([pieces[k] for k in cand], T0[mk].mean(1))
        hk = cand[hk] if hk >= 0 else -1
        if hk < 0:
            return cur, _falha(i, nome, [_chk('erro', 'A área marcada foi tomada por outro corte.')])
    else:
        return cur, _falha(i, nome, [_chk('erro', 'Sem linha e sem área marcada: desenhe a linha em volta da parte.')])
    host = pieces[hk]
    hm = host['mesh']
    Vh, Fh = E.mesh_arrays(hm)[:2]
    Th = Vh[Fh]
    nt = len(Fh)
    # área dentro da linha (na malha da peça) e a marcada com pincel ou balde
    A = np.zeros(nt, bool)
    topo = None
    if loops:
        topo = SPL._topology(hm)
        mm = FC.mask_from_lines(hm, loops, topo, diag, np.asarray(E.centroid(S), np.float64), bool(cut.get('inverter')))
        if mm is None or not np.asarray(mm[0]).any():
            return cur, _falha(i, nome, [_chk('erro', 'A linha não fecha uma área nesta peça.')])
        A |= np.asarray(mm[0], bool)
    if mk is not None and mk.any():
        if cut.get('peca'):
            if len(mk) != nt:
                return cur, _falha(i, nome, [_chk('erro', 'A peça deste corte mudou depois da marcação: marque de novo.')])
            A |= mk
        else:
            # a marcação é sobre o modelo aberto: cada triângulo da peça herda a marca do triângulo do modelo mais perto
            T0 = SPL.tri_array(S)
            _, j = cKDTree(T0.mean(1)).query(Th.mean(1))
            A |= mk[j]
        if cut.get('inverter') and not loops:
            A = ~A
    if not A.any():
        return cur, _falha(i, nome, [_chk('erro', 'Nenhuma área dentro da linha.')])
    paint = np.where(A, 2, 1).astype(np.uint8)
    R = SPL.Regions(hm, paint)
    regs = [r for r in R.list if r['cor'] == 2]
    if not regs:
        return cur, _falha(i, nome, [_chk('erro', 'A área é pequena demais para um tampão.')])
    if loops:
        # só as áreas que encostam na linha (num flexi articulado, as outras cascas também ficam "dentro")
        lp = cKDTree(np.vstack(loops))
        perto = [r for r in regs if float(lp.query(R.cen[r['tris']])[0].min()) < 1.5]
        regs = perto or regs
    reg = max(regs, key=lambda r: r['area'])
    checks = [_chk('ok', 'Tampão (beta): paredes retas na direção de encaixe, fundo plano 2 mm abaixo do ponto mais baixo da área, '
                         'a mesma folga em toda a volta.')]
    resto = sum(r['area'] for r in regs) - reg['area']
    if resto > max(2.0, 0.05 * reg['area']):
        checks.append(_chk('aviso', f'A área tinha partes separadas: só a maior sai neste corte ({resto:.0f} mm² ficaram). '
                                    'Para cada parte sair, use um corte para cada uma.'))
    prm = dict(SPL.DEFAULTS, tipo='tampao', profundidade=PROFUNDIDADE, folga=float(cut.get('folga') or FOLGA),
               pino=PINO[enc], pino_mm=float(cut.get('pino_mm') or 0), _aninhar=set())
    if loops and not (mk is not None and mk.any()):
        prm['_borda'] = loops                          # a costura fica na linha desenhada
    try:
        r_ = SPL.cut_plug_auto(hm, R, reg['id'], prm, diag + 5.0)
    except Exception as ex:
        traceback.print_exc()
        return cur, _falha(i, nome, [_chk('erro', f'O tampão falhou neste corte: {ex}')])
    checks += [dict(c, texto=_texto_livre(c['texto'])) for c in r_.get('checks', [])]
    if not r_.get('ok'):
        checks.append(_chk('erro', 'Este corte não cabe num tampão. Mude a direção da linha ou use outra forma de corte '
                                   '(Automático, Seguir a linha ou Plano).'))
        return cur, _falha(i, nome, checks)
    body, piece = r_['body'], r_['piece']
    d = np.asarray(r_['axis'], np.float64)
    # o resto continua uma peça só, como veio (as cascas de um flexi articulado ficam juntas); se o bolso partiu o
    # resto, o cut_plug já avisou com erro
    Tt, col = FC._paint_from(host['T'], host['paint'], body, host['base'])
    repl = [dict(host, mesh=body, T=Tt, paint=col, _dirs=list(host.get('_dirs', [])) + [(-d).tolist()])]
    Tn, coln = FC._paint_from(host['T'], host['paint'], piece, host['base'])
    new = [dict(mesh=piece, base=host['base'], nome=nome, tipo='livre', rid=None, axis=d.tolist(), print_T=r_.get('print_T'),
                T=Tn, paint=coln, livre=i, _dir=d.tolist(), _dirs=[d.tolist()])]
    for k, x in enumerate(r_.get('extra') or []):
        m = x['mesh']
        new.append(dict(mesh=m, base=host['base'], nome=f'Cavilha · {nome}' + (f' {k + 1}' if k else ''), tipo='cavilha', rid=None,
                        axis=x.get('axis'), print_T=None, T=SPL.tri_array(m), paint=np.full(m.num_tri(), host['base'], np.uint8), livre=i))
    pieces = pieces[:hk] + repl + pieces[hk + 1:] + new
    o2 = dict(cur)
    o2['pieces'] = pieces
    az, el = _angulos(d)
    r = dict(i=i, nome=nome, ok=True, checks=checks, forma='tampao', encaixe=enc, sem_pino=PINO[enc] == 'nenhum',
             dir=dict(az=az, el=el, sugerida=True), _s=round(time.time() - t0, 1))
    return o2, r


def _angulos(d):
    d = np.asarray(d, float) / max(np.linalg.norm(d), 1e-12)
    az = (np.degrees(np.arctan2(d[0], -d[1])) + 360.0) % 360.0
    el = np.degrees(np.arcsin(np.clip(d[2], -1, 1)))
    return int(round(az)), int(round(el))
