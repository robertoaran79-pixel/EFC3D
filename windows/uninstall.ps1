# EFC3D (Easy Flexy and Cuts 3D): remove o app instalado pelo codigo no Windows.
# Suas configuracoes (%USERPROFILE%\EFC3D) e saidas (Documentos\EFC3D\saidas) sao mantidas.
$App  = Join-Path $env:USERPROFILE 'EFC3D'
$Name = 'EFC3D'
Get-Process python, pythonw -ErrorAction SilentlyContinue |
  Where-Object { $_.Path -and $_.Path -like "$App\venv\*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
$Menu = [Environment]::GetFolderPath('Programs')
$Desk = [Environment]::GetFolderPath('Desktop')
Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $Menu "$Name.lnk"), (Join-Path $Desk "$Name.lnk"), (Join-Path $Menu "Desinstalar $Name.lnk")
foreach ($d in @('app', 'venv')) { $p = Join-Path $App $d; if (Test-Path $p) { Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $p } }
Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $App 'uninstall.ps1')
Write-Host "$Name removido."
Write-Host "Suas configuracoes e pecas de corte importadas continuam em $App e as saidas em Documentos\EFC3D\saidas (apague se quiser)."
Read-Host "Pressione Enter para fechar"
