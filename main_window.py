"""사출성형 제조 데이터 분석용 Tkinter 메인 화면."""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from data_analyzer import DataAnalyzer
from data_loader import DataLoader
from data_visualizer import DataVisualizer

# from model_manager import ModelManager
# from predictor import Predictor
from preprocessor import Preprocessor


DEFAULT_DATA_PATH = (
    Path(__file__).resolve().parent
    / "04. Dataset_Molding"
    / "dataset"
    / "labeled_data.csv"
)


class MainWindow:
    """데이터 로드부터 예측까지 각 클래스를 연결"""

    PREVIEW_ROWS = 100

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
        # 모델링 상태값은 구현 시 활성화
        # self.model_manager: ModelManager | None = None
        # self.predictor: Predictor | None = None
        # self.model_features: list[str] = []
        self.chart_canvas: FigureCanvasTkAgg | None = None

        self.file_path_var = tk.StringVar(value=str(DEFAULT_DATA_PATH))
        self.cn7_rg3_only_var = tk.BooleanVar(value=True)
        self.chart_type_var = tk.StringVar(value="불량 분포")
        self.sensor_var = tk.StringVar(value="Injection_Time")
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
            # ("4. 모델 학습", self.train_model),  # 구현 예정
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
        # self.model_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.preview_tab, text="데이터 미리보기")
        self.notebook.add(self.analysis_tab, text="분석 결과")
        self.notebook.add(self.chart_tab, text="시각화")
        # self.notebook.add(self.model_tab, text="모델 및 예측")

        self._build_preview_tab()
        self._build_analysis_tab()
        self._build_chart_tab()
        # self._build_model_tab()
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
        self.analysis_tab.rowconfigure(0, weight=1)
        self.analysis_text = tk.Text(
            self.analysis_tab, wrap="none", font=("Consolas", 10)
        )
        self.analysis_text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(
            self.analysis_tab,
            orient="vertical",
            command=self.analysis_text.yview,
        )
        scroll.grid(row=0, column=1, sticky="ns")
        self.analysis_text.configure(yscrollcommand=scroll.set)

    def _build_chart_tab(self) -> None:
        self.chart_tab.columnconfigure(0, weight=1)
        self.chart_tab.rowconfigure(1, weight=1)
        controls = ttk.Frame(self.chart_tab, padding=8)
        controls.grid(row=0, column=0, sticky="ew")
        ttk.Label(controls, text="그래프").pack(side="left")
        ttk.Combobox(
            controls,
            textvariable=self.chart_type_var,
            values=("불량 분포", "히스토그램", "품질별 박스플롯", "상관관계"),
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
        processor.remove_duplicates()
        duplicate_count = before_rows - len(processor.df)
        processor.convert_datetime("TimeStamp")
        processor.fill_missing()
        processor.encode_target()
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
        data = self._analysis_data()
        self.analyzer = DataAnalyzer(data)
        target_distribution = self.analyzer.get_class_distribution("PassOrFail")
        missing = self.analyzer.get_missing_summary().query("missing_count > 0")
        product_defect = self.analyzer.get_group_summary(
            "PART_NAME", "target", ("count", "sum", "mean")
        )
        product_defect.columns = ["생산수", "불량수", "불량률"]
        report = "\n".join(
            [
                "[데이터 크기]",
                str(data.shape),
                "",
                "[양품/불량 분포]",
                target_distribution.to_string(),
                "",
                "[제품별 불량 현황]",
                product_defect.to_string(float_format=lambda value: f"{value:.4f}"),
                "",
                "[결측치가 있는 컬럼]",
                missing.to_string() if not missing.empty else "없음",
            ]
        )
        self._set_text(self.analysis_text, report)
        self.notebook.select(self.analysis_tab)
        self.status_var.set("기초 분석 완료")
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
        elif chart_type == "상관관계":
            figure = self.visualizer.plot_correlation_heatmap()
        else:
            raise ValueError(f"지원하지 않는 그래프입니다: {chart_type}")
        self._show_figure(figure)
        self.notebook.select(self.chart_tab)
        self.status_var.set(f"시각화 완료: {chart_type}")
        return figure

#----- AI 모델 구현해야함

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

    def _show_figure(self, figure) -> None:
        if self.chart_canvas is not None:
            self.chart_canvas.get_tk_widget().destroy()
        self.chart_canvas = FigureCanvasTkAgg(figure, master=self.chart_frame)
        self.chart_canvas.draw()
        self.chart_canvas.get_tk_widget().pack(fill="both", expand=True)

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
