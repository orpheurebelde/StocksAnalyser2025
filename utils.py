import os
import json
import yfinance as yf
from datetime import datetime, timedelta
import requests

CACHE_DIR = "cache"
CACHE_DURATION_HOURS = 24  # Cache data for 24 hours

os.makedirs(CACHE_DIR, exist_ok=True)

def get_cache_filepath(ticker):
    """Returns the file path for a specific stock's cache."""
    return os.path.join(CACHE_DIR, f"{ticker.upper()}_info.json")

def is_cache_valid(filepath):
    """Check if the cache file exists and is still valid (within 24 hours)."""
    if not os.path.exists(filepath):
        return False
    file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
    return datetime.now() - file_time < timedelta(hours=CACHE_DURATION_HOURS)

def fetch_and_cache_stock_info(ticker):
    """Fetch stock info using yfinance and cache the result."""
    ticker = ticker.upper()
    stock = yf.Ticker(ticker)
    
    try:
        info = stock.info
        # List of fields to cache
        fields = [
            "marketCap", "freeCashflow", "netIncomeToCommon", "grossMargins", "operatingMargins",
            "profitMargins", "earningsGrowth", "revenueGrowth", "dividendYield", "trailingPE", 
            "forwardPE", "pegRatio", "priceToBook", "priceToSalesTrailing12Months", "returnOnEquity",
            "epsCurrentYear", "forwardEps", "totalRevenue", "totalDebt", "totalCash", "heldPercentInstitutions",
            "heldPercentInsiders", "longBusinessSummary", "sector", "industry", "website", "fullTimeEmployees",
            "city", "state", "country", "logo_url", "symbol", "shortName"
        ]
        
        # Collect necessary data from the info
        data = {field: info.get(field, "N/A") for field in fields}
        
        # Save to cache
        with open(get_cache_filepath(ticker), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        
        return data
    
    except requests.exceptions.RequestException as e:
        # Handle request errors (e.g., network problems, invalid ticker)
        print(f"Error fetching data for {ticker}: {e}")
        return {"error": f"Could not retrieve data for {ticker}. Please check the ticker symbol or try again later."}
    
    except Exception as e:
        # Handle any other exceptions
        print(f"Unexpected error: {e}")
        return {"error": f"An unexpected error occurred: {e}"}

def get_stock_info(ticker):
    """Get stock info, either from cache or by fetching and caching."""
    cache_file = get_cache_filepath(ticker)
    if is_cache_valid(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return fetch_and_cache_stock_info(ticker)