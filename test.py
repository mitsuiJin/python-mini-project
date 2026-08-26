import tkinter as tk
from tkinter import messagebox
import threading
import webbrowser

import requests
from bs4 import BeautifulSoup

global status_label


# ==================================================
# 크롤링 사이트 URL
# ==================================================

SHORT_SHOT_URL = (
    "https://help.autodesk.com/cloudhelp/2021/ENU/"
    "MoldflowInsight-CLC-Troubleshoot/files/"
    "Troubleshooting-molding-problems/"
    "MoldflowInsight_CLC_Troubleshoot_"
    "Troubleshooting_molding_problems_"
    "Troubleshooting_short_shot_html.html"
)

BURN_MARK_URL = (
    "https://help.autodesk.com/cloudhelp/2021/ENU/"
    "MoldflowInsight-CLC-Troubleshoot/files/"
    "Troubleshooting-molding-problems/"
    "MoldflowInsight_CLC_Troubleshoot_"
    "Troubleshooting_molding_problems_"
    "Troubleshooting_burn_marks_html.html"
)

AIR_TRAP_URL = (
    "https://help.autodesk.com/cloudhelp/2017/ENU/"
    "MoldflowComm-UsersGuide/files/"
    "GUID-E81A1CF3-0A91-43DE-8954-005E76897E51.htm"
)


# ==================================================
# 불량 유형별 검색어와 연결 사이트
# ==================================================

DEFECT_DATA = {
    "가스": [
        {
            "query": (
                "injection molding gas defect "
                "air trap causes remedies"
            ),
            "url": (
                "https://help.autodesk.com/cloudhelp/2017/ENU/"
                "MoldflowComm-UsersGuide/files/"
                "GUID-E81A1CF3-0A91-43DE-8954-005E76897E51.htm"
            )
        },
        {
            "query": (
                "injection molding burn marks "
                "trapped air troubleshooting"
            ),
            "url": (
                "https://help.autodesk.com/cloudhelp/2021/ENU/"
                "MoldflowInsight-CLC-Troubleshoot/files/"
                "Troubleshooting-molding-problems/"
                "MoldflowInsight_CLC_Troubleshoot_"
                "Troubleshooting_molding_problems_"
                "Troubleshooting_burn_marks_html.html"
            )
        },
        {
            "query": (
                "injection mold poor venting "
                "gas defect solution"
            ),
            "url": (
                "https://www.injectionmould.org/"
                "2019/03/13/mold-venting/"
            )
        }
    ],

    "미성형": [
        {
            "query": (
                "injection molding short shot "
                "causes remedies"
            ),
            "url": (
                "https://help.autodesk.com/cloudhelp/2021/ENU/"
                "MoldflowInsight-CLC-Troubleshoot/files/"
                "Troubleshooting-molding-problems/"
                "MoldflowInsight_CLC_Troubleshoot_"
                "Troubleshooting_molding_problems_"
                "Troubleshooting_short_shot_html.html"
            )
        },
        {
            "query": (
                "incomplete filling "
                "low injection pressure"
            ),
            "url": (
                "https://www.huarong.com.tw/page/news/"
                "en/company_news/detail/138/"
            )
        },
        {
            "query": (
                "short shot mold temperature "
                "injection speed troubleshooting"
            ),
            "url": (
                "https://www.fictiv.com/articles/"
                "injection-molding-short-shot-defects"
            )
        }
    ],

    "초기허용불량": [
        {
            "query": (
                "injection molding startup scrap "
                "process stabilization"
            ),
            "url": (
                "https://chenhsong.com/ichen-ai-molder/"
            )
        },
        {
            "query": (
                "injection molding startup "
                "mold temperature stabilization"
            ),
            "url": (
                "https://www.mazin.tech/columns/33"
            )
        },
        {
            "query": (
                "injection molding first shot "
                "defects after startup"
            ),
            "url": (
                "https://www.mangoapps.com/templates/"
                "inspections/mold-tooling-pre-run-inspection"
            )
        }
    ]
}


