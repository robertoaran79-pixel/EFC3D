"""EFC3D (Easy Flexy and Cuts 3D): pastas do usuário.

Até a 1.49 o app se chamava 3D Flexi Creator e guardava as configurações em ~/FlexiStudio e as saídas em
Documentos/Flexi Studio/saidas. Da 1.50 em diante: ~/EFC3D e Documentos/EFC3D/saidas. Na primeira vez, as
configurações, as peças de corte importadas e o cache de força da pasta antiga (~/FlexiStudio) são copiados para a nova (nada é
apagado), e quem já tinha arquivos na pasta de saída antiga continua usando ela.
"""
import json
import os
import shutil
import sys

DADOS = os.path.join(os.path.expanduser('~'), 'EFC3D')
_ANTIGA = os.path.join(os.path.expanduser('~'), 'FlexiStudio')


def documentos():
    """A pasta Documentos (no Windows ela pode ter sido movida, por exemplo para o OneDrive)."""
    if sys.platform == 'win32':
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(1024)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:
                return buf.value
        except Exception:
            pass
    return os.path.join(os.path.expanduser('~'), 'Documents')


SAIDA_PADRAO = os.path.join(documentos(), 'EFC3D', 'saidas')
_SAIDA_ANTIGA = os.path.join(documentos(), 'Flexi Studio', 'saidas')


def migrar():
    """Copia o que importa da pasta antiga (~/FlexiStudio) para a nova, uma vez. Nunca apaga a antiga."""
    os.makedirs(DADOS, exist_ok=True)
    marca = os.path.join(DADOS, '.migrado')
    if os.path.exists(marca) or os.path.isfile(os.path.join(DADOS, 'config.json')) or not os.path.isdir(_ANTIGA):
        return False
    try:
        open(marca, 'w').close()
    except Exception:
        pass
    for nome in ('config.json', 'cache_forca.json'):
        a = os.path.join(_ANTIGA, nome)
        if os.path.isfile(a):
            try:
                shutil.copy2(a, os.path.join(DADOS, nome))
            except Exception:
                pass
    cut = os.path.join(_ANTIGA, 'cutters')
    if os.path.isdir(cut):
        try:
            shutil.copytree(cut, os.path.join(DADOS, 'cutters'), dirs_exist_ok=True)
        except Exception:
            pass
    # quem usava a pasta de saída padrão antiga continua nela (os arquivos dele estão lá)
    cfg_p = os.path.join(DADOS, 'config.json')
    try:
        cfg = json.load(open(cfg_p, encoding='utf-8')) if os.path.isfile(cfg_p) else {}
        if not cfg.get('pasta_saida') and os.path.isdir(_SAIDA_ANTIGA):
            cfg['pasta_saida'] = _SAIDA_ANTIGA
            json.dump(cfg, open(cfg_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    except Exception:
        pass
    return True


migrar()
