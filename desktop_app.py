"""
AegisEHR - Desktop Application Runner
Launches AegisEHR as a native desktop application with an embedded WSGI server and WebView2 window.
"""

import os
import sys
import time
import socket
import shutil
import threading
import webbrowser
from pathlib import Path

# Setup paths and frozen environment awareness
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
    DATA_DIR = Path(sys.executable).resolve().parent
else:
    BUNDLE_DIR = Path(__file__).resolve().parent
    DATA_DIR = BUNDLE_DIR

# Ensure BUNDLE_DIR is in sys.path
if str(BUNDLE_DIR) not in sys.path:
    sys.path.insert(0, str(BUNDLE_DIR))

# Ensure Data Directories Exist
(DATA_DIR / 'media' / 'encrypted_packages').mkdir(parents=True, exist_ok=True)

# Copy pre-seeded database if launching for the first time in a new directory
target_db = DATA_DIR / 'db.sqlite3'
source_db = BUNDLE_DIR / 'db.sqlite3'
if not target_db.exists() and source_db.exists() and target_db != source_db:
    try:
        shutil.copy2(source_db, target_db)
        print(f"[AegisEHR] Initialized persistent database at {target_db}")
    except Exception as e:
        print(f"[AegisEHR] Could not pre-seed DB: {e}")

# Configure Django Environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr_portal.settings')
import django
django.setup()

from django.core.management import call_command
from django.core.wsgi import get_wsgi_application
from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.contrib.auth import get_user_model
from wsgiref.simple_server import make_server, WSGIServer, WSGIRequestHandler
from socketserver import ThreadingMixIn

class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True
    allow_reuse_address = True

class QuietWSGIRequestHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        # Suppress routine static asset log noise
        if "GET /static/" not in args[0] and "GET /media/" not in args[0]:
            sys.stdout.write(f"[Server] {args[0]} -> {args[1]}\n")

def find_available_port(start_port=8000, max_attempts=50):
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    return 8000

def initialize_database():
    try:
        print("[AegisEHR] Verifying database schema migrations...")
        call_command('migrate', interactive=False, verbosity=0)
        
        User = get_user_model()
        if not User.objects.exists():
            print("[AegisEHR] Database empty. Seeding initial accounts and clinical records...")
            call_command('seed_data', verbosity=0)
            print("[AegisEHR] Database seeded successfully.")
    except Exception as e:
        print(f"[AegisEHR] Database initialization note: {e}")

def run_server(server):
    try:
        server.serve_forever()
    except Exception as e:
        print(f"[AegisEHR Server Error]: {e}")

def main():
    print("=" * 65)
    print("  AegisEHR - Algorand TestNet Healthcare Portal")
    print("  Decentralized Health Record Framework with Cryptographic Consent")
    print("=" * 65)

    initialize_database()

    port = find_available_port(8000)
    app_url = f"http://127.0.0.1:{port}"
    print(f"[AegisEHR] Starting embedded WSGI server on {app_url}...")

    # Wrap WSGI app to serve static assets directly
    django_wsgi = get_wsgi_application()
    static_app = StaticFilesHandler(django_wsgi)

    server = ThreadingWSGIServer(('127.0.0.1', port), QuietWSGIRequestHandler)
    server.set_app(static_app)

    server_thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    server_thread.start()

    time.sleep(0.5)
    print(f"[AegisEHR] Service is live and listening on {app_url}")

    # Check CLI options
    use_browser = '--browser' in sys.argv

    if not use_browser:
        try:
            import webview
            print("[AegisEHR] Launching native Windows application window (WebView2)...")
            window = webview.create_window(
                title="AegisEHR - Algorand TestNet Healthcare Portal",
                url=app_url,
                width=1320,
                height=880,
                min_size=(1000, 680),
                confirm_close=True,
                background_color='#0f172a'
            )
            webview.start(debug=False)
            print("[AegisEHR] Desktop window closed. Shutting down...")
            server.shutdown()
            sys.exit(0)
        except Exception as e:
            print(f"[AegisEHR] Native window warning: {e}. Falling back to default web browser...")

    # Browser fallback
    print(f"[AegisEHR] Opening in default web browser: {app_url}")
    webbrowser.open(app_url)
    print("[AegisEHR] Press Ctrl+C in this console to terminate the application.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[AegisEHR] Terminating application...")
        server.shutdown()
        sys.exit(0)

if __name__ == '__main__':
    main()
