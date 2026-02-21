#!/usr/bin/env python3
"""
Liocorni Stream Deck bridge server.
Runs at http://localhost:8765/

Endpoints:
  GET /           → serves the game (index.html)
  GET /events     → SSE stream the browser subscribes to
  GET /trigger?a=N   → trigger animal at index N  (0-9)
  GET /trigger?music=1 → toggle music
  GET /trigger?skip=1  → next song
  GET /trigger?rain=1  → toggle rain
"""
import http.server, socketserver, threading, queue, json, os, sys
from urllib.parse import urlparse, parse_qs

PORT      = 8765
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
GAME_HTML = os.path.join(BASE_DIR, 'index.html')

clients      = []
clients_lock = threading.Lock()

def broadcast(payload: dict):
    with clients_lock:
        dead = []
        for q in clients:
            try:    q.put(payload)
            except: dead.append(q)
        for q in dead:
            clients.remove(q)

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_): pass   # silence access logs

    def send_cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip('/')
        params = parse_qs(parsed.query)

        # ── Serve game ────────────────────────────────────────────
        if path in ('', '/'):
            try:
                data = open(GAME_HTML, 'rb').read()
            except FileNotFoundError:
                self.send_error(404, 'index.html not found'); return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_cors()
            self.end_headers()
            self.wfile.write(data)

        # ── SSE stream ────────────────────────────────────────────
        elif path == '/events':
            self.send_response(200)
            self.send_header('Content-Type',  'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection',    'keep-alive')
            self.send_cors()
            self.end_headers()

            q = queue.Queue()
            with clients_lock: clients.append(q)
            try:
                self.wfile.write(b': connected\n\n'); self.wfile.flush()
                while True:
                    try:
                        payload = q.get(timeout=25)
                        self.wfile.write(
                            ('data: ' + json.dumps(payload) + '\n\n').encode())
                        self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(b': ping\n\n'); self.wfile.flush()
            except Exception:
                pass
            finally:
                with clients_lock:
                    if q in clients: clients.remove(q)

        # ── Trigger ───────────────────────────────────────────────
        elif path == '/trigger':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_cors()
            self.end_headers()
            self.wfile.write(b'ok')

            if   'a'     in params: broadcast({'type': 'animal', 'idx': int(params['a'][0])})
            elif 'music' in params: broadcast({'type': 'music'})
            elif 'skip'  in params: broadcast({'type': 'skip'})
            elif 'rain'  in params: broadcast({'type': 'rain'})

        else:
            self.send_error(404)

socketserver.TCPServer.allow_reuse_address = True
server = socketserver.ThreadingTCPServer(('127.0.0.1', PORT), Handler)
print(f'Liocorni server → http://localhost:{PORT}/', flush=True)
server.serve_forever()
