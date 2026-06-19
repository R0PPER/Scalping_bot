# data_fetcher.py - Download and store 5m data for 30 days
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import time
import os

class DataFetcher:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
    def fetch_klines(self, symbol: str, interval: str = "5m", limit: int = 1000, start_time: int = None, end_time: int = None) -> pd.DataFrame:
        """
        Φέρνει klines από το Binance Futures API
        """
        base_url = "https://fapi.binance.com/fapi/v1/klines"
        symbol_pair = f"{symbol}USDT"
        
        params = {
            'symbol': symbol_pair,
            'interval': interval,
            'limit': limit
        }
        
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        
        try:
            response = requests.get(base_url, params=params, timeout=30)
            data = response.json()
            
            if isinstance(data, dict) and 'code' in data:
                print(f"⚠️ API error for {symbol}: {data}")
                return pd.DataFrame()
            
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Κρατάμε μόνο τα απαραίτητα
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            print(f"❌ Error fetching {symbol}: {e}")
            return pd.DataFrame()
    
    def fetch_historical_data(self, symbol: str, days: int = 30, interval: str = "5m") -> pd.DataFrame:
        """
        Φέρνει ιστορικά δεδομένα για X μέρες (σε κομμάτια των 1000 candlesticks)
        """
        print(f"\n📡 Φορτώνω δεδομένα για {symbol} ({days} μέρες, {interval})...")
        
        # Υπολογισμός πόσα candlesticks χρειαζόμαστε
        interval_minutes = {
            '1m': 1, '3m': 3, '5m': 5, '15m': 15, 
            '30m': 30, '1h': 60, '2h': 120, '4h': 240
        }
        minutes = interval_minutes.get(interval, 5)
        total_candles = days * 24 * 60 // minutes
        
        # 1000 candlesticks per request (Binance limit)
        chunk_size = 1000
        chunks = (total_candles // chunk_size) + 1
        
        print(f"   • Σύνολο candlesticks: {total_candles}")
        print(f"   • Chunks: {chunks} (των {chunk_size})")
        
        all_data = []
        end_time = int(datetime.now().timestamp() * 1000)
        
        for i in range(chunks):
            # Υπολογισμός start_time
            start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
            
            # Αν υπάρχουν ήδη δεδομένα, συνεχίζουμε από το τελευταίο timestamp
            if all_data:
                last_timestamp = all_data[-1].index[0]
                start_time = int(last_timestamp.timestamp() * 1000) + 1
            
            print(f"   • Chunk {i+1}/{chunks}: Φορτώνω από {datetime.fromtimestamp(start_time/1000)}")
            
            df = self.fetch_klines(symbol, interval, chunk_size, start_time, end_time)
            
            if df.empty:
                print(f"   ⚠️ Chunk {i+1} empty, stopping...")
                break
            
            all_data.append(df)
            
            # Προσοχή στα rate limits
            time.sleep(0.2)
            
            # Αν πήραμε λιγότερα από chunk_size, είμαστε στο τέλος
            if len(df) < chunk_size:
                break
        
        if not all_data:
            print(f"❌ No data fetched for {symbol}")
            return pd.DataFrame()
        
        # Συγχώνευση όλων των chunks
        final_df = pd.concat(all_data)
        final_df = final_df[~final_df.index.duplicated(keep='first')]
        final_df.sort_index(inplace=True)
        
        print(f"✅ Φόρτωσα {len(final_df)} καντέλια για {symbol}")
        print(f"   • Από: {final_df.index[0]} έως {final_df.index[-1]}")
        
        return final_df
    
    def save_data(self, symbol: str, df: pd.DataFrame) -> str:
        """
        Αποθηκεύει τα δεδομένα σε CSV
        """
        filename = f"{self.data_dir}/{symbol}_5m_30days.csv"
        df.to_csv(filename)
        print(f"💾 Αποθηκεύτηκαν {len(df)} καντέλια στο {filename}")
        return filename
    
    def load_data(self, symbol: str) -> pd.DataFrame:
        """
        Φορτώνει δεδομένα από CSV
        """
        filename = f"{self.data_dir}/{symbol}_5m_30days.csv"
        if os.path.exists(filename):
            df = pd.read_csv(filename, index_col=0, parse_dates=True)
            print(f"✅ Φόρτωσα {len(df)} καντέλια από {filename}")
            return df
        else:
            print(f"⚠️ File {filename} not found")
            return pd.DataFrame()
    
    def fetch_and_save(self, symbol: str, days: int = 30, interval: str = "5m", force_refresh: bool = False):
        """
        Κατεβάζει και αποθηκεύει δεδομένα (ή φορτώνει αν υπάρχουν)
        """
        if not force_refresh:
            df = self.load_data(symbol)
            if not df.empty:
                return df
        
        df = self.fetch_historical_data(symbol, days, interval)
        if not df.empty:
            self.save_data(symbol, df)
        return df


# Script για να τρέξουμε τη λήψη δεδομένων
if __name__ == "__main__":
    fetcher = DataFetcher()
    
    # Λήψη δεδομένων για ONDO και HYPE
    symbols = ["ONDO", "HYPE"]
    days = 30
    
    for symbol in symbols:
        print(f"\n{'='*50}")
        print(f"📊 Λήψη δεδομένων για {symbol}")
        print('='*50)
        df = fetcher.fetch_and_save(symbol, days, "5m", force_refresh=True)
        
        # Εμφάνιση στατιστικών
        if not df.empty:
            print(f"\n📊 Στατιστικά {symbol}:")
            print(f"   • Πρώτο: {df.index[0]}")
            print(f"   • Τελευταίο: {df.index[-1]}")
            print(f"   • Σύνολο: {len(df)} candlesticks")
            print(f"   • Min price: {df['low'].min():.4f}")
            print(f"   • Max price: {df['high'].max():.4f}")