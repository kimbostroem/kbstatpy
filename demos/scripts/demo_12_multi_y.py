"""Demo 12: Multiple dependent variables combined with correlation analysis.

When options.y is a list, kbstat iterates over the variables and runs the full
analysis pipeline independently for each one. Results are saved into per-variable
subdirectories under out_dir.

Setting options.correlation runs a pairwise Pearson correlation independently
of the GLMM — both analyses share the same options block and input file.

Here all four iris measurements are analysed against species (four separate LMs)
and also correlated with each other in a single run. The setosa species is excluded
via options.constraints to illustrate categorical filtering — only versicolor and
virginica are compared.

Dataset: iris (R base / Fisher, 1936). 150 observations, 3 species × 50 plants.
"""

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file = '../data/iris.csv'                          # input data file
options.out_dir = 'results/demo_12_multi_y'                # output folder (subfolders per variable)
options.y           = 'Sepal.Length, Sepal.Width, Petal.Length, Petal.Width'  # dependent variables (comma-separated)
options.y_units     = 'cm'                                                    # unit label for y-axis (same for all variables)
options.x           = 'Species'                                               # fixed-effect factor
options.constraints = 'Species != "setosa"'                                   # exclude setosa — compare versicolor vs virginica only
options.correlation = options.y  # also run pairwise correlation on all dependent variables (must be numerical)
options.rename      = 'Sepal.Length -> SepalLength; Sepal.Width -> SepalWidth; Petal.Length -> PetalLength; Petal.Width -> PetalWidth'
# options.correlation = 'Sepal.Length, Sepal.Width, Petal.Length, Petal.Width'  # equivalent explicit form

kb = Kbstat(options)
kb.run()
