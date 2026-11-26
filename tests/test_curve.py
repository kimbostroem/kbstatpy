#!/usr/bin/env python3
"""Tests for options.curve (SPM1D-style curve analysis) and options.alpha.

The numbers kbstatpy reports for a curve -- smoothness, threshold, cluster
endpoints, cluster p -- must be those of SPM1D (Pataky's spm1d), the reference
implementation biomechanics reviewers know. spm1d is not a dependency, so its
results are stored below (REF); they were computed with spm1d 0.4.59 on the
same seeded data (equal_var=True for the ANOVAs: spm1d's default estimates a
numerator df of ~2 for two groups). spm1d's optimiser stops the threshold
search early -- at its t threshold for the two groups p is 0.024987, not
0.025 -- so thresholds and cluster endpoints are compared to 1e-3, and
kbstatpy's own threshold is required to give exactly alpha. What is checked:

- the random field theory in _curve.py on its own, against spm1d's numbers;
- whole runs: two groups (F term against anova1, t comparison against
  ttest2), a one-sample test (intercept only, against ttest), a regression
  (covariate, F threshold from spm1d's F field at its smoothness), and a
  repeated-measures design. There kbstatpy fits a mixed model, whose residuals
  shrink the subject effects, where spm1d treats subjects as fixed: the F
  curve is the same, the smoothness differs by about 1 %, so that case has a
  tolerance;
- long and wide input give the same result, trials without a trial column
  are told apart, and the internal columns stay out of Data.csv;
- the errors: unequal spacing, incomplete curves, non-normal models, unknown
  columns, a malformed spec;
- options.alpha and alpha_stars: stars cut at alpha, scaled or kept, the
  legend, the curve threshold.

Needs R (kbstatpy starts it on import; the fits use lme4/emmeans).

Run:  python3 tests/test_curve.py
"""
import contextlib
import io
import os
import shutil
import sys
import warnings

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy import _curve as C                    # noqa: E402
from kbstatpy.kbstat import Kbstat, _sig_stars, _sig_key   # noqa: E402
from kbstatpy.options import KbstatOptions          # noqa: E402

OUT = '/tmp/kbstatpy_curve_test'
TOL = 1e-3        # against spm1d's thresholds and cluster endpoints, see above
Q = 101


def smooth(rng, n, sigma, scale):
    return gaussian_filter1d(rng.normal(size=(n, Q)), sigma, axis=1) * scale


def two_groups():
    rng = np.random.default_rng(3)
    a = smooth(rng, 10, 6, 6)
    b = smooth(rng, 12, 6, 6) + np.exp(-((np.arange(Q) - 60) / 10) ** 2) * 2.5
    return a, b


def one_sample():
    rng = np.random.default_rng(7)
    return smooth(rng, 12, 5, 5) + np.exp(-((np.arange(Q) - 55) / 12) ** 2) * 2.0


def regression():
    rng = np.random.default_rng(9)
    x = np.linspace(-1, 1, 16)
    return smooth(rng, 16, 7, 6) + np.outer(x, np.exp(-((np.arange(Q) - 30) / 9) ** 2) * 3), x


def repeated():
    rng = np.random.default_rng(11)
    ys, subj, cond = [], [], []
    for s in range(10):
        base = gaussian_filter1d(rng.normal(size=Q), 8) * 8
        for c in range(3):
            eff = np.exp(-((np.arange(Q) - 40) / 8) ** 2) * (1.5 * c)
            ys.append(base + eff + gaussian_filter1d(rng.normal(size=Q), 6) * 5)
            subj.append(s)
            cond.append(c)
    return np.array(ys), np.array(subj), np.array(cond)


# spm1d 0.4.59 on the data above: (fwhm, threshold, [(start, end, p), ...])
REF = {
    'ttest2': (14.082031146536035, 3.415275416962133,
               [(57.6458407964007, 59.91818775010822, 0.04425613880087331)]),
    'anova1': (14.082031146536039, 11.61965114561207,
               [(57.54830249984205, 60.02806160209603, 0.04333325665082366)]),
    'ttest': (11.901728993716088, 4.018745408348204,
              [(49.59290268203718, 60.112218069932716, 0.00033049504132875995)]),
    # spm1d's regress gives a t curve; the F reference is spm1d's own F
    # inference (SPM_F) on t^2 at the regression's smoothness.
    'regress_F': (14.688218437252825, 13.163856138424515,
                  [(22.870040519949676, 41.893013771867345, 6.863378606003501e-06)]),
    'anova1rm': (14.835273940619505, 8.371122882692212,
                 [(35.58051744851199, 42.960495974429676, 0.012611702481502451)]),
}


