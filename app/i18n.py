"""EFC3D: idiomas no servidor.

Os textos do app são escritos em português. O relatório da exportação (LEIA.txt) e os nomes das
peças nos arquivos saem no idioma escolhido na tela, com o mesmo dicionário da tela
(web/i18n/<idioma>.js; o app avisa o idioma em /api/lang)."""
import json
import os
import re

LANGS = ('pt', 'en', 'es')
_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web', 'i18n')
_cur = ['pt']
_dicts = {}


def set_lang(lang):
    _cur[0] = lang if lang in LANGS else 'pt'


def lang():
    return _cur[0]


def _load(lang):
    if lang in _dicts:
        return _dicts[lang]
    exact, tpls = {}, []
    try:
        with open(os.path.join(_DIR, f'{lang}.js'), encoding='utf-8') as f:
            txt = f.read()
        d = json.loads(txt[txt.index('=\n') + 2:txt.rindex(';')])
    except Exception:
        d = {}
    for k, v in d.items():
        if '{}' not in k:
            exact[k] = v
            continue
        parts = k.split('{}')
        fixed = len(re.sub(r'[^A-Za-zÀ-ÖØ-öø-ÿ]', '', ''.join(parts)))
        if not fixed or any(p == '' for p in parts[1:-1]):
            continue                              # só valores, ou dois valores colados: não dá para separar
        solid = len(re.sub(r'\s', '', ''.join(parts)))
        tpls.append((re.compile('^' + '(.+?)'.join(re.escape(p) for p in parts) + '$', re.S), v, fixed * 1000 + solid, solid < 6))
    tpls.sort(key=lambda t: -t[2])
    _dicts[lang] = (exact, tpls)
    return _dicts[lang]


def _short(g):
    # valor de verdade: número curto ("3 de 10", "J2 de J5")
    return len(g) <= 14 and bool(re.search(r'\d', g)) and len(g.split()) <= 2


def _num(s, lg):
    """Números no jeito do inglês: 78.206 -> 78,206 e 0,4 -> 0.4."""
    if lg != 'en':
        return s

    def f(m):
        t = m.group(0)
        if re.fullmatch(r'\d{1,3}(\.\d{3})+', t):
            return t.replace('.', ',')
        if re.fullmatch(r'\d+,\d+', t):
            return t.replace(',', '.')
        return t
    return re.sub(r'\d+(?:[.,]\d+)*', f, s)


def _one(s, lg, depth, strong=False):
    """strong: só aceita modelo cujos valores com palavras também foram traduzidos."""
    exact, tpls = _load(lg)
    if s in exact:
        return exact[s]
    if len(s) > 500:
        return None                               # texto longo: só por pedaços (modelo com valores seria lento)
    weak = None
    for rx, v, _, strict in tpls:
        m = rx.match(s)
        if not m or (strict and not all(_short(g) for g in m.groups())):
            continue
        if strong and any(re.search(r'[.!?;:]\s|\s·\s|\s→|,\s', g) for g in m.groups()):
            continue                              # um valor não pode engolir outra frase
        out, ok = v, True
        for j, g in enumerate(m.groups()):
            t = tr(g, lg, depth + 1) if depth < 3 else g
            if t == g and re.search(r'[A-Za-zÀ-ÖØ-öø-ÿ]{3,}', g):
                ok = False                        # frase que ficou em português
            out = out.replace('{%d}' % j, _num(g, lg) if t == g else t)
        if ok:
            return out
        if weak is None:
            weak = out
    return None if strong else weak


def _residue(src, out):
    """Quantas palavras do original ficaram iguais (sem tradução)."""
    return sum(1 for w in re.findall(r'[A-Za-zÀ-ÖØ-öø-ÿ]{3,}', src) if w in out)


def _split_keep(s, rx):
    bits = re.split(rx, s)
    out = []
    for i in range(0, len(bits), 2):
        sep = bits[i + 1] if i + 1 < len(bits) else ''
        if bits[i] or sep:
            out.append((bits[i], sep or ''))
    return out


_CUTS = [r'([.!?;:](?:\s+))', r'(,\s+)', r'(\s+·\s+|\s+→\s+|\s+\|\s+)']


