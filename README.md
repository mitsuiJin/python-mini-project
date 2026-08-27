

## Architecture

```mermaid
graph LR

    A[CSV] --> B[DataLoader]
    B --> C[DataFrame]

    C --> D[Preprocessor]
    D --> E[Clean DataFrame]

    E --> F[DataAnalyzer]
    E --> G[DataVisualizer]
    E --> H[ModelManager]

    F --> I[통계 대시보드]
    G --> J[그래프]

    H --> K[분류/회귀 모델]

    K --> L[Predictor]
    E --> L

    L --> M[불량 예측<br/>품질 수치 예측]

    I --> N[MainWindow]
    J --> N
    M --> N



    P[Dynamic Fault Crawler]
    P --> Q
    Q[CrawlerWindow]
    N --> Q
    %% 클래스 글자색
    classDef pythonClass color:#0066ff;

    %% 클래스 지정
    class B,D,F,G,H,L,N,Q,P pythonClass;
  
```

## Module

- 분석 
  - [DataLoader](Analyze/data_loader.py) : CSV 데이터를 불러오는 모듈
  - [Preprocessor](Analyze/preprocessor.py) : CSV 데이터를 학습하기 위해서 전처리하는 모듈
  - [DataAnalyzer](Analyze/analyzer.py) : 전처리 된 데이터의 주요 지표를 분석하는 모듈
  - [DataVisualizer](Analyze/visualizer.py) : 데이터 값을 시각화 하는 모듈
- 머신 러닝
  - [ModelManager](ML/model_manager.py) : 머신러닝 모델 학습
  - [Predictor](ML/predictor.py) : 학습된 머신러닝 모델 우리 데이터에 적용
- UI
  - [MainWindow](UI/main_window.py) : 크롤링을 포함하지 않는 UI 
  - [CrawlerWindow](UI/crawler_window.py) : 크롤링 포함 UI
- 크롤링
  - [DynamicFaultCrawler](Crawling/dynamic_fault_crawler.py) : 고장 원인을 네이버에 자동으로 검색하고 관련 링크를 제공

## 폴더 구조
```mermaid
graph TD
    Root["📁 Root Project"]
    
    %% Analyze Group
    subgraph Analyze ["📁 Analyze (데이터 분석/처리)"]
        A0["__init__.py"]
        A1["data_analyzer.py"]
        A2["data_loader.py"]
        A3["data_visualizer.py"]
        A4["preprocessor.py"]
    end

    %% Crawling Group
    subgraph Crawling ["📁 Crawling (웹 수집)"]
        C0["__init__.py"]
        C1["dynamic_fault_crawler.py"]
    end

    %% ML Group
    subgraph ML ["📁 ML (머신러닝 파이프라인)"]
        M0["__init__.py"]
        M1["model_manager.py"]
        M2["predictor.py"]
    end

    %% UI Group
    subgraph UI ["📁 UI (사용자 인터페이스)"]
        U0["__init__.py"]
        U1["crawler_window.py"]
        U2["main_window.py"]
    end

    Root --> Analyze
    Root --> Crawling
    Root --> ML
    Root --> UI
```

