# Creates .venv, installs VIHA + dependencies, and adds a desktop shortcut.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Get-VihaPython {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        foreach ($tag in @("-3.14", "-3.13", "-3.12", "-3.11", "-3.10", "-3")) {
            try {
                $exe = & py $tag -c "import sys; print(sys.executable)" 2>$null
                if ($LASTEXITCODE -ne 0 -or -not $exe) { continue }
                $ver = & py $tag -c "import sys; print('%d.%d' % (sys.version_info[0], sys.version_info[1]))" 2>$null
                if ([version]$ver -ge [version]"3.10") {
                    return $exe.Trim()
                }
            } catch { }
        }
    }
    foreach ($name in @("python", "python3")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        try {
            $ver = & $cmd.Source -c "import sys; print('%d.%d' % (sys.version_info[0], sys.version_info[1]))"
            if ([version]$ver -ge [version]"3.10") {
                return $cmd.Source
            }
        } catch { }
    }
    return $null
}

$python = Get-VihaPython
if (-not $python) {
    Write-Host "Python 3.10+ was not found."
    Write-Host "Install it from https://www.python.org/downloads/ (check 'Add python.exe to PATH'), then run this again."
    exit 1
}

Write-Host "Using $python"
$venv = Join-Path $root ".venv"
$venvPy = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "Creating virtual environment at $venv"
    & $python -m venv $venv
}
Write-Host "Installing VIHA and dependencies…"
& $venvPy -m pip install -U pip
& $venvPy -m pip install -e "$root"
if ($LASTEXITCODE -ne 0) {
    throw "pip install failed (exit $LASTEXITCODE)"
}

$shortcut = Join-Path $PSScriptRoot "install-shortcut.ps1"
if (Test-Path $shortcut) {
    & $shortcut
}

Write-Host ""
Write-Host "VIHA is installed. Use the desktop shortcut, or:"
Write-Host "  $venvPy -m viha"
