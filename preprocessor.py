import pandas as pd

class Preprocessor:

    def __init__(self, df):
        self.df = df.copy()

    # 각 컬럼별 결측치의 개수를 계산
    def check_missing(self):
        return self.df.isna().sum()

    # select_dtypes(include="number")로 수치형(정수·실수) 컬럼만 추출 ->
    # 각 수치형 컬럼의 결측치를 평균 대신 중앙값(median)으로 대체합니다.
    def fill_missing(self):
        numeric_cols = self.df.select_dtypes(
            include="number"
        ).columns

        for col in numeric_cols:
            self.df[col] = self.df[col].fillna(
                self.df[col].median()
            )

        return self.df

    # 지정한 컬럼의 데이터를 날짜/시간 타입(datetime64)으로 변환
    def convert_datetime(self, column):
        self.df[column] = pd.to_datetime(
            self.df[column],
            errors="coerce"
        )

        return self.df

    # 분석이나 모델 학습에 불필요한 컬럼 목록을 데이터프레임에서 제거
    def remove_columns(self, columns):
        self.df = self.df.drop(
            columns=columns,
            errors="ignore"
        )

        return self.df
    def remove_duplicates(self):
        """모든 컬럼값이 동일한 완전 중복 행을 제거합니다."""
        self.df = self.df.drop_duplicates().copy()
        return self.df

    def remove_constant_numeric_columns(self, exclude=None):
        """값이 하나뿐인 수치형 센서 컬럼을 제거합니다."""
        exclude = set(exclude or [])
        numeric_cols = self.df.select_dtypes(include="number").columns
        constant_cols = [
            col
            for col in numeric_cols
            if col not in exclude and self.df[col].nunique(dropna=False) <= 1
        ]
        self.df = self.df.drop(columns=constant_cols)
        return constant_cols

    def encode_target(self, source="PassOrFail", target="target"):
        """Y/N 품질 판정을 0/1 머신러닝 타깃으로 변환합니다."""
        if source not in self.df.columns:
            raise KeyError(f"종속변수 컬럼이 없습니다: {source}")
        self.df[target] = self.df[source].map({"Y": 0, "N": 1})
        return self.df

    def get_data(self):
        """현재 전처리 결과의 복사본을 반환합니다."""
        return self.df.copy()
