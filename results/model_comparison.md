# Model comparison (Part A, step 2: "train and compare different ML models for each case")

This study chose the model family that the Phase 7 per-current models (`src/dvdml/ml_v2.py`) build on. It was run on branch `main`
(`scripts/03_train_compare_models.py`, `scripts/04_select_and_evaluate.py`, `src/dvdml/ml.py`). This branch keeps only the result.
The full tables are on `main` in `results/models/comparison_val.csv`, `comparison_val_by_current.csv` and `all_trials_val.csv` (64 trials).

## Setup

- **Data:** the specified 10,000-row dataset per case, split 70/15/15 with seed 20261105. The split is the same one this branch
  uses (`data/splits/<case>.npz`).
- **Inputs:** 15 physics features (`ml.featurize`).
- **Target:** the signed log of each current, `asinh(I / 1e-15 A) / ln 10`. One multi-output model predicts id, ig, is and ib.
- **Selection:** on the VALIDATION set only. Score = 0.5 * (median + P95 relative error), lower is better, macro-averaged over
  the currents that are above the 1e-15 A noise floor in at least 5 % of rows. OFF-state ig is pure noise and is not scored.
- **Hyper-parameter grids (tuned on validation):**

| Family | Implementation | Grid |
|---|---|---|
| MLP | PyTorch float64, tanh, Adam + cosine LR, best-validation epoch, L-BFGS polish | hidden (96,96,96) or (128,128,128), 1200 epochs |
| LightGBM | one booster per current, early stopping on validation | num_leaves 31 or 127 |
| Kernel ridge | RBF kernel | gamma {0.01, 0.03, 0.1} x alpha {1e-5, 1e-3} |
| Polynomial ridge | polynomial features + ridge | degree {3, 4} x alpha {1e-3, 0.1, 10} |

## Validation results (best configuration of each family; winner in bold)

| Case | Family | Best hyper-parameters | R² (signed-log) | Median err | P95 err | Score | Fit time (s) |
|---|---|---|---|---|---|---|---|
| nmos_on | **mlp** | hidden (128, 128, 128), 1200 epochs | 0.9963 | 4.3 % | 22.3 % | **0.133** | 267 |
| nmos_on | lightgbm | num_leaves 31 | 0.9976 | 12.6 % | 61.7 % | 0.372 | 87 |
| nmos_on | kernel_ridge | gamma 0.01, alpha 0.001 | 0.9281 | 69.4 % | 5359.9 % | 27.147 | 10 |
| nmos_on | poly_ridge | degree 4, alpha 10 | 0.9068 | 71.4 % | 30690.4 % | 153.809 | 8 |
| nmos_off | **mlp** | hidden (96, 96, 96), 1200 epochs | 0.9951 | 1.7 % | 14.8 % | **0.083** | 255 |
| nmos_off | lightgbm | num_leaves 31 | 0.9794 | 8.8 % | 63.2 % | 0.360 | 66 |
| nmos_off | kernel_ridge | gamma 0.01, alpha 0.001 | 0.9316 | 42.7 % | 161.3 % | 1.020 | 7 |
| nmos_off | poly_ridge | degree 4, alpha 0.1 | 0.9302 | 41.7 % | 233.0 % | 1.373 | 4 |
| pmos_on | **mlp** | hidden (96, 96, 96), 1200 epochs | 0.9995 | 2.0 % | 12.2 % | **0.071** | 236 |
| pmos_on | lightgbm | num_leaves 31 | 0.9968 | 13.1 % | 66.0 % | 0.396 | 41 |
| pmos_on | kernel_ridge | gamma 0.01, alpha 0.001 | 0.9327 | 68.4 % | 4639.7 % | 23.541 | 5 |
| pmos_on | poly_ridge | degree 4, alpha 10 | 0.9137 | 70.1 % | 27706.8 % | 138.884 | 4 |
| pmos_off | **mlp** | hidden (128, 128, 128), 1200 epochs | 0.9950 | 4.3 % | 24.8 % | **0.145** | 189 |
| pmos_off | lightgbm | num_leaves 31 | 0.9785 | 8.6 % | 65.1 % | 0.368 | 21 |
| pmos_off | kernel_ridge | gamma 0.03, alpha 0.001 | 0.9383 | 35.7 % | 151.7 % | 0.937 | 5 |
| pmos_off | poly_ridge | degree 4, alpha 0.001 | 0.9287 | 40.1 % | 187.5 % | 1.138 | 4 |

## Outcome

- **The MLP wins all four cases.** Its score is 2.5-5x better than LightGBM, the runner-up, and far better than the kernel and
  polynomial ridge models, whose P95 errors are in the hundreds to tens of thousands of percent.
- LightGBM sometimes has a similar R² (NMOS ON 0.9976). R² on the log scale hides relative errors of 10-60 %, which is why the
  score uses relative-error percentiles.
- Test-set results of the winning multi-output MLP (`main`, `results/models/test_results.csv`), median / P95 error:
  NMOS ON 4.1 / 22.7 %, NMOS OFF 1.6 / 20.2 %, PMOS ON 1.9 / 11.3 %, PMOS OFF 4.2 / 22.7 %.
  Gate-level mean accuracy was 92.8 % and parity checker 92.5 %.
- **Phase 7 (this branch)** keeps the winning family (tanh MLP, Adam + L-BFGS polish) and changes how it is used: one MLP
  ensemble per current, physics features, width-normalised targets and rail-corner training data. See `README.md` and
  `results/models/test_results.csv` for the resulting models.
