import pandas as pd

class DataLoader:

    def __init__(self):
        self.df = None

    # csv 파일 -> DataFrame 형태로 저장
    def load_csv(self, file_path):
        self.df = pd.read_csv(file_path)
        return self.df

    # dataFrame 행,열 확인
    def get_shape(self):
        return self.df.shape

    # 모든 컬럼(열) 리스트로 반환
    def get_columns(self):
        return self.df.columns.tolist()

    # 각 컬럼의 데이터 타입 Pandas Series 로 반환
    def get_dtypes(self):
        return self.df.dtypes