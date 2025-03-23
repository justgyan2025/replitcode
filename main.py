from flask import Flask, render_template, request, redirect, session, flash, url_for, jsonify
from dotenv import load_dotenv
import os
import requests
from functools import wraps
import uuid
import json
import pandas as pd
from datetime import datetime
import re

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24))

# Load user credentials from .env file
users = {}
user_credentials = os.getenv('USER_CREDENTIALS', 'demo@example.com:demo123:Demo User')
for user_entry in user_credentials.split(','):
    if user_entry and ':' in user_entry:
        parts = user_entry.strip().split(':')
        if len(parts) >= 3:
            email, password, name = parts[0], parts[1], parts[2]
            users[email] = {"password": password, "name": name}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_stock_info(symbol):
    """Lightweight implementation to get stock data without using yfinance"""
    # For Indian stocks, use NSE/BSE identifiers
    if not symbol.endswith('.NS') and not symbol.endswith('.BO'):
        # Try NSE first
        symbol = f"{symbol}.NS"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # Use Yahoo Finance API directly
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if 'chart' in data and 'result' in data['chart'] and data['chart']['result']:
            result = data['chart']['result'][0]
            meta = result['meta']
            
            # Get company name
            url_company = f"https://query1.finance.yahoo.com/v1/finance/search?q={symbol}"
            response_company = requests.get(url_company, headers=headers)
            data_company = response_company.json()
            company_name = "N/A"
            
            if 'quotes' in data_company and data_company['quotes']:
                for quote in data_company['quotes']:
                    if quote['symbol'] == symbol:
                        company_name = quote.get('longname', quote.get('shortname', "N/A"))
                        break
            
            # Calculate percentage change
            regular_market_price = meta.get('regularMarketPrice', 0)
            previous_close = meta.get('previousClose', 0)
            change_percent = ((regular_market_price - previous_close) / previous_close * 100) if previous_close else 0
            
            return {
                'success': True,
                'symbol': symbol.split('.')[0],
                'company_name': company_name,
                'current_price': round(regular_market_price, 2),
                'change': round(change_percent, 2)
            }
        
        return {'success': False, 'error': 'Could not fetch stock data'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.route('/firebase-config')
def firebase_config():
    """Return Firebase configuration as JSON for client-side initialization"""
    config = {
        "apiKey": os.getenv('FIREBASE_API_KEY'),
        "authDomain": os.getenv('FIREBASE_AUTH_DOMAIN'),
        "databaseURL": os.getenv('FIREBASE_DATABASE_URL'),
        "projectId": os.getenv('FIREBASE_PROJECT_ID'),
        "storageBucket": os.getenv('FIREBASE_STORAGE_BUCKET'),
        "messagingSenderId": os.getenv('FIREBASE_MESSAGING_SENDER_ID'),
        "appId": os.getenv('FIREBASE_APP_ID')
    }
    return jsonify(config)

@app.route('/api/stock-data')
@login_required
def get_stock_data():
    """API endpoint to get stock data"""
    symbol = request.args.get('symbol', '').upper().strip()
    if not symbol:
        return jsonify({"success": False, "error": "Symbol is required"})
    
    result = get_stock_info(symbol)
    return jsonify(result)

@app.route('/')
@login_required
def index():
    return render_template('dashboard.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if email in users and users[email]['password'] == password:
            session['user'] = {'email': email, 'name': users[email]['name']}
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/stocks', methods=['GET', 'POST'])
@login_required
def stocks():
    user_email = session['user']['email']
    
    # Only handle session-based storage for SSR mode,
    # client-side will use Firebase directly
    if request.method == 'POST' and not (request.is_json or request.content_type == 'application/json'):
        symbol = request.form.get('symbol', '').upper().strip()
        if symbol:
            try_symbols = [f"{symbol}.NS", f"{symbol}.BO"]
            added = False
            for try_symbol in try_symbols:
                stock_info = get_stock_info(try_symbol)
                if stock_info['success']:
                    # For form submissions, use session and redirect
                    session.setdefault('stocks', []).append(try_symbol)
                    flash(f'Added {symbol} to your portfolio', 'success')
                    added = True
                    break
            
            if not added:
                flash(f'Could not find stock {symbol} on NSE or BSE', 'error')
        
        return redirect(url_for('stocks'))

    # Get stocks from session for SSR
    stocks_data = []
    for symbol in session.get('stocks', []):
        stock_info = get_stock_info(symbol)
        if stock_info['success']:
            stocks_data.append({
                'symbol': stock_info['symbol'],
                'company_name': stock_info['company_name'],
                'current_price': stock_info['current_price'],
                'change': stock_info['change']
            })

    return render_template('stocks.html', stocks=stocks_data)

@app.route('/mutual-funds')
@login_required
def mutual_funds():
    # Empty initial data, client will load from Firebase
    return render_template('mutual_funds.html', mutual_funds=[])

@app.route('/api/mutual-fund')
@login_required
def get_mutual_fund_data():
    """API endpoint to get mutual fund data"""
    scheme_code = request.args.get('scheme_code', '').strip()
    if not scheme_code:
        return jsonify({"success": False, "error": "Scheme code is required"})
    
    try:
        response = requests.get(f'https://api.mfapi.in/mf/{scheme_code}')
        data = response.json()
        if data and data.get('status') == 'SUCCESS':
            return jsonify({
                "success": True,
                "scheme_code": scheme_code,
                "scheme_name": data['meta']['scheme_name'],
                "nav": data['data'][0]['nav'],
                "date": data['data'][0]['date']
            })
        return jsonify({"success": False, "error": "Invalid scheme code"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/insurance')
@login_required
def insurance():
    # Empty initial data, client will load from Firebase
    return render_template('insurance.html', policies=[])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
