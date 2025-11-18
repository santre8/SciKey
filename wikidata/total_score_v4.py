import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix

# ============================================================
# 1. Cargar CSV original de features
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
csv_path = BASE_DIR / (r"C:\Users\sanda\Documents\Langara_College\DANA-4850-001-Capstone_Project\hall-api-test-db-mysql\wikidata\debug_scores_mode_upec_y_v4.csv")

print("Leyendo:", csv_path)
df = pd.read_csv(csv_path)

# ============================================================
# 2. Features principales
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

# Si existen features adicionales, agrégalas
optional = ["lbl_sim", "ctx_label_overlap", "alias_count"]
for col in optional:
    if col in df.columns:
        feature_cols.append(col)

print("\nFeatures usados:")
print(feature_cols)

X_all = df[feature_cols]
y_all = df["y"]

# ============================================================
# 3. Split por keyword (no por fila)
# ============================================================

df["query"] = df["kw"].astype(str)

queries = df["query"].unique()
q_train, q_test = train_test_split(
    queries,
    test_size=0.30,
    random_state=42
)

train_df = df[df["query"].isin(q_train)]
test_df  = df[df["query"].isin(q_test)]

X_train = train_df[feature_cols]
y_train = train_df["y"]

X_test  = test_df[feature_cols]
y_test  = test_df["y"]

# ============================================================
# 4. GridSearch para optimizar C
# ============================================================

logreg = LogisticRegression(
    max_iter=5000,
    class_weight="balanced",
    solver="lbfgs",
    penalty="l2",
)

param_grid = {
    "C": [0.1, 0.3, 1, 3, 10, 30, 100, 300]
}

print("\nBuscando mejor C...")
grid = GridSearchCV(logreg, param_grid, cv=5, n_jobs=-1)
grid.fit(X_train, y_train)

best_C = grid.best_params_["C"]
print("✔ Mejor C encontrado:", best_C)

# ============================================================
# 5. Entrenar modelo final con el mejor C
# ============================================================

model = LogisticRegression(
    C=best_C,
    class_weight="balanced",
    solver="lbfgs",
    max_iter=5000
)

model.fit(X_train, y_train)

# ============================================================
# 6. Evaluación en test
# ============================================================

y_pred = model.predict(X_test)
acc = accuracy_score(y_test, y_pred)
cm  = confusion_matrix(y_test, y_pred)

print("\n=========== RESULTADOS ===========")
print(f"Accuracy test: {acc * 100:.2f}%")
print("Matriz de confusión:")
print(cm)

print("\n=========== PESOS ===========")
weights = model.coef_[0]
intercept = model.intercept_[0]

for name, w in zip(feature_cols, weights):
    print(f"{name:20s} = {w:.6f}")
print("intercept:", intercept)

# ============================================================
# 7. EXPORTAR PESOS A CSV
# ============================================================

weights_df = pd.DataFrame({
    "feature": feature_cols + ["intercept"],
    "weight": list(weights) + [intercept]
})

output_path = BASE_DIR / "logreg_weights_final_v4.csv"
weights_df.to_csv(output_path, index=False, encoding="utf-8")

print("\n✔ CSV generado con pesos finales:")
print(output_path)
