## 🛠️ 기술 스택

### Programming Language

| 기술 | 사용 목적 |
|---|---|
| Python | 데이터 처리, 시각화, 머신러닝, 웹 크롤링 및 데스크톱 UI 구현 |

---

### Desktop UI

| 기술 | 사용 목적 |
|---|---|
| Tkinter | 데스크톱 프로그램의 기본 UI 구성 |
| ttkbootstrap | Tkinter 위젯의 테마와 디자인 개선 |
| ttk.Notebook | 데이터 미리보기, 분석, 시각화, 모델, 크롤링 탭 구성 |
| ttk.Treeview | DataFrame과 크롤링 결과를 표 형태로 표시 |
| Matplotlib TkAgg | Matplotlib 그래프를 Tkinter 화면에 삽입 |
| Threading | 크롤링 중 UI가 멈추지 않도록 백그라운드 작업 수행 |
| Queue | 크롤링 Thread와 Tkinter 메인 Thread 사이의 데이터 전달 |

---

### Data Analysis

| 기술 | 사용 목적 |
|---|---|
| Pandas | CSV 로드, DataFrame 처리, 전처리 및 통계 분석 |
| NumPy | 수치 연산, 배열 처리 및 혼동행렬 계산 |
| Datetime 처리 | 제조 데이터의 `TimeStamp` 컬럼 변환 |
| GroupBy / Value Counts | 제품, 품질, 고장 원인별 집계 |
| 기술통계 | 평균, 결측치 수, 유효 데이터 수 계산 |

### 주요 전처리 기능

- CN7·RG3 제품 데이터 필터링
- 완전 중복 행 제거
- 날짜·시간 타입 변환
- 수치형 결측치 중앙값 대체
- 상수 수치형 컬럼 제거
- `PassOrFail` 품질 데이터를 `target` 0/1로 인코딩
- 수치 컬럼을 Time, 속도, 압력, 위치 등의 특성으로 분류

---

### Data Visualization

| 기술 | 사용 목적 |
|---|---|
| Matplotlib | 데이터 분석 그래프와 대시보드 생성 |
| Histogram | 제조 수치 컬럼의 분포 확인 |
| Box Plot | 양품·불량 그룹의 분포와 이상치 비교 |
| Correlation Heatmap | 수치 컬럼 사이의 상관관계 확인 |
| Pie Chart | CN7·RG3 데이터 비율 표시 |
| Donut Chart | 양품·불량 비율과 불량률 표시 |
| Bar Chart | 특성별 평균 및 고장 원인별 불량 건수 표시 |
| Confusion Matrix | 머신러닝 모델의 분류 결과 평가 |

---

### Machine Learning

| 기술 | 사용 목적 |
|---|---|
| Scikit-learn | 제조 데이터 불량 분류 모델 구현 |
| Gaussian Naive Bayes | 확률 기반 양품·불량 분류 |
| Random Forest | 다수의 의사결정나무를 이용한 불량 분류 |
| Support Vector Machine | 클래스 경계를 이용한 불량 분류 |
| StandardScaler | 각 Fold의 학습 데이터 기준 수치 표준화 |
| StratifiedKFold | 클래스 비율을 유지하는 5-fold 교차검증 |
| GridSearchCV | SVM과 Random Forest 하이퍼파라미터 탐색 |
| Pseudo-labeling | 라벨이 없는 데이터에 임시 라벨을 부여하는 준지도학습 |

### 모델 평가 지표

- Accuracy
- Precision
- Recall
- F1-score
- ROC-AUC
- Confusion Matrix

> 현재 UI의 `모델 학습` 기능은 모델별 5-fold 교차검증과 성능 비교를 수행합니다.

---

### Web Crawling

| 기술 | 사용 목적 |
|---|---|
| Selenium | JavaScript가 포함된 동적 웹페이지 렌더링 |
| Chrome WebDriver | Chrome 브라우저 자동 제어 |
| WebDriverWait | 검색 결과와 본문 요소가 나타날 때까지 대기 |
| BeautifulSoup4 | 렌더링된 HTML에서 제목, 링크, 본문 추출 |
| urllib.parse | 검색어 URL 인코딩과 URL 구조 분석 |
| Regular Expression | 한글 비율, 문자열 및 문서 관련성 검사 |
| Naver Web Search | 사출성형 고장 원인 관련 문서 검색 |
| webbrowser | 선택한 수집 문서를 기본 브라우저에서 열기 |

### 크롤링 문서 필터

- 한국어 문서 여부
- 제목의 사출성형 관련성
- 선택한 고장 원인 포함 여부
- 제조업 관련 본문 여부
- 중복 URL 여부
- 네이버 내부 페이지 및 잘못된 URL 제외

---

### Architecture

프로젝트는 기능별 클래스를 분리한 모듈형 구조를 사용합니다.

```mermaid
flowchart LR
    UI[MainWindow] --> Loader[DataLoader]
    Loader --> Preprocessor
    Preprocessor --> Analyzer[DataAnalyzer]
    Analyzer --> Visualizer[DataVisualizer]
    UI --> ML[Machine Learning]
    CrawlerUI[CrawlerMainWindow] --> UI
    CrawlerUI --> Crawler[DynamicFaultCrawler]