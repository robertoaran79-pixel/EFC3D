"""EFC3D: posição de cada peça na mesa (orientação de impressão).

Para cada peça cortada testa várias direções para baixo (as faces planas grandes, a face do corte,
o eixo do encaixe e os 6 eixos) e fica com a que pede menos suporte, com mais área encostada na
mesa e sem ficar alta e instável. O corpo principal fica de pé como no modelo (as juntas e o rosto
dependem disso); dele só sai o relatório de suporte.

Regras (PLA em impressora calibrada):
  - balanço: face virada para baixo a mais de 45° da parede (ângulo com a mesa abaixo de 45°)
    precisa de suporte; a área de suporte é a área projetada dessas faces;
  - a face que encosta na mesa é a que fica a menos de 0,4 mm do ponto mais baixo e virada
    para baixo;
  - pouca área de contato para a altura da peça: recomenda brim (aba) só nessa peça.
A posição antiga (face do corte na mesa) continua quando a nova não é claramente melhor, para não
mudar o que já funcionava.
"""
import numpy as np

from split import _frame, _T, _inv

BALANCO = 45.0                 # graus: acima disso (da parede) precisa de suporte
COS_B = float(np.cos(np.radians(BALANCO)))
MESA_TOL = 0.4                 # mm acima do ponto mais baixo que ainda conta como apoio (duas camadas)
GANHO = 0.85                   # a nova posição precisa ser 15% melhor que a antiga


def _tri_geom(T):
    T = np.asarray(T, np.float64)
    nr = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    ar = np.linalg.norm(nr, axis=1) / 2
    un = nr / np.maximum(2 * ar[:, None], 1e-12)
    return T, ar, un


def evaluate(T, M):
    """Mede a peça (triângulos T no mundo) na posição M (4x4). Devolve dict(suporte mm², contato mm²,
    altura mm, base (dx, dy) mm)."""
    T, ar, un = _tri_geom(T)
    R = np.asarray(M, np.float64)[:3, :3]
    V = T.reshape(-1, 3) @ R.T
    z = V[:, 2].reshape(-1, 3)
    z0 = float(z.min())
    nz = un @ R.T[:, 2]
    zmax_t = z.max(1)
    on_bed = zmax_t <= z0 + MESA_TOL
    down = nz < -COS_B
    contato = float(ar[on_bed & (nz < -0.9)].sum())
    sup = float((ar * -nz)[down & ~on_bed].sum())
    P = V.reshape(-1, 3, 3)[on_bed].reshape(-1, 3)
    base = (np.ptp(P[:, 0]), np.ptp(P[:, 1])) if len(P) else (0.0, 0.0)
    return dict(suporte=sup, contato=contato, altura=float(z.max() - z0), base=(float(base[0]), float(base[1])))


def _M_down(d):
    """Posição em que a direção d (no modelo) fica para baixo (vai para a mesa)."""
    d = np.asarray(d, np.float64)
    d = d / max(np.linalg.norm(d), 1e-12)
    return _inv(_T(_frame(-d), np.zeros(3)))


def _score(e):
    h, c = e['altura'], e['contato']
    s = e['suporte'] + 1.5 * h
    need = 5.0 + 0.05 * h * h                     # apoio mínimo para a altura (senão tomba ou solta)
    s += 4.0 * max(0.0, need - c)
    return s - 0.15 * min(c, 400.0)


def _candidates(T, ar, un, extra):
    ds = [np.array(v, np.float64) for v in ((0, 0, -1), (0, 0, 1), (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0))]
    # faces planas grandes: normais agrupadas numa esfera de direções
    g = np.round(un * 6.0).astype(int)
    key, inv = np.unique(g, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    acc = np.bincount(inv, ar, len(key))
    for k in np.argsort(-acc)[:10]:
        sel = inv == k
        n = (un[sel] * ar[sel, None]).sum(0)
        if np.linalg.norm(n) > 1e-9:
            ds.append(n / np.linalg.norm(n))
    for d in extra:
        if d is not None and np.linalg.norm(d) > 1e-9:
            ds.append(np.asarray(d, np.float64) / np.linalg.norm(d))
    return ds


def best(T, cur=None, axis=None):
    """Melhor posição para a peça T (triângulos no mundo). cur: posição atual (print_T) ou None
    (como no modelo). axis: eixo do encaixe (fica de pé se der: furo redondo).
    Devolve (M, avaliação, mudou)."""
    T, ar, un = _tri_geom(T)
    M0 = np.eye(4) if cur is None else np.asarray(cur, np.float64)
    e0 = evaluate(T, M0)
    s0 = _score(e0)
    extra = []
    if cur is not None:
        extra.append(np.asarray(cur, np.float64)[:3, :3].T @ np.array([0.0, 0.0, -1.0]))
    if axis is not None:
        a = np.asarray(axis, np.float64)
        extra += [a, -a]
    bestM, be, bs = M0, e0, s0
    for d in _candidates(T, ar, un, extra):
        M = _M_down(d)
        e = evaluate(T, M)
        s = _score(e)
        if axis is not None:
            al = abs(float(np.dot(np.asarray(axis, np.float64) / max(np.linalg.norm(axis), 1e-12), d)))
            s += 0.2 * abs(s) * (1.0 - al)          # encaixe deitado: furo e pino saem ovais
        if s < bs:
            bestM, be, bs = M, e, s
    if bestM is not M0 and (s0 - bs) < (1.0 - GANHO) * abs(s0) + 1.0:
        return M0, e0, False                         # ganho pequeno: fica a posição de antes
    return bestM, be, bestM is not M0


def brim(e):
    """Recomenda brim quando a área de contato é pequena para a altura da peça."""
    c, h = e['contato'], e['altura']
    return c < 15.0 or (h > 15.0 and c < 0.06 * h * h)
