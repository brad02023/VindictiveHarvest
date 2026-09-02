param(
    [string]$Pythonw = ""
)

$root = Split-Path -Parent $PSScriptRoot

function Get-VihaPythonw {
    if ($Pythonw -and (Test-Path $Pythonw)) { return $Pythonw }
    $venvW = Join-Path $root ".venv\Scripts\pythonw.exe"
    if (Test-Path $venvW) { return $venvW }
    $venvPy = Join-Path $root ".venv\Scripts\python.exe"
    if (Test-Path $venvPy) { return $venvPy }
    foreach ($name in @("pythonw", "python")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    return $null
}

$pythonw = Get-VihaPythonw
if (-not $pythonw) {
    throw "Python not found. Double-click install.bat first (needs Python 3.10+)."
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

$cs = Join-Path $PSScriptRoot "LnkAppId.cs"
if (Test-Path $cs) {
    Add-Type -TypeDefinition (Get-Content -Raw $cs) -Language CSharp
    $relaunch = '"{0}" -m viha' -f $pythonw
    $iconRes = if (Test-Path $icon) { "$icon,0" } else { "" }
    [ShortcutProps.Writer]::Apply($lnk, "VIHA.VindictiveHarvest.1", $relaunch, "VIHA", $iconRes)
}

Write-Host "Shortcut: $lnk"
Write-Host "Python: $pythonw"
Write-Host "Icon: $icon"
Write-Host "AppId: VIHA.VindictiveHarvest.1"
