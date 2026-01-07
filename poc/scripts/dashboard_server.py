"""
Archivist Web Dashboard Server
- Simple HTTP server for monitoring progress
- Open http://localhost:8200 in browser
- Auto-refreshes every 5 seconds
"""
import json
import http.server
import socketserver
from pathlib import Path
from datetime import datetime

PORT = 8200
DATA_DIR = Path(__file__).parent.parent / "data"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Archivist Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #1a1a2e;
            color: #eee;
            padding: 20px;
            min-height: 100vh;
        }
        .container { max-width: 900px; margin: 0 auto; }
        h1 {
            text-align: center;
            color: #00d9ff;
            margin-bottom: 10px;
            font-size: 2em;
        }
        .last-update {
            text-align: center;
            color: #888;
            margin-bottom: 30px;
            font-size: 0.9em;
        }
        .phase-card {
            background: #16213e;
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 20px;
            border: 1px solid #0f3460;
        }
        .phase-title {
            font-size: 1.3em;
            color: #00d9ff;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .status-badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.7em;
            font-weight: bold;
        }
        .status-idle { background: #666; }
        .status-waiting { background: #666; }
        .status-running { background: #f39c12; color: #000; }
        .status-completed { background: #27ae60; }
        .status-error { background: #e74c3c; }
        .progress-container {
            background: #0f3460;
            border-radius: 10px;
            height: 30px;
            overflow: hidden;
            margin: 15px 0;
        }
        .progress-bar {
            height: 100%;
            background: linear-gradient(90deg, #00d9ff, #00ff88);
            transition: width 0.5s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: #000;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }
        .stat-item {
            background: #0f3460;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }
        .stat-value {
            font-size: 1.8em;
            font-weight: bold;
            color: #00d9ff;
        }
        .stat-label {
            font-size: 0.85em;
            color: #888;
            margin-top: 5px;
        }
        .file-counts {
            background: #16213e;
            border-radius: 12px;
            padding: 25px;
            border: 1px solid #0f3460;
        }
        .file-counts h3 {
            color: #00d9ff;
            margin-bottom: 15px;
        }
        .error-msg {
            background: #e74c3c22;
            border: 1px solid #e74c3c;
            border-radius: 8px;
            padding: 10px;
            margin-top: 10px;
            font-size: 0.9em;
        }
        .refresh-indicator {
            position: fixed;
            top: 10px;
            right: 10px;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #27ae60;
            animation: pulse 1s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
    </style>
</head>
<body>
    <div class="refresh-indicator"></div>
    <div class="container">
        <h1>ARCHIVIST DASHBOARD</h1>
        <div class="last-update" id="lastUpdate">Loading...</div>

        <div class="phase-card" id="phase1Card">
            <div class="phase-title">
                PHASE 1 <span class="status-badge status-idle" id="p1Status">IDLE</span>
            </div>
            <div id="p1Content">Loading...</div>
        </div>

        <div class="phase-card" id="phase2Card">
            <div class="phase-title">
                PHASE 2 <span class="status-badge status-waiting" id="p2Status">WAITING</span>
            </div>
            <div id="p2Content">Loading...</div>
        </div>

        <div class="file-counts">
            <h3>FILE COUNTS</h3>
            <div class="stats-grid" id="fileCounts">Loading...</div>
        </div>
    </div>

    <script>
        function formatNumber(n) {
            return n ? n.toLocaleString() : '0';
        }

        function formatDuration(hours) {
            if (!hours) return '-';
            if (hours < 1) return Math.round(hours * 60) + 'm';
            if (hours < 24) return hours.toFixed(1) + 'h';
            return (hours / 24).toFixed(1) + 'd';
        }

        function updateDashboard() {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('lastUpdate').textContent =
                        'Last update: ' + new Date().toLocaleString('ko-KR');

                    // Phase 1
                    const p1 = data.status?.phase1 || {};
                    const p1Status = p1.status || 'idle';
                    const p1Badge = document.getElementById('p1Status');
                    p1Badge.textContent = p1Status.toUpperCase();
                    p1Badge.className = 'status-badge status-' + p1Status;

                    let p1Html = '';
                    if (p1Status === 'running' || p1Status === 'completed') {
                        const percent = p1.progress_percent || 0;
                        p1Html = `
                            <div class="progress-container">
                                <div class="progress-bar" style="width: ${percent}%">${percent.toFixed(1)}%</div>
                            </div>
                            <div class="stats-grid">
                                <div class="stat-item">
                                    <div class="stat-value">${formatNumber(p1.processed_files)}</div>
                                    <div class="stat-label">/ ${formatNumber(p1.total_files)} Files</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-value">${formatNumber(p1.speed_files_per_hour)}</div>
                                    <div class="stat-label">Files/Hour</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-value">${formatDuration(p1.eta_hours)}</div>
                                    <div class="stat-label">ETA</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-value">${formatNumber(p1.total_entities)}</div>
                                    <div class="stat-label">Entities</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-value">${formatNumber(p1.total_pending)}</div>
                                    <div class="stat-label">Pending</div>
                                </div>
                            </div>
                        `;
                    } else if (p1Status === 'error') {
                        p1Html = '<div class="error-msg">' + (p1.errors?.[p1.errors.length-1] || 'Unknown error') + '</div>';
                    } else {
                        p1Html = '<p style="color:#888">Not started yet</p>';
                    }
                    document.getElementById('p1Content').innerHTML = p1Html;

                    // Phase 2
                    const p2 = data.status?.phase2 || {};
                    const p2Status = p2.status || 'waiting';
                    const p2Badge = document.getElementById('p2Status');
                    p2Badge.textContent = p2Status.toUpperCase();
                    p2Badge.className = 'status-badge status-' + p2Status;

                    let p2Html = '';
                    if (p2Status === 'running' || p2Status === 'completed') {
                        const percent = p2.progress_percent || 0;
                        p2Html = `
                            <div class="progress-container">
                                <div class="progress-bar" style="width: ${percent}%">${percent.toFixed(1)}%</div>
                            </div>
                            <div class="stats-grid">
                                <div class="stat-item">
                                    <div class="stat-value">${formatNumber(p2.processed_pending)}</div>
                                    <div class="stat-label">/ ${formatNumber(p2.total_pending)} Items</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-value">${formatNumber(p2.speed_items_per_hour)}</div>
                                    <div class="stat-label">Items/Hour</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-value">${formatNumber(p2.link_existing_count)}</div>
                                    <div class="stat-label">LINK_EXISTING</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-value">${formatNumber(p2.create_new_count)}</div>
                                    <div class="stat-label">CREATE_NEW</div>
                                </div>
                            </div>
                        `;
                    } else {
                        p2Html = '<p style="color:#888">Waiting for Phase 1 pending items</p>';
                    }
                    document.getElementById('p2Content').innerHTML = p2Html;

                    // File counts
                    const fc = data.file_counts || {};
                    document.getElementById('fileCounts').innerHTML = `
                        <div class="stat-item">
                            <div class="stat-value">${formatNumber(fc.pending_queue)}</div>
                            <div class="stat-label">Pending Queue</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">${formatNumber(fc.decisions)}</div>
                            <div class="stat-label">Decisions Made</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">${formatNumber(fc.remaining)}</div>
                            <div class="stat-label">Remaining</div>
                        </div>
                    `;
                })
                .catch(err => {
                    console.error('Error fetching status:', err);
                });
        }

        // Initial load
        updateDashboard();

        // Auto-refresh every 5 seconds
        setInterval(updateDashboard, 5000);
    </script>
</body>
</html>
"""


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode('utf-8'))

        elif self.path == '/api/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            response = {
                "status": None,
                "file_counts": {
                    "pending_queue": 0,
                    "decisions": 0,
                    "remaining": 0
                },
                "timestamp": datetime.now().isoformat()
            }

            # Load status
            status_file = DATA_DIR / "status.json"
            if status_file.exists():
                try:
                    with open(status_file, 'r', encoding='utf-8') as f:
                        response["status"] = json.load(f)
                except:
                    pass

            # Count files
            pending_file = DATA_DIR / "pending_queue.jsonl"
            decisions_file = DATA_DIR / "phase2_decisions.jsonl"

            if pending_file.exists():
                with open(pending_file, 'r', encoding='utf-8') as f:
                    response["file_counts"]["pending_queue"] = sum(1 for line in f if line.strip())

            if decisions_file.exists():
                with open(decisions_file, 'r', encoding='utf-8') as f:
                    response["file_counts"]["decisions"] = sum(1 for line in f if line.strip())

            response["file_counts"]["remaining"] = max(0,
                response["file_counts"]["pending_queue"] - response["file_counts"]["decisions"])

            self.wfile.write(json.dumps(response).encode('utf-8'))

        else:
            self.send_error(404)

    def log_message(self, format, *args):
        # Suppress default logging
        pass


def main():
    print(f"=" * 50)
    print(f"  Archivist Web Dashboard")
    print(f"=" * 50)
    print()
    print(f"  Open in browser: http://localhost:{PORT}")
    print()
    print(f"  Press Ctrl+C to stop")
    print(f"=" * 50)

    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\nDashboard stopped.")


if __name__ == "__main__":
    main()
