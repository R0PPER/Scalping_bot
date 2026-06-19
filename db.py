import os
import json
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

# Load environment variables
load_dotenv()

# Initialize Firebase Admin SDK
USE_FIRESTORE = False
IN_MEMORY_TRADES = []
IN_MEMORY_POSITIONS = {}
IN_MEMORY_STATE = {}
db = None

firebase_creds_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")

if firebase_creds_json:
    try:
        # Try to parse the service account key from JSON string
        cred_dict = json.loads(firebase_creds_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        USE_FIRESTORE = True
        db = firestore.client()
        print("🔥 Firebase initialized successfully!")
    except Exception as e:
        print(f"⚠️ Firebase initialization failed: {e}")
        print("💡 Falling back to in-memory storage for local testing!")
else:
    print("⚠️ FIREBASE_SERVICE_ACCOUNT_KEY not set! Using in-memory storage!")

# --- Helper functions for both Firestore and in-memory ---

def get_collection_ref(collection_name: str):
    if USE_FIRESTORE:
        return db.collection(collection_name)
    return None

# --- Bot state management ---
def init_bot_state(symbol: str, initial_capital: float):
    if USE_FIRESTORE:
        doc_ref = get_collection_ref("bot_state").document(symbol)
        if not doc_ref.get().exists:
            doc_ref.set({
                "capital": initial_capital,
                "entry_counter": 0,
                "updated_at": datetime.now()
            })
    else:
        if symbol not in IN_MEMORY_STATE:
            IN_MEMORY_STATE[symbol] = {
                "capital": initial_capital,
                "entry_counter": 0
            }

def get_bot_state(symbol: str) -> Optional[Dict]:
    if USE_FIRESTORE:
        doc = get_collection_ref("bot_state").document(symbol).get()
        if doc.exists:
            return doc.to_dict()
        return None
    else:
        return IN_MEMORY_STATE.get(symbol)

def update_bot_state(symbol: str, capital: float, entry_counter: int):
    if USE_FIRESTORE:
        get_collection_ref("bot_state").document(symbol).set({
            "capital": capital,
            "entry_counter": entry_counter,
            "updated_at": datetime.now()
        }, merge=True)
    else:
        IN_MEMORY_STATE[symbol] = {
            "capital": capital,
            "entry_counter": entry_counter
        }

# --- Trades management ---
def add_trade(symbol: str, trade_type: str, price: float, quantity: float,
              notional: float, entry_index: int = None, profit: float = None):
    trade_data = {
        "symbol": symbol,
        "type": trade_type,
        "price": price,
        "quantity": quantity,
        "notional": notional,
        "profit": profit,
        "entry_index": entry_index,
        "timestamp": datetime.now()
    }
    
    if USE_FIRESTORE:
        get_collection_ref("trades").add(trade_data)
    else:
        IN_MEMORY_TRADES.append(trade_data)

def get_trades(symbol: str = None, limit: int = 100) -> List[Dict]:
    if USE_FIRESTORE:
        query = get_collection_ref("trades").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)
        if symbol:
            query = query.where("symbol", "==", symbol)
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
    else:
        filtered = [t for t in IN_MEMORY_TRADES if symbol is None or t["symbol"] == symbol]
        filtered.sort(key=lambda x: x["timestamp"], reverse=True)
        return filtered[:limit]

# --- Open positions management ---
def add_open_position(symbol: str, entry_price: float, quantity: float, margin: float,
                      notional: float, entry_index: int, leverage: int):
    position_data = {
        "symbol": symbol,
        "entry_price": entry_price,
        "quantity": quantity,
        "margin": margin,
        "notional": notional,
        "entry_index": entry_index,
        "entry_timestamp": datetime.now(),
        "leverage": leverage
    }
    
    if USE_FIRESTORE:
        doc_id = f"{symbol}_{entry_index}"
        get_collection_ref("open_positions").document(doc_id).set(position_data)
    else:
        if symbol not in IN_MEMORY_POSITIONS:
            IN_MEMORY_POSITIONS[symbol] = []
        IN_MEMORY_POSITIONS[symbol].append(position_data)

def get_open_positions(symbol: str) -> List[Dict]:
    if USE_FIRESTORE:
        docs = get_collection_ref("open_positions").where("symbol", "==", symbol).order_by("entry_index").stream()
        return [doc.to_dict() for doc in docs]
    else:
        return IN_MEMORY_POSITIONS.get(symbol, [])

def close_open_position(symbol: str, entry_index: int):
    if USE_FIRESTORE:
        doc_id = f"{symbol}_{entry_index}"
        get_collection_ref("open_positions").document(doc_id).delete()
    else:
        if symbol in IN_MEMORY_POSITIONS:
            IN_MEMORY_POSITIONS[symbol] = [p for p in IN_MEMORY_POSITIONS[symbol] if p["entry_index"] != entry_index]

def close_all_open_positions(symbol: str):
    if USE_FIRESTORE:
        docs = get_collection_ref("open_positions").where("symbol", "==", symbol).stream()
        for doc in docs:
            doc.reference.delete()
    else:
        IN_MEMORY_POSITIONS[symbol] = []
