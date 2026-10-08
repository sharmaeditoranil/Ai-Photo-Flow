const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

let mainWindow = null;
let pythonProcess = null;

function killPythonProcess() {
  if (!pythonProcess) return;
  try {
    if (process.platform === 'win32' && pythonProcess.pid) {
      spawn('taskkill', ['/pid', pythonProcess.pid.toString(), '/f', '/t']);
    } else {
      pythonProcess.kill('SIGTERM');
    }
  } catch (e) {
    console.error('Error stopping Python process:', e);
  }
  pythonProcess = null;
}

function startPythonBackend() {
  let pythonBin;
  let pythonArgs = [];
  let cwd;
  const isWin = process.platform === 'win32';

  if (app.isPackaged) {
    if (isWin) {
      // 1. Check for standalone compiled executable (PyInstaller on Windows)
      const exeCandidate = path.join(process.resourcesPath, 'photoflow-backend', 'photoflow-backend.exe');
      // 2. Check for bundled standalone Windows Python runtime
      const winPyCandidate1 = path.join(process.resourcesPath, 'photoflow-backend-win', 'python', 'python.exe');
      const winPyCandidate2 = path.join(process.resourcesPath, 'python-win', 'python.exe');

      if (fs.existsSync(exeCandidate)) {
        pythonBin = exeCandidate;
        pythonArgs = [];
        cwd = path.join(process.resourcesPath, 'photoflow-backend');
      } else if (fs.existsSync(winPyCandidate1)) {
        pythonBin = winPyCandidate1;
        pythonArgs = [path.join(process.resourcesPath, 'photoflow-backend-win', 'backend_entry.py')];
        cwd = path.join(process.resourcesPath, 'photoflow-backend-win');
      } else if (fs.existsSync(winPyCandidate2)) {
        pythonBin = winPyCandidate2;
        pythonArgs = [path.join(process.resourcesPath, 'backend_entry.py')];
        cwd = process.resourcesPath;
      } else {
        // Fallback: search system Python installations on Windows
        const sysPythonPaths = [
          path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python310', 'python.exe'),
          path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python311', 'python.exe'),
          path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python312', 'python.exe'),
          path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python39', 'python.exe'),
          'C:\\Python310\\python.exe',
          'C:\\Python311\\python.exe',
          'C:\\Python39\\python.exe',
          'python.exe',
          'py.exe'
        ];
        pythonBin = sysPythonPaths.find(p => fs.existsSync(p)) || 'python';
        pythonArgs = [path.join(process.resourcesPath, 'backend_entry.py')];
        cwd = process.resourcesPath;
      }
    } else {
      // macOS / Linux
      pythonBin = path.join(process.resourcesPath, 'photoflow-backend', 'photoflow-backend');
      if (fs.existsSync(pythonBin)) {
        try {
          fs.chmodSync(pythonBin, 0o755);
        } catch (e) {}
      }
      pythonArgs = [];
      cwd = process.resourcesPath;
    }
  } else {
    // Development mode
    const venvPython = isWin
      ? path.join(__dirname, '..', 'venv', 'Scripts', 'python.exe')
      : path.join(__dirname, '..', 'venv', 'bin', 'python3');
    pythonBin = fs.existsSync(venvPython) ? venvPython : (isWin ? 'python' : 'python3');
    pythonArgs = ['backend_entry.py'];
    cwd = path.join(__dirname, '..');
  }

  console.log(`Starting Python AI service from: ${pythonBin}...`);
  console.log(`Args: ${JSON.stringify(pythonArgs)}, CWD: ${cwd}`);

  // Persistent disk logger for easy troubleshooting
  let logStream = null;
  try {
    const userHome = app.getPath('home');
    const logDir = path.join(userHome, '.photoflow');
    if (!fs.existsSync(logDir)) fs.mkdirSync(logDir, { recursive: true });
    const logFilePath = path.join(logDir, 'backend.log');
    logStream = fs.createWriteStream(logFilePath, { flags: 'a' });
    logStream.write(`\n--- [${new Date().toISOString()}] Launching Backend: ${pythonBin} ---\n`);
  } catch (e) {}

  const extraPath = isWin
    ? `${path.join(cwd, 'python')};${path.join(cwd, 'python', 'Lib', 'site-packages', 'numpy.libs')};${path.join(cwd, 'python', 'Lib', 'site-packages')};${process.env.PATH || ''}`
    : (process.env.PATH || '');

  try {
    pythonProcess = spawn(pythonBin, pythonArgs, {
      cwd: cwd,
      env: { ...process.env, PYTHONPATH: cwd, PATH: extraPath },
      windowsHide: true
    });

    pythonProcess.stdout.on('data', (data) => {
      console.log(`[Python AI]: ${data}`);
      if (logStream) logStream.write(`[STDOUT] ${data}`);
    });

    pythonProcess.stderr.on('data', (data) => {
      console.error(`[Python AI Err]: ${data}`);
      if (logStream) logStream.write(`[STDERR] ${data}`);
    });

    pythonProcess.on('error', (err) => {
      console.error('[Python Process Error]:', err);
      if (logStream) logStream.write(`[PROC_ERR] ${err}\n`);
    });

    pythonProcess.on('exit', (code, signal) => {
      console.log(`[Python AI Exited]: code ${code}, signal ${signal}`);
      if (logStream) logStream.write(`[EXIT] code ${code}, signal ${signal}\n`);
    });
  } catch (err) {
    console.error('Failed to launch Python backend process:', err);
    if (logStream) logStream.write(`[SPAWN_ERR] ${err}\n`);
  }
}

