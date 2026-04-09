const { app, BrowserWindow, Menu, Tray, shell, dialog, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

// ── Config ──
const BACKEND_PORT = 9200;
const APP_TITLE = 'FinAI - Financial Intelligence Platform';
let mainWindow = null;
let tray = null;
let backendProcess = null;
let backendReady = false;

// ── Find Python ──
function findPython() {
  const candidates = [
    'python',
    'python3',
    'python3.13',
    'python3.11',
    path.join(__dirname, '..', 'backend', 'venv2', 'Scripts', 'python.exe'),
    path.join(__dirname, '..', 'backend', 'venv', 'Scripts', 'python.exe'),
    path.join(__dirname, '..', 'backend', 'venv', 'bin', 'python'),
  ];
  // In packaged app, look in resources
  if (app.isPackaged) {
    candidates.unshift(
      path.join(process.resourcesPath, 'backend', 'venv2', 'Scripts', 'python.exe'),
      path.join(process.resourcesPath, 'backend', 'venv', 'bin', 'python'),
    );
  }
  return candidates[0]; // Will try the first one
}

// ── Start Backend ──
function startBackend() {
  const backendDir = app.isPackaged
    ? path.join(process.resourcesPath, 'backend')
    : path.join(__dirname, '..', 'backend');

  const pythonExe = findPython();

  console.log(`Starting backend: ${pythonExe} -m uvicorn main:app --port ${BACKEND_PORT}`);
  console.log(`Working dir: ${backendDir}`);

  backendProcess = spawn(pythonExe, [
    '-m', 'uvicorn', 'main:app',
    '--host', '127.0.0.1',
    '--port', String(BACKEND_PORT),
  ], {
    cwd: backendDir,
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  backendProcess.stdout.on('data', (data) => {
    const line = data.toString().trim();
    console.log(`[Backend] ${line}`);
    if (line.includes('Application startup complete') || line.includes('Uvicorn running')) {
      backendReady = true;
      if (mainWindow) {
        mainWindow.loadURL(`http://127.0.0.1:${BACKEND_PORT}`);
      }
    }
  });

  backendProcess.stderr.on('data', (data) => {
    console.error(`[Backend ERR] ${data.toString().trim()}`);
  });

  backendProcess.on('close', (code) => {
    console.log(`Backend exited with code ${code}`);
    backendReady = false;
  });

  backendProcess.on('error', (err) => {
    console.error('Failed to start backend:', err.message);
    dialog.showErrorBox('Backend Error',
      `Could not start the Python backend.\n\n${err.message}\n\nMake sure Python is installed and uvicorn is available.`
    );
  });
}

// ── Wait for Backend ──
function waitForBackend(retries = 30) {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const check = () => {
      attempts++;
      const req = http.get(`http://127.0.0.1:${BACKEND_PORT}/health`, (res) => {
        if (res.statusCode === 200) {
          resolve();
        } else if (attempts < retries) {
          setTimeout(check, 2000);
        } else {
          reject(new Error('Backend health check failed'));
        }
      });
      req.on('error', () => {
        if (attempts < retries) {
          setTimeout(check, 2000);
        } else {
          reject(new Error('Backend not responding'));
        }
      });
      req.end();
    };
    check();
  });
}

// ── Create Window ──
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 600,
    title: APP_TITLE,
    backgroundColor: '#040507',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // Show loading screen first
  mainWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(getSplashHTML())}`);
  mainWindow.once('ready-to-show', () => mainWindow.show());

  // Menu
  const menuTemplate = [
    {
      label: 'FinAI',
      submenu: [
        { label: 'About FinAI', click: () => showAbout() },
        { type: 'separator' },
        { label: 'Open API Docs', click: () => shell.openExternal(`http://127.0.0.1:${BACKEND_PORT}/docs`) },
        { label: 'Open in Browser', click: () => shell.openExternal(`http://127.0.0.1:${BACKEND_PORT}`) },
        { type: 'separator' },
        { role: 'quit' },
      ],
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { role: 'resetZoom' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },
    {
      label: 'Reports',
      submenu: [
        { label: 'Generate PDF Report', click: () => mainWindow.webContents.executeJavaScript('downloadPDFReport && downloadPDFReport()') },
        { label: 'Open Exports Folder', click: () => shell.openPath(path.join(__dirname, '..', 'backend', 'exports')) },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(menuTemplate));

  // Handle external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

// ── Splash Screen ──
function getSplashHTML() {
  return `<!DOCTYPE html>
<html><head><style>
  body { margin:0; background:#040507; display:flex; align-items:center; justify-content:center; height:100vh; font-family:'Inter',system-ui,sans-serif; }
  .splash { text-align:center; }
  .logo { font-size:42px; font-weight:800; color:#fff; margin-bottom:8px; }
  .logo span { color:#38bdf8; }
  .sub { font-size:12px; color:#5a6a85; letter-spacing:3px; text-transform:uppercase; margin-bottom:30px; }
  .bar { width:200px; height:3px; background:#10121b; border-radius:2px; overflow:hidden; margin:0 auto; }
  .bar::after { content:''; display:block; width:40%; height:100%; background:linear-gradient(90deg,#38bdf8,#818cf8); animation:slide 1.4s ease-in-out infinite; border-radius:2px; }
  @keyframes slide { 0%{transform:translateX(-100%)} 100%{transform:translateX(350%)} }
  .msg { font-size:11px; color:#5a6a85; margin-top:16px; }
</style></head><body>
  <div class="splash">
    <div class="logo">Fin<span>AI</span></div>
    <div class="sub">Financial Intelligence</div>
    <div class="bar"></div>
    <div class="msg">Starting backend services...</div>
  </div>
</body></html>`;
}

// ── About Dialog ──
function showAbout() {
  dialog.showMessageBox(mainWindow, {
    type: 'info',
    title: 'About FinAI',
    message: 'FinAI - Financial Intelligence Platform',
    detail: [
      'Version: 1.0.0 (Phases A-S)',
      'Backend: FastAPI + SQLite + ChromaDB',
      'AI Engine: Multi-Agent (5 agents + Supervisor)',
      'Knowledge Graph: 710+ entities',
      'Verified: 594/594 checks passing',
      '',
      'Built with Claude Code',
    ].join('\n'),
  });
}

// ── App Lifecycle ──
app.whenReady().then(async () => {
  createWindow();
  startBackend();

  try {
    await waitForBackend(60); // Wait up to 2 minutes
    console.log('Backend is ready!');
    if (mainWindow) {
      mainWindow.loadURL(`http://127.0.0.1:${BACKEND_PORT}`);
    }
  } catch (err) {
    console.error('Backend failed to start:', err.message);
    if (mainWindow) {
      mainWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(`
        <html><body style="background:#040507;color:#f87171;font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
          <div style="text-align:center">
            <h1 style="color:#fff;font-size:28px">FinAI</h1>
            <p style="color:#f87171">Backend failed to start</p>
            <p style="color:#5a6a85;font-size:12px">${err.message}</p>
            <p style="color:#5a6a85;font-size:11px;margin-top:20px">Make sure Python and uvicorn are installed</p>
          </div>
        </body></html>
      `)}`);
    }
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  // Kill backend process
  if (backendProcess && !backendProcess.killed) {
    console.log('Stopping backend...');
    backendProcess.kill('SIGTERM');
    setTimeout(() => {
      if (backendProcess && !backendProcess.killed) {
        backendProcess.kill('SIGKILL');
      }
    }, 3000);
  }
});
