"""가이드북 2.3.2절 '준지도 학습' 트랙 ([코드46]~[코드51]) 구현.

라벨 있는 데이터로 모델을 학습 -> 라벨 없는 데이터 중 예측 확신도가 가장
높은 상위 percentage%에 pseudo-label을 부여해 학습 데이터에 통합 ->
unlabeled 데이터의 unlabeled_usage%를 소진할 때까지 반복한다.

가이드북 원본([코드50])은 confidence 상위 percentage%를 클래스 구분 없이
통째로 뽑는다. 이 리포지토리의 라벨 데이터는 불량 비율이 1~2%대로 극단적
이라, 그렇게 뽑으면 확신도 높은 예측이 거의 다 양품이라서 pseudo-label이
양품 쪽으로만 쌓이고 반복할수록 불균형이 심해진다(RandomForest/SVM이
결국 "전부 양품"으로만 예측하는 상태로 수렴하는 것을 실제로 확인했다).
그래서 여기서는 confidence 상위 percentage%를 **예측 클래스별로 따로**
선택해 두 클래스의 pseudo-label이 비슷한 비율로 쌓이도록 한다.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.base import ClassifierMixin, clone
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def confident_prediction(proba: np.ndarray) -> np.ndarray:
    """[코드46]: 클래스별 확률 중 더 큰(모델이 확신하는) 값만 뽑아낸다.

    proba: predict_proba()의 결과 (n_samples, 2)
    """
    return proba.max(axis=1)


def evaluation(y_true, y_pred, y_score=None) -> dict:
    """[코드47]을 딕셔너리 반환 형태로 변형 (print 대신 리포트/UI에서 재사용)."""
    score_for_auc = y_score if y_score is not None else y_pred
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "roc_auc": roc_auc_score(y_true, score_for_auc),
        "confusion_matrix": confusion_matrix(y_true, y_pred),
    }


@dataclass
class SemiSupervisedResult:
    """반복 학습 과정의 매 스텝 평가 지표와 최종 학습된 모델."""

    model: ClassifierMixin
    history: list[dict] = field(default_factory=list)

    @property
    def final_metrics(self) -> dict:
        return self.history[-1]


def _select_pseudo_labels(
    without_label: pd.DataFrame, proba: np.ndarray, percentage: float
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """예측 클래스(0/1)별로 confidence 상위 percentage%를 따로 골라 합친다."""
    predicted_class = proba.argmax(axis=1)
    confidence = confident_prediction(proba)

    scored = without_label.copy()
    scored["_confidence"] = confidence
    scored["_predicted"] = predicted_class

    chosen_parts = []
    for label in np.unique(predicted_class):
        subset = scored[scored["_predicted"] == label].sort_values(
            "_confidence", ascending=False
        )
        cutting_index = int(len(subset) * (percentage * 0.01))
        chosen_parts.append(subset.iloc[:cutting_index])

    chosen = pd.concat(chosen_parts) if chosen_parts else scored.iloc[0:0]
    remaining = scored.drop(index=chosen.index)

    pseudo_label = chosen["_predicted"].astype(int)
    chosen = chosen.drop(columns=["_confidence", "_predicted"])
    remaining = remaining.drop(columns=["_confidence", "_predicted"])
    return chosen, pseudo_label, remaining


def pseudo_label_train(
    model: ClassifierMixin,
    X_labeled: pd.DataFrame,
    y_labeled: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    X_unlabeled: pd.DataFrame,
    percentage: float = 10,
    unlabeled_usage: float = 90,
) -> SemiSupervisedResult:
    """[코드50] train_and_evaluate()의 일반화 버전 (클래스별 확신도 선택 적용)."""
    model = clone(model)
    X_with_label = X_labeled.reset_index(drop=True).copy()
    y_with_label = y_labeled.reset_index(drop=True).copy()
    without_label = X_unlabeled.reset_index(drop=True).copy()

    num_left_unlabeled = int(len(X_unlabeled) * (100 - unlabeled_usage) * 0.01)
    history: list[dict] = []

    while len(without_label) >= num_left_unlabeled and len(without_label) > 0:
        model.fit(X_with_label, y_with_label)
        y_pred = model.predict(X_test)
        y_score = model.predict_proba(X_test)[:, 1]
        history.append(evaluation(y_test, y_pred, y_score))

        proba = model.predict_proba(without_label)
        chosen, pseudo_label, remaining = _select_pseudo_labels(
            without_label, proba, percentage
        )
        if chosen.empty:
            break

        X_with_label = pd.concat([X_with_label, chosen], ignore_index=True)
        y_with_label = pd.concat(
            [y_with_label, pseudo_label.reset_index(drop=True)], ignore_index=True
        )
        without_label = remaining.reset_index(drop=True)

    if not history:
        # num_left_unlabeled가 애초에 전체 unlabeled 개수보다 커서
        # 반복문이 한 번도 안 돈 경우를 대비한 최초 1회 학습/평가
        model.fit(X_with_label, y_with_label)
        y_pred = model.predict(X_test)
        y_score = model.predict_proba(X_test)[:, 1]
        history.append(evaluation(y_test, y_pred, y_score))

    return SemiSupervisedResult(model=model, history=history)
