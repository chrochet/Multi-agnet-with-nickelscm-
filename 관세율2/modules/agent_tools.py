import pandas as pd

class CustomsTools:

    def __init__(self, df):
        self.df = df

    def search_tariff(self, country=None, item=None):
        df = self.df

        if country:
            df = df[df["country"].str.contains(country, case=False)]

        if item:
            df = df[df["desc"].str.contains(item, case=False)]

        return df.head(10).to_dict(orient="records")

    def compare_tariff(self, c1, c2, item):
        t1 = self.search_tariff(c1, item)
        t2 = self.search_tariff(c2, item)
        return {"country1": t1, "country2": t2}

    def find_hs_code(self, keyword):
        df = self.df[self.df["desc"].str.contains(keyword, case=False)]
        return df[["hs_code", "desc"]].head(5).to_dict(orient="records")

    def calculate_customs(self, price, rate):
        return {"final_price": price * (1 + rate/100)}
