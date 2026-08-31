Set-Location (Split-Path -Parent $PSScriptRoot)
$pythonw = Join-Path $env:LOCALAPPDATA "Programs\Python\Python314\pythonw.exe"
if (-not (Test-Path $pythonw)) {
    $pythonw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
}
if (-not $pythonw) {
    $pythonw = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if (-not $pythonw) {
    throw "Python not found. Install Python 3.11+ and re-run."
}
Start-Process -FilePath $pythonw -ArgumentList "-m","viha" -WorkingDirectory (Get-Location)
