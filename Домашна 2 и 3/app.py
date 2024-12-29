import csv
import os

import matplotlib
import numpy as np
import pandas as pd
import requests
import ta
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.layers import LSTM, Dense
from tensorflow.keras.models import Sequential
from textblob import TextBlob

matplotlib.use('Agg')

import matplotlib.pyplot as plt

app = Flask(__name__)


def read_company_codes():
    company_codes = []
    with open('issuers.csv', newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)
        for row in reader:
            company_codes.append(row[0])
    return company_codes


def read_historical_data(company_code):
    file_path = os.path.join(os.getcwd(), f'historical_data_{company_code}.csv')
    data = []

    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                data.append(row)
    else:
        print(f"CSV file for {company_code} does not exist.")

    return data


@app.route('/')
def home():
    company_codes = read_company_codes()
    return render_template('index.html', company_codes=company_codes)


@app.route('/company', methods=['POST'])
def company_data():
    company_code = request.form.get('company')
    historical_data = read_historical_data(company_code)
    return render_template('company_data.html', company_code=company_code, historical_data=historical_data)


@app.route('/technical-analysis', methods=['POST'])
def technical_analysis():
    company_code = request.form.get('companyCode')

    csv_file = f"historical_data_{company_code}.csv"

    try:

        data = pd.read_csv(csv_file, parse_dates=['record_date'])
        data.set_index('record_date', inplace=True)

        data['SMA_10'] = ta.trend.sma_indicator(data['last_price'], window=10)
        data['EMA_10'] = ta.trend.ema_indicator(data['last_price'], window=10)
        data['RSI'] = ta.momentum.rsi(data['last_price'], window=14)
        data['MACD'] = ta.trend.macd(data['last_price'])
        data['MACD_signal'] = ta.trend.macd_signal(data['last_price'])
        data['MACD_hist'] = ta.trend.macd_diff(data['last_price'])
        data['Stochastic_K'] = ta.momentum.stoch(data['high_price'], data['low_price'], data['last_price'], window=14)
        data['Stochastic_D'] = ta.momentum.stoch_signal(data['high_price'], data['low_price'], data['last_price'],
                                                        window=14)
        data['CCI'] = ta.trend.cci(data['high_price'], data['low_price'], data['last_price'], window=14)
        data['ROC'] = ta.momentum.roc(data['last_price'], window=10)

        data['Future_Price_1D'] = data['last_price'].shift(-1)
        data['Future_Price_1W'] = data['last_price'].shift(-5)
        data['Future_Price_1M'] = data['last_price'].shift(-20)

        data['Target_1D'] = np.where(data['Future_Price_1D'] > data['last_price'], 1,
                                     np.where(data['Future_Price_1D'] < data['last_price'], -1, 0))
        data['Target_1W'] = np.where(data['Future_Price_1W'] > data['last_price'], 1,
                                     np.where(data['Future_Price_1W'] < data['last_price'], -1, 0))
        data['Target_1M'] = np.where(data['Future_Price_1M'] > data['last_price'], 1,
                                     np.where(data['Future_Price_1M'] < data['last_price'], -1, 0))

        data.dropna(subset=['Target_1D', 'Target_1W', 'Target_1M'], inplace=True)

        features = ['SMA_10', 'EMA_10', 'RSI', 'MACD', 'MACD_signal', 'MACD_hist',
                    'Stochastic_K', 'Stochastic_D', 'CCI', 'ROC']

        X = data[features]
        y_1D = data['Target_1D']
        y_1W = data['Target_1W']
        y_1M = data['Target_1M']

        X_train, X_test, y_train_1D, y_test_1D = train_test_split(X, y_1D, test_size=0.2, shuffle=False)
        X_train, X_test, y_train_1W, y_test_1W = train_test_split(X, y_1W, test_size=0.2, shuffle=False)
        X_train, X_test, y_train_1M, y_test_1M = train_test_split(X, y_1M, test_size=0.2, shuffle=False)

        model_1D = RandomForestClassifier(n_estimators=100, random_state=42)
        model_1D.fit(X_train, y_train_1D)

        model_1W = RandomForestClassifier(n_estimators=100, random_state=42)
        model_1W.fit(X_train, y_train_1W)

        model_1M = RandomForestClassifier(n_estimators=100, random_state=42)
        model_1M.fit(X_train, y_train_1M)

        y_pred_1D = model_1D.predict(X_test)
        y_pred_1W = model_1W.predict(X_test)
        y_pred_1M = model_1M.predict(X_test)

        latest_data = data[features].iloc[-1].values.reshape(1, -1)

        predicted_signal_1D = model_1D.predict(latest_data)
        predicted_signal_1W = model_1W.predict(latest_data)
        predicted_signal_1M = model_1M.predict(latest_data)

        response = {
            "predicted_signal_1D": "Buy" if predicted_signal_1D == 1 else "Sell" if predicted_signal_1D == -1 else "Hold",
            "predicted_signal_1W": "Buy" if predicted_signal_1W == 1 else "Sell" if predicted_signal_1W == -1 else "Hold",
            "predicted_signal_1M": "Buy" if predicted_signal_1M == 1 else "Sell" if predicted_signal_1M == -1 else "Hold",
        }

        return jsonify(response)

    except FileNotFoundError:
        return jsonify({"error": "CSV file for the company not found."}), 404