def wide(y, **cols):
    d = pd.DataFrame(y, columns=[f'p{q}' for q in range(Q)])
    for i, (k, v) in enumerate(cols.items()):
        d.insert(i, k, v)
    return d


def run(df, **kw):
    path = os.path.join(OUT, 'data.csv')
    df.to_csv(path, index=False)
    o = KbstatOptions()
    o.in_file, o.out_dir, o.figure_display = path, '', 'save_only'
    o.y = 'Y'
    for k, v in kw.items():
        setattr(o, k, v)
    k = Kbstat(o)
    with contextlib.redirect_stdout(io.StringIO()), warnings.catch_warnings():
        warnings.simplefilter('ignore')
        k.run()
    return k


def close(a, b, tol, what):
    assert abs(a - b) <= tol, f'{what}: {a} vs spm1d {b}'


def same_clusters(got, ref, tol, what, tol_ends=None):
    # A cluster that barely crosses the threshold meets it at a shallow angle,
    # so its endpoints move about ten times as much as the threshold does.
    tol_ends = 10 * tol if tol_ends is None else tol_ends
    assert len(got) == len(ref), f'{what}: {len(got)} clusters vs spm1d {len(ref)}'
    for c, (s, e, p) in zip(got, ref):
        close(c['start'], s, tol_ends, f'{what} start')
        close(c['end'], e, tol_ends, f'{what} end')
        close(c['p'], p, tol, f'{what} p')


# --- random field theory alone ------------------------------------------------

def test_rft_matches_spm1d_two_groups():
    a, b = two_groups()
    r = np.vstack([a - a.mean(0), b - b.mean(0)])
    fwhm = C.estimate_fwhm(r)
    close(fwhm, REF['ttest2'][0], 1e-9, 'fwhm')
    t = (b.mean(0) - a.mean(0))
    sp = np.sqrt(((a - a.mean(0)) ** 2).sum(0) + ((b - b.mean(0)) ** 2).sum(0)) / np.sqrt(20)
    t = -(t / (sp * np.sqrt(1 / 10 + 1 / 12)))          # a - b, as spm1d.ttest2(a, b)
    inf = C.infer('t', t, 20, fwhm, 0.05, two_tailed=True)
    close(C.p_max('t', inf['threshold'], 20, inf['resels'], Q), 0.025, 1e-12, 'p at threshold')
    close(inf['threshold'], REF['ttest2'][1], TOL, 't threshold')
    same_clusters(inf['clusters'], REF['ttest2'][2], TOL, 't')
    # At spm1d's own threshold the cluster geometry agrees exactly.
    (c,) = C.clusters(-t, REF['ttest2'][1])
    s0, e0, _ = REF['ttest2'][2][0]
    close(c['start'], s0, 1e-9, 'start at the spm1d threshold')
    close(c['end'], e0, 1e-9, 'end at the spm1d threshold')
    inf = C.infer('F', t ** 2, (1, 20), fwhm, 0.05)
    close(C.p_max('F', inf['threshold'], (1, 20), inf['resels'], Q), 0.05, 1e-12, 'p at threshold')
    close(inf['threshold'], REF['anova1'][1], TOL, 'F threshold')
    same_clusters(inf['clusters'], REF['anova1'][2], TOL, 'F')


def test_cluster_geometry():
    z = np.array([0, 1, 3, 4, 3, 1, 0, 2, 5, 5])
    cs = C.clusters(z, 2.5)
    assert [(round(c['start'], 3), round(c['end'], 3)) for c in cs] == [(1.75, 4.25), (7.167, 9.0)], cs
    assert cs[1]['height'] == 2.5, 'interpolated start: the height is the threshold'
    whole = C.clusters(np.full(10, 5.0), 2.5)[0]
    assert whole['height'] == 5.0 and whole['extent'] == 9.0, whole


