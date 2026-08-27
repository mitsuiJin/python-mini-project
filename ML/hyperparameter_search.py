"""[코드49] GridSearchCV + StratifiedKFold를 이용한 하이퍼파라미터 탐색.

가이드북 원본은 SVM에서 C·gamma를 1e-4 * (1~100) 범위로 촘촘하게(약 1만
조합) 탐색하고 RandomForest도 n_estimators까지 넓게 탐색하지만, 그대로
재현하면 CV 학습이 지나치게 오래 걸린다. 여기서는 같은 하이퍼파라미터
축을 사용하되 격자를 성능이 실용적인 수준으로 줄였다.

가이드북은 SVM에 class_weight={0:100.0, 1:1.0}(다수 클래스에 더 큰 가중치)을
그대로 사용하는데, 이는 소수 클래스(불량)를 잘 못 잡는 방향으로 학습을
유도해 실제로 가이드북 결과표에서도 SVM의 재현율이 가장 낮게 나온
원인으로 보인다. 이 리포지토리의 라벨 관례(0=양품, 1=불량, 소수 클래스가
불량)에서는 표준적인 class_weight='balanced'를 사용한다.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.svm import SVC


def search_svm_params(
    X: pd.DataFrame, y: pd.Series, n_splits: int = 5, random_state: int = 42
) -> dict:
    param_grid = {
        "kernel": ["rbf"],
        "C": np.logspace(-2, 2, 5).tolist(),
        "gamma": np.logspace(-3, 1, 5).tolist(),
    }
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    search = GridSearchCV(
        SVC(class_weight="balanced", random_state=random_state),
        param_grid=param_grid,
        scoring="f1",
        cv=cv,
        n_jobs=1,
    )
    search.fit(X, y)
    return search.best_params_


def search_random_forest_params(
    X: pd.DataFrame, y: pd.Series, n_splits: int = 5, random_state: int = 42
) -> dict:
    param_grid = {
        "n_estimators": [200, 400, 800],
        "max_depth": [5, 10, None],
        "min_samples_split": [2, 5, 10],
        "min_samples_leaf": [1, 2, 4],
        "max_features": ["sqrt", "log2"],
    }
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    search = GridSearchCV(
        RandomForestClassifier(class_weight="balanced", random_state=random_state),
        param_grid=param_grid,
        scoring="f1",
        cv=cv,
        n_jobs=1,
    )
    search.fit(X, y)
    return search.best_params_
