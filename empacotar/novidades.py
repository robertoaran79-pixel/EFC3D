"""Imprime a seção da versão pedida do CHANGELOG.md (para a página da versão no GitHub)."""
import re, sys
v = sys.argv[1]
txt = open('CHANGELOG.md', encoding='utf-8').read()
m = re.search(r'^## ' + re.escape(v) + r'\b.*?$(.*?)(?=^## |\Z)', txt, re.M | re.S)
print((m.group(1).strip() if m else f'EFC3D {v}') + '\n\n**Downloads:** escolha o arquivo do seu sistema em *Assets*, logo abaixo.\n\n**Primeira abertura:** no Mac, botão direito no EFC3D › Abrir (ou Ajustes do Sistema › Privacidade e Segurança › Abrir Mesmo Assim), porque o app ainda não é notarizado pela Apple. No Windows, se o SmartScreen avisar: Mais informações › Executar assim mesmo. Detalhes no [README](https://github.com/robertoaran79-pixel/EFC3D#primeira-abertura).\n')
