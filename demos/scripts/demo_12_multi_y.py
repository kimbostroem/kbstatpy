"""Demo 12 — Multiple dependent variables + correlation

Research questions often span several outcomes at once; kbstatpy can run the whole
pipeline for each in a single call and correlate them together. This demo shows
that on the `iris` dataset (R base; Fisher 1936): the four flower measurements of
150 plants across three species, with `setosa` excluded so only versicolor and
virginica are compared.

Passing a list to `options.y` runs the full pipeline once per measurement:

    {Sepal.Length, Sepal.Width, Petal.Length, Petal.Width} ~ Species

with results saved into per-variable subdirectories, and a shared pairwise
correlation among the four measurements computed in the same call. The
`constraints = 'Species != "setosa"'` filter demonstrates categorical row
selection.
"""

import os

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file = os.path.join(options.demo_dir, 'data/iris.csv')                          # input data file
options.out_dir = os.path.join(options.working_dir, 'results/demo_12_multi_y')                # output folder (subfolders per variable)
options.y           = 'Sepal.Length, Sepal.Width, Petal.Length, Petal.Width'  # dependent variables (comma-separated)
options.y_units     = 'cm'                                                    # unit label for y-axis (same for all variables)
options.x           = 'Species'                                               # fixed-effect factor
options.constraints = 'Species != "setosa"'                                   # exclude setosa — compare versicolor vs virginica only
options.correlation = options.y  # also run pairwise correlation on all dependent variables (must be numerical)
options.rename      = 'Sepal.Length -> SepalLength; Sepal.Width -> SepalWidth; Petal.Length -> PetalLength; Petal.Width -> PetalWidth'
# options.correlation = 'Sepal.Length, Sepal.Width, Petal.Length, Petal.Width'  # equivalent explicit form

kb = Kbstat(options)
kb.run_save()
