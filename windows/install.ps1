# EFC3D: instalacao local no Windows 10 ou 11
# Uso: clique duas vezes em "instalar_windows.bat" (ele chama este script).
$ErrorActionPreference = 'Stop'
$Src  = Split-Path -Parent $PSScriptRoot
$App  = Join-Path $env:USERPROFILE 'EFC3D'   # programa em app\ e venv\; suas configuracoes ficam ao lado
$Name = 'EFC3D'
$Ver  = '1.58'

Write-Host "== $Name $Ver : instalando" -ForegroundColor Cyan
if (-not (Test-Path (Join-Path $Src 'app\desktop.py'))) {
  Write-Host "Pasta 'app' nao encontrada ao lado deste instalador. Extraia o .zip inteiro antes de instalar." -ForegroundColor Red
  exit 1
}

# ---------------------------------------------------------------- Python 3.10 a 3.13
function Test-Py([string]$exe, [string[]]$pre) {
  try {
    $v = & $exe @pre -c "import sys;print(sys.version_info[0]*100+sys.version_info[1])" 2>$null
    if ($LASTEXITCODE -eq 0 -and $v -match '^\d+$') {
      $n = [int]$v
      if ($n -ge 310 -and $n -le 313) { return $true }
    }
  } catch { }
  return $false
}
$PyExe = $null; $PyPre = @()
$cands = @(
  @('py', '-3.12'), @('py', '-3.13'), @('py', '-3.11'), @('py', '-3.10'),
  @("$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"),
  @("$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"),
  @("$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"),
  @('python')
)
foreach ($c in $cands) {
  $exe = $c[0]; $pre = @(); if ($c.Count -gt 1) { $pre = $c[1..($c.Count - 1)] }
  if (($exe -like '*\*') -and -not (Test-Path $exe)) { continue }
  if (-not ($exe -like '*\*') -and -not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
  if (Test-Py $exe $pre) { $PyExe = $exe; $PyPre = $pre; break }
}
if (-not $PyExe) {
  Write-Host "Python 3.10 a 3.13 nao encontrado." -ForegroundColor Yellow
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    $r = Read-Host "Instalar o Python 3.12 agora (winget, so para o seu usuario)? [S/N]"
    if ($r -match '^[sSyY]') {
      winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
      $p312 = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
      if (Test-Path $p312) { $PyExe = $p312; $PyPre = @() }
    }
  }
  if (-not $PyExe) {
    Write-Host "Instale o Python 3.12 por https://www.python.org/downloads/windows/" -ForegroundColor Yellow
    Write-Host "(marque 'Add python.exe to PATH') e rode o instalador de novo."
    exit 1
  }
}
$pv = & $PyExe @PyPre --version
Write-Host "   Python: $PyExe $($PyPre -join ' ') ($pv)"

# ---------------------------------------------------------------- copia do app e ambiente
Get-Process python, pythonw -ErrorAction SilentlyContinue |
  Where-Object { $_.Path -and $_.Path -like "$App\venv\*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
New-Item -ItemType Directory -Force -Path $App | Out-Null
if (Test-Path "$App\app") { Remove-Item -Recurse -Force "$App\app" }
Copy-Item -Recurse -Force (Join-Path $Src 'app') "$App\app"
Copy-Item -Force (Join-Path $PSScriptRoot 'uninstall.ps1') "$App\uninstall.ps1"

$VPy = "$App\venv\Scripts\python.exe"
if (-not (Test-Path $VPy)) {
  Write-Host "   criando o ambiente do app..."
  & $PyExe @PyPre -m venv "$App\venv"
  if ($LASTEXITCODE -ne 0) { Write-Host "Falha ao criar o ambiente Python." -ForegroundColor Red; exit 1 }
}
Write-Host "   instalando o motor de geometria (alguns minutos na primeira vez)..."
& $VPy -m pip install --upgrade pip --disable-pip-version-check -q
& $VPy -m pip install -r "$App\app\requirements.txt" --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { Write-Host "Falha ao instalar as bibliotecas. Confira a internet e rode de novo." -ForegroundColor Red; exit 1 }
Write-Host "   janela propria do app (pywebview)..."
& $VPy -m pip install "pywebview>=5.0" --disable-pip-version-check -q
if ($LASTEXITCODE -ne 0) {
  Write-Host "   aviso: pywebview nao instalou; o app vai abrir no Edge (modo app) ou no navegador." -ForegroundColor Yellow
}
& $VPy -c "import manifold3d, numpy; print('   motor de geometria OK')"
if ($LASTEXITCODE -ne 0) { Write-Host "O motor de geometria nao carregou. Veja a mensagem acima." -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------- atalhos
$W = New-Object -ComObject WScript.Shell
function New-Lnk([string]$path, [string]$target, [string]$arguments, [string]$icon, [string]$desc) {
  $s = $W.CreateShortcut($path)
  $s.TargetPath = $target
  $s.Arguments = $arguments
  $s.WorkingDirectory = "$App\app"
  $s.IconLocation = "$icon,0"
  $s.Description = $desc
  $s.Save()
}
$PyW  = "$App\venv\Scripts\pythonw.exe"
$Ico  = "$App\app\windows\AppIcon.ico"
$Run  = "`"$App\app\desktop.py`""
$Menu = [Environment]::GetFolderPath('Programs')
$Desk = [Environment]::GetFolderPath('Desktop')
New-Lnk (Join-Path $Menu "$Name.lnk") $PyW $Run $Ico 'Easy Flexy and Cuts 3D'
New-Lnk (Join-Path $Desk "$Name.lnk") $PyW $Run $Ico 'Easy Flexy and Cuts 3D'
New-Lnk (Join-Path $Menu "Desinstalar $Name.lnk") "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  "-NoProfile -ExecutionPolicy Bypass -File `"$App\uninstall.ps1`"" $Ico "Remove o $Name"

$Out = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'EFC3D\saidas'
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host ""
Write-Host "== Pronto: $Name $Ver instalado." -ForegroundColor Green
Write-Host "   Abra pelo atalho na Area de Trabalho ou pelo menu Iniciar (digite EFC3D)."
Write-Host "   Para fixar na barra de tarefas: com o app aberto, botao direito no icone > Fixar."
Write-Host "   Os arquivos gerados ficam em $Out"
Start-Process -FilePath $PyW -ArgumentList $Run -WorkingDirectory "$App\app"
