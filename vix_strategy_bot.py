
import yfinance as yf
import pandas as pd
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
import os
import json
import time

# ==== CONFIG ====
EMAIL_ADDRESS = "harrymc154@gmail.com"
EMAIL_PASSWORD = "gazmfjyjiuoayruk"
TO_EMAIL = "harrymc154@gmail.com"

STATUS_FILE = "live_strategy_status.json"  # Track position between runs

# ==== EMAIL SENDING FUNCTION ====
def send_email(subject, body):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = TO_EMAIL
    msg.set_content(body)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

# ==== LOAD/INITIALIZE STATUS ====
def load_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, 'r') as f:
            return json.load(f)
    return {"position": "none", "entry_price": 0, "entry_date": None}

def save_status(status):
    with open(STATUS_FILE, 'w') as f:
        json.dump(status, f)

# ==== STRATEGY ====
def run_strategy():
    status = load_status()

    # Get last 6 days of data to compute 5-day VIX change
    end_date = datetime.today()
    start_date = end_date - timedelta(days=7)
    data = yf.download(["^VIX", "VXX", "SVXY"], start=start_date.strftime("%Y-%m-%d"))['Close'].dropna()
    data.columns = ['VIX', 'VXX', 'SVXY']
    data['VIX_Change5D'] = data['VIX'].pct_change(5)
    data['SVXY_Return'] = data['SVXY'].pct_change()

    latest = data.iloc[-1]
    vix_val = latest['VIX']
    vix_change5d = latest['VIX_Change5D']
    vxx_price = latest['VXX']
    svxy_return = latest['SVXY_Return']

    recommendation = "No signal today."
    now = datetime.now()

    # Entry signal: SHORT VXX
    if vix_val > 25 and vix_change5d > 0.20 and status["position"] == "none":
        status["position"] = "short_vxx"
        status["entry_price"] = vxx_price
        status["entry_date"] = str(now.date())
        recommendation = f"SHORT SIGNAL: VIX spike detected.\n→ Consider shorting VXX at ${vxx_price:.2f}"

    # Exit signal: Close SHORT
    elif status["position"] == "short_vxx":
        entry_price = status["entry_price"]
        entry_date = datetime.strptime(status["entry_date"], "%Y-%m-%d")
        days_held = (now.date() - entry_date.date()).days
        if vix_val < 16 or days_held >= 15:
            profit_pct = (entry_price - vxx_price) / entry_price * 100
            recommendation = f"EXIT SHORT SIGNAL: Close short VXX.\n→ Entry: ${entry_price:.2f}, Now: ${vxx_price:.2f}, P/L: {profit_pct:.2f}%"
            status["position"] = "none"
            status["entry_price"] = 0
            status["entry_date"] = None

    # Safe to hold SVXY
    elif status["position"] == "none" and (vix_val < 22 and vix_change5d < 0.10):
        recommendation = f"HOLD SVXY SIGNAL: VIX low and stable.\n→ Consider holding SVXY. Last daily return: {svxy_return:.2%}"

    # Daily 9:20 AM status report
    if now.hour == 9 and now.minute == 20:
        position_note = f"Current Position: {status['position']}" if status['position'] != "none" else "Currently in cash"
        body = (
            f"📈 Daily VIX Strategy Update ({now.date()} @ 9:20 AM):\n\n"
            f"VIX: {vix_val:.2f}\n"
            f"VIX 5-day Change: {vix_change5d:.2%}\n\n"
            f"{recommendation}\n\n"
            f"{position_note}\n"
        )
        send_email("📊 Daily VIX Strategy Update", body)

    # Signal-based alert (any time of day)
    elif recommendation != "No signal today.":
        send_email("⚡ VIX Strategy Trade Alert", recommendation)

    save_status(status)

# Run indefinitely
while True:
    run_strategy()
    time.sleep(60)  # Check every minute
