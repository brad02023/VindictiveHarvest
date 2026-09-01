$root = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $env:LOCALAPPDATA "Programs\Python\Python314\pythonw.exe"
if (-not (Test-Path $pythonw)) {
    $cmd = Get-Command pythonw -ErrorAction SilentlyContinue
    if ($cmd) { $pythonw = $cmd.Source }
}
if (-not $pythonw) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $pythonw = $cmd.Source }
}
if (-not $pythonw) {
    throw "Python not found. Install Python 3.11+ and re-run."
}
$icon = Join-Path $root "viha\data\viha.ico"
$desktop = [Environment]::GetFolderPath("Desktop")
$lnk = Join-Path $desktop "VIHA.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($lnk)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = "-m viha"
$shortcut.WorkingDirectory = $root
$shortcut.WindowStyle = 1
$shortcut.Description = "Vindictive Harvest public-source persona workbench"
if (Test-Path $icon) {
    $shortcut.IconLocation = "$icon,0"
}
$shortcut.Save()
Write-Host "Shortcut: $lnk"
Write-Host "Icon: $icon"
