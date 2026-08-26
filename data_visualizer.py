"""DataFrame 분석 결과를 matplotlib Figure로 생성한다."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.ticker import FormatStrFormatter


# Windows 환경에서 그래프의 한글과 마이너스 기호가 깨지지 않도록 설정한다.
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


class DataVisualizer:
    """Tkinter에 삽입할 수 있는 matplotlib Figure"""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def plot_class_distribution(self, target_column: str) -> Figure:
        """종속변수의 클래스별 건수를 막대그래프로 표시"""
        self._require_column(target_column)
        counts = self.df[target_column].value_counts(dropna=False)

        figure, axis = plt.subplots(figsize=(7, 4))
        counts.plot(kind="bar", ax=axis, color="#3b82f6")
        axis.set_title(f"{target_column} 분포")
        axis.set_xlabel(target_column)
        axis.set_ylabel("건수")
        axis.tick_params(axis="x", rotation=0)
        figure.tight_layout()
        return figure

    def plot_histogram(self, column: str, bins: int = 30) -> Figure:
        """수치형 컬럼의 히스토그램을 생성"""
        self._require_numeric_column(column)

        figure, axis = plt.subplots(figsize=(7, 4))
        axis.hist(self.df[column].dropna(), bins=bins, color="#14b8a6", alpha=0.8)
        axis.set_title(f"{column} 분포")
        axis.set_xlabel(column)
        axis.set_ylabel("빈도")
        axis.xaxis.set_major_formatter(FormatStrFormatter("%.2f"))
        figure.tight_layout()
        return figure

    def plot_boxplot(self, column: str, group_column: str | None = None) -> Figure:
        """전체 또는 그룹별 수치형 컬럼의 박스플롯을 생성"""
        self._require_numeric_column(column)
        figure, axis = plt.subplots(figsize=(8, 5))

        if group_column is None:
            axis.boxplot(self.df[column].dropna(), tick_labels=[column])
        else:
            self._require_column(group_column)
            groups = list(self.df.groupby(group_column, dropna=False))
            grouped = [group[column].dropna().to_numpy() for _, group in groups]
            labels = [str(label) for label, _ in groups]
            axis.boxplot(grouped, tick_labels=labels)
            axis.set_xlabel(group_column)

        axis.set_title(f"{column} 박스플롯")
        axis.set_ylabel(column)
        axis.yaxis.set_major_formatter(FormatStrFormatter("%.2f"))
        figure.tight_layout()
        return figure

    def plot_correlation_heatmap(self) -> Figure:
        """수치형 컬럼의 상관관계 히트맵을 생성"""
        correlation = self.df.select_dtypes(include="number").corr()
        if correlation.empty:
            raise ValueError("상관관계를 계산할 수치형 컬럼이 없습니다.")

        size = max(7, min(14, len(correlation.columns) * 0.45))
        figure, axis = plt.subplots(figsize=(size, size))
        image = axis.imshow(correlation, cmap="coolwarm", vmin=-1, vmax=1)
        ticks = np.arange(len(correlation.columns))
        axis.set_xticks(ticks, correlation.columns, rotation=90, fontsize=7)
        axis.set_yticks(ticks, correlation.columns, fontsize=7)
        axis.set_title("수치형 컬럼 상관관계")
        figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
        figure.tight_layout()
        return figure

    def _require_column(self, column: str) -> None:
        if column not in self.df.columns:
            raise KeyError(f"DataFrame에 없는 컬럼입니다: {column}")

    def _require_numeric_column(self, column: str) -> None:
        self._require_column(column)
        if not pd.api.types.is_numeric_dtype(self.df[column]):
            raise TypeError(f"수치형 컬럼이 아닙니다: {column}")
