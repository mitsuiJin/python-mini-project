"""향상 기법을 하나로 묶은 분류기 래퍼.

기존 후보 모델(random_forest / gradient_boosting / logistic_regression)을 감싸서
아래 기법을 순서대로 적용한다. scikit-learn 추정기 인터페이스(fit/predict/predict_proba)
를 그대로 노출하므로 ModelManager·Predictor 는 수정 없이 재사용된다.

적용 파이프라인
 1) 가동시점 파생피처   : TimeStamp 로 shot_in_run·gap_sec·run_elapsed_sec 등 생성
                          (불량이 설비 가동 초기에 몰려 있음 → 강한 신호)
 2) 준지도 self-training : 라벨 없는 공정 데이터에 의사라벨을 붙여 학습셋 확장
 3) 잡음제거 오토인코더  : 양품만 학습 → 복원오차 z-점수·잠재표현을 피처로 추가
 4) 소수클래스 오버샘플링: SMOTE 방식으로 불량 표본을 보간 생성
 5) 결정임계값 튜닝      : 교차검증 확률로 F1 최대 임계값 탐색 (기본 0.5 대신)
 6) DAE 3σ 하이브리드    : 분류기가 놓쳐도 복원오차가 임계값을 넘으면 불량으로 판정
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import f1_score
from sklearn.pipeline import Pipeline

from ML.denoising_autoencoder import DenoisingAutoencoder
from ML.semi_supervised import SelfTrainingExpander

RUN_GAP_SECONDS = 600  # 이 시간 이상 벌어지면 새 가동(run) 시작으로 본다


def add_run_features(df: pd.DataFrame, timestamp_column: str = "TimeStamp") -> pd.DataFrame:
    """TimeStamp 로 가동 구간 파생피처를 만들어 붙인다. TimeStamp 가 없으면 원본 그대로."""
    if timestamp_column not in df.columns:
        return df.copy()

    result = df.copy()
    stamp = pd.to_datetime(result[timestamp_column], errors="coerce")
    order = stamp.sort_values(kind="stable").index
    stamp_sorted = stamp.loc[order]

    gap = stamp_sorted.diff().dt.total_seconds()
    is_start = gap.isna() | (gap > RUN_GAP_SECONDS)
    run_id = is_start.cumsum()
    shot_in_run = stamp_sorted.groupby(run_id).cumcount()
    run_start_time = stamp_sorted.groupby(run_id).transform("min")
    run_elapsed = (stamp_sorted - run_start_time).dt.total_seconds()

    features = pd.DataFrame(index=stamp_sorted.index)
    features["gap_sec"] = gap.fillna(0.0).clip(upper=6 * RUN_GAP_SECONDS)
    features["is_run_start"] = is_start.astype(int)
    features["shot_in_run"] = shot_in_run.astype(float)
    features["log_shot_in_run"] = np.log1p(shot_in_run.astype(float))
    features["run_elapsed_sec"] = run_elapsed.fillna(0.0)

    features = features.reindex(df.index)
    for column in features.columns:
        result[column] = features[column]
    return result


RUN_FEATURE_COLUMNS = [
    "gap_sec",
    "is_run_start",
    "shot_in_run",
    "log_shot_in_run",
    "run_elapsed_sec",
]


def smote_oversample(
    X: np.ndarray,
    y: np.ndarray,
    minority_ratio: float = 0.35,
    k_neighbors: int = 5,
    random_state: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """소수 클래스(1)를 SMOTE 보간으로 늘린다. 외부 라이브러리 없이 numpy 로 구현."""
    rng = np.random.default_rng(random_state)
    minority = X[y == 1]
    majority_count = int((y == 0).sum())
    target_count = int(majority_count * minority_ratio)
    need = target_count - len(minority)
    if need <= 0 or len(minority) < 2:
        return X, y

    k = min(k_neighbors, len(minority) - 1)
    # 소수 표본 간 유클리드 거리로 최근접 이웃 인덱스
    diff = minority[:, None, :] - minority[None, :, :]
    distance = np.sqrt((diff**2).sum(axis=2))
    np.fill_diagonal(distance, np.inf)
    neighbor_index = np.argsort(distance, axis=1)[:, :k]

    base_rows = rng.integers(0, len(minority), size=need)
    neighbor_pick = rng.integers(0, k, size=need)
    gap = rng.random(size=(need, 1))
    starts = minority[base_rows]
    ends = minority[neighbor_index[base_rows, neighbor_pick]]
    synthetic = starts + gap * (ends - starts)

    X_out = np.vstack([X, synthetic])
    y_out = np.concatenate([y, np.ones(need, dtype=int)])
    return X_out, y_out


@dataclass
class EnhancementInfo:
    steps: list[str] = field(default_factory=list)
    semi_supervised: str = ""
    dae_threshold: float = 0.0
    dae_latent_dim: int = 0
    dae_active: bool = False
    hybrid_active: bool = False
    decision_threshold: float = 0.5
    threshold_tuned: bool = False
    train_rows_before: int = 0
    train_rows_after_semi: int = 0
    train_rows_after_smote: int = 0

    def as_lines(self) -> list[str]:
        rows_line = (
            f"  학습행: 원본 {self.train_rows_before:,} → 준지도 확장 "
            f"{self.train_rows_after_semi:,}"
        )
        if self.train_rows_after_smote != self.train_rows_after_semi:
            rows_line += f" → 오버샘플 {self.train_rows_after_smote:,}"
        if self.dae_active:
            dae_line = (
                f"  DAE 복원오차 3σ 임계값 {self.dae_threshold:.5f}"
                f"{f', 잠재피처 {self.dae_latent_dim}개' if self.dae_latent_dim else ''}"
                f"{' · 3σ 하이브리드 판정 ON' if self.hybrid_active else ''}"
            )
        else:
            dae_line = "  DAE: 비활성"
        threshold_line = (
            f"  결정임계값 {self.decision_threshold:.3f}"
            + (" (교차검증 F1 기준 튜닝)" if self.threshold_tuned else " (기본값)")
        )
        return [
            f"  적용 단계: {', '.join(self.steps)}",
            rows_line,
            f"  {self.semi_supervised}",
            dae_line,
            threshold_line,
        ]


class EnhancedClassifier(BaseEstimator, ClassifierMixin):
    """DAE + 준지도 + 오버샘플링 + 임계값 튜닝 + 하이브리드를 적용한 분류기."""

    def __init__(
        self,
        base_estimator,
        *,
        use_run_features: bool = False,
        use_semi_supervised: bool = True,
        use_dae_features: bool = True,
        dae_use_latent: bool = False,
        use_oversample: bool = False,
        tune_threshold: bool = True,
        hybrid_dae: bool = False,
        dae_sigma: float = 3.0,
        pseudo_weight: float = 0.3,
        unlabeled_df: pd.DataFrame | None = None,
        random_state: int = 42,
    ):
        self.base_estimator = base_estimator
        self.use_run_features = use_run_features
        self.use_semi_supervised = use_semi_supervised
        self.use_dae_features = use_dae_features
        self.dae_use_latent = dae_use_latent
        self.use_oversample = use_oversample
        self.tune_threshold = tune_threshold
        self.hybrid_dae = hybrid_dae
        self.dae_sigma = dae_sigma
        self.pseudo_weight = pseudo_weight
        self.unlabeled_df = unlabeled_df
        self.random_state = random_state

    # --- 내부 유틸 -----------------------------------------------------------
    @staticmethod
    def _fit_base(model, X, y, sample_weight):
        """Pipeline 이면 마지막 스텝으로, 아니면 직접 sample_weight 를 전달한다."""
        if isinstance(model, Pipeline):
            step_name = model.steps[-1][0]
            model.fit(X, y, **{f"{step_name}__sample_weight": sample_weight})
        else:
            model.fit(X, y, sample_weight=sample_weight)
        return model
    def _numeric_frame(self, X: pd.DataFrame) -> pd.DataFrame:
        """가동피처를 붙인 뒤 학습에 쓸 수치 컬럼만 정렬해 돌려준다."""
        frame = X.copy()
        if self.use_run_features:
            frame = add_run_features(frame)
        return frame[self.feature_names_after_run_]

    def _augment_with_dae(self, numeric: pd.DataFrame) -> np.ndarray:
        matrix = numeric.to_numpy(dtype=float)
        if not self.use_dae_features or self.dae_ is None:
            return matrix
        error_z = self.dae_.error_zscore(numeric).reshape(-1, 1)
        flag = self.dae_.anomaly_flags(numeric).astype(float).reshape(-1, 1)
        parts = [matrix, error_z, flag]
        if self.dae_use_latent:
            parts.append(self.dae_.latent(numeric))
        return np.hstack(parts)

    # --- 학습 --------------------------------------------------------------
    def fit(self, X: pd.DataFrame, y) -> "EnhancedClassifier":
        if not isinstance(X, pd.DataFrame):
            raise TypeError("EnhancedClassifier 는 DataFrame 입력이 필요합니다.")
        y = pd.Series(np.asarray(y).astype(int), index=X.index)
        info = EnhancementInfo(train_rows_before=len(X))
        steps: list[str] = []
        sample_weight = None

        # 1) 가동시점 파생피처
        working = add_run_features(X) if self.use_run_features else X.copy()
        run_columns = [c for c in RUN_FEATURE_COLUMNS if c in working.columns]
        self.sensor_columns_ = [
            c
            for c in X.columns
            if c != "TimeStamp" and pd.api.types.is_numeric_dtype(X[c])
        ]
        self.feature_names_after_run_ = self.sensor_columns_ + run_columns
        if run_columns:
            steps.append("가동시점 파생피처")
        numeric = working[self.feature_names_after_run_]

        # 2) 잡음제거 오토인코더 — 원본 양품 행만 학습 (의사라벨 편입 전에 학습해
        #    양품 분포가 오염되지 않게 한다)
        self.dae_ = None
        if self.use_dae_features:
            normal_rows = numeric[y.to_numpy() == 0]
            self.dae_ = DenoisingAutoencoder(
                sigma=self.dae_sigma, random_state=self.random_state
            ).fit(normal_rows)
            info.dae_threshold = float(self.dae_.threshold_)
            info.dae_active = True
            info.hybrid_active = self.hybrid_dae
            info.dae_latent_dim = (
                int(self.dae_.latent(normal_rows.iloc[:1]).shape[1])
                if self.dae_use_latent
                else 0
            )
            label = "DAE 복원오차"
            if self.dae_use_latent:
                label += "·잠재피처"
            if self.hybrid_dae:
                label += "·3σ 하이브리드"
            steps.append(label)

        # 3) 결정임계값 튜닝 — 반드시 원본 라벨 데이터로만 교차검증한다.
        #    (의사라벨은 대부분 양품이라 편입 후 튜닝하면 임계값이 왜곡됨)
        self.decision_threshold_ = 0.5
        original_matrix = self._augment_with_dae(numeric)
        if self.tune_threshold and int((y.to_numpy() == 1).sum()) >= 3:
            self.decision_threshold_ = self._search_threshold(
                original_matrix, y.to_numpy()
            )
            info.threshold_tuned = True
            steps.append("결정임계값 튜닝(원본 라벨 CV)")
        info.decision_threshold = self.decision_threshold_

        # 4) 준지도 self-training — 최종 적합용 학습셋만 확장
        if self.use_semi_supervised and self.unlabeled_df is not None:
            unlabeled = (
                add_run_features(self.unlabeled_df)
                if self.use_run_features
                else self.unlabeled_df
            )
            expander = SelfTrainingExpander(
                clone(self.base_estimator), random_state=self.random_state
            )
            expansion = expander.expand(numeric, y, unlabeled)
            numeric, y = expansion.X, expansion.y
            info.semi_supervised = expansion.summary()
            if expansion.added_total > 0:
                # 의사라벨은 낮은 가중치로 반영해 확률 보정이 깨지지 않게 한다
                sample_weight = np.where(expansion.is_pseudo, self.pseudo_weight, 1.0)
                steps.append(f"준지도 self-training(의사라벨 가중치 {self.pseudo_weight})")
        else:
            info.semi_supervised = "준지도 확장: 비활성(라벨없는 데이터 미제공)"
        info.train_rows_after_semi = len(numeric)

        X_matrix = self._augment_with_dae(numeric)
        y_array = y.to_numpy()
        weight_array = (
            sample_weight if sample_weight is not None else np.ones(len(y_array))
        )

        # 5) 소수클래스 오버샘플링
        if self.use_oversample and (y_array == 1).sum() >= 2:
            before = len(X_matrix)
            X_matrix, y_array = smote_oversample(
                X_matrix, y_array, random_state=self.random_state
            )
            weight_array = np.concatenate(
                [weight_array, np.ones(len(X_matrix) - before)]
            )
            steps.append("SMOTE 오버샘플링")
        info.train_rows_after_smote = len(X_matrix)

        # 6) 최종 분류기 학습
        self.model_ = clone(self.base_estimator)
        self._fit_base(self.model_, X_matrix, y_array, weight_array)
        self.classes_ = np.array([0, 1])

        info.steps = steps or ["없음"]
        self.enhancement_info_ = info
        return self

    def _search_threshold(self, X_matrix: np.ndarray, y_array: np.ndarray) -> float:
        splits = min(5, int((y_array == 1).sum()))
        cv = StratifiedKFold(
            n_splits=max(2, splits), shuffle=True, random_state=self.random_state
        )
        proba = cross_val_predict(
            clone(self.base_estimator),
            X_matrix,
            y_array,
            cv=cv,
            method="predict_proba",
        )[:, 1]
        best_threshold, best_f1 = 0.5, -1.0
        # 극단값에서 과적합되지 않도록 탐색 구간을 제한한다
        for threshold in np.linspace(0.15, 0.7, 56):
            score = f1_score(y_array, (proba >= threshold).astype(int), zero_division=0)
            if score > best_f1 + 1e-9:
                best_threshold, best_f1 = float(threshold), score
        return best_threshold

    # --- 예측 -------------------------------------------------------------
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        numeric = self._numeric_frame(X)
        matrix = self._augment_with_dae(numeric)
        return self.model_.predict_proba(matrix)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        numeric = self._numeric_frame(X)
        matrix = self._augment_with_dae(numeric)
        proba = self.model_.predict_proba(matrix)[:, 1]
        prediction = (proba >= self.decision_threshold_).astype(int)
        if self.hybrid_dae and self.dae_ is not None:
            prediction = np.where(
                self.dae_.anomaly_flags(numeric), 1, prediction
            ).astype(int)
        return prediction
