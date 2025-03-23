from flask import Flask, render_template, request, redirect, session, flash, url_for, jsonify
from dotenv import load_dotenv
import os
import yfinance as yf
import requests
from functools import wraps
import uuid

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
    
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        if info and 'regularMarketPrice' in info:
            return jsonify({
                "success": True,
                "symbol": symbol.split('.')[0],
                "company_name": info.get('longName', 'N/A'),
                "current_price": round(info.get('regularMarketPrice', 0), 2),
                "change": round(info.get('regularMarketChangePercent', 0), 2)
            })
        return jsonify({"success": False, "error": "Could not fetch stock data"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

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
    
    if request.method == 'POST':
        symbol = request.form.get('symbol', '').upper().strip()
        if symbol:
            try_symbols = [f"{symbol}.NS", f"{symbol}.BO"]
            added = False
            for try_symbol in try_symbols:
                try:
                    stock = yf.Ticker(try_symbol)
                    info = stock.info
                    if info and 'regularMarketPrice' in info:
                        # For AJAX requests, return JSON
                        if request.is_json or request.content_type == 'application/json':
                            return jsonify({
                                "success": True, 
                                "symbol": try_symbol,
                                "message": f"Stock {symbol} found and added"
                            })
                        
                        # For form submissions, use session and redirect
                        session.setdefault('stocks', []).append(try_symbol)
                        flash(f'Added {symbol} to your portfolio', 'success')
                        added = True
                        break
                except Exception as e:
                    print(f"Error adding stock: {e}")
                    continue
            
            if not added:
                if request.is_json or request.content_type == 'application/json':
                    return jsonify({
                        "success": False, 
                        "error": f"Could not find stock {symbol} on NSE or BSE"
                    })
                flash(f'Could not find stock {symbol} on NSE or BSE', 'error')
        
        # Return redirect for form submissions
        if not (request.is_json or request.content_type == 'application/json'):
            return redirect(url_for('stocks'))

    # Get stocks from session for now (will be replaced by client-side Firestore)
    stocks_data = []
    for symbol in session.get('stocks', []):
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            if info and 'regularMarketPrice' in info:
                stocks_data.append({
                    'symbol': symbol.split('.')[0],
                    'company_name': info.get('longName', 'N/A'),
                    'current_price': round(info.get('regularMarketPrice', 0), 2),
                    'change': round(info.get('regularMarketChangePercent', 0), 2)
                })
        except Exception as e:
            print(f"Error retrieving stock data: {e}")
            continue

    return render_template('stocks.html', stocks=stocks_data)

@app.route('/mutual-funds', methods=['GET', 'POST'])
@login_required
def mutual_funds():
    user_email = session['user']['email']
    
    if request.method == 'POST':
        scheme_code = request.form.get('scheme_code')
        if scheme_code:
            try:
                response = requests.get(f'https://api.mfapi.in/mf/{scheme_code}')
                data = response.json()
                if data and 'status' in data and data['status'] == 'SUCCESS':
                    # Note: Firestore operations are now in client-side JavaScript
                    session.setdefault('mutual_funds', []).append(scheme_code)
                    flash('Added mutual fund to your portfolio', 'success')
                else:
                    flash('Invalid scheme code', 'error')
            except Exception as e:
                flash(f'Error fetching mutual fund data: {str(e)}', 'error')
        return redirect(url_for('mutual_funds'))

    # Get mutual funds from session for now (will be replaced by client-side Firestore)
    funds_data = []
    for scheme_code in session.get('mutual_funds', []):
        try:
            response = requests.get(f'https://api.mfapi.in/mf/{scheme_code}')
            data = response.json()
            if data and data.get('status') == 'SUCCESS':
                funds_data.append({
                    'scheme_code': scheme_code,
                    'scheme_name': data['meta']['scheme_name'],
                    'nav': data['data'][0]['nav'],
                    'date': data['data'][0]['date']
                })
        except Exception as e:
            print(f"Error retrieving mutual fund data: {e}")
            continue

    return render_template('mutual_funds.html', mutual_funds=funds_data)

@app.route('/insurance', methods=['GET', 'POST'])
@login_required
def insurance():
    user_email = session['user']['email']
    
    if request.method == 'POST':
        policy_id = str(uuid.uuid4())
        policy = {
            'policy_id': policy_id,
            'policy_name': request.form.get('policy_name'),
            'policy_number': request.form.get('policy_number'),
            'premium': float(request.form.get('premium', 0))
        }
        # Note: Firestore operations are now in client-side JavaScript
        session.setdefault('policies', []).append(policy)
        flash('Added insurance policy to your portfolio', 'success')
        return redirect(url_for('insurance'))

    # Get policies from session for now (will be replaced by client-side Firestore)
    return render_template('insurance.html', policies=session.get('policies', []))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
