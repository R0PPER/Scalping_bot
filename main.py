# main.py - CORRECTED
import json
from backtest_engine import BacktestEngine
from visualizer import Visualizer
import pandas as pd
from datetime import datetime
import os

def main():
    print("="*60)
    print("🚀 BUICK BOT BACKTEST ENGINE")
    print("="*60)
    
    # Φόρτωση config
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ config.json not found! Creating default...")
        config = {
            "initial_capital": 680,
            "leverage": 50,
            "entry_spacing_up": 0.005,
            "entry_spacing_down": 0.0005,
            "target_move": 0.02,
            "max_entries": 200,
            "max_drawdown": 0.30,
            "test_coins": ["ONDO", "HYPE"],
            "test_days": 7,
            "timeframe": "5m"
        }
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=4)
    
    print(f"\n📊 Config loaded:")
    print(f"   • Coins: {config['test_coins']}")
    print(f"   • Days: {config['test_days']}")
    print(f"   • Initial Capital: ${config['initial_capital']}")
    print(f"   • Leverage: {config['leverage']}x")
    
    # 🔥 ΕΜΦΑΝΙΣΗ ΚΑΙ ΤΩΝ ΔΥΟ SPACINGS
    if 'entry_spacing_up' in config and 'entry_spacing_down' in config:
        print(f"   • Entry Spacing (Άνοδος): {config['entry_spacing_up']*100:.2f}%")
        print(f"   • Entry Spacing (Πτώση): {config['entry_spacing_down']*100:.2f}%")
    else:
        # Fallback για παλιά config
        entry_spacing = config.get('entry_spacing', 0.001)
        print(f"   • Entry Spacing: {entry_spacing*100:.2f}%")
    
    # Εκτέλεση backtest
    engine = BacktestEngine(config)
    results = engine.run_multi_backtest()
    
    # Εκτύπωση αποτελεσμάτων
    print("\n" + "="*60)
    print("📈 BACKTEST RESULTS")
    print("="*60)
    
    for coin, result in results.items():
        print(f"\n🪙 {coin}:")
        print(f"   • Initial: ${result['initial_capital']:,.2f}")
        print(f"   • Final:   ${result['final_capital']:,.2f}")
        print(f"   • Profit:  ${result['total_profit']:,.2f}")
        print(f"   • ROI:     {result['roi']:.2f}%")
        print(f"   • Trades:  {result['total_trades']}")
        print(f"   • Entries: {result['entries']}")
        if 'min_distance_to_liq' in result:
            print(f"   • Min Distance to Liq: {result['min_distance_to_liq']:.2f}%")
        if 'max_exposure' in result:
            print(f"   • Max Exposure: {result['max_exposure']:.2f}%")
    
    # Δημιουργία γραφημάτων
    viz = Visualizer()
    
    print("\n" + "="*60)
    print("📊 Generating Charts...")
    print("="*60)
    
    for coin in config['test_coins']:
        print(f"   • {coin} chart...")
        try:
            viz.plot_backtest_results(results, coin)
        except Exception as e:
            print(f"   ⚠️ Error plotting {coin}: {e}")
    
    # Comparison chart
    print("   • Comparison chart...")
    try:
        viz.plot_multi_comparison(results)
    except Exception as e:
        print(f"   ⚠️ Error plotting comparison: {e}")
    
    # Αποθήκευση raw δεδομένων
    print("\n💾 Saving raw data...")
    for coin, result in results.items():
        try:
            trades_df = pd.DataFrame(result['trades_df'])
            trades_df.to_csv(f'{coin}_trades.csv', index=False)
            print(f"   • {coin}_trades.csv saved")
        except Exception as e:
            print(f"   ⚠️ Error saving {coin}: {e}")
    
    print("\n✅ Backtest complete!")
    print(f"📁 Files saved: ")
    for coin in config['test_coins']:
        print(f"   • {coin}_backtest_results.png")
    print(f"   • multi_coin_comparison.png")
    print(f"   • *_trades.csv")
    
    return results

if __name__ == "__main__":
    results = main()