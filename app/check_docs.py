"""Confere se a Ajuda (web/ajuda.js, ajuda.en.js, ajuda.es.js) e as traduções acompanham a versão do app. Roda antes de cada pacote:
    python3 app/check_docs.py      -> sai com erro se algo estiver desatualizado."""
import os, re, sys
H = os.path.dirname(os.path.abspath(__file__))
ver = re.search(r"VERSION = '([^']+)'", open(os.path.join(H, 'server.py'), encoding='utf-8').read()).group(1)
doc = open(os.path.join(H, 'web', 'ajuda.js'), encoding='utf-8').read().split('export const DOCS', 1)[1]
dv = re.search(r"versao: '([^']+)'", doc).group(1)
nv = re.search(r"novidades: \[\s*\{ versao: '([^']+)'", doc).group(1)
leia = open(os.path.join(H, '..', 'LEIA-ME.md'), encoding='utf-8').read() if os.path.exists(os.path.join(H, '..', 'LEIA-ME.md')) else ''
erros = []
if dv != ver: erros.append(f'ajuda.js versao {dv} diferente do app {ver}')
if nv != ver: erros.append(f'ajuda.js sem novidades da versão {ver} (topo: {nv})')
if leia and f'# EFC3D {ver}' not in leia: erros.append(f'LEIA-ME.md não está na versão {ver}')
for sel in sorted(set(re.findall(r'data-show="(#[\w-]+)"', doc) + re.findall(r"alvo: '(#[\w-]+)'", doc))):
    html = open(os.path.join(H, 'web', 'index.html'), encoding='utf-8').read() + open(os.path.join(H, 'web', 'app.js'), encoding='utf-8').read() + open(os.path.join(H, 'web', 'ui.js'), encoding='utf-8').read().replace("viewbar.id = 'viewbar'", 'id="viewbar"')
    if f'id="{sel[1:]}"' not in html: erros.append(f'"Mostrar na tela" aponta para {sel}, que não existe na tela')
# Ajuda em inglês e espanhol: mesma versão, mesmos tópicos e os mesmos "Mostrar na tela"
def _ids(t):
    return re.findall(r"^\s+id: '([\w-]+)', grupo:", t, re.M)
for lg in ('en', 'es'):
    p = os.path.join(H, 'web', f'ajuda.{lg}.js')
    if not os.path.exists(p):
        erros.append(f'falta a Ajuda em {lg} (web/ajuda.{lg}.js)'); continue
    d2 = open(p, encoding='utf-8').read().split('export const DOCS', 1)[1]
    if re.search(r"versao: '([^']+)'", d2).group(1) != ver: erros.append(f'ajuda.{lg}.js não está na versão {ver}')
    if re.search(r"novidades: \[\s*\{ versao: '([^']+)'", d2).group(1) != ver: erros.append(f'ajuda.{lg}.js sem novidades da versão {ver}')
    if _ids(d2) != _ids(doc): erros.append(f'ajuda.{lg}.js com tópicos diferentes da ajuda.js')
    if sorted(re.findall(r'data-show="(#[\w-]+)"', d2)) != sorted(re.findall(r'data-show="(#[\w-]+)"', doc)):
        erros.append(f'ajuda.{lg}.js com "Mostrar na tela" diferentes da ajuda.js')
# textos da tela sem tradução (o JavaScript e o HTML são lidos com Node, se houver: tools/i18n)
import json, subprocess, tempfile, shutil
T = os.path.join(H, '..', 'tools', 'i18n')
if os.path.isdir(T):
    keys = set()
    with tempfile.TemporaryDirectory() as td:
        try:
            subprocess.run([sys.executable, os.path.join(T, 'extract_py.py'), os.path.join(td, 'py.json')], check=True, capture_output=True)
            keys |= set(json.load(open(os.path.join(td, 'py.json'), encoding='utf-8')))
        except Exception as e:
            erros.append(f'não consegui ler os textos do Python: {e}')
        if shutil.which('node') and os.path.isdir(os.path.join(T, 'node_modules')):
            try:
                subprocess.run(['node', os.path.join(T, 'extract.mjs'), os.path.join(td, 'js.json')], check=True, capture_output=True)
                keys |= set(json.load(open(os.path.join(td, 'js.json'), encoding='utf-8')))
            except Exception as e:
                erros.append(f'não consegui ler os textos do JavaScript: {e}')
        else:
            print('(aviso: sem Node em tools/i18n: só os textos do Python foram conferidos)')
    keys = {k for k in keys if not any(p == '' for p in k.split('{}')[1:-1])}
    for lg in ('en', 'es'):
        txt = open(os.path.join(H, 'web', 'i18n', f'{lg}.js'), encoding='utf-8').read()
        d = json.loads(txt[txt.index('=\n') + 2:txt.rindex(';')])
        falta = sorted(k for k in keys if k not in d)
        if falta:
            erros.append(f'{len(falta)} texto(s) sem tradução em {lg} (ex.: {falta[0]!r}). Veja tools/i18n/LEIA.md')
        for k, v in d.items():
            n = k.count('{}')
            if sorted(set(re.findall(r'\{(\d+)\}', v))) != [str(i) for i in range(n)]:
                erros.append(f'{lg}: valores trocados em {k!r}'); break
print('\n'.join(erros) if erros else f'Ajuda e traduções em dia com a versão {ver}.')
sys.exit(1 if erros else 0)
