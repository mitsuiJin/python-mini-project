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

from ML.enhanced_classifier import EnhancedClassifier


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

    # 향상 기법 요약(리포트용)
    ENHANCEMENT_OVERVIEW = (
        "잡음제거 오토인코더(DAE) → 3σ 임계값 → 준지도 self-training 을 축으로, "
        "가동시점 파생피처와 교차검증 기반 결정임계값 튜닝을 3개 후보 모델에 동일하게 적용. "
        "(SMOTE 오버샘플링·DAE 3σ 하이브리드 판정은 EnhancedClassifier 옵션으로 추가 가능)"
    )

    def __init__(
        self,
        df: pd.DataFrame,
        target: str = "target",
        exclude_columns=None,
        unlabeled_df: pd.DataFrame | None = None,
    ):
        if target not in df.columns:
            raise KeyError(f"타깃 컬럼이 없습니다: {target}")

        self.df = df.copy()
        self.target = target
        self.unlabeled_df = unlabeled_df
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
        self.enhanced_models: dict[str, EnhancedClassifier] = {}

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

    # 4-1. TimeStamp 를 포함한 향상용 학습/평가 프레임 (원본 인덱스로 되살린다)
    def _enhanced_frame(self, base_X: pd.DataFrame) -> pd.DataFrame:
        columns = list(self.feature_columns)
        if "TimeStamp" in self.df.columns:
            columns = columns + ["TimeStamp"]
        return self.df.loc[base_X.index, columns].copy()

    # 4-2. 향상 기법을 적용한 모델 한 개 학습
    def train_enhanced(self, name: str, random_state: int = 42) -> EnhancedClassifier:
        if self.X_train is None:
            self.split_data(random_state=random_state)
        candidates = self._build_candidates(random_state)
        if name not in candidates:
            raise KeyError(f"지원하지 않는 모델입니다: {name}")

        enhanced = EnhancedClassifier(
            candidates[name],
            unlabeled_df=self.unlabeled_df,
            random_state=random_state,
        )
        enhanced.fit(self._enhanced_frame(self.X_train), self.y_train)
        self.enhanced_models[name] = enhanced
        return enhanced

    # 4-3. 향상 모델 모두 학습
    def train_all_enhanced(self, random_state: int = 42) -> dict:
        if self.X_train is None:
            self.split_data(random_state=random_state)
        for name in self._build_candidates(random_state):
            self.train_enhanced(name, random_state=random_state)
        return self.enhanced_models

    # 5. 모델 한 개를 평가. 불량 비율이 낮아 accuracy보다 recall·f1·PR-AUC를 우선 확인
    def evaluate(self, name: str, enhanced: bool = False) -> dict:
        source = self.enhanced_models if enhanced else self.models
        if name not in source:
            raise KeyError(f"학습되지 않은 모델입니다: {name}")

        model = source[name]
        X_test = self._enhanced_frame(self.X_test) if enhanced else self.X_test
        prediction = model.predict(X_test)
        probability = model.predict_proba(X_test)[:, 1]

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
    def evaluate_all(self, enhanced: bool = False) -> pd.DataFrame:
        source = self.enhanced_models if enhanced else self.models
        if not source:
            raise RuntimeError("먼저 모델을 학습하세요.")

        rows = {
            name: {
                key: value
                for key, value in self.evaluate(name, enhanced=enhanced).items()
                if key in {"precision", "recall", "f1", "roc_auc", "pr_auc"}
            }
            for name in source
        }
        return pd.DataFrame(rows).T.sort_values("f1", ascending=False)

    # 6-1. 3개 모델의 기본 vs 향상 성능을 나란히 놓은 비교표
    def compare_baseline_vs_enhanced(self) -> pd.DataFrame:
        if not self.models or not self.enhanced_models:
            raise RuntimeError("기본 모델과 향상 모델을 모두 학습하세요.")

        metrics = ["precision", "recall", "f1", "roc_auc", "pr_auc"]
        records = []
        for name in self.models:
            base = self.evaluate(name)
            enh = self.evaluate(name, enhanced=True)
            row = {"model": name}
            for metric in metrics:
                row[f"{metric}_기본"] = base[metric]
                row[f"{metric}_향상"] = enh[metric]
                row[f"{metric}_Δ"] = enh[metric] - base[metric]
            records.append(row)
        return pd.DataFrame(records).set_index("model")

    # 6-2. 향상 기법 적용 내역을 사람이 읽을 수 있는 문자열로
    def enhancement_report(self) -> str:
        if not self.enhanced_models:
            raise RuntimeError("먼저 향상 모델을 학습하세요.")
        lines = [f"[향상 기법 개요] {self.ENHANCEMENT_OVERVIEW}", ""]
        comparison = self.compare_baseline_vs_enhanced()
        display = comparison[
            ["precision_기본", "precision_향상", "recall_기본", "recall_향상",
             "f1_기본", "f1_향상", "pr_auc_기본", "pr_auc_향상"]
        ]
        lines.append("[3개 모델 성능 — 기본 vs 향상]")
        lines.append(display.to_string(float_format=lambda value: f"{value:.4f}"))
        lines.append("")
        for name, model in self.enhanced_models.items():
            base = self.evaluate(name)
            enh = self.evaluate(name, enhanced=True)
            lines.append(
                f"[{name}] f1 {base['f1']:.3f} → {enh['f1']:.3f} "
                f"(recall {base['recall']:.3f} → {enh['recall']:.3f}, "
                f"precision {base['precision']:.3f} → {enh['precision']:.3f})"
            )
            lines.extend(model.enhancement_info_.as_lines())
            lines.append(
                "  혼동행렬 기본→향상 (행=실제, 열=예측): "
                f"{base['confusion_matrix'].tolist()} → {enh['confusion_matrix'].tolist()}"
            )
            lines.append("")
        return "\n".join(lines)

    # 7. f1 기준 최고 성능 모델 이름
    def best_model_name(self, enhanced: bool = False) -> str:
        return self.evaluate_all(enhanced=enhanced).index[0]

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
    def save_model(self, name: str, path: str | Path, enhanced: bool = False) -> Path:
        source = self.enhanced_models if enhanced else self.models
        if name not in source:
            raise KeyError(f"학습되지 않은 모델입니다: {name}")

        # 향상 모델은 내부에서 가동피처를 만들므로 TimeStamp 도 예측 입력에 포함한다
        feature_columns = list(self.feature_columns)
        if enhanced and "TimeStamp" in self.df.columns:
            feature_columns = feature_columns + ["TimeStamp"]

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {"model": source[name], "feature_columns": feature_columns},
            path,
        )
        return path

    # 9-1. 향상 모델을 Predictor 호환 객체로 바로 반환
    def build_enhanced_predictor(self, name: str):
        from ML.predictor import Predictor

        if name not in self.enhanced_models:
            raise KeyError(f"학습되지 않은 향상 모델입니다: {name}")
        feature_columns = list(self.feature_columns)
        if "TimeStamp" in self.df.columns:
            feature_columns = feature_columns + ["TimeStamp"]
        return Predictor(self.enhanced_models[name], feature_columns)

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

    # 14. 3개 모델의 기본 vs 향상 성능(recall·precision·f1·pr_auc)을 막대로 비교
    def plot_enhancement_comparison(self) -> Figure:
        comparison = self.compare_baseline_vs_enhanced()
        metrics = ["recall", "precision", "f1", "pr_auc"]
        models = list(comparison.index)
        figure, axes = plt.subplots(1, len(metrics), figsize=(4 * len(metrics), 4.2))
        x = range(len(models))
        for axis, metric in zip(axes, metrics):
            base = comparison[f"{metric}_기본"].to_numpy()
            enh = comparison[f"{metric}_향상"].to_numpy()
            axis.bar([i - 0.2 for i in x], base, width=0.4, label="기본", color="#94A3B8")
            axis.bar([i + 0.2 for i in x], enh, width=0.4, label="향상", color="#2563EB")
            axis.set_title(metric)
            axis.set_ylim(0, 1)
            axis.set_xticks(list(x), models, rotation=20, fontsize=8, ha="right")
            axis.legend(fontsize=8)
        figure.suptitle("향상 기법 적용 전/후 — 3개 모델")
        figure.tight_layout()
        return figure
