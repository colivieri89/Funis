# Build Funis.exe (one-folder) and the Windows installer with Inno Setup.
#
# Usage (PowerShell, from any folder):
#   powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1 [-Python py]
# Requirements: Python 3.9 or later on the PATH (the "py" launcher by default) and
# Inno Setup 6 (https://jrsoftware.org/isinfo.php). Output in dist\:
#   Funis\Funis.exe and Funis-<version>-Windows-Setup.exe
param(
    [string]$Python = "py",
    [string]$InnoSetup = ""
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if ($Python -eq "py") { $pyArgs = @("-3") } else { $pyArgs = @() }
& $Python @pyArgs -m venv build_env
$venv = Join-Path (Get-Location) "build_env\Scripts\python.exe"
& $venv -m pip install --quiet --upgrade pip
& $venv -m pip install --quiet --upgrade -r requirements.txt pyinstaller
$version = (& $venv -c "import funis; print(funis.__version__)").Trim()
Write-Host "Building Funis $version with $venv"

& $venv packaging\make_icon.py
if (Test-Path build) { Remove-Item build -Recurse -Force }
if (Test-Path dist) { Remove-Item dist -Recurse -Force }
& $venv -m PyInstaller --noconfirm --clean --log-level WARN packaging\funis.spec
if (-not (Test-Path "dist\Funis\Funis.exe")) { throw "PyInstaller did not produce dist\Funis\Funis.exe" }

# the packaged program must start and solve every example. It has no console, so it writes its
# report to build\selftest.log; the time limit guards against a program that never closes.
$env:QT_QPA_PLATFORM = "offscreen"
$root = (Get-Location).Path
$log = Join-Path $root "build\selftest.log"
$proc = Start-Process -FilePath (Join-Path $root "dist\Funis\Funis.exe") -WorkingDirectory $root `
    -ArgumentList @("--selftest", "`"$(Join-Path $root 'build\selftest.png')`"") -PassThru
$null = $proc.Handle  # keeps the exit code readable after the process ends
if (-not $proc.WaitForExit(900000)) {
    Stop-Process -Id $proc.Id -Force
    throw "The packaged program did not finish its self-test within 15 minutes"
}
if (Test-Path $log) { Get-Content $log | ForEach-Object { Write-Host $_ } }
else { Write-Warning "No self-test report was written ($log)" }
if ($proc.ExitCode -ne 0) { throw "The packaged program failed its self-test (exit code $($proc.ExitCode))" }
Remove-Item Env:QT_QPA_PLATFORM

if ($InnoSetup -eq "") {
    $candidates = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
                    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe")
    foreach ($c in $candidates) { if (Test-Path $c) { $InnoSetup = $c; break } }
}
if ($InnoSetup -eq "" -or -not (Test-Path $InnoSetup)) {
    Write-Warning "Inno Setup (ISCC.exe) not found: the folder dist\Funis is ready, the installer was not built."
    exit 0
}
& $InnoSetup "/DAppVersion=$version" "/DSourceDir=$((Get-Location).Path)" packaging\windows\funis.iss
Get-ChildItem dist\*.exe | ForEach-Object { Write-Host "Built $($_.FullName) ($([math]::Round($_.Length/1MB,1)) MB)" }
