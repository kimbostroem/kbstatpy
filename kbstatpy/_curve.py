"""Inference on curves (options.curve): random field theory in one dimension.

A curve analysis fits the same model at every point of a curve (a gait cycle
normalised to 0-100 %, say) and gets one test statistic per point: an F per
model term, a t per pairwise comparison. Testing each point at alpha would give
a false positive somewhere on almost every curve; Bonferroni over 101 points
ignores that neighbouring points are nearly the same test. Random field theory
(RFT) sets one threshold for the whole curve from its smoothness: the chance
that the statistic exceeds it anywhere, if nothing is going on, is alpha.

This is the method of Statistical Parametric Mapping (SPM; Friston, Worsley)
as Pataky's spm1d applies it to 1D biomechanical data. It is written here from
the published formulas, not from spm1d's code:

- Worsley KJ et al. (1996) A unified statistical approach for determining
  significant signals in images of cerebral activation. Hum Brain Mapp 4:58-73
  (Euler characteristic densities of t and F fields, Table 2).
- Friston KJ et al. (1994) Assessing the significance of focal activations
  using their spatial extent. Hum Brain Mapp 1:210-220 (cluster extent).
- Kiebel SJ et al. (1999) Robust smoothness estimation in statistical
  parametric maps using standardized residuals. NeuroImage 10:756-766.
- Pataky TC (2016) RFT1D: Smooth one-dimensional random field upcrossing
  probabilities. J Stat Softw 71(7) (the 1D conventions followed here: node
  based field size Q - 1, gradient smoothness estimate, Bonferroni bound for
  rough fields). tests/test_curve.py checks every number against spm1d.

Everything here is plain numpy/scipy and knows nothing about kbstatpy.
"""
import math

import numpy as np
from scipy import optimize, special, stats

_EPS = np.finfo(float).eps
_FOUR_LOG2 = 4.0 * math.log(2.0)


# --- smoothness -------------------------------------------------------------

def estimate_fwhm(residuals):
    """Smoothness of the residual curves (rows = curves, columns = points), as
    the full width at half maximum of a Gaussian kernel, in points.

    Each point's squared gradient is divided by its residual sum of squares, so
    the estimate does not depend on the residual variance (Kiebel et al. 1999).
    The gradient is the central difference inside the curve and the one-sided
    difference at its ends. Points without variance carry no information on
    smoothness and are left out.
    """
    r = np.asarray(residuals, dtype=float)
    ssq = (r ** 2).sum(axis=0)
    grad = np.gradient(r, axis=1)
    v = (grad ** 2).sum(axis=0) / (ssq + _EPS)
    v = v[np.isfinite(v) & (ssq > 0)]
    resels_per_point = np.sqrt(v / _FOUR_LOG2)
    return float(1.0 / resels_per_point.mean())


def resel_counts(n_points, fwhm):
    """(segments, resels) of one unbroken curve of n_points equally spaced
    points: the curve is n_points - 1 steps long."""
    return 1.0, (n_points - 1) / fwhm


# --- Euler characteristic densities ----------------------------------------

def ec_densities(stat, u, df):
    """Euler characteristic densities (rho0, rho1) of a t or F field at height
    u: rho0 is the chance of exceeding u at one point, rho1 the expected
    number of upcrossings per resel (Worsley et al. 1996, Table 2)."""
    if stat == 't':
        v = float(df)
        rho0 = stats.t.sf(u, v)
        rho1 = math.sqrt(_FOUR_LOG2) / (2 * math.pi) * (1 + u * u / v) ** (-(v - 1) / 2)
        return rho0, rho1
    if stat == 'F':
        k, v = float(df[0]), float(df[1])
        if u <= 0:
            return 1.0, math.inf
        rho0 = stats.f.sf(u, k, v)
        log_c = (special.gammaln((v + k - 1) / 2) - special.gammaln(v / 2)
                 - special.gammaln(k / 2))
        rho1 = (math.sqrt(_FOUR_LOG2 / (2 * math.pi)) * math.exp(log_c) * math.sqrt(2)
                * (k * u / v) ** ((k - 1) / 2) * (1 + k * u / v) ** (-(v + k - 2) / 2))
        return rho0, rho1
    raise ValueError(f'unknown statistic {stat!r}')


