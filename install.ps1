#Requires -Version 5.1
<#
.SYNOPSIS
    kbstatpy installer for native Windows - the PowerShell counterpart of install.sh.

.DESCRIPTION
    Mirrors install.sh step for step, with two substitutions. The macOS-only steps
    (Xcode Command Line Tools architecture check, R.framework version symlink fix)
    have no Windows analogue and are dropped; in their place this script locates R
    the way Windows actually requires and verifies the rpy2 -> R bridge at the end.

    Three Windows-specific problems it handles, none of which exist on macOS/Linux:
      * The R installer does not add R to PATH, so `Get-Command Rscript` alone
        would fail on a perfectly good install. The registry is consulted next.
      * Non-interactive Rscript cannot answer R's "use a personal library?"
        prompt, so a fresh install fails at the first install.packages() unless
        the user library already exists. It is created up front.
      * rpy2 loads R.dll out of R_HOME. When that fails it fails at *import*,
        long before any statistics run, so the bridge is checked here rather
        than left for the user's first analysis.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File install.ps1
#>

$ErrorActionPreference = 'Stop'

Write-Host '=== kbstatpy installer (Windows) ==='
Write-Host ''

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

function Get-LastLine {
    # Native executables can emit more than the one line a probe expects (a
    # deprecation warning, say). Take the last line and normalise to a string,
    # so callers can .Trim()/-match it without tripping over an array.
    param($Value)
    if ($null -eq $Value) { return $null }
    return ([string](@($Value)[-1])).Trim()
}

function Invoke-Python {
    # Always goes through `-m` on the interpreter resolved below: pip.exe is
    # routinely absent from PATH on Windows even when Python itself is fine,
    # and `-m pip` cannot install into the wrong interpreter.
    #
    # Output is deliberately not collected into a variable here - that would
    # buffer pip's progress until the command finished, where install.sh shows
    # it live.
    param([string[]]$Arguments, [switch]$Quiet)
    $all = @($script:PythonArgs) + $Arguments
    if ($Quiet) { & $script:PythonExe @all 2>$null } else { & $script:PythonExe @all }
}

function Show-PythonHelp {
    # Named at every Python failure, so a user who has none, or too old a one,
    # is told where to get it rather than left to search.
    Write-Host '  Where to get Python 3.10+ (64-bit):'
    Write-Host '    winget:     winget install Python.Python.3.13'
    Write-Host '    Installer:  https://www.python.org/downloads/windows/'
    Write-Host '                (pick "Windows installer (64-bit)" and tick'
    Write-Host '                 "Add python.exe to PATH" on the first screen)'
    Write-Host '    The Microsoft Store stub named python.exe is not a Python'
    Write-Host '    installation and cannot be used.'
}

function Show-RHelp {
    Write-Host '  Where to get R 4.4+:'
    Write-Host '    winget:     winget install RProject.R'
    Write-Host '    Installer:  https://cran.r-project.org/bin/windows/base/'
    Write-Host '    Accept the default install location; this installer finds R'
    Write-Host '    through the registry, so no PATH entry is needed.'
}

function Show-RToolsHelp {
    Write-Host '  A package with no prebuilt binary has to compile, which needs Rtools:'
    Write-Host '    https://cran.r-project.org/bin/windows/Rtools/'
    Write-Host '    Install the version matching your R (Rtools44 for R 4.4, and so on).'
}

