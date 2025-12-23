from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
import numpy as np

# Requires df from previous script
# df must have a binary label column, e.g. df["is_positive"] in {0,1}
LABEL_COL = "is_positive"

if LABEL_COL not in df.columns:
    raise ValueError(f"Add {LABEL_COL} column to merged CSV (0/1) before training.")

X = df[[delta_col, "texture_score"]].apply(pd.to_numeric, errors="coerce")
y = df[LABEL_COL].astype(int)

# Drop rows with NaNs in features
mask = X.notnull().all(axis=1) & y.notnull()
X = X[mask]
y = y[mask]

model = Pipeline([
    ("scaler", StandardScaler()),                 # correct math: fit on train folds only
    ("clf", LogisticRegression(max_iter=2000))
])

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
auc = cross_val_score(model, X, y, cv=cv, scoring="roc_auc")

print("AUC per fold:", np.round(auc, 3))
print("Mean AUC:", float(np.mean(auc)))
