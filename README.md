## 프로젝트 제목



## 데이터 분석 프로젝트 아키텍처

```mermaid
graph LR

    A[CSV] --> B[DataLoader]
    B --> C[DataFrame]

    C --> D[Preprocessor]
    D --> E[Clean DataFrame]

    E --> F[DataAnalyzer]
    E --> G[DataVisualizer]
    E --> H[ModelManager]

    F --> I[통계 분석 결과]
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

## 분석할 데이터
labeled_data.csv

## 해야하는 것
