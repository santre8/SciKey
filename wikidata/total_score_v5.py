import numpy as np
import pandas as pd
from pathlib import Path

from sklearn.model_selection import train_test_split, GridSearchCV, GroupKFold
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report, f1_score

# ============================================================
# 1. Load original feature CSV
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

# ADJUST THIS PATH TO YOUR CSV
csv_path = Path(r"C:\Users\sanda\Documents\Langara_College\DANA-4850-001-Capstone_Project\hall-api-test-db-mysql\wikidata\debug_scores_mode_upec_n_y.csv")

print("Reading:", csv_path)
df = pd.read_csv(csv_path)

# ============================================================
# 2. Define features
# ============================================================

feature_cols = [
    "ctx",
    "sl_log1p",
    "p31_cnt",
    "p279_cnt",
    "ctx_p31",
    "ctx_p279",
    "alias_inv",
    "exact_label",
    "exact_alias",
]

# If additional features exist, add them
optional = ["lbl_sim", "ctx_label_overlap", "alias_count"]
for col in optional:
    if col in df.columns:
        feature_cols.append(col)

print("\nFeatures used:")
print(feature_cols)

# Target
y_all = df["y"]

# In case there are NaNs in any feature
df[feature_cols] = df[feature_cols].fillna(0.0)

# ============================================================
# 3. Split by keyword (not by row)
# ============================================================

df["query"] = df["kw"].astype(str)
queries = df["query"].unique()

q_train, q_test = train_test_split(
    queries,
    test_size=0.30,
    random_state=42,
)

train_df = df[df["query"].isin(q_train)].copy()
test_df  = df[df["query"].isin(q_test)].copy()

X_train = train_df[feature_cols]
y_train = train_df["y"].astype(int)

X_test  = test_df[feature_cols]
y_test  = test_df["y"].astype(int)

# ============================================================
# 4. GridSearch with GroupKFold (CV by keyword)
# ============================================================

print("\n# ====== GRID SEARCH (GroupKFold by keyword) ======")

groups = train_df["query"]

cv = GroupKFold(n_splits=5)

base_logreg = LogisticRegression(
    max_iter=5000,
    class_weight="balanced",   # for the grid; later we reinforce positives more
    solver="lbfgs",
    penalty="l2",
)

param_grid = {
    "C": [0.1, 0.3, 1, 3, 10, 30, 100, 300],
}

grid = GridSearchCV(
    estimator=base_logreg,
    param_grid=param_grid,
    cv=cv,
    n_jobs=-1,
    scoring="f1",              # better than accuracy for imbalanced datasets
    verbose=1,
)

grid.fit(X_train, y_train, groups=groups)

best_C = grid.best_params_["C"]
print("\n✔ Best C found:", best_C)
print("Best F1 (CV):", grid.best_score_)

# ============================================================
# 5. Train final model with best C and reinforced weights
# ============================================================

print("\n# ====== TRAINING FINAL MODEL ======")

# Reinforce positive class more (you can adjust 6.0 to 4.0 or 8.0 if needed)
class_weight_final = {0: 1.0, 1: 6.0}

model = LogisticRegression(
    C=best_C,
    class_weight=class_weight_final,
    solver="lbfgs",
    max_iter=5000,
    penalty="l2",
)

model.fit(X_train, y_train)

# ============================================================
# 6. Evaluation on test
# ============================================================

y_pred = model.predict(X_test)
y_proba = model.predict_proba(X_test)[:, 1]

acc = accuracy_score(y_test, y_pred)
f1  = f1_score(y_test, y_pred)
cm  = confusion_matrix(y_test, y_pred)

print("\n=========== TEST RESULTS ===========")
print(f"Accuracy: {acc * 100:.2f}%")
print(f"F1-score: {f1:.4f}")
print("Confusion matrix:")
print(cm)
print("\nClassification report:")
print(classification_report(y_test, y_pred, digits=4))

# ============================================================
# 7. Show weights on console
# ============================================================

print("\n=========== WEIGHTS (coefficients) ===========")
weights = model.coef_[0]
intercept = model.intercept_[0]

for name, w in zip(feature_cols, weights):
    print(f"{name:20s} = {w:.6f}")
print("intercept:", intercept)

# ============================================================
# 8. Export weights to CSV
# ============================================================

weights_df = pd.DataFrame({
    "feature": feature_cols + ["intercept"],
    "weight": list(weights) + [intercept]
})

output_path = BASE_DIR / "logreg_weights_groupkfold_v1.csv"
weights_df.to_csv(output_path, index=False, encoding="utf-8")

print("\n✔ CSV generated with final weights:")
print(output_path)

# ============================================================
# 9. Export model metrics to CSV
# ============================================================

# Confusion matrix unpack
tn, fp, fn, tp = cm.ravel()

metrics_df = pd.DataFrame([{
    "best_C": best_C,
    "cv_best_f1": grid.best_score_,
    "test_accuracy": acc,
    "test_f1": f1,
    "true_positives": tp,
    "false_positives": fp,
    "true_negatives": tn,
    "false_negatives": fn,
    "n_train_rows": len(train_df),
    "n_test_rows": len(test_df),
    "n_train_keywords": len(q_train),
    "n_test_keywords": len(q_test),
}])

metrics_output_path = BASE_DIR / "logreg_metrics_groupkfold_v1.csv"
metrics_df.to_csv(metrics_output_path, index=False, encoding="utf-8")

print("\n✔ CSV generated with model metrics:")
print(metrics_output_path)

import statsmodels.api as sm

X_train_sm = sm.add_constant(X_train)
logit_model = sm.Logit(y_train, X_train_sm)
result = logit_model.fit()

print(result.summary())
