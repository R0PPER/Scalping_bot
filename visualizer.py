# visualizer.py - CORRECTED
import matplotlib.pyplot as plt
import pandas as pd
import matplotlib.dates as mdates
from datetime import datetime
from typing import Dict, List, Optional, Any

class Visualizer:
    def __init__(self):
        plt.style.use('dark_background')
        
    def plot_backtest_results(self, results: Dict, coin: str):
        """Δημιουργεί το γράφημα με entries/exits"""
        result = results[coin]
        
        if result['price_data'].empty:
            print(f"⚠️ Δεν υπάρχουν δεδομένα για {coin}")
            return
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))
        fig.suptitle(f'{coin} - Buick Strategy (LIFO DCA Grid)', fontsize=16, color='white')
        
        # Plot 1: Price with entries/exits
        price_data = result['price_data']
        ax1.plot(price_data.index, price_data['close'], label='Price', color='cyan', alpha=0.7, linewidth=1)
        
        # Entries (green triangles)
        if not result['entries_df'].empty:
            entry_times = pd.to_datetime(result['entries_df']['time'])
            entry_prices = result['entries_df']['price']
            ax1.scatter(entry_times, entry_prices, color='lime', s=30, marker='^', 
                       label=f'Entries ({len(entry_times)})', zorder=5, alpha=0.8)
        
        # Exits (red triangles)
        if not result['exits_df'].empty:
            exit_times = pd.to_datetime(result['exits_df']['time'])
            exit_prices = result['exits_df']['price']
            ax1.scatter(exit_times, exit_prices, color='red', s=50, marker='v',
                       label=f'Exits ({len(exit_times)})', zorder=5, alpha=0.8)
        
        ax1.set_ylabel('Price', color='white')
        ax1.legend(loc='upper left')
        ax1.grid(alpha=0.2)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
        
        # Plot 2: Equity Curve
        equity = result['equity_history']
        ax2.plot(equity, color='lime', linewidth=2, label='Equity')
        ax2.axhline(y=result['initial_capital'], color='gray', linestyle='--', 
                   alpha=0.5, label='Initial Capital')
        
        final = equity[-1] if equity else result['initial_capital']
        profit_pct = ((final - result['initial_capital']) / result['initial_capital']) * 100
        
        ax2.text(0.02, 0.95, f'Final: ${final:,.2f}\nROI: {profit_pct:.2f}%', 
                transform=ax2.transAxes, color='white', fontsize=12,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='black', alpha=0.7))
        
        ax2.set_ylabel('Equity ($)', color='white')
        ax2.set_xlabel('Trade #', color='white')
        ax2.legend(loc='upper left')
        ax2.grid(alpha=0.2)
        
        plt.tight_layout()
        plt.savefig(f'{coin}_backtest_results.png', dpi=150, facecolor='black')
        plt.show()
        
        return fig
    
    def plot_multi_comparison(self, results: Dict):
        """Σύγκριση αποτελεσμάτων"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Buick Strategy - Multi Coin Comparison', fontsize=16, color='white')
        
        coins = list(results.keys())
        for idx, coin in enumerate(coins):
            row = idx // 2
            col = idx % 2
            
            ax = axes[row, col]
            result = results[coin]
            
            if result['price_data'].empty:
                ax.text(0.5, 0.5, f'No data for {coin}', ha='center', va='center', color='white')
                continue
            
            price_data = result['price_data']
            ax.plot(price_data.index, price_data['close'], color='cyan', alpha=0.7, linewidth=1)
            
            if not result['entries_df'].empty:
                entry_times = pd.to_datetime(result['entries_df']['time'])
                entry_prices = result['entries_df']['price']
                ax.scatter(entry_times, entry_prices, color='lime', s=20, marker='^', alpha=0.6)
            
            if not result['exits_df'].empty:
                exit_times = pd.to_datetime(result['exits_df']['time'])
                exit_prices = result['exits_df']['price']
                ax.scatter(exit_times, exit_prices, color='red', s=20, marker='v', alpha=0.6)
            
            final = result['final_capital']
            roi = result['roi']
            trades = result['total_trades']
            
            ax.set_title(f'{coin} | ROI: {roi:.2f}% | Trades: {trades}', color='white')
            ax.grid(alpha=0.2)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        
        for idx in range(len(coins), 4):
            row = idx // 2
            col = idx % 2
            axes[row, col].axis('off')
        
        plt.tight_layout()
        plt.savefig('multi_coin_comparison.png', dpi=150, facecolor='black')
        plt.show()