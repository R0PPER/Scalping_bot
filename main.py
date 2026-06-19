# main.py
import json
from backtest_engine import BacktestEngine
import pandas as pd
import sys
import io

# Fix encoding for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def main():
    print("=" * 60)
    print("BUICK BOT BACKTEST ENGINE")
    print("=" * 60)

    with open('config.json', 'r') as f:
        config = json.load(f)

    print(f"\nConfig:")
    print(f"   • Coins: {config['test_coins']}")
    print(f"   • Days requested: {config['test_days']}")
    print(f"   • Capital per coin: ${config['initial_capital']} "
          f"(x{len(config['test_coins'])} coins = ${config['initial_capital']*len(config['test_coins'])} total)")
    print(f"   • Leverage: {config['leverage']}x")
    print(f"   • Margin per entry: {config['margin_fraction']*100:.2f}% of capital "
          f"(min ${config['min_margin']})")
    print(f"   • Target move to exit: {config['target_move']*100:.2f}% "
          f"(~{config['target_move']*config['leverage']*100:.1f}% ROI on margin)")
    print(f"   • Entry spacing UP/DOWN: {config['entry_spacing_up']*100:.2f}% / "
          f"{config['entry_spacing_down']*100:.2f}%")

    engine = BacktestEngine(config)
    results = engine.run_multi_backtest()

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)

    total_initial = 0
    total_final = 0

    for coin, result in results.items():
        print(f"\n{coin}:")
        print(f"   • Initial: ${result['initial_capital']:,.2f}")
        print(f"   • Final:   ${result['final_capital']:,.2f}")
        print(f"   • Profit:  ${result['total_profit']:,.2f}")
        print(f"   • Fees:    ${result['total_fees']:,.2f}")
        print(f"   • ROI:     {result['roi']:.2f}%")
        print(f"   • Entries: {result['entries']} | Exits(trades): {result['total_trades']}")
        print(f"   • Liquidation: {'YES' if result['liquidation_occurred'] else 'NO'}")
        print(f"   • Min distance to liq: {result['min_distance_to_liq']:.2f}%")
        print(f"   • Max exposure: {result['max_exposure']:.2f}%")
        print(f"   • Warnings (<5% from liq): {result['liquidation_warnings']}")
        print(f"   • Max drawdown: {result['max_drawdown']:.2f}%")

        total_initial += result['initial_capital']
        total_final += result['final_capital']

    print(f"\nTOTAL (ONDO+HYPE):")
    print(f"   • Initial: ${total_initial:.2f}")
    print(f"   • Final:   ${total_final:.2f}")
    print(f"   • ROI:     {((total_final-total_initial)/total_initial)*100:.2f}%")

    print("\nSaving trade logs...")
    for coin, result in results.items():
        trades_df = pd.DataFrame(result['trades_df'])
        trades_df.to_csv(f'{coin}_trades.csv', index=False)
        result['liq_history'].to_csv(f'{coin}_liquidation_history.csv', index=False)
        print(f"   • {coin}_trades.csv, {coin}_liquidation_history.csv saved")

    print("\nBacktest complete!")
    return results


if __name__ == "__main__":
    results = main()