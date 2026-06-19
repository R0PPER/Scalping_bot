# data_fetcher.py - Download and store 5m data for 30 days
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import time
import os
import sys
import io

# Fix encoding for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

class DataFetcher:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
    def fetch_klines(self, symbol: str, interval: str = "5m", limit: int = 1000, start_time: int = None, end_time: int = None) -> pd.DataFrame:
        """
        Fetch klines from Binance Futures API
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
                print(f"API error for {symbol}: {data}")
                return pd.DataFrame()
            
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Keep only necessary columns
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            return pd.DataFrame()
    
    def fetch_historical_data(self, symbol: str, days: int = 30, interval: str = "5m") -> pd.DataFrame:
        """
        Fetch historical data for X days (in chunks of 1000 candlesticks)
        """
        print(f"\nFetching data for {symbol} ({days} days, {interval})...")
        
        # Calculate how many candlesticks we need
        interval_minutes = {
            '1m': 1, '3m': 3, '5m': 5, '15m': 15, 
            '30m': 30, '1h': 60, '2h': 120, '4h': 240
        }
        minutes = interval_minutes.get(interval, 5)
        total_candles = days * 24 * 60 // minutes
        
        # 1000 candlesticks per request (Binance limit)
        chunk_size = 1000
        chunks = (total_candles // chunk_size) + 1
        
        print(f"   • Total candlesticks: {total_candles}")
        print(f"   • Chunks: {chunks} (of {chunk_size})")
        
        all_data = []
        end_time = int(datetime.now().timestamp() * 1000)
        
        for i in range(chunks):
            # Calculate start_time
            start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
            
            # If we already have data, continue from last timestamp
            if all_data:
                last_timestamp = all_data[-1].index[-1]
                start_time = int(last_timestamp.timestamp() * 1000) + 1
            
            print(f"   • Chunk {i+1}/{chunks}: Fetching from {datetime.fromtimestamp(start_time/1000)}")
            
            df = self.fetch_klines(symbol, interval, chunk_size, start_time, end_time)
            
            if df.empty:
                print(f"   Chunk {i+1} empty, stopping...")
                break
            
            all_data.append(df)
            
            # Be nice to rate limits
            time.sleep(0.2)
            
            # If we got less than chunk_size, we're at the end
            if len(df) < chunk_size:
                break
        
        if not all_data:
            print(f"No data fetched for {symbol}")
            return pd.DataFrame()
        
        # Combine all chunks
        final_df = pd.concat(all_data)
        final_df = final_df[~final_df.index.duplicated(keep='first')]
        final_df.sort_index(inplace=True)
        
        print(f"Fetched {len(final_df)} candles for {symbol}")
        print(f"   • From: {final_df.index[0]} to {final_df.index[-1]}")
        
        return final_df
    
    def save_data(self, symbol: str, df: pd.DataFrame, days: int = 30) -> str:
        """
        Save data to CSV
        """
        filename = f"{self.data_dir}/{symbol}_5m_{days}days.csv"
        df.to_csv(filename)
        print(f"Saved {len(df)} candles to {filename}")
        return filename
    
    def load_data(self, symbol: str, days: int = 30) -> pd.DataFrame:
        """
        Load data from CSV
        """
        filename = f"{self.data_dir}/{symbol}_5m_{days}days.csv"
        if os.path.exists(filename):
            df = pd.read_csv(filename, index_col=0, parse_dates=True)
            print(f"Loaded {len(df)} candles from {filename}")
            return df
        else:
            print(f"File {filename} not found")
            return pd.DataFrame()
    
    def fetch_and_save(self, symbol: str, days: int = 30, interval: str = "5m", force_refresh: bool = False):
        """
        Download and save data (or load if exists)
        """
        if not force_refresh:
            df = self.load_data(symbol, days)
            if not df.empty:
                return df
        
        df = self.fetch_historical_data(symbol, days, interval)
        if not df.empty:
            self.save_data(symbol, df, days)
        return df


# Script to run data download
if __name__ == "__main__":
    fetcher = DataFetcher()
    
    # Download data for ONDO, HYPE, WIF, DOGE, SHIB
    symbols = ["ONDO", "HYPE", "WIF", "DOGE", "SHIB"]
    days = 90
    
    for symbol in symbols:
        print(f"\n{'='*50}")
        print(f"Downloading data for {symbol}")
        print('='*50)
        df = fetcher.fetch_and_save(symbol, days, "5m", force_refresh=True)
        
        # Show stats
        if not df.empty:
            print(f"\n{symbol} stats:")
            print(f"   • First: {df.index[0]}")
            print(f"   • Last: {df.index[-1]}")
            print(f"   • Total: {len(df)} candlesticks")
            print(f"   • Min price: {df['low'].min():.4f}")
            print(f"   • Max price: {df['high'].max():.4f}")