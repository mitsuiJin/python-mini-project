"""준지도학습 — 라벨 없는 공정 데이터에 의사라벨(pseudo-label)을 붙여 학습셋을 넓힌다.

self-training 방식: 현재 라벨 데이터로 임시 분류기를 학습 → 라벨 없는 풀에서
확신도가 높은 행만 골라 그 예측을 라벨처럼 붙여 학습셋에 편입 → 반복.

불량이 60건뿐이라 결정경계를 잡을 표본이 부족한 상황을 라벨 없는 데이터로 보강하는 것이
목적이다. (라벨 없는 데이터가 대부분 양품이면 양품 경계가 촘촘해지는 효과가 크다.)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.base import clone


@dataclass
class ExpansionResult:
    X: pd.DataFrame
    y: pd.Series
    is_pseudo: np.ndarray | None = None  # X 각 행이 의사라벨인지 여부
    added_total: int = 0
    added_pass: int = 0
    added_fail: int = 0
    iterations: int = 0
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.added_total == 0:
            reason = self.notes[0] if self.notes else "확신도 기준을 넘는 행이 없었음"
            return f"준지도 확장: 추가 0건 ({reason})"
        return (
            f"준지도 self-training: {self.iterations}회 반복, "
            f"의사라벨 {self.added_total:,}건 편입 "
            f"(양품 {self.added_pass:,} / 불량 {self.added_fail:,})"
        )


class SelfTrainingExpander:
    """확신도 임계값 기반 self-training 으로 학습셋을 확장한다."""

    def __init__(
        self,
        base_estimator,
        confidence: float = 0.97,
        max_iter: int = 2,
        max_add_per_iter: int = 2000,
        max_add_ratio: float = 2.0,
        sample_unlabeled: int = 9000,
        accept_classes: tuple[int, ...] = (0,),
        random_state: int = 42,
    ):
        self.base_estimator = base_estimator
        self.confidence = confidence
        self.max_iter = max_iter
        self.max_add_per_iter = max_add_per_iter
        # 의사라벨 총량 상한 = 원본 라벨 수 × 이 비율 (양품 홍수로 보정을 망치지 않게)
        self.max_add_ratio = max_add_ratio
        self.sample_unlabeled = sample_unlabeled
        # 편입을 허용할 의사라벨 클래스. 기본은 양품(0)만 —
        # 분포 밖(다른 부품) 데이터를 불량으로 오탐한 라벨이 섞이지 않게 한다
        self.accept_classes = set(accept_classes)
        self.random_state = random_state

    def expand(
        self,
        X_labeled: pd.DataFrame,
        y_labeled: pd.Series,
        X_unlabeled: pd.DataFrame,
    ) -> ExpansionResult:
        feature_columns = list(X_labeled.columns)
        missing = [c for c in feature_columns if c not in X_unlabeled.columns]
        if missing:
            return ExpansionResult(
                X_labeled.copy(),
                y_labeled.copy(),
                notes=[f"라벨없는 데이터에 피처 {missing} 없음 → 건너뜀"],
            )

        pool = X_unlabeled[feature_columns].dropna()
        if len(pool) > self.sample_unlabeled:
            pool = pool.sample(self.sample_unlabeled, random_state=self.random_state)
        if pool.empty:
            return ExpansionResult(
                X_labeled.copy(), y_labeled.copy(), notes=["라벨없는 표본이 비어 있음"]
            )

        X_current = X_labeled.copy()
        y_current = y_labeled.copy()
        result = ExpansionResult(X_current, y_current)
        add_budget = int(len(X_labeled) * self.max_add_ratio)

        for iteration in range(1, self.max_iter + 1):
            if pool.empty or result.added_total >= add_budget:
                break
            model = clone(self.base_estimator)
            model.fit(X_current, y_current)
            proba = model.predict_proba(pool[feature_columns])
            classes = model.classes_
            confidence = proba.max(axis=1)
            predicted = classes[proba.argmax(axis=1)]

            accepted_class = np.isin(predicted, list(self.accept_classes))
            confident = (confidence >= self.confidence) & accepted_class
            if not confident.any():
                result.notes.append(
                    f"{iteration}회차: 확신도 {self.confidence:.2f}·허용클래스 조건을 "
                    "만족하는 행 없음"
                )
                break

            per_iter_cap = min(
                self.max_add_per_iter, add_budget - result.added_total
            )
            chosen_index = pool.index[confident]
            if len(chosen_index) > per_iter_cap:
                order = np.argsort(confidence[confident])[::-1][:per_iter_cap]
                chosen_index = chosen_index[order]

            chosen_mask = pool.index.isin(chosen_index)
            pseudo_labels = pd.Series(
                predicted[chosen_mask], index=pool.index[chosen_mask]
            )

            X_current = pd.concat([X_current, pool.loc[chosen_index, feature_columns]])
            y_current = pd.concat([y_current, pseudo_labels.loc[chosen_index]])
            pool = pool.drop(index=chosen_index)

            added = int(len(chosen_index))
            result.added_total += added
            result.added_fail += int((pseudo_labels.loc[chosen_index] == 1).sum())
            result.added_pass += added - int(
                (pseudo_labels.loc[chosen_index] == 1).sum()
            )
            result.iterations = iteration

        result.X = X_current
        result.y = y_current.astype(int)
        pseudo = np.zeros(len(X_current), dtype=bool)
        if result.added_total:
            pseudo[len(X_labeled):] = True
        result.is_pseudo = pseudo
        return result
