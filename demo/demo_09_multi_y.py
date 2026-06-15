"""Demo 9: Multiple dependent variables.

When options.y is a list, kbstat iterates over the variables and runs the full
analysis pipeline independently for each one. Results are saved into per-variable
subdirectories under out_dir.

Here all four iris measurements (sepal length/width, petal length/width) are
analysed against species with the same model — four separate LMs from a single
options block.

Dataset: iris (R base / Fisher, 1936). 150 observations, 3 species × 50 plants.
"""

import sys, os
DEMO_DIR = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(DEMO_DIR, '..'))

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file = os.path.join(DEMO_DIR, 'data', 'iris.csv')            # input data file
options.out_dir = os.path.join(DEMO_DIR, 'results', 'demo_08_multi_y')  # output folder (subfolders per variable)
options.y       = 'Sepal.Length, Sepal.Width, Petal.Length, Petal.Width'  # dependent variables (comma-separated)
options.y_units = 'cm'                                                    # unit label for y-axis (same for all variables)
options.x       = 'Species'      # fixed-effect factor

kb = Kbstat(options)
kb.run()
