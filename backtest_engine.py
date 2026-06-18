# backtest_engine.py - WITH 5m DATA FOR MORE TRADES
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
        
    def fetch_data(self, symbol: str, days: int = 7) -> pd.DataFrame:
        """
        🔥 Χρησιμοποιούμε 5m intervals για ΠΕΡΙΣΣΟΤΕΡΑ trades
        """
        print(f"📡 Φορτώνω δεδομένα για {symbol}...")
        
        interval = "5m"  # 🔥 5 λεπτά για πολλά trades
        
        # 7 μέρες * 24 ώρες * 12 = 2016 καντέλια
        # Binance limit = 1000, οπότε παίρνουμε όσα περισσότερα γίνεται
        limit = 1000
        days_to_fetch = 7  # 7 μέρες με 5m = 2016 καντέλια, παίρνουμε 1000
        
        start_time = int((datetime.now() - timedelta(days=days_to_fetch)).timestamp() * 1000)
        end_time = int(datetime.now().timestamp() * 1000)
        
        print(f"   • Διαστήματα: 5m")
        print(f"   • Ζητώ: {limit} καντέλια")
        print(f"   • Από: {datetime.fromtimestamp(start_time/1000).strftime('%Y-%m-%d %H:%M')}")
        print(f"   • Έως: {datetime.fromtimestamp(end_time/1000).strftime('%Y-%m-%d %H:%M')}")
        
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
                    print(f"⚠️ {symbol} δεν υπάρχει στα futures")
                else:
                    print(f"⚠️ API error: {data}")
            else:
                df = self._process_klines_data(data)
                print(f"✅ Φόρτωσα {len(df)} καντέλια για {symbol} (futures)")
                print(f"   • Από: {df.index[0]} έως {df.index[-1]}")
                return df
                
        except Exception as e:
            print(f"⚠️ Futures error: {e}")
        
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
                print(f"❌ {symbol} δεν υπάρχει ούτε στο spot")
            else:
                df = self._process_klines_data(data)
                print(f"✅ Φόρτωσα {len(df)} καντέλια για {symbol} (spot)")
                print(f"   • Από: {df.index[0]} έως {df.index[-1]}")
                return df
                
        except Exception as e:
            print(f"❌ Spot error: {e}")
        
        print(f"⚠️ Χρησιμοποιώ συνθετικά δεδομένα για {symbol}")
        return self.generate_synthetic_data(symbol, 7)
    
    def _process_klines_data(self, data) -> pd.DataFrame:
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
        print(f"🧪 Συνθετικά δεδομένα για {symbol}...")
        periods = days * 24 * 12
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
        }, index=pd.date_range(end=datetime.now(), periods=periods, freq='5min'))
        
        return df
    
    def run_backtest(self, symbol: str) -> Dict:
        print(f"\n🔄 Backtesting {symbol}...")
        
        df = self.fetch_data(symbol, self.config['test_days'])
        
        strategy = BuickStrategy(self.config)
        strategy.capital = self.config['initial_capital']
        
        positions = []
        trades = []
        equity_history = [strategy.capital]
        liq_history = []
        
        total_entries = 0
        total_exits = 0
        total_profit = 0
        liquidated = False
        
        for idx, row in df.iterrows():
            price = row['close']
            
            # 1. EXITS: Κάθε θέση ανεξάρτητα
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
            
            # 3. LIQUIDATION INFO
            liq_info = strategy.get_liquidation_info(price, positions)
            liq_history.append({
                'timestamp': idx,
                'price': price,
                'distance': liq_info['distance'],
                'exposure': liq_info['exposure_percent'],
                'open_positions': liq_info['open_positions']
            })
            
            if liq_info['is_liquidated']:
                liquidated = True
                print(f"💀 LIQUIDATION ΣΤΟ {symbol} στις {idx} με τιμή {price}")
                positions = []
                break
            
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
        
        final_capital = strategy.capital if not liquidated else 0
        total_trades = len([t for t in trades if t['type'] == 'EXIT'])
        roi = ((final_capital - self.config['initial_capital']) / self.config['initial_capital']) * 100 if not liquidated else -100
        
        entries_df = pd.DataFrame([
            {'time': t['timestamp'], 'price': t['price'], 'entry_index': t.get('entry_index', 0)}
            for t in trades if t['type'] == 'ENTRY'
        ])
        
        exits_df = pd.DataFrame([
            {'time': t['timestamp'], 'price': t['price'], 'entry_index': t.get('entry_index', 0)}
            for t in trades if t['type'] == 'EXIT'
        ])
        
        liq_df = pd.DataFrame(liq_history)
        if not liq_df.empty:
            min_distance = liq_df['distance'].min()
            avg_distance = liq_df['distance'].mean()
            max_exposure = liq_df['exposure'].max()
            warnings = len([d for d in liq_df['distance'] if d < 5])
        else:
            min_distance = 100
            avg_distance = 100
            max_exposure = 0
            warnings = 0
        
        print(f"\n📊 {symbol} | ROI: {roi:.2f}% | Trades: {total_trades} | Entries: {len(entries_df)}")
        print(f"   • Σύνολο κερδών: ${total_profit:.2f}")
        print(f"   • Μέσο κέρδος/trade: ${total_profit/total_trades if total_trades > 0 else 0:.4f}")
        print(f"   • 🔥 LIQUIDATION: {'✅ ΟΧΙ' if not liquidated else '💀 ΝΑΙ'}")
        if not liquidated:
            print(f"   • Ελάχιστη απόσταση: {min_distance:.2f}%")
            print(f"   • Μέγιστη έκθεση: {max_exposure:.2f}%")
        
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
            'price_data': df,
            'liquidation_occurred': liquidated,
            'min_distance_to_liq': min_distance,
            'avg_distance_to_liq': avg_distance,
            'max_exposure': max_exposure,
            'liquidation_warnings': warnings,
            'liq_history': liq_df
        }
    
    def run_multi_backtest(self) -> Dict:
        results = {}
        for coin in self.config['test_coins']:
            result = self.run_backtest(coin)
            results[coin] = result
        return results