#Requires -Version 5.1
<#
.SYNOPSIS
    kbstatpy installer for native Windows - the PowerShell counterpart of install.sh.

.DESCRIPTION
    Mirrors install.sh step for step, with two substitutions. The macOS-only steps
    (Xcode Command Line Tools architecture check, R.framework version symlink fix)
    have no Windows analogue and are dropped; in their place this script locates R
    the way Windows actually requires and verifies the rpy2 -> R bridge at the end.

    Four Windows-specific problems it handles, none of which exist on macOS/Linux:
      * PowerShell 5.1 treats anything a native executable writes to stderr as an
        error record, so every external call is routed through Invoke-Native /
        Get-NativeLine (see the comment there).
      * The R installer does not add R to PATH, so `Get-Command Rscript` alone
        would fail on a perfectly good install. The registry is consulted next.
      * Non-interactive Rscript cannot answer R's "use a personal library?"
        prompt, so a fresh install fails at the first install.packages() unless
        the user library already exists. It is created up front.
      * rpy2 loads R.dll out of R_HOME. When that fails it fails at *import*,
        long before any statistics run, so the bridge is checked here rather
        than left for the user's first analysis.

    Anaconda and venv users: activate the environment first and the installer
    picks it up on its own (it reads CONDA_PREFIX / VIRTUAL_ENV, so it works
    from the Anaconda Prompt as well as from PowerShell). It always prints which
    interpreter it is installing into before it installs anything.

.PARAMETER Python
    The Python interpreter to install into - a full path to python.exe, or a
    command name to resolve on PATH. Use it when several Pythons are installed
    and no environment is active. Without it the installer takes the active
    conda/venv interpreter, then `python`, then the `py -3` launcher.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File install.ps1

.EXAMPLE
    # Into a specific Anaconda environment (from the Anaconda Prompt):
    #   conda activate ankle-instability
    #   powershell -ExecutionPolicy Bypass -File install.ps1

.EXAMPLE
    # Into a specific interpreter, no activation needed:
    powershell -ExecutionPolicy Bypass -File install.ps1 -Python C:\Users\me\anaconda3\envs\ankle\python.exe
#>

param(
    [string]$Python
)

$ErrorActionPreference = 'Stop'

Write-Host '=== kbstatpy installer (Windows) ==='
Write-Host ''

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

function Invoke-Native {
    # Runs an external program, streaming its output the way a shell would.
    #
    # Every native call in this script goes through here or Get-NativeLine, for
    # one reason: PowerShell 5.1 wraps whatever a native executable writes to
    # stderr in an error record, and under $ErrorActionPreference = 'Stop' that
    # record is *terminating* - it aborts the installer. Redirecting with
    # 2>$null does not help, because the record is raised before the
    # redirection discards the text. Resetting the preference inside these two
    # functions scopes the change to them and leaves cmdlet error handling in
    # the rest of the script strict.
    #
    # Both halves of that were live bugs, not hypotheticals. The Microsoft
    # Store python.exe placeholder prints "Python was not found" to stderr,
    # which killed the installer at the first probe instead of moving on to the
    # next candidate; and R prints its download progress to stderr, which would
    # have killed step 3 on any machine that got that far.
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [string[]]$Arguments = @()
    )
    $ErrorActionPreference = 'Continue'
    & $Exe @Arguments
}

function Get-NativeLine {
    # As Invoke-Native, but captures stdout and returns its last line, with
    # stderr discarded. Native executables can emit more than the one line a
    # probe expects (a deprecation warning, say), so the last line is taken and
    # normalised to a string - callers can then .Trim()/-match it without
    # tripping over an array. $LASTEXITCODE is set by the engine and stays
    # readable by the caller.
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [string[]]$Arguments = @()
    )
    $ErrorActionPreference = 'Continue'
    $out = & $Exe @Arguments 2>$null
    if ($null -eq $out) { return $null }
    return ([string](@($out)[-1])).Trim()
}

function Invoke-Python {
    # Always goes through `-m` on the interpreter resolved below: pip.exe is
    # routinely absent from PATH on Windows even when Python itself is fine,
    # and `-m pip` cannot install into the wrong interpreter.
    #
    # Output is deliberately streamed rather than collected - that would buffer
    # pip's progress until the command finished, where install.sh shows it live.
    param([string[]]$Arguments)
    Invoke-Native -Exe $script:PythonExe -Arguments (@($script:PythonArgs) + $Arguments)
}

