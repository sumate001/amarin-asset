#!/usr/bin/env python3
"""
Amarin Employee Database — Universal Installer
รองรับ: macOS, Linux (Ubuntu/Debian), Windows
รัน: python3 install.py  หรือ  python install.py
"""

import sys, os, subprocess, platform, shutil, textwrap

# ── สี terminal ──────────────────────────────────────────────
if platform.system() == 'Windows':
    os.system('color')   # เปิด ANSI บน Windows Terminal
R  = '\033[91m'; G = '\033[92m'; Y = '\033[93m'
B  = '\033[94m'; C = '\033[96m'; W = '\033[0m'

def ok(msg):  print(f'{G}✅  {msg}{W}')
def err(msg): print(f'{R}❌  {msg}{W}'); sys.exit(1)
def info(msg):print(f'{C}ℹ️   {msg}{W}')
def step(n, msg): print(f'\n{B}[{n}]{W} {msg}')

# ── helpers ──────────────────────────────────────────────────
def run(*cmd, check=True, capture=False):
    return subprocess.run(list(cmd),
                          check=check,
                          capture_output=capture,
                          text=True)

def pip_install(*pkgs):
    run(sys.executable, '-m', 'pip', 'install', '--upgrade', '-q', *pkgs)

# ── detect OS ────────────────────────────────────────────────
OS      = platform.system()   # 'Darwin' | 'Linux' | 'Windows'
IS_MAC  = OS == 'Darwin'
IS_LIN  = OS == 'Linux'
IS_WIN  = OS == 'Windows'

ROOT    = os.path.dirname(os.path.abspath(__file__))
PORT    = os.environ.get('PORT', '5100')

print(f"""
{C}╔══════════════════════════════════════════╗
║   Amarin Employee Database — Installer  ║
╚══════════════════════════════════════════╝{W}
  OS      : {OS} ({platform.machine()})
  Python  : {sys.version.split()[0]}
  Folder  : {ROOT}
  Port    : {PORT}
""")

# ── 1. Python version check ──────────────────────────────────
step(1, 'ตรวจสอบ Python version')
major, minor = sys.version_info[:2]
if major < 3 or minor < 9:
    err(f'ต้องการ Python 3.9+ (ปัจจุบัน {major}.{minor})\n'
        '   ดาวน์โหลดที่: https://www.python.org/downloads/')
ok(f'Python {major}.{minor}')

# ── 2. ติดตั้ง Python packages ───────────────────────────────
step(2, 'ติดตั้ง Python dependencies')
pkgs = ['flask', 'beautifulsoup4', 'openpyxl', 'requests']
if not IS_WIN:
    pkgs.append('gunicorn')
pip_install(*pkgs)
ok('Python packages ติดตั้งแล้ว')

# ── 3. OS-specific setup ─────────────────────────────────────
step(3, 'ตั้งค่าตาม OS')

if IS_LIN:
    # ── Linux: Nginx + systemd ─────────────────────────────
    info('ตรวจหา Nginx...')
    if not shutil.which('nginx'):
        info('ติดตั้ง Nginx...')
        run('sudo', 'apt-get', 'update', '-q')
        run('sudo', 'apt-get', 'install', '-y', '-q', 'nginx')
    ok('Nginx พร้อม')

    APP_DIR = '/opt/amarin-employee'
    LOG_DIR = '/var/log/amarin-employee'

    info(f'copy ไฟล์ไปยัง {APP_DIR}')
    run('sudo', 'mkdir', '-p', APP_DIR, LOG_DIR)
    run('sudo', 'rsync', '-a',
        '--exclude=.git', '--exclude=__pycache__',
        '--exclude=*.pyc', '--exclude=.env',
        f'{ROOT}/', APP_DIR)
    run('sudo', 'chown', '-R', 'www-data:www-data', APP_DIR, LOG_DIR)

    # systemd service
    SERVICE = textwrap.dedent(f"""\
        [Unit]
        Description=Amarin Employee Database
        After=network.target

        [Service]
        Type=simple
        User=www-data
        WorkingDirectory={APP_DIR}
        ExecStart={shutil.which('gunicorn') or '/usr/local/bin/gunicorn'} app:app \\
            --bind 127.0.0.1:{PORT} --workers 3 --timeout 120 \\
            --access-logfile {LOG_DIR}/access.log \\
            --error-logfile  {LOG_DIR}/error.log --preload
        Restart=always
        RestartSec=5
        PrivateTmp=true

        [Install]
        WantedBy=multi-user.target
    """)
    svc_path = '/tmp/amarin-employee.service'
    with open(svc_path, 'w') as f: f.write(SERVICE)
    run('sudo', 'cp', svc_path, '/etc/systemd/system/amarin-employee.service')
    run('sudo', 'systemctl', 'daemon-reload')
    run('sudo', 'systemctl', 'enable', 'amarin-employee')
    run('sudo', 'systemctl', 'restart', 'amarin-employee')
    ok('systemd service รันอยู่')

    # nginx config
    NGINX_CONF = textwrap.dedent(f"""\
        server {{
            listen 80;
            server_name _;
            client_max_body_size 20M;
            gzip on;
            gzip_types text/plain text/css application/json application/javascript;
            location /static/ {{
                alias {APP_DIR}/static/;
                expires 7d;
            }}
            location / {{
                proxy_pass       http://127.0.0.1:{PORT};
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_read_timeout 120s;
            }}
        }}
    """)
    nginx_tmp = '/tmp/amarin-nginx.conf'
    with open(nginx_tmp, 'w') as f: f.write(NGINX_CONF)
    run('sudo', 'cp', nginx_tmp, '/etc/nginx/sites-available/amarin-employee')
    run('sudo', 'ln', '-sf',
        '/etc/nginx/sites-available/amarin-employee',
        '/etc/nginx/sites-enabled/amarin-employee')
    # เอา default site ออก
    run('sudo', 'rm', '-f', '/etc/nginx/sites-enabled/default', check=False)
    run('sudo', 'nginx', '-t')
    run('sudo', 'systemctl', 'restart', 'nginx')
    ok('Nginx ตั้งค่าแล้ว')

