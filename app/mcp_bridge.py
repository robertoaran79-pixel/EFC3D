"""EFC3D: ponte para o Claude controlar o app (MCP).

O servidor MCP (mcp_server.py, iniciado pelo Claude Desktop) manda comandos para cá em
/api/mcp/cmd. A janela do app busca os comandos em /api/mcp/poll, executa (câmera, cliques,
captura de tela, prévia, etc.) e devolve em /api/mcp/result. Nada disso funciona com o
controle desligado: o usuário liga em "🤖 Claude" no topo do app.
"""
import json
import os
import sys
import threading
import time
import uuid

HOME = os.path.join(os.path.expanduser('~'), 'EFC3D')
PORT_FILE = os.path.join(HOME, 'porta.json')
APP_DIR = os.path.dirname(os.path.abspath(__file__))

_lock = threading.Lock()
_queue = []                      # comandos esperando a janela
_waiting = {}                    # id -> [Event, resultado]
_cond = threading.Condition(_lock)
_last_poll = [0.0]


def announce(port, version):
    """Grava a porta em ~/EFC3D/porta.json para o servidor MCP achar o app."""
    try:
        os.makedirs(HOME, exist_ok=True)
        with open(PORT_FILE, 'w', encoding='utf-8') as f:
            json.dump(dict(porta=int(port), pid=os.getpid(), versao=version, desde=time.time()), f)
    except Exception:
        pass


def claude_config_path():
    if sys.platform == 'darwin':
        return os.path.expanduser('~/Library/Application Support/Claude/claude_desktop_config.json')
    if sys.platform.startswith('win'):
        return os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'Claude', 'claude_desktop_config.json')
    return os.path.expanduser('~/.config/Claude/claude_desktop_config.json')


def mcp_entry():
    if getattr(sys, 'frozen', False):              # app instalado (pacote): o próprio executável faz o MCP
        return dict(command=sys.executable, args=['--mcp'])
    py = sys.executable
    if sys.platform.startswith('win') and py.lower().endswith('pythonw.exe'):
        alt = py[:-len('pythonw.exe')] + 'python.exe'
        if os.path.exists(alt):
            py = alt
    return dict(command=py, args=[os.path.join(APP_DIR, 'mcp_server.py')])


def register_claude():
    """Acrescenta o EFC3D na configuração do Claude Desktop (com cópia de segurança)."""
    path = claude_config_path()
    cfg = {}
    if os.path.exists(path):
        try:
            with open(path, encoding='utf-8') as f:
                cfg = json.load(f)
        except Exception:
            return dict(ok=False, msg=f'Não consegui ler {path}: o arquivo não é um JSON válido. Corrija ou apague e tente de novo.')
        try:
            with open(path + '.bak', 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    srv = cfg.setdefault('mcpServers', {})
    srv.pop('3d-flexi-creator', None)                # o nome antigo (3D Flexi Creator) sai
    srv['efc3d'] = mcp_entry()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
    return dict(ok=True, arquivo=path, entrada=cfg['mcpServers']['efc3d'])


def registered():
    try:
        with open(claude_config_path(), encoding='utf-8') as f:
            return 'efc3d' in (json.load(f).get('mcpServers') or {})
    except Exception:
        return False


def window_alive():
    return time.time() - _last_poll[0] < 40


def send(tipo, args, timeout):
    """Manda um comando para a janela e espera a resposta."""
    cid = uuid.uuid4().hex
    ev = threading.Event()
    with _cond:
        _waiting[cid] = [ev, None]
        _queue.append(dict(id=cid, tipo=tipo, args=args or {}))
        _cond.notify_all()
    ok = ev.wait(timeout)
    with _cond:
        res = _waiting.pop(cid, [None, None])[1]
        if not ok:
            _queue[:] = [c for c in _queue if c['id'] != cid]
    if not ok:
        return dict(ok=False, erro='A janela do app não respondeu a tempo. Ela está aberta?')
    return res


def poll(wait=25.0):
    _last_poll[0] = time.time()
    end = time.time() + wait
    with _cond:
        while not _queue:
            left = end - time.time()
            if left <= 0:
                return {}
            _cond.wait(left)
            _last_poll[0] = time.time()
        return _queue.pop(0)


def result(cid, res):
    with _cond:
        w = _waiting.get(cid)
        if w:
            w[1] = res
            w[0].set()
