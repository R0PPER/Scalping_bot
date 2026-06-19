import json
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from binance.client import Client

from strategy import BuickStrategy
import db

# Load config
with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

# Binance client (paper trading uses testnet or just real prices with virtual capital)
BINANCE_CLIENT = Client()

# Initialize strategy instances per coin
STRATEGIES: Dict[str, BuickStrategy] = {}


def load_strategy_from_db(symbol: str):
    state = db.get_bot_state(symbol)
    if state:
        strategy = BuickStrategy(CONFIG)
        strategy.capital = state["capital"]
        strategy.entry_counter = state["entry_counter"]
        
        # Load open positions from DB
        open_positions = db.get_open_positions(symbol)
        for pos in open_positions:
            strategy.positions.append({
                "entry_price": pos["entry_price"],
                "quantity": pos["quantity"],
                "margin": pos["margin"],
                "leverage": pos["leverage"],
                "entry_index": pos["entry_index"],
                "closed": False,
                "notional": pos["notional"],
            })
        
        return strategy
    else:
        # Initialize fresh
        db.init_bot_state(symbol, CONFIG["initial_capital"])
        return BuickStrategy(CONFIG)


def get_current_price(symbol: str) -> float:
    # Get real-time price from Binance spot/futures (use futures for consistency)
    ticker = BINANCE_CLIENT.futures_symbol_ticker(symbol=symbol)
    return float(ticker["price"])


async def process_coin(symbol: str):
    strategy = STRATEGIES[symbol]
    price = get_current_price(symbol)
    
    # Get current open positions from strategy
    open_positions = [p for p in strategy.positions if not p.get("closed", False)]
    
    # --- 1. EXITS ---
    exits = strategy.calculate_exits(price, strategy.positions)
    for exit_order in exits:
        pos = exit_order["position"]
        profit = exit_order["profit"]
        
        # Update capital
        strategy.update_capital(profit)
        
        # Save trade to DB
        db.add_trade(
            symbol=symbol,
            trade_type="EXIT",
            price=price,
            quantity=pos["quantity"],
            notional=pos["notional"],
            entry_index=pos["entry_index"],
            profit=profit
        )
        
        # Remove from open positions in DB
        db.close_open_position(symbol, pos["entry_index"])
    
    # --- 2. ENTRIES ---
    if strategy.should_enter(price, strategy.positions):
        entry = strategy.calculate_entry(price, strategy.capital)
        if entry:
            # Add to strategy
            strategy.positions.append(entry)
            
            # Save to DB
            db.add_open_position(
                symbol=symbol,
                entry_price=entry["entry_price"],
                quantity=entry["quantity"],
                margin=entry["margin"],
                notional=entry["notional"],
                entry_index=entry["entry_index"],
                leverage=entry["leverage"]
            )
            db.add_trade(
                symbol=symbol,
                trade_type="ENTRY",
                price=price,
                quantity=entry["quantity"],
                notional=entry["notional"],
                entry_index=entry["entry_index"]
            )
    
    # Update state in DB
    db.update_bot_state(symbol, strategy.capital, strategy.entry_counter)


async def bot_loop():
    """Main bot background loop, runs every 10 seconds!"""
    print("🚀 Bot loop started!")
    while True:
        try:
            for symbol in CONFIG["test_coins"]:
                await process_coin(symbol)
            
            # Print current stats every 60 seconds
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            total_equity = 0.0
            total_open_positions = 0
            for symbol in CONFIG["test_coins"]:
                strat = STRATEGIES[symbol]
                open_pos = [p for p in strat.positions if not p.get("closed", False)]
                current_price = get_current_price(symbol)
                unrealized_pnl = strat.calculate_unrealized_pnl(current_price, strat.positions)
                equity = strat.capital + unrealized_pnl
                
                total_equity += equity
                total_open_positions += len(open_pos)
            
            print(f"[{now}] Total Equity: ${total_equity:.2f} | Open Positions: {total_open_positions}")
            
            await asyncio.sleep(10)
        except Exception as e:
            print(f"⚠️ Error in bot loop: {e}")
            await asyncio.sleep(10)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load strategies
    for symbol in CONFIG["test_coins"]:
        STRATEGIES[symbol] = load_strategy_from_db(symbol)
    
    # Start background loop
    asyncio.create_task(bot_loop())
    
    yield
    
    # Shutdown: Nothing to do for now
    print("🛑 Bot shutting down...")


app = FastAPI(lifespan=lifespan)


# --- API ENDPOINTS ---

@app.get("/")
async def root():
    return {"message": "Buick Bot Paper Trading API", "version": "1.0"}


@app.get("/api/stats")
async def get_stats():
    total_initial = 0.0
    total_equity = 0.0
    total_open_positions = 0
    stats = {}
    
    for symbol in CONFIG["test_coins"]:
        state = db.get_bot_state(symbol)
        strategy = STRATEGIES[symbol]
        open_pos = [p for p in strategy.positions if not p.get("closed", False)]
        current_price = get_current_price(symbol)
        unrealized_pnl = strategy.calculate_unrealized_pnl(current_price, strategy.positions)
        equity = strategy.capital + unrealized_pnl
        liq_info = strategy.get_liquidation_info(current_price, strategy.positions, equity)
        
        stats[symbol] = {
            "capital": round(strategy.capital, 2),
            "equity": round(equity, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "open_positions": len(open_pos),
            "distance_to_liq": round(liq_info["distance"], 2),
            "max_exposure": round(strategy.max_exposure_percent, 2),
        }
        
        total_initial += CONFIG["initial_capital"]
        total_equity += equity
        total_open_positions += len(open_pos)
    
    total_roi = ((total_equity - total_initial) / total_initial * 100) if total_initial > 0 else 0.0
    
    return JSONResponse(content={
        "total": {
            "initial_capital": round(total_initial, 2),
            "equity": round(total_equity, 2),
            "roi": round(total_roi, 2),
            "total_open_positions": total_open_positions
        },
        "per_coin": stats
    })


@app.get("/api/trades")
async def get_trades(symbol: str = None, limit: int = 100):
    trades = db.get_trades(symbol, limit)
    # Convert timestamps to strings
    for t in trades:
        t["timestamp"] = t["timestamp"] if isinstance(t["timestamp"], str) else str(t["timestamp"])
    return JSONResponse(content=trades)


@app.get("/api/open_positions")
async def get_open_positions(symbol: str = None):
    if symbol:
        positions = db.get_open_positions(symbol)
    else:
        positions = []
        for s in CONFIG["test_coins"]:
            positions.extend(db.get_open_positions(s))
    
    # Convert timestamps
    for p in positions:
        p["entry_timestamp"] = p["entry_timestamp"] if isinstance(p["entry_timestamp"], str) else str(p["entry_timestamp"])
    return JSONResponse(content=positions)


@app.post("/api/reset/{symbol}")
async def reset_bot(symbol: str):
    if symbol not in CONFIG["test_coins"]:
        return JSONResponse(content={"error": "Invalid symbol"}, status_code=400)
    
    # Clear everything for this symbol
    db.close_all_open_positions(symbol)
    db.init_bot_state(symbol, CONFIG["initial_capital"])
    STRATEGIES[symbol] = BuickStrategy(CONFIG)
    
    return JSONResponse(content={"message": f"Bot for {symbol} reset successfully!"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
