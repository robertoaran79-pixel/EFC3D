"""EFC3D: opens as a desktop app on Mac (Dock icon, menu bar name) and Windows (taskbar icon).

The geometry server runs inside this process; closing the window quits the app. If the native
window library (pywebview) is missing, the interface opens in Chrome as an app window, or in
the default browser.
"""
import os
import socket
import sys
import threading
import time
import webbrowser
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
APP_NAME = 'EFC3D'
ICON = os.path.join(HERE, 'mac', 'AppIcon_1024.png')
ICO = os.path.join(HERE, 'windows', 'AppIcon.ico')
LOG = os.path.join(os.path.expanduser('~'), 'EFC3D', 'app.log')


def _win_setup():
    """Windows: log to ~/EFC3D/app.log (pythonw has no console) and an app id of its own,
    so the taskbar shows the EFC3D icon instead of Python's."""
    if sys.platform != 'win32':
        return
    try:
        if sys.stdout is None or 'pythonw' in os.path.basename(sys.executable).lower():
            os.makedirs(os.path.dirname(LOG), exist_ok=True)
            f = open(LOG, 'a', encoding='utf-8', buffering=1)
            sys.stdout = sys.stderr = f
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('RLALabs.EFC3D')
    except Exception:
        pass


def _win_icon():
    """Windows: put the app icon on the window (title bar and taskbar)."""
    if sys.platform != 'win32' or not os.path.exists(ICO):
        return
    try:
        import ctypes
        u = ctypes.windll.user32
        for _ in range(40):
            hwnd = u.FindWindowW(None, APP_NAME)
            if hwnd:
                break
            time.sleep(0.25)
        if not hwnd:
            return
        big = u.LoadImageW(None, ICO, 1, 256, 256, 0x10)
        small = u.LoadImageW(None, ICO, 1, 32, 32, 0x10)
        if big:
            u.SendMessageW(hwnd, 0x80, 1, big)          # WM_SETICON, ICON_BIG
        if small:
            u.SendMessageW(hwnd, 0x80, 0, small)        # WM_SETICON, ICON_SMALL
    except Exception:
        pass


