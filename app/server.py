"""EFC3D (Easy Flexy and Cuts 3D) local server.

Runs only on this computer (127.0.0.1). Serves the web interface and the geometry engine.
Start: python server.py   (the install script creates a launcher for this)
"""
import json
import os
import sys
import threading
import time
import traceback
import webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import numpy as np

import engine as E
import planner as PL
import editor as ED
import paint as PT
import split as SPL
import freecut as FC
import conectores as CN
import mcp_bridge as BR
import printers as PRN
import texture as TX
import base64
import subprocess

VERSION = '1.54'

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, 'web')
def _documents():
    """The user's Documents folder (on Windows it may be moved, e.g. to OneDrive)."""
    if sys.platform == 'win32':
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(1024)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:
                return buf.value
        except Exception:
            pass
    return os.path.join(os.path.expanduser('~'), 'Documents')


import pastas as PST
OUT_DIR = PST.SAIDA_PADRAO                                        # default
CONFIG_FILE = os.path.join(PST.DADOS, 'config.json')


def load_config():
    try:
        return json.load(open(CONFIG_FILE, encoding='utf-8'))
    except Exception:
        return {}


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    tmp = CONFIG_FILE + '.tmp'
    json.dump(cfg, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(tmp, CONFIG_FILE)


def out_dir():
    """Where exports, coupons and projects go: the folder you chose, or the default."""
    d = load_config().get('pasta_saida') or OUT_DIR
    os.makedirs(d, exist_ok=True)
    return d


RECENT_MAX = 10


def add_recent(path, tipo):
    """Remember a project or model opened/saved by path (newest first, no duplicates)."""
    try:
        path = os.path.abspath(os.path.expanduser(path))
        cfg = load_config()
        lst = [r for r in cfg.get('recentes', []) if r.get('path') != path]
        lst.insert(0, dict(path=path, tipo=tipo, quando=time.strftime('%Y-%m-%d %H:%M')))
        cfg['recentes'] = lst[:RECENT_MAX]
        save_config(cfg)
    except Exception:
        pass                                    # the list is a convenience; never block opening


def recent_list():
    out = []
    for r in load_config().get('recentes', []):
        pth = r.get('path') or ''
        if os.path.isfile(pth):
            out.append(dict(path=pth, tipo=r.get('tipo', 'projeto'), quando=r.get('quando', ''),
                            nome=os.path.basename(pth), pasta=os.path.dirname(pth)))
    return out


def _win_dialog(kind, name='', start=''):
    """Windows dialog (tkinter) for when the app runs in the browser instead of its own window.
    Returns a path, '' when cancelled, None when tkinter is not available."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        ini = start if start and os.path.isdir(start) else None
        if kind == 'pasta':
            r = filedialog.askdirectory(parent=root, initialdir=ini, title='Escolha a pasta onde salvar')
        elif kind == 'salvar':
            r = filedialog.asksaveasfilename(parent=root, initialdir=ini, initialfile=name, title='Salvar projeto como',
                                             defaultextension='.flexiproj', filetypes=[('Projeto 3D Flexi', '*.flexiproj')])
        else:
            r = filedialog.askopenfilename(parent=root, initialdir=ini, title='Abrir modelo ou projeto',
                                           filetypes=[('Modelos e projetos', '*.flexiproj *.stl *.glb *.gltf *.obj *.zip'),
                                                      ('Todos', '*.*')])
        root.destroy()
        return os.path.normpath(r) if r else ''
    except Exception:
        return None


def mac_dialog(kind, name='', start=''):
    """Native Mac dialog through AppleScript. Returns a path, '' when cancelled, None when
    there is no Mac dialog here."""
    if sys.platform == 'win32':
        return _win_dialog(kind, name, start)
    if sys.platform != 'darwin':
        return None
    esc = lambda t: str(t).replace('\\', '\\\\').replace('"', '\\"')
    loc = f' default location (POSIX file "{esc(start)}")' if start and os.path.isdir(start) else ''
    if kind == 'pasta':
        script = f'POSIX path of (choose folder with prompt "Escolha a pasta onde salvar"{loc})'
    elif kind == 'salvar':
        script = f'POSIX path of (choose file name with prompt "Salvar projeto como" default name "{esc(name)}"{loc})'
    else:
        script = f'POSIX path of (choose file with prompt "Abrir modelo (STL, GLB, OBJ, .zip) ou projeto (.flexiproj)"{loc})'
    r = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    if r.returncode != 0:
        return ''
    return r.stdout.strip()
PORT = int(os.environ.get('FLEXI_PORT', '8765'))

JANELAS = {}              # janela -> último aviso de que está aberta (/api/ping)
STATE = dict(original=None, base=None, name='modelo', result=None, report=None,
             busy=False, progress='', joints=[], an=None, preview={}, export=None,
             paint=None, palette=None, proj_path=None, split=None)


def _project_full(S, joints, clearance, prepare=None, separar=None, livres=None):
    """The whole project: model, joints, painting, palette and the "Separar por cor" options."""
    extra = dict(prepare=prepare)
    if separar:
        extra['separar'] = separar
    if livres:
        extra['livres'] = livres                        # Corte livre: as linhas e as opções
    extra.update(ED.paint_extra(_paint_ok(), STATE.get('palette')))
    return ED.project_dict(E.write_stl(S), joints, float(clearance or 0.4), STATE['name'], extra)


def _write_export_project(S, folder, body):
    """Every export carries the full project (not only the articulated part), so opening it
    brings back the colours and the cuts."""
    safe = ''.join(c if c.isalnum() or c in '-_' else '_' for c in STATE['name']) or 'modelo'
    pj = body.get('projeto') or {}
    d = _project_full(S, body.get('joints', []), body.get('clearance', 0.4), pj.get('prepare'), pj.get('separar'), pj.get('livres'))
    for root, _dirs, files in os.walk(folder):        # partial copies written per articulated part
        for fn in files:
            if fn.endswith('.flexiproj'):
                os.remove(os.path.join(root, fn))
    path = os.path.join(folder, f'{safe}.flexiproj')
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(d, f)
    os.replace(tmp, path)
    return path


def _paint_ok():
    p = STATE.get('paint')
    return p if (p is not None and STATE['base'] is not None and len(p) == STATE['base'].num_tri()) else None
CHECK_LOCK = threading.Lock()

JOINT_KEYS = ('type', 'x', 'y', 'z', 'angle', 'size', 'yaw', 'pitch', 'papel', 'parte', 'estilo')


def _clean(j):
    """Planner joints carry internal data (numpy, plans): send only what the UI edits."""
    out = {}
    for k in JOINT_KEYS:
        v = j.get(k)
        if v is None:
            continue
        out[k] = round(float(v), 2) if isinstance(v, (int, float, np.floating, np.integer)) else v
    return out


def _analyze():
    try:
        STATE['an'] = PL.analyze(STATE['base'])
    except Exception:
        traceback.print_exc()
        STATE['an'] = None


def _plan(target, clearance):
    an = STATE['an']
    if an is None:
        return [], ['Não consegui reconhecer corpo e patas neste modelo. Adicione as juntas clicando nele.']
    vol = STATE['base'].volume()
    first, _ = PL.plan(an, clearance)
    n_chain = max(1, sum(1 for q in first if q['type'] == 'corrente'))
    budget = 0.4 * (100.0 - target) / 100.0 * vol / n_chain
    J, notes = PL.plan(an, clearance, budget=budget)
    return [_clean(j) for j in J], notes


def _jsonable(j):
    out = {}
    for k, v in j.items():
        if k.startswith('_') or k == 'zona':
            continue
        if isinstance(v, (np.floating, np.integer)):
            v = float(v)
        try:
            json.dumps(v)
        except TypeError:
            continue
        out[k] = v
    return out


def _auto_prepare(m):
    """Every model goes in ready to print: centred, on the bed, and in millimetres
    (files without units come out tiny: they are scaled to 120 mm)."""
    bb = m.bounding_box()
    size = max(bb[3] - bb[0], bb[4] - bb[1])
    # modelo leve fica exatamente como no arquivo; modelo denso perde só triângulos repetidos
    opts = dict(center=True, flatten_mm=0.3, simplify_mm=0.005 if m.num_tri() > AUTO_SIMP_MIN else 0)
    if size < 5.0:
        opts['length_mm'] = _unitless_length(bb)
    return E.prepare(m, opts)


AUTO_SIMP_MIN = 250000        # até aqui o modelo abre sem simplificar nada
QUAL_PERGUNTA = 500000        # acima disso o app pergunta a qualidade ao abrir
QUAL_NIVEIS = (('manter', 0.005), ('media', 0.02), ('baixa', 0.05))


def _quality_options(b):
    """Modelo muito denso: as 3 qualidades com o número de triângulos de cada uma, para o usuário
    escolher. None quando o modelo é leve (nada a perguntar)."""
    n = int(b.num_tri())
    if n <= QUAL_PERGUNTA:
        return None
    ops = []
    for nivel, tol in QUAL_NIVEIS:
        try:
            k = n if nivel == 'manter' else int(b.as_original().simplify(tol).num_tri())
        except Exception:
            continue
        ops.append(dict(nivel=nivel, desvio_mm=tol, triangulos=k))
    return dict(triangulos=n, opcoes=ops)


def _unitless_length(bb):
    """Files without units become 120 mm on their LONGEST side: a standing figure is 120 mm
    tall (prepare() takes the longest horizontal side, so it is converted here)."""
    hmax = max(bb[3] - bb[0], bb[4] - bb[1])
    h = bb[5] - bb[2]
    return 120.0 * hmax / max(hmax, h, 1e-9)
LOCK = threading.Lock()


def _json(h, obj, code=200):
    data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
    h.send_response(code)
    h.send_header('Content-Type', 'application/json; charset=utf-8')
    h.send_header('Content-Length', str(len(data)))
    h.send_header('Cache-Control', 'no-store')
    h.end_headers()
    h.wfile.write(data)


def _bin(h, data, name='modelo.stl'):
    h.send_response(200)
    h.send_header('Content-Type', 'application/octet-stream')
    h.send_header('Content-Disposition', f'attachment; filename="{name}"')
    h.send_header('Content-Length', str(len(data)))
    h.send_header('Cache-Control', 'no-store')
    h.end_headers()
    h.wfile.write(data)


EXPORT_EXT = ('.3mf', '.stl', '.obj', '.mtl', '.txt', '.flexiproj')


def _list_files(folder):
    """Every file of an export, relative to its folder (3MF first, then STL, then the rest)."""
    out = []
    for root, _, fs in os.walk(folder):
        for f in fs:
            if f.lower().endswith(EXPORT_EXT):
                full = os.path.join(root, f)
                out.append(dict(rel=os.path.relpath(full, folder).replace(os.sep, '/'), bytes=os.path.getsize(full)))
    order = {'.3mf': 0, '.stl': 1}
    out.sort(key=lambda d: (order.get(os.path.splitext(d['rel'])[1].lower(), 2), d['rel'].count('/'), d['rel']))
    return out


def _printer(body=None):
    """The printer chosen in the interface (saved in the config)."""
    cfg = load_config()
    pid = (body or {}).get('impressora') or cfg.get('impressora') or PRN.DEFAULT
    return PRN.get(pid, (body or {}).get('impressora_custom') or cfg.get('impressora_custom'))


def _info(m):
    bb = m.bounding_box()
    return dict(triangulos=m.num_tri(), volume=round(m.volume(), 1),
                tamanho=[round(bb[3] - bb[0], 2), round(bb[4] - bb[1], 2), round(bb[5] - bb[2], 2)],
                minimo=[round(v, 2) for v in bb[:3]])


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=WEB, **k)

    def log_message(self, fmt, *args):
        pass

    def end_headers(self):
        # a new version must never show files or settings of the previous one
        if not self.path.startswith('/api/'):
            self.send_header('Cache-Control', 'no-store, must-revalidate')
        super().end_headers()

    def _body(self):
        n = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(n) if n else b''

    # ------------------------------------------------------------------ GET
    def do_GET(self):
        u = urlparse(self.path)
        p = u.path
        q = parse_qs(u.query)
        try:
            if p.startswith('/api/mcp/'):
                return self._mcp_get(p, q)
            if p == '/api/ping':
                # cada janela avisa que está aberta (a cada 5 s): o motor só fecha quando não sobra nenhuma
                JANELAS[(q.get('j') or ['?'])[0]] = time.time()
                return _json(self, dict(ok=True, versao=VERSION))
            if p == '/api/status':
                return _json(self, dict(busy=STATE['busy'], progress=STATE['progress'], versao=VERSION, sistema=sys.platform,
                                        loaded=STATE['base'] is not None, name=STATE['name']))
            if p == '/api/base.stl':
                if STATE['base'] is None:
                    return _json(self, dict(error='Nenhum modelo carregado.'), 400)
                return _bin(self, E.write_stl(STATE['base']), 'base.stl')
            if p == '/api/paint':
                pnt = _paint_ok()
                return _json(self, dict(n=STATE['base'].num_tri() if STATE['base'] is not None else 0,
                                        paleta=STATE.get('palette'),
                                        pintura=base64.b64encode(pnt.tobytes()).decode('ascii') if pnt is not None else None))
            if p == '/api/recentes':
                return _json(self, dict(recentes=recent_list()))
            if p == '/api/config':
                cfg = load_config()
                return _json(self, dict(pasta_saida=out_dir(), padrao=OUT_DIR, projeto=STATE.get('proj_path'),
                                        tema=cfg.get('tema', 'auto'), impressora=_printer()['id'], impressora_custom=cfg.get('impressora_custom'),
                                        impressoras=PRN.listing()))
            if p == '/api/cutters':
                lib = ED.library()
                return _json(self, dict(cutters=[dict(id=k, nome=v['nome'], origem=v.get('origem'), placa=v['placa'],
                                                      folga=v.get('folga'), nucleo_meio=v['nucleo_meio'],
                                                      uso=v.get('uso', ''), autor=v.get('autor', ''),
                                                      mecanismo=v.get('mecanismo', 'elos'))
                                                 for k, v in lib.items()]))
            if p == '/api/cutter.stl':
                return _bin(self, ED.cutter_stl_bytes(q.get('id', [ED.PADRAO])[0]), 'peca_de_corte.stl')
            if p == '/api/preview.stl':
                m = STATE['preview'].get(q.get('p', ['a'])[0])
                if m is None:
                    return _json(self, dict(error='Sem prévia.'), 404)
                return _bin(self, E.write_stl(m), 'previa.stl')
            if p == '/api/piece.stl':
                i = int(q.get('i', ['0'])[0])
                return _bin(self, E.write_stl(STATE['export']['pieces'][i]), f'peca_{i}.stl')
            if p == '/api/export.stl':
                return _bin(self, E.write_stl(STATE['export']['pieces']), f"{STATE['name']}_flexi.stl")
            if p == '/api/export/file':
                ex = STATE.get('export') or {}
                folder = ex.get('pasta')
                rel = q.get('rel', [''])[0]
                full = os.path.realpath(os.path.join(folder or '', rel))
                if not folder or not full.startswith(os.path.realpath(folder) + os.sep) or not os.path.isfile(full):
                    return _json(self, dict(error='Arquivo não encontrado.'), 404)
                return _bin(self, open(full, 'rb').read(), os.path.basename(full))
            if p == '/api/export.zip':
                import zipfile, io as _io
                ex = STATE.get('export') or {}
                folder = ex.get('pasta')
                if not folder or not os.path.isdir(folder):
                    return _json(self, dict(error='Exporte primeiro.'), 404)
                buf = _io.BytesIO()
                with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
                    for d in _list_files(folder):
                        z.write(os.path.join(folder, d['rel']), d['rel'])
                return _bin(self, buf.getvalue(), os.path.basename(folder) + '.zip')
            if p == '/api/export.3mf':
                ex = STATE['export']
                return _bin(self, ex['data3mf'], ex['nome3mf'])
            if p.startswith('/api/split/'):
                return self._split_get(p, q)
            if p.startswith('/api/free/'):
                return self._free_get(p, q)
            if p.startswith('/api/pieces/'):
                return self._pieces_get(p, q)
            if p == '/api/piece_paint':
                # filament number of each triangle of piece i (same order as /api/piece.stl)
                i = int(q.get('i', ['0'])[0])
                ex = STATE['export']
                return _json(self, dict(pintura=base64.b64encode(np.asarray(ex['paint'][i], np.uint8).tobytes()).decode('ascii'),
                                        paleta=ex.get('palette')))
        except Exception as ex:
            traceback.print_exc()
            return _json(self, dict(error=str(ex)), 500)
        return super().do_GET()

    def _open_project(self, body):
        data, joints, clr, nome = ED.open_project(body)
        m = E.read_stl(data)
        joints, avisos_juntas = ED.ajustar_antigas(m, joints)
        paint = None
        if body.get('pintura'):
            fp = np.frombuffer(base64.b64decode(body['pintura']), dtype=np.uint8)
            ft = PT.stl_tris(data)
            if len(fp) == len(ft):
                paint = PT.transfer(ft, fp, PT.tri_array(m))   # file order -> this model's order
        livres = body.get('livres')
        if livres and isinstance(livres.get('cortes'), list):
            # área marcada do Corte livre: mesma troca de ordem dos triângulos que a pintura
            ft_ = None
            for c in livres['cortes']:
                if not c.get('mascara') or c.get('peca'):
                    continue                      # área marcada numa peça: é da malha da peça, não do modelo
                if ft_ is None:
                    ft_ = PT.stl_tris(data)
                mk = FC.decode_mask(c['mascara'], len(ft_))
                if mk is None:
                    c.pop('mascara', None)
                    continue
                nm = PT.transfer(ft_, mk.astype(np.uint8) + 1, PT.tri_array(m)) > 1
                c['mascara'], c['n'] = FC.encode_mask(nm), int(len(nm))
        with LOCK:
            STATE.update(original=m, base=m, export=None, preview={}, name=nome, paint=paint, tex=None,
                         palette=body.get('paleta') or STATE.get('palette'))
        threading.Thread(target=_analyze, daemon=True).start()
        return dict(ok=True, info=_info(m), joints=joints, clearance=clr, nome=nome, avisos_juntas=avisos_juntas,
                    prepare=body.get('prepare'), paleta=body.get('paleta'), separar=body.get('separar'),
                    livres=livres)

    def _busy(self, label):
        if STATE['busy']:
            _json(self, dict(error='Já existe um cálculo em andamento.'), 409)
            return False
        STATE['busy'] = True
        STATE['progress'] = label
        return True

    def _done(self):
        STATE['busy'] = False
        STATE['progress'] = ''

    def _load_model(self, data, name):
        """Model bytes (STL, or GLB / OBJ / .zip with colours) -> the open model."""
        T = C = None
        tlog = []
        if TX.is_colored_file(name):
            # GLB / glTF / OBJ (+ texture, or a .zip with them): colours become the painting
            T, C, tlog = TX.read_colored(data, name)
            data = TX.to_stl_bytes(T)
        m = E.read_stl(data)          # sem reduzir: a única simplificação é a do preparo (0,005 mm, no tamanho real)
        b, log = _auto_prepare(m)
        log = tlog + list(E.LAST_REPAIR) + list(log)
        with LOCK:
            STATE.update(original=m, base=b, result=None, report=None, export=None, preview={},
                         name=os.path.splitext(os.path.basename(name))[0] or 'modelo',
                         paint=None, proj_path=None, tex=None)
        tex = None
        if C is not None:
            STATE['tex'] = dict(T=PT.tri_array(b), rgb=TX.transfer_rgb(T, C, PT.tri_array(b)))
            tex = self._tex_paint(None, 2.0)
        threading.Thread(target=_analyze, daemon=True).start()
        return dict(ok=True, info=_info(b), log=log, textura=tex, qualidade=_quality_options(b), simplificar_mm=0.005 if m.num_tri() > AUTO_SIMP_MIN else 0)

    # ------------------------------------------------------------------ POST
    def do_POST(self):
        u = urlparse(self.path)
        p = u.path
        q = parse_qs(u.query)
        try:
            if p.startswith('/api/mcp/'):
                return self._mcp_post(p, json.loads(self._body() or b'{}'))

            if p == '/api/download/prepare':
                # janela do app: o WebKit do Mac não grava por cima de um arquivo que já existe (o "Substituir"
                # do diálogo não vale). O app pede o caminho e o servidor grava o arquivo, substituindo.
                import urllib.request, re as _re, uuid
                url = (json.loads(self._body() or b'{}').get('url') or '')
                if not url.startswith('/api/') or url.startswith('/api/download/'):
                    return _json(self, dict(error='Endereço inválido.'), 400)
                op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                port_ = self.server.server_address[1]          # a porta em que este motor está (8765 ocupada: o app sobe em outra)
                with op.open(f'http://127.0.0.1:{port_}{url}', timeout=600) as rsp:
                    data = rsp.read()
                    cd = rsp.headers.get('Content-Disposition') or ''
                m_ = _re.search(r'filename="([^"]+)"', cd)
                tok = uuid.uuid4().hex
                STATE['download'] = dict(token=tok, data=data, nome=m_.group(1) if m_ else 'arquivo')
                return _json(self, dict(ok=True, token=tok, nome=STATE['download']['nome']))

            if p == '/api/download/save':
                b_ = json.loads(self._body() or b'{}')
                dl = STATE.get('download') or {}
                path = b_.get('path') or ''
                if not dl or b_.get('token') != dl.get('token') or not os.path.isabs(path):
                    return _json(self, dict(error='Baixe de novo.'), 400)
                tmp = path + '.parcial'
                with open(tmp, 'wb') as f_:
                    f_.write(dl['data'])
                os.replace(tmp, path)                  # substitui o arquivo que já existia
                STATE.pop('download', None)
                return _json(self, dict(ok=True, path=path))

            if p == '/api/lang':
                import i18n
                i18n.set_lang((json.loads(self._body() or b'{}').get('lang') or 'pt'))
                return _json(self, dict(ok=True, lang=i18n.lang()))

            if p == '/api/encerrar':
                # uma versão nova do app pediu para assumir (atualização com o app aberto)
                _json(self, dict(ok=True))
                threading.Timer(0.3, lambda: os._exit(0)).start()
                return

            if p == '/api/load':
                from urllib.parse import unquote
                name = unquote(q.get('name', ['modelo'])[0])
                return _json(self, self._load_model(self._body(), name))

            if p == '/api/load_path':
                path = os.path.abspath(os.path.expanduser(json.loads(self._body() or b'{}').get('path', '')))
                if not os.path.isfile(path):
                    return _json(self, dict(error='Arquivo não encontrado: ' + path), 400)
                with open(path, 'rb') as f:
                    r = self._load_model(f.read(), os.path.basename(path))
                add_recent(path, 'modelo')
                r['path'] = path
                return _json(self, r)

            if p == '/api/recentes/limpar':
                cfg = load_config()
                cfg['recentes'] = []
                save_config(cfg)
                return _json(self, dict(ok=True))


            if p == '/api/prepare':
                if STATE['original'] is None:
                    return _json(self, dict(error='Carregue um STL primeiro.'), 400)
                opts = json.loads(self._body() or b'{}')
                bb = STATE['original'].bounding_box()
                if not float(opts.get('length_mm') or 0) and max(bb[3] - bb[0], bb[4] - bb[1]) < 5.0:
                    opts['length_mm'] = _unitless_length(bb)
                m, log = E.prepare(STATE['original'], opts)
                old_p, old_b = _paint_ok(), STATE['base']
                newp = None
                if old_p is not None:
                    newp = PT.transfer_scaled(PT.tri_array(old_b), old_p, PT.tri_array(m))
                    log = list(log) + ['cores levadas para o modelo ajustado (confira as bordas)']
                # o modelo mudou de tamanho ou de lugar: os cortes (linhas, planos, áreas marcadas) vão junto
                ob, nb_ = np.array(old_b.bounding_box()), np.array(m.bounding_box())
                oe, ne = ob[3:] - ob[:3], nb_[3:] - nb_[:3]
                sc = float(max(ne[0], ne[1]) / max(oe[0], oe[1], 1e-9))
                oc = np.array([(ob[0] + ob[3]) / 2, (ob[1] + ob[4]) / 2, ob[5]])
                nc = np.array([(nb_[0] + nb_[3]) / 2, (nb_[1] + nb_[4]) / 2, nb_[5]])
                mapa = dict(s=sc, t=(nc - sc * oc).tolist())
                masks = []
                for mk_ in (opts.get('mascaras') or []):
                    try:
                        mk = FC.decode_mask(mk_['mascara'], old_b.num_tri())
                        if mk is None:
                            continue
                        nm = PT.transfer_scaled(PT.tri_array(old_b), mk.astype(np.uint8) + 1, PT.tri_array(m)) > 1
                        masks.append(dict(k=mk_.get('k'), mascara=FC.encode_mask(nm), n=int(len(nm))))
                    except Exception:
                        traceback.print_exc()
                with LOCK:
                    STATE.update(base=m, result=None, report=None, export=None, preview={}, paint=newp, split=None)
                threading.Thread(target=_analyze, daemon=True).start()
                return _json(self, dict(ok=True, info=_info(m), log=log, mapa=mapa, mascaras=masks))

            if p == '/api/cutters/import':
                from urllib.parse import unquote
                cid, meta = ED.import_cutter(self._body(), unquote(q.get('name', [''])[0]))
                ok = meta.get('partes_teste') == 2 and all(g >= 1 for g in meta.get('aneis_fechados', []))
                msg = ('Peça de corte importada.' if ok else
                       'Importada, mas o teste num bloco não deu duas peças com elos fechados: confira se é mesmo uma peça de corte de junta.')
                return _json(self, dict(ok=True, id=cid, meta=meta, msg=msg))

            body = json.loads(self._body() or b'{}')
            S = STATE['base']
            need_model = p.startswith('/api/editor/') and p != '/api/editor/coupon'
            if need_model and S is None:
                return _json(self, dict(error='Carregue um STL primeiro.'), 400)

            if p == '/api/editor/suggest':
                jp = ED.suggest_at(S, float(body['x']), float(body['y']),
                                   None if body.get('angle') is None else float(body['angle']),
                                   tipo=ED.canon(body.get('tipo') or ED.PADRAO),
                                   cadeado=body.get('cadeado'),
                                   others=[o for o in body.get('others', []) if o])
                return _json(self, dict(ok=True, joint=jp))

            if p == '/api/editor/fit':
                jp = body['joint']
                s_, dz = ED.fit_scale(S, jp, float(body.get('pele', ED.DEFAULT_WALL)))
                if s_ is None:
                    return _json(self, dict(ok=False, msg='Os elos não cabem aqui com essa pele: mova a junta ou use outra peça de corte.'))
                jp = dict(jp, escala=[round(v, 3) for v in s_])
                jp['pos'] = [jp['pos'][0], jp['pos'][1], round(jp['pos'][2] + dz, 3)]
                jp['limites'] = ED.section_limits(S, jp)
                return _json(self, dict(ok=True, joint=jp))

            if p == '/api/editor/suggest_all':
                if STATE['an'] is None:
                    return _json(self, dict(ok=False, joints=[], msg='Não reconheci corpo e patas neste modelo: adicione as juntas clicando nele.'))
                if not self._busy('sugerindo juntas'):
                    return
                try:
                    J = ED.suggest_all(STATE['an'], S, ED.canon(body.get('tipo') or ED.PADRAO), float(body.get('clearance', 0.4)))
                finally:
                    self._done()
                return _json(self, dict(ok=True, joints=J))

            if p == '/api/editor/check':
                jp = body['joint']
                clr = float(jp.get('folga') or body.get('clearance') or 0.4)
                others = [(k, o) for k, o in enumerate(body.get('others', [])) if o is not None]
                if 'isl' not in STATE or STATE.get('isl_key') != id(S):
                    STATE['isl'] = E.islands(S)
                    STATE['isl_key'] = id(S)
                with CHECK_LOCK:
                    r, A, B, Cw = ED.check_joint(S, jp, clr, others, STATE['isl'])
                r['luz'] = ED.light(r['checks'])
                STATE['preview'] = dict(a=A, b=B, c=Cw)
                r['tem'] = dict(a=A is not None, b=B is not None, c=True)
                return _json(self, dict(ok=True, **r))

            if p == '/api/editor/export':
                # one export for both tools: joints only, separated parts only, or both
                joints = body.get('joints', [])
                sep = body.get('separar') or None
                use_sep = bool(sep and any(c.get('separar', True) for c in (sep.get('configs') or [])))
                livres = [c for c in (body.get('livres') or []) if c.get('linhas') or c.get('mascara') or c.get('plano')]
                STATE['conectores'] = body.get('conectores') or []
                if not joints and not use_sep and not livres:
                    return _json(self, dict(error='Nada para exportar: posicione juntas (aba Juntas), marque áreas para separar '
                                                  'ou desenhe um corte livre (aba Cortes).'), 400)
                if use_sep and (self._split_key() is None or sep.get('chave') != self._split_key()):
                    return _json(self, dict(error='A pintura mudou desde que as áreas foram escolhidas: abra "Separar por cor" de novo.'), 409)
                if not self._busy('iniciando'):
                    return
                try:
                    stamp = time.strftime('%Y%m%d_%H%M%S')
                    folder = os.path.join(out_dir(), f"{STATE['name']}_{stamp}")
                    prog = lambda t: STATE.__setitem__('progress', t)
                    if not use_sep and not livres:
                        R = ED.export(S, E.write_stl(S), joints, float(body.get('clearance', 0.4)), folder,
                                      STATE['name'], force=bool(body.get('force')), progress=prog,
                                      paint=_paint_ok(), palette=STATE.get('palette'))
                        if R.get('ok'):
                            STATE['export'] = dict(pieces=R['_pieces'], paint=R['_piece_paint'], data3mf=R['_3mf'],
                                                   nome3mf=R['arquivo3mf'], pasta=folder,
                                                   palette=list(STATE.get('palette') or []))
                            # plates of the chosen printer (extra files; the joint export itself is unchanged)
                            safe = ''.join(c if c.isalnum() or c in '-_' else '_' for c in STATE['name']) or 'modelo'
                            pnt = [np.asarray(c, np.uint8) for c in R['_piece_paint']] if R.get('_piece_paint') else \
                                [np.ones(m.num_tri(), np.uint8) for m in R['_pieces']]
                            item = dict(nome='Corpo articulado', base=1,
                                        T=np.concatenate([SPL.tri_array(m) for m in R['_pieces']]), paint=np.concatenate(pnt))
                            _, R['placas'], R['avisos_placa'], packed = SPL.write_plates([item], folder, safe,
                                                                                         list(STATE.get('palette') or []), _printer(body))
                            Mm = SPL.rigid(item['T'], packed[0][0][1]).tolist()
                            R['mesa'] = dict(pecas=[Mm] * len(R['_pieces']), placas=len(packed), impressora=_printer(body))
                            R['impressora'] = _printer(body)['nome']
                    else:
                        R = self._export_with_parts(S, joints, sep if use_sep else {'configs': []}, body, folder, prog, livres)
                finally:
                    self._done()
                out = {k: v for k, v in R.items() if not k.startswith('_') and k != 'pieces'}
                if R.get('ok'):
                    try:
                        out['projeto'] = _write_export_project(S, folder, body)
                    except Exception as ex_:
                        out.setdefault('avisos', []).append('Projeto não gravado na pasta da exportação: ' + str(ex_))
                    out['arquivos'] = _list_files(folder)
                return _json(self, out)

            if p == '/api/editor/coupon':
                jp = body['joint']
                folgas = body.get('folgas') or [0.20, 0.25, 0.30, 0.35, 0.40, 0.50]
                if not self._busy('cupom'):
                    return
                try:
                    P, rep = ED.make_coupon(jp, [float(v) for v in folgas],
                                            progress=lambda t: STATE.__setitem__('progress', t))
                finally:
                    self._done()
                stamp = time.strftime('%Y%m%d_%H%M%S')
                folder = os.path.join(out_dir(), f'cupom_calibracao_{stamp}')
                os.makedirs(folder, exist_ok=True)
                with open(os.path.join(folder, 'cupom_calibracao.stl'), 'wb') as f:
                    f.write(E.write_stl(P))
                lines = ['Cupom de calibração EFC3D ' + VERSION, '',
                         f"Peça de corte: {rep['peca']}  escala {rep['escala']}", '',
                         'Imprima sem suporte, sem redimensionar. Cada amostra tem furinhos em cima do bloco:',
                         'conte os furinhos para saber qual amostra é. Depois de imprimir, gire cada pata.', '',
                         'Furinhos | Folga para digitar no programa | Folga real | Verificação']
                for a_ in rep['amostras']:
                    fr = f"{a_['folga_real']:.2f} mm" if a_.get('folga_real') is not None else 'não coube'
                    lines.append(f"{a_['furinhos']:>8} | {a_['folga_programa']:.2f} mm{'':<23}| {fr:<10} | {'ok' if a_.get('presa') else 'atenção'}")
                lines += ['', 'Escolha a MENOR folga em que a pata gira sem grudar e não fica frouxa.',
                          'Digite esse valor no campo "Folga" antes de exportar o seu modelo.']
                import i18n
                with open(os.path.join(folder, 'LEIA.txt'), 'w', encoding='utf-8') as f:
                    f.write(i18n.tr_text('\n'.join(lines)) + '\n')
                return _json(self, dict(ok=True, folder=folder, report=rep))

            if p == '/api/project/save':
                if S is None:
                    return _json(self, dict(error='Carregue um STL primeiro.'), 400)
                path = (body.get('path') or '').strip()
                if not path and STATE.get('proj_path') and not body.get('como'):
                    path = STATE['proj_path']                 # Salvar: overwrite the open project
                if not path:
                    stamp = time.strftime('%Y%m%d_%H%M%S')
                    folder = os.path.join(out_dir(), 'projetos')
                    path = os.path.join(folder, f"{STATE['name']}_{stamp}.flexiproj")
                path = os.path.expanduser(path)
                if not path.lower().endswith('.flexiproj'):
                    path += '.flexiproj'
                os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
                d = _project_full(S, body.get('joints', []), body.get('clearance', 0.4), body.get('prepare'), body.get('separar'), body.get('livres'))
                tmp = path + '.tmp'
                with open(tmp, 'w', encoding='utf-8') as f:
                    json.dump(d, f)
                os.replace(tmp, path)
                STATE['proj_path'] = path
                add_recent(path, 'projeto')
                return _json(self, dict(ok=True, path=path))

            if p == '/api/project/open_path':
                path = os.path.expanduser(body.get('path', ''))
                body = json.load(open(path, encoding='utf-8'))
                r = self._open_project(body)
                STATE['proj_path'] = path
                add_recent(path, 'projeto')
                r['path'] = path
                return _json(self, r)

            if p == '/api/project/open':
                r = self._open_project(body)
                STATE['proj_path'] = None
                return _json(self, r)

            if p == '/api/paint':
                raw = base64.b64decode(body.get('pintura') or '')
                if body.get('paleta'):
                    STATE['palette'] = [str(c) for c in body['paleta']][:16]
                if raw:
                    arr = np.frombuffer(raw, dtype=np.uint8).copy()
                    if S is None or len(arr) != S.num_tri():
                        return _json(self, dict(error='A pintura não corresponde ao modelo aberto. Recarregue o modelo.'), 400)
                    STATE['paint'] = arr
                return _json(self, dict(ok=True))

            if p == '/api/paint/bands':
                if S is None:
                    return _json(self, dict(error='Carregue um STL primeiro.'), 400)
                z0, z1 = sorted([float(body['z0']), float(body['z1'])])
                cor = max(1, min(16, int(body.get('cor', 2))))
                cur = _paint_ok()
                if cur is None:
                    cur = np.ones(S.num_tri(), np.uint8)
                mudou = False
                if body.get('exato', True):
                    S2 = PT.refine_bands(S, [z0, z1])
                    if S2.num_tri() != S.num_tri():
                        cur = PT.transfer(PT.tri_array(S), cur, PT.tri_array(S2))
                        with LOCK:
                            STATE.update(base=S2, preview={}, export=None)
                        S = S2
                        mudou = True
                t = PT.tri_array(S)
                zc = t[:, :, 2].mean(1)
                cur = cur.copy()
                cur[(zc >= z0) & (zc <= z1)] = cor
                STATE['paint'] = cur
                return _json(self, dict(ok=True, mudou_malha=mudou, triangulos=S.num_tri(),
                                        pintados=int(((zc >= z0) & (zc <= z1)).sum())))

            if p == '/api/config':
                cfg = load_config()
                if body.get('tema') in ('light', 'dark', 'auto'):
                    cfg['tema'] = body['tema']
                    save_config(cfg)
                if 'pasta_saida' in body:
                    d = os.path.expanduser(str(body['pasta_saida']).strip())
                    if d:
                        os.makedirs(d, exist_ok=True)
                        test = os.path.join(d, '.teste_gravacao')
                        open(test, 'w').write('ok')
                        os.remove(test)
                        cfg['pasta_saida'] = d
                    else:
                        cfg.pop('pasta_saida', None)       # back to the default
                if 'impressora' in body:
                    cfg['impressora'] = str(body['impressora'])
                    if body.get('impressora_custom'):
                        cfg['impressora_custom'] = body['impressora_custom']
                if 'pasta_saida' in body or 'impressora' in body:
                    save_config(cfg)
                return _json(self, dict(ok=True, pasta_saida=out_dir(), padrao=OUT_DIR, projeto=STATE.get('proj_path')))

            if p == '/api/reveal':
                path = os.path.expanduser(body.get('path') or out_dir())
                if sys.platform == 'darwin' and os.path.exists(path):
                    subprocess.Popen(['open', path] if os.path.isdir(path) else ['open', '-R', path])
                    return _json(self, dict(ok=True))
                if sys.platform == 'win32' and os.path.exists(path):
                    if os.path.isdir(path):
                        os.startfile(path)
                    else:
                        subprocess.Popen(['explorer', '/select,', os.path.normpath(path)])
                    return _json(self, dict(ok=True))
                return _json(self, dict(ok=False, path=path))

            if p == '/api/dialog':
                kind = body.get('tipo', 'pasta')
                start = body.get('inicio') or (os.path.dirname(STATE['proj_path']) if STATE.get('proj_path') else out_dir())
                r = mac_dialog(kind, body.get('nome', ''), start)
                if r is None:
                    return _json(self, dict(ok=False, indisponivel=True))
                return _json(self, dict(ok=bool(r), path=r, cancelado=not r))

            if p.startswith('/api/split/'):
                return self._split_post(p, body)

            if p.startswith('/api/free/'):
                return self._free_post(p, body)

            if p.startswith('/api/pieces/'):
                return self._pieces_post(p, body)

            if p.startswith('/api/conectores/'):
                return self._cn_post(p, body)

            if p == '/api/texture/paint':
                if not STATE.get('tex'):
                    return _json(self, dict(error='Este modelo não veio com textura (abra um .glb, .gltf, .obj ou .zip).'), 400)
                k = body.get('cores')
                r = self._tex_paint(None if not k else int(k), float(body.get('limpar', 2.0)))
                return _json(self, dict(ok=True, **r))

        except Exception as ex:
            traceback.print_exc()
            STATE['busy'] = False
            return _json(self, dict(error=str(ex)), 500)
        return _json(self, dict(error='rota desconhecida'), 404)

    # ------------------------------------------------------------------ separate parts (module)
    def _tex_paint(self, k, min_area):
        """Painting from the colours of the texture: k filaments (None = automatic), specks
        smaller than min_area mm2 cleaned."""
        S, tx = STATE['base'], STATE.get('tex')
        if S is None or not tx:
            return None
        Tb = PT.tri_array(S)
        if len(tx['T']) != len(Tb) or not np.allclose(tx['T'][:50], Tb[:50]):
            tx = dict(T=Tb, rgb=TX.transfer_rgb(tx['T'], tx['rgb'], Tb))       # the model changed since
            STATE['tex'] = tx
        area = np.linalg.norm(np.cross(Tb[:, 1] - Tb[:, 0], Tb[:, 2] - Tb[:, 0]), axis=1) / 2
        lab, pal, k = TX.cluster(tx['rgb'], area, k)
        _, _, nb = SPL._topology(S)
        lab = TX.clean(lab, nb, area, float(min_area))
        STATE['paint'] = (lab + 1).astype(np.uint8)
        STATE['palette'] = pal
        return dict(cores=int(k), paleta=pal, limpar=float(min_area))

    def _split_key(self):
        S, pnt = STATE['base'], _paint_ok()
        if S is None or pnt is None:
            return None
        return f'{id(S)}:{hash(pnt.tobytes())}'

    def _snap_key(self, cfg):
        return json.dumps([self._split_key() or f"{id(STATE['base'])}:sem_pintura", cfg or []], sort_keys=True)

    def _split_out(self, cfg, prog=None, livres=None):
        """Cut result for these options (cached: the preview and the export reuse it). Free
        cuts (Corte livre) come on top of the colour split."""
        sp = STATE.get('split') or {}
        key = self._split_key() or f"{id(STATE['base'])}:sem_pintura"
        livres = CN.normalizar(livres)                  # conector manual: no motor, só a navalha
        ck = json.dumps([cfg, livres or []], sort_keys=True)
        if not (sp.get('out') is not None and sp.get('cfg') == ck and sp.get('key') == key):
            pnt = _paint_ok()
            if pnt is None:
                pnt = np.ones(STATE['base'].num_tri(), np.uint8)
            out = SPL.run(STATE['base'], pnt, cfg, progress=prog)
            base_out = out
            if livres:
                out = FC.apply(out, livres, STATE['base'], progress=prog, snap_key=self._snap_key(cfg))
            if sp.get('key') != key:
                sp = dict(key=key)
            sp.update(out=out, cfg=ck, key=key, base_out=base_out, livres=livres, juntas=None, cn_key=None, cn_out=None)
            STATE['split'] = sp
        if not CN.tem_manual(livres):
            return sp['out']
        # conectores manuais (módulo à parte): as peças cortadas ficam guardadas; mudar um conector só
        # refaz pino e furo nas duas peças da junta
        cn = STATE.get('conectores') or []
        if not cn:
            return sp['out']
        kk = json.dumps(cn, sort_keys=True)
        if sp.get('cn_key') != kk or sp.get('cn_out') is None:
            if prog:
                prog('conectores')
            sp['cn_out'] = CN.aplicar(sp['out'], self._juntas(sp), cn)
            sp['cn_key'] = kk
        return sp['cn_out']

    def _juntas(self, sp):
        if sp.get('juntas') is None:
            sp['juntas'] = CN.juntas(sp['out'], sp.get('livres'))
        return sp['juntas']

    def _cn_post(self, p, body):
        sp = STATE.get('split') or {}
        if sp.get('out') is None or not CN.tem_manual(sp.get('livres')):
            return _json(self, dict(error='Faça a prévia das peças com um corte de conector manual primeiro.'), 404)
        js = self._juntas(sp)
        if p == '/api/conectores/juntas':
            return _json(self, dict(ok=True, juntas=CN.publico(js)))
        if p == '/api/conectores/conferir':
            res, _ = CN.conferir(sp['out'], js, body.get('conectores') or [])
            return _json(self, dict(ok=True, conectores=res))
        return _json(self, dict(error='rota desconhecida'), 404)

    def _export_with_parts(self, S, joints, sep, body, folder, prog, livres=None):
        t0 = time.time()
        prog('separando as peças')
        out = self._split_out(sep.get('configs') or [], prog, livres)
        res = SPL.summary(out)
        res['livres'] = FC.summary(out)
        safe = ''.join(c if c.isalnum() or c in '-_' else '_' for c in STATE['name']) or 'modelo'
        pal = list(STATE.get('palette') or [])
        ok_parts = [r for r in res['regioes'] if r['ok']] + [r for r in res['livres'] if r['ok']]
        if not ok_parts and not joints:
            return dict(ok=False, cortes=res, msg='Nenhuma área foi cortada: veja os itens vermelhos.')
        if not joints:
            ex = SPL.export(out, folder, safe, pal, printer=_printer(body))
            pieces = [p['mesh'] for p in out['pieces']]
            paints = [p['paint'] for p in out['pieces']]
            mesa = dict(pecas=[ex['mesa'].get(k) for k in range(len(pieces))], placas=ex['n_placas'], impressora=_printer(body))
            STATE['export'] = dict(pieces=pieces, paint=paints, data3mf=ex['data3mf'], nome3mf=ex['arquivo3mf'],
                                   pasta=folder, palette=pal)
            return dict(ok=True, pasta=folder, pecas=len(pieces), arquivo3mf=ex['arquivo3mf'], pintado=True,
                        cortes=res, conferido3mf=ex['ok'], modo='cortes', segundos=round(time.time() - t0, 1),
                        placas=ex['placas'], avisos_placa=ex['avisos_placa'], impressora=_printer(body)['nome'], mesa=mesa,
                        impressao=ex.get('impressao'), malha_stl=ex.get('malha'))
        # both: each joint goes on the part it sits in (the body with its pockets, a loose part
        # such as a hand, or even a separated limb); the other parts come next to them
        clr = float(body.get('clearance', 0.4))
        groups, conflitos = SPL.assign_joints(out, joints, S, clr)
        multi = len(groups) > 1
        juntas_all = [None] * len(joints)
        verm_all, flexi, Rs = [], {}, []
        for n_, (pi, idxs) in enumerate(sorted(groups.items())):
            part = out['pieces'][pi]
            sub = os.path.join(folder, f'articulado_{n_ + 1}') if multi else folder
            prog(f'juntas da parte {n_ + 1} de {len(groups)}' if multi else 'juntas')
            R = ED.export(part['mesh'], E.write_stl(part['mesh']), [joints[k] for k in idxs], clr, sub,
                          STATE['name'], force=bool(body.get('force')), progress=prog,
                          paint=np.asarray(part['paint'], np.uint8), palette=STATE.get('palette'))
            for j_, k in enumerate(idxs):
                if R.get('juntas') and j_ < len(R['juntas']):
                    juntas_all[k] = R['juntas'][j_]
            verm_all += [idxs[v] for v in R.get('vermelhas', [])]
            Rs.append((pi, R))
            if not R.get('ok'):
                R = dict(R, juntas=[q or dict(luz='nada', checks=[]) for q in juntas_all],
                         vermelhas=sorted(set(verm_all)), cortes=res, conflitos=conflitos)
                return R
            flexi[pi] = [(SPL.tri_array(m), np.asarray(c, np.uint8)) for m, c in zip(R['_pieces'], R['_piece_paint'])]
        ex = SPL.export(out, folder, safe, pal, flexi=flexi, stl_sub='pecas_por_cor', printer=_printer(body))
        pieces, paints, mats = [], [], []
        for pi, R in Rs:
            pieces += list(R['_pieces'])
            paints += list(R['_piece_paint'])
            mats += [ex['mesa'].get(pi)] * len(R['_pieces'])        # the articulated body moves as one
        for k, p in enumerate(out['pieces']):
            if k not in flexi:
                pieces.append(p['mesh'])
                paints.append(p['paint'])
                mats.append(ex['mesa'].get(k))
        STATE['export'] = dict(pieces=pieces, paint=paints, data3mf=ex['data3mf'], nome3mf=ex['arquivo3mf'],
                               pasta=folder, palette=pal)
        R0 = dict(Rs[0][1])
        R0.update(juntas=[q or dict(luz='nada', checks=[]) for q in juntas_all], vermelhas=sorted(set(verm_all)),
                  testes=[t for _, R in Rs for t in R.get('testes', [])], cortes=res, conflitos=conflitos,
                  pecas=len(pieces), arquivo3mf=ex['arquivo3mf'], pintado=True, modo='juntas_e_cortes',
                  segundos=round(time.time() - t0, 1), placas=ex['placas'], avisos_placa=ex['avisos_placa'],
                  impressora=_printer(body)['nome'], partes_articuladas=len(Rs), impressao=ex.get('impressao'), malha_stl=ex.get('malha'),
                  mesa=dict(pecas=mats, placas=ex['n_placas'], impressora=_printer(body)))
        return R0

    def _split_post(self, p, body):
        sp = STATE.get('split') or {}
        if p == '/api/split/regions':
            key = self._split_key()
            if key is None:
                return _json(self, dict(ok=False, regioes=[], msg='Pinte o modelo primeiro: cada área pintada pode virar uma peça.'))
            if sp.get('key') != key:
                R = SPL.Regions(STATE['base'], _paint_ok())
                sp = dict(key=key, R=R)
                STATE['split'] = sp
            R = sp['R']
            of = R.of.astype(np.int32)
            return _json(self, dict(ok=True, chave=key, regioes=[R.info(k) for k in range(len(R.list))],
                                    por_triangulo=base64.b64encode(of.tobytes()).decode('ascii')))
        if p in ('/api/split/preview', '/api/split/export'):
            key = self._split_key()
            if key is None or body.get('chave') != key:
                return _json(self, dict(error='A pintura mudou: abra a lista de áreas de novo.'), 409)
            cfg = body.get('configs') or []
            if not any(c.get('separar', True) for c in cfg):
                return _json(self, dict(error='Marque pelo menos uma área para separar.'), 400)
            if not self._busy('separando peças'):
                return
            try:
                out = self._split_out(cfg, lambda t: STATE.__setitem__('progress', t))
            finally:
                self._done()
            sp = STATE['split']
            res = SPL.summary(out)
            if body.get('joints'):
                try:
                    _, res['conflitos'] = SPL.assign_joints(out, body['joints'], STATE['base'], float(body.get('clearance', 0.4)))
                except Exception:
                    traceback.print_exc()
            if p == '/api/split/export':
                stamp = time.strftime('%Y%m%d_%H%M%S')
                folder = os.path.join(out_dir(), f"{STATE['name']}_partes_{stamp}")
                ex = SPL.export(out, folder, STATE['name'], list(STATE.get('palette') or []))
                sp['export'] = dict(data=ex['data3mf'], nome=ex['arquivo3mf'], pasta=folder)
                res.update(exportado=True, pasta=folder, arquivo3mf=ex['arquivo3mf'], montado=ex['montado'],
                           stls=ex['stls'], conferido=ex['ok'])
            return _json(self, dict(ok=True, **res))
        return _json(self, dict(error='rota desconhecida'), 404)

    def _free_post(self, p, body):
        if p == '/api/free/preview':
            if STATE['base'] is None:
                return _json(self, dict(error='Carregue um modelo primeiro.'), 400)
            livres = [c for c in (body.get('livres') or []) if c.get('linhas') or c.get('mascara') or c.get('plano')]
            if not livres:
                return _json(self, dict(error='Desenhe pelo menos uma linha de corte.'), 400)
            if not self._busy('corte livre'):
                return
            try:
                out = self._split_out([], lambda t: STATE.__setitem__('progress', t), livres)
            finally:
                self._done()
            STATE['free'] = dict(out=out)
            res = SPL.summary(out)
            return _json(self, dict(ok=True, livres=FC.summary(out), partes=res['partes'], segundos=out['segundos']))
        return _json(self, dict(error='rota desconhecida'), 404)

    # ------------------------------------------------------------------ controle pelo Claude (MCP)
    def _mcp_get(self, p, q):
        ativo = bool(load_config().get('mcp'))
        if p == '/api/mcp/config':
            return _json(self, dict(ativo=ativo, registrado=BR.registered(), arquivo_claude=BR.claude_config_path(),
                                    janela=BR.window_alive(), versao=VERSION))
        if p == '/api/mcp/poll':
            if not ativo:
                time.sleep(2)
                return _json(self, {})
            return _json(self, BR.poll(25.0))
        return _json(self, dict(error='rota desconhecida'), 404)

    def _mcp_post(self, p, body):
        if p == '/api/mcp/config':
            cfg = load_config()
            cfg['mcp'] = bool(body.get('ativo'))
            save_config(cfg)
            return _json(self, dict(ok=True, ativo=cfg['mcp']))
        if p == '/api/mcp/registrar':
            try:
                return _json(self, BR.register_claude())
            except Exception as ex:
                return _json(self, dict(ok=False, msg=str(ex)))
        if p == '/api/mcp/result':
            BR.result(body.get('id'), body.get('resultado'))
            return _json(self, dict(ok=True))
        if p == '/api/mcp/cmd':
            if not load_config().get('mcp'):
                return _json(self, dict(ok=False, erro='O controle pelo Claude está desligado. No app, clique em 🤖 Claude (no topo) '
                                                        'e ligue "Permitir que o Claude controle o app".'), 403)
            if not BR.window_alive():
                return _json(self, dict(ok=False, erro='A janela do EFC3D não está aberta.'), 409)
            res = BR.send(body.get('tipo', ''), body.get('args') or {}, float(body.get('timeout') or 120))
            return _json(self, res if isinstance(res, dict) else dict(ok=True, resultado=res))
        return _json(self, dict(error='rota desconhecida'), 404)

    def _pieces_post(self, p, body):
        """Prévia única (1.9): peças por cor e cortes livres juntos, como na exportação."""
        if p == '/api/pieces/host':
            # corte numa peça: a peça como ela está antes deste corte (os cortes anteriores aplicados),
            # para desenhar a linha sobre ela, inclusive nas faces de corte
            if STATE['base'] is None:
                return _json(self, dict(error='Carregue um modelo primeiro.'), 400)
            sep = body.get('separar') or None
            cfg = []
            if sep:
                key = self._split_key()
                if key is None or sep.get('chave') != key:
                    return _json(self, dict(error='A pintura mudou: abra a lista de áreas de novo.'), 409)
                cfg = sep.get('configs') or []
            livres = CN.normalizar([c for c in (body.get('livres') or []) if c.get('linhas') or c.get('mascara') or c.get('plano')]) or None
            ponto = body.get('ponto') or [0, 0, 0]
            skey = self._snap_key(cfg)

            def look():
                if livres:
                    return FC.host_piece(skey, livres, ponto)
                sp_ = STATE.get('split') or {}
                same = sp_.get('key') == (self._split_key() or f"{id(STATE['base'])}:sem_pintura") and \
                    sp_.get('cfg') is not None and json.loads(sp_['cfg'])[0] == json.loads(json.dumps(cfg))
                b_ = sp_.get('base_out') if same else None
                return FC.host_piece(skey, [], ponto, pieces=b_['pieces']) if b_ is not None else None
            # a peça como o corte vai vê-la: guardada pela última prévia, ou calculada de novo
            hp = look()
            if hp is None:
                if not self._busy('peça para o corte'):
                    return
                try:
                    self._split_out(cfg, lambda t: STATE.__setitem__('progress', t), livres)
                finally:
                    self._done()
                hp = look()
                if hp is None and livres:
                    # o resultado guardado era de outra lista de cortes: calcula esta de novo
                    STATE['split'] = {}
                    if not self._busy('peça para o corte'):
                        return
                    try:
                        self._split_out(cfg, lambda t: STATE.__setitem__('progress', t), livres)
                    finally:
                        self._done()
                    hp = look()
            if not hp:
                return _json(self, dict(error='A peça deste corte não existe mais: escolha a peça de novo.'), 404)
            T, nome = hp
            STATE['host_piece'] = SPL._stl(T)
            return _json(self, dict(ok=True, nome=nome, triangulos=int(len(T))))
        if p != '/api/pieces/preview':
            return _json(self, dict(error='rota desconhecida'), 404)
        if STATE['base'] is None:
            return _json(self, dict(error='Carregue um modelo primeiro.'), 400)
        sep = body.get('separar') or None
        cfg = []
        if sep:
            key = self._split_key()
            if key is None or sep.get('chave') != key:
                return _json(self, dict(error='A pintura mudou: abra a lista de áreas de novo.'), 409)
            cfg = sep.get('configs') or []
        livres = [c for c in (body.get('livres') or []) if c.get('linhas') or c.get('mascara') or c.get('plano')] or None
        STATE['conectores'] = body.get('conectores') or []
        if not any(c.get('separar', True) for c in cfg) and not livres:
            return _json(self, dict(error='Nada para separar: marque áreas para separar ou crie um corte livre (aba Cortes).'), 400)
        if not self._busy('prévia das peças'):
            return
        try:
            out = self._split_out(cfg, lambda t: STATE.__setitem__('progress', t), livres)
        finally:
            self._done()
        STATE['pieces_prev'] = out
        res = SPL.summary(out)
        res['livres'] = FC.summary(out) if livres else []
        if out.get('conectores') is not None:
            res['conectores'] = out['conectores']
        if body.get('joints'):
            try:
                _, res['conflitos'] = SPL.assign_joints(out, body['joints'], STATE['base'], float(body.get('clearance', 0.4)))
            except Exception:
                traceback.print_exc()
        return _json(self, dict(ok=True, **res))

    def _pieces_get(self, p, q):
        if p == '/api/pieces/host.stl':
            if not STATE.get('host_piece'):
                return _json(self, dict(error='Escolha a peça primeiro.'), 404)
            return _bin(self, STATE['host_piece'], 'peca.stl')
        out = STATE.get('pieces_prev')
        if out is None:
            return _json(self, dict(error='Faça a prévia primeiro.'), 404)
        i = int(q.get('i', ['0'])[0])
        if not 0 <= i < len(out['pieces']):
            return _json(self, dict(error='peça inexistente'), 404)
        part = out['pieces'][i]
        if p == '/api/pieces/part.stl':
            return _bin(self, SPL._stl(part['T']), f'peca_{i}.stl')
        if p == '/api/pieces/owner':
            # de qual peça da prévia é cada triângulo do modelo (para ocultar uma peça já recortada na
            # vista e continuar marcando o que está por baixo); -1 = fora de todas
            if out.get('_owner') is None:
                from scipy.spatial import cKDTree
                cs, lab = [], []
                for j, pc in enumerate(out['pieces']):
                    c_ = np.asarray(pc['T'], np.float64).mean(1)
                    cs.append(c_)
                    lab.append(np.full(len(c_), j, np.int16))
                tb = PT.tri_array(STATE['base']).mean(1)
                d_, k_ = cKDTree(np.concatenate(cs)).query(tb, distance_upper_bound=0.5)
                own = np.full(len(tb), -1, np.int16)
                ok_ = np.isfinite(d_)
                own[ok_] = np.concatenate(lab)[k_[ok_]]
                out['_owner'] = own
            return _json(self, dict(dono=base64.b64encode(out['_owner'].tobytes()).decode('ascii')))
        if p == '/api/pieces/part_paint':
            return _json(self, dict(pintura=base64.b64encode(np.asarray(part['paint'], np.uint8).tobytes()).decode('ascii'),
                                    paleta=STATE.get('palette')))
        return _json(self, dict(error='rota desconhecida'), 404)

    def _free_get(self, p, q):
        out = (STATE.get('free') or {}).get('out')
        if out is None:
            return _json(self, dict(error='Faça a prévia primeiro.'), 404)
        i = int(q.get('i', ['0'])[0])
        part = out['pieces'][i]
        if p == '/api/free/part.stl':
            return _bin(self, SPL._stl(part['T']), f'parte_{i}.stl')
        if p == '/api/free/part_paint':
            return _json(self, dict(pintura=base64.b64encode(np.asarray(part['paint'], np.uint8).tobytes()).decode('ascii'),
                                    paleta=STATE.get('palette')))
        return _json(self, dict(error='rota desconhecida'), 404)

    def _split_get(self, p, q):
        sp = STATE.get('split') or {}
        out = sp.get('out')
        if p == '/api/split/export.3mf':
            ex = sp.get('export')
            if not ex:
                return _json(self, dict(error='Exporte as peças primeiro.'), 404)
            return _bin(self, ex['data'], ex['nome'])
        if out is None:
            return _json(self, dict(error='Faça a prévia primeiro.'), 404)
        i = int(q.get('i', ['0'])[0])
        part = out['pieces'][i]
        if p == '/api/split/part.stl':
            return _bin(self, SPL._stl(part['T']), f'parte_{i}.stl')
        if p == '/api/split/part_paint':
            return _json(self, dict(pintura=base64.b64encode(np.asarray(part['paint'], np.uint8).tobytes()).decode('ascii'),
                                    paleta=STATE.get('palette')))
        return _json(self, dict(error='rota desconhecida'), 404)


def main():
    srv = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    url = f'http://127.0.0.1:{PORT}/'
    BR.announce(PORT, VERSION)
    print(f'EFC3D {VERSION} rodando em {url}  (feche esta janela para encerrar)')
    if '--no-browser' not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
