# backtest_engine.py - FIXED: equity curve με σωστό leveraged PnL,
# liquidation check πάνω στο live equity (όχι ξεχωριστό/ανεξάρτητο tracking)
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from typing import Dict, List, Optional, Any
import os
from strategy import BuickStrategy


class BacktestEngine:
    def __init__(self, config: Dict):
        self.config = config
        self.data_dir = "data"

    def load_local_data(self, symbol: str) -> pd.DataFrame:
        filename = f"{self.data_dir}/{symbol}_5m_30days.csv"

        if os.path.exists(filename):
            df = pd.read_csv(filename, index_col=0, parse_dates=True)
            print(f"✅ Φόρτωσα {len(df)} καντέλια για {symbol} από τοπικό αρχείο")
            print(f"   • Από: {df.index[0]} έως {df.index[-1]} "
                  f"({df.index[-1] - df.index[0]})")
            return df
        else:
            print(f"⚠️ Τοπικό αρχείο για {symbol} δεν βρέθηκε: {filename}")
            return pd.DataFrame()

    def fetch_data(self, symbol: str, days: int = 7) -> pd.DataFrame:
        """
        Φορτώνει local CSV. Αν τα data είναι ΛΙΓΟΤΕΡΑ από τα ζητούμενα 'days',
        χρησιμοποιεί ό,τι υπάρχει (δεν κάνει fallback σε synthetic - θέλουμε
        πάντα πραγματικά δεδομένα όταν υπάρχουν, ακόμα κι αν είναι λιγότερα).
        """
        df = self.load_local_data(symbol)

        if df.empty:
            raise FileNotFoundError(
                f"Δεν βρέθηκαν δεδομένα για {symbol} στο {self.data_dir}/. "
                f"Ανέβασε το {symbol}_5m_30days.csv."
            )

        available_span = df.index[-1] - df.index[0]
        requested_span = timedelta(days=days)

        if available_span < requested_span:
            print(f"   ⚠️ Ζητήθηκαν {days} μέρες αλλά υπάρχουν μόνο "
                  f"{available_span}. Χρησιμοποιώ ΟΛΑ τα διαθέσιμα δεδομένα.")
        else:
            cutoff = df.index[-1] - requested_span
            df = df[df.index >= cutoff]
            print(f"   • Περικοπή σε {days} μέρες: {df.index[0]} έως {df.index[-1]}")

        return df

    def run_backtest(self, symbol: str) -> Dict:
        print(f"\n🔄 Backtesting {symbol}...")

        df = self.fetch_data(symbol, self.config['test_days'])

        strategy = BuickStrategy(self.config)
        strategy.capital = self.config['initial_capital']

        positions = []
        trades = []
        equity_history = [strategy.capital]
        equity_timestamps = [df.index[0]]
        liq_history = []

        total_entries = 0
        total_exits = 0
        total_profit = 0.0
        liquidated = False
        liquidation_time = None
        liquidation_price = None
        min_distance_overall = 100.0
        max_exposure_overall = 0.0
        warning_count = 0

        for idx, row in df.iterrows():
            price = row['close']

            # 1. EXITS primero — κλείνουμε θέσεις που έφτασαν target
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
                    'roi': exit_order.get('roi', 0),
                })

            # 2. ENTRIES
            if strategy.should_enter(price, positions):
                entry = strategy.calculate_entry(price, strategy.capital)
                if entry is not None:
                    entry['entry_time'] = idx
                    positions.append(entry)
                    total_entries += 1

                    trades.append({
                        'timestamp': idx,
                        'type': 'ENTRY',
                        'price': price,
                        'margin': entry['margin'],
                        'notional': entry['notional'],
                        'entry_index': entry['entry_index'],
                        'symbol': symbol,
                    })

            # 3. ΣΩΣΤΟ unrealized PnL (με leverage) -> live equity
            unrealized = strategy.calculate_unrealized_pnl(price, positions)
            current_equity = strategy.capital + unrealized

            # 4. Liquidation check βάσει ΖΩΝΤΑΝΟΥ equity (όχι μόνο realized capital)
            liq_info = strategy.get_liquidation_info(price, positions, equity=current_equity)

            liq_history.append({
                'timestamp': idx,
                'price': price,
                'distance': liq_info['distance'],
                'exposure': liq_info['exposure_percent'],
                'open_positions': liq_info['open_positions'],
                'equity': current_equity,
            })

            if liq_info['distance'] < min_distance_overall:
                min_distance_overall = liq_info['distance']
            if liq_info['exposure_percent'] > max_exposure_overall and liq_info['exposure_percent'] != float('inf'):
                max_exposure_overall = liq_info['exposure_percent']
            if 0 < liq_info['distance'] < 5:
                warning_count += 1

            if liq_info['is_liquidated'] or current_equity <= 0:
                liquidated = True
                liquidation_time = idx
                liquidation_price = price
                print(f"💀 LIQUIDATION στο {symbol} στις {idx} με τιμή {price:.5f} "
                      f"(equity έπεσε στα ${current_equity:.2f})")
                strategy.capital = max(current_equity, 0)
                positions = []
                equity_history.append(strategy.capital)
                equity_timestamps.append(idx)
                break

            # 5. Emergency stop (πριν φτάσουμε σε liquidation, κλείνουμε όλα χειροκίνητα)
            if strategy.check_emergency(price, positions):
                print(f"⚠️ EMERGENCY STOP για {symbol} στο {price:.5f} "
                      f"({idx}) — κλείνω όλες τις ανοιχτές θέσεις")
                emergency_pnl = strategy.calculate_unrealized_pnl(price, positions)
                strategy.capital += emergency_pnl
                total_profit += emergency_pnl
                trades.append({
                    'timestamp': idx,
                    'type': 'EMERGENCY_EXIT',
                    'price': price,
                    'profit': emergency_pnl,
                    'symbol': symbol,
                })
                positions = []
                current_equity = strategy.capital

            equity_history.append(current_equity)
            equity_timestamps.append(idx)

        final_capital = strategy.capital if not liquidated else 0
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

        liq_df = pd.DataFrame(liq_history)

        print(f"\n📊 {symbol} | ROI: {roi:.2f}% | Trades(exits): {total_trades} | Entries: {total_entries}")
        print(f"   • Σύνολο κερδών: ${total_profit:.2f}")
        if total_trades > 0:
            print(f"   • Μέσο κέρδος/exit: ${total_profit/total_trades:.4f}")
        print(f"   • 🔥 LIQUIDATION: {'💀 ΝΑΙ' if liquidated else '✅ ΟΧΙ'}")
        print(f"   • Ελάχιστη απόσταση από liq: {min_distance_overall:.2f}%")
        print(f"   • Μέγιστη έκθεση (notional/capital): {max_exposure_overall:.2f}%")
        print(f"   • Warnings (<5% από liq): {warning_count}")

        return {
            'symbol': symbol,
            'initial_capital': self.config['initial_capital'],
            'final_capital': final_capital,
            'total_profit': total_profit,
            'roi': roi,
            'total_trades': total_trades,
            'entries': total_entries,
            'trades_df': trades,
            'entries_df': entries_df,
            'exits_df': exits_df,
            'equity_history': equity_history,
            'equity_timestamps': equity_timestamps,
            'price_data': df,
            'liquidation_occurred': liquidated,
            'liquidation_time': liquidation_time,
            'liquidation_price': liquidation_price,
            'min_distance_to_liq': min_distance_overall,
            'max_exposure': max_exposure_overall,
            'liquidation_warnings': warning_count,
            'liq_history': liq_df,
        }

    def run_multi_backtest(self) -> Dict:
        results = {}
        for coin in self.config['test_coins']:
            result = self.run_backtest(coin)
            results[coin] = result
        return results