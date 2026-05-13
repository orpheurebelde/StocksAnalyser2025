from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
import pandas as pd
import io
import requests

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

@router.post("/analyze")
@limiter.limit("5/minute")
async def analyze_portfolio(request: Request, file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(400, "Only CSV files are allowed.")
        
    try:
        content = await file.read()
        df = pd.read_csv(io.BytesIO(content), parse_dates=["Date"], dayfirst=True, on_bad_lines='skip')
        df.columns = [col.strip() for col in df.columns]
        
        required_cols = {"Date", "Symbol", "Quantity", "Purchase Price", "Current Price"}
        missing_cols = required_cols - set(df.columns)
        if missing_cols:
            raise HTTPException(400, f"Missing columns: {missing_cols}")
            
        df["Symbol"] = df["Symbol"].astype(str).str.upper().str.split('.').str[0]
        df["Investment"] = df["Quantity"] * df["Purchase Price"]
        df["Market Value"] = df["Quantity"] * df["Current Price"]
        df["Unrealized Gain (€)"] = df["Market Value"] - df["Investment"]
        df["Unrealized Gain (%)"] = (df["Unrealized Gain (€)"] / df["Investment"]) * 100
        df["Year"] = df["Date"].dt.year
        
        summary = df.groupby("Symbol").agg({
            "Quantity": "sum",
            "Investment": "sum",
            "Market Value": "sum",
            "Unrealized Gain (€)": "sum"
        }).reset_index()
        summary["Unrealized Gain (%)"] = (summary["Unrealized Gain (€)"] / summary["Investment"]) * 100
        
        annual = df.groupby("Year").agg({
            "Investment": "sum",
            "Market Value": "sum",
            "Unrealized Gain (€)": "sum"
        }).reset_index()
        annual["Unrealized Gain (%)"] = (annual["Unrealized Gain (€)"] / annual["Investment"]) * 100
        
        return {
            "transactions": df.to_dict(orient="records"),
            "summary": summary.to_dict(orient="records"),
            "annual": annual.to_dict(orient="records")
        }
    except Exception as e:
        raise HTTPException(500, str(e))
