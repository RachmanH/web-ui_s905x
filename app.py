from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Khadas VIM Dashboard</title>

        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
                font-family: Arial, sans-serif;
            }

            body {
                background: #f4f7fb;
                color: #1f2937;
            }

            .container {
                display: flex;
                min-height: 100vh;
            }

            .sidebar {
                width: 250px;
                background: linear-gradient(180deg, #111827, #1f2937);
                color: white;
                padding: 25px 20px;
            }

            .sidebar h2 {
                margin-bottom: 35px;
                font-size: 22px;
            }

            .sidebar a {
                display: block;
                color: #d1d5db;
                text-decoration: none;
                margin: 18px 0;
                padding: 12px;
                border-radius: 10px;
                transition: 0.3s;
            }

            .sidebar a:hover {
                background: #374151;
                color: white;
            }

            .main {
                flex: 1;
                padding: 30px;
            }

            .header {
                background: white;
                padding: 25px;
                border-radius: 18px;
                box-shadow: 0 8px 25px rgba(0,0,0,0.08);
                margin-bottom: 30px;
            }

            .header h1 {
                font-size: 32px;
                color: #111827;
                margin-bottom: 8px;
            }

            .header p {
                color: #6b7280;
            }

            .cards {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }

            .card {
                background: white;
                padding: 25px;
                border-radius: 18px;
                box-shadow: 0 8px 25px rgba(0,0,0,0.08);
            }

            .card h3 {
                font-size: 16px;
                color: #6b7280;
                margin-bottom: 12px;
            }

            .card .value {
                font-size: 28px;
                font-weight: bold;
                color: #111827;
            }

            .status-online {
                display: inline-block;
                margin-top: 10px;
                padding: 7px 14px;
                background: #dcfce7;
                color: #166534;
                border-radius: 999px;
                font-size: 14px;
                font-weight: bold;
            }

            .panel {
                background: white;
                padding: 25px;
                border-radius: 18px;
                box-shadow: 0 8px 25px rgba(0,0,0,0.08);
            }

            .panel h2 {
                margin-bottom: 15px;
            }

            .button {
                display: inline-block;
                margin-top: 20px;
                padding: 12px 20px;
                background: #2563eb;
                color: white;
                text-decoration: none;
                border-radius: 10px;
                transition: 0.3s;
            }

            .button:hover {
                background: #1d4ed8;
            }

            @media (max-width: 768px) {
                .container {
                    flex-direction: column;
                }

                .sidebar {
                    width: 100%;
                }
            }
        </style>
    </head>

    <body>
        <div class="container">

            <div class="sidebar">
                <h2>Khadas VIM</h2>
                <a href="#">Dashboard</a>
                <a href="#">Monitoring</a>
                <a href="#">Device Info</a>
                <a href="#">Settings</a>
            </div>

            <div class="main">

                <div class="header">
                    <h1>Dashboard Khadas VIM</h1>
                    <p>Mini Python Web Server berhasil berjalan menggunakan Flask.</p>
                    <span class="status-online">Server Online</span>
                </div>

                <div class="cards">
                    <div class="card">
                        <h3>Status Server</h3>
                        <div class="value">Aktif</div>
                    </div>

                    <div class="card">
                        <h3>Port</h3>
                        <div class="value">5000</div>
                    </div>

                    <div class="card">
                        <h3>Framework</h3>
                        <div class="value">Flask</div>
                    </div>

                    <div class="card">
                        <h3>Device</h3>
                        <div class="value">VIM</div>
                    </div>
                </div>

                <div class="panel">
                    <h2>Informasi Sistem</h2>
                    <p>
                        Web server ini berjalan di jaringan lokal dan bisa diakses dari device lain
                        selama masih berada dalam jaringan yang sama.
                    </p>

                    <a href="#" class="button">Refresh Dashboard</a>
                </div>

            </div>
        </div>
    </body>
    </html>
    """

app.run(host="0.0.0.0", port=5000)
