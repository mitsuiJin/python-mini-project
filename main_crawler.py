"""고장 원인 동적 웹 조사가 포함된 제조 데이터 분석 UI 실행 파일."""

import tkinter as tk

from crawler_window import CrawlerMainWindow


def main() -> None:
    root = tk.Tk()
    CrawlerMainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