# ==================================================
# 기존 화면 내용 제거
# ==================================================

def clear_screen():
    for widget in content_frame.winfo_children():
        widget.destroy()


# ==================================================
# 첫 화면
# ==================================================

def show_main_screen():
    clear_screen()

    title_label = tk.Label(
        content_frame,
        text="사출성형 불량 분석 시스템",
        font=("Malgun Gothic", 24, "bold"),
        bg="#f4f6f9"
    )
    title_label.pack(pady=(100, 20))

    description_label = tk.Label(
        content_frame,
        text="불량 유형별 기술자료를 조회할 수 있습니다.",
        font=("Malgun Gothic", 12),
        bg="#f4f6f9",
        fg="#666666"
    )
    description_label.pack(pady=10)

    analysis_button = tk.Button(
        content_frame,
        text="오류원인 분석",
        font=("Malgun Gothic", 16, "bold"),
        width=22,
        height=3,
        bg="#34495e",
        fg="white",
        activebackground="#2c3e50",
        command=show_defect_screen
    )
    analysis_button.pack(pady=30)


# ==================================================
# 불량 유형 선택 화면
# ==================================================

def show_defect_screen():
    clear_screen()

    title_label = tk.Label(
        content_frame,
        text="불량 유형 선택",
        font=("Malgun Gothic", 22, "bold"),
        bg="#f4f6f9"
    )
    title_label.pack(pady=(55, 10))

    description_label = tk.Label(
        content_frame,
        text="분석할 불량 유형을 선택해주세요.",
        font=("Malgun Gothic", 12),
        bg="#f4f6f9",
        fg="#666666"
    )
    description_label.pack(pady=(0, 30))

    defect_button_frame = tk.Frame(
        content_frame,
        bg="#f4f6f9"
    )
    defect_button_frame.pack()

    gas_button = tk.Button(
        defect_button_frame,
        text="가스",
        font=("Malgun Gothic", 14, "bold"),
        width=16,
        height=3,
        bg="#e67e22",
        fg="white",
        command=lambda: show_query_screen("가스")
    )
    gas_button.grid(row=0, column=0, padx=10, pady=10)

    short_shot_button = tk.Button(
        defect_button_frame,
        text="미성형",
        font=("Malgun Gothic", 14, "bold"),
        width=16,
        height=3,
        bg="#3498db",
        fg="white",
        command=lambda: show_query_screen("미성형")
    )
    short_shot_button.grid(
        row=0,
        column=1,
        padx=10,
        pady=10
    )

    startup_button = tk.Button(
        defect_button_frame,
        text="초기허용불량",
        font=("Malgun Gothic", 14, "bold"),
        width=16,
        height=3,
        bg="#9b59b6",
        fg="white",
        command=lambda: show_query_screen("초기허용불량")
    )
    startup_button.grid(
        row=0,
        column=2,
        padx=10,
        pady=10
    )

    back_button = tk.Button(
        content_frame,
        text="처음으로",
        font=("Malgun Gothic", 11),
        width=15,
        command=show_main_screen
    )
    back_button.pack(pady=35)


# ==================================================
# 검색어 선택 화면
# ==================================================

