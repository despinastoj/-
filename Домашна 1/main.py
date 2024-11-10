import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import time
from datetime import datetime
import webbrowser


def extract_valid_companies(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    options = soup.find_all('option')
    valid_companies = []

    for option in options:
        symbol = option['value']
        if not (symbol.startswith('M') and any(char.isdigit() for char in symbol)):
            valid_companies.append(symbol)

    return valid_companies


def check_last_available_date(symbol, database_path='data.xlsx'):
    try:
        existing_data = pd.read_excel(database_path, sheet_name=None)
        if symbol in existing_data:

            last_date = existing_data[symbol]['датум'].max()
            return last_date
    except (FileNotFoundError, KeyError):
        pass
    return "2014-01-01"


def fetch_company_data(symbol, start_date):
    url = f'https://www.mse.mk/mk/stats/symbolhistory/{symbol}'
    end_date = datetime.today().strftime('%d.%m.%Y')
    payload = {'FromDate': start_date, 'ToDate': end_date, 'symbol': symbol}
    data = []

    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        table = soup.find('table')

        if table:
            for row in table.find_all('tr')[1:]:
                cols = row.find_all('td')
                if len(cols) >= 9:
                    data.append({
                        'симбол': symbol,
                        'датум': cols[0].text.strip(),
                        'отворена цена': cols[1].text.strip(),
                        'најголема цена': cols[2].text.strip(),
                        'најмала цена': cols[3].text.strip(),
                        'затворена цена': cols[4].text.strip(),
                        'волумен': cols[5].text.strip(),
                        'промет': cols[6].text.strip(),
                        'трансакции': cols[7].text.strip(),
                        'друго': cols[8].text.strip(),
                    })
    except requests.RequestException as e:
        print(f"Request failed for {symbol}: {e}")

    return data


def save_data(symbol, data, file_path='data.xlsx'):
    try:
        if os.path.exists(file_path):
            with pd.ExcelWriter(file_path, engine='openpyxl', mode='a') as writer:
                df = pd.DataFrame(data)
                df.to_excel(writer, sheet_name=symbol, index=False)
        else:
            # If the file doesn't exist, create a new one and write data
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df = pd.DataFrame(data)
                df.to_excel(writer, sheet_name=symbol, index=False)

    except Exception as e:
        print(f"Error saving data for {symbol}: {e}")


def open_excel_file(file_path='data.xlsx'):
    webbrowser.open(file_path)


def main():
    start_time = time.time()
    with open("com.html", "r", encoding="utf-8") as file:
        html_content = file.read()
    symbols = extract_valid_companies(html_content)

    for symbol in symbols:
        last_date = check_last_available_date(symbol)
        symbol_data = fetch_company_data(symbol, last_date)
        if symbol_data:
            save_data(symbol, symbol_data)

    total_time = time.time() - start_time
    print(f"Total execution time: {total_time:.2f} seconds")

    open_excel_file()


if __name__ == "__main__":
    main()
