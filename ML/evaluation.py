"""라벨 있는 불량 표본이 극히 적은(CN7 17건, RG3 25건) 상황에서 신뢰할 수
있는 성능 지표를 얻기 위한 층화 K-fold 교차검증 하리네스.

단 한 번의 train/test 분리로 평가하면 어떤 몇 건이 테스트 폴드에
들어가느냐에 따라 recall/precision이 크게 흔들린다(직접 확인 결과 CN7은
불량 3~4건, RG3는 5건만 테스트에 들어가는 수준). 5-fold 교차검증으로 모든
라벨 데이터가 한 번씩은 평가에 쓰이도록 하고 그 평균을 최종 성능으로
본다. 정규화(StandardScaler)는 데이터 누수를 막기 위해 매 fold의 학습
데이터로만 fit한다.
"""

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.base import ClassifierMixin
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

from ML.semi_supervised import evaluation, pseudo_label_train

ModelFactory = Callable[[], ClassifierMixin]


@dataclass
class CVResult:
    """fold별 지표와 합산 혼동행렬."""

    fold_metrics: list[dict] = field(default_factory=list)

    def summary(self) -> pd.Series:
        keys = ["accuracy", "precision", "recall", "f1", "roc_auc"]
        table = pd.DataFrame(
            [{k: fold[k] for k in keys} for fold in self.fold_metrics]
        )
        return table.mean()

    def pooled_confusion_matrix(self) -> np.ndarray:
        return sum(fold["confusion_matrix"] for fold in self.fold_metrics)


def cross_validate(
    model_factory: ModelFactory,
    X_labeled: pd.DataFrame,
    y_labeled: pd.Series,
    X_unlabeled: pd.DataFrame | None = None,
    use_pseudo_labeling: bool = False,
    n_splits: int = 5,
    percentage: float = 10,
    unlabeled_usage: float = 90,
    random_state: int = 42,
) -> CVResult:
    """StratifiedKFold로 라벨 데이터를 나눠 fold마다 학습/평가를 반복한다.

    use_pseudo_labeling=True면 fold의 학습 폴드 + X_unlabeled로
    pseudo_label_train()을 실행한다. False면 fold의 학습 폴드만으로
    일반 지도학습을 수행한다(이 데이터셋에서는 라벨 수가 너무 적어
    pseudo-labeling이 오히려 성능을 깎아먹는 경우가 많아 기본값을
    False로 둔다. ML/dataset.py, scripts/run_semi_supervised.py 참고).
    """
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    result = CVResult()

    for train_index, test_index in cv.split(X_labeled, y_labeled):
        X_train_raw = X_labeled.iloc[train_index]
        X_test_raw = X_labeled.iloc[test_index]
        y_train = y_labeled.iloc[train_index].reset_index(drop=True)
        y_test = y_labeled.iloc[test_index].reset_index(drop=True)

        scaler = StandardScaler().fit(X_train_raw)
        columns = X_train_raw.columns
        X_train = pd.DataFrame(
            scaler.transform(X_train_raw), columns=columns
        ).reset_index(drop=True)
        X_test = pd.DataFrame(
            scaler.transform(X_test_raw), columns=columns
        ).reset_index(drop=True)

        if use_pseudo_labeling:
            if X_unlabeled is None:
                raise ValueError("use_pseudo_labeling=True면 X_unlabeled가 필요합니다.")
            X_unlabeled_scaled = pd.DataFrame(
                scaler.transform(X_unlabeled[columns]), columns=columns
            ).reset_index(drop=True)
            fold_result = pseudo_label_train(
                model_factory(),
                X_train,
                y_train,
                X_test,
                y_test,
                X_unlabeled_scaled,
                percentage=percentage,
                unlabeled_usage=unlabeled_usage,
            )
            result.fold_metrics.append(fold_result.final_metrics)
        else:
            model = model_factory()
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            y_score = model.predict_proba(X_test)[:, 1]
            result.fold_metrics.append(evaluation(y_test, y_pred, y_score))

    return result
