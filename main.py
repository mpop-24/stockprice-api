from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime
import requests
import time
import os

app = FastAPI(title="Stock Price API")
API_KEY = os.getenv("FINNHUB_API_KEY", "your_finnhub_api_key")
BASE_URL = "https://finnhub.io/api/v1/quote"

INDEX_TO_ETF = {
    "^DJI": "DIA",
    "^GSPC": "SPY",
    "^IXIC": "QQQ",
    "^RUT": "IWM"
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://financecalculate.com"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

last_prices: Dict[str, float] = {}

class TickerData(BaseModel):
    ticker: str
    current_price: float
    price_change: str | None
    percentage_change: float | None  # New field for percentage change
    timestamp: str

@app.get("/tickers/{tickers}", response_model=List[TickerData])
async def get_tickers_data(tickers: str):
    try:
        ticker_list = [t.strip().upper() for t in tickers.split(",")]
        results = []
        failed_tickers = []

        for ticker in ticker_list:
            if ticker == "AAPL":
                failed_tickers.append(ticker)
                continue

            symbol = INDEX_TO_ETF.get(ticker, ticker)

            for attempt in range(3):
                try:
                    url = f"{BASE_URL}?symbol={symbol}&token={API_KEY}"
                    response = requests.get(url).json()
                    price = response.get("c") or response.get("pc")
                    if price is None or price == 0:
                        failed_tickers.append(ticker)
                        break

                    price_change = None
                    percentage_change = None
                    if ticker in last_prices:
                        previous_price = last_prices[ticker]
                        if previous_price != 0:
                            percentage_change = ((price - previous_price) / previous_price) * 100
                            if price > previous_price:
                                price_change = "up"
                            elif price < previous_price:
                                price_change = "down"
                            else:
                                price_change = "flat"
                        else:
                            percentage_change = 0  # Avoid division by zero

                    last_prices[ticker] = price

                    results.append({
                        "ticker": ticker,
                        "current_price": price,
                        "price_change": price_change,
                        "percentage_change": round(percentage_change, 2) if percentage_change is not None else None,
                        "timestamp": datetime.now().isoformat()
                    })
                    time.sleep(1)
                    break
                except Exception as e:
                    if "429" in str(e) or "Too Many Requests" in str(e):
                        if attempt < 2:
                            time.sleep(5 * (2 ** attempt))
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