def _pieces(ps, lg, depth):
    """Junta o maior trecho seguido que tenha tradução ("Área marcada: 2 borda(s)..." tem ":" no meio)."""
    out, anyt, i, n = [], False, 0, len(ps)
    while i < n:
        done = False
        for k in range(n - 1, i - 1, -1):
            txt = ''.join(ps[q][0] + (ps[q][1] if q < k else '') for q in range(i, k + 1))
            if not re.search(r'[A-Za-zÀ-ÖØ-öø-ÿ]', txt):
                continue
            punct = ps[k][1].rstrip()
            if punct and k > i:                   # com o sinal que fecha o trecho ("... de corte.")
                tp = _one(re.sub(r'\s+', ' ', txt + punct).strip(), lg, depth, True)
                if tp is not None:
                    out.append(tp + ps[k][1][len(punct):])
                    i, anyt, done = k + 1, True, True
                    break
            if k > i:
                t = _one(re.sub(r'\s+', ' ', txt).strip(), lg, depth, True)
                if t is None:
                    bt = re.sub(r'[.!?:;,]$', '', txt)
                    if bt != txt:
                        tb = _one(re.sub(r'\s+', ' ', bt).strip(), lg, depth, True)
                        t = tb + txt[len(bt):] if tb is not None else None
            else:
                t = _core(txt, lg, depth, True)
            if t is not None:
                out.append(t + ps[k][1])
                i, anyt, done = k + 1, True, True
                break
        if not done:
            out.append(ps[i][0] + ps[i][1])
            i += 1
    return ''.join(out) if anyt else None


def _core(s, lg, depth, inner):
    m = re.match(r'^([^A-Za-zÀ-ÖØ-öø-ÿ0-9(¿¡"\'«]*)(.*?)(\s*)$', s, re.S)
    pre, body, post = m.group(1), m.group(2), m.group(3)
    if not body:
        return None if inner else s
    key = re.sub(r'\s+', ' ', body)
    r = None
    if pre.strip():                               # o texto com o símbolo do começo ("📂 Abrir…")
        full = re.sub(r'\s+', ' ', (pre + body)).strip()
        r0 = _one(full, lg, depth)
        if r0 is not None:
            return r0 + post if not pre[:len(pre) - len(pre.lstrip())] else pre[:len(pre) - len(pre.lstrip())] + r0 + post
    r = None
    if re.search(r'\S\s{2,}\S', body) and depth < 4:   # colunas separadas por 2+ espaços
        r = _pieces(_split_keep(body, r'(\s{2,})'), lg, depth + 1)
    if r is None:
        r = _one(key, lg, depth, True)
    if r is None:
        bare = re.sub(r'[.!?:;,]$', '', key)
        if bare != key:
            rb = _one(bare, lg, depth, True)
            if rb is not None:
                r = rb + key[len(bare):]
    if r is None and depth < 4:
        for rx in _CUTS:
            ps = _split_keep(key, rx)
            if len(ps) > 1:
                r = _pieces(ps, lg, depth + 1)
                if r is not None:
                    break
    w = _one(key, lg, depth)                      # modelo com valor sem tradução (nome dado pelo usuário)
    if w is not None and (r is None or _residue(key, w) <= _residue(key, r)):
        r = w
    if r is None:
        return None if inner else s
    return pre + r + post


def tr(s, lg=None, depth=0):
    """Traduz um texto: inteiro; senão em pedaços (frases, listas), linha por linha."""
    lg = lg or _cur[0]
    if lg == 'pt' or not s or not re.search(r'[A-Za-zÀ-ÖØ-öø-ÿ]', s):
        return s
    if '\n' in s:
        if len(s) < 400 and s.count('\n') <= 3:     # parágrafo quebrado em linhas
            whole = _core(re.sub(r'\s*\n\s*', ' ', s), lg, depth, True)
            if whole is not None and not re.search(r'\S\s{2,}\S', s):
                return whole
        return '\n'.join(_core(x, lg, depth, False) for x in s.split('\n'))
    return _core(s, lg, depth, False)


def tr_text(text, lg=None):
    """Um texto de várias linhas (relatório): linha por linha."""
    lg = lg or _cur[0]
    if lg == 'pt':
        return text
    tags = {'en': {'ok': 'ok', 'aviso': 'warning', 'erro': 'error'}, 'es': {'ok': 'ok', 'aviso': 'aviso', 'erro': 'error'}}.get(lg, {})

    def line(x):
        if not re.search(r'[A-Za-zÀ-ÖØ-öø-ÿ]', x):
            return x
        m = re.match(r'^(\s*)\[(\w+)\](\s+)(.*)$', x)       # "   [aviso] mensagem"
        if m:
            return m.group(1) + '[' + tags.get(m.group(2), m.group(2)) + ']' + m.group(3) + _core(m.group(4), lg, 0, False)
        return _core(x, lg, 0, False)
    return '\n'.join(line(x) for x in text.split('\n'))
