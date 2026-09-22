#!/usr/bin/env python3
"""Tests for the gamma default link and the post-hoc scale note.

Two changes, both about a reader being able to trust what a table says.

`distribution = 'gamma'` and `'inverse_gaussian'` used to inherit R's
canonical links, the inverse and 1/mu^2. Under it beta acts on 1/mu, so a POSITIVE coefficient means a SMALLER
mean and every gamma coefficient reads backwards; mu = 1/(X beta) also needs
the linear predictor to stay positive, where exp(X beta) never can; and every
other positive-outcome family here uses a log, so switching `distribution`
between gamma and tweedie silently changed the mean model rather than only the
variance function, which left the two uncomparable by AIC. 'auto' now means
the link kbstatpy recommends rather than the one R makes canonical. Setting
`link` explicitly is untouched, inverse included.

The post-hoc row mixes two scales: emm_1, emm_2 and diff are on the response
scale (diff being the difference of the back-transformed means) while t, df
and p come from the contrast emmeans tested on the link scale. Under any
non-identity link those are different quantities, so t is not diff over its
standard error; under a decreasing link they do not even share a sign, which
is how it was noticed -- diff = -0.938 printed beside t = +9.38. The columns
are therefore labelled. Nothing is renamed and no number moves.

Needs R + glmmTMB.

Run:  python3 tests/test_gamma_link_and_scale.py
"""
import os
import re
import sys
import warnings

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat            # noqa: E402
from kbstatpy.options import KbstatOptions    # noqa: E402

OUT = '/tmp/kbstatpy_gamma_link'


def toy(n_subj=14, seed=0):
    """Positive, right-skewed, with a multiplicative group effect."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_subj):
        re_ = rng.normal(scale=0.25)
        for g, shift in (('g1', 0.0), ('g2', 0.5)):
            for _ in range(8):
                mu = np.exp(0.5 + re_ + shift)
                rows.append({'y': rng.gamma(9.0, mu / 9.0),
                             'grp': g, 'subj': f's{s}'})
    return pd.DataFrame(rows)


def fit(**kw):
    os.makedirs(OUT, exist_ok=True)
    csv = os.path.join(OUT, 'toy.csv')
    toy().to_csv(csv, index=False)
    o = KbstatOptions()
    o.in_file = csv
    o.y, o.x, o.id = 'y', 'grp', 'subj'
    o.out_dir, o.figure_display = OUT, 'save_only'
    for k_, v in kw.items():
        setattr(o, k_, v)
    k = Kbstat(o)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        k.run()
    return k


def fit_loud(**kw):
    """Like fit(), but lets warnings out: fit() silences them on purpose."""
    os.makedirs(OUT, exist_ok=True)
    csv = os.path.join(OUT, 'toy.csv')
    toy().to_csv(csv, index=False)
    o = KbstatOptions()
    o.in_file = csv
    o.y, o.x, o.id = 'y', 'grp', 'subj'
    o.out_dir, o.figure_display = OUT, 'save_only'
    for k_, v in kw.items():
        setattr(o, k_, v)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        Kbstat(o).run()
        return [str(w.message) for w in caught]


def inverse_gaussian_available():
    """Whether the installed glmmTMB implements the inverse Gaussian family.

    It varies by version: some builds fit it, others answer TMB's
    "Family not implemented!". glmmTMB's own .valid_family does not list it
    even on a build that fits it, so the only reliable check is to try.
    Probed once, because a fit is not free.
    """
    global _IG_OK
    if _IG_OK is None:
        try:
            fit(distribution='inverse_gaussian')
            _IG_OK = True
        except Exception as exc:                        # noqa: BLE001
            _IG_OK = 'not implement' not in str(exc)
            if not _IG_OK:
                print('  (skipping the inverse Gaussian tests: this glmmTMB '
                      'does not implement the family)')
    return _IG_OK


_IG_OK = None


def field(text, label):
    m = re.search(rf'^\s*{re.escape(label)}\s*:\s*(.+)$', text, re.M)
    assert m, f'no {label!r} line in the summary'
    return m.group(1).strip()


def posthoc_block(k):
    return k._summary_text().split('POST-HOC PAIRWISE COMPARISONS')[1].split('\n\n')[0]


def test_gamma_defaults_to_the_log_link():
    """The change itself: 'auto' must no longer give R's inverse."""
    got = field(fit(distribution='gamma')._summary_text(), 'Link function')
    assert got == 'log', f"expected 'log', got {got!r}"


