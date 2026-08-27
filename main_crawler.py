"""고장 원인 조사가 포함된 ttkbootstrap 분석 UI 실행 진입점."""

import ttkbootstrap as ttk

from UI.crawler_window import CrawlerMainWindow


def main() -> None:
    root = ttk.Window(themename="united")
    CrawlerMainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()