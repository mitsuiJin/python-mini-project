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
    """matplotlib Figure 시각화 그래프들"""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def plot_class_distribution(self, target_column: str) -> Figure:
        """1. 종속변수의 클래스별 건수를 막대그래프로 표시"""
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
        """2. 수치형 컬럼의 히스토그램을 생성"""
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
        """3. 전체 또는 그룹별 수치형 컬럼의 박스플롯을 생성"""
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
        """4. 수치형 컬럼의 상관관계 히트맵을 생성"""
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

    def plot_dashboard(
        self,
        product_distribution: pd.DataFrame,
        quality_distribution: pd.DataFrame,
        numeric_summary: pd.DataFrame,
        fault_distribution: pd.DataFrame,
    ) -> Figure:
        """제품·품질·수치 평균·고장 원인을 2×2 대시보드로 표시한다."""
        figure = plt.figure(
            figsize=(12.5, 6.4),
            facecolor="#F4F7FB",
            constrained_layout=True,
        )
        grid = figure.add_gridspec(2, 2, hspace=0.28, wspace=0.20)
        product_axis = figure.add_subplot(grid[0, 0])
        quality_axis = figure.add_subplot(grid[0, 1])
        mean_axis = figure.add_subplot(grid[1, 0])
        fault_axis = figure.add_subplot(grid[1, 1])

        self._plot_dashboard_pie(
            product_axis,
            product_distribution,
            title="CN7 · RG3 데이터 비율",
            colors=("#2563EB", "#14B8A6"),
        )
        self._plot_quality_donut(quality_axis, quality_distribution)
        self._plot_numeric_means(mean_axis, numeric_summary)
        self._plot_fault_reasons(fault_axis, fault_distribution)
        return figure

    @staticmethod
    def _plot_dashboard_pie(axis, distribution, title, colors) -> None:
        counts = distribution["count"].astype(float)
        axis.set_facecolor("white")
        if counts.sum() == 0:
            axis.text(0.5, 0.5, "표시할 데이터가 없습니다.", ha="center", va="center")
            axis.set_title(title, loc="left", fontweight="bold")
            axis.axis("off")
            return

        labels = [str(label) for label in distribution.index]
        wedges, _, _ = axis.pie(
            counts,
            colors=colors[:len(counts)],
            startangle=90,
            counterclock=False,
            autopct="%1.1f%%",
            pctdistance=0.70,
            textprops={"fontsize": 9, "fontweight": "bold"},
            wedgeprops={"edgecolor": "white", "linewidth": 2},
        )
        legend_labels = [
            f"{label}  {int(count):,}건"
            for label, count in zip(labels, counts)
        ]
        axis.legend(
            wedges,
            legend_labels,
            loc="center left",
            bbox_to_anchor=(0.86, 0.5),
            frameon=False,
            fontsize=9,
        )
        axis.set_title(title, loc="left", fontweight="bold", color="#172033")

    @staticmethod
    def _plot_quality_donut(axis, distribution) -> None:
        counts = distribution["count"].astype(float)
        axis.set_facecolor("white")
        if counts.sum() == 0:
            axis.text(0.5, 0.5, "표시할 데이터가 없습니다.", ha="center", va="center")
            axis.set_title("양품 · 불량 비율", loc="left", fontweight="bold")
            axis.axis("off")
            return

        labels = [str(label) for label in distribution.index]
        colors = ["#22C55E" if label == "양품" else "#EF4444" for label in labels]
        wedges, _, _ = axis.pie(
            counts,
            colors=colors,
            startangle=90,
            counterclock=False,
            autopct="%1.1f%%",
            pctdistance=0.78,
            textprops={"fontsize": 9, "fontweight": "bold"},
            wedgeprops={"width": 0.38, "edgecolor": "white", "linewidth": 2},
        )
        defect_rate = (
            float(distribution.loc["불량", "percentage"])
            if "불량" in distribution.index
            else 0.0
        )
        axis.text(
            0, 0, f"불량률\n{defect_rate:.2f}%",
            ha="center", va="center", fontsize=12,
            fontweight="bold", color="#172033",
        )
        legend_labels = [
            f"{label}  {int(count):,}건"
            for label, count in zip(labels, counts)
        ]
        axis.legend(
            wedges,
            legend_labels,
            loc="center left",
            bbox_to_anchor=(0.86, 0.5),
            frameon=False,
            fontsize=9,
        )
        axis.set_title("양품 · 불량 비율", loc="left", fontweight="bold", color="#172033")

    @staticmethod
    def _plot_numeric_means(axis, numeric_summary) -> None:
        preferred = (
            "Injection_Time", "Filling_Time", "Plasticizing_Time", "Cycle_Time",
            "Max_Injection_Speed", "Max_Screw_RPM",
            "Max_Injection_Pressure", "Hopper_Temperature",
        )
        indicators = [
            indicator for indicator in preferred if indicator in numeric_summary.index
        ]
        if not indicators:
            indicators = numeric_summary.index.astype(str).tolist()[:8]

        axis.set_facecolor("white")
        axis.set_title("주요 수치 지표 평균", loc="left", fontweight="bold", color="#172033")
        if not indicators:
            axis.text(0.5, 0.5, "표시할 수치 지표가 없습니다.", ha="center", va="center")
            axis.axis("off")
            return

        means = numeric_summary.loc[indicators, "mean"].astype(float)
        max_value = means.abs().max()
        relative = means.abs() / max_value if max_value else means.abs()
        positions = np.arange(len(indicators))
        bars = axis.barh(positions, relative, color="#64748B", height=0.62)
        axis.set_yticks(positions, indicators, fontsize=8)
        axis.invert_yaxis()
        axis.set_xlim(0, 1.22)
        axis.set_xticks([])
        axis.set_xlabel("막대 길이는 지표 내 상대 크기 · 라벨은 실제 평균값", fontsize=8)
        axis.grid(False)
        for spine in axis.spines.values():
            spine.set_visible(False)
        for bar, value in zip(bars, means):
            axis.text(
                min(bar.get_width() + 0.025, 1.05),
                bar.get_y() + bar.get_height() / 2,
                f"{value:,.2f}",
                va="center",
                fontsize=8,
                color="#172033",
            )

    @staticmethod
    def _plot_fault_reasons(axis, distribution) -> None:
        axis.set_facecolor("white")
        axis.set_title("고장 원인별 불량 현황", loc="left", fontweight="bold", color="#172033")
        if distribution.empty or distribution["count"].sum() == 0:
            axis.text(0.5, 0.5, "표시할 고장 원인이 없습니다.", ha="center", va="center")
            axis.axis("off")
            return

        values = distribution.sort_values("count", ascending=True)
        bars = axis.barh(
            values.index.astype(str), values["count"], color="#F59E0B", height=0.58
        )
        maximum = float(values["count"].max())
        axis.set_xlim(0, maximum * 1.28 if maximum else 1)
        axis.set_xlabel("불량 건수")
        axis.grid(axis="x", alpha=0.18)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        for bar, (_, row) in zip(bars, values.iterrows()):
            axis.text(
                bar.get_width() + maximum * 0.025,
                bar.get_y() + bar.get_height() / 2,
                f"{int(row['count']):,}건  ({row['percentage']:.1f}%)",
                va="center",
                fontsize=9,
                color="#172033",
            )

    def _require_column(self, column: str) -> None:
        if column not in self.df.columns:
            raise KeyError(f"DataFrame에 없는 컬럼입니다: {column}")

    def _require_numeric_column(self, column: str) -> None:
        self._require_column(column)
        if not pd.api.types.is_numeric_dtype(self.df[column]):
            raise TypeError(f"수치형 컬럼이 아닙니다: {column}")