elif IS_MAC:
    # ── macOS: launchd (auto-start เมื่อ login) ───────────────
    PLIST_NAME = 'com.amarin.employee'
    PLIST_PATH = os.path.expanduser(f'~/Library/LaunchAgents/{PLIST_NAME}.plist')
    LOG_DIR    = os.path.expanduser('~/Library/Logs/amarin-employee')
    GUNICORN   = shutil.which('gunicorn') or os.path.expanduser('~/.local/bin/gunicorn')
    os.makedirs(LOG_DIR, exist_ok=True)

    PLIST = textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
            "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0"><dict>
            <key>Label</key>             <string>{PLIST_NAME}</string>
            <key>ProgramArguments</key>
            <array>
                <string>{GUNICORN}</string>
                <string>app:app</string>
                <string>--bind</string>  <string>0.0.0.0:{PORT}</string>
                <string>--workers</string><string>2</string>
                <string>--timeout</string><string>120</string>
            </array>
            <key>WorkingDirectory</key>  <string>{ROOT}</string>
            <key>RunAtLoad</key>         <true/>
            <key>KeepAlive</key>         <true/>
            <key>StandardOutPath</key>   <string>{LOG_DIR}/stdout.log</string>
            <key>StandardErrorPath</key> <string>{LOG_DIR}/stderr.log</string>
        </dict></plist>
    """)
    with open(PLIST_PATH, 'w') as f: f.write(PLIST)
    run('launchctl', 'unload', PLIST_PATH, check=False)
    run('launchctl', 'load', PLIST_PATH)
    ok(f'launchd service ลงทะเบียนแล้ว (auto-start เมื่อ login)')

elif IS_WIN:
    # ── Windows: NSSM หรือ bat file ───────────────────────────
    BAT = os.path.join(ROOT, 'start-prod.bat')
    PYTHON = sys.executable.replace('\\', '\\\\')
    with open(BAT, 'w', encoding='utf-8') as f:
        f.write(f'@echo off\n')
        f.write(f'cd /d "{ROOT}"\n')
        f.write(f'echo Starting Amarin Employee Database on port {PORT}...\n')
        f.write(f'"{PYTHON}" -m flask --app app run --host=0.0.0.0 --port={PORT}\n')
        f.write(f'pause\n')
    ok(f'สร้างไฟล์: start-prod.bat')

    # ตรวจว่ามี NSSM ไหม (Windows Service manager)
    if shutil.which('nssm'):
        info('พบ NSSM — ลงทะเบียน Windows Service...')
        run('nssm', 'install', 'AmarinEmployee', sys.executable,
            '-m', 'flask', '--app', 'app', 'run',
            '--host=0.0.0.0', f'--port={PORT}', check=False)
        run('nssm', 'set', 'AmarinEmployee', 'AppDirectory', ROOT, check=False)
        run('nssm', 'start', 'AmarinEmployee', check=False)
        ok('Windows Service ลงทะเบียนแล้ว (รันเป็น background)')
    else:
        info('ไม่พบ NSSM — ใช้ start-prod.bat แทน (double-click เพื่อรัน)')
        info('ถ้าต้องการรันเป็น Windows Service ติดตั้ง NSSM ก่อน:')
        info('  https://nssm.cc/download')

# ── 4. สรุป ──────────────────────────────────────────────────
import socket
try:
    local_ip = socket.gethostbyname(socket.gethostname())
except Exception:
    local_ip = '127.0.0.1'

print(f"""
{G}╔══════════════════════════════════════════╗
║         ✅  ติดตั้งเสร็จแล้ว!           ║
╚══════════════════════════════════════════╝{W}""")

if IS_LIN:
    print(f"  🌐  เปิดได้ที่:  http://{local_ip}")
    print(f"  📋  ดู log:     journalctl -u amarin-employee -f")
    print(f"  🔄  restart:    sudo systemctl restart amarin-employee")
elif IS_MAC:
    print(f"  🌐  เปิดได้ที่:  http://localhost:{PORT}")
    print(f"  📋  ดู log:     tail -f {LOG_DIR}/stderr.log")
    print(f"  🔄  restart:    launchctl kickstart -k gui/$UID/com.amarin.employee")
elif IS_WIN:
    print(f"  🌐  เปิดได้ที่:  http://localhost:{PORT}")
    print(f"  ▶️   รัน server:  double-click start-prod.bat")
    if shutil.which('nssm'):
        print(f"  🔄  restart:    nssm restart AmarinEmployee")
