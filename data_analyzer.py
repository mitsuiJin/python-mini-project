"""DataFrame 기반 통계 분석 기능을 제공한다."""

from collections.abc import Sequence
import pandas as pd


class DataAnalyzer:
    """전처리된 DataFrame의 요약 통계와 관계를 분석한다."""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def get_summary(self) -> pd.DataFrame:
        """수치형·범주형 컬럼의 기초 통계를 반환"""
        return self.df.describe(include="all").transpose()

    def get_class_distribution(self, target_column: str) -> pd.DataFrame:
        """종속변수의 건수와 비율을 반환"""
        self._require_columns([target_column])
        counts = self.df[target_column].value_counts(dropna=False)

        return pd.DataFrame(
            {
                "count": counts,
                "ratio": counts / len(self.df),
            }
        )

    def get_group_summary(
        self,
        group_columns: str | Sequence[str],
        value_columns: str | Sequence[str],
        agg: str | Sequence[str] = ("count", "mean", "median", "std"),
    ) -> pd.DataFrame:
        """제품·설비 등 그룹별 집계 결과를 반환한다."""
        groups = [group_columns] if isinstance(group_columns, str) else list(group_columns)
        values = [value_columns] if isinstance(value_columns, str) else list(value_columns)
        self._require_columns(groups + values)
        return self.df.groupby(groups, dropna=False)[values].agg(agg)

    def get_correlation(self) -> pd.DataFrame:
        """수치형 컬럼의 피어슨 상관계수 행렬을 반환한다."""
        numeric_df = self.df.select_dtypes(include="number")
        return numeric_df.corr()

    def get_missing_summary(self) -> pd.DataFrame:
        """컬럼별 결측치 건수와 비율을 반환한다."""
        missing_count = self.df.isna().sum()
        return pd.DataFrame(
            {
                "missing_count": missing_count,
                "missing_ratio": missing_count / len(self.df),
            }
        ).sort_values("missing_count", ascending=False)

    def _require_columns(self, columns: Sequence[str]) -> None:
        missing = [column for column in columns if column not in self.df.columns]
        if missing:
            raise KeyError(f"DataFrame에 없는 컬럼입니다: {missing}")
