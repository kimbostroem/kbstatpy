#!/usr/bin/env python3
"""Build analysis_template.ipynb from analysis_template.py.

The notebook is the template for people who run kbstatpy on Google Colab (or
any Jupyter server): set up, upload the data, fill in the options, run,
download. Its options cell is the body of analysis_template.py, so the option
list is written once; tests/test_analysis_template.py fails if the committed
notebook no longer matches what this script builds.

Run after every change to analysis_template.py:

    python3 demos/make_template_notebook.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, 'analysis_template.py')
NOTEBOOK = os.path.join(ROOT, 'analysis_template.ipynb')

COLAB_URL = ('https://colab.research.google.com/github/kimbostroem/kbstatpy/'
             'blob/master/analysis_template.ipynb')

# The script's base_dir block anchors paths to the script's folder. A notebook
# has no script file, and on Colab the uploaded data sits in the working
# directory, so the block goes and in_file becomes a plain file name.
BASE_DIR_BLOCK = re.compile(
    r"# Anchor in_file and out_dir.*?\noptions\.base_dir = 'script_dir'\n\n", re.S)
IN_FILE_LINE = re.compile(r"^options\.in_file = 'data/my_data\.csv'.*$", re.M)
IN_FILE_NOTEBOOK = ("options.in_file = 'my_data.csv'".ljust(44)
                    + "# the uploaded file's name, .csv or .xlsx, one row per observation")
OUT_DIR_COMMENT = re.compile(r"(?<=^options\.out_dir = 'results/my_analysis'     # created if missing, )relative to base_dir$", re.M)
RUN_LINE = re.compile(r"^# -+\nKbstat\(options\)\.run_save\(\).*\n?\Z", re.M)


def options_cell(src):
    """The template body from `from kbstatpy import` up to the run line."""
    body = src[src.index('from kbstatpy import'):]
    for pattern, repl in ((BASE_DIR_BLOCK, ''), (IN_FILE_LINE, IN_FILE_NOTEBOOK),
                          (OUT_DIR_COMMENT, 'in the working directory'),
                          (RUN_LINE, '')):
        body, n = pattern.subn(repl, body)
        if n != 1:
            raise RuntimeError(
                f'analysis_template.py changed shape: {pattern.pattern!r} matched '
                f'{n} times, expected once. Update make_template_notebook.py.')
    return body.rstrip() + '\n'


INTRO = f"""# kbstatpy: your own analysis

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)]({COLAB_URL})

A template for analysing **your own data** with
[kbstatpy](https://github.com/kimbostroem/kbstatpy) on Google Colab. Run the cells
from top to bottom:

1. **Setup** installs kbstatpy and its R packages (~1-2 min, once per session).
2. **Upload** your data file (`.csv` or `.xlsx`, one row per observation) and
   see its columns.
3. **Options**: fill in the file name and your column names.
4. **Run** fits the model and shows tables and figures.
5. **Download** the results as a zip file.

> **Files vanish with the runtime.** Uploads and results are deleted when the
> Colab session ends. To keep them, mount your Google Drive (Drive icon in the
> Files pane on the left) and use paths such as
> `/content/drive/MyDrive/stats/my_data.csv`.
>
> **Whose notebook is this?** The moment you run or edit a cell, Colab keeps a
> private copy in your own Google account (*File → Save a copy in Drive*)."""

SETUP_MD = """## 1. Setup

Installs kbstatpy and the R packages it relies on. Does nothing outside Colab,
where kbstatpy is expected to be installed already."""

SETUP_CODE = """import sys
if 'google.colab' in sys.modules:
    !curl -sSL https://raw.githubusercontent.com/kimbostroem/kbstatpy/master/demos/colab_setup.sh | bash"""

UPLOAD_MD = """## 2. Upload your data

Run the cell and pick your file. It lands in `/content`, the notebook's working
directory, so the options below find it by its plain file name. The cell then
shows the columns and the first rows, which you need for the options.

Alternatively, drag the file into the Files pane (folder icon on the left)."""

UPLOAD_CODE = """import sys
import pandas as pd

if 'google.colab' in sys.modules:
    from google.colab import files
    uploaded = list(files.upload())
else:
    uploaded = []
    print('Not on Colab: put your data file next to this notebook.')

for name in uploaded:
    data = pd.read_excel(name) if name.endswith(('.xlsx', '.xls')) else pd.read_csv(name)
    print(f'{name}: {len(data)} rows, columns: {", ".join(data.columns)}')
    display(data.head())"""

OPTIONS_MD = """## 3. Options

Set `in_file` to the uploaded file's name and `y`, `x` and `id` to your column
names. Every commented-out line shows the value kbstatpy uses anyway: uncomment
a line only to change it, and delete what you do not need. Full reference:
[options table](https://github.com/kimbostroem/kbstatpy#options-reference) and
[statistical notes](https://github.com/kimbostroem/kbstatpy/blob/master/STATISTICAL_NOTES.md)."""

RUN_MD = """## 4. Run

Fits the model, tests it, shows tables and figures, and writes everything to
`out_dir`. Rerun this cell after changing the options.

The options cell goes into `out_dir` too, as `analysis.py`: a script that
reruns exactly this analysis (`python3 analysis.py`, started from the folder
that holds the data file), so the results never get separated from the code
that made them."""

RUN_CODE = """kb = Kbstat(options)
kb.run_save();"""


DOWNLOAD_MD = """## 5. Download the results

Zips `out_dir`, results and `analysis.py`, and downloads it. The files are
also visible in the Files pane, where a right-click downloads a single one."""

DOWNLOAD_CODE = """import shutil, sys

archive = shutil.make_archive(options.out_dir.rstrip('/'), 'zip', options.out_dir)
if 'google.colab' in sys.modules:
    from google.colab import files
    files.download(archive)
else:
    print('Results zipped to', archive)"""


def lines(text):
    parts = text.split('\n')
    return [p + '\n' for p in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


def cell(kind, cid, text):
    c = {'cell_type': kind, 'id': cid, 'metadata': {}, 'source': lines(text)}
    if kind == 'code':
        c.update(execution_count=None, outputs=[])
    return c


def build():
    src = open(TEMPLATE, encoding='utf-8').read()
    cells = [
        cell('markdown', 'intro', INTRO),
        cell('markdown', 'setup-md', SETUP_MD),
        cell('code', 'setup-code', SETUP_CODE),
        cell('markdown', 'upload-md', UPLOAD_MD),
        cell('code', 'upload-code', UPLOAD_CODE),
        cell('markdown', 'options-md', OPTIONS_MD),
        cell('code', 'options-code', options_cell(src)),
        cell('markdown', 'run-md', RUN_MD),
        cell('code', 'run-code', RUN_CODE),
        cell('markdown', 'download-md', DOWNLOAD_MD),
        cell('code', 'download-code', DOWNLOAD_CODE),
    ]
    nb = {'cells': cells,
          'metadata': {'colab': {'provenance': [], 'toc_visible': True},
                       'kernelspec': {'display_name': 'Python 3', 'language': 'python',
                                      'name': 'python3'},
                       'language_info': {'name': 'python'}},
          'nbformat': 4, 'nbformat_minor': 5}
    return json.dumps(nb, indent=1, ensure_ascii=False) + '\n'


if __name__ == '__main__':
    with open(NOTEBOOK, 'w', encoding='utf-8') as f:
        f.write(build())
    print('Wrote', os.path.relpath(NOTEBOOK, ROOT))
