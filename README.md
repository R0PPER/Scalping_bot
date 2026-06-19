# Buick Bot - Paper Trading

Περιεχόμενα:
- Backtesting engine (main.py)
- Live paper trading bot (live_bot.py) with FastAPI
- Firebase Firestore database (or in-memory for local testing)
- Ready to deploy to Render (Free)

## Δομή Αρχείων:

```
buick/
├── config.json             # Strategy config
├── db.py                   # Firebase/Firestore DB helper (with in-memory fallback)
├── live_bot.py             # FastAPI live bot
├── main.py                 # Backtest script
├── strategy.py             # Core strategy logic
├── backtest_engine.py      # Backtesting engine
├── requirements.txt        # Dependencies
├── Procfile                # Render deployment config
├── .gitignore              # Git ignore rules
├── .env.example            # Example environment variables
└── README.md               # This file
```

## Firebase Setup (Required for Cloud Persistence):
1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Create a new project
3. Go to Project Settings → Service Accounts → Generate New Private Key
4. Save the JSON file
5. Copy the entire JSON content as a string for the environment variable

## Deploy to Render:

### 1. Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin [your-github-repo]
git push -u origin main
```

### 2. Create a new Web Service on Render
- Connect your GitHub account
- Select your repo
- Choose "Web Service"
- Add an Environment Variable:
  - Key: `FIREBASE_SERVICE_ACCOUNT_KEY`
  - Value: Paste your Firebase service account JSON (entire file as a single line string!)
- Set:
  - Runtime: Python 3
  - Build Command: `pip install -r requirements.txt`
  - Start Command: `uvicorn live_bot:app --host 0.0.0.0 --port $PORT`
  - Instance Type: Free

### 3. Deploy!
Render will auto-deploy on every git push!

## API Endpoints (on Render):
- `GET /` - Root page
- `GET /api/stats` - Total and per-coin stats (equity, PnL, open positions)
- `GET /api/trades` - Recent trades (pass ?symbol=ONDO to filter)
- `GET /api/open_positions` - Current open positions
- `POST /api/reset/{symbol}` - Reset bot for a specific coin

## Notes:
- Render Free Web Services will sleep after 15 mins of inactivity. To keep it awake, use a free service like UptimeRobot to ping your Render URL every 10-15 mins!
- The bot uses real-time Binance prices with virtual (paper) capital!
- No API keys needed for paper trading!
- If Firebase isn't configured, bot falls back to in-memory storage (data will reset on restart)
