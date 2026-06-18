# strategy.py - BUICK EXACT REPLICA (με calculate_entry)
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

class BuickStrategy:
    def __init__(self, config: Dict):
        self.config = config
        self.positions = []
        self.trades = []
        self.capital = config['initial_capital']
        self.equity_curve = [self.capital]
        self.entry_counter = 0
        self.total_profit = 0
        
        # Παράμετροι Buick
        self.target_roi = 92  # %
        self.target_move = 0.02  # 2% αύξηση
        self.entry_spacing = 0.001  # 0.1% πτώση
        
    def calculate_entry(self, price: float, capital: float) -> Dict:
        """
        Υπολογίζει το μέγεθος θέσης όπως ο Buick
        """
        # Buick χρησιμοποιεί σταθερό ποσό $30-50 ανά trade
        base_amount = min(50, max(30, capital / 10))
        
        # Αν το κεφάλαιο είναι μικρό, χρησιμοποιεί μικρότερα ποσά
        if capital < 100:
            base_amount = 20
        elif capital < 300:
            base_amount = 30
        else:
            base_amount = 50
        
        quantity = base_amount / price
        
        self.entry_counter += 1
        
        return {
            'entry_price': price,
            'quantity': quantity,
            'base_amount': base_amount,
            'margin': base_amount / self.config['leverage'],
            'leverage': self.config['leverage'],
            'entry_index': self.entry_counter,
            'closed': False,
            'entry_time': datetime.now(),
            'notional': base_amount  # Για συμβατότητα
        }
    
    def should_enter(self, price: float, positions: List[Dict]) -> bool:
        """
        Entry logic όπως ο Buick
        """
        open_positions = [p for p in positions if not p.get('closed', False)]
        
        # Μέγιστο 200 ανοιχτές θέσεις
        if len(open_positions) >= self.config.get('max_entries', 200):
            return False
        
        # Αν δεν υπάρχουν θέσεις, ανοίγει
        if not open_positions:
            return True
        
        # Τελευταίο entry
        last_entry = open_positions[-1]['entry_price']
        
        # Buick: ανοίγει όταν πέσει 0.1%-0.2%
        drop = (last_entry - price) / last_entry
        
        return drop >= self.entry_spacing
    
    def calculate_exits(self, price: float, positions: List[Dict]) -> List[Dict]:
        """
        Exit logic όπως ο Buick
        """
        exits = []
        open_positions = [p for p in positions if not p.get('closed', False)]
        
        # Buick: κλείνει όλες τις θέσεις ταυτόχρονα όταν φτάσει target
        for pos in open_positions:
            price_change = (price - pos['entry_price']) / pos['entry_price']
            
            # 2% target για 92% ROI με 50x
            if price_change >= self.target_move:
                profit = pos['base_amount'] * price_change
                
                exits.append({
                    'position': pos,
                    'close_amount': pos['base_amount'],
                    'profit': profit,
                    'price_change': price_change,
                    'entry_index': pos['entry_index']
                })
                pos['closed'] = True
        
        return exits
    
    def check_emergency(self, price: float, positions: List[Dict]) -> bool:
        """
        Buick: ΔΕΝ έχει stop loss, αλλά αντέχει μέχρι -30%
        """
        open_positions = [p for p in positions if not p.get('closed', False)]
        if not open_positions:
            return False
        
        # Weighted average entry
        total_amount = sum(p['base_amount'] for p in open_positions)
        if total_amount == 0:
            return False
            
        avg_entry = sum(p['entry_price'] * p['base_amount'] for p in open_positions) / total_amount
        
        # Πτώση από το weighted average
        drop = (avg_entry - price) / avg_entry
        
        # Buick αντέχει -30%
        if drop > 0.30:
            print(f"⚠️ BUICK LIQUIDATION: -{drop*100:.1f}% από weighted average")
            return True
        
        return False
    
    def reset_capital_if_needed(self):
        """
        Buick: Όταν φτάσει $600+, κρατά μόνο $300
        """
        if self.capital >= 600:
            self.total_profit += (self.capital - 300)
            self.capital = 300
            print(f"💰 BUICK RESET: ${self.capital} (κρατήθηκαν ${self.total_profit:.2f})")
    
    def calculate_roi(self, entry: float, exit: float) -> float:
        """
        ROI όπως το δείχνει η Bybit
        """
        change = (exit - entry) / entry
        roi = change * 50 * 100  # 50x leverage
        return roi * 0.975  # -2.5% fees
    
    def calculate_liquidation(self, positions: List[Dict]) -> float:
        """Weighted average entry για liquidation check"""
        open_positions = [p for p in positions if not p.get('closed', False)]
        if not open_positions:
            return 0
        
        total_amount = sum(p['base_amount'] for p in open_positions)
        if total_amount == 0:
            return 0
            
        avg_entry = sum(p['entry_price'] * p['base_amount'] for p in open_positions) / total_amount
        
        # 2% από το weighted average για 50x
        return avg_entry * 0.98
    
    def update_capital(self, profit: float):
        """Ενημέρωση κεφαλαίου"""
        self.capital += profit
        self.equity_curve.append(self.capital)
        return self.capital