def test_the_default_matches_asking_for_log_explicitly():
    """'auto' and link='log' must be the same fit, not merely both logs."""
    a = fit(distribution='gamma')
    b = fit(distribution='gamma', link='log')
    assert np.isclose(a.AIC, b.AIC), (a.AIC, b.AIC)


def test_an_explicit_inverse_link_is_still_honoured():
    """The default changed; the option did not. Asking for inverse must work."""
    got = field(fit(distribution='gamma', link='inverse')._summary_text(),
                'Link function')
    assert got.startswith('inverse'), got


def test_the_gamma_coefficient_no_longer_reads_backwards():
    """Under the inverse link the sign of every coefficient is reversed.

    The toy has g2 above g1, so with effects coding the g1 term must be
    negative on a log link and positive on an inverse one.
    """
    def grp_term(k):
        c = k.model.coefs
        c = c.to_pandas() if hasattr(c, 'to_pandas') else c
        row = c[c['term'].astype(str).str.contains('grp')]
        return float(row['Estimate'].iloc[0])
    assert grp_term(fit(distribution='gamma')) < 0
    assert grp_term(fit(distribution='gamma', link='inverse')) > 0


def test_other_families_keep_their_own_default():
    """Only gamma departs from R; nothing else may be dragged along."""
    assert field(fit()._summary_text(), 'Link function') == 'identity'
    assert field(fit(distribution='poisson')._summary_text(),
                 'Link function') == 'log'


def test_an_identity_link_gets_no_scale_note():
    """With one scale there is nothing to disambiguate, and a note would be
    noise on the overwhelmingly common gaussian fit."""
    block = posthoc_block(fit())
    assert 'response scale' not in block, block


def test_a_non_identity_link_says_which_scale_each_column_is_on():
    """The fix: a reader must not have to discover that t is not diff/SE."""
    block = posthoc_block(fit(distribution='gamma'))
    assert 'emm_1, emm_2 and diff are on the response scale' in block, block
    assert 'on the log scale' in block, block
    assert 'not diff divided by its standard error' in block, block


def test_a_decreasing_link_also_warns_about_the_sign():
    """Under the inverse link t and diff disagree in sign in every row."""
    block = posthoc_block(fit(distribution='gamma', link='inverse'))
    assert 'opposite sign to diff' in block, block
    assert 'p-values are unaffected' in block, block


def test_the_sign_disagreement_is_real_and_is_what_the_note_describes():
    """Guards the note against the code it describes drifting away from it."""
    k = fit(distribution='gamma', link='inverse')
    ph = k.posthoc_table
    ph = ph.to_pandas() if hasattr(ph, 'to_pandas') else ph
    row = ph.iloc[0]
    assert float(row['diff']) * float(row['t']) < 0, (row['diff'], row['t'])
    assert 'opposite sign to diff' in posthoc_block(k)


def test_no_number_moved_for_an_explicit_link():
    """The labelling is presentational: asking for a link must give the same
    fit it always did."""
    k = fit(distribution='gamma', link='inverse')
    ph = k.posthoc_table
    ph = ph.to_pandas() if hasattr(ph, 'to_pandas') else ph
    assert np.isfinite(float(ph.iloc[0]['p']))
    assert float(ph.iloc[0]['t']) > 0        # as the inverse link produces


def test_inverse_gaussian_defaults_to_the_log_link():
    """Same argument as gamma: R's canonical 1/mu^2 is decreasing in the mean,
    so coefficients read backwards, and it is the harder of the two to read --
    a change in the reciprocal of the squared mean."""
    if not inverse_gaussian_available():
        return
    got = field(fit(distribution='inverse_gaussian')._summary_text(),
                'Link function')
    assert got == 'log', f"expected 'log', got {got!r}"


