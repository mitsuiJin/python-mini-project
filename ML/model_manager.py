"""머신러닝 학습 모델(분류, 회귀 모델) 을 만들고 학습·평가·저장"""

from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight


# Windows 환경에서 그래프의 한글과 마이너스 기호가 깨지지 않도록 설정한다.
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


class ModelManager:
    """전처리된 DataFrame으로 분류 모델을 학습·평가·비교한다."""

    # 학습 피처로 쓰면 안 되는 식별자·원본 라벨 컬럼
    DEFAULT_EXCLUDE = {
        "target", "PassOrFail", "Reason", "_id", "TimeStamp",
        "PART_FACT_PLAN_DATE", "PART_FACT_SERIAL", "PART_NAME",
        "EQUIP_CD", "EQUIP_NAME", "product_family", "part_side",
    }

    # 각 후보 모델을 candidate로 넣은 이유. 리포트에 그대로 노출해 선택 근거를 남긴다
    CANDIDATE_REASONS = {
        "logistic_regression": (
            "해석이 쉬운 선형 baseline. 계수 부호로 어떤 공정변수가 "
            "불량에 영향을 주는지 바로 확인할 수 있음"
        ),
        "random_forest": (
            "정형(tabular) 센서 데이터에서 무난히 성능이 잘 나오고 "
            "스케일링이 불필요하며 피처 중요도를 함께 제공"
        ),
        "gradient_boosting": (
            "이전 트리의 오차를 순차적으로 보정하는 방식이라 "
            "소수 클래스(불량) 탐지에 강점을 보이는 경우가 많음"
        ),
    }

    def __init__(self, df: pd.DataFrame, target: str = "target", exclude_columns=None):
        if target not in df.columns:
            raise KeyError(f"타깃 컬럼이 없습니다: {target}")

        self.df = df.copy()
        self.target = target
        exclude = self.DEFAULT_EXCLUDE | set(exclude_columns or [])
        self.feature_columns = [
            column
            for column in self.df.select_dtypes(include="number").columns
            if column not in exclude
        ]
        if not self.feature_columns:
            raise ValueError("학습에 사용할 수치형 피처 컬럼이 없습니다.")

        self.X_train = self.X_test = self.y_train = self.y_test = None
        self.models: dict[str, object] = {}

    # 1. 학습/평가 데이터 분할. 불량 비율이 매우 낮아 stratify로 클래스 비율을 유지
    def split_data(self, test_size: float = 0.2, random_state: int = 42):
        X = self.df[self.feature_columns]
        y = self.df[self.target]
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=y
        )
        return self.X_train, self.X_test, self.y_train, self.y_test

    # 2. 후보 분류 모델 정의. 로지스틱 회귀는 피처 스케일 차이가 커서 스케일링을 함께 묶음
    def _build_candidates(self, random_state: int = 42) -> dict:
        return {
            "logistic_regression": Pipeline(
                [
                    ("scaler", StandardScaler()),
                    (
                        "model",
                        LogisticRegression(
                            max_iter=1000,
                            class_weight="balanced",
                            random_state=random_state,
                        ),
                    ),
                ]
            ),
            "random_forest": RandomForestClassifier(
                n_estimators=300,
                class_weight="balanced",
                random_state=random_state,
            ),
            "gradient_boosting": GradientBoostingClassifier(random_state=random_state),
        }

    # 3. 모델 한 개를 학습. gradient_boosting은 class_weight를 지원하지 않아 sample_weight로 보정
    def train(self, name: str, random_state: int = 42):
        if self.X_train is None:
            self.split_data(random_state=random_state)
        candidates = self._build_candidates(random_state)
        if name not in candidates:
            raise KeyError(f"지원하지 않는 모델입니다: {name}")

        model = candidates[name]
        if name == "gradient_boosting":
            sample_weight = compute_sample_weight("balanced", self.y_train)
            model.fit(self.X_train, self.y_train, sample_weight=sample_weight)
        else:
            model.fit(self.X_train, self.y_train)

        self.models[name] = model
        return model

    # 4. 후보 모델을 모두 학습
    def train_all(self, random_state: int = 42) -> dict:
        if self.X_train is None:
            self.split_data(random_state=random_state)
        for name in self._build_candidates(random_state):
            self.train(name, random_state=random_state)
        return self.models

    # 5. 모델 한 개를 평가. 불량 비율이 낮아 accuracy보다 recall·f1·PR-AUC를 우선 확인
    def evaluate(self, name: str) -> dict:
        if name not in self.models:
            raise KeyError(f"학습되지 않은 모델입니다: {name}")

        model = self.models[name]
        prediction = model.predict(self.X_test)
        probability = model.predict_proba(self.X_test)[:, 1]

        return {
            "precision": precision_score(self.y_test, prediction, zero_division=0),
            "recall": recall_score(self.y_test, prediction, zero_division=0),
            "f1": f1_score(self.y_test, prediction, zero_division=0),
            "roc_auc": roc_auc_score(self.y_test, probability),
            "pr_auc": average_precision_score(self.y_test, probability),
            "confusion_matrix": confusion_matrix(self.y_test, prediction),
            "report": classification_report(self.y_test, prediction, zero_division=0),
        }

    # 6. 학습된 모델 전체의 성능을 f1 기준으로 정렬한 표로 비교
    def evaluate_all(self) -> pd.DataFrame:
        if not self.models:
            raise RuntimeError("먼저 모델을 학습하세요.")

        rows = {
            name: {
                key: value
                for key, value in self.evaluate(name).items()
                if key in {"precision", "recall", "f1", "roc_auc", "pr_auc"}
            }
            for name in self.models
        }
        return pd.DataFrame(rows).T.sort_values("f1", ascending=False)

    # 7. f1 기준 최고 성능 모델 이름
    def best_model_name(self) -> str:
        return self.evaluate_all().index[0]

    # 최고 모델을 f1로 고른 이유를 문장으로 반환 (리포트용)
    def selection_reason(self) -> str:
        best_name = self.best_model_name()
        return (
            f"불량 비율이 매우 낮아 accuracy는 의미가 없고, 정밀도와 재현율의 "
            f"균형을 함께 보는 f1-score가 가장 높은 모델을 자동 선택 → {best_name}"
        )

    # 8. 랜덤포레스트·그래디언트부스팅의 피처 중요도
    def get_feature_importance(self, name: str) -> pd.Series:
        if name not in self.models:
            raise KeyError(f"학습되지 않은 모델입니다: {name}")

        model = self.models[name]
        if not hasattr(model, "feature_importances_"):
            raise TypeError(f"{name} 모델은 feature_importances_를 지원하지 않습니다.")

        return pd.Series(
            model.feature_importances_, index=self.feature_columns
        ).sort_values(ascending=False)

    # 9. 학습된 모델과 피처 목록을 함께 저장. Predictor가 그대로 불러와 사용
    def save_model(self, name: str, path: str | Path) -> Path:
        if name not in self.models:
            raise KeyError(f"학습되지 않은 모델입니다: {name}")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {"model": self.models[name], "feature_columns": self.feature_columns},
            path,
        )
        return path

    # 10. 학습된 모델들의 precision·recall·f1·roc_auc·pr_auc를 막대그래프로 비교
    def plot_model_comparison(self) -> Figure:
        comparison = self.evaluate_all()
        figure, axis = plt.subplots(figsize=(8, 5))
        comparison.plot(kind="bar", ax=axis)
        axis.set_title("모델별 성능 비교")
        axis.set_ylabel("점수")
        axis.set_ylim(0, 1)
        axis.tick_params(axis="x", rotation=0)
        axis.legend(loc="lower right", fontsize=8)
        figure.tight_layout()
        return figure

    # 11. 학습된 모델별 혼동행렬을 나란히 표시
    def plot_confusion_matrices(self) -> Figure:
        if not self.models:
            raise RuntimeError("먼저 모델을 학습하세요.")

        figure, axes = plt.subplots(1, len(self.models), figsize=(4.5 * len(self.models), 4))
        if len(self.models) == 1:
            axes = [axes]

        for axis, name in zip(axes, self.models):
            matrix = self.evaluate(name)["confusion_matrix"]
            axis.imshow(matrix, cmap="Blues")
            for row in range(matrix.shape[0]):
                for column in range(matrix.shape[1]):
                    axis.text(column, row, str(matrix[row, column]), ha="center", va="center")
            axis.set_title(name, fontsize=10)
            axis.set_xlabel("예측")
            axis.set_ylabel("실제")
            axis.set_xticks([0, 1], ["양품", "불량"])
            axis.set_yticks([0, 1], ["양품", "불량"])
        figure.tight_layout()
        return figure

    # 12. 학습된 모델별 ROC 커브를 한 그래프에 겹쳐 표시
    def plot_roc_curves(self) -> Figure:
        if not self.models:
            raise RuntimeError("먼저 모델을 학습하세요.")

        figure, axis = plt.subplots(figsize=(6, 6))
        for name, model in self.models.items():
            probability = model.predict_proba(self.X_test)[:, 1]
            fpr, tpr, _ = roc_curve(self.y_test, probability)
            auc = roc_auc_score(self.y_test, probability)
            axis.plot(fpr, tpr, label=f"{name} (AUC={auc:.3f})")
        axis.plot([0, 1], [0, 1], linestyle="--", color="gray", label="무작위 기준선")
        axis.set_title("ROC 커브")
        axis.set_xlabel("False Positive Rate")
        axis.set_ylabel("True Positive Rate")
        axis.legend(loc="lower right", fontsize=8)
        figure.tight_layout()
        return figure

    # 13. 트리 기반 모델의 피처 중요도 상위 top_n개를 막대그래프로 표시
    def plot_feature_importance(self, name: str, top_n: int = 15) -> Figure:
        importance = self.get_feature_importance(name).head(top_n)
        figure, axis = plt.subplots(figsize=(7, max(4, top_n * 0.3)))
        importance.sort_values().plot(kind="barh", ax=axis, color="#14b8a6")
        axis.set_title(f"{name} 피처 중요도 (상위 {top_n}개)")
        axis.set_xlabel("중요도")
        figure.tight_layout()
        return figure
