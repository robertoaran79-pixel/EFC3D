#!/usr/bin/env python3
"""EFC3D: servidor MCP (stdio) para o Claude controlar o app.

O Claude Desktop inicia este arquivo (o app registra em "🤖 Claude" › Registrar no Claude
Desktop). Ele conversa com o app aberto pela porta gravada em ~/EFC3D/porta.json.
Só funciona com "Permitir que o Claude controle o app" ligado no próprio app.
Sem dependências: só a biblioteca padrão do Python.
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

HOME = os.path.join(os.path.expanduser('~'), 'EFC3D')
APP_DIR = os.path.dirname(os.path.abspath(__file__))
NAME, VERSION = 'efc3d', '1.0'


def _port():
    try:
        with open(os.path.join(HOME, 'porta.json'), encoding='utf-8') as f:
            return int(json.load(f)['porta'])
    except Exception:
        return int(os.environ.get('FLEXI_PORT', '8765'))


def _http(path, body=None, timeout=30):
    url = f'http://127.0.0.1:{_port()}{path}'
    data = None if body is None else json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='GET' if body is None else 'POST',
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read() or b'{}')
        except Exception:
            return dict(ok=False, erro=f'HTTP {e.code}')
    except Exception as e:
        return dict(ok=False, erro='O EFC3D não está aberto (ou não respondeu). Use a ferramenta iniciar_app '
                                  f'ou abra o app. Detalhe: {e}')


def _cmd(tipo, args=None, timeout=120):
    r = _http('/api/mcp/cmd', dict(tipo=tipo, args=args or {}, timeout=timeout), timeout=timeout + 15)
    return r


XY = {'x': {'type': 'number', 'description': 'pixels a partir da esquerda da vista 3D'},
      'y': {'type': 'number', 'description': 'pixels a partir do topo da vista 3D'}}
MOD = {'shift': {'type': 'boolean'}, 'alt': {'type': 'boolean'}, 'meta': {'type': 'boolean', 'description': '⌘ no Mac'},
       'ctrl': {'type': 'boolean'}}

TOOLS = [
    dict(name='status', description='Versão do app, se está aberto, se o controle pelo Claude está ligado e se há um modelo carregado.',
         inputSchema={'type': 'object', 'properties': {}}),
    dict(name='iniciar_app', description='Abre o EFC3D se ele não estiver aberto.',
         inputSchema={'type': 'object', 'properties': {}}),
    dict(name='estado', description='Estado do app: modelo, modo (pintura, marcação, separar), ferramenta, vista, juntas, cortes livres '
                                    '(linhas, área marcada, encaixe, semáforo e mensagens) e tamanho da vista 3D em pixels.',
         inputSchema={'type': 'object', 'properties': {}}),
    dict(name='captura', description='Imagem da vista 3D como está agora (com os rótulos). Use para ver o modelo e decidir onde clicar. '
                                     'Coordenadas de clique = pixels da imagem × escala_px.',
         inputSchema={'type': 'object', 'properties': {'largura': {'type': 'number', 'description': 'largura máxima em pixels (padrão 1100)'}}}),
    dict(name='camera', description='Posiciona a câmera. vista: frente, tras, esquerda, direita, topo, baixo, 3d. Ou azimute/elevação em '
                                    'graus (azimute 0 = frente, 90 = direita). zoom > 1 aproxima. alvo = ponto [x,y,z] em mm para olhar.',
         inputSchema={'type': 'object', 'properties': {'vista': {'type': 'string'}, 'azimute': {'type': 'number'}, 'elevacao': {'type': 'number'},
                                                       'zoom': {'type': 'number'}, 'distancia': {'type': 'number'},
                                                       'alvo': {'type': 'array', 'items': {'type': 'number'}}}}),
    dict(name='abrir_modelo', description='Abre um modelo (STL, GLB, OBJ, .zip) ou projeto (.flexiproj) pelo caminho no computador.',
         inputSchema={'type': 'object', 'properties': {'caminho': {'type': 'string'}}, 'required': ['caminho']}),
    dict(name='clicar', description='Clica na vista 3D, como o mouse: pontos da Linha, balde, selecionar área. botao: esquerdo ou direito.',
         inputSchema={'type': 'object', 'properties': dict(XY, botao={'type': 'string'}, duplo={'type': 'boolean'}, **MOD), 'required': ['x', 'y']}),
    dict(name='arrastar', description='Arrasta na vista 3D (pincel, borracha, girar com o botão direito).',
         inputSchema={'type': 'object', 'properties': {'de': {'type': 'array', 'items': {'type': 'number'}}, 'para': {'type': 'array', 'items': {'type': 'number'}},
                                                       'passos': {'type': 'number'}, 'botao': {'type': 'string'}, 'shift': {'type': 'boolean'}},
                      'required': ['de', 'para']}),
    dict(name='mover_mouse', description='Passa o mouse sobre a vista 3D (mostra a prévia do balde).',
         inputSchema={'type': 'object', 'properties': dict(XY, shift={'type': 'boolean'}), 'required': ['x', 'y']}),
    dict(name='tecla', description='Aperta uma tecla, como no teclado: "Enter", "Escape", "Backspace", "l", "b", "f", "e", "z" com meta '
                                   '(⌘Z), "[", "]".',
         inputSchema={'type': 'object', 'properties': dict({'tecla': {'type': 'string'}, 'vezes': {'type': 'number'}}, **MOD), 'required': ['tecla']}),
    dict(name='clicar_botao', description='Clica num botão ou item da barra lateral pelo texto (ex.: "Novo corte", "Prévia das peças", '
                                          '"Exportar") ou pelo seletor CSS (ex.: "#fc-new").',
         inputSchema={'type': 'object', 'properties': {'texto': {'type': 'string'}, 'seletor': {'type': 'string'}}}),
    dict(name='preencher', description='Muda um campo da barra lateral (select, número, caixa de marcar) pelo seletor CSS.',
         inputSchema={'type': 'object', 'properties': {'seletor': {'type': 'string'}, 'valor': {}}, 'required': ['seletor', 'valor']}),
    dict(name='ler_tela', description='Texto da barra lateral, linha de status e botões visíveis (com id).',
         inputSchema={'type': 'object', 'properties': {}}),
    dict(name='ponto_3d', description='Qual ponto do modelo (mm) está no pixel x, y da vista 3D.',
         inputSchema={'type': 'object', 'properties': XY, 'required': ['x', 'y']}),
    dict(name='tela_de_3d', description='Onde pontos do modelo [[x,y,z] mm] aparecem na vista 3D, em pixels.',
         inputSchema={'type': 'object', 'properties': {'pontos': {'type': 'array', 'items': {'type': 'array', 'items': {'type': 'number'}}}},
                      'required': ['pontos']}),
    dict(name='previa_pecas', description='Roda a prévia das peças (peças por cor e cortes livres) e devolve as peças e o semáforo de cada corte.',
         inputSchema={'type': 'object', 'properties': {}}),
    dict(name='executar_js', description='Executa JavaScript na janela do app (função async com F = window.flexi e S = estado). '
                                         'Devolve o valor retornado. Para diagnóstico e automações.',
         inputSchema={'type': 'object', 'properties': {'codigo': {'type': 'string'}}, 'required': ['codigo']}),
]
MAP = {'abrir_modelo': 'abrir', 'previa_pecas': 'previa', 'executar_js': 'js'}
LONG = {'previa_pecas': 1800, 'abrir_modelo': 300, 'executar_js': 600}


def _text(obj, err=False):
    return dict(content=[dict(type='text', text=obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, indent=1))],
                isError=bool(err))


def call(name, args):
    if name == 'status':
        st = _http('/api/status', timeout=5)
        if st.get('ok') is False and 'erro' in st:
            return _text(st['erro'], True)
        cfg = _http('/api/mcp/config', timeout=5)
        return _text(dict(versao=st.get('versao'), modelo_carregado=st.get('loaded'), modelo=st.get('name'), ocupado=st.get('busy'),
                          progresso=st.get('progress'), controle_ligado=cfg.get('ativo'), janela_aberta=cfg.get('janela')))
    if name == 'iniciar_app':
        st = _http('/api/status', timeout=3)
        if st.get('versao'):
            return _text('O app já está aberto (versão %s).' % st['versao'])
        kw = {}
        if sys.platform.startswith('win'):
            kw['creationflags'] = 0x00000008 | 0x00000200          # DETACHED_PROCESS | NEW_PROCESS_GROUP
        else:
            kw['start_new_session'] = True
        log = open(os.path.join(HOME, 'app.log'), 'a')
        cmd = [sys.executable] if getattr(sys, 'frozen', False) else [sys.executable, os.path.join(APP_DIR, 'desktop.py')]
        subprocess.Popen(cmd, cwd=APP_DIR, stdout=log, stderr=log, **kw)
        for _ in range(60):
            time.sleep(1)
            st = _http('/api/status', timeout=3)
            if st.get('versao'):
                return _text('App aberto (versão %s). Ligue "Permitir que o Claude controle o app" em 🤖 Claude, se ainda não estiver.' % st['versao'])
        return _text('Mandei abrir o app, mas ele ainda não respondeu.', True)
    tipo = MAP.get(name, name)
    r = _cmd(tipo, args, LONG.get(name, 120))
    if not r.get('ok', True) and 'resultado' not in r:
        return _text(r.get('erro') or r.get('error') or r, True)
    res = r.get('resultado', r)
    if isinstance(res, dict) and res.get('ok') is False:
        return _text(res.get('erro') or res, True)
    val = res.get('resultado') if isinstance(res, dict) and 'resultado' in res else res
    if name == 'captura' and isinstance(val, dict) and val.get('imagem'):
        info = {k: v for k, v in val.items() if k != 'imagem'}
        return dict(content=[dict(type='image', data=val['imagem'], mimeType=val.get('mime', 'image/jpeg')),
                             dict(type='text', text=json.dumps(info, ensure_ascii=False))], isError=False)
    if isinstance(val, dict) and val.get('erro'):
        return _text(val['erro'], True)
    return _text(val)


def main():
    for st in (sys.stdin, sys.stdout):
        try:
            st.reconfigure(encoding='utf-8')
        except Exception:
            pass
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        mid, method, params = msg.get('id'), msg.get('method'), msg.get('params') or {}
        if mid is None:
            continue                                     # notificações (initialized, cancelled)
        try:
            if method == 'initialize':
                res = dict(protocolVersion=params.get('protocolVersion') or '2024-11-05', capabilities=dict(tools={}),
                           serverInfo=dict(name=NAME, version=VERSION),
                           instructions='Controla o EFC3D aberto no computador. Comece com status e estado; use captura '
                                        'para ver a vista 3D e clicar/arrastar/tecla para agir como o usuário.')
            elif method == 'tools/list':
                res = dict(tools=TOOLS)
            elif method == 'tools/call':
                res = call(params.get('name'), params.get('arguments') or {})
            elif method == 'ping':
                res = {}
            else:
                out = dict(jsonrpc='2.0', id=mid, error=dict(code=-32601, message='método desconhecido: %s' % method))
                sys.stdout.write(json.dumps(out) + '\n')
                sys.stdout.flush()
                continue
            out = dict(jsonrpc='2.0', id=mid, result=res)
        except Exception as e:
            out = dict(jsonrpc='2.0', id=mid, result=_text('Erro: %s' % e, True))
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + '\n')
        sys.stdout.flush()


if __name__ == '__main__':
    main()