def test_glmmtmb_substitutes_a_log_for_the_squared_canonical_link():
    """The premise behind reporting the fitted link for this family.

    glmmTMB accepts inverse.gaussian(link="1/mu^2") and then fits a log link
    anyway, while family(m)$link keeps echoing "1/mu^2".

    Asserted on the linear predictor, which settles it: eta is reconstructed
    from the fitted values and compared against each candidate link, so this
    says which link the fit USED rather than which one it reported. Equality
    of coefficients alone would not do -- a model saturated in its fixed part
    gives the same fitted values under every link, so a factor-only design
    cannot tell the links apart. A continuous covariate is used here for that
    reason.

    Checked against glmmTMB 1.1.14. `inverse` and `identity` ARE honoured, so
    this is a missing link rather than links being ignored; if a later version
    implements 1/mu^2, this fails and _SUBSTITUTED_LINKS must go.
    """
    if not inverse_gaussian_available():
        return
    import rpy2.robjects as ro
    ro.r("""
    suppressMessages(library(glmmTMB))
    set.seed(7)
    .kb_d <- do.call(rbind, lapply(1:20, function(s) {
      re <- rnorm(1, sd = 0.20); x <- runif(12, -1, 1)
      mu <- exp(0.6 + re + 0.8 * x)
      data.frame(y = rgamma(12, shape = 12, scale = mu / 12), x = x,
                 subj = sprintf('s%02d', s))
    }))
    .kb_d$subj <- factor(.kb_d$subj)
    .kb_eta_link <- function(l) {
      m <- glmmTMB(y ~ x + (1|subj), data = .kb_d,
                   family = inverse.gaussian(link = l))
      eta <- as.numeric(predict(m, type = 'link'))
      mu  <- as.numeric(predict(m, type = 'response'))
      cands <- c(log = 'log', `1/mu^2` = '1/mu^2', inverse = 'inverse')
      f <- list(log = log(mu), `1/mu^2` = 1/mu^2, inverse = 1/mu)
      hit <- names(f)[sapply(f, function(v)
                 isTRUE(all.equal(v, eta, tolerance = 1e-6)))]
      if (length(hit)) hit[1] else 'NONE'
    }
    """)
    used = lambda l: str(ro.r('.kb_eta_link')(l)[0])
    assert used('log') == 'log', used('log')
    assert used('inverse') == 'inverse', (
        'glmmTMB stopped honouring the inverse link too; the substitution '
        'table assumes only 1/mu^2 is missing')
    assert used('1/mu^2') == 'log', (
        f"glmmTMB now fits {used('1/mu^2')!r} for '1/mu^2'; "
        'drop _SUBSTITUTED_LINKS')


def test_the_reported_link_is_the_one_fitted_not_the_one_asked_for():
    """Reporting '1/mu^2' would name a link the fit never used, which is
    exactly the failure the link line exists to prevent."""
    if not inverse_gaussian_available():
        return
    k = fit(distribution='inverse_gaussian', link='1/mu^2')
    assert k._fitted_link() == 'log', k._fitted_link()
    assert field(k._summary_text(), 'Link function').startswith('log')


def test_asking_for_the_substituted_link_warns():
    """Silently fitting something other than what was asked for is the worst
    of the options; the summary alone would be easy to miss."""
    if not inverse_gaussian_available():
        return
    msgs = fit_loud(distribution='inverse_gaussian', link='1/mu^2')
    assert any('does not implement' in m and 'log' in m for m in msgs), msgs


def test_no_such_warning_when_the_link_is_honoured():
    """The warning must name a real substitution, not fire on every GLMM."""
    if not inverse_gaussian_available():
        return
    msgs = fit_loud(distribution='inverse_gaussian', link='inverse')
    assert not any('does not implement' in m for m in msgs), msgs


def test_no_sign_warning_when_the_substituted_link_is_increasing():
    """The fit is a log, so t and diff agree; announcing that they oppose
    would be worse than saying nothing."""
    if not inverse_gaussian_available():
        return
    block = posthoc_block(fit(distribution='inverse_gaussian', link='1/mu^2'))
    assert 'opposite sign to diff' not in block, block
    assert 'on the log scale' in block, block


def test_a_link_glmmtmb_does_honour_is_left_alone():
    """Only 1/mu^2 is substituted; 'inverse' must still be fitted and named."""
    if not inverse_gaussian_available():
        return
    k = fit(distribution='inverse_gaussian', link='inverse')
    assert k._fitted_link() == 'inverse'
    assert 'opposite sign to diff' in posthoc_block(k)


if __name__ == '__main__':
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn()
                print(f'PASS  {name}', flush=True)
            except AssertionError as e:
                failures += 1
                print(f'FAIL  {name}\n      {e}', flush=True)
            except Exception as e:                      # noqa: BLE001
                failures += 1
                print(f'ERROR {name}\n      {type(e).__name__}: {e}', flush=True)
    print(f'\n{"all tests passed" if not failures else f"{failures} test(s) FAILED"}')
    sys.exit(1 if failures else 0)