function Resolve-RHome {
    # PATH first (matches install.sh), then the registry keys the Windows
    # installer writes, then the default install location. R.home() is asked
    # rather than derived from the Rscript path, because that path may be either
    # bin\ or bin\x64\ depending on the R version.
    $cmd = Get-Command 'Rscript.exe' -ErrorAction SilentlyContinue
    if ($cmd) {
        $fromR = Get-LastLine (& $cmd.Source '-e' 'cat(R.home())' 2>$null)
        if ($LASTEXITCODE -eq 0 -and $fromR) { return $fromR }
    }

    # R64 before R, HKLM before HKCU: prefer the 64-bit build, and a
    # machine-wide install over a per-user one.
    foreach ($key in @('HKLM:\SOFTWARE\R-core\R64', 'HKLM:\SOFTWARE\R-core\R',
                       'HKCU:\SOFTWARE\R-core\R64', 'HKCU:\SOFTWARE\R-core\R')) {
        $path = (Get-ItemProperty -Path $key -Name 'InstallPath' -ErrorAction SilentlyContinue).InstallPath
        if ($path -and (Test-Path $path)) { return $path }
    }

    $root = Join-Path $env:ProgramFiles 'R'
    if (Test-Path $root) {
        $newest = Get-ChildItem -Path $root -Directory -ErrorAction SilentlyContinue |
                  Where-Object { $_.Name -match '^R-\d+\.\d+\.\d+$' } |
                  Sort-Object { [version]($_.Name -replace '^R-', '') } -Descending |
                  Select-Object -First 1
        if ($newest) { return $newest.FullName }
    }

    return $null
}

function Get-RScriptPath {
    # R >= 4.2 merged bin\x64 into bin\; the arch-specific paths are tried first
    # for R <= 4.1 compatibility. Same order rpy2 itself uses (openrlib.py).
    param([string]$RHome)
    foreach ($rel in @('bin\x64\Rscript.exe', 'bin\arm64\Rscript.exe', 'bin\Rscript.exe')) {
        $path = Join-Path $RHome $rel
        if (Test-Path $path) { return $path }
    }
    return $null
}

# ------------------------------------------------------------------
# 1. Check prerequisites
# ------------------------------------------------------------------

Write-Host '[1/4] Checking prerequisites...'

# A bare `python` on Windows is often the Microsoft Store stub, which exits
# non-zero instead of reporting a version - hence the version probe, and the
# fallback to the `py` launcher.
$script:PythonExe = $null
$script:PythonArgs = @()
$pythonVersion = $null

foreach ($candidate in @(@{ Exe = 'python'; Args = @() }, @{ Exe = 'py'; Args = @('-3') })) {
    if (-not (Get-Command $candidate.Exe -ErrorAction SilentlyContinue)) { continue }
    # chr(46) rather than a literal '.': PowerShell 5.1 re-quotes arguments on
    # their way to a native executable, so quote characters inside a -c snippet
    # are the one thing to keep out of it.
    $probe = Get-LastLine (& $candidate.Exe @($candidate.Args + @('-c', 'import sys; print(str(sys.version_info[0]) + chr(46) + str(sys.version_info[1]))')) 2>$null)
    if ($LASTEXITCODE -eq 0 -and $probe) {
        $script:PythonExe = $candidate.Exe
        $script:PythonArgs = $candidate.Args
        $pythonVersion = $probe
        break
    }
}

if (-not $script:PythonExe) {
    Write-Host 'ERROR: no working Python found.'
    Show-PythonHelp
    exit 1
}

if ([version]$pythonVersion -lt [version]'3.10') {
    Write-Host "ERROR: Python $pythonVersion found, but kbstatpy needs 3.10 or newer."
    Show-PythonHelp
    exit 1
}

# rpy2 ships win_amd64 wheels only, and a 32-bit interpreter cannot load a
# 64-bit R.dll in any case. Caught here because the failure would otherwise
# surface as an opaque import error much later.
$is64 = Get-LastLine (Invoke-Python -Arguments @('-c', 'import sys; print(sys.maxsize > 2**32)') -Quiet)
if ($is64 -and $is64 -ne 'True') {
    Write-Host "ERROR: this Python is 32-bit. rpy2 needs a 64-bit interpreter to load R's DLL."
    Show-PythonHelp
    exit 1
}

$rHome = Resolve-RHome
if (-not $rHome) {
    Write-Host 'ERROR: R not found (looked on PATH, in the registry, and under Program Files).'
    Show-RHelp
    exit 1
}

$rscript = Get-RScriptPath -RHome $rHome
if (-not $rscript) {
    Write-Host "ERROR: R found at $rHome but no Rscript.exe inside it."
    Write-Host '  The R installation looks incomplete. Reinstalling R should fix it.'
    Show-RHelp
    exit 1
}

