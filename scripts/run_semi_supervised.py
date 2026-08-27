"""가이드북 2.3.2 '준지도 학습' 트랙 실행 스크립트.

CN7·RG3 각 제품에 대해 GaussianNB / RandomForest / SVM 세 모델을 학습·
평가하고, 가이드북 5절과 같은 형태의 정확도/정밀도/재현율/ROC-AUC/F1
비교표를 출력한다.

라벨 있는 불량 표본이 극히 적어(CN7 17건, RG3 25건) 단일 train/test
분리는 결과가 불안정하다. 5-fold 층화 교차검증으로 평가하고, 매 폴드
평균을 최종 성능으로 보고한다 (ML/evaluation.py).

기본값은 순수 지도학습(라벨 데이터만 사용)이다. --pseudo-label을 주면
가이드북 방식대로 unlabeled 데이터를 pseudo-labeling에 사용하는데, 이
데이터셋에서는 실측 결과 pseudo-labeling이 성능을 오히려 낮추는 경우가
많았다(ML/semi_supervised.py 모듈 docstring 참고). 기본을 끈 상태로 둔 것은
"최대한 좋은 성능"을 우선한 선택이다.

실행:
    python scripts/run_semi_supervised.py                # 지도학습, 기본 하이퍼파라미터
    python scripts/run_semi_supervised.py --tune          # GridSearchCV 탐색 후 실행
    python scripts/run_semi_supervised.py --pseudo-label  # 가이드북 방식 pseudo-labeling 포함
"""

import argparse
import sys
import warnings
from pathlib import Path

import pandas as pd
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ML.dataset import load_raw_product_data
from ML.evaluation import cross_validate
from ML.hyperparameter_search import search_random_forest_params, search_svm_params
from ML.models import DEFAULT_RF_PARAMS, DEFAULT_SVM_PARAMS, build_model_factories

# sklearn 1.9+ SVC(probability=True) 지원 경고: 반복 학습마다 매번 뜨는
# 잡음이라 실행 로그에서는 숨긴다.
warnings.filterwarnings("ignore", category=FutureWarning, module="sklearn.svm")

PRODUCTS = ["cn7", "rg3"]


def resolve_params(X_labeled: pd.DataFrame, y_labeled: pd.Series, tune: bool):
    if not tune:
        return DEFAULT_RF_PARAMS, DEFAULT_SVM_PARAMS

    print("  하이퍼파라미터 탐색 중 (RandomForest, SVM)...")
    # 하이퍼파라미터 탐색용으로만 전체 라벨 데이터에 스케일러를 fit한다.
    # (최종 성능 평가는 ML/evaluation.cross_validate가 fold별로 다시
    # 스케일링하므로 여기서의 약간의 데이터 재사용은 탐색 단계에 한정된다.)
    X_scaled = pd.DataFrame(
        StandardScaler().fit_transform(X_labeled), columns=X_labeled.columns
    )
    rf_params = search_random_forest_params(X_scaled, y_labeled)
    svm_params = search_svm_params(X_scaled, y_labeled)
    rf_params.pop("class_weight", None)  # class_weight는 balanced_subsample 고정
    print(f"  RandomForest best params: {rf_params}")
    print(f"  SVM best params: {svm_params}")
    return {**DEFAULT_RF_PARAMS, **rf_params}, svm_params


def run_product(product: str, tune: bool, pseudo_label: bool, max_unlabeled: int | None):
    print(f"\n=== {product.upper()} ===")
    data = load_raw_product_data(product, max_unlabeled=max_unlabeled)
    print(
        f"  labeled={len(data.X_labeled)} (불량 {int(data.y_labeled.sum())}건, "
        f"{data.y_labeled.mean():.2%}), unlabeled={len(data.X_unlabeled)}, "
        f"pseudo_labeling={'ON' if pseudo_label else 'OFF'}"
    )

    rf_params, svm_params = resolve_params(data.X_labeled, data.y_labeled, tune)
    factories = build_model_factories(rf_params, svm_params)

    rows = {}
    for name, factory in factories.items():
        print(f"  {name}: 5-fold 교차검증 중...")
        result = cross_validate(
            factory,
            data.X_labeled,
            data.y_labeled,
            X_unlabeled=data.X_unlabeled if pseudo_label else None,
            use_pseudo_labeling=pseudo_label,
        )
        rows[name] = result.summary()
        print(f"    합산 혼동행렬 (5-fold):\n{result.pooled_confusion_matrix()}")

    comparison = pd.DataFrame(rows).T.sort_values("f1", ascending=False)
    print(f"\n[{product.upper()} 결과 비교 (5-fold 교차검증 평균, F1 기준 정렬)]")
    print(comparison.to_string(float_format=lambda v: f"{v:.4f}"))
    return comparison


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tune",
        action="store_true",
        help="GridSearchCV로 RandomForest/SVM 하이퍼파라미터를 탐색한 뒤 실행",
    )
    parser.add_argument(
        "--pseudo-label",
        action="store_true",
        help="가이드북 방식대로 unlabeled 데이터를 pseudo-labeling에 사용 "
        "(기본은 라벨 데이터만 쓰는 지도학습 — 이 데이터셋에서 더 안정적)",
    )
    parser.add_argument(
        "--product",
        choices=PRODUCTS,
        help="특정 제품만 실행 (지정하지 않으면 CN7, RG3 모두 실행)",
    )
    parser.add_argument(
        "--max-unlabeled",
        type=int,
        default=5000,
        help="pseudo-labeling에 사용할 unlabeled 데이터 상한 (SVM 학습 시간 제어용, "
        "기본 5000). 0을 지정하면 전체 사용",
    )
    args = parser.parse_args()

    max_unlabeled = None if args.max_unlabeled == 0 else args.max_unlabeled
    products = [args.product] if args.product else PRODUCTS
    for product in products:
        run_product(product, args.tune, args.pseudo_label, max_unlabeled)


if __name__ == "__main__":
    main()
