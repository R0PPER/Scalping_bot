import numpy as np
import pandas as pd

class MarketSimulator:
    def __init__(self, start_price, volatility=0.01, drift=0):
        self.price = start_price
        self.volatility = volatility
        self.drift = drift

    def step(self):
        change = np.random.normal(self.drift, self.volatility)
        self.price *= (1 + change)
        return self.price


class Position:
    def __init__(self, entry, size, leverage):
        self.entry = entry
        self.size = size
        self.leverage = leverage
        self.closed = False
        self.pnl = 0


class BuickStyleBot:
    def __init__(self, start_capital=300, leverage=20):
        self.initial_capital = start_capital
        self.capital = start_capital
        self.leverage = leverage

        self.positions = []
        self.equity_curve = []
        self.peak = start_capital

    def open_position(self, price):
        size = self.capital * 0.01  # 1% per entry
        self.capital -= size

        pos = Position(price, size, self.leverage)
        self.positions.append(pos)

    def update_positions(self, price):
        total_equity = self.capital

        for p in self.positions:
            if p.closed:
                continue

            change = (price - p.entry) / p.entry
            pnl = p.size * self.leverage * change

            # partial take profit logic
            if change > 0.02:
                pnl *= 0.8
                p.closed = True
            elif change > 0.01:
                pnl *= 0.5
                p.closed = False

            total_equity += p.size + pnl

        return total_equity

    def step(self, price, last_price):
        drop = (price - last_price) / last_price

        # DCA logic
        if drop < -0.003:  # -0.3%
            self.open_position(price)

        equity = self.update_positions(price)

        self.peak = max(self.peak, equity)
        drawdown = (self.peak - equity) / self.peak

        self.equity_curve.append(equity)

        return equity, drawdown


def run_sim(symbol, days=7, steps=2000):
    if symbol == "ONDO":
        sim = MarketSimulator(0.37, volatility=0.015)
    else:
        sim = MarketSimulator(0.025, volatility=0.03)

    bot = BuickStyleBot(start_capital=300, leverage=20)

    price = sim.price
    last_price = price

    for _ in range(steps):
        price = sim.step()
        equity, dd = bot.step(price, last_price)
        last_price = price

    return {
        "symbol": symbol,
        "final_equity": bot.equity_curve[-1],
        "return_%": (bot.equity_curve[-1] / 300 - 1) * 100,
        "max_drawdown_%": max(bot.equity_curve)
    }


results = pd.DataFrame([
    run_sim("ONDO"),
    run_sim("HYPE")
])

print(results)