import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

# ==============================================================
# 1. Cargar el CSV que ya generaste con tus features
# ==============================================================

#df = pd.read_csv(r"C:\Users\sanda\Documents\Langara_College\DANA-4850-001-Capstone_Project\hall-api-test-db-mysql\wikidata\debug_scores_mode_upec_y.csv")   # <-- AJUSTA EL NOMBRE SI NECESITA

import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix

# ==============================================================
# 1. Cargar el CSV (mismo folder que este script)
# ==============================================================

BASE_DIR = Path(__file__).resolve().parent
csv_path = BASE_DIR / (r"C:\Users\sanda\Documents\Langara_College\DANA-4850-001-Capstone_Project\hall-api-test-db-mysql\wikidata\debug_scores_mode_upec_y.csv")

print(f"Leyendo CSV desde: {csv_path}")
df = pd.read_csv(csv_path)

print("Columnas encontradas:")
print(df.columns.tolist())

# ==============================================================
# 2. Definir features y target
# ==============================================================

# Usamos exactamente las columnas que tiene tu archivo
feature_cols = [
    "ctx",        # similitud de contexto 0..100
    "sl_log1p",   # log(1 + sitelinks)
    "p31_cnt",    # número de P31
    "p279_cnt",   # número de P279
    "ctx_p31",    # fuzzy ctx vs P31
    "ctx_p279",   # fuzzy ctx vs P279
    "alias_inv",  # score inverso según #aliases
    "exact_label",# 1 si label exacto
    "exact_alias" # 1 si alias exacto
]

for col in feature_cols + ["y"]:
    if col not in df.columns:
        raise ValueError(f"Falta la columna en el CSV: {col}")

X = df[feature_cols]
y = df["y"]

print("\nFeatures usadas:")
print(feature_cols)

# ==============================================================
# 3. Train / test split
# ==============================================================

X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=0.30,
    random_state=42,
    stratify=y
)

# ==============================================================
# 4. Modelo de regresión logística (sin escalado)
#    -> los coeficientes quedan en la escala original
# ==============================================================

model = LogisticRegression(
    penalty="l2",
    C=1.0,
    fit_intercept=True,
    max_iter=5000,
    solver="lbfgs"
)

print("\nEntrenando modelo...")
model.fit(X_train, y_train)
print("✔ Modelo entrenado.")

# ==============================================================
# 5. Evaluación
# ==============================================================

y_pred = model.predict(X_test)
acc = accuracy_score(y_test, y_pred)
cm  = confusion_matrix(y_test, y_pred)

print("\n=========== RESULTADOS ===========")
print(f"Accuracy Top-1 en test: {acc*100:.2f}%")
print("\nMatriz de confusión (rows = y_real, cols = y_pred):")
print(cm)

# ==============================================================
# 6. Extraer coeficientes (pesos) y guardarlos
# ==============================================================

coef = model.coef_[0]
intercept = model.intercept_[0]

print("\n=========== PESOS APRENDIDOS ===========")
for name, w in zip(feature_cols, coef):
    print(f"{name:12s} = {w:.6f}")
print(f"\nIntercepto = {intercept:.6f}")

weights_df = pd.DataFrame({
    "feature": feature_cols + ["intercept"],
    "weight":  list(coef) + [intercept]
})

out_path = BASE_DIR / "learned_weights_upec.csv"
weights_df.to_csv(out_path, index=False)
print(f"\n✔ Pesos guardados en: {out_path}")

