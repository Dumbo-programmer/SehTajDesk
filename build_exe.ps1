param(
    [switch]$OneFile,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Resolve-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return "py"
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        return "python"
    }

    throw "Python is not available in PATH. Install Python 3.10+ first."
}

function Remove-ObsoletePathlibBackport {
    param(
        [string]$PythonCommand
    )

    Write-Host "Checking for obsolete pathlib backport package..."
    $installedPackages = & $PythonCommand -m pip list --format=freeze
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to read installed package list with pip."
    }

    $hasPathlibBackport = $false
    foreach ($pkg in $installedPackages) {
        if ($pkg -match '^pathlib==') {
            $hasPathlibBackport = $true
            break
        }
    }

    if ($hasPathlibBackport) {
        Write-Warning "Detected incompatible 'pathlib' backport. Removing it for PyInstaller compatibility..."
        & $PythonCommand -m pip uninstall -y pathlib

        if ($LASTEXITCODE -ne 0) {
            throw "Failed to uninstall incompatible 'pathlib' package."
        }

        Write-Host "Removed incompatible pathlib backport."
    } else {
        Write-Host "No incompatible pathlib backport detected."
    }
}

$PythonCmd = Resolve-PythonCommand
Write-Host "Using Python command: $PythonCmd"

if ($Clean) {
    Write-Host "Cleaning previous build artifacts..."
    Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
    Remove-Item -Force *.spec -ErrorAction SilentlyContinue
}

Write-Host "Installing/updating build dependencies..."
& $PythonCmd -m pip install --upgrade pip
& $PythonCmd -m pip install -r requirements.txt
& $PythonCmd -m pip install pyinstaller

Remove-ObsoletePathlibBackport -PythonCommand $PythonCmd

$pyInstallerArgs = @(
    "--noconfirm",
    "--clean",
    "--windowed",
    "--name", "SehTajDesk",
    "--hidden-import", "fitz"
)

$excludedModules = @(
    "tensorflow",
    "tensorboard",
    "keras",
    "torch",
    "jax",
    "jaxlib"
)

foreach ($excluded in $excludedModules) {
    $pyInstallerArgs += @("--exclude-module", $excluded)
}

if ($OneFile) {
    $pyInstallerArgs += "--onefile"
} else {
    $pyInstallerArgs += "--onedir"
}

$pyInstallerArgs += "main.py"

Write-Host "Running PyInstaller..."
& $PythonCmd -m PyInstaller @pyInstallerArgs

if ($LASTEXITCODE -ne 0) {
    throw "Build failed with exit code $LASTEXITCODE."
}

if ($OneFile) {
    $ExePath = Join-Path $ProjectRoot "dist\SehTajDesk.exe"
} else {
    $ExePath = Join-Path $ProjectRoot "dist\SehTajDesk\SehTajDesk.exe"
}

Write-Host "Build complete."
Write-Host "Executable path: $ExePath"
