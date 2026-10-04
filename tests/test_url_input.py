#!/usr/bin/env python3
"""in_file may be a URL, including a share link without a file extension.

The guarded failure mode: a URL in options.in_file was resolved like a
relative path, so 'https://host/data.csv' became '/current/dir/https:/host/
data.csv' and failed as a missing file. Reading course data straight from a
sciebo (Nextcloud) share link was therefore impossible; students had to
download and re-upload every file. Such links usually end in /download, with
no extension, so the format has to come from the content: xlsx and xls are
recognised by their magic bytes, anything else is read as CSV.

A share link without /download returns the share's web page. pandas reads
that HTML as a table without complaint, which would make the error surface
much later as a missing column; it is rejected at the source with a hint.

Served from a local HTTP server, so no network is needed. Needs R only
because importing kbstatpy starts it.

Run:  python3 tests/test_url_input.py
"""
import contextlib
import http.server
import io
import os
import sys
import threading

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat            # noqa: E402
from kbstatpy.options import KbstatOptions    # noqa: E402

FAILED = []


def check(name, cond, detail=''):
    print(('PASS' if cond else 'FAIL'), name, detail)
    if not cond:
        FAILED.append(name)


rng = np.random.default_rng(0)
DF = pd.DataFrame({'y': rng.normal(5, 1, 12).round(3), 'g': ['a', 'b'] * 6})
CSV = DF.to_csv(index=False).encode()
_buf = io.BytesIO()
DF.to_excel(_buf, index=False)
XLSX = _buf.getvalue()
HTML = b'<!DOCTYPE html><html><head><title>sciebo</title></head><body>share</body></html>'
ROUTES = {'/data.csv': CSV, '/data.xlsx': XLSX, '/s/tok/download': CSV,
          '/s/tokx/download': XLSX, '/s/tok': HTML}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = ROUTES.get(self.path.split('?')[0])
        if body is None:
            self.send_error(404)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


srv = http.server.HTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f'http://127.0.0.1:{srv.server_address[1]}'


def load(url):
    o = KbstatOptions()
    o.in_file = url
    o.y = 'y'
    kb = Kbstat(o)
    kb._normalize_options()
    kb._load_data()
    return kb


for path, label in [('/data.csv', 'csv by extension'), ('/data.xlsx', 'xlsx by extension'),
                    ('/s/tok/download', 'csv share link, no extension'),
                    ('/s/tokx/download', 'xlsx share link, no extension')]:
    try:
        kb = load(BASE + path)
        check(label, kb.options.in_file == BASE + path
              and np.allclose(kb.data['y'].to_numpy(), DF['y'].to_numpy())
              and list(kb.data.columns) == ['y', 'g'])
    except Exception as e:
        check(label, False, repr(e))

for path, label, needle in [('/s/tok', 'share page rejected with a hint', '/download'),
                            ('/missing.csv', 'HTTP error reported', '404')]:
    try:
        load(BASE + path)
        check(label, False, 'no error raised')
    except ValueError as e:
        check(label, needle in str(e), str(e)[:90])

# end to end: a model fitted from a URL
o = KbstatOptions()
o.in_file = BASE + '/s/tok/download'
o.y, o.x = 'y', 'g'
o.figure_display = 'save_only'
kb = Kbstat(o)
with contextlib.redirect_stdout(io.StringIO()):
    kb.run()
check('model fitted from a share link', kb.anova_table is not None and len(kb.anova_table) == 1)

srv.shutdown()
if FAILED:
    print(f'\n{len(FAILED)} FAILED: {FAILED}')
    sys.exit(1)
print('\nall passed')
