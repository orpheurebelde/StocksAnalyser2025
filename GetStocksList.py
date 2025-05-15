import pandas as pd
import requests

# === S&P 500 from Wikipedia ===
sp500_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
sp500_tables = pd.read_html(sp500_url)
sp500_df = sp500_tables[0][["Symbol", "Security"]]
sp500_df.columns = ["Ticker", "Name"]
sp500_df["Exchange"] = "S&P 500"

# === NASDAQ from GitHub mirror ===
nasdaq_url = "https://raw.githubusercontent.com/datasets/nasdaq-listings/master/data/nasdaq-listed-symbols.csv"
nasdaq_df = pd.read_csv(nasdaq_url)
nasdaq_df = nasdaq_df[["Symbol", "Company Name"]]
nasdaq_df.columns = ["Ticker", "Name"]
nasdaq_df["Exchange"] = "NASDAQ"

# === Combine and drop duplicates ===
combined_df = pd.concat([sp500_df, nasdaq_df], ignore_index=True)
combined_df.drop_duplicates(subset="Ticker", inplace=True)

# === Save to CSV ===
combined_df.to_csv("stocks_list.csv", index=False)

print("✅ Saved to stocks_list.csv")