function Show-PythonHelp {
    # Named at every Python failure, so a user who has none, or too old a one,
    # is told where to get it rather than left to search.
    Write-Host '  Where to get Python 3.10+ (64-bit):'
    Write-Host '    winget:     winget install Python.Python.3.13'
    Write-Host '    Installer:  https://www.python.org/downloads/windows/'
    Write-Host '                (pick "Windows installer (64-bit)" and tick'
    Write-Host '                 "Add python.exe to PATH" on the first screen)'
    Write-Host '    Anaconda:   already fine - activate the environment you want'
    Write-Host '                (conda activate <env>) and re-run this installer,'
    Write-Host '                or pass -Python <path to that env>\python.exe'
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

function Get-ActiveEnvironment {
    # An activated conda env or venv is the interpreter the user means, and
    # naming its python.exe explicitly is what makes the "installing into" line
    # below trustworthy: a Windows PATH can put the Microsoft Store alias ahead
    # of the environment, and `python` would then resolve to the wrong thing.
    #
    # conda activate and venv's Activate.ps1 both export real environment
    # variables, so these are visible even when the installer is launched as a
    # child process from the Anaconda Prompt.
    if ($env:CONDA_PREFIX) {
        # CONDA_DEFAULT_ENV is the name conda itself uses ('base', 'ankle'); the
        # directory leaf is only a good name for a named env, and reads as
        # 'anaconda3' for base.
        $name = if ($env:CONDA_DEFAULT_ENV) { $env:CONDA_DEFAULT_ENV } else { Split-Path $env:CONDA_PREFIX -Leaf }
        # conda puts python.exe in the environment root on Windows, not in bin/.
        return @{ Root = $env:CONDA_PREFIX; Kind = 'conda environment'; Name = $name
                  Exe  = (Join-Path $env:CONDA_PREFIX 'python.exe') }
    }
    if ($env:VIRTUAL_ENV) {
        return @{ Root = $env:VIRTUAL_ENV; Kind = 'virtual environment'
                  Name = (Split-Path $env:VIRTUAL_ENV -Leaf)
                  Exe  = (Join-Path $env:VIRTUAL_ENV 'Scripts\python.exe') }
    }
    return $null
}

function Resolve-RHome {
    # PATH first (matches install.sh), then the registry keys the Windows
    # installer writes, then the default install location. R.home() is asked
    # rather than derived from the Rscript path, because that path may be either
    # bin\ or bin\x64\ depending on the R version.
    $cmd = Get-Command 'Rscript.exe' -ErrorAction SilentlyContinue
    if ($cmd) {
        $fromR = Get-NativeLine -Exe $cmd.Source -Arguments @('-e', 'cat(R.home())')
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

$active = Get-ActiveEnvironment

# Candidates in order of how specific they are: an explicit -Python, then the
# activated environment, then whatever PATH and the py launcher offer. A bare
# `python` on Windows is often the Microsoft Store placeholder, which exits
# non-zero instead of reporting a version - hence the version probe rather than
# a mere existence check, and the fallback to `py`.
$candidates = @()
if ($Python) {
    $resolved = $null
    if (Test-Path -LiteralPath $Python -PathType Container) {
        # A directory is the natural mistake, because that is how an
        # environment is named everywhere else (conda activate <dir>, the env
        # path in the Anaconda Navigator). Accept it: python.exe sits in the
        # root of a conda env and in Scripts\ of a venv.
        foreach ($rel in @('python.exe', 'Scripts\python.exe')) {
            $probePath = Join-Path $Python $rel
            if (Test-Path -LiteralPath $probePath) { $resolved = (Resolve-Path -LiteralPath $probePath).Path; break }
        }
        if (-not $resolved) {
            Write-Host "ERROR: -Python '$Python' is a folder with no python.exe in it"
            Write-Host '  (looked for python.exe and Scripts\python.exe inside it).'
            Show-PythonHelp
            exit 1
        }
    } elseif (Test-Path -LiteralPath $Python) {
        $resolved = (Resolve-Path -LiteralPath $Python).Path
    } else {
        # A -Python given as a command name rather than a path is resolved on
        # PATH like any other command.
        $cmd = Get-Command $Python -ErrorAction SilentlyContinue
        if ($cmd) { $resolved = $cmd.Source }
    }
    if (-not $resolved) {
        Write-Host "ERROR: -Python '$Python' is neither a file nor a command this shell can find."
        Show-PythonHelp
        exit 1
    }
    $candidates += @{ Exe = $resolved; Args = @() }
} else {
    if ($active -and (Test-Path $active.Exe)) {
        $candidates += @{ Exe = $active.Exe; Args = @() }
    }
    $candidates += @{ Exe = 'python'; Args = @() }
    $candidates += @{ Exe = 'py';     Args = @('-3') }
}

$script:PythonExe = $null
$script:PythonArgs = @()
$pythonVersion = $null
$storeStubSeen = $false

foreach ($candidate in $candidates) {
    $cmd = Get-Command $candidate.Exe -ErrorAction SilentlyContinue
    if (-not $cmd) { continue }
    # chr(46) rather than a literal '.': PowerShell 5.1 re-quotes arguments on
    # their way to a native executable, so quote characters inside a -c snippet
    # are the one thing to keep out of it.
    $probe = Get-NativeLine -Exe $candidate.Exe -Arguments @($candidate.Args + @('-c', 'import sys; print(str(sys.version_info[0]) + chr(46) + str(sys.version_info[1]))'))
    if ($LASTEXITCODE -eq 0 -and $probe -match '^\d+\.\d+$') {
        $script:PythonExe = $candidate.Exe
        $script:PythonArgs = $candidate.Args
        $pythonVersion = $probe
        break
    }
    # Remember a rejected Store placeholder, so the failure below can name the
    # actual problem instead of claiming there is no Python at all.
    if ($cmd.Source -and $cmd.Source -like '*\WindowsApps\*') { $storeStubSeen = $true }
}

if (-not $script:PythonExe) {
    if ($Python) {
        Write-Host "ERROR: '$Python' is not a working Python interpreter."
    } elseif ($storeStubSeen) {
        Write-Host 'ERROR: no working Python found. The python.exe on PATH is the Microsoft'
        Write-Host '  Store placeholder, which only prints "Python was not found".'
        Write-Host '  If you use Anaconda, activate the environment you want and re-run:'
        Write-Host '    conda activate <env>'
        Write-Host '    powershell -ExecutionPolicy Bypass -File install.ps1'
        Write-Host '  Or point the installer straight at an interpreter:'
        Write-Host '    powershell -ExecutionPolicy Bypass -File install.ps1 -Python <path>\python.exe'
    } else {
        Write-Host 'ERROR: no working Python found.'
    }
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
$is64 = Get-NativeLine -Exe $script:PythonExe -Arguments (@($script:PythonArgs) + @('-c', 'import sys; print(sys.maxsize > 2**32)'))
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

$rVersionRaw = Get-NativeLine -Exe $rscript -Arguments @('-e', 'cat(R.version.string)')
$rVersion = if ($rVersionRaw -match '\d+\.\d+\.\d+') { $Matches[0] } else { $null }

# Which interpreter is about to be written to, spelled out. On a machine with
# Anaconda plus a python.org install plus the Store alias, "Python 3.12 found"
# alone does not say where the packages are going, and the user finds out only
# when `import kbstatpy` fails in the environment they meant to use.
$pythonPath = Get-NativeLine -Exe $script:PythonExe -Arguments (@($script:PythonArgs) + @('-c', 'import sys; print(sys.executable)'))
Write-Host "  Python $pythonVersion found"
Write-Host "    $pythonPath"
if ($active -and $pythonPath -and $pythonPath.StartsWith($active.Root, [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Host "    installing into the active $($active.Kind) '$($active.Name)'"
    if ($active.Kind -eq 'conda environment' -and $active.Name -eq 'base') {
        Write-Host '    (that is conda base, shared by every environment that inherits from'
        Write-Host '     it - conda create -n <name> ... for a project-specific one instead)'
    }
} elseif ($active) {
    Write-Host "    WARNING: the active $($active.Kind) is '$($active.Name)'"
    Write-Host "             ($($active.Root)) but the interpreter above is outside it,"
    Write-Host '             so kbstatpy will NOT be installed into that environment.'
} else {
    Write-Host '    no conda environment or venv is active, so this installs into that'
    Write-Host '    interpreter itself. To keep kbstatpy and its dependencies isolated,'
    Write-Host '    activate an environment first and re-run:'
    Write-Host '      conda create -n kbstatpy python=3.13'
    Write-Host '      conda activate kbstatpy'
    Write-Host '      (or)  python -m venv $HOME\kbstatpy-env'
    Write-Host '            $HOME\kbstatpy-env\Scripts\Activate.ps1'
}
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
    Write-Host '  If the error mentions permissions, install into an environment instead:'
    Write-Host '    conda create -n kbstatpy python=3.13'
    Write-Host '    conda activate kbstatpy'
    Write-Host '    (or)  python -m venv $HOME\kbstatpy-env'
    Write-Host '          $HOME\kbstatpy-env\Scripts\Activate.ps1'
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
    Write-Host '  If it mentions permissions, install into an environment instead:'
    Write-Host '    conda create -n kbstatpy python=3.13'
    Write-Host '    conda activate kbstatpy'
    Write-Host '    (or)  python -m venv $HOME\kbstatpy-env'
    Write-Host '          $HOME\kbstatpy-env\Scripts\Activate.ps1'
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
    Invoke-Native -Exe $rscript -Arguments @($rScriptFile)
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
if ($active -and $pythonPath -and $pythonPath.StartsWith($active.Root, [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Host "kbstatpy is installed in the $($active.Kind) '$($active.Name)'."
    Write-Host 'Activate it in any new shell before using kbstatpy.'
    Write-Host ''
}
Write-Host 'To verify, run any of the demos in the demos\scripts subfolder, e.g.'
Write-Host '  python demos\scripts\demo_01_unpaired.py'
Write-Host ''