$rVersionRaw = Get-LastLine (& $rscript '-e' 'cat(R.version.string)' 2>$null)
$rVersion = if ($rVersionRaw -match '\d+\.\d+\.\d+') { $Matches[0] } else { $null }

Write-Host "  Python $pythonVersion found ($script:PythonExe)"
if ($rVersion) {
    Write-Host "  R $rVersion found ($rHome)"
} else {
    Write-Host "  R found ($rHome), version not determined"
}

if ($rVersion -and ([version]$rVersion -lt [version]'4.4')) {
    Write-Host "ERROR: R $rVersion found, but kbstatpy needs 4.4 or newer."
    Write-Host '  glmmTMB and emmeans track current R closely; older R either cannot'
    Write-Host '  install them or installs versions that disagree with each other.'
    Show-RHelp
    exit 1
}

# ------------------------------------------------------------------
# 2. Install Python packages
# ------------------------------------------------------------------

Write-Host ''
Write-Host '[2/4] Installing Python packages...'

Invoke-Python -Arguments @('-m', 'pip', 'install', '--upgrade', 'pip', '--quiet')
if ($LASTEXITCODE -ne 0) {
    Write-Host 'ERROR: could not upgrade pip.'
    Write-Host '  If the error mentions permissions, install into a virtual environment:'
    Write-Host '    python -m venv $HOME\kbstatpy-env'
    Write-Host '    $HOME\kbstatpy-env\Scripts\Activate.ps1'
    Write-Host '  Then re-run this installer.'
    exit 1
}

# Editable (-e) so the install tracks this checkout - users can pull updates
# without reinstalling. $PSScriptRoot rather than '.', so the script also works
# when invoked from another working directory.
#
# install.sh pins great_tables==0.14.0 when the Xcode CLT are missing, because
# great_tables >= 0.15 pulls multimark, which then has to compile. No such pin
# is needed here: multimark publishes a win_amd64 wheel.
Invoke-Python -Arguments @('-m', 'pip', 'install', '-e', $PSScriptRoot)
if ($LASTEXITCODE -ne 0) {
    Write-Host ''
    Write-Host 'ERROR: installing the Python packages failed.'
    Write-Host '  If the error mentions a compiler or "building wheel", every dependency'
    Write-Host '  kbstatpy needs ships a Windows wheel, so this usually means pip could'
    Write-Host '  not reach PyPI, or the Python version is one with no wheels yet.'
    Write-Host '    Supported Python versions: 3.10 - 3.14'
    Write-Host '  If it mentions permissions, install into a virtual environment:'
    Write-Host '    python -m venv $HOME\kbstatpy-env'
    Write-Host '    $HOME\kbstatpy-env\Scripts\Activate.ps1'
    exit 1
}

Write-Host '  kbstatpy and Python packages installed.'

# ------------------------------------------------------------------
# 3. Install R packages
# ------------------------------------------------------------------

Write-Host ''
Write-Host '[3/4] Installing R packages...'

# Passed as a file rather than via `Rscript -e`: PowerShell 5.1 mangles quotes
# when it hands arguments to a native executable, and this snippet needs them.
$rCode = @'
pkgs <- c(
    "lme4", "lmerTest", "glmmTMB", "emmeans", "pbkrtest", "DHARMa",
    "tibble", "broom", "broom.mixed",
    "report", "see", "parameters", "performance",
    "effectsize", "insight", "datawizard", "bayestestR"
)

# R prompts to create a personal library on first use, which a non-interactive
# Rscript cannot answer - it errors out instead. Create the library up front and
# install into it explicitly. R_LIBS_USER may list several paths; take the first.
lib <- strsplit(Sys.getenv("R_LIBS_USER"), .Platform$path.sep)[[1]][1]
if (!is.na(lib) && nzchar(lib)) {
    if (!dir.exists(lib)) dir.create(lib, recursive = TRUE, showWarnings = FALSE)
    .libPaths(c(lib, .libPaths()))
} else {
    lib <- .libPaths()[1]
}

