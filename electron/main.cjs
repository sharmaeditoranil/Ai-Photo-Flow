const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

let mainWindow = null;
let pythonProcess = null;

function startPythonBackend() {
  let pythonBin;
  let pythonArgs;
  let cwd;
  const isWin = process.platform === 'win32';

  if (app.isPackaged) {
    const binName = isWin ? 'photoflow-backend.exe' : 'photoflow-backend';
    pythonBin = path.join(process.resourcesPath, 'photoflow-backend', binName);
    if (!isWin && fs.existsSync(pythonBin)) {
      try {
        fs.chmodSync(pythonBin, 0o755);
      } catch (e) {}
    }
    pythonArgs = [];
    cwd = process.resourcesPath;
  } else {
    const venvPython = isWin
      ? path.join(__dirname, '..', 'venv', 'Scripts', 'python.exe')
      : path.join(__dirname, '..', 'venv', 'bin', 'python3');
    pythonBin = fs.existsSync(venvPython) ? venvPython : (isWin ? 'python' : 'python3');
    pythonArgs = ['backend_entry.py'];
    cwd = path.join(__dirname, '..');
  }

  console.log(`Starting Python AI service from: ${pythonBin}...`);
  try {
    pythonProcess = spawn(pythonBin, pythonArgs, {
      cwd: cwd,
      env: { ...process.env, PYTHONPATH: cwd }
    });

    pythonProcess.stdout.on('data', (data) => {
      console.log(`[Python AI]: ${data}`);
    });

    pythonProcess.stderr.on('data', (data) => {
      console.error(`[Python AI Err]: ${data}`);
    });

    pythonProcess.on('error', (err) => {
      console.error('[Python Process Error]:', err);
    });
  } catch (err) {
    console.error('Failed to launch Python backend process:', err);
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
  if (pythonProcess) {
    console.log('Stopping Python backend...');
    pythonProcess.kill();
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
});
