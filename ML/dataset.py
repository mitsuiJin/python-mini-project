"""CN7/RG3 준지도 학습용 데이터(2차 가공 데이터) 로드.

'04. Dataset_Molding/dataset/' 안의 moldset_labeled_{product}.csv,
moldset_unlabeled_{product}.csv는 가이드북 기준 이미 2차 가공이 끝난
데이터라서(제품별 컬럼 정리, PassOrFail 0/1 인코딩 완료), 가이드북의
[단계①~④](make_input, Y/N 변환)를 다시 적용할 필요가 없다.

CN7/RG3 모두 라벨 있는 불량 표본이 매우 적다(CN7 17건, RG3 25건). 이렇게
적은 수에서 한 번의 train/test 분리로 평가하면 어떤 몇 건이 테스트에
걸리느냐에 따라 지표가 크게 흔들리므로, 정규화(StandardScaler)는 매
교차검증 fold 안에서 fold의 학습 데이터로만 fit해야 한다. 그래서 여기서는
스케일링 이전의 원본 수치만 반환하고, 스케일링은 평가 루프
(ML/evaluation.py) 쪽에서 fold마다 수행한다.
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

DATASET_DIR = (
    Path(__file__).resolve().parent.parent / "04. Dataset_Molding" / "dataset"
)

TARGET = "PassOrFail"


@dataclass
class RawProductData:
    """제품 1개(CN7 또는 RG3)의 스케일링 전 원본 데이터."""

    product: str
    X_labeled: pd.DataFrame
    y_labeled: pd.Series
    X_unlabeled: pd.DataFrame


def _read_product_csv(product: str, kind: str) -> pd.DataFrame:
    path = DATASET_DIR / f"moldset_{kind}_{product}.csv"
    if not path.exists():
        raise FileNotFoundError(f"데이터 파일을 찾을 수 없습니다: {path}")
    df = pd.read_csv(path)
    return df.drop(columns=[c for c in df.columns if c.startswith("Unnamed")])


def load_raw_product_data(
    product: str,
    max_unlabeled: int | None = 5000,
    random_state: int = 42,
) -> RawProductData:
    """moldset_labeled_{product}.csv / moldset_unlabeled_{product}.csv를 불러온다.

    max_unlabeled: pseudo-labeling 루프에서 매 반복마다 모델을 통째로
        재학습하므로, unlabeled 전체(3만 건 이상)를 그대로 쓰면 특히 SVM이
        비현실적으로 느려진다. 실습 목적상 unlabeled 데이터를 이 개수로
        무작위 다운샘플링한다. None을 넘기면 원본 그대로 사용한다.
    """
    labeled = _read_product_csv(product, "labeled")
    unlabeled = _read_product_csv(product, "unlabeled")
    if max_unlabeled is not None and len(unlabeled) > max_unlabeled:
        unlabeled = unlabeled.sample(n=max_unlabeled, random_state=random_state)

    y = labeled[TARGET].reset_index(drop=True)
    X = labeled.drop(columns=[TARGET]).reset_index(drop=True)
    X_unlabeled = unlabeled[X.columns].reset_index(drop=True)

    return RawProductData(
        product=product, X_labeled=X, y_labeled=y, X_unlabeled=X_unlabeled
    )
