"""DataFrame 기반 통계 분석 기능을 제공"""

from collections.abc import Sequence
import pandas as pd


class DataAnalyzer:
    """전처리된 DataFrame의 요약 통계와 관계를 분석한"""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def get_product_distribution(
        self,
        product_column: str = "PART_NAME",
        product_codes: Sequence[str] = ("CN7", "RG3"),
    ) -> pd.DataFrame:
        """제품 접두어별 건수·비율·퍼센트를 반환한다."""
        self._require_columns([product_column])
        codes = self._normalize_product_codes(product_codes)
        product_names = (
            self.df[product_column].astype("string").str.strip().str.upper()
        )
        product_groups = pd.Series(
            pd.NA, index=self.df.index, dtype="string", name="product"
        )
        for code in codes:
            product_groups.loc[
                product_groups.isna()
                & product_names.str.startswith(code, na=False)
            ] = code

        counts = (
            product_groups.dropna()
            .value_counts()
            .reindex(codes, fill_value=0)
        )
        counts.index.name = "product"
        return self._make_distribution(counts)

    def get_quality_distribution(
        self,
        target_column: str = "PassOrFail",
        pass_value: str = "Y",
        fail_value: str = "N",
    ) -> pd.DataFrame:
        """양품·불량 건수와 비율·퍼센트를 반환한다."""
        self._require_columns([target_column])
        target = self.df[target_column].astype("string").str.strip().str.casefold()
        quality = pd.Series(pd.NA, index=self.df.index, dtype="string")
        quality.loc[target.eq(str(pass_value).strip().casefold())] = "양품"
        quality.loc[target.eq(str(fail_value).strip().casefold())] = "불량"
        counts = quality.dropna().value_counts().reindex(
            ["양품", "불량"], fill_value=0
        )
        counts.index.name = "quality"
        return self._make_distribution(counts)

    def get_numeric_mean_summary(
        self,
        value_columns: Sequence[str] | None = None,
        exclude_columns: Sequence[str] = ("PART_FACT_SERIAL", "target"),
    ) -> pd.DataFrame:
        """수치 지표별 평균·유효 건수·결측 건수를 반환한다."""
        if value_columns is None:
            columns = self.df.select_dtypes(include="number").columns.tolist()
        else:
            columns = list(value_columns)
            self._require_columns(columns)

        excluded = set(exclude_columns)
        columns = [column for column in columns if column not in excluded]
        non_numeric = [
            column
            for column in columns
            if not pd.api.types.is_numeric_dtype(self.df[column])
        ]
        if non_numeric:
            raise TypeError(f"수치형이 아닌 컬럼입니다: {non_numeric}")

        if not columns:
            return pd.DataFrame(
                columns=["mean", "valid_count", "missing_count"],
                index=pd.Index([], name="indicator"),
            )

        values = self.df[columns]
        summary = pd.DataFrame(
            {
                "mean": values.mean(),
                "valid_count": values.count(),
                "missing_count": values.isna().sum(),
            }
        )
        summary.index.name = "indicator"
        return summary

    def get_fault_reason_distribution(
        self,
        reason_column: str = "Reason",
        target_column: str = "PassOrFail",
        fail_value: str = "N",
    ) -> pd.DataFrame:
        """불량 행만 대상으로 고장 원인별 건수·비율·퍼센트를 반환한다."""
        self._require_columns([reason_column, target_column])
        target = self.df[target_column].astype("string").str.strip().str.casefold()
        reasons = (
            self.df.loc[
                target.eq(str(fail_value).strip().casefold()),
                reason_column,
            ]
            .astype("string")
            .str.strip()
            .dropna()
        )
        reasons = reasons[reasons.ne("")]
        counts = reasons.value_counts()
        counts.index.name = "fault_reason"
        return self._make_distribution(counts)

    @staticmethod
    def _make_distribution(counts: pd.Series) -> pd.DataFrame:
        total = int(counts.sum())
        ratio = counts.astype(float) / total if total else counts.astype(float)
        return pd.DataFrame(
            {
                "count": counts.astype("int64"),
                "ratio": ratio,
                "percentage": ratio.mul(100),
            }
        )

    @staticmethod
    def _normalize_product_codes(product_codes: Sequence[str]) -> list[str]:
        codes = [
            str(code).strip().upper()
            for code in product_codes
            if str(code).strip()
        ]
        if not codes:
            raise ValueError("분석할 제품 코드를 하나 이상 지정하세요.")
        if len(codes) != len(set(codes)):
            raise ValueError("제품 코드가 중복되었습니다.")
        return codes

    def _require_columns(self, columns: Sequence[str]) -> None:
        missing = [column for column in columns if column not in self.df.columns]
        if missing:
            raise KeyError(f"DataFrame에 없는 컬럼입니다: {missing}")
