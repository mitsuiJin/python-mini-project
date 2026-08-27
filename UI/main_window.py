"""사출성형 제조 데이터 분석용 Tkinter 메인 화면."""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from Analyze.data_analyzer import DataAnalyzer
from Analyze.data_loader import DataLoader
from Analyze.data_visualizer import DataVisualizer
from ML.model_manager import ModelManager
from ML.predictor import Predictor
from Analyze.preprocessor import Preprocessor


DEFAULT_DATA_PATH = (
    Path(__file__).resolve().parent.parent
    / "04. Dataset_Molding"
    / "dataset"
    / "labeled_data.csv"
)

# 준지도학습에 쓰는 라벨 없는 공정 데이터
UNLABELED_DATA_PATH = DEFAULT_DATA_PATH.with_name("unlabeled_data.csv")

# 준지도 self-training 용으로 읽어올 라벨없는 최대 행 수 (속도 절충)
UNLABELED_SAMPLE_ROWS = 20000


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
        self.model_manager: ModelManager | None = None
        self.predictor: Predictor | None = None
        self.chart_canvas: FigureCanvasTkAgg | None = None
        self.model_chart_canvas: FigureCanvasTkAgg | None = None
        self.analysis_chart_canvas: FigureCanvasTkAgg | None = None
        self.dashboard_kpi_vars: dict[str, tuple[tk.StringVar, tk.StringVar]] = {}

        self.file_path_var = tk.StringVar(value=str(DEFAULT_DATA_PATH))
        self.cn7_rg3_only_var = tk.BooleanVar(value=True)
        self.chart_type_var = tk.StringVar(value="불량 분포")
        self.sensor_var = tk.StringVar(value="Injection_Time")
        self.model_chart_type_var = tk.StringVar(value="모델별 성능 비교")
        self.model_select_var = tk.StringVar(value="random_forest")
        self.use_enhancement_var = tk.BooleanVar(value=True)
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
            ("4. 모델 학습", self.train_model),
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
        self.model_tab.columnconfigure(0, weight=1)
        self.model_tab.columnconfigure(1, weight=1)
        self.model_tab.rowconfigure(1, weight=1)

        controls = ttk.Frame(self.model_tab, padding=8)
        controls.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Button(
            controls,
            text="모델 학습 & 비교",
            command=lambda: self._run_ui_action(self.train_model),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            controls,
            text="예측 실행",
            command=lambda: self._run_ui_action(self.run_prediction),
        ).pack(side="left", padx=(0, 12))

        ttk.Checkbutton(
            controls,
            text="향상 기법 적용(DAE·준지도·임계값)",
            variable=self.use_enhancement_var,
        ).pack(side="left", padx=(0, 12))

        ttk.Label(controls, text="그래프").pack(side="left")
        ttk.Combobox(
            controls,
            textvariable=self.model_chart_type_var,
            values=(
                "모델별 성능 비교",
                "기본 vs 향상 비교",
                "혼동행렬",
                "ROC 커브",
                "피처 중요도",
            ),
            state="readonly",
            width=16,
        ).pack(side="left", padx=6)
        ttk.Label(controls, text="모델(피처 중요도용)").pack(side="left", padx=(6, 0))
        self.model_select_combo = ttk.Combobox(
            controls,
            textvariable=self.model_select_var,
            state="readonly",
            width=20,
        )
        self.model_select_combo.pack(side="left", padx=6)
        ttk.Button(
            controls,
            text="그래프 표시",
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

    def _load_unlabeled_df(self) -> pd.DataFrame | None:
        """준지도학습용 라벨 없는 공정 데이터를 읽는다. 없으면 None."""
        if not UNLABELED_DATA_PATH.exists():
            return None
        try:
            return pd.read_csv(UNLABELED_DATA_PATH, nrows=UNLABELED_SAMPLE_ROWS)
        except Exception:
            return None

    def train_model(self) -> pd.DataFrame:
        data = self.clean_df if self.clean_df is not None else self.preprocess_data()
        use_enhancement = self.use_enhancement_var.get()

        unlabeled_df = self._load_unlabeled_df() if use_enhancement else None
        self.model_manager = ModelManager(data, unlabeled_df=unlabeled_df)

        self.status_var.set("기본 모델 학습 중...")
        self.root.update_idletasks()
        self.model_manager.train_all()
        comparison = self.model_manager.evaluate_all()
        best_name = comparison.index[0]
        best_metrics = self.model_manager.evaluate(best_name)

        candidate_lines = [
            f"- {name}: {reason}"
            for name, reason in self.model_manager.CANDIDATE_REASONS.items()
        ]
        sections = [
            "[후보 모델과 선택 이유]",
            *candidate_lines,
            "",
            "[기본 모델 성능 비교 (F1 기준 정렬)]",
            comparison.to_string(float_format=lambda value: f"{value:.4f}"),
            "",
            f"[최고 기본 모델 자동 선택] {self.model_manager.selection_reason()}",
            "",
            f"[{best_name} 상세 리포트]",
            best_metrics["report"],
            "[혼동행렬 (행=실제, 열=예측, 0=양품 1=불량)]",
            str(best_metrics["confusion_matrix"]),
        ]

        self.predictor = Predictor(
            self.model_manager.models[best_name], self.model_manager.feature_columns
        )
        selected_name = best_name
        status_tail = f"최고 모델 {best_name} (F1={best_metrics['f1']:.3f})"

        if use_enhancement:
            self.status_var.set(
                "향상 기법(DAE·준지도·임계값 튜닝) 학습 중... 수십 초 걸릴 수 있습니다."
            )
            self.root.update_idletasks()
            self.model_manager.train_all_enhanced()
            enhanced_comparison = self.model_manager.evaluate_all(enhanced=True)
            best_enhanced = enhanced_comparison.index[0]
            enhanced_metrics = self.model_manager.evaluate(best_enhanced, enhanced=True)

            unlabeled_note = (
                f"라벨없는 데이터 {len(unlabeled_df):,}행 사용"
                if unlabeled_df is not None
                else "라벨없는 데이터 파일 없음 → 준지도 단계 생략"
            )
            sections += [
                "",
                "=" * 60,
                self.model_manager.enhancement_report(),
                f"[준지도 입력] {unlabeled_note}",
                "",
                "[예측/평가에 사용할 모델] "
                f"향상 모델 중 F1 최고 → {best_enhanced} "
                f"(F1={enhanced_metrics['f1']:.3f})",
            ]
            self.predictor = self.model_manager.build_enhanced_predictor(best_enhanced)
            selected_name = best_enhanced
            status_tail = (
                f"향상 모델 {best_enhanced} "
                f"(F1 {self.model_manager.evaluate(best_enhanced)['f1']:.3f}"
                f"→{enhanced_metrics['f1']:.3f})"
            )

        self._set_text(self.model_text, "\n".join(sections))
        self.model_select_combo.configure(values=list(self.model_manager.models.keys()))
        self.model_select_var.set(selected_name if selected_name in self.model_manager.models else best_name)
        self.notebook.select(self.model_tab)
        self.status_var.set(f"모델 학습 완료: {status_tail}")
        return comparison

    def render_model_chart(self):
        if self.model_manager is None or not self.model_manager.models:
            raise RuntimeError("먼저 모델을 학습하세요.")
        chart_type = self.model_chart_type_var.get()
        if chart_type == "모델별 성능 비교":
            figure = self.model_manager.plot_model_comparison()
        elif chart_type == "기본 vs 향상 비교":
            if not self.model_manager.enhanced_models:
                raise RuntimeError(
                    "향상 기법 결과가 없습니다. '향상 기법 적용'을 켜고 다시 학습하세요."
                )
            figure = self.model_manager.plot_enhancement_comparison()
        elif chart_type == "혼동행렬":
            figure = self.model_manager.plot_confusion_matrices()
        elif chart_type == "ROC 커브":
            figure = self.model_manager.plot_roc_curves()
        elif chart_type == "피처 중요도":
            figure = self.model_manager.plot_feature_importance(self.model_select_var.get())
        else:
            raise ValueError(f"지원하지 않는 그래프입니다: {chart_type}")
        self._show_figure(figure, self.model_chart_frame, "model_chart_canvas")
        self.status_var.set(f"모델 그래프 표시: {chart_type}")
        return figure

    def run_prediction(self) -> pd.DataFrame:
        if self.predictor is None:
            raise RuntimeError("먼저 모델을 학습하세요.")
        data = self._analysis_data()
        predicted = self.predictor.predict_with_labels(data)
        defect_count = int((predicted["predicted_target"] == 1).sum())
        summary = (
            f"\n[예측 결과] 총 {len(predicted):,}건 중 불량 예측 "
            f"{defect_count:,}건 ({defect_count / len(predicted):.2%})"
        )
        self.model_text.insert("end", summary)
        self._update_preview(predicted)
        self.notebook.select(self.preview_tab)
        self.status_var.set("예측 완료")
        return predicted

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
