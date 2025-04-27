from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime
import requests
import time
import os
API_KEY = os.getenv("FINNHUB_API_KEY", "your_finnhub_api_key")  # Fallback for local testing
app = FastAPI(title="Stock Price API")
API_KEY = "d06lpapr01qg26s8oragd06lpapr01qg26s8orb0"  # Replace with your Finnhub API key
BASE_URL = "https://finnhub.io/api/v1/quote"

# Map index tickers to ETF proxies
INDEX_TO_ETF = {
    "^DJI": "DIA",
    "^GSPC": "SPY",
    "^IXIC": "QQQ",
    "^RUT": "IWM"
}

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://your-project.pages.dev"],  # Update with Cloudflare Pages URL
    allow_methods=["GET"],
    allow_headers=["*"],
)

# In-memory storage for last prices (used for price change)
last_prices: Dict[str, float] = {}

# Response model
class TickerData(BaseModel):
    ticker: str
    current_price: float
    price_change: str | None  # "up", "down", "flat", or null
    timestamp: str

@app.get("/tickers/{tickers}", response_model=List[TickerData])
async def get_tickers_data(tickers: str):
    try:
        ticker_list = [t.strip().upper() for t in tickers.split(",")]
        results = []
        failed_tickers = []

        for ticker in ticker_list:
            # Skip AAPL
            if ticker == "AAPL":
                failed_tickers.append(ticker)
                continue

            # Map index to ETF, or use ticker directly if not an index
            symbol = INDEX_TO_ETF.get(ticker, ticker)

            for attempt in range(3):  # Retry up to 3 times for rate limits
                try:
                    url = f"{BASE_URL}?symbol={symbol}&token={API_KEY}"
                    response = requests.get(url).json()
                    price = response.get("c") or response.get("pc")  # Current or previous close
                    if price is None or price == 0:
                        failed_tickers.append(ticker)
                        break

                    # Calculate price change
                    price_change = None
                    if ticker in last_prices:
                        previous_price = last_prices[ticker]
                        if price > previous_price:
                            price_change = "up"  # Price increased
                        elif price < previous_price:
                            price_change = "down"  # Price decreased
                        else:
                            price_change = "flat"  # Price unchanged

                    # Update last price for next comparison
                    last_prices[ticker] = price

                    results.append({
                        "ticker": ticker,  # Return index ticker, not ETF
                        "current_price": price,
                        "price_change": price_change,
                        "timestamp": datetime.now().isoformat()
                    })
                    time.sleep(1)  # Respect rate limits (60 requests/minute)
                    break
                except Exception as e:
                    if "429" in str(e) or "Too Many Requests" in str(e):  # Handle rate limit
                        if attempt < 2:
                            time.sleep(5 * (2 ** attempt))  # Backoff: 5s, 10s
                            continue
                        failed_tickers.append(ticker)
                    else:
                        failed_tickers.append(ticker)
                    break

        if not results:
            raise HTTPException(
                status_code=404,
                detail=f"No valid tickers found. Failed tickers: {', '.join(failed_tickers) or 'None'}"
            )

        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
