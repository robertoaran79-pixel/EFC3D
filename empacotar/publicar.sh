#!/bin/bash
# Monta a cópia pública do EFC3D (repositório robertoaran79-pixel/EFC3D) a partir deste repositório de trabalho.
# Só vai o que é do produto: o app Python (Mac e Windows), os instaladores, a licença e a página inicial.
# Fica de fora: o app Swift (apple/), as ferramentas e gabaritos de teste (tools/), os documentos internos e as
# fontes das juntas no Fusion (app/cutters/own).
#   bash empacotar/publicar.sh /caminho/do/clone/EFC3D
set -e
ORIG="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:?informe a pasta do clone do EFC3D}"
cd "$DEST"
git rm -rq --ignore-unmatch . >/dev/null 2>&1 || true
find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
mkdir -p app .github/workflows empacotar docs/img windows
cp -R "$ORIG/app/." app/
rm -rf app/cutters/own app/MANUTENCAO.md
find app -name '__pycache__' -type d -prune -exec rm -rf {} +
cp "$ORIG"/empacotar/{efc3d.spec,efc3d.iss,gerar_versao_windows.py,guardar_registro.sh,novidades.py,publicar.sh} empacotar/
cp "$ORIG/empacotar/github/pacotes.yml" .github/workflows/pacotes.yml
printf 'github: robertoaran79-pixel\n' > .github/FUNDING.yml
cp "$ORIG"/publico/*.md .
cp "$ORIG"/{LICENSE,CHANGELOG.md,LEIA-ME.md,install.sh,uninstall.sh,instalar_windows.bat,desinstalar_windows.bat} .
cp "$ORIG"/windows/*.ps1 windows/
cp "$ORIG/docs/logo.png" docs/
cp "$ORIG"/docs/img/efc3d_*.jpg docs/img/ 2>/dev/null || true
mkdir -p docs/video && cp "$ORIG"/docs/video/efc3d_demo_*.mp4 docs/video/
cat > .gitignore <<'GI'
__pycache__/
*.pyc
build/
dist/
saida/
registro/
.DS_Store
GI
# nada de terceiros nem de teste pode ir junto
if grep -rIlq "fjm_negative\|flexicutter.stl\|carol.npz\|tartaruga.stl" . --exclude-dir=.git --exclude=publicar.sh; then
  echo "ERRO: arquivo de terceiros ou de teste na cópia pública"; grep -rIl "fjm_negative\|flexicutter.stl\|carol.npz\|tartaruga.stl" . --exclude-dir=.git --exclude=publicar.sh; exit 1
fi
ls app/cutters/lib
git add -A
git status --short | wc -l
