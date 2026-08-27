import pandas as pd

class DataLoader:

    def __init__(self):
        self.df = None

    # csv 파일 -> DataFrame 형태로 저장
    def load_csv(self, file_path):
        self.df = pd.read_csv(file_path)
        return self.df