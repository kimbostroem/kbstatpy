"""Demo 20 — Several input files: one file per subject

Lab data often come as one file per subject or session, named after it:
`subject_308.csv`, `subject_309.csv`, ... with no subject column inside, because
the file name says whose data it is. `options.in_file` can name a whole folder
(or a pattern such as 'data/subject_*.csv', or files separated by ';'), and
kbstatpy stacks the files row by row. Each row's source goes into a new column
`file`, the file name without extension, and that column is the subject ID.

The data are those of demo 6, `sleepstudy` (lme4; Belenky et al. 2003): reaction
times of 18 subjects over ten days of sleep restriction, here a rested block
(days 0-4) against a deprived one (days 5-9). `sleepstudy_subjects/` holds them
as 18 files of ten rows each. The model is demo 6's, with the file as subject:

    Reaction ~ Period + (1 + Period|file)

and the results are identical to demo 6, which reads the same data from one
file with a Subject column. `rename = 'file -> Subject'` shows the column as
Subject in the tables and the plot.

The files are read in natural order (subject_2 would come before subject_10),
the same on every machine, and Summary.txt lists them with their row counts.
For one separate analysis per file, set `split = 'file'` instead of `id`.
"""

import os

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file      = os.path.join(options.demo_dir, 'data/sleepstudy_subjects')  # a folder: all its data files
options.out_dir      = 'results/demo_20_several_files'   # output folder
options.y            = 'Reaction'        # dependent variable
options.y_units      = 'ms'             # unit label for y-axis
options.x            = 'Period'          # fixed-effect factor(s)
options.id           = 'file'            # the source file of each row is the subject
options.slope        = 'Period'          # random slope: each subject gets their own Period effect
options.rename       = 'Reaction -> ReactionTime; Period -> Day; file -> Subject'

kb = Kbstat(options)
kb.run_save()
