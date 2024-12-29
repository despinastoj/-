import os

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
from locale import setlocale, LC_ALL


class Filter1:
    MARKET_DATA_URL = "https://www.mse.mk/mk/stats/symbolhistory/kmb"

    def __init__(self, csv_file):
        self.csv_file = csv_file

    def execute(self):
        response = requests.get(self.MARKET_DATA_URL)
        response.raise_for_status()
        page_content = response.text

        soup = BeautifulSoup(page_content, 'html.parser')
        dropdown_menu = soup.select_one("select#Code")

        company_codes = []

        if dropdown_menu:
            dropdown_options = dropdown_menu.find_all("option")
            for option in dropdown_options:
                company_code = option.get("value")
                if self.is_valid_company_code(company_code):
                    company_codes.append(company_code)

        self.save_to_csv(company_codes)

        return company_codes

    @staticmethod
    def is_valid_company_code(code):
        return code is not None and code.strip() and code.isalpha()

    def save_to_csv(self, company_codes):
        data = pd.DataFrame({"CompanyCode": company_codes})
        data.to_csv(self.csv_file, index=False)


class Filter2:
    HISTORICAL_DATA_URL = "https://www.mse.mk/mk/stats/symbolhistory/"

    def __init__(self, input_csv):
        self.input_csv = input_csv

    def execute(self):
        issuers = self.read_issuers_from_csv()
        for issuer in issuers:
            self.populate_historical_data(issuer)
            break

    def read_issuers_from_csv(self):
        df = pd.read_csv(self.input_csv)
        return [{"company_code": code, "last_updated": None} for code in df["CompanyCode"]]

    def populate_historical_data(self, issuer):
        current_year = datetime.now().year
        for year in range(current_year, current_year - 10, -1):
            start_date = datetime(year, 1, 1)
            end_date = datetime(year, 12, 31)
            self.fetch_and_save_historical_data(issuer, start_date, end_date)

    def fetch_and_save_historical_data(self, issuer, from_date, to_date):
        payload = {
            "FromDate": from_date.strftime("%Y-%m-%d"),
            "ToDate": to_date.strftime("%Y-%m-%d"),
        }

        response = requests.post(self.HISTORICAL_DATA_URL + issuer["company_code"], data=payload)
        response.raise_for_status()
        document = BeautifulSoup(response.text, 'html.parser')
        results_table = document.select_one("table#resultsTable")

        if results_table:
            self.process_table_rows(results_table.select("tbody tr"), issuer)

    def process_table_rows(self, rows, issuer):
        company_data_list = []

        for row in rows:
            columns = row.select("td")
            if columns:
                high_price = self.parse_number(columns[2].text)
                if high_price is None:
                    continue

                company_data = {
                    "record_date": self.parse_date(columns[0].text, "%d.%m.%Y"),
                    "last_price": self.parse_number(columns[1].text),
                    "high_price": high_price,
                    "low_price": self.parse_number(columns[3].text),
                    "avg_price": self.parse_number(columns[4].text),
                    "percent_change": self.parse_number(columns[5].text),
                    "volume": self.parse_number(columns[6].text, is_integer=True),
                    "turnover_best": self.parse_number(columns[7].text, is_integer=True),
                    "total_turnover": self.parse_number(columns[8].text, is_integer=True),
                }
                company_data_list.append(company_data)

        self.save_to_csv(company_data_list, issuer["company_code"])

    @staticmethod
    def parse_date(date_str, date_format):
        return datetime.strptime(date_str, date_format).date()

    @staticmethod
    def parse_number(number_str, is_integer=False):
        setlocale(LC_ALL, "de_DE")
        try:
            if is_integer:
                return int(number_str.replace('.', '').replace(',', ''))
            return float(number_str.replace('.', '').replace(',', '.'))
        except ValueError:
            return None

    def save_to_csv(self, company_data_list, company_code):
        df = pd.DataFrame(company_data_list)
        file_name = f"historical_data_{company_code}.csv"
        df.to_csv(file_name, mode='a', header=not pd.io.common.file_exists(file_name), index=False)

