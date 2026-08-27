"""ttkbootstrap 제조 데이터 분석 UI 실행 진입점."""

import ttkbootstrap as ttk

from UI.main_window import MainWindow


def main() -> None:
    root = ttk.Window(themename="united")
    MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()