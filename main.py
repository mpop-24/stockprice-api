from fastapi import FastAPI, HTTPException
import yfinance as yf

app = FastAPI()

@app.get("/price/{ticker}")
async def get_stock_price(ticker: str):
    try:
        # Fetch ticker data
        stock = yf.Ticker(ticker)
        info = stock.info

        # Extract current price and previous close (works for indices like ^GSPC or ^DJI)
        current_price = info.get('regularMarketPrice') or info.get('currentPrice')
        previous_close = info.get('regularMarketPreviousClose')

        if current_price is None or previous_close is None:
            # Fallback to history if info doesn't have it (e.g., after hours)
            hist = stock.history(period="2d")
            if len(hist) < 2:
                raise HTTPException(status_code=404, detail="Insufficient data for this ticker.")
            current_price = hist['Close'].iloc[-1]
            previous_close = hist['Close'].iloc[-2]

        # Compute change
        price_change = current_price - previous_close
        price_change_percent = (price_change / previous_close * 100) if previous_close != 0 else 0

        return {
            "ticker": ticker.upper(),
            "current_price": round(current_price, 2),
            "previous_close": round(previous_close, 2),
            "price_change": round(price_change, 2),
            "price_change_percent": round(price_change_percent, 2)
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching data: {str(e)}")
