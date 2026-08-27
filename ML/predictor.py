"""학습된 모델로 제조 데이터를 예측"""

from pathlib import Path

import joblib
import pandas as pd


class Predictor:
    """저장된 분류 모델을 불러와 새 데이터에 예측 결과를 붙여준다."""

    def __init__(self, model, feature_columns: list[str]):
        self.model = model
        self.feature_columns = feature_columns

    # ModelManager.save_model()로 저장한 파일을 그대로 불러온다
    @classmethod
    def load(cls, path: str | Path) -> "Predictor":
        payload = joblib.load(Path(path))
        return cls(payload["model"], payload["feature_columns"])

    def _select_features(self, df: pd.DataFrame) -> pd.DataFrame:
        missing = [column for column in self.feature_columns if column not in df.columns]
        if missing:
            raise KeyError(f"예측에 필요한 컬럼이 없습니다: {missing}")
        return df[self.feature_columns]

    # 0/1 예측값 (0=양품, 1=불량)
    def predict(self, df: pd.DataFrame):
        return self.model.predict(self._select_features(df))

    # 불량(1) 예측 확률
    def predict_proba(self, df: pd.DataFrame):
        return self.model.predict_proba(self._select_features(df))[:, 1]

    # 원본 DataFrame에 예측 라벨·불량 확률 컬럼을 추가해 반환
    def predict_with_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        result["predicted_target"] = self.predict(df)
        result["fail_probability"] = self.predict_proba(df)
        result["predicted_label"] = result["predicted_target"].map({0: "Y", 1: "N"})
        return result
