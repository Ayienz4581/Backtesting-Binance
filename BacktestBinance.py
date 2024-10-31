import time
import hmac
import hashlib
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import pytz
from colorama import Fore, Style

# Konfigurasi API
API_KEY = 'YOUR_API_KEY'
API_SECRET = 'YOUR_API_SECRET'
BASE_URL = 'https://fapi.binance.com'

# Fungsi untuk membuat signature
def create_signature(query_string):
    return hmac.new(API_SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()

# Fungsi untuk mendapatkan data historis
def get_historical_data(symbol, interval, limit=1000):  # Mengambil lebih banyak data
    url = f"{BASE_URL}/fapi/v1/klines"
    params = {
        'symbol': symbol,
        'interval': interval,
        'limit': limit,
        'timestamp': int(time.time() * 1000)
    }
    params['signature'] = create_signature('&'.join([f"{key}={value}" for key, value in params.items()]))
    headers = {'X-MBX-APIKEY': API_KEY}
    response = requests.get(url, headers=headers, params=params)
    return response.json()

# Fungsi untuk melakukan backtesting
def backtest_strategy(data, initial_balance, start_time):
    df = pd.DataFrame(data, columns=['Open Time', 'Open', 'High', 'Low', 'Close', 
                                      'Volume', 'Close Time', 'Quote Asset Volume', 
                                      'Number of Trades', 'Taker Buy Base Asset Volume', 
                                      'Taker Buy Quote Asset Volume', 'Ignore'])
    
    # Konversi Open Time ke format TahunBulanTanggal JamMenitDetik
    df['Open Time'] = pd.to_datetime(df['Open Time'], unit='ms')
    df['Open Time'] = df['Open Time'].dt.tz_localize('UTC').dt.tz_convert('Asia/Jakarta')
    df['Open Time'] = df['Open Time'].dt.strftime('%Y%m%d %H%M%S')

    df['Close'] = df['Close'].astype(float)
    df['Low'] = df['Low'].astype(float)  # Pastikan Low adalah float
    df['High'] = df['High'].astype(float)  # Pastikan High adalah float
    
    # Menghitung SMA10 dan SMA30
    df['SMA_10'] = df['Close'].rolling(window=10).mean()
    df['SMA_30'] = df['Close'].rolling(window=30).mean()
    
    # Mengisi nilai NaN pada SMA30 dengan nilai terakhir yang valid
    df['SMA_30'] = df['SMA_30'].ffill()

    # Sinyal beli/jual
    df['Signal'] = 0
    df.loc[30:, 'Signal'] = np.where(df['SMA_10'][30:] > df['SMA_30'][30:], 1, 0)
    df['Position'] = df['Signal'].diff()

    # Backtrading
    balance = initial_balance
    position = 0  # Jumlah yang dibeli
    entry_price = 0  # Harga masuk
    first_trade_time = None  # Waktu pertama kali melakukan trade

    for index, row in df.iterrows():
        if row['Position'] == 1:  # Buy signal
            if balance > 0:  # Pastikan ada saldo untuk membeli
                entry_price = row['Low']  # Buka posisi Buy pada harga low sebelumnya
                position = balance / entry_price  # Beli dengan seluruh saldo
                balance = 0  # Set saldo menjadi 0 setelah membeli
                print(f"BUY at {entry_price} on {row['Open Time']}")
                if first_trade_time is None:  # Simpan waktu pertama kali trade
                    first_trade_time = row['Open Time']
                time.sleep(2)  # Jeda 2 detik
            
        elif row['Position'] == -1:  # Sell signal
            if position > 0:  # Pastikan ada posisi untuk dijual
                sell_price = row['High']  # Jual pada harga high berikutnya
                balance = position * sell_price  # Jual semua posisi
                profit = balance - (position * entry_price)  # Hitung profit

                # Cetak hasil dengan format yang sesuai
                if profit > 0:
                    print(f"SELL at {sell_price} on {row['Open Time']}, Profit: {Fore.GREEN}+{profit:.2f}{Style.RESET_ALL}")
                else:
                    print(f"SELL at {sell_price} on {row['Open Time']}, Loss: {Fore.RED}{profit:.2f}{Style.RESET_ALL}")

                print(f"Subtotal Balance after Sell: {balance:.2f}")
                position = 0  # Set posisi menjadi 0 setelah menjual
                time.sleep(2)  # Jeda 2 detik

    # Jika masih ada posisi yang belum dijual, hitung profit akhir
    if position > 0:
        balance = position * df.iloc[-1]['Close']  # Jual pada harga terakhir
        profit = balance - (position * entry_price)
        if profit > 0:
            print(f"SELL at {df.iloc[-1]['Close']} on {df.iloc[-1]['Open Time']}, Profit: {Fore.GREEN}+{profit:.2f}{Style.RESET_ALL}")
        else:
            print(f"SELL at {df.iloc[-1]['Close']} on {df.iloc[-1]['Open Time']}, Loss: {Fore.RED}{profit:.2f}{Style.RESET_ALL}")
        print(f"Subtotal Balance after final Sell: {balance:.2f}")

    total_profit = balance - initial_balance
    print(f"Total Profit/Loss: {total_profit:.2f}")
    print(f"Final Balance: {balance:.2f}")

    # Menghitung interval waktu backtesting dari waktu pertama kali trade
    end_time = datetime.now(pytz.timezone('Asia/Jakarta'))
    if first_trade_time is not None:
        first_trade_time = datetime.strptime(first_trade_time, '%Y%m%d %H%M%S').replace(tzinfo=pytz.timezone('Asia/Jakarta'))
        duration = end_time - first_trade_time
        days = duration.days
        hours, remainder = divmod(duration.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        print(f"Backtesting Duration from first trade: {days} days, {hours} hours, {minutes} minutes")
        print(f"Backtesting Start Time: {first_trade_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Backtesting End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("No trades were executed during the backtesting period.")

# Fungsi untuk mendapatkan waktu saat ini dalam format TahunBulanTanggal JamMenitDetik (UTC +7)
def get_current_time_utc_plus_7():
    utc_plus_7 = pytz.timezone('Asia/Jakarta')
    now = datetime.now(utc_plus_7)
    return now  # Mengembalikan objek datetime untuk perhitungan durasi

# Main function
def main():
    # Input dari pengguna
    symbol = input("Masukkan simbol (misalnya BTCUSDT): ")
    interval = input("Masukkan interval (misalnya 1h, 1d): ")
    initial_balance = float(input("Masukkan saldo awal: "))  # Mengonversi input ke float
    
    # Ambil waktu mulai
    start_time = get_current_time_utc_plus_7()
    
    # Ambil data historis
    historical_data = get_historical_data(symbol, interval)
    
    # Lakukan backtesting
    backtest_strategy(historical_data, initial_balance, start_time)
    
    # Tampilkan waktu saat ini
    current_time = start_time.strftime("%Y%m%d %H%M%S")
    print("Waktu saat ini dalam format TahunBulanTanggal JamMenitDetik (UTC +7):", current_time)

if __name__ == "__main__":
    main()
