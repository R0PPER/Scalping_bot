# strategy.py - FIXED: leverage-consistent PnL, target_move δεν είναι hardcoded πια
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

        self.leverage = config['leverage']
        self.target_move = config.get('target_move', 0.018)
        self.entry_spacing_up = config.get('entry_spacing_up', 0.005)
        self.entry_spacing_down = config.get('entry_spacing_down', 0.002)

        # Πόσο % του ΣΥΝΟΛΙΚΟΥ κεφαλαίου (όχι σταθερό $) μπαίνει ως margin ανά θέση.
        # Αυτό κρατάει τη στρατηγική σωστή ανεξάρτητα από το αν ξεκινάμε με 300$ ή 3000$.
        self.margin_fraction = config.get('margin_fraction', 0.01)  # 1% του capital ανά entry
        self.min_margin = config.get('min_margin', 0.50)  # ελάχιστο $ ανά θέση

        # 🔑 HARD CAP: μέγιστο συνολικό notional exposure σε σχέση με το capital.
        # Χωρίς αυτό, σε σταθερές μονόπλευρες κινήσεις (ακόμα και ανοδικές) το bot
        # στοιβάζει εκατοντάδες θέσεις και φτάνει σε liquidation πολύ πριν από
        # οποιοδήποτε "μεγάλο crash". Αυτό πιθανότατα είναι το πραγματικό μυστικό
        # πίσω από bots τύπου Buick: δεν αντέχουν τα drops επειδή κάνουν μαγικά,
        # αντέχουν επειδή ΣΤΑΜΑΤΑΝΕ να ανοίγουν νέες θέσεις όταν το exposure
        # ξεπεράσει ένα όριο.
        self.max_exposure_ratio = config.get('max_exposure_ratio', 8.0)  # notional <= 8x capital

        # Liquidation tracking
        self.liquidation_warnings = []
        self.liquidation_occurred = False
        self.liquidation_price = 0
        self.liquidation_time = None
        self.min_distance_to_liq = 100
        self.max_exposure_percent = 0

    def calculate_entry(self, price: float, capital: float) -> Optional[Dict]:
        """
        Margin = % του τρέχοντος κεφαλαίου (όχι σταθερό $ ανεξάρτητο από capital).
        Notional = margin * leverage.
        """
        margin_per_position = max(capital * self.margin_fraction, self.min_margin)

        # Δεν ανοίγουμε θέση αν δεν έχουμε καθόλου διαθέσιμο κεφάλαιο
        if capital <= 0:
            return None

        notional = margin_per_position * self.leverage
        quantity = notional / price

        self.entry_counter += 1

        return {
            'entry_price': price,
            'quantity': quantity,
            'margin': margin_per_position,
            'leverage': self.leverage,
            'entry_index': self.entry_counter,
            'closed': False,
            'entry_time': None,  # ορίζεται από caller με το πραγματικό timestamp
            'notional': notional,
        }

    def should_enter(self, price: float, positions: List[Dict]) -> bool:
        """
        Δυναμικό entry spacing:
        - Άνοδος (price > last_entry): πιο αραιά ανοίγματα
        - Πτώση (price < last_entry): πιο πυκνά ανοίγματα (DCA grid)

        Επιπλέον: ΔΕΝ ανοίγει νέα θέση αν το συνολικό notional exposure
        ήδη ξεπερνά max_exposure_ratio * capital. Αυτό είναι το hard
        risk cap — χωρίς αυτό το exposure μεγαλώνει απεριόριστα.
        """
        open_positions = [p for p in positions if not p.get('closed', False)]

        if len(open_positions) >= self.config.get('max_entries', 300):
            return False

        total_notional = sum(p['notional'] for p in open_positions)
        if self.capital > 0 and total_notional >= self.max_exposure_ratio * self.capital:
            return False

        if not open_positions:
            return True

        last_entry = open_positions[-1]['entry_price']
        change = abs(price - last_entry) / last_entry

        if price > last_entry:
            required_change = self.entry_spacing_up
        else:
            required_change = self.entry_spacing_down

        return change >= required_change

    def calculate_exits(self, price: float, positions: List[Dict]) -> List[Dict]:
        """
        Κάθε θέση κλείνει ανεξάρτητα όταν η ΤΙΜΗ κινηθεί target_move% προς τα πάνω.
        Το ROI% (στο margin) είναι price_change * leverage * 100 — δεν είναι σταθερό 50,
        παίρνει το πραγματικό leverage από config.
        """
        exits = []
        open_positions = [p for p in positions if not p.get('closed', False)]

        for pos in open_positions:
            price_change = (price - pos['entry_price']) / pos['entry_price']

            if price_change >= self.target_move:
                profit = pos['notional'] * price_change
                roi = price_change * pos['leverage'] * 100

                exits.append({
                    'position': pos,
                    'close_amount': pos['notional'],
                    'profit': profit,
                    'price_change': price_change,
                    'entry_index': pos['entry_index'],
                    'entry_price': pos['entry_price'],
                    'roi': roi,
                })
                pos['closed'] = True

        return exits

    def calculate_unrealized_pnl(self, price: float, positions: List[Dict]) -> float:
        """
        ΣΩΣΤΟ unrealized PnL: notional (= margin*leverage) * price_change.
        ΟΧΙ base_amount/entry_price χωρίς leverage, που υποτιμούσε το ρίσκο.
        """
        unrealized = 0.0
        for pos in positions:
            if not pos.get('closed', False):
                price_change = (price - pos['entry_price']) / pos['entry_price']
                unrealized += pos['notional'] * price_change
        return unrealized

    def get_liquidation_info(self, price: float, positions: List[Dict], equity: Optional[float] = None) -> Dict:
        """
        Cross margin liquidation βάσει του ΣΥΝΟΛΙΚΟΥ equity (capital + unrealized PnL
        όλων των ανοιχτών θέσεων), όχι μόνο του realized capital.
        """
        open_positions = [p for p in positions if not p.get('closed', False)]

        empty = {
            'avg_entry': 0, 'liq_price': 0, 'distance': 100, 'distance_percent': 100,
            'total_exposure': 0, 'open_positions': 0, 'exposure_percent': 0,
            'risk_ratio': 0, 'is_liquidated': False,
        }

        if not open_positions:
            return empty

        total_notional = sum(p['notional'] for p in open_positions)
        if total_notional == 0:
            return empty

        if equity is None:
            equity = self.capital

        avg_entry = sum(p['entry_price'] * p['notional'] for p in open_positions) / total_notional
        total_quantity = sum(p['quantity'] for p in open_positions)

        maintenance_rate = 0.005  # Binance-like ~0.4-0.5% για τα coins αυτά στο 50x bracket
        total_maintenance = total_notional * maintenance_rate

        # Διαθέσιμο "cushion" πάνω από maintenance margin, βάσει ΤΡΕΧΟΝΤΟΣ equity
        available_cushion = equity - total_maintenance

        if total_quantity > 0:
            max_loss_per_unit = available_cushion / total_quantity
            liq_price = avg_entry - max_loss_per_unit
        else:
            liq_price = avg_entry * 0.98

        liq_price = max(liq_price, 0)

        distance = (price - liq_price) / liq_price * 100 if liq_price > 0 else 100
        exposure_percent = (total_notional / self.capital * 100) if self.capital > 0 else float('inf')
        loss_at_liquidation = (avg_entry - liq_price) / avg_entry * total_notional if avg_entry > 0 else 0
        risk_ratio = (loss_at_liquidation / self.capital * 100) if self.capital > 0 else float('inf')
        is_liquidated = price <= liq_price

        if distance < self.min_distance_to_liq:
            self.min_distance_to_liq = distance
        if exposure_percent > self.max_exposure_percent:
            self.max_exposure_percent = exposure_percent

        if is_liquidated:
            self.liquidation_occurred = True
            self.liquidation_price = price

        if 0 < distance < 5:
            self.liquidation_warnings.append({
                'price': price,
                'avg_entry': avg_entry,
                'liq_price': liq_price,
                'distance': distance,
                'open_positions': len(open_positions),
                'total_exposure': total_notional,
                'exposure_percent': exposure_percent,
                'risk_ratio': risk_ratio,
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
            'is_liquidated': is_liquidated,
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

        return drop > abs(self.config.get('emergency_stop', -0.30))

    def update_capital(self, profit: float):
        self.capital += profit
        self.equity_curve.append(self.capital)
        return self.capital