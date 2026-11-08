"""EFC3D (Easy Flexy and Cuts 3D): autoteste do app instalado.

    EFC3D --autoteste <pasta>      (no app empacotado)
    python3 desktop.py --autoteste <pasta>

Monta um boneco simples (tronco, pescoço e cabeça), faz um corte livre no pescoço com soquete, exporta as peças
(3MF e STLs) e uma junta própria (Arco) no tronco, relê os arquivos gravados e confere a malha. Não abre janela
nem rede. Sai com código 0 se tudo deu certo; o relatório vai para <pasta>/autoteste.json.
"""
import json
import math
import os
import sys
import time
import traceback


def _laco(z, r, seg=96, k=192):
    """Linha em volta do pescoço (cilindro de `seg` lados e raio r) na altura z, em cima da pele: cada ponto fica na
    face do polígono, como a linha desenhada na tela."""
    import numpy as np
    t = np.linspace(0, 2 * math.pi, k, endpoint=False)
    passo = 2 * math.pi / seg
    off = (t % passo) - passo / 2                      # ângulo até o meio da face do polígono
    rr = r * math.cos(passo / 2) / np.cos(off)
    return np.c_[rr * np.cos(t), rr * np.sin(t), np.full(k, z)]


def rodar(pasta, rel=None):
    import numpy as np
    import manifold3d as mf
    import engine as E
    import split as SPL
    import freecut as FC
    import editor as ED
    import printers as PRN
    import server as SV
    os.makedirs(pasta, exist_ok=True)
    rel = rel if rel is not None else {}
    rel.update(versao=SV.VERSION, plataforma=sys.platform, etapas=[])

    def etapa(nome, ok, **kw):
        rel['etapas'].append(dict(nome=nome, ok=bool(ok), **kw))
        if not ok:
            raise RuntimeError(nome)
    t0 = time.time()
    # formas arredondadas como um boneco de verdade (faces planas grandes e subdivididas o Manifold junta depois
    # do corte, e o teste 7 da junta leria isso como perda de resolução)
    tronco = mf.Manifold.sphere(15, 160).scale([1.0, 0.75, 1.0]).translate([0, 0, 15])
    pesc = mf.Manifold.cylinder(14, 5, 5, 96).refine_to_length(1.0).translate([0, 0, 27])   # pescoço com malha fina
    cab = mf.Manifold.sphere(12, 128).translate([0, 0, 50])
    S = E.read_stl(E.write_stl(tronco + pesc + cab))
    etapa('modelo', S.volume() > 1000, triangulos=int(S.num_tri()))
    out = SPL.run(S, np.ones(S.num_tri(), np.uint8), [])
    corte = dict(nome='Corte 1', linhas=[_laco(34.0, 5.0).tolist()], forma='curva', encaixe='colar', folga=0.2,
                 folga_pino=0.4, pino_mm=0, inverter=False, soquete=True, soquete_mm=4)
    out = FC.apply(out, [corte], S)
    lv = out.get('livres') or [{}]
    etapa('corte livre', lv[0].get('ok') and len(out['pieces']) >= 2, pecas=len(out['pieces']),
          avisos=[c['texto'] for c in lv[0].get('checks', []) if c['nivel'] != 'ok'])
    ex = SPL.export(out, os.path.join(pasta, 'cortes'), 'autoteste', ['#cccccc'] * 9, printer=PRN.get('a1'))
    ruins = []
    for f in ex.get('stls', []):
        b = open(os.path.join(pasta, 'cortes', f), 'rb').read()
        T = np.frombuffer(b[84:], dtype=np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')]))['v']
        e = SPL.mesh_errors(T)
        if any(e[:2]):
            ruins.append((f, e))
    etapa('exportação das peças', ex.get('ok') and len(ex.get('stls', [])) >= 2 and not ruins,
          arquivos=ex.get('stls'), arquivo3mf=ex.get('arquivo3mf'), malha_ruim=ruins)
    jp = ED.suggest_at(S, 0.0, 0.0, 0.0, ED.PADRAO)       # junta sugerida pelo app no tronco, como na tela
    R = ED.export(S, E.write_stl(S), [jp], 0.4, os.path.join(pasta, 'juntas'), nome='autoteste')
    luz = [j.get('luz') for j in R.get('juntas', [])]
    testes = [t.get('ok') for t in (R.get('testes') or [])]
    etapa('junta própria (Arco)', R.get('ok') and not R.get('bloqueado') and luz and 'erro' not in luz
          and all(testes), tipo=jp['tipo'], luz=luz, testes=testes, arquivos=R.get('arquivos') or R.get('stls'))
    rel['segundos'] = round(time.time() - t0, 1)
    return rel


def main(pasta):
    if sys.stdout is None or sys.stderr is None:      # app de janela no Windows: sem console
        nul = open(os.devnull, 'w')
        sys.stdout = sys.stdout or nul
        sys.stderr = sys.stderr or nul
    pasta = os.path.abspath(os.path.expanduser(pasta))
    os.makedirs(pasta, exist_ok=True)
    rel = dict(etapas=[])
    code = 0
    try:
        rel = rodar(pasta, rel)
        rel['ok'] = True
    except Exception as ex:
        rel['ok'] = False
        rel['erro'] = f'{type(ex).__name__}: {ex}'
        rel['traceback'] = traceback.format_exc()
        code = 1
    with open(os.path.join(pasta, 'autoteste.json'), 'w', encoding='utf-8') as f:
        json.dump(rel, f, ensure_ascii=False, indent=1, default=str)
    print(json.dumps(rel, ensure_ascii=False, default=str), flush=True)
    return code
