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
    
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print(f"Error 401: Authentication failed for {ticker}. Check API keys or permissions.")
        else:
            print(f"HTTP Error {e.response.status_code}: {e.response.reason} while fetching {ticker}")
        return {"error": f"Could not retrieve data for {ticker}. Authentication failed. Please check API keys or permissions."}
    
    except requests.exceptions.RequestException as e:
        # Handle any request exceptions
        print(f"Error fetching data for {ticker}: {e}")
        return {"error": f"Could not retrieve data for {ticker}. Please try again later."}
    
    except Exception as e:
        # Handle other exceptions
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

# Check if key exists and value is valid before using it
def safe_metric(value, divisor=1, suffix="", percentage=False):
        """Safely formats a metric value for Streamlit display."""
        try:
            if value is None:
                return "N/A"
            if isinstance(value, (int, float)):
                if math.isnan(value):  # Handle NaN values
                    return "N/A"
                if percentage:
                    return f"{value:.2%}"
                return f"${value / divisor:.2f}{suffix}" if divisor > 1 else f"${value:.2f}"
            return "N/A"
        except Exception as e:
            return f"Error: {e}"  # Return error message instead of crashing