function createWindow() {
  const isMac = process.platform === 'darwin';
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 940,
    minWidth: 1100,
    minHeight: 700,
    title: 'Ai PhotoFlow – Wedding Photography Culling & Batch Editing',
    backgroundColor: '#0e1014',
    titleBarStyle: isMac ? 'hiddenInset' : 'default',
    trafficLightPosition: isMac ? { x: 18, y: 16 } : undefined,
    icon: path.join(__dirname, '..', 'build', isMac ? 'icon.png' : 'icon.ico'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  // Native folder selection IPC
  ipcMain.handle('dialog:openDirectory', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory', 'createDirectory'],
      title: 'Select Wedding Photo Folder'
    });
    if (result.canceled || result.filePaths.length === 0) {
      return null;
    }
    return result.filePaths[0];
  });

  // Sample photos folder IPC for zero-friction testing on both Windows & Mac
  ipcMain.handle('app:getSamplePhotosPath', () => {
    if (app.isPackaged) {
      const p1 = path.join(process.resourcesPath, 'sample_wedding_photos');
      if (fs.existsSync(p1)) return p1;
      const p2 = path.join(process.resourcesPath, 'photoflow-backend-win', 'sample_wedding_photos');
      if (fs.existsSync(p2)) return p2;
    }
    const devPath = path.join(__dirname, '..', 'sample_wedding_photos');
    if (fs.existsSync(devPath)) return devPath;
    return null;
  });

  mainWindow.webContents.on('console-message', (e, level, message, line, sourceId) => {
    console.log(`[Frontend Log ${level}]: ${message} (line ${line})`);
  });

  mainWindow.webContents.on('render-process-gone', (e, details) => {
    console.error('Renderer process gone:', details);
  });

  if (process.env.DEBUG_PHOTOFLOW === '1') {
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  }

  if (app.isPackaged) {
    const indexPath = path.join(__dirname, '..', 'frontend', 'dist', 'index.html');
    console.log('Loading packaged file:', indexPath);
    mainWindow.loadFile(indexPath).catch(err => {
      console.error('loadFile error:', err);
    });
  } else {
    mainWindow.loadURL('http://localhost:5173');
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  startPythonBackend();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  killPythonProcess();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  killPythonProcess();
});
