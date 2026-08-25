"""사출성형기 라벨 데이터(labeled_data.csv) 분석.

노트북에서 수행하던 기초 데이터 조작과 시각화 4종을 일반 Python
프로그램으로 실행할 수 있도록 변환한 파일입니다.

실행:
    python analyze_labeled_data.py
    python analyze_labeled_data.py --no-show
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = PROJECT_DIR / "04. Dataset_Molding" / "dataset" / "labeled_data.csv"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "outputs" / "labeled_data_analysis"

KEY_COLUMNS = [
    "Injection_Time",
    "Filling_Time",
    "Plasticizing_Time",
    "Cycle_Time",
    "Max_Injection_Speed",
    "Max_Injection_Pressure",
    "Max_Back_Pressure",
    "Barrel_Temperature_1",
    "Mold_Temperature_3",
    "Mold_Temperature_4",
]


def configure_plot_style() -> None:
    """Windows에서 한글과 마이너스 기호가 깨지지 않도록 설정합니다."""
    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except OSError:
        plt.style.use("default")

    font_path = Path(r"C:\Windows\Fonts\malgun.ttf")
    if font_path.exists():
        fm.fontManager.addfont(font_path)
        font_name = fm.FontProperties(fname=font_path).get_name()
        plt.rcParams["font.family"] = font_name
    else:
        plt.rcParams["font.family"] = "Malgun Gothic"

    plt.rcParams["axes.unicode_minus"] = False


def load_data(csv_path: Path) -> pd.DataFrame:
    """사출성형 라벨 CSV를 불러오고 필수 컬럼을 검사합니다."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {csv_path}")

    df = pd.read_csv(csv_path)
    required_columns = {"PART_NAME", "PassOrFail", *KEY_COLUMNS}
    missing_columns = sorted(required_columns.difference(df.columns))
    if missing_columns:
        raise ValueError(f"필수 컬럼이 없습니다: {missing_columns}")
    return df


def print_data_overview(df: pd.DataFrame) -> None:
    """데이터 개요, 주요 기초통계 및 전체 컬럼 구조를 출력합니다."""
    print("=" * 72)
    print("사출성형기 라벨 데이터 분석")
    print("=" * 72)
    print("행/열:", df.shape)

    print("\n[데이터 상위 5행]")
    print(df.head())

    print("\n[주요 공정변수 기초통계]")
    print(df[KEY_COLUMNS].describe().T)

    print("\n[전체 컬럼]")
    print(f"전체 컬럼 수: {len(df.columns)}")
    print(list(df.columns))

    print("\n[DataFrame 정보]")
    df.info()


def calculate_group_statistics(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """제품·양불 그룹 통계와 제품별 불량률을 계산합니다."""
    group_stats = (
        df.groupby(["PART_NAME", "PassOrFail"])[KEY_COLUMNS]
        .mean()
        .round(2)
    )
    defect_rate_by_part = (
        df.groupby("PART_NAME")["PassOrFail"]
        .apply(lambda values: (values == "N").mean())
        .sort_values(ascending=False)
        .rename("defect_rate")
    )

    print("\n[제품·양불 그룹별 주요 공정변수 평균]")
    print(group_stats)

    print("\n[제품별 불량률 - 내림차순]")
    print(defect_rate_by_part)
    return group_stats, defect_rate_by_part


def finish_figure(
    figure: plt.Figure,
    output_path: Path,
    show_plots: bool,
) -> None:
    """그래프를 PNG로 저장하고 필요하면 화면에도 표시합니다."""
    figure.tight_layout()
    figure.savefig(output_path, dpi=160, bbox_inches="tight")
    if show_plots:
        plt.show()
    plt.close(figure)


def plot_quality_distribution(
    df: pd.DataFrame,
    output_dir: Path,
    show_plots: bool,
) -> None:
    """시각화 1: 양품과 불량의 클래스 분포를 표시합니다."""
    counts = df["PassOrFail"].value_counts().reindex(["Y", "N"], fill_value=0)

    figure, axis = plt.subplots(figsize=(5, 4))
    bars = axis.bar(counts.index, counts.values, color=["#4C72B0", "#C44E52"])
    axis.bar_label(bars, fmt="%d", padding=3)
    axis.set_title("양품(Y) / 불량(N) 개수 분포")
    axis.set_xlabel("PassOrFail")
    axis.set_ylabel("건수", rotation=0, labelpad=20, va="center")
    finish_figure(figure, output_dir / "01_quality_distribution.png", show_plots)


def plot_defects_by_part(
    df: pd.DataFrame,
    output_dir: Path,
    show_plots: bool,
) -> None:
    """시각화 2: 생산량 100건 이상 제품의 불량 건수를 비교합니다."""
    main_parts = df["PART_NAME"].value_counts()[lambda values: values >= 100].index
    subset = df[df["PART_NAME"].isin(main_parts)]
    defect_count_by_part = (
        subset.groupby("PART_NAME")["PassOrFail"]
        .apply(lambda values: (values == "N").sum())
        .sort_values()
    )

    figure, axis = plt.subplots(figsize=(8, 4.5))
    colors = plt.cm.Reds(np.linspace(0.4, 0.85, len(defect_count_by_part)))
    bars = axis.barh(defect_count_by_part.index, defect_count_by_part.values, color=colors)
    axis.bar_label(bars, fmt="%d", padding=3)
    axis.set_title("제품별 불량 건수 (생산량 100건 이상 제품)")
    axis.set_xlabel("불량 건수")
    axis.set_ylabel("제품명", rotation=0, labelpad=30, va="center")
    finish_figure(figure, output_dir / "02_defects_by_part.png", show_plots)


def plot_correlation_heatmap(
    df: pd.DataFrame,
    output_dir: Path,
    show_plots: bool,
) -> None:
    """시각화 3: 주요 공정변수의 상관관계 히트맵을 표시합니다."""
    correlation = df[KEY_COLUMNS].corr()
    figure, axis = plt.subplots(figsize=(10, 8))
    image = axis.imshow(correlation, cmap="coolwarm", vmin=-1, vmax=1)

    axis.set_xticks(range(len(KEY_COLUMNS)), labels=KEY_COLUMNS, rotation=60, ha="right")
    axis.set_yticks(range(len(KEY_COLUMNS)), labels=KEY_COLUMNS)
    for row in range(len(KEY_COLUMNS)):
        for column in range(len(KEY_COLUMNS)):
            value = correlation.iloc[row, column]
            text_color = "white" if abs(value) >= 0.55 else "black"
            axis.text(
                column,
                row,
                f"{value:.2f}",
                ha="center",
                va="center",
                color=text_color,
                fontsize=8,
            )

    axis.set_title("주요 공정변수 간 상관관계")
    figure.colorbar(image, ax=axis, shrink=0.8, label="상관계수")
    finish_figure(figure, output_dir / "03_correlation_heatmap.png", show_plots)


def plot_injection_speed_boxplot(
    df: pd.DataFrame,
    output_dir: Path,
    show_plots: bool,
) -> None:
    """시각화 4: 양품·불량별 최대 사출속도 분포를 비교합니다."""
    quality_speed = df.loc[df["PassOrFail"] == "Y", "Max_Injection_Speed"].dropna()
    defect_speed = df.loc[df["PassOrFail"] == "N", "Max_Injection_Speed"].dropna()

    figure, axis = plt.subplots(figsize=(5, 4))
    boxplot = axis.boxplot(
        [quality_speed, defect_speed],
        tick_labels=["Y", "N"],
        patch_artist=True,
    )
    for patch, color in zip(boxplot["boxes"], ["#4C72B0", "#C44E52"]):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)

    axis.set_title("양품/불량별 최대 사출속도 비교")
    axis.set_xlabel("PassOrFail")
    axis.set_ylabel("Max_Injection_Speed (mm/s)")
    finish_figure(figure, output_dir / "04_injection_speed_boxplot.png", show_plots)


