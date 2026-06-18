# backtest_engine.py - 30 DAYS WITH REAL DATA
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from typing import Dict, List, Optional, Any
import requests
from strategy import BuickStrategy

class BacktestEngine:
    def __init__(self, config: Dict):
        self.config = config
        self.strategy = BuickStrategy(config)
        self.results = {}
        
    def fetch_data(self, symbol: str, days: int = 30) -> pd.DataFrame:
        """Φέρνει ΠΡΑΓΜΑΤΙΚΑ δεδομένα από Binance για 30 μέρες"""
        print(f"📡 Φορτώνω πραγματικά δεδομένα για {symbol}...")
        
        # Χρησιμοποιούμε 1h intervals για να χωρέσουν 30 μέρες
        interval = self.config.get('timeframe', '1h')
        
        # Χάρτης intervals
        interval_minutes = {
            '1m': 1, '3m': 3, '5m': 5, '15m': 15, 
            '30m': 30, '1h': 60, '2h': 120, '4h': 240,
            '6h': 360, '8h': 480, '12h': 720, '1d': 1440
        }
        
        minutes = interval_minutes.get(interval, 60)
        
        # Υπολογισμός πόσα candlesticks χρειαζόμαστε
        # 30 μέρες * 24 ώρες * 60 λεπτά / minutes_per_candle
        total_candles = days * 24 * 60 // minutes
        limit = min(total_candles, 1000)  # Max 1000 από Binance
        
        # Start time: πριν από 'days' μέρες
        start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        end_time = int(datetime.now().timestamp() * 1000)
        
        print(f"   • Διαστήματα: {interval} ({minutes} λεπτά)")
        print(f"   • Ζητώ: {limit} καντέλια")
        print(f"   • Από: {datetime.fromtimestamp(start_time/1000).strftime('%Y-%m-%d %H:%M')}")
        print(f"   • Έως: {datetime.fromtimestamp(end_time/1000).strftime('%Y-%m-%d %H:%M')}")
        
        # Δοκιμάζουμε Futures πρώτα
        try:
            base_url = "https://fapi.binance.com/fapi/v1/klines"
            symbol_pair = f"{symbol}USDT"
            
            params = {
                'symbol': symbol_pair,
                'interval': interval,
                'limit': limit,
                'startTime': start_time,
                'endTime': end_time
            }
            
            response = requests.get(base_url, params=params, timeout=10)
            data = response.json()
            
            if isinstance(data, dict) and 'code' in data:
                if data['code'] == -1121:
                    print(f"⚠️ Το {symbol} δεν υπάρχει στα futures, δοκιμάζω spot...")
                else:
                    print(f"⚠️ Futures API error: {data}")
            else:
                df = self._process_klines_data(data)
                print(f"✅ Φόρτωσα {len(df)} καντέλια για {symbol} (futures)")
                print(f"   • Από: {df.index[0]} έως {df.index[-1]}")
                return df
                
        except Exception as e:
            print(f"⚠️ Futures error: {e}")
        
        # Δοκιμάζουμε Spot
        try:
            base_url = "https://api.binance.com/api/v3/klines"
            symbol_pair = f"{symbol}USDT"
            
            params = {
                'symbol': symbol_pair,
                'interval': interval,
                'limit': limit,
                'startTime': start_time,
                'endTime': end_time
            }
            
            response = requests.get(base_url, params=params, timeout=10)
            data = response.json()
            
            if isinstance(data, dict) and 'code' in data:
                if data['code'] == -1121:
                    print(f"❌ Το {symbol} δεν υπάρχει ούτε στο spot")
                else:
                    print(f"⚠️ Spot API error: {data}")
            else:
                df = self._process_klines_data(data)
                print(f"✅ Φόρτωσα {len(df)} καντέλια για {symbol} (spot)")
                print(f"   • Από: {df.index[0]} έως {df.index[-1]}")
                return df
                
        except Exception as e:
            print(f"❌ Spot error: {e}")
        
        # Fallback σε συνθετικά
        print(f"⚠️ Χρησιμοποιώ συνθετικά δεδομένα για {symbol}")
        return self.generate_synthetic_data(symbol, days)
    
    def _process_klines_data(self, data) -> pd.DataFrame:
        """Επεξεργάζεται τα δεδομένα από Binance"""
        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        return df
    
    def generate_synthetic_data(self, symbol: str, days: int) -> pd.DataFrame:
        """Δημιουργεί συνθετικά δεδομένα"""
        print(f"🧪 Δημιουργώ ΣΥΝΘΕΤΙΚΑ δεδομένα για {symbol}...")
        
        interval = self.config.get('timeframe', '1h')
        interval_minutes = {'1h': 60, '4h': 240, '1d': 1440}
        minutes = interval_minutes.get(interval, 60)
        periods = days * 24 * 60 // minutes
        
        base_price = 1.0 if symbol == "ONDO" else 25.0 if symbol == "HYPE" else 100.0
        
        np.random.seed(42)
        returns = np.random.normal(0, 0.002, periods)
        prices = base_price * np.exp(np.cumsum(returns))
        
        df = pd.DataFrame({
            'open': prices * (1 + np.random.normal(0, 0.0005, periods)),
            'high': prices * (1 + np.random.normal(0.001, 0.001, periods)),
            'low': prices * (1 + np.random.normal(-0.001, 0.001, periods)),
            'close': prices,
            'volume': np.random.uniform(1000, 10000, periods)
        }, index=pd.date_range(end=datetime.now(), periods=periods, freq=interval))
        
        return df
    
    def run_backtest(self, symbol: str) -> Dict:
        """Τρέχει το backtest για ένα σύμβολο"""
        print(f"\n🔄 Backtesting {symbol}...")
        
        df = self.fetch_data(symbol, self.config['test_days'])
        
        strategy = BuickStrategy(self.config)
        strategy.capital = self.config['initial_capital']
        
        positions = []
        trades = []
        equity_history = [strategy.capital]
        
        total_entries = 0
        total_exits = 0
        total_profit = 0
        
        for idx, row in df.iterrows():
            price = row['close']
            
            # 1. EXITS
            exits = strategy.calculate_exits(price, positions)
            for exit_order in exits:
                pos = exit_order['position']
                profit = exit_order['profit']
                
                strategy.capital += profit
                total_profit += profit
                total_exits += 1
                
                trades.append({
                    'timestamp': idx,
                    'type': 'EXIT',
                    'price': price,
                    'profit': profit,
                    'entry_index': pos['entry_index'],
                    'entry_price': pos['entry_price'],
                    'symbol': symbol,
                    'price_change': exit_order.get('price_change', 0),
                    'roi': exit_order.get('roi', 0)
                })
                
                pos['closed'] = True
            
            # 2. ENTRIES
            if strategy.should_enter(price, positions):
                entry = strategy.calculate_entry(price, strategy.capital)
                if entry is not None:
                    positions.append(entry)
                    total_entries += 1
                    
                    trades.append({
                        'timestamp': idx,
                        'type': 'ENTRY',
                        'price': price,
                        'margin': entry['margin'],
                        'base_amount': entry['base_amount'],
                        'entry_index': entry['entry_index'],
                        'symbol': symbol
                    })
            
            # 3. EMERGENCY CHECK
            if strategy.check_emergency(price, positions):
                print(f"⚠️ EMERGENCY STOP για {symbol} στο {price}")
                for pos in positions:
                    if not pos.get('closed', False):
                        profit = (price - pos['entry_price']) * pos['base_amount'] / pos['entry_price']
                        strategy.capital += profit
                        trades.append({
                            'timestamp': idx,
                            'type': 'EMERGENCY_EXIT',
                            'price': price,
                            'profit': profit,
                            'symbol': symbol
                        })
                positions = []
                break
            
            # 4. EQUITY CURVE
            current_equity = strategy.capital
            unrealized = 0
            for pos in positions:
                if not pos.get('closed', False):
                    unrealized += (price - pos['entry_price']) * pos['base_amount'] / pos['entry_price']
            equity_history.append(current_equity + unrealized)
        
        final_capital = strategy.capital
        total_trades = len([t for t in trades if t['type'] == 'EXIT'])
        roi = ((final_capital - self.config['initial_capital']) / self.config['initial_capital']) * 100
        
        entries_df = pd.DataFrame([
            {'time': t['timestamp'], 'price': t['price'], 'entry_index': t.get('entry_index', 0)}
            for t in trades if t['type'] == 'ENTRY'
        ])
        
        exits_df = pd.DataFrame([
            {'time': t['timestamp'], 'price': t['price'], 'entry_index': t.get('entry_index', 0)}
            for t in trades if t['type'] == 'EXIT'
        ])
        
        print(f"📊 {symbol} | ROI: {roi:.2f}% | Trades: {total_trades} | Entries: {len(entries_df)}")
        print(f"   • Σύνολο κερδών: ${total_profit:.2f}")
        print(f"   • Μέσο κέρδος/trade: ${total_profit/total_trades if total_trades > 0 else 0:.4f}")
        
        return {
            'symbol': symbol,
            'initial_capital': self.config['initial_capital'],
            'final_capital': final_capital,
            'total_profit': total_profit,
            'roi': roi,
            'total_trades': total_trades,
            'entries': len(entries_df),
            'trades_df': trades,
            'entries_df': entries_df,
            'exits_df': exits_df,
            'equity_history': equity_history,
            'price_data': df
        }
    
    def run_multi_backtest(self) -> Dict:
        results = {}
        for coin in self.config['test_coins']:
            result = self.run_backtest(coin)
            results[coin] = result
        return results