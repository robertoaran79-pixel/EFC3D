"""Gera empacotar/versao_windows.txt (propriedades do EFC3D.exe no Windows) com a versão do server.py."""
import os, re
R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
v = re.search(r"VERSION = '([^']+)'", open(os.path.join(R, 'app', 'server.py'), encoding='utf-8').read()).group(1)
n = [int(x) for x in re.findall(r'\d+', v)][:3] + [0, 0, 0]
t = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({n[0]}, {n[1]}, {n[2]}, 0), prodvers=({n[0]}, {n[1]}, {n[2]}, 0)),
  kids=[StringFileInfo([StringTable('041604B0', [
    StringStruct('CompanyName', 'RLA LABS'),
    StringStruct('FileDescription', 'EFC3D · Easy Flexy and Cuts 3D'),
    StringStruct('FileVersion', '{v}'),
    StringStruct('ProductName', 'EFC3D'),
    StringStruct('ProductVersion', '{v}'),
    StringStruct('LegalCopyright', 'RLA LABS · PolyForm Noncommercial 1.0.0')])]),
    VarFileInfo([VarStruct('Translation', [1046, 1200])])])
"""
open(os.path.join(R, 'empacotar', 'versao_windows.txt'), 'w', encoding='utf-8').write(t)
print(v)
