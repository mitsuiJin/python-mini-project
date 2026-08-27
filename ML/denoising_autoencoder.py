"""잡음제거 오토인코더(DAE) — 양품 신호만 학습해 복원오차로 이상(불량 후보)을 가려낸다.

가이드북(KAMP)이 지시하는 비지도 이상탐지 방식이다. TensorFlow 없이 scikit-learn의
MLPRegressor 로 구현했고, 학습 입력에만 가우시안 잡음 + 입력 드롭아웃을 섞어
"잡음을 지운 원본"을 복원하도록 만든다(그래서 denoising).

주요 산출물
- reconstruction_error(X): 행별 복원 MSE (클수록 정상 패턴에서 벗어남)
- threshold_: 양품 복원오차의 평균 + sigma·표준편차 (3시그마 임계값)
- anomaly_flags(X): 임계값 초과 여부 (True = 불량 후보)
- latent(X): 병목층 잠재표현 — 분류기에 추가 피처로 넣을 수 있다
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler


class DenoisingAutoencoder:
    """양품 데이터로만 학습하는 잡음제거 오토인코더."""

    def __init__(
        self,
        hidden_layers: tuple[int, ...] = (32, 8, 32),
        noise_std: float = 0.15,
        input_dropout: float = 0.3,
        sigma: float = 3.0,
        max_iter: int = 300,
        random_state: int = 42,
    ):
        self.hidden_layers = tuple(hidden_layers)
        self.noise_std = noise_std
        self.input_dropout = input_dropout
        self.sigma = sigma
        self.max_iter = max_iter
        self.random_state = random_state

        self.scaler_: StandardScaler | None = None
        self.net_: MLPRegressor | None = None
        self.threshold_: float | None = None
        self.bottleneck_index_: int | None = None
        self.normal_error_mean_: float | None = None
        self.normal_error_std_: float | None = None

    # 병목(가장 작은 은닉층) 위치. latent() 계산에 사용
    def _find_bottleneck(self) -> int:
        return int(np.argmin(self.hidden_layers))

    def _corrupt(self, X: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        noisy = X + rng.normal(0.0, self.noise_std, size=X.shape)
        if self.input_dropout > 0:
            keep = rng.random(X.shape) >= self.input_dropout
            noisy = noisy * keep
        return noisy

    # 양품 행렬만 넣어 학습한다
    def fit(self, X_normal: pd.DataFrame | np.ndarray) -> "DenoisingAutoencoder":
        X = np.asarray(X_normal, dtype=float)
        rng = np.random.default_rng(self.random_state)

        self.scaler_ = StandardScaler().fit(X)
        X_scaled = self.scaler_.transform(X)
        X_noisy = self._corrupt(X_scaled, rng)

        self.net_ = MLPRegressor(
            hidden_layer_sizes=self.hidden_layers,
            activation="relu",
            solver="adam",
            alpha=1e-4,
            batch_size=min(128, len(X_scaled)),
            learning_rate_init=1e-3,
            max_iter=self.max_iter,
            early_stopping=False,
            random_state=self.random_state,
        )
        self.net_.fit(X_noisy, X_scaled)
        self.bottleneck_index_ = self._find_bottleneck()

        errors = self._errors(X_scaled)
        self.normal_error_mean_ = float(errors.mean())
        self.normal_error_std_ = float(errors.std())
        self.threshold_ = self.normal_error_mean_ + self.sigma * self.normal_error_std_
        return self

    def _errors(self, X_scaled: np.ndarray) -> np.ndarray:
        reconstructed = self.net_.predict(X_scaled)
        if reconstructed.ndim == 1:
            reconstructed = reconstructed.reshape(-1, 1)
        return np.mean((X_scaled - reconstructed) ** 2, axis=1)

    def _check_fitted(self) -> None:
        if self.net_ is None or self.scaler_ is None:
            raise RuntimeError("먼저 fit() 으로 DAE를 학습하세요.")

    # 행별 복원 오차
    def reconstruction_error(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        self._check_fitted()
        X_scaled = self.scaler_.transform(np.asarray(X, dtype=float))
        return self._errors(X_scaled)

    # 복원 오차를 양품 분포 기준 z-점수로 (피처로 쓰기 좋게)
    def error_zscore(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        error = self.reconstruction_error(X)
        std = self.normal_error_std_ or 1.0
        return (error - (self.normal_error_mean_ or 0.0)) / (std if std else 1.0)

    # 3시그마(=sigma) 임계값 초과 여부
    def anomaly_flags(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        return self.reconstruction_error(X) > float(self.threshold_)

    # 병목층 잠재표현 — 은닉 활성값을 coefs_ 로 직접 순전파해서 구한다
    def latent(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        self._check_fitted()
        activation = self.scaler_.transform(np.asarray(X, dtype=float))
        for layer_index in range(self.bottleneck_index_ + 1):
            activation = activation @ self.net_.coefs_[layer_index]
            activation += self.net_.intercepts_[layer_index]
            activation = np.maximum(activation, 0.0)  # relu
        return activation
