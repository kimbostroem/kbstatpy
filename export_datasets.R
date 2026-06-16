#!/usr/bin/env Rscript
# Export standard R datasets to CSV for kbstatpy demos.
# Run once from the repo root: Rscript export_datasets.R

suppressMessages(library(lme4))
suppressMessages(library(nlme))

dir.create("demo/data", showWarnings = FALSE)

# --- Demos 1 & 2: sleep (unpaired and paired t-test) ---
# extra: increase in hours of sleep; group: drug 1 or 2; ID: patient
write.csv(sleep, "demo/data/sleep.csv", row.names = FALSE)
cat("Exported sleep.csv\n")

# --- Demo 3: ToothGrowth (two-way ANOVA) ---
# len: tooth length (mm); supp: supplement type; dose: low/medium/high
tg <- ToothGrowth
tg$dose <- factor(tg$dose, levels = c(0.5, 1, 2), labels = c("low", "medium", "high"))
write.csv(tg, "demo/data/toothgrowth.csv", row.names = FALSE)
cat("Exported toothgrowth.csv\n")

# --- Demo 4: ergoStool (one-way repeated-measures ANOVA via LMM) ---
# effort: perceived effort to arise (Borg scale); Type: stool type T1-T4 (within-subject factor);
# Subject: 9 subjects, exactly one measurement per subject per stool type (balanced, no replication)
es <- as.data.frame(ergoStool)
es$Subject <- factor(as.character(es$Subject))   # drop the ordered-factor ordering
write.csv(es, "demo/data/ergostool.csv", row.names = FALSE)
cat("Exported ergostool.csv\n")

# --- Demos 6 & 7: sleepstudy (random slopes; log-transformed LMM) ---
# Reaction: reaction time (ms); Days binned into Period factor; Subject: ID
ss <- as.data.frame(sleepstudy)
ss$Period <- factor(ifelse(ss$Days < 5, "rested", "deprived"),
                    levels = c("rested", "deprived"))
write.csv(ss, "demo/data/sleepstudy.csv", row.names = FALSE)
cat("Exported sleepstudy.csv\n")

# --- Demo 8: Oats (GLMM gamma) ---
# yield: oat yield (qt/plot); Variety: 3 varieties;
# Nitrogen: 4 levels; Block: 6 blocks
oats <- as.data.frame(nlme::Oats)
oats$Nitrogen <- factor(oats$nitro,
                        levels = c(0, 0.2, 0.4, 0.6),
                        labels = c("0.0", "0.2", "0.4", "0.6"))
oats$nitro <- NULL
write.csv(oats, "demo/data/oats.csv", row.names = FALSE)
cat("Exported oats.csv\n")

# --- Demo 9: npk (LMM with partial interaction) ---
# yield: pea yield (lb/plot); N/P/K: binary treatment factors; block: 6 blocks
write.csv(npk, "demo/data/npk.csv", row.names = FALSE)
cat("Exported npk.csv\n")

# --- Demo 12: iris (multi-y GLMM + correlation) ---
# Sepal.Length/Width, Petal.Length/Width (cm); Species: 3 species
write.csv(iris, "demo/data/iris.csv", row.names = FALSE)
cat("Exported iris.csv\n")

# --- Demo 13: mtcars (VIF with mixed predictors) ---
# mpg, cyl, hp, wt and other continuous/categorical car performance variables
write.csv(mtcars, "demo/data/mtcars.csv", row.names = TRUE)
cat("Exported mtcars.csv\n")

# --- Demo 5: longley (standalone correlation) ---
# GNP.deflator, GNP, Unemployed, Armed.Forces, Population, Year, Employed
# Classic high-multicollinearity dataset (Longley, 1967)
write.csv(longley, "demo/data/longley.csv", row.names = FALSE)
cat("Exported longley.csv\n")

# --- Demo 10: stackloss (LM with outliers) ---
# stack.loss: percentage of ammonia lost; Air.Flow, Water.Temp, Acid.Conc: process variables
# Observations 1, 3, 4, 21 are documented outliers (Brownlee, 1965)
write.csv(stackloss, "demo/data/stackloss.csv", row.names = FALSE)
cat("Exported stackloss.csv\n")

# --- Demo 11: bacteria (GLMM binomial) ---
# present: bacteria presence (1) / absence (0); trt: placebo/drug/drug+
# week: time point (factor); ID: child ID (random effect)
bact <- MASS::bacteria
bact$present <- as.integer(bact$y == "y")
bact$week    <- factor(bact$week)
bact <- bact[, c("ID", "trt", "week", "present")]
write.csv(bact, "demo/data/bacteria.csv", row.names = FALSE)
cat("Exported bacteria.csv\n")

cat("\nDone. All datasets written to demo/data/\n")
