"""사출성형 제조 데이터 분석용 Tkinter 메인 화면."""

import warnings
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# sklearn 1.9+ SVC(probability=True) 지원 경고: 준지도 학습 교차검증마다
# 매번 뜨는 잡음이라 숨긴다.
warnings.filterwarnings("ignore", category=FutureWarning, module="sklearn.svm")

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from Analyze.data_analyzer import DataAnalyzer
from Analyze.data_loader import DataLoader
from Analyze.data_visualizer import DataVisualizer
from Analyze.preprocessor import Preprocessor
from ML.dataset import load_raw_product_data
from ML.evaluation import CVResult, cross_validate
from ML.models import build_model_factories


DEFAULT_DATA_PATH = (
    Path(__file__).resolve().parent.parent
    / "04. Dataset_Molding"
    / "dataset"
    / "labeled_data.csv"
)


class MainWindow:
    """데이터 로드부터 예측까지 각 클래스를 연결"""

    PREVIEW_ROWS = 100 # 행 미리보기 개수 설정

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("CN7 · RG3 사출성형 데이터 분석")
        self.root.geometry("1380x820")
        self.root.minsize(1100, 680)

        self.loader = DataLoader()
        self.raw_df: pd.DataFrame | None = None
        self.clean_df: pd.DataFrame | None = None
        self.analyzer: DataAnalyzer | None = None
        self.visualizer: DataVisualizer | None = None
        self.chart_canvas: FigureCanvasTkAgg | None = None
        self.analysis_chart_canvas: FigureCanvasTkAgg | None = None
        self.model_chart_canvas: FigureCanvasTkAgg | None = None
        self.dashboard_kpi_vars: dict[str, tuple[tk.StringVar, tk.StringVar]] = {}
        self.cv_comparison: pd.DataFrame | None = None
        self.cv_results: dict[str, CVResult] | None = None

        self.file_path_var = tk.StringVar(value=str(DEFAULT_DATA_PATH))
        self.cn7_rg3_only_var = tk.BooleanVar(value=True)
        self.chart_type_var = tk.StringVar(value="불량 분포")
        self.sensor_var = tk.StringVar(value="Injection_Time")
        self.model_product_var = tk.StringVar(value="cn7")
        self.pseudo_label_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="CSV 파일을 불러오세요.")
        self._build_ui()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self.root, padding=10)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(1, weight=1)
        ttk.Label(toolbar, text="CSV 파일").grid(row=0, column=0, padx=(0, 6))
        ttk.Entry(toolbar, textvariable=self.file_path_var).grid(
            row=0, column=1, sticky="ew", padx=(0, 6)
        )
        ttk.Button(toolbar, text="찾아보기", command=self.browse_file).grid(
            row=0, column=2, padx=3
        )

        buttons = (
            ("1. 데이터 로드", self.load_data),
            ("2. 전처리", self.preprocess_data),
            ("3. 분석", self.run_analysis),
        )

        for column, (label, action) in enumerate(buttons, start=3):
            ttk.Button(
                toolbar,
                text=label,
                command=lambda selected=action: self._run_ui_action(selected),
            ).grid(row=0, column=column, padx=3)

        ttk.Checkbutton(
            toolbar,
            text="CN7·RG3만 사용",
            variable=self.cn7_rg3_only_var,
        ).grid(row=1, column=1, sticky="w", pady=(7, 0))

        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        self.preview_tab = ttk.Frame(self.notebook)
        self.analysis_tab = ttk.Frame(self.notebook)
        self.chart_tab = ttk.Frame(self.notebook)
        self.model_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.preview_tab, text="데이터 미리보기")
        self.notebook.add(self.analysis_tab, text="분석 대시보드")
        self.notebook.add(self.chart_tab, text="시각화")
        self.notebook.add(self.model_tab, text="모델 및 예측")

        self._build_preview_tab()
        self._build_analysis_tab()
        self._build_chart_tab()
        self._build_model_tab()
        ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief="sunken",
            anchor="w",
            padding=5,
        ).grid(row=2, column=0, sticky="ew")

    def _build_preview_tab(self) -> None:
        self.preview_tab.columnconfigure(0, weight=1)
        self.preview_tab.rowconfigure(0, weight=1)
        self.preview_tree = ttk.Treeview(self.preview_tab, show="headings")
        y_scroll = ttk.Scrollbar(
            self.preview_tab, orient="vertical", command=self.preview_tree.yview
        )
        x_scroll = ttk.Scrollbar(
            self.preview_tab, orient="horizontal", command=self.preview_tree.xview
        )
        self.preview_tree.configure(
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
        )
        self.preview_tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

    def _build_analysis_tab(self) -> None:
        self.analysis_tab.columnconfigure(0, weight=1)
        self.analysis_tab.rowconfigure(2, weight=1)

        header = tk.Frame(self.analysis_tab, bg="#172033", padx=18, pady=12)
        header.grid(row=0, column=0, sticky="ew")
        tk.Label(
            header,
            text="CN7 · RG3 제조 품질 대시보드",
            bg="#172033",
            fg="white",
            font=("Malgun Gothic", 16, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            header,
            text="전처리 완료 데이터를 기준으로 제품 구성, 품질, 공정 평균과 고장 원인을 요약합니다.",
            bg="#172033",
            fg="#CBD5E1",
            font=("Malgun Gothic", 9),
            anchor="w",
        ).pack(fill="x", pady=(3, 0))

        kpi_frame = tk.Frame(self.analysis_tab, bg="#F4F7FB", padx=10, pady=10)
        kpi_frame.grid(row=1, column=0, sticky="ew")
        kpi_specs = (
            ("total", "전체 데이터", "#475569"),
            ("cn7", "CN7 비율", "#2563EB"),
            ("rg3", "RG3 비율", "#14B8A6"),
            ("defect", "전체 불량률", "#EF4444"),
        )
        for column, (key, title, accent) in enumerate(kpi_specs):
            kpi_frame.columnconfigure(column, weight=1, uniform="dashboard_kpi")
            card = tk.Frame(
                kpi_frame,
                bg="white",
                highlightbackground="#DCE3ED",
                highlightthickness=1,
                padx=14,
                pady=9,
            )
            card.grid(
                row=0,
                column=column,
                sticky="nsew",
                padx=(0 if column == 0 else 5, 0 if column == 3 else 5),
            )
            title_row = tk.Frame(card, bg="white")
            title_row.pack(fill="x")
            tk.Frame(title_row, bg=accent, width=5, height=18).pack(side="left")
            tk.Label(
                title_row,
                text=title,
                bg="white",
                fg="#64748B",
                font=("Malgun Gothic", 9, "bold"),
            ).pack(side="left", padx=(7, 0))

            value_var = tk.StringVar(value="—")
            detail_var = tk.StringVar(value="분석 버튼을 눌러주세요.")
            tk.Label(
                card,
                textvariable=value_var,
                bg="white",
                fg="#172033",
                font=("Malgun Gothic", 18, "bold"),
                anchor="w",
            ).pack(fill="x", pady=(5, 0))
            tk.Label(
                card,
                textvariable=detail_var,
                bg="white",
                fg="#64748B",
                font=("Malgun Gothic", 8),
                anchor="w",
            ).pack(fill="x")
            self.dashboard_kpi_vars[key] = (value_var, detail_var)

        self.dashboard_chart_frame = tk.Frame(
            self.analysis_tab,
            bg="#F4F7FB",
            padx=8,
            pady=0,
        )
        self.dashboard_chart_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 8))

    def _build_chart_tab(self) -> None:
        self.chart_tab.columnconfigure(0, weight=1)
        self.chart_tab.rowconfigure(1, weight=1)
        controls = ttk.Frame(self.chart_tab, padding=8)
        controls.grid(row=0, column=0, sticky="ew")
        ttk.Label(controls, text="그래프").pack(side="left")
        ttk.Combobox(
            controls,
            textvariable=self.chart_type_var,
            values=("불량 분포", "히스토그램", "품질별 박스플롯", "상관관계(heatmap)"),
            state="readonly",
            width=18,
        ).pack(side="left", padx=6)
        ttk.Label(controls, text="센서").pack(side="left", padx=(12, 0))
        self.sensor_combo = ttk.Combobox(
            controls,
            textvariable=self.sensor_var,
            state="readonly",
            width=28,
        )
        self.sensor_combo.pack(side="left", padx=6)
        ttk.Button(
            controls,
            text="그래프 표시",
            command=lambda: self._run_ui_action(self.render_selected_chart),
        ).pack(side="left", padx=6)
        self.chart_frame = ttk.Frame(self.chart_tab)
        self.chart_frame.grid(row=1, column=0, sticky="nsew")

    def _build_model_tab(self) -> None:
        # 준지도 학습 파이프라인(GaussianNB/RandomForest/SVM, ML/evaluation.py)을
        # 5-fold 교차검증으로 실행한다. 라벨 있는 불량 표본이 매우 적어서
        # (CN7 17건, RG3 25건) 단일 train/test 분리 대신 교차검증 평균을 쓴다.
        # 자세한 배경은 scripts/run_semi_supervised.py 참고.
        self.model_tab.columnconfigure(0, weight=1)
        self.model_tab.columnconfigure(1, weight=1)
        self.model_tab.rowconfigure(1, weight=1)

        controls = ttk.Frame(self.model_tab, padding=8)
        controls.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(controls, text="제품").pack(side="left")
        ttk.Combobox(
            controls,
            textvariable=self.model_product_var,
            values=("cn7", "rg3"),
            state="readonly",
            width=8,
        ).pack(side="left", padx=(4, 12))
        ttk.Checkbutton(
            controls,
            text="pseudo-labeling 사용 (가이드북 방식, 느림)",
            variable=self.pseudo_label_var,
        ).pack(side="left", padx=(0, 12))
        ttk.Button(
            controls,
            text="5-fold 교차검증 실행",
            command=lambda: self._run_ui_action(self.run_model_evaluation),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            controls,
            text="비교 그래프 표시",
            command=lambda: self._run_ui_action(self.render_model_chart),
        ).pack(side="left", padx=6)

        text_frame = ttk.Frame(self.model_tab)
        text_frame.grid(row=1, column=0, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        self.model_text = tk.Text(text_frame, wrap="none", font=("Consolas", 10))
        self.model_text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(
            text_frame, orient="vertical", command=self.model_text.yview
        )
        scroll.grid(row=0, column=1, sticky="ns")
        self.model_text.configure(yscrollcommand=scroll.set)

        self.model_chart_frame = ttk.Frame(self.model_tab)
        self.model_chart_frame.grid(row=1, column=1, sticky="nsew")

    def browse_file(self) -> None:
        selected = filedialog.askopenfilename(
            title="제조 데이터 CSV 선택",
            filetypes=(("CSV 파일", "*.csv"), ("모든 파일", "*.*")),
        )
        if selected:
            self.file_path_var.set(selected)

    def load_data(self, file_path: str | Path | None = None) -> pd.DataFrame:
        path = Path(file_path or self.file_path_var.get())
        if not path.exists():
            raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {path}")
        loaded = self.loader.load_csv(path)
        if self.cn7_rg3_only_var.get():
            mask = loaded["PART_NAME"].astype(str).str.startswith(("CN7", "RG3"))
            loaded = loaded.loc[mask].copy()
        loaded["product_family"] = loaded["PART_NAME"].str.extract(r"^(CN7|RG3)")
        loaded["part_side"] = loaded["PART_NAME"].str.extract(r"\b(LH|RH)\b")
        self.raw_df = loaded
        self.clean_df = None
        self.file_path_var.set(str(path))
        self._update_preview(loaded)
        self._update_sensor_columns(loaded)
        self.status_var.set(f"로드 완료: {len(loaded):,}행 × {len(loaded.columns):,}열")
        return loaded

    def preprocess_data(self) -> pd.DataFrame:
        if self.raw_df is None:
            raise RuntimeError("먼저 CSV 데이터를 불러오세요.")
        processor = Preprocessor(self.raw_df)
        before_rows = len(processor.df)
        processor.remove_duplicates() # 컬럼이 모두 중복되는 행 제거
        duplicate_count = before_rows - len(processor.df)
        processor.convert_datetime("TimeStamp") # TimeStamp 컬럼의 Type 을 문자열에서 날짜·시간 자료형으로 변환
        processor.fill_missing() # 결측치를 중앙값으로, 현재 데이터셋에는 결측치가 없어서 아무 일도 안일어남
        processor.encode_target() # 머신러닝을 수행하도록 숫자로 변경
        # 모든 값이 동일한 수치형 컬럼을 제거
        removed_constants = processor.remove_constant_numeric_columns(
            exclude={"target", "PART_FACT_SERIAL"}
        )
        self.clean_df = processor.get_data()
        self.analyzer = DataAnalyzer(self.clean_df)
        self.visualizer = DataVisualizer(self.clean_df)
        self._update_preview(self.clean_df)
        self._update_sensor_columns(self.clean_df)
        self.status_var.set(
            f"전처리 완료: 중복 {duplicate_count:,}행 제거, "
            f"상수 센서 {len(removed_constants)}개 제거"
        )
        return self.clean_df

    def run_analysis(self) -> str:
        """전처리 데이터 집계값으로 분석 대시보드를 갱신한다."""
        data = self._analysis_data()
        self.status_var.set("분석 대시보드를 생성하고 있습니다...")
        self.analyzer = DataAnalyzer(data)
        product_distribution = self.analyzer.get_product_distribution()
        quality_distribution = self.analyzer.get_quality_distribution()
        numeric_summary = self.analyzer.get_numeric_mean_summary()
        fault_distribution = self.analyzer.get_fault_reason_distribution()

        total_count = len(data)
        cn7_count = int(product_distribution.loc["CN7", "count"])
        cn7_percentage = float(product_distribution.loc["CN7", "percentage"])
        rg3_count = int(product_distribution.loc["RG3", "count"])
        rg3_percentage = float(product_distribution.loc["RG3", "percentage"])
        defect_count = int(quality_distribution.loc["불량", "count"])
        defect_percentage = float(
            quality_distribution.loc["불량", "percentage"]
        )

        kpi_values = {
            "total": (f"{total_count:,}건", f"{data.shape[1]:,}개 컬럼"),
            "cn7": (f"{cn7_percentage:.2f}%", f"{cn7_count:,}건"),
            "rg3": (f"{rg3_percentage:.2f}%", f"{rg3_count:,}건"),
            "defect": (
                f"{defect_percentage:.2f}%",
                f"불량 {defect_count:,}건",
            ),
        }
        for key, (value, detail) in kpi_values.items():
            value_var, detail_var = self.dashboard_kpi_vars[key]
            value_var.set(value)
            detail_var.set(detail)

        self.visualizer = DataVisualizer(data)
        dashboard_figure = self.visualizer.plot_dashboard(
            product_distribution=product_distribution,
            quality_distribution=quality_distribution,
            numeric_summary=numeric_summary,
            fault_distribution=fault_distribution,
        )
        self._show_figure(
            dashboard_figure,
            self.dashboard_chart_frame,
            "analysis_chart_canvas",
        )

        report = "\n".join(
            [
                "[제품 비율]",
                product_distribution.to_string(
                    float_format=lambda value: f"{value:.2f}"
                ),
                "",
                "[양품/불량 비율]",
                quality_distribution.to_string(
                    float_format=lambda value: f"{value:.2f}"
                ),
                "",
                "[수치 지표 평균]",
                numeric_summary.to_string(
                    float_format=lambda value: f"{value:.2f}"
                ),
                "",
                "[고장 원인]",
                fault_distribution.to_string(
                    float_format=lambda value: f"{value:.2f}"
                ),
            ]
        )
        self.notebook.select(self.analysis_tab)
        self.status_var.set(
            f"대시보드 분석 완료: {total_count:,}건 · 불량률 "
            f"{defect_percentage:.2f}%"
        )
        return report

    def render_selected_chart(self):
        data = self._analysis_data()
        self.visualizer = DataVisualizer(data)
        chart_type = self.chart_type_var.get()
        sensor = self.sensor_var.get()
        if chart_type == "불량 분포":
            figure = self.visualizer.plot_class_distribution("PassOrFail")
        elif chart_type == "히스토그램":
            figure = self.visualizer.plot_histogram(sensor)
        elif chart_type == "품질별 박스플롯":
            figure = self.visualizer.plot_boxplot(sensor, "PassOrFail")
        elif chart_type == "상관관계(heatmap)":
            figure = self.visualizer.plot_correlation_heatmap()
        else:
            raise ValueError(f"지원하지 않는 그래프입니다: {chart_type}")
        self._show_figure(figure, self.chart_frame, "chart_canvas")
        self.notebook.select(self.chart_tab)
        self.status_var.set(f"시각화 완료: {chart_type}")
        return figure

    def run_model_evaluation(self) -> pd.DataFrame:
        product = self.model_product_var.get()
        use_pseudo_labeling = self.pseudo_label_var.get()
        self.status_var.set(f"{product.upper()} 교차검증 실행 중...")
        self.root.update_idletasks()

        data = load_raw_product_data(product)
        factories = build_model_factories()

        rows = {}
        results: dict[str, CVResult] = {}
        for name, factory in factories.items():
            result = cross_validate(
                factory,
                data.X_labeled,
                data.y_labeled,
                X_unlabeled=data.X_unlabeled if use_pseudo_labeling else None,
                use_pseudo_labeling=use_pseudo_labeling,
            )
            results[name] = result
            rows[name] = result.summary()

        comparison = pd.DataFrame(rows).T.sort_values("f1", ascending=False)
        self.cv_comparison = comparison
        self.cv_results = results

        confusion_lines = [
            f"[{name} 합산 혼동행렬 (5-fold)]\n{result.pooled_confusion_matrix()}"
            for name, result in results.items()
        ]
        report = "\n\n".join(
            [
                f"[{product.upper()} 라벨 데이터] {len(data.X_labeled):,}건 "
                f"(불량 {int(data.y_labeled.sum())}건, {data.y_labeled.mean():.2%})",
                f"[결과 비교 (5-fold 교차검증 평균, F1 기준 정렬)]\n"
                + comparison.to_string(float_format=lambda value: f"{value:.4f}"),
                *confusion_lines,
            ]
        )
        self._set_text(self.model_text, report)
        self.notebook.select(self.model_tab)
        best_name = comparison.index[0]
        self.status_var.set(
            f"{product.upper()} 교차검증 완료: 최고 모델 {best_name} "
            f"(F1={comparison.loc[best_name, 'f1']:.3f})"
        )
        return comparison

    def render_model_chart(self):
        if self.cv_comparison is None:
            raise RuntimeError("먼저 교차검증을 실행하세요.")
        figure, axis = plt.subplots(figsize=(6, 4.5))
        self.cv_comparison[["precision", "recall", "f1", "roc_auc"]].plot(
            kind="bar", ax=axis
        )
        axis.set_title(f"{self.model_product_var.get().upper()} 모델별 성능 비교")
        axis.set_ylabel("점수")
        axis.set_ylim(0, 1)
        axis.tick_params(axis="x", rotation=0)
        axis.legend(loc="upper right", fontsize=8)
        figure.tight_layout()
        self._show_figure(figure, self.model_chart_frame, "model_chart_canvas")
        self.status_var.set("모델 비교 그래프 표시")
        return figure

    def _analysis_data(self) -> pd.DataFrame:
        if self.clean_df is not None:
            return self.clean_df
        if self.raw_df is None:
            raise RuntimeError("먼저 데이터를 불러오고 전처리하세요.")
        temporary = self.raw_df.copy()
        temporary["target"] = temporary["PassOrFail"].map({"Y": 0, "N": 1})
        return temporary

    def _update_preview(self, df: pd.DataFrame) -> None:
        self.preview_tree.delete(*self.preview_tree.get_children())
        columns = list(df.columns)
        self.preview_tree.configure(columns=columns)
        for column in columns:
            self.preview_tree.heading(column, text=column)
            self.preview_tree.column(column, width=125, minwidth=80, stretch=False)
        for position, (_, row) in enumerate(df.head(self.PREVIEW_ROWS).iterrows()):
            values = [self._display_value(row[column]) for column in columns]
            self.preview_tree.insert("", "end", iid=str(position), values=values)

    def _update_sensor_columns(self, df: pd.DataFrame) -> None:
        numeric_columns = [
            column
            for column in df.select_dtypes(include="number").columns
            if column not in {"PART_FACT_SERIAL", "target"}
        ]
        self.sensor_combo.configure(values=numeric_columns)
        if numeric_columns and self.sensor_var.get() not in numeric_columns:
            self.sensor_var.set(numeric_columns[0])

    def _show_figure(self, figure, frame: ttk.Frame, canvas_attr: str) -> None:
        existing_canvas = getattr(self, canvas_attr)
        if existing_canvas is not None:
            existing_canvas.get_tk_widget().destroy()
        canvas = FigureCanvasTkAgg(figure, master=frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        setattr(self, canvas_attr, canvas)

    @staticmethod
    def _set_text(widget: tk.Text, content: str) -> None:
        widget.delete("1.0", "end")
        widget.insert("1.0", content)

    def _run_ui_action(self, action) -> None:
        try:
            action()
        except Exception as error:
            self.status_var.set(f"오류: {error}")
            messagebox.showerror("작업 오류", str(error), parent=self.root)

    @staticmethod
    def _display_value(value):
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.2f}"
        return value