def show_query_screen(defect_name):
    global status_label

    clear_screen()

    title_label = tk.Label(
        content_frame,
        text=f"{defect_name} 기술자료 검색",
        font=("Malgun Gothic", 21, "bold"),
        bg="#f4f6f9"
    )
    title_label.pack(pady=(45, 10))

    description_label = tk.Label(
        content_frame,
        text=(
            "검색어를 누르면 사이트 접속 상태를 확인한 후\n"
            "웹브라우저에서 기술자료를 엽니다."
        ),
        font=("Malgun Gothic", 11),
        bg="#f4f6f9",
        fg="#666666"
    )
    description_label.pack(pady=(0, 25))

    queries = DEFECT_DATA[defect_name]

    for number, information in enumerate(
        queries,
        start=1
    ):
        query = information["query"]
        url = information["url"]

        query_button = tk.Button(
            content_frame,
            text=f"{number}. {query}",
            font=("Arial", 11),
            width=70,
            height=3,
            wraplength=650,
            bg="white",
            fg="#222222",
            activebackground="#dfe6e9",
            command=lambda q=query, u=url: check_and_open(q, u)
        )

        query_button.pack(pady=8)

    status_label = tk.Label(
        content_frame,
        text="",
        font=("Malgun Gothic", 11, "bold"),
        bg="#f4f6f9"
    )
    status_label.pack(pady=15)

    back_button = tk.Button(
        content_frame,
        text="불량 유형 선택으로 돌아가기",
        font=("Malgun Gothic", 11),
        width=25,
        command=show_defect_screen
    )
    back_button.pack(pady=10)


# ==================================================
# 사이트 크롤링 확인 후 브라우저 열기
# ==================================================

def check_and_open(query, url):
    # 버튼을 누르면 바로 브라우저로 사이트 열기
    opened = webbrowser.open_new_tab(url)

    if opened:
        status_label.config(
            text="사이트를 열었습니다. 크롤링 상태 확인 중...",
            fg="blue"
        )
    else:
        status_label.config(
            text="브라우저 실행을 확인할 수 없습니다.",
            fg="orange"
        )

    # 사이트를 연 뒤 백그라운드에서 크롤링 확인
    crawling_thread = threading.Thread(
        target=crawl_site_only,
        args=(query, url),
        daemon=True
    )

    crawling_thread.start()


def crawl_site_only(query, url):
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "Chrome/131.0.0.0 Safari/537.36"
            )
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=15
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        # 페이지 제목 추출
        title_tag = soup.select_one("h1")

        if title_tag is not None:
            page_title = title_tag.get_text(
                " ",
                strip=True
            )

        elif soup.title is not None:
            page_title = soup.title.get_text(
                " ",
                strip=True
            )

        else:
            page_title = "제목 없음"

        # 본문 추출
        paragraphs = []

        for tag in soup.select("p, li"):
            text = tag.get_text(" ", strip=True)

            if len(text) >= 15:
                paragraphs.append(text)

        if len(paragraphs) == 0:
            raise ValueError(
                "사이트는 열렸지만 크롤링할 본문을 찾지 못했습니다."
            )

        root.after(
            0,
            crawling_success,
            query,
            url,
            response.status_code,
            page_title,
            len(paragraphs)
        )

    except Exception as error:
        root.after(
            0,
            crawling_failure,
            str(error)
        )

# ==================================================
# 크롤링 성공
# ==================================================

def crawling_success(
    query,
    url,
    status_code,
    page_title,
    paragraph_count
):
    status_label.config(
        text=(
            f"접속 성공 · HTTP {status_code} · "
            f"본문 {paragraph_count}개 확인"
        ),
        fg="green"
    )

    print("\n[크롤링 성공]")
    print("선택 검색어:", query)
    print("페이지 제목:", page_title)
    print("HTTP 상태:", status_code)
    print("수집 문단 수:", paragraph_count)
    print("연결 URL:", url)




# ==================================================
# 크롤링 실패
# ==================================================

def crawling_failure(error_message):
    status_label.config(
        text="크롤링 또는 사이트 접속 실패",
        fg="red"
    )

    messagebox.showerror(
        "사이트 접속 실패",
        error_message
    )


# ==================================================
# 프로그램 실행
# ==================================================

root = tk.Tk()

root.title("사출성형 불량 원인 분석")
root.geometry("1000x650")
root.configure(bg="#f4f6f9")

content_frame = tk.Frame(
    root,
    bg="#f4f6f9"
)

content_frame.pack(
    fill="both",
    expand=True
)

show_main_screen()

root.mainloop()