#!/bin/bash
# EFC3D: instalacao local (macOS, Apple Silicon ou Intel)
# Uso: abra o Terminal e rode:  bash "<pasta>/install.sh"
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
APP="$HOME/EFC3D"          # programa em app/ e venv/; suas configuracoes ficam ao lado
NAME="EFC3D"

echo "== $NAME: instalando"
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1; then
    v=$("$c" -c 'import sys;print(sys.version_info[0]*100+sys.version_info[1])' 2>/dev/null || echo 0)
    if [ "$v" -ge 310 ]; then PY="$(command -v $c)"; break; fi
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3.10 ou mais novo nao encontrado."
  echo "Instale por https://www.python.org/downloads/macos/  (ou: brew install python) e rode de novo."
  exit 1
fi
echo "   Python: $PY ($($PY --version))"

pkill -f "$APP/venv/bin/python" 2>/dev/null || true
# espera o app antigo fechar de verdade (senao a janela nova fala com o motor antigo)
for i in $(seq 1 20); do pgrep -f "$APP/venv/bin/python" >/dev/null 2>&1 || break; sleep 0.5; done
pkill -9 -f "$APP/venv/bin/python" 2>/dev/null || true
mkdir -p "$APP"
rm -rf "$APP/app"
cp -R "$SRC/app" "$APP/app"
"$PY" -m venv "$APP/venv"
"$APP/venv/bin/python" -m pip install --upgrade pip >/dev/null
"$APP/venv/bin/python" -m pip install -r "$APP/app/requirements.txt"
echo "   janela propria do Mac (pywebview)..."
if ! "$APP/venv/bin/python" -m pip install "pywebview>=5.0" >/dev/null 2>&1; then
  echo "   aviso: pywebview nao instalou; o app vai abrir no Chrome (modo app) ou no navegador."
fi

# app do Mac: icone, nome no Dock e na barra de menus
DEST="/Applications"
[ -w "$DEST" ] || { DEST="$HOME/Applications"; mkdir -p "$DEST"; }
BUNDLE="$DEST/$NAME.app"
rm -rf "$BUNDLE"
mkdir -p "$BUNDLE/Contents/MacOS" "$BUNDLE/Contents/Resources"
cp "$APP/app/mac/AppIcon.icns" "$BUNDLE/Contents/Resources/AppIcon.icns"
cat > "$BUNDLE/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>$NAME</string>
  <key>CFBundleDisplayName</key><string>$NAME</string>
  <key>CFBundleIdentifier</key><string>com.rlalabs.efc3d.desktop</string>
  <key>CFBundleVersion</key><string>1.50</string>
  <key>CFBundleShortVersionString</key><string>1.50</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>launcher</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST
cat > "$BUNDLE/Contents/MacOS/launcher" <<LAUNCHER
#!/bin/bash
cd "$APP/app"
exec "$APP/venv/bin/python" desktop.py >> "$APP/app.log" 2>&1
LAUNCHER
chmod +x "$BUNDLE/Contents/MacOS/launcher"
touch "$BUNDLE"
LSREG=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
[ -x "$LSREG" ] && "$LSREG" -f "$BUNDLE" >/dev/null 2>&1 || true

# o app com o nome antigo (3D Flexi Creator) sai; seus arquivos continuam onde estao
rm -rf "/Applications/3D Flexi Creator.app" "$HOME/Applications/3D Flexi Creator.app"
rm -f "$HOME/Applications/Flexi Studio.command" "$HOME/Documents/Flexi Studio/Abrir Flexi Studio.command"

"$APP/venv/bin/python" -c "import manifold3d, numpy; print('   motor de geometria OK')"
echo ""
echo "== Pronto: $BUNDLE"
echo "   Abra pelo Launchpad, pelo Spotlight (Cmd+Espaco, digite EFC3D) ou pela pasta Aplicativos."
echo "   Para deixar no Dock: com o app aberto, clique com o botao direito no icone > Opcoes > Manter no Dock."
echo "   Os arquivos gerados ficam em ~/Documents/EFC3D/saidas (ou na pasta Flexi Studio, se voce ja usava)"
open "$BUNDLE" || true
