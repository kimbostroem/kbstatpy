#!/usr/bin/env Rscript
# Export standard R datasets to CSV for kbstatpy demos.
# Run once from the repo root: Rscript demo/export_datasets.R

suppressMessages(library(lme4))
suppressMessages(library(nlme))

dir.create("demo/data", showWarnings = FALSE)

# --- Demo 1 & 2: sleep (unpaired and paired t-test) ---
# extra: increase in hours of sleep; group: drug 1 or 2; ID: patient
write.csv(sleep, "demo/data/sleep.csv", row.names = FALSE)
cat("Exported sleep.csv\n")

# --- Demo 3: ToothGrowth (two-way ANOVA) ---
# len: tooth length; supp: supplement type; dose converted to factor
tg <- ToothGrowth
tg$dose <- factor(tg$dose, levels = c(0.5, 1, 2), labels = c("low", "medium", "high"))
write.csv(tg, "demo/data/toothgrowth.csv", row.names = FALSE)
cat("Exported toothgrowth.csv\n")

# --- Demo 4 & 5: sleepstudy (LMM, with and without random slopes) ---
# Reaction: reaction time (ms); Days binned into Period factor; Subject: ID
ss <- as.data.frame(sleepstudy)
ss$Period <- factor(ifelse(ss$Days < 5, "rested", "deprived"),
                    levels = c("rested", "deprived"))
write.csv(ss, "demo/data/sleepstudy.csv", row.names = FALSE)
cat("Exported sleepstudy.csv\n")

# --- Demo 6: Oats (GLMM gamma) ---
# yield: oat yield (bushels/acre); Variety: 3 varieties;
# Nitrogen: 4 levels of nitrogen concentration; Block: 6 blocks
oats <- as.data.frame(nlme::Oats)
oats$Nitrogen <- factor(oats$nitro,
                        levels = c(0, 0.2, 0.4, 0.6),
                        labels = c("N0", "N1", "N2", "N3"))
oats$nitro <- NULL
write.csv(oats, "demo/data/oats.csv", row.names = FALSE)
cat("Exported oats.csv\n")

cat("Done. All datasets written to demo/data/\n")
