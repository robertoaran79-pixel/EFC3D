@echo off
rem EFC3D: remove o app do Windows (suas configuracoes e saidas ficam).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\uninstall.ps1"
