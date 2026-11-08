# EFC3D (Easy Flexy and Cuts 3D): pacote do app (PyInstaller), Mac e Windows.
#   pyinstaller --noconfirm empacotar/efc3d.spec      (rodar na raiz do repositório)
import os, re, sys
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

RAIZ = os.path.abspath(os.path.join(SPECPATH, '..'))
APP = os.path.join(RAIZ, 'app')
VERSAO = re.search(r"VERSION = '([^']+)'", open(os.path.join(APP, 'server.py'), encoding='utf-8').read()).group(1)

datas = [(os.path.join(APP, 'web'), 'web'),
         (os.path.join(APP, 'cutters', 'lib'), os.path.join('cutters', 'lib')),
         (os.path.join(APP, 'mac'), 'mac'),
         (os.path.join(APP, 'windows'), 'windows')]
binaries = []
hidden = ['server', 'editor', 'engine', 'split', 'freecut', 'pelecut', 'conectores', 'encaixe', 'orienta', 'paint',
          'planner', 'plano', 'printers', 'repair', 'texture', 'i18n', 'mcp_bridge', 'mcp_server', 'pastas', 'autoteste',
          'scipy.sparse.csgraph', 'scipy.ndimage', 'scipy.spatial', 'skimage.measure']
for pkg in ('manifold3d', 'trimesh', 'webview', 'shapely'):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hidden += h

a = Analysis([os.path.join(APP, 'desktop.py')], pathex=[APP], binaries=binaries, datas=datas, hiddenimports=hidden,
             excludes=['tkinter', 'matplotlib', 'IPython', 'pytest', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6'],
             noarchive=False)
pyz = PYZ(a.pure)
icone = os.path.join(APP, 'windows', 'AppIcon.ico') if sys.platform == 'win32' else os.path.join(APP, 'mac', 'AppIcon.icns')
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='EFC3D', console=False, icon=icone,
          version=os.path.join(SPECPATH, 'versao_windows.txt') if sys.platform == 'win32' else None)
coll = COLLECT(exe, a.binaries, a.datas, name='EFC3D')
if sys.platform == 'darwin':
    app = BUNDLE(coll, name='EFC3D.app', icon=icone, bundle_identifier='com.rlalabs.efc3d.desktop',
                 info_plist={'CFBundleName': 'EFC3D', 'CFBundleDisplayName': 'EFC3D',
                             'CFBundleGetInfoString': 'EFC3D · Easy Flexy and Cuts 3D',
                             'CFBundleShortVersionString': VERSAO, 'CFBundleVersion': VERSAO,
                             'NSHighResolutionCapable': True, 'LSMinimumSystemVersion': '11.0',
                             'NSHumanReadableCopyright': 'RLA LABS · PolyForm Noncommercial 1.0.0'})
