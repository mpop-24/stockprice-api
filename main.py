from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache
import requests
import os
import time

app = FastAPI()

# CORS for financecalculate.com
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://financecalculate.com"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Initialize in-memory cache
@app.on_event("startup")
async def startup():
    FastAPICache.init(InMemoryBackend())

@app.get("/price/{ticker}")
@cache(expire=300)  # Cache for 5 minutes to reduce API calls
async def get_stock_price(ticker: str):
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="API key not configured")

    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={api_key}"

    # Retry logic: Try up to 3 times with backoff for rate limits or transient errors
    for attempt in range(3):
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise if not 200 OK
            data = response.json()

            if "Global Quote" not in data or not data["Global Quote"]:
                raise HTTPException(status_code=404, detail="Ticker not found or insufficient data")

            quote = data["Global Quote"]
            current_price = float(quote.get("05. price", 0))
            previous_close = float(quote.get("08. previous close", 0))
            price_change = float(quote.get("09. change", 0))
            price_change_percent = float(quote.get("10. change percent", "0%").strip("%"))

            return {
                "ticker": ticker.upper(),
                "current_price": round(current_price, 2),
                "previous_close": round(previous_close, 2),
                "price_change": round(price_change, 2),
                "price_change_percent": round(price_change_percent, 2)
            }

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # Rate limit hit
                time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                continue
            raise HTTPException(status_code=400, detail=f"Error fetching data: {str(e)}")

        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error fetching data: {str(e)}")

    raise HTTPException(status_code=429, detail="Rate limit exceeded after retries")