def print_data_literacy(df: pd.DataFrame) -> None:
    """노트북의 고정 문구 대신 현재 데이터에서 계산한 인사이트를 출력합니다."""
    total_count = len(df)
    defect_count = int((df["PassOrFail"] == "N").sum())
    defect_rate = defect_count / total_count * 100 if total_count else 0.0

    part_summary = df.groupby("PART_NAME")["PassOrFail"].agg(
        production_count="size",
        defect_count=lambda values: int((values == "N").sum()),
        defect_rate=lambda values: float((values == "N").mean() * 100),
    )
    priority_part = part_summary.sort_values(
        ["defect_rate", "defect_count"], ascending=False
    ).iloc[0]
    priority_name = part_summary.sort_values(
        ["defect_rate", "defect_count"], ascending=False
    ).index[0]

    correlation = df[KEY_COLUMNS].corr().abs()
    upper_triangle = correlation.where(
        np.triu(np.ones(correlation.shape), k=1).astype(bool)
    )
    strongest_pair = upper_triangle.stack().idxmax()
    strongest_value = df[list(strongest_pair)].corr().iloc[0, 1]

    quality_speed = df.loc[
        df["PassOrFail"] == "Y", "Max_Injection_Speed"
    ].mean()
    defect_speed = df.loc[
        df["PassOrFail"] == "N", "Max_Injection_Speed"
    ].mean()

    print("\n[데이터 리터러시 요약]")
    print(f"- 전체 {total_count:,}건 중 불량은 {defect_count:,}건({defect_rate:.2f}%)입니다.")
    print(
        f"- 불량률 우선 점검 제품은 {priority_name}이며, "
        f"생산 {int(priority_part['production_count']):,}건 중 "
        f"불량 {int(priority_part['defect_count']):,}건"
        f"({priority_part['defect_rate']:.2f}%)입니다."
    )
    print(
        f"- 가장 강한 상관관계는 {strongest_pair[0]}와 {strongest_pair[1]} "
        f"({strongest_value:.2f})입니다."
    )
    print(
        "- 최대 사출속도 평균은 "
        f"양품 {quality_speed:.2f}, 불량 {defect_speed:.2f}mm/s입니다."
    )
    print("- 불량 비율이 낮으므로 모델 평가는 정확도뿐 아니라 재현율과 F1도 봐야 합니다.")
    print("- 관찰된 관계는 상관관계이며, 인과관계 확정에는 추가 공정 실험이 필요합니다.")


def run_analysis(csv_path: Path, output_dir: Path, show_plots: bool) -> None:
    configure_plot_style()
    df = load_data(csv_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    print_data_overview(df)
    calculate_group_statistics(df)
    plot_quality_distribution(df, output_dir, show_plots)
    plot_defects_by_part(df, output_dir, show_plots)
    plot_correlation_heatmap(df, output_dir, show_plots)
    plot_injection_speed_boxplot(df, output_dir, show_plots)
    print_data_literacy(df)
    print(f"\n그래프 저장 위치: {output_dir.resolve()}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="사출성형기 라벨 데이터 분석")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="분석할 CSV 경로")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="그래프 PNG 저장 폴더",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="그래프 창을 열지 않고 PNG 파일만 저장",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    run_analysis(arguments.csv, arguments.output_dir, not arguments.no_show)


if __name__ == "__main__":
    main()
