# Installing kbstatpy

kbstatpy fits its models in R, so it needs Python **and** R with a handful of R packages. There are three ways to get there; pick the one that fits.

| Where | Install | Account | Files |
|---|---|---|---|
| [Your own computer](#your-own-computer) | once, with an installer script | none | on your computer |
| [Google Colab](#google-colab) | nothing; a setup cell runs in every session (~1-2 min) | Google | vanish when the session ends, unless downloaded or on Drive |
| [A JupyterHub](#jupyterhub), such as a university's | once, with one command (a few minutes) | the hub's, e.g. your university login | stay in your home folder |

## Contents

- [Requirements](#requirements)
- [Your own computer](#your-own-computer)
  - [macOS / Linux](#macos--linux)
  - [Windows](#windows)
  - [What the installers do](#what-the-installers-do)
  - [If the Windows install fails](#if-the-windows-install-fails)
- [Google Colab](#google-colab)
- [JupyterHub](#jupyterhub)
  - [Step by step](#step-by-step)
  - [Update, start afresh, remove](#update-start-afresh-remove)
  - [If something goes wrong on the hub](#if-something-goes-wrong-on-the-hub)

## Requirements

- Python 3.10+ (64-bit)
- R 4.4+
- **Platform:** macOS, Linux, or Windows. macOS and Linux are the routinely tested platforms; native Windows is supported by `install_windows.ps1`, with [WSL](https://learn.microsoft.com/windows/wsl/install) as a fallback.

All Python and R package dependencies are handled by the installers. On Colab and on a JupyterHub, Python and R come with the platform or the installer; nothing has to be set up beforehand.

## Your own computer

### macOS / Linux

```bash
cd kbstatpy
bash install_mac_linux.sh
```

### Windows

```powershell
cd kbstatpy
powershell -ExecutionPolicy Bypass -File install_windows.ps1
```

**Anaconda / Miniconda, or a venv:** activate the environment you want *first* and the installer uses it — no extra flag needed. This works from the Anaconda Prompt as well as from PowerShell, since the installer reads `CONDA_PREFIX` / `VIRTUAL_ENV` and those survive into the `powershell` call:

```powershell
conda create -n kbstatpy python=3.13
conda activate kbstatpy
powershell -ExecutionPolicy Bypass -File install_windows.ps1
```

The installer prints the full path of the interpreter it is about to write to before it installs anything, and names the conda environment or venv it belongs to — so nothing lands in an environment you did not mean. With none activated it installs into the interpreter it finds and says so. To pick one without activating it, pass `-Python` (a path to `python.exe`, or the environment folder, or a command name to look up on `PATH`):

```powershell
powershell -ExecutionPolicy Bypass -File install_windows.ps1 -Python C:\Users\me\anaconda3\envs\kbstatpy\python.exe
```

Only Python is installed per environment. The R packages go into your R user library and are shared by every environment, which is what you want: they are the same packages either way.

### What the installers do

Both installers for your own computer (the JupyterHub one is described [below](#update-start-afresh-remove)):
1. Checks the prerequisites and **stops with instructions if one is missing or too old** — which package manager command or download page to use for Python 3.10+ and R 4.4+ on your platform, rather than a failure further down that does not name the cause
2. Installs **kbstatpy** and its Python dependencies (`pymer4`, `rpy2`, `pandas`, `scipy`, `sympy`, `seaborn`, `openpyxl`, …) from `pyproject.toml`, so `import kbstatpy` works from any directory
3. Installs all required R packages (`lme4`, `lmerTest`, `glmmTMB`, `emmeans`, `DHARMa`, …)
4. Verifies that `rpy2` can actually start R and load `glmmTMB` and `emmeans`, so a broken bridge is reported here instead of part-way through your first analysis

Plus what the platform needs on top of that:
- **macOS:** fixes the `rpy2` / R version symlink if needed, and warns about a mismatched Xcode Command Line Tools architecture
- **Windows:** installs into the activated conda environment or venv if there is one (and reports which), finds R through the registry (the R installer does not add R to `PATH`, so there is nothing to configure by hand), and creates the personal R library that a non-interactive `Rscript` cannot create on demand. `import kbstatpy` then adds R's own library folder (`<R_HOME>\bin\x64`) to the search path of that Python process, so R can load the DLLs it fetches lazily, `Rlapack` above all; nothing has to be set by hand for this either

On Windows nothing needs to be compiled: `rpy2` installs from a prebuilt `win_amd64` wheel, and CRAN serves the R packages as Windows binaries, so Rtools is not required.

On **Linux** the opposite holds: CRAN serves Linux packages as source only, so a cold install compiles the whole dependency closure — around 130 packages, a quarter of an hour — and needs a C/C++/Fortran toolchain plus libcurl, OpenSSL, libuv, zlib and ICU in their `-dev`/`-devel` form (`sudo apt install r-base-dev build-essential libcurl4-openssl-dev libssl-dev libuv1-dev zlib1g-dev libicu-dev cmake` on Debian/Ubuntu). `DHARMa` is the package that needs most of them, by way of `gap` → `plotly` → `httr` → `curl` and `qgam` → `shiny` → `bslib` → `sass` → `fs`, so a missing header shows up as a `DHARMa` failure that looks unrelated to anything network- or filesystem-shaped. `install_mac_linux.sh` names the command for your distribution if a build fails.

To avoid compiling altogether, point R at a binary repository — [Posit Package Manager](https://packagemanager.posit.co/client/#/repos/cran/setup) serves prebuilt packages for the common distributions — and put the `options(repos = ...)` line it gives you in `~/.Rprofile`. `install_mac_linux.sh` installs from whatever repository R is configured with, and falls back to CRAN when that is nothing.

Native Windows support is recent — earlier versions of `rpy2` could not be installed there reliably, and this README said so. If a native install does give trouble, run the macOS/Linux steps inside a [WSL](https://learn.microsoft.com/windows/wsl/install) shell (e.g. Ubuntu) instead, and please open an issue.

### If the Windows install fails

The messages below are the common ones on Windows. Each is followed by what it means and what to do.

> **`python.exe : Python was not found; run without arguments to install from the Microsoft Store`**
> PowerShell found the Microsoft Store placeholder named `python.exe` instead of your Python — usually because Anaconda is installed but no environment is activated in the shell you called from. Activate one, or pass `-Python`, as above. (Up to version 1.15.0 the installer aborted here with a `NativeCommandError` instead of moving on to the next interpreter; fixed in 1.15.1.)

> **`unable to load shared object '...\library\stats\libs\x64\stats.dll': LoadLibrary failure: The specified module could not be found`**
> R started (`rpy2` even reports its version) but cannot load its own libraries. The file it names is present; the R DLLs beside `R.dll` that it depends on are not on the search path, because R installs itself without touching `PATH`. From version 1.15.7 `import kbstatpy` puts them there itself. On an older version, or if it persists, set it for your account and open a new shell (with your own R version in the path):
> ```powershell
> $p = [Environment]::GetEnvironmentVariable('Path', 'User')
> [Environment]::SetEnvironmentVariable('Path', $p + ';C:\Program Files\R\R-4.6.1\bin\x64', 'User')
> ```

> **`UnicodeDecodeError: 'utf-8' codec can't decode byte ...` while R prints a message**
> R is reporting in a language whose accented characters `rpy2` cannot decode, so the real message is lost behind this one. Switch R to English and open a new shell: `[Environment]::SetEnvironmentVariable('LANGUAGE', 'en', 'User')`.

## Google Colab

Nothing to install: open a notebook in the browser and run it top to bottom. Its first cell installs kbstatpy and the R packages (~1-2 min) into the Colab runtime, which forgets everything when the session ends, so the setup runs again next time. A Google account is needed.

- **Your own data:** the [template notebook](https://colab.research.google.com/github/kimbostroem/kbstatpy/blob/master/analysis_template.ipynb): setup, upload, options, run, download.
- **The demos:** the [guided playground](https://colab.research.google.com/github/kimbostroem/kbstatpy/blob/master/demos/kbstatpy_colab.ipynb), or any demo from the [list in the README](README.md#try-the-demos-on-google-colab).

Uploads and results vanish with the runtime: download the results zip (it includes `analysis.py`, the script that reruns the analysis), or mount Google Drive.

## JupyterHub

A JupyterHub is a Jupyter server run by an institution, used in the browser with that institution's login. kbstatpy installs there **once** into your home folder, which persists, so files and installation stay between sessions. No Google account is involved, and the data stay on the institution's servers.

It works on any hub that offers a terminal and conda or mamba. It was set up and tested on [JupyterHub.nrw](https://www.jupyterhub.nrw), the hub of the universities in North Rhine-Westphalia; at the University of Münster that is <https://uni-muenster.jupyterhub.nrw>, with the university login.

### Step by step

**Once: install**

1. **Log in and start an environment.** On JupyterHub.nrw choose **Data Science** (it has Python and R); 0.5-4 vCPU is plenty.
2. **Open a terminal.** On the Launcher page, click **Terminal** (not "Desktop Terminal").
3. **Run the installer.** Paste this line and press Enter:

   ```bash
   curl -sSL https://raw.githubusercontent.com/kimbostroem/kbstatpy/master/install_jupyterhub.sh | bash
   ```

   The first time it takes a few minutes. It shows its progress in five numbered steps (`==> [1/5]` to `==> [5/5]`); the second, Python and R with all R packages, is the long one, and shows a line *… still working* every 20 seconds. It is finished when a framed message says **kbstatpy is installed** and the input line (ending in `$`) is back. Leave the tab open until then. If it says *Something went wrong* instead, run the same command once more: it completes what is missing.
4. **Reload the page** in the browser (F5, or Cmd+R on a Mac). The Launcher now has a **kbstatpy** tile under *Notebook*. Closing the terminal tab is fine; nothing is lost.

**Every time: analyse**

5. **Open a notebook with the kbstatpy kernel:** click the **kbstatpy** tile. In a notebook that is already open: *Kernel → Change Kernel → kbstatpy*; the kernel's name shows at the top right.
6. **Bring in the data:** upload the file with the arrow button in the file browser on the left, or read it from a link (`options.in_file` takes a URL; for a sciebo/Nextcloud share the link ending in `/download`). A sciebo connected to the hub appears as `~/sciebo`, and `in_file` can point there directly, for example `'~/sciebo/my_data.csv'`.
7. **Run kbstatpy.** A first check, in a cell (Shift+Enter runs it):

   ```python
   from kbstatpy import Kbstat, KbstatOptions
   print(Kbstat)
   ```

   The import says *kbstatpy: starting R …* and, when it is done, *kbstatpy … ready*: the first time in a session that takes up to a minute, while R starts. The very first import ever also prints *Matplotlib is building the font cache*, once. After Shift+Enter the cursor jumps to a new, empty cell; the number in brackets appears to the left of the cell that ran. Then fill in the options and run, or upload the [template notebook](analysis_template.ipynb) and work through it with the kbstatpy kernel. Its setup cell recognises the hub: without kbstatpy in the kernel it runs the installer of step 3 itself and then says to switch the kernel.

A cell is finished when `[*]` to its left has turned into a number.

### Update, start afresh, remove

- **Update kbstatpy, or repair an interrupted installation:** run the command of step 3 again. It keeps the existing environment, adds whatever is missing, and installs the newest kbstatpy. Restart the kernel afterwards (*Kernel → Restart Kernel*).
- **Start afresh:** `rm -rf ~/envs/kbstat`, then step 3 again.
- **Remove:** `rm -rf ~/envs/kbstat ~/.local/share/jupyter/kernels/kbstat`.

What the installer sets up: a conda environment in `~/envs/kbstat` with Python, R and the R packages, all from conda-forge as matching binaries (nothing is compiled); kbstatpy from GitHub; and the Jupyter kernel *kbstatpy*, which points `R_HOME` at that environment's R. Another location: `KBSTATPY_ENV=~/somewhere bash install_jupyterhub.sh`.

### If something goes wrong on the hub

The installer avoids the first three. They are listed for anyone installing by hand, and to recognise them.

> **`CondaValueError: You have chosen a non-default solver backend (libmamba) but it was not recognized`**
> The hub's conda asks for a solver it does not have. Use `mamba` instead of `conda`; where there is no mamba, the installer fetches `micromamba` into `~/bin`.

> **`critical libmamba filesystem error: cannot create directories: Read-only file system [/opt/conda/envs/...]`**
> `-n name` puts the environment into the system's folder, which is read-only. Create it by path in the home folder instead: `-p ~/envs/kbstat`.

> **`PackageNotInstalledError: The R package "broom.mixed" is not installed`**, with many lines *library '…' contains no packages*
> The kernel starts the hub's own R (the one for RStudio) instead of the environment's. Register the kernel with `R_HOME`, then restart the kernel:
> ```bash
> ~/envs/kbstat/bin/python -m ipykernel install --user --name kbstat --display-name "kbstatpy" --env R_HOME ~/envs/kbstat/lib/R
> ```
> To check which R runs: `import rpy2.robjects as ro; print(ro.r('R.home()')[0])` should end in `envs/kbstat/lib/R`.

> **`ModuleNotFoundError: No module named 'kbstatpy'`**
> The notebook runs a different kernel. Switch to *kbstatpy* (top right, or *Kernel → Change Kernel*).

> **Odd errors after reinstalling, such as `No module named 'stack_data'`**
> A notebook kept running on the old installation while it was deleted or replaced. Restart its kernel (*Kernel → Restart Kernel*), or close the notebook and open a new one.

> **No kbstatpy tile after the installation**
> Reload the page once more. If it is still missing, run the command of step 3 again and read its last lines.
