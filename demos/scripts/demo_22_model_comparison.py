#!/usr/bin/env python3
"""Demo 22 — Comparing model structures (model_comparison)

Which fixed-effect structure do the data support: the additive model, every
two-way interaction, or the full factorial? `options.model_comparison = True`
answers that next to the analysis, without changing it. Summary.txt gets a table
MODEL STRUCTURE COMPARISON with the maximum-likelihood AIC and BIC of each
structure (random effects held fixed, so only the fixed effects vary), the fitted
one marked, and a verdict that reads the table: structures within 2 AIC of each
other are not told apart.

It is a report, not a selection. Choosing the structure by AIC and then quoting
that model's p-values makes them optimistic; the tested model follows from the
design, fixed before the data. See STATISTICAL_NOTES.md, "Model structure, and why
kbstatpy will not pick one for you".

Part A, ToothGrowth (R base): odontoblast length of 60 guinea pigs, vitamin C as
orange juice (OJ) or ascorbic acid (VC) at three doses. Two factors, so the ladder
has two rungs: additive `supp + dose` and full factorial `supp * dose`.

  1. y, x: the full factorial is fitted, and the table agrees (dAIC of the
     additive model 4.5).
  2. formula `len ~ supp + dose`: the additive model is fitted; the table names
     the full factorial as better supported, with the caveat about choosing.
  3. formula `len ~ supp + supp:dose`: written without the dose main effect, but
     R codes it as dose nested within supp, the same model as `supp * dose`.
     kbstatpy matches formulas to the ladder by likelihood, not by their text, so
     the full-factorial row is marked "fitted (same fit)".

Part B, npk (R base; also Demo 9): pea yield under nitrogen, phosphate and
potassium in six blocks, with a random intercept per block. Three factors, so the
ladder adds the rung "all two-way", `(N + P + K)^2`.

  4. formula `yield ~ (N + P + K)^2 + (1 | block)`: matched to "all two-way".
  5. formula `yield ~ N + P*K + (1 | block)`, Demo 9's partial interaction: equal
     to none of the rungs, so it gets its own row, "your formula".

In Part B all structures lie within about 2.6 AIC, and the verdict says the
criteria do not separate them: the data cannot tell these structures apart, which
is a finding in itself.
"""

import os

from kbstatpy import Kbstat, KbstatOptions


def toothgrowth():
    o = KbstatOptions()
    o.in_file          = os.path.join(o.demo_dir, 'data/toothgrowth.csv')  # input data file
    o.y_units          = 'mm'                       # unit label for y-axis
    o.x_order          = 'dose: low, medium, high'  # ordered doses
    o.model_comparison = True                       # the ladder of structures in Summary.txt
    return o


def npk():
    o = KbstatOptions()
    o.in_file          = os.path.join(o.demo_dir, 'data/npk.csv')
    o.y_units          = 'lb/plot'
    o.model_comparison = True
    return o


def show(title, kb):
    """Print the comparison table that Summary.txt also contains."""
    mc = kb.model_comparison_table
    print(f'\n=== {title}')
    print(mc[['Structure', 'Fixed effects', 'npar', 'AIC', 'dAIC', 'fitted']]
          .to_string(index=False, float_format=lambda v: f'{v:.1f}'))


# Part A, 1) y and x: the full factorial supp * dose (interaction 'auto').
o = toothgrowth()
o.y       = 'len'
o.x       = 'supp, dose'
o.out_dir = 'results/demo_22_model_comparison/A1_variables'
kb = Kbstat(o)
kb.run_save()
show('A1  y, x: supp * dose', kb)

# Part A, 2) an additive formula: the table argues for the interaction.
o = toothgrowth()
o.formula = 'len ~ supp + dose'
o.out_dir = 'results/demo_22_model_comparison/A2_additive'
kb = Kbstat(o)
kb.run_save()
show('A2  formula: len ~ supp + dose', kb)

# Part A, 3) written differently, the same model: matched by likelihood.
o = toothgrowth()
o.formula = 'len ~ supp + supp:dose'
o.out_dir = 'results/demo_22_model_comparison/A3_nested'
kb = Kbstat(o)
kb.run_save()
show('A3  formula: len ~ supp + supp:dose (dose within supp)', kb)

# Part B, 4) all two-way interactions of three factors.
o = npk()
o.formula = 'yield ~ (N + P + K)^2 + (1 | block)'
o.out_dir = 'results/demo_22_model_comparison/B4_two_way'
kb = Kbstat(o)
kb.run_save()
show('B4  formula: yield ~ (N + P + K)^2 + (1 | block)', kb)

# Part B, 5) a partial interaction (Demo 9): its own row.
o = npk()
o.formula = 'yield ~ N + P*K + (1 | block)'
o.out_dir = 'results/demo_22_model_comparison/B5_partial'
kb = Kbstat(o)
kb.run_save()
show('B5  formula: yield ~ N + P*K + (1 | block)', kb)
