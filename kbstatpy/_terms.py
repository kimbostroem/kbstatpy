"""Covariate terms that are expressions of one column: powers and functions.

`options.covariate = 'z, z^2, log(w)'` and `options.formula = 'y ~ z^2 + ...'`
both end up here. Each expression becomes a column of its own, computed in
Python before the fit, and R only ever sees plain column names. Two reasons:

* kbstatpy works on column names throughout -- the NA filter, the covariate
  scaling, the VIF, Data.csv and the ANOVA labels. An `I(z^2)` passed through
  to R was invisible to all of them, and emmeans' joint_tests, which builds the
  ANOVA table, folds a function of z into z's own row, so the squared term
  vanished from Anova.xlsx and Summary.txt while it was being fitted.
* The order of operations matters and only kbstatpy knows it: log(z) has to be
  taken of the raw values and scaled afterwards, where R would have taken the
  log of an already scaled, partly negative column.

What an expression means:

* `z^k`, k a whole number >= 2: the polynomial z + z^2 + ... + z^k, the powers
  built from z centred at its mean (from its z-score when the covariates are
  scaled). Without the lower terms the curve is pinned to a vertex at z = 0, an
  arbitrary point of the scale; centring makes the lower coefficients slopes at
  the mean of z instead of at z = 0, and removes most of their collinearity.
  The fit itself is the same either way.
* `I(...)`: exactly as written, from the raw values, no expansion and no
  centring. R's "as is", for the rare case where the vertex really is at zero.
* anything else in one column, `log(z)`, `sqrt(z)`, `z^0.5`, `1/z`: a transform
  of the raw values, scaled afterwards like any other covariate.

In a formula this makes `^` on a single numeric variable a power, where R reads
`z^2` as `z` crossed with itself, which is just `z`. Nothing meaningful in R
changes by that, since the R reading is a no-op; `(a + b)^2`, the crossing that
does mean something, is left to R.
"""
import re
from dataclasses import dataclass

#: Functions an expression may call, mapped to their sympy spelling.
_FUNCTIONS = ('log', 'log10', 'log2', 'exp', 'sqrt', 'abs')

_IDENT = re.compile(r'(?<![0-9.])[A-Za-z_.][A-Za-z0-9_.]*')
_PLAIN = re.compile(r'^[A-Za-z_.][A-Za-z0-9_.]*$')


@dataclass(frozen=True)
class CovTerm:
    """One derived covariate column."""
    label: str      # as shown in the output: 'z^2', 'log(w)', 'I(z^2)'
    column: str     # the R-safe column name it is fitted under
    var: str        # the data column it is computed from
    kind: str       # 'power' (polynomial, from centred var) or 'transform' (raw)
    power: int = 0  # for 'power'
    expr: str = ''  # for 'transform': sympy expression in the symbol _v

    def function(self):
        """numpy function of the raw column, for kind 'transform'."""
        import sympy as sp
        v = sp.Symbol('_v', real=True)
        return sp.lambdify(v, sp.sympify(self.expr, locals=_sympy_locals(v)), 'numpy')


def _sympy_locals(v):
    import sympy as sp
    return {'_v': v, 'log': sp.log, 'exp': sp.exp, 'sqrt': sp.sqrt, 'abs': sp.Abs,
            'log10': lambda e: sp.log(e, 10), 'log2': lambda e: sp.log(e, 2)}


def _column_name(label):
    s = (label.replace('**', '^').replace('^', '_pow').replace('-', 'm')
         .replace('+', 'p').replace('*', 'x').replace('/', 'd'))
    s = re.sub(r'[^A-Za-z0-9_.]+', '_', s).strip('_')
    return s if s and not s[0].isdigit() else f'term_{s}'


def is_expression(text):
    """Whether a covariate entry or formula term is an expression to compute,
    rather than a plain column name or something R should read itself."""
    t = text.strip()
    if not t or _PLAIN.match(t) or '|' in t:
        return False
    if t.startswith('I(') and t.endswith(')'):
        return True
    if re.match(rf'^({"|".join(_FUNCTIONS)})\s*\(', t):
        return True
    # A power of a single name; '(a + b)^2' is R's crossing and stays R's.
    return bool(re.match(r'^[A-Za-z_.][A-Za-z0-9_.]*\s*(\^|\*\*)', t)
                or re.match(r'^\(\s*[A-Za-z_.][A-Za-z0-9_.]*\s*\)\s*(\^|\*\*)', t))