@app.route('/fundamental-analysis', methods=['POST'])
def fundamental_analysis():
    company_code = request.form.get('companyCode')

    url = f"https://www.mse.mk/mk/symbol/{company_code}"
    response = requests.get(url)

    soup = BeautifulSoup(response.content, 'html.parser')

    news_div = soup.find('div', id='seiNetIssuerLatestNews')
    if news_div:

        news_links = news_div.find_all('a', href=True)

        sentiment_score = 0
        sentiment_count = 0

        for link in news_links:
            news_url = link['href']

            news_response = requests.get(news_url)
            news_soup = BeautifulSoup(news_response.content, 'html.parser')

            news_content = news_soup.get_text()

            blob = TextBlob(news_content)
            sentiment = blob.sentiment.polarity

            sentiment_score += sentiment
            sentiment_count += 1

        if sentiment_count > 0:
            average_sentiment = sentiment_score / sentiment_count
            if average_sentiment > 0:
                recommendation = "Buy stocks"
            else:
                recommendation = "Sell stocks"
        else:
            recommendation = "No relevant news found"

    else:
        recommendation = "No news available for this company."

    return recommendation


@app.route('/lstm', methods=['POST'])
def lstm():
    company_code = request.form.get('companyCode')

    csv_file = f"historical_data_{company_code}.csv"
    df = pd.read_csv(csv_file)

    df['record_date'] = pd.to_datetime(df['record_date'], format='%Y-%m-%d')

    data = df[['record_date', 'last_price']].set_index('record_date')

    scaler = MinMaxScaler(feature_range=(0, 1))
    data_scaled = scaler.fit_transform(data[['last_price']])

    train_size = int(len(data) * 0.7)
    train_data = data_scaled[:train_size]
    val_data = data_scaled[train_size:]

    def create_dataset(data, time_step=30):
        X, y = [], []
        for i in range(len(data) - time_step - 1):
            X.append(data[i:(i + time_step), 0])
            y.append(data[i + time_step, 0])
        return np.array(X), np.array(y)

    time_step = 30
    X_train, y_train = create_dataset(train_data, time_step)
    X_val, y_val = create_dataset(val_data, time_step)
    print(f'X_train shape: {X_train.shape}')
    print(f'X_val shape: {X_val.shape}')

    X_train = X_train.reshape(X_train.shape[0], X_train.shape[1], 1)
    X_val = X_val.reshape(X_val.shape[0], X_val.shape[1], 1)

    model = Sequential()
    model.add(LSTM(units=100, return_sequences=True, input_shape=(X_train.shape[1], 1)))
    model.add(LSTM(units=100, return_sequences=False))
    model.add(Dense(units=1))  # Output layer

    model.compile(optimizer='adam', loss='mean_squared_error')

    history = model.fit(X_train, y_train, epochs=50, batch_size=32, validation_data=(X_val, y_val))

    predictions = model.predict(X_val)
    predictions = scaler.inverse_transform(predictions.reshape(-1, 1))

    y_val_actual = scaler.inverse_transform(y_val.reshape(-1, 1))

    rmse = np.sqrt(mean_squared_error(y_val_actual, predictions))
    print(f'Root Mean Squared Error (RMSE): {rmse}')

    plt.figure(figsize=(12, 6))
    plt.plot(y_val_actual, color='blue', label='Actual Stock Price')
    plt.plot(predictions, color='red', label='Predicted Stock Price')
    plt.title('Stock Price Prediction')
    plt.xlabel('Date')
    plt.ylabel('Stock Price')
    plt.legend()
    prediction_value = predictions[0][0]

    return jsonify({"predicted_price": float(prediction_value)})


if __name__ == '__main__':
    app.run(debug=True,port=5002)
