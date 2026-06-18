# config.py
import json

CONFIG = {
    # Βασικές παράμετροι
    "initial_capital": 300,  # $ όπως ο Buick
    "max_capital": 680,      # τρέχον κεφάλαιο
    "leverage": 50,          # όσο δείχνει η φωτογραφία
    
    # Παράμετροι Entry
    "entry_spacing": 0.003,  # 0.3% κάθε dip (από την ανάλυσή μας)
    "base_position": 0.005,  # 0.5% του capital ανά entry
    "max_entries": 100,      # μαξ θέσεις
    
    # Risk Management
    "max_exposure": 0.25,    # 25% του κεφαλαίου
    "max_drawdown": 0.35,    # αντέχει -35%
    "liquidation_buffer": 0.10, # extra safety
    
    # Exit Logic (όπως Buick)
    "tp1": 0.008,   # +0.8% κλείνει 20%
    "tp1_close": 0.20,
    "tp2": 0.015,   # +1.5% κλείνει 30%
    "tp2_close": 0.30,
    "tp3": 0.025,   # +2.5% κλείνει υπόλοιπο
    "tp3_close": 0.50,
    
    # Συνθήκες backtest
    "test_coins": ["ONDO", "HYPE"],
    "test_days": 7,
    "timeframe": "5m",
    
    # Safety
    "emergency_stop": -0.40, # -40% stop all
}

# Αποθήκευση για χρήση
with open('config.json', 'w') as f:
    json.dump(CONFIG, f, indent=4)