def _port_free(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(('127.0.0.1', port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def _already_running(port):
    """Já tem um EFC3D nesta porta? Se for de outra versão (ficou aberto durante uma
    atualização), ele é encerrado e esta versão assume: senão a janela nova falaria com o motor
    antigo, ou com nenhum quando ele fechar ("Load failed")."""
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/status', timeout=1.5) as r:
            st = json.loads(r.read())
    except Exception:
        return False
    if 'versao' not in st:
        return False
    try:
        import server as SV
        mine = SV.VERSION
    except Exception:
        mine = None
    if mine and st.get('versao') != mine:
        try:
            req = urllib.request.Request(f'http://127.0.0.1:{port}/api/encerrar', data=b'{}', method='POST')
            urllib.request.urlopen(req, timeout=2).read()
        except Exception:
            pass
        for _ in range(40):
            if _port_free(port):
                return False
            time.sleep(0.25)
        return False
    return True


def _mac_identity():
    """Menu bar name and Dock icon of the app (the process runs the venv Python)."""
    if sys.platform != 'darwin':
        return
    try:
        from Foundation import NSBundle
        from AppKit import NSApplication, NSImage
        info = NSBundle.mainBundle().localizedInfoDictionary() or NSBundle.mainBundle().infoDictionary()
        if info is not None:
            info['CFBundleName'] = APP_NAME
            info['CFBundleDisplayName'] = APP_NAME
        app = NSApplication.sharedApplication()
        img = NSImage.alloc().initByReferencingFile_(ICON)
        if img is not None:
            app.setApplicationIconImage_(img)
    except Exception:
        pass


class Api:
    """Native dialogs (Mac and Windows) for the page (window.pywebview.api.*). Each returns a path or ''."""

    def _dlg(self, kind, **kw):
        import webview
        FD = getattr(webview, 'FileDialog', None)
        const = {'pasta': (FD.FOLDER if FD else webview.FOLDER_DIALOG),
                 'abrir': (FD.OPEN if FD else webview.OPEN_DIALOG),
                 'salvar': (FD.SAVE if FD else webview.SAVE_DIALOG)}[kind]
        r = webview.windows[0].create_file_dialog(const, **kw)
        if not r:
            return ''
        return r if isinstance(r, str) else r[0]

    def escolher_pasta(self, inicio=''):
        return self._dlg('pasta', directory=inicio or '')

    def salvar_como(self, nome='projeto.flexiproj', inicio=''):
        return self._dlg('salvar', directory=inicio or '', save_filename=nome)

    def abrir(self, inicio=''):
        try:
            from i18n import tr                       # no idioma escolhido na tela
        except Exception:
            tr = lambda x: x
        return self._dlg('abrir', directory=inicio or '', file_types=(tr('Modelos e projetos') + ' (*.flexiproj;*.stl;*.glb;*.gltf;*.obj;*.zip)',
                                                                      tr('Projeto EFC3D') + ' (*.flexiproj)', tr('Todos') + ' (*.*)'))


def _open_fallback(url):
    chrome = '/Applications/Google Chrome.app'
    if sys.platform == 'darwin' and os.path.exists(chrome):
        os.system(f'open -na "{chrome}" --args --app={url} --window-size=1500,950')
        return
    if sys.platform == 'win32':
        # Edge (always present on Windows 10 and 11) or Chrome as an app window
        import subprocess
        pf = [os.environ.get(k, '') for k in ('ProgramFiles(x86)', 'ProgramFiles', 'LOCALAPPDATA')]
        cands = [os.path.join(b, 'Microsoft', 'Edge', 'Application', 'msedge.exe') for b in pf if b] + \
                [os.path.join(b, 'Google', 'Chrome', 'Application', 'chrome.exe') for b in pf if b]
        for exe in cands:
            if os.path.exists(exe):
                subprocess.Popen([exe, f'--app={url}', '--window-size=1500,950'])
                return
    webbrowser.open(url)


def main():
    _win_setup()
    port = int(os.environ.get('FLEXI_PORT', '8765'))
    url = f'http://127.0.0.1:{port}/'
    server = None
    if _already_running(port):
        pass                                  # second click on the icon: just open another window
    else:
        if not _port_free(port):
            for p in range(port + 1, port + 50):
                if _port_free(p):
                    port = p
                    break
            url = f'http://127.0.0.1:{port}/'
        import server as SV
        server = ThreadingHTTPServer(('127.0.0.1', port), SV.Handler)
        SV.BR.announce(port, SV.VERSION)
        threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        import webview
    except Exception:
        webview = None
    if webview is None:
        _open_fallback(url)
        if server is not None:
            print(f'{APP_NAME} rodando em {url} (feche esta janela do Terminal para encerrar)')
            sys.stdout.flush()
            try:
                while True:
                    time.sleep(3600)
            except KeyboardInterrupt:
                pass
        return
    try:
        webview.settings['ALLOW_DOWNLOADS'] = True
    except Exception:
        pass
    _mac_identity()                           # before the window: menu bar name and Dock icon
    # a janela do processo que tem o motor se identifica (?j=dono): ao fechar, o motor continua enquanto
    # outra janela do app estiver aberta (aberta por um segundo clique no ícone)
    win_url = url + ('?j=dono' if server is not None else '')
    webview.create_window(APP_NAME, win_url, width=1500, height=950, min_size=(1000, 650), js_api=Api())
    if sys.platform == 'win32':
        threading.Thread(target=_win_icon, daemon=True).start()
    webview.start()
    if server is not None:
        _wait_other_windows()
        server.shutdown()


def _wait_other_windows():
    """A janela que tem o motor fechou. Se outra janela do app ainda está aberta (ela avisa a cada 5 s em
    /api/ping), o motor continua até a última fechar; antes, fechar a primeira janela derrubava o motor das
    outras ("Load failed")."""
    try:
        import server as SV
    except Exception:
        return
    def others():
        now = time.time()
        return [j for j, t in list(SV.JANELAS.items()) if j != 'dono' and now - t < 15]
    while others():
        time.sleep(2)


if __name__ == '__main__':
    if '--mcp' in sys.argv:
        import mcp_server                             # servidor MCP do Claude (app instalado)
        mcp_server.main()
        sys.exit(0)
    if '--autoteste' in sys.argv:
        # app instalado conferindo a si mesmo (corte, exportação e junta), sem janela: usado no empacotamento
        import autoteste
        k = sys.argv.index('--autoteste')
        sys.exit(autoteste.main(sys.argv[k + 1] if len(sys.argv) > k + 1 else os.path.join(os.path.expanduser('~'), 'EFC3D', 'autoteste')))
    main()
