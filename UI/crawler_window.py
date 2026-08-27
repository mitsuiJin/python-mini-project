"""기존 제조 데이터 분석 화면에 고장 원인 웹 조사 탭을 추가한다."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser

import pandas as pd

from Crawling.dynamic_fault_crawler import CrawlResult, DynamicFaultCrawler
from .main_window import MainWindow


class CrawlerMainWindow(MainWindow):
    """기존 MainWindow 기능을 보존한 크롤링 확장 화면."""

    def __init__(self, root: tk.Tk):
        self.crawl_results: list[CrawlResult] = []
        self.crawl_queue: queue.Queue = queue.Queue()
        self.crawl_thread: threading.Thread | None = None
        self.fault_reasons: list[str] = []
        super().__init__(root)

        self.fault_reason_var = tk.StringVar(value="")
        self.crawl_query_var = tk.StringVar(value="")
        self.crawl_limit_var = tk.IntVar(value=5)
        self.crawl_headless_var = tk.BooleanVar(value=True)
        self.crawler_tab = ttk.Frame(self.notebook)
        self.notebook.insert(2, self.crawler_tab, text="고장 원인 조사")
        self._build_crawler_tab()

    def load_data(self, file_path=None) -> pd.DataFrame:
        loaded = super().load_data(file_path)
        self._update_fault_reasons(loaded)
        return loaded

    def _build_crawler_tab(self) -> None:
        self.crawler_tab.columnconfigure(1, weight=1)
        self.crawler_tab.rowconfigure(0, weight=1)

        reason_frame = ttk.LabelFrame(
            self.crawler_tab, text="1. 데이터의 고장 원인", padding=8
        )
        reason_frame.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        reason_frame.rowconfigure(1, weight=1)
        ttk.Label(
            reason_frame,
            text="CSV를 로드한 뒤 원인 하나를 선택하세요.",
            wraplength=230,
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.fault_reason_list = tk.Listbox(
            reason_frame, width=30, exportselection=False, activestyle="dotbox"
        )
        reason_scroll = ttk.Scrollbar(
            reason_frame, orient="vertical", command=self.fault_reason_list.yview
        )
        self.fault_reason_list.configure(yscrollcommand=reason_scroll.set)
        self.fault_reason_list.grid(row=1, column=0, sticky="nsew")
        reason_scroll.grid(row=1, column=1, sticky="ns")
        self.fault_reason_list.bind("<<ListboxSelect>>", self._on_fault_reason_selected)

        content = ttk.Frame(self.crawler_tab, padding=(4, 8, 8, 8))
        content.grid(row=0, column=1, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(1, weight=2)
        content.rowconfigure(2, weight=3)

        controls = ttk.LabelFrame(content, text="2. 동적 웹 크롤링", padding=8)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        controls.columnconfigure(1, weight=1)
        ttk.Label(controls, text="선택 원인").grid(row=0, column=0, sticky="w")
        ttk.Label(controls, textvariable=self.fault_reason_var).grid(
            row=0, column=1, sticky="w", padx=6
        )
        ttk.Label(controls, text="검색어").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(controls, textvariable=self.crawl_query_var).grid(
            row=1, column=1, sticky="ew", padx=6, pady=(6, 0)
        )
        ttk.Label(controls, text="문서 수").grid(row=1, column=2, pady=(6, 0))
        ttk.Spinbox(
            controls, from_=1, to=10, textvariable=self.crawl_limit_var, width=5
        ).grid(row=1, column=3, padx=6, pady=(6, 0))
        ttk.Checkbutton(
            controls, text="브라우저 숨김", variable=self.crawl_headless_var
        ).grid(row=1, column=4, padx=6, pady=(6, 0))
        self.crawl_button = ttk.Button(
            controls, text="3. 선택 원인 크롤링", command=self.start_fault_crawl
        )
        self.crawl_button.grid(row=1, column=5, padx=(6, 0), pady=(6, 0))

        result_frame = ttk.LabelFrame(content, text="검색 결과", padding=6)
        result_frame.grid(row=1, column=0, sticky="nsew")
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        self.crawl_result_tree = ttk.Treeview(
            result_frame,
            columns=("title", "url"),
            show="headings",
            selectmode="browse",
        )
        self.crawl_result_tree.heading("title", text="문서 제목")
        self.crawl_result_tree.heading("url", text="출처 URL")
        self.crawl_result_tree.column("title", width=360)
        self.crawl_result_tree.column("url", width=520)
        result_scroll = ttk.Scrollbar(
            result_frame, orient="vertical", command=self.crawl_result_tree.yview
        )
        self.crawl_result_tree.configure(yscrollcommand=result_scroll.set)
        self.crawl_result_tree.grid(row=0, column=0, sticky="nsew")
        result_scroll.grid(row=0, column=1, sticky="ns")
        self.crawl_result_tree.bind("<<TreeviewSelect>>", self._show_crawl_content)
        self.crawl_result_tree.bind("<Double-1>", self.open_selected_crawl_url)

        preview_frame = ttk.LabelFrame(content, text="수집 본문 미리보기", padding=6)
        preview_frame.grid(row=2, column=0, sticky="nsew", pady=(6, 0))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        self.crawl_content_text = tk.Text(preview_frame, wrap="word", height=12)
        content_scroll = ttk.Scrollbar(
            preview_frame, orient="vertical", command=self.crawl_content_text.yview
        )
        self.crawl_content_text.configure(yscrollcommand=content_scroll.set)
        self.crawl_content_text.grid(row=0, column=0, sticky="nsew")
        content_scroll.grid(row=0, column=1, sticky="ns")
        ttk.Button(
            preview_frame,
            text="선택 문서 웹에서 열기",
            command=self.open_selected_crawl_url,
        ).grid(row=1, column=0, sticky="e", pady=(6, 0))

    def _update_fault_reasons(self, df: pd.DataFrame) -> None:
        self.fault_reason_list.delete(0, "end")
        self.fault_reasons = []
        if "Reason" not in df.columns:
            return
        reasons = df["Reason"].dropna().astype(str).str.strip()
        counts = reasons[reasons.ne("")].value_counts()
        for reason, count in counts.items():
            self.fault_reasons.append(reason)
            self.fault_reason_list.insert("end", f"{reason} ({count:,}건)")
        if self.fault_reasons:
            self.fault_reason_list.selection_set(0)
            self._select_fault_reason(0)

    def _on_fault_reason_selected(self, _event=None) -> None:
        selection = self.fault_reason_list.curselection()
        if selection:
            self._select_fault_reason(selection[0])

    def _select_fault_reason(self, index: int) -> None:
        reason = self.fault_reasons[index]
        self.fault_reason_var.set(reason)
        self.crawl_query_var.set(f"사출성형 {reason} 불량 원인 해결 방법")

    def start_fault_crawl(self) -> None:
        if self.crawl_thread is not None and self.crawl_thread.is_alive():
            messagebox.showinfo("크롤링 진행 중", "현재 웹 자료를 수집하고 있습니다.")
            return
        if not self.fault_reason_var.get():
            self._show_crawl_error("CSV를 로드하고 고장 원인을 선택하세요.")
            return
        query_text = self.crawl_query_var.get().strip()
        if not query_text:
            self._show_crawl_error("검색어를 입력하세요.")
            return
        try:
            max_pages = int(self.crawl_limit_var.get())
            if not 1 <= max_pages <= 10:
                raise ValueError
        except (TypeError, ValueError):
            self._show_crawl_error("문서 수는 1~10 사이의 숫자여야 합니다.")
            return

        self.crawl_button.configure(state="disabled")
        self.status_var.set("동적 웹 크롤링을 시작합니다...")
        self.notebook.select(self.crawler_tab)
        self.crawl_thread = threading.Thread(
            target=self._crawl_worker,
            args=(query_text, max_pages, self.crawl_headless_var.get()),
            daemon=True,
        )
        self.crawl_thread.start()
        self.root.after(100, self._poll_crawl_queue)

    def _crawl_worker(self, query_text: str, max_pages: int, headless: bool) -> None:
        try:
            crawler = DynamicFaultCrawler(headless=headless)
            results = crawler.crawl(
                query=query_text,
                max_pages=max_pages,
                progress=lambda message: self.crawl_queue.put(("progress", message)),
            )
            self.crawl_queue.put(("done", results))
        except Exception as error:
            self.crawl_queue.put(("error", error))

    def _poll_crawl_queue(self) -> None:
        try:
            event, payload = self.crawl_queue.get_nowait()
        except queue.Empty:
            if self.crawl_thread is not None and self.crawl_thread.is_alive():
                self.root.after(100, self._poll_crawl_queue)
            return

        if event == "progress":
            self.status_var.set(str(payload))
            self.root.after(100, self._poll_crawl_queue)
        elif event == "done":
            self._display_crawl_results(payload)
            self.crawl_button.configure(state="normal")
            self.status_var.set(f"웹 자료 수집 완료: {len(payload)}건")
        elif event == "error":
            self.crawl_button.configure(state="normal")
            self._show_crawl_error(str(payload))

    def _display_crawl_results(self, results: list[CrawlResult]) -> None:
        self.crawl_results = results
        self.crawl_result_tree.delete(*self.crawl_result_tree.get_children())
        self._set_text(self.crawl_content_text, "")
        for index, result in enumerate(results):
            self.crawl_result_tree.insert(
                "", "end", iid=str(index), values=(result.title, result.url)
            )
        if results:
            self.crawl_result_tree.selection_set("0")
            self.crawl_result_tree.focus("0")
            self._show_crawl_content()
        else:
            self._set_text(
                self.crawl_content_text,
                "수집된 공개 문서가 없습니다. 검색어를 바꾸거나 잠시 후 다시 시도하세요.",
            )

    def _show_crawl_content(self, _event=None) -> None:
        selection = self.crawl_result_tree.selection()
        if not selection:
            return
        result = self.crawl_results[int(selection[0])]
        self._set_text(
            self.crawl_content_text,
            f"제목: {result.title}\n출처: {result.url}\n\n{result.content}",
        )

    def open_selected_crawl_url(self, _event=None) -> None:
        selection = self.crawl_result_tree.selection()
        if not selection:
            messagebox.showinfo("문서 선택", "먼저 검색 결과를 선택하세요.")
            return
        webbrowser.open(self.crawl_results[int(selection[0])].url)

    def _show_crawl_error(self, message: str) -> None:
        self.status_var.set(f"크롤링 오류: {message}")
        messagebox.showerror("크롤링 오류", message, parent=self.root)