class Filter3:
    HISTORICAL_DATA_URL = "https://www.mse.mk/mk/stats/symbolhistory/"

    def __init__(self, input_csv):
        self.input_csv = input_csv

    def execute(self):
        issuers = self.read_issuers_from_csv()
        for issuer in issuers:
            self.fetch_missing_data(issuer)

    def read_issuers_from_csv(self):
        df = pd.read_csv(self.input_csv)
        return [{"company_code": code, "last_updated": None} for code in df["CompanyCode"]]

    def fetch_missing_data(self, issuer):
        company_code = issuer["company_code"]
        csv_file = f"historical_data_{company_code}.csv"

        if os.path.exists(csv_file):
            last_date = self.get_last_date_from_csv(csv_file)
            if last_date:
                self.fetch_and_save_historical_data(issuer, last_date, datetime.now())
        else:
            print(f"No data found for {company_code}. Fetching the last 10 years of data.")
            current_year = datetime.now().year
            for year in range(current_year, current_year - 10, -1):
                start_date = datetime(year, 1, 1)
                end_date = datetime(year, 12, 31)
                self.fetch_and_save_historical_data(issuer, start_date, end_date)


    def get_last_date_from_csv(self, csv_file):
        df = pd.read_csv(csv_file)
        if not df.empty:
            last_record_date = pd.to_datetime(df["record_date"]).max()
            return last_record_date
        return None

    def fetch_and_save_historical_data(self, issuer, from_date, to_date):
        payload = {
            "FromDate": from_date.strftime("%Y-%m-%d"),
            "ToDate": to_date.strftime("%Y-%m-%d"),
        }

        response = requests.post(self.HISTORICAL_DATA_URL + issuer["company_code"], data=payload)
        response.raise_for_status()
        document = BeautifulSoup(response.text, 'html.parser')
        results_table = document.select_one("table#resultsTable")

        if results_table:
            self.process_table_rows(results_table.select("tbody tr"), issuer)

    def process_table_rows(self, rows, issuer):
        company_data_list = []

        for row in rows:
            columns = row.select("td")
            if columns:
                high_price = self.parse_number(columns[2].text)
                if high_price is None:
                    continue

                company_data = {
                    "record_date": self.parse_date(columns[0].text, "%d.%m.%Y"),
                    "last_price": self.parse_number(columns[1].text),
                    "high_price": high_price,
                    "low_price": self.parse_number(columns[3].text),
                    "avg_price": self.parse_number(columns[4].text),
                    "percent_change": self.parse_number(columns[5].text),
                    "volume": self.parse_number(columns[6].text, is_integer=True),
                    "turnover_best": self.parse_number(columns[7].text, is_integer=True),
                    "total_turnover": self.parse_number(columns[8].text, is_integer=True),
                }
                company_data_list.append(company_data)

        self.save_to_csv(company_data_list, issuer["company_code"])

    @staticmethod
    def parse_date(date_str, date_format):
        return datetime.strptime(date_str, date_format).date()

    @staticmethod
    def parse_number(number_str, is_integer=False):
        setlocale(LC_ALL, "de_DE")
        try:
            if is_integer:
                return int(number_str.replace('.', '').replace(',', ''))
            return float(number_str.replace('.', '').replace(',', '.'))
        except ValueError:
            return None

    def save_to_csv(self, company_data_list, company_code):
        df = pd.DataFrame(company_data_list)
        file_name = f"historical_data_{company_code}.csv"
        df.to_csv(file_name, mode='a', header=not pd.io.common.file_exists(file_name), index=False)


if __name__ == "__main__":
    filter1 = Filter1("issuers.csv")
    company_codes = filter1.execute()

    filter2 = Filter2("issuers.csv")
    filter2.execute()

    filter3 = Filter3("issuers.csv")
    filter3.execute()