# --- whole runs ---------------------------------------------------------------

def test_two_groups_match_anova1_and_ttest2():
    a, b = two_groups()
    k = run(wide(np.vstack([a, b]), Group=['a'] * 10 + ['b'] * 12),
            x='Group', curve='p0 : p100')
    cr = k.curve_result
    close(cr['fwhm'], REF['anova1'][0], 1e-6, 'fwhm')
    f = cr['terms']['Group']
    close(f['threshold'], REF['anova1'][1], TOL, 'F threshold')
    same_clusters(f['clusters'], REF['anova1'][2], TOL, 'F')
    (t,) = cr['posthoc']
    close(t['threshold'], REF['ttest2'][1], TOL, 't threshold')
    same_clusters(t['clusters'], REF['ttest2'][2], TOL, 't')
    assert t['clusters'][0]['sign'] == -1, 'a lies below b'


def test_one_sample_matches_ttest():
    y = one_sample()
    k = run(wide(y), curve='p0 : p100')
    (inf,) = k.curve_result['terms'].values()
    fwhm, thr, clusters = REF['ttest']
    close(k.curve_result['fwhm'], fwhm, 1e-6, 'fwhm')
    close(inf['threshold'], thr, TOL, 't threshold')
    same_clusters(inf['clusters'], clusters, TOL, 'one-sample')


def test_regression_matches_spm1d_F_field():
    y, x = regression()
    k = run(wide(y, Age=x), covariate='Age', curve='p0 : p100')
    fwhm, thr, clusters = REF['regress_F']
    inf = k.curve_result['terms']['Age']
    close(k.curve_result['fwhm'], fwhm, 1e-6, 'fwhm')
    close(inf['threshold'], thr, TOL, 'F threshold')
    same_clusters(inf['clusters'], clusters, TOL, 'regression')


def test_repeated_measures_close_to_anova1rm():
    y, s, c = repeated()
    k = run(wide(y, subj=[f's{v}' for v in s], cond=[f'c{v}' for v in c]),
            x='cond', id='subj', curve='p0 : p100')
    fwhm, thr, clusters = REF['anova1rm']
    inf = k.curve_result['terms']['cond']
    assert inf['df1'] == 2 and inf['df2'] == 18, (inf['df1'], inf['df2'])
    assert abs(k.curve_result['fwhm'] / fwhm - 1) < 0.03, (k.curve_result['fwhm'], fwhm)
    assert abs(inf['threshold'] / thr - 1) < 0.01, (inf['threshold'], thr)
    same_clusters(inf['clusters'], clusters, 0.05, 'repeated measures')


def test_long_equals_wide_and_trials_are_told_apart():
    a, b = two_groups()
    y = np.vstack([a, b])
    w = wide(y, Subject=[f's{i // 2}' for i in range(22)], Group=['a'] * 10 + ['b'] * 12)
    kw = run(w, x='Group', id='Subject', curve='Time = (p0 : p100)')
    long = w.melt(id_vars=['Subject', 'Group'], var_name='Time', value_name='Y')
    long['Time'] = long['Time'].str[1:].astype(int)
    # Point-major instead of curve-major order. Each subject has two trials and
    # no trial column, so a trial is the k-th row of its subject at each point:
    # any consistent order works, a shuffled one could not.
    long = long.sort_values('Time', kind='stable')
    kl = run(long, x='Group', id='Subject', curve='Time')
    assert kl.curve_result['n_curves'] == 22, kl.curve_result['n_curves']
    for t in kw.curve_result['terms']:
        np.testing.assert_allclose(kl.curve_result['terms'][t]['values'],
                                   kw.curve_result['terms'][t]['values'], rtol=1e-8)
    close(kl.curve_result['fwhm'], kw.curve_result['fwhm'], 1e-9, 'fwhm long vs wide')
    exported = kl._data_for_export()
    assert not [c for c in exported.columns if c.startswith('kbstat_')], list(exported.columns)


