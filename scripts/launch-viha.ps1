Set-Location (Split-Path -Parent $PSScriptRoot)
$root = Get-Location
$pythonw = Join-Path $root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) {
    $pythonw = Join-Path $root ".venv\Scripts\python.exe"
}
if (-not (Test-Path $pythonw)) {
    $cmd = Get-Command pythonw -ErrorAction SilentlyContinue
    if ($cmd) { $pythonw = $cmd.Source }
}
if (-not $pythonw -or -not (Test-Path $pythonw)) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $pythonw = $cmd.Source }
}
if (-not $pythonw) {
    throw "Python not found. Double-click install.bat first (needs Python 3.10+)."
}
Start-Process -FilePath $pythonw -ArgumentList "-m","viha" -WorkingDirectory $root
