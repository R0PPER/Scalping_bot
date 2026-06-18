# strategy.py - BUICK EXACT REPLICA (με $1 margin ανά θέση, δυναμικό spacing)
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
        self.total_withdrawn = 0
        
        # 🔥 Διαβάζει από config
        self.target_move = config.get('target_move', 0.018)  # 1.8% = ~90% ROI
        self.entry_spacing_up = config.get('entry_spacing_up', 0.005)  # 0.5% σε άνοδο
        self.entry_spacing_down = config.get('entry_spacing_down', 0.002)  # 0.2% σε πτώση
        
        # Liquidation tracking
        self.liquidation_warnings = []
        self.liquidation_occurred = False
        self.liquidation_price = 0
        self.liquidation_time = None
        self.min_distance_to_liq = 100
        self.max_exposure_percent = 0
        
    def calculate_entry(self, price: float, capital: float) -> Dict:
        """
        🔥 ΣΩΣΤΟ position sizing (όπως ο Buick)
        Margin: $0.80-$1.20 ανά θέση (σταθερό, όχι % του κεφαλαίου)
        """
        # Σταθερό margin ~$1 ανά θέση (ανεξάρτητα από κεφάλαιο)
        if capital < 300:
            margin_per_position = 0.80
        elif capital < 500:
            margin_per_position = 0.90
        elif capital < 700:
            margin_per_position = 1.00
        elif capital < 1000:
            margin_per_position = 1.10
        else:
            margin_per_position = 1.20
        
        # Notional = margin × leverage
        notional = margin_per_position * self.config['leverage']
        
        # Quantity = notional / price
        quantity = notional / price
        
        self.entry_counter += 1
        
        return {
            'entry_price': price,
            'quantity': quantity,
            'base_amount': notional,  # notional (όχι margin)
            'margin': margin_per_position,
            'leverage': self.config['leverage'],
            'entry_index': self.entry_counter,
            'closed': False,
            'entry_time': datetime.now(),
            'notional': notional
        }
    
    def should_enter(self, price: float, positions: List[Dict]) -> bool:
        """
        🔥 ΔΥΝΑΜΙΚΟ entry spacing:
        - Σε άνοδο (price > last_entry): ΑΡΑΙΑ (0.5%)
        - Σε πτώση (price < last_entry): ΠΥΚΝΑ (0.15%-0.30%)
        """
        open_positions = [p for p in positions if not p.get('closed', False)]
        
        # Μέγιστο 300 θέσεις (για να αντέχει -30%)
        if len(open_positions) >= self.config.get('max_entries', 300):
            return False
        
        if not open_positions:
            return True
        
        # Τελευταίο entry
        last_entry = open_positions[-1]['entry_price']
        
        # Υπολογισμός μεταβολής
        change = abs(price - last_entry) / last_entry
        
        # 🔥 ΔΥΝΑΜΙΚΟ SPACING
        if price > last_entry:
            # ΑΝΟΔΟΣ: Αραιά openings (0.5%)
            required_change = self.entry_spacing_up
        else:
            # ΠΤΩΣΗ: Πυκνά openings (0.2%)
            required_change = self.entry_spacing_down
        
        return change >= required_change
    
    def calculate_exits(self, price: float, positions: List[Dict]) -> List[Dict]:
        """
        🔥 Κάθε θέση κλείνει ΑΝΕΞΑΡΤΗΤΑ στο +1.8% (~90% ROI)
        """
        exits = []
        open_positions = [p for p in positions if not p.get('closed', False)]
        
        for pos in open_positions:
            price_change = (price - pos['entry_price']) / pos['entry_price']
            
            # 1.8% target → ~90% ROI με 50x
            if price_change >= self.target_move:
                # Κέρδος = notional × price_change
                profit = pos['notional'] * price_change
                roi = price_change * 50 * 100
                
                exits.append({
                    'position': pos,
                    'close_amount': pos['notional'],
                    'profit': profit,
                    'price_change': price_change,
                    'entry_index': pos['entry_index'],
                    'entry_price': pos['entry_price'],
                    'roi': roi
                })
                pos['closed'] = True
        
        return exits
    
    def get_liquidation_info(self, price: float, positions: List[Dict]) -> Dict:
        """Cross margin liquidation"""
        open_positions = [p for p in positions if not p.get('closed', False)]
        
        if not open_positions:
            return {
                'avg_entry': 0,
                'liq_price': 0,
                'distance': 100,
                'distance_percent': 100,
                'total_exposure': 0,
                'open_positions': 0,
                'risk_ratio': 0,
                'is_liquidated': False
            }
        
        total_notional = sum(p['notional'] for p in open_positions)
        if total_notional == 0:
            return {
                'avg_entry': 0,
                'liq_price': 0,
                'distance': 100,
                'distance_percent': 100,
                'total_exposure': 0,
                'open_positions': 0,
                'risk_ratio': 0,
                'is_liquidated': False
            }
        
        avg_entry = sum(p['entry_price'] * p['notional'] for p in open_positions) / total_notional
        
        # Cross margin liquidation
        maintenance_rate = 0.02
        total_maintenance = total_notional * maintenance_rate
        available_capital = self.capital - total_maintenance
        total_quantity = sum(p['quantity'] for p in open_positions)
        
        if total_quantity > 0 and available_capital > 0:
            max_loss = available_capital / total_quantity
            liq_price = avg_entry - max_loss
        else:
            liq_price = avg_entry * 0.98
        
        distance = (price - liq_price) / liq_price * 100 if liq_price > 0 else 100
        exposure_percent = (total_notional / self.capital) * 100
        loss_at_liquidation = (avg_entry - liq_price) / avg_entry * total_notional if avg_entry > 0 else 0
        risk_ratio = (loss_at_liquidation / self.capital) * 100
        is_liquidated = price <= liq_price
        
        if distance < self.min_distance_to_liq:
            self.min_distance_to_liq = distance
        
        if exposure_percent > self.max_exposure_percent:
            self.max_exposure_percent = exposure_percent
        
        if is_liquidated:
            self.liquidation_occurred = True
            self.liquidation_price = price
            self.liquidation_time = datetime.now()
        
        if distance < 5 and distance > 0:
            self.liquidation_warnings.append({
                'price': price,
                'avg_entry': avg_entry,
                'liq_price': liq_price,
                'distance': distance,
                'open_positions': len(open_positions),
                'total_exposure': total_notional,
                'exposure_percent': exposure_percent,
                'risk_ratio': risk_ratio,
                'timestamp': datetime.now()
            })
        
        return {
            'avg_entry': avg_entry,
            'liq_price': liq_price,
            'distance': distance,
            'distance_percent': distance,
            'total_exposure': total_notional,
            'open_positions': len(open_positions),
            'exposure_percent': exposure_percent,
            'risk_ratio': risk_ratio,
            'is_liquidated': is_liquidated
        }
    
    def check_emergency(self, price: float, positions: List[Dict]) -> bool:
        open_positions = [p for p in positions if not p.get('closed', False)]
        if not open_positions:
            return False
        
        total_notional = sum(p['notional'] for p in open_positions)
        if total_notional == 0:
            return False
            
        avg_entry = sum(p['entry_price'] * p['notional'] for p in open_positions) / total_notional
        drop = (avg_entry - price) / avg_entry
        
        if drop > 0.30:
            return True
        
        return False
    
    def calculate_liquidation(self, positions: List[Dict]) -> float:
        open_positions = [p for p in positions if not p.get('closed', False)]
        if not open_positions:
            return 0
        
        total_notional = sum(p['notional'] for p in open_positions)
        if total_notional == 0:
            return 0
            
        avg_entry = sum(p['entry_price'] * p['notional'] for p in open_positions) / total_notional
        
        maintenance_rate = 0.02
        total_maintenance = total_notional * maintenance_rate
        available_capital = self.capital - total_maintenance
        total_quantity = sum(p['quantity'] for p in open_positions)
        
        if total_quantity > 0 and available_capital > 0:
            max_loss = available_capital / total_quantity
            return avg_entry - max_loss
        else:
            return avg_entry * 0.98
    
    def update_capital(self, profit: float):
        self.capital += profit
        self.equity_curve.append(self.capital)
        return self.capital