def test_positions_from_names_or_default():
    y = one_sample()[:, :50]
    d = pd.DataFrame(y, columns=[f'v{q}' for q in range(1, 51)])
    k = run(d, curve='v1 : v50')
    assert k.curve_result['positions'][0] == 1 and k.curve_result['step'] == 1
    d.columns = [f'x{c}' for c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWX']
    k = run(d, curve='xa : xX')
    pos = k.curve_result['positions']
    assert pos[0] == 0 and pos[-1] == 100 and len(pos) == 50, pos


def test_errors():
    a, b = two_groups()
    w = wide(np.vstack([a, b]), Group=['a'] * 10 + ['b'] * 12)
    long = w.melt(id_vars=['Group'], var_name='Time', value_name='Y')
    long['Time'] = long['Time'].str[1:].astype(int)
    cases = [
        (dict(curve='p0 : p999', x='Group'), w, 'is not a column'),
        (dict(curve='Time = (p0)', x='Group'), w, 'not understood'),
        (dict(curve='p0 : p100', x='Group', distribution='gamma'), w, 'does not support'),
        (dict(curve='Nope', x='Group'), long, 'is not a column'),
        (dict(curve='Time', x='Group'), long[long['Time'] != 50], 'not equally spaced'),
        (dict(curve='Time', x='Group'), long.drop(index=[5]), 'exactly once'),
        (dict(curve='p0 : p100', x='Group', alpha=1.5), w, 'between 0 and 1'),
    ]
    for kw, data, text in cases:
        try:
            run(data, **kw)
        except ValueError as e:
            assert text in str(e), (kw, str(e))
            continue
        raise AssertionError(f'{kw}: no ValueError mentioning {text!r}')


# --- options.alpha ------------------------------------------------------------

def test_stars_follow_alpha_and_alpha_stars():
    assert [_sig_stars(p) for p in (0.0005, 0.005, 0.03, 0.07)] == ['***', '**', '*', 'n.s.']
    assert [_sig_stars(p, 0.01) for p in (0.0005, 0.005, 0.03)] == ['***', '**', 'n.s.']
    assert [_sig_stars(p, 0.10) for p in (0.03, 0.07, 0.2)] == ['*', '+', 'n.s.']
    assert [_sig_stars(p, 0.01, 'scale') for p in (0.0001, 0.001, 0.005, 0.02)] == ['***', '**', '*', 'n.s.']
    assert [_sig_stars(p, 0.01, 'keep') for p in (0.0005, 0.005, 0.03, 0.07)] == ['***', '**', '*', 'n.s.']
    assert [_sig_stars(p, 0.10, 'keep') for p in (0.03, 0.07)] == ['*', '+']
    assert 'p < 0.0002' in '\n'.join(_sig_key(0.01, 'scale'))
    assert 'significant only where p < 0.01' in '\n'.join(_sig_key(0.01, 'keep'))
    key = '\n'.join(_sig_key(0.01))
    assert 'p < 0.05' not in key and 'p >= 0.01' in key, key
    assert '+    p < 0.1' in '\n'.join(_sig_key(0.1))


def test_alpha_sets_the_curve_threshold():
    a, b = two_groups()
    w = wide(np.vstack([a, b]), Group=['a'] * 10 + ['b'] * 12)
    k = run(w, x='Group', curve='p0 : p100', alpha=0.01)
    f = k.curve_result['terms']['Group']
    fwhm = k.curve_result['fwhm']
    close(f['threshold'], C.threshold('F', 0.01, (1, 20), C.resel_counts(Q, fwhm), Q),
          1e-9, 'F threshold at alpha = 0.01')
    assert not f['clusters'], 'the cluster at p = 0.043 is gone at alpha = 0.01'
    assert 'alpha = 0.01' in k._summary_text()


if __name__ == '__main__':
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            if os.path.isdir(OUT):
                shutil.rmtree(OUT)
            os.makedirs(OUT)
            try:
                fn()
                print(f'PASS  {name}')
            except AssertionError as e:
                failures += 1
                print(f'FAIL  {name}\n      {e}')
            except Exception as e:                      # noqa: BLE001
                failures += 1
                print(f'ERROR {name}\n      {type(e).__name__}: {e}')
    if failures:
        print(f'\n{failures} test(s) FAILED')
        sys.exit(1)
    print('\nall tests passed')