def _expected(stat, u, df, resels):
    """Expected Euler characteristic of the excursion set above u (the
    expected number of clusters) and the expected cluster extent in resels."""
    rho0, rho1 = ec_densities(stat, u, df)
    rho0, rho1 = max(rho0, _EPS), max(rho1, _EPS)
    r0, r1 = resels
    r1 = max(r1, _EPS)
    expected_clusters = r0 * rho0 + r1 * rho1
    expected_extent = rho0 / rho1             # (rho0 * r1) / (rho1 * r1)
    return expected_clusters, expected_extent, rho0


def p_max(stat, u, df, resels, n_points):
    """Chance that the field exceeds u anywhere: 1 - exp(-E[EC]) (Poisson
    clumping). Bounded by Bonferroni over the points, which is the smaller of
    the two for a very rough curve, and never below the single-point p."""
    ec, _, rho0 = _expected(stat, u, df, resels)
    p = -math.expm1(-ec)              # 1 - exp(-ec), exact for small ec
    p = min(p, n_points * rho0, 1.0)
    return max(p, rho0)


def threshold(stat, alpha, df, resels, n_points):
    """Critical height u* with p_max(u*) = alpha."""
    if stat == 't':
        lo = stats.t.isf(alpha, df)
        hi = stats.t.isf(alpha / (n_points * 10), df) + 10
    else:
        lo = stats.f.isf(alpha, df[0], df[1])
        hi = stats.f.isf(alpha / (n_points * 10), df[0], df[1]) * 2 + 10
    f = lambda u: p_max(stat, u, df, resels, n_points) - alpha
    while f(hi) > 0:
        hi *= 2
    return float(optimize.brentq(f, lo, hi, xtol=1e-12))


def p_cluster(stat, extent_resels, u, df, resels):
    """Chance of at least one cluster at least extent_resels wide when the
    field is thresholded at u (Friston et al. 1994, in 1D:
    P(extent >= k) = exp(-beta k^2), beta = (Gamma(3/2) / E[extent])^2)."""
    ec, expected_extent, _ = _expected(stat, u, df, resels)
    beta = (special.gamma(1.5) / expected_extent) ** 2
    p_extent = math.exp(-beta * extent_resels ** 2)
    return -math.expm1(-(ec + _EPS) * p_extent)


# --- clusters ---------------------------------------------------------------

def clusters(z, u, sign=1):
    """Runs of consecutive points where sign * z >= u. Each is returned with
    its endpoints in point units, interpolated linearly to where the curve
    crosses u (a run at the end of the curve ends at that point), its extent
    (end - start, at least 1 for a single point at a curve end) and the index
    of its peak."""
    z = sign * np.asarray(z, dtype=float)
    above = z >= u
    out, q, n = [], 0, len(z)
    while q < n:
        if not above[q]:
            q += 1
            continue
        first = q
        while q < n and above[q]:
            q += 1
        last = q - 1
        start, end = float(first), float(last)
        if first > 0:
            start = first - (z[first] - u) / (z[first] - z[first - 1])
        if last < n - 1:
            end = last + (z[last] - u) / (z[last] - z[last + 1])
        extent = end - start
        if extent == 0:
            extent = 1.0
        # The height for the cluster p is u where the run was interpolated to
        # it; a run spanning the whole curve never reaches u, so its lowest
        # point is the height.
        interpolated = first > 0 or last < n - 1
        height = u if interpolated else float(z[first:last + 1].min())
        peak = first + int(np.argmax(z[first:last + 1]))
        out.append({'start': start, 'end': end, 'extent': extent, 'peak': peak,
                    'first': first, 'last': last, 'height': height})
    return out


def infer(stat, z, df, fwhm, alpha=0.05, two_tailed=False):
    """Threshold and clusters of one statistic curve.

    stat 'F' (one-tailed) or 't' (two_tailed: |t| against the threshold at
    alpha / 2 on each side, cluster p doubled, as spm1d does). df: v for t,
    (k, v) for F. Returns {'threshold', 'clusters': [...], 'resels'}, each
    cluster with 'start', 'end', 'extent', 'peak', 'sign', 'p'."""
    z = np.asarray(z, dtype=float)
    n_points = len(z)
    resels = resel_counts(n_points, fwhm)
    a = alpha / 2 if two_tailed else alpha
    u = threshold(stat, a, df, resels, n_points)
    found = []
    for sign in ((1, -1) if two_tailed else (1,)):
        for c in clusters(z, u, sign):
            p = p_cluster(stat, c['extent'] / fwhm, c.pop('height'), df, resels)
            c['p'] = min(1.0, 2 * p) if two_tailed else p
            c['sign'] = sign
            found.append(c)
    found.sort(key=lambda c: c['start'])
    return {'threshold': u, 'clusters': found, 'resels': resels}