def parse(text):
    """Expand one covariate entry into plain names and CovTerms.

    Returns a list: the entry itself when it is a plain name, `[z, z^2, ...]`
    for a polynomial, or one CovTerm for a literal or a transform. Raises
    ValueError for anything that is not an expression in one column.
    """
    import sympy as sp
    t = ' '.join(text.split())
    if _PLAIN.match(t):
        return [t]
    literal = t.startswith('I(') and t.endswith(')') and _balanced(t[2:-1])
    body = t[2:-1].strip() if literal else t
    body = body.replace('^', '**')

    names = []
    for m in _IDENT.finditer(body):
        rest = body[m.end():].lstrip()
        if rest.startswith('('):
            if m.group(0) not in _FUNCTIONS:
                raise ValueError(
                    f"covariate term {text!r}: function {m.group(0)!r} is not "
                    f"supported; use one of {', '.join(_FUNCTIONS)}")
            continue
        if m.group(0) not in names:
            names.append(m.group(0))
    if len(names) != 1:
        raise ValueError(
            f"covariate term {text!r} must be an expression in exactly one "
            f"column, found " + (f"{len(names)} ({', '.join(names)}). A product "
            "of two variables is an interaction, not a covariate term."
            if names else "none."))
    var = names[0]

    v = sp.Symbol('_v', real=True)
    sub = re.sub(rf'(?<![A-Za-z0-9_.]){re.escape(var)}(?![A-Za-z0-9_.(])', '_v', body)
    try:
        expr = sp.sympify(sub, locals=_sympy_locals(v))
    except Exception as e:                                  # noqa: BLE001
        raise ValueError(f"covariate term {text!r} could not be parsed: {e}") from None

    if expr == v:
        return [var]
    if (not literal and isinstance(expr, sp.Pow) and expr.base == v
            and expr.exp.is_Integer and int(expr.exp) >= 2):
        k = int(expr.exp)
        return [var] + [CovTerm(label=f'{var}^{j}', column=_column_name(f'{var}^{j}'),
                                var=var, kind='power', power=j)
                        for j in range(2, k + 1)]
    label = f'I({t[2:-1].strip()})' if literal else t
    return [CovTerm(label=label, column=_column_name(label), var=var,
                    kind='transform', expr=str(expr))]


def _balanced(s):
    depth = 0
    for ch in s:
        depth += ch == '('
        depth -= ch == ')'
        if depth < 0:
            return False
    return depth == 0


def expand(entries, registry):
    """Expand covariate entries into column names.

    `registry` maps already generated column names to their CovTerm, so a
    second pass over the result is a no-op (the options are normalised more
    than once). Returns (columns, registry, notes), notes being one line per
    polynomial that was expanded, for the console.
    """
    registry = dict(registry)
    columns, notes = [], []
    for entry in entries:
        if entry in registry or _PLAIN.match(entry.strip()):
            parts = [entry.strip()]
        else:
            parts = parse(entry)
            terms = [p for p in parts if isinstance(p, CovTerm)]
            if terms and terms[0].kind == 'power':
                notes.append(f"{entry.strip()} -> " + ' + '.join(
                    [parts[0]] + [p.label for p in terms])
                    + f" (powers of centred {parts[0]})")
        for p in parts:
            col = p.column if isinstance(p, CovTerm) else p
            if isinstance(p, CovTerm):
                registry[col] = p
            if col not in columns:
                columns.append(col)
    return columns, registry, notes


def _split_top(s, seps):
    """Split `s` at the characters in `seps` outside parentheses."""
    out, depth, cur = [], 0, ''
    for ch in s:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch in seps and depth == 0:
            out.append(cur)
            cur = ''
        else:
            cur += ch
    out.append(cur)
    return out


def rewrite_formula(formula, registry):
    """Replace the expression terms of a formula's fixed part by columns.

    Returns (formula, covariate entries, registry, caret): the rewritten
    formula, the entries to add to options.covariate (the plain base columns
    and the generated ones), and whether a `^` was read as a power, which is
    where kbstatpy departs from R's formula syntax.
    """
    lhs, sep, rhs = formula.partition('~')
    if not sep:
        return formula, [], registry, False
    registry = dict(registry)
    entries, caret, out = [], False, []
    summands = _split_top(rhs, '+')
    # Plain terms already in the formula, so `z + z^2` does not list z twice.
    present = {t.strip() for t in summands if _PLAIN.match(t.strip())}
    for summand in summands:
        term = summand.strip()
        m = re.match(r'^poly\s*\(\s*([A-Za-z_.][A-Za-z0-9_.]*)\s*,\s*(\d+)', term)
        if m:
            # R's poly() gives orthogonal polynomials, a third parametrisation
            # with coefficients unlike either the raw or the centred powers,
            # and its matrix-valued column crashes the pymer4 bridge.
            raise ValueError(
                f"formula term {term!r}: poly() is not supported; write "
                f"{m.group(1)}^{m.group(2)} for the polynomial in centred "
                f"{m.group(1)}.")
        if not is_expression(term):
            if (any(is_expression(p) for p in _split_top(term, '*:'))
                    and '|' not in term):
                raise ValueError(
                    f"formula term {term!r}: a power or function of a covariate "
                    "inside an interaction is not supported. Write the "
                    "interaction with the plain variable, or fit the term as a "
                    "covariate on its own.")
            out.append(summand)
            continue
        if not (term.startswith('I(')) and re.search(r'\^', term):
            caret = True
        cols, registry, _ = expand([term], registry)
        entries += [c for c in cols if c not in entries]
        new = [c for c in cols if c not in present]
        present.update(new)
        if new:
            out.append(' ' + ' + '.join(new) + ' ')
    # A plain term whose variable is also inside an expression, as cadence in
    # `cadence + I(cadence^2)`, is numeric by implication; left alone, the
    # formula backfill would read it as a factor.
    plain = {t.strip() for t in summands if _PLAIN.match(t.strip())}
    for t in list(registry.values()):
        if t.var in plain and t.var not in entries:
            entries.insert(0, t.var)
    rhs_new = '+'.join(out)
    return f'{lhs.rstrip()} ~ {" ".join(rhs_new.split())}', entries, registry, caret
