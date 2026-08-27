"""준지도 학습 트랙에서 쓰는 3개 모델(GaussianNB, RandomForest, SVM)의
기본 하이퍼파라미터와 생성 함수.

scripts/run_semi_supervised.py와 UI(UI/main_window.py)가 같은 설정을
공유하기 위한 모듈이다. 기본값은 CN7 라벨 데이터에 GridSearchCV(5-fold,
scoring='f1')로 찾은 값이다(scripts/run_semi_supervised.py --tune 참고).
"""

from typing import Callable

from sklearn.base import ClassifierMixin
from sklearn.ensemble import RandomForestClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.svm import SVC

DEFAULT_RF_PARAMS = {
    "n_estimators": 300,
    "max_depth": 12,
    "min_samples_leaf": 1,
    "class_weight": "balanced_subsample",
}
DEFAULT_SVM_PARAMS = {"C": 1.0, "gamma": "scale", "kernel": "rbf"}

ModelFactory = Callable[[], ClassifierMixin]


def build_model_factories(
    rf_params: dict | None = None, svm_params: dict | None = None
) -> dict[str, ModelFactory]:
    rf_params = rf_params or DEFAULT_RF_PARAMS
    svm_params = svm_params or DEFAULT_SVM_PARAMS
    return {
        "gaussian_nb": lambda: GaussianNB(),
        "random_forest": lambda: RandomForestClassifier(random_state=42, **rf_params),
        "svm": lambda: SVC(
            class_weight="balanced", probability=True, random_state=42, **svm_params
        ),
    }
