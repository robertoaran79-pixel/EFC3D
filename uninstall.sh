#!/bin/bash
# EFC3D (Easy Flexy and Cuts 3D): remove o app instalado pelo codigo. Suas configuracoes e saidas sao mantidas.
APP="$HOME/EFC3D"
pkill -f "$APP/venv/bin/python" 2>/dev/null || true
rm -rf "$APP/app" "$APP/venv"
rm -rf "/Applications/EFC3D.app" "$HOME/Applications/EFC3D.app"
echo "EFC3D removido."
echo "Suas configuracoes e pecas de corte importadas continuam em ~/EFC3D e as saidas em ~/Documents/EFC3D/saidas (apague se quiser)."