missing <- pkgs[!pkgs %in% installed.packages()[, "Package"]]
if (length(missing) > 0) {
    cat("Installing R packages:", paste(missing, collapse = ", "), "\n")
    cat("Library:", lib, "\n")
    install.packages(missing, lib = lib, repos = "https://cloud.r-project.org", quiet = TRUE)

    # install.packages() only warns on failure and Rscript still exits 0, so a
    # package with no Windows binary would install "successfully" and then blow
    # up at analysis time. Re-check instead of trusting the exit status.
    still <- missing[!missing %in% installed.packages()[, "Package"]]
    if (length(still) > 0) {
        cat("ERROR: these R packages failed to install:", paste(still, collapse = ", "), "\n")
        quit(status = 1)
    }
} else {
    cat("All R packages already installed.\n")
}
'@

$rScriptFile = Join-Path $env:TEMP 'kbstatpy_install_r.R'
Set-Content -Path $rScriptFile -Value $rCode -Encoding ASCII
try {
    & $rscript $rScriptFile
    if ($LASTEXITCODE -ne 0) {
        Write-Host ''
        Write-Host 'ERROR: installing the R packages failed.'
        Write-Host '  CRAN serves Windows binaries for all of them, so this is usually a'
        Write-Host '  network problem or a package with no binary for this R version.'
        Show-RToolsHelp
        exit 1
    }
} finally {
    Remove-Item $rScriptFile -ErrorAction SilentlyContinue
}

Write-Host '  R packages installed.'

# ------------------------------------------------------------------
# 4. Verify the rpy2 -> R bridge
# ------------------------------------------------------------------

Write-Host ''
Write-Host '[4/4] Verifying the rpy2 -> R bridge...'

# rpy2 normally finds R through the registry, but R_HOME is set explicitly for
# this check so it tests the R installation found above rather than whichever
# one the registry happens to name.
$env:R_HOME = $rHome

$pyCode = @'
import rpy2.robjects as ro
print("  rpy2 -> " + ro.r("R.version.string")[0])
# glmmTMB and emmeans are the two packages every non-Gaussian analysis needs.
# Loading them here turns a first-analysis failure into an install-time one.
ro.r("suppressMessages(library(glmmTMB))")
ro.r("suppressMessages(library(emmeans))")
print("  glmmTMB and emmeans load through the bridge")
import kbstatpy
print("  kbstatpy " + kbstatpy.__version__ + " imports")
'@

$pyScriptFile = Join-Path $env:TEMP 'kbstatpy_verify.py'
Set-Content -Path $pyScriptFile -Value $pyCode -Encoding ASCII
try {
    Invoke-Python -Arguments @($pyScriptFile)
    $verifyFailed = ($LASTEXITCODE -ne 0)
} finally {
    Remove-Item $pyScriptFile -ErrorAction SilentlyContinue
}

if ($verifyFailed) {
    Write-Host ''
    Write-Host 'ERROR: rpy2 could not start R. Things to check, in order:'
    Write-Host "  1. Both Python and R must be 64-bit (R at $rHome)."
    Write-Host '  2. Set R_HOME permanently for your account, then open a new shell:'
    Write-Host "       [Environment]::SetEnvironmentVariable('R_HOME', '$rHome', 'User')"
    Write-Host '  3. Reinstall rpy2 from a wheel:'
    Write-Host '       python -m pip install --force-reinstall --only-binary :all: rpy2'
    Write-Host '  4. Failing all that, install inside WSL and follow the Linux steps'
    Write-Host '     (see README.md).'
    exit 1
}

# ------------------------------------------------------------------
# Done
# ------------------------------------------------------------------

Write-Host ''
Write-Host '=== Installation complete ==='
Write-Host ''
Write-Host 'To verify, run any of the demos in the demos\scripts subfolder, e.g.'
Write-Host '  python demos\scripts\demo_01_unpaired.py'
Write-Host ''
