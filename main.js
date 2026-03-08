/*
 * ============================================================
 *  Quest Widget - Electron 메인 프로세스
 * ============================================================
 *  역할: 윈도우 생성, 시스템 트레이, IPC 통신, 전역 단축키
 *  렌더러(index.html)와 preload.js를 통해 양방향 통신
 * ============================================================
 */

const { app, BrowserWindow, Tray, Menu, screen, ipcMain, nativeImage, dialog, globalShortcut } = require('electron');
const path = require('path');
const fs = require('fs');
const { exec } = require('child_process');

let mainWindow;   // 메인 위젯 윈도우
let tray;          // 시스템 트레이 아이콘
let backendProcess = null;   // FastAPI 백엔드 프로세스
let isDesktopMode = true;    // true: 바탕화면 고정 / false: 항상 위
let isClickThrough = false;  // true: 마우스 이벤트를 뒤쪽 창으로 통과시킴

// ============================================================
//  백엔드 서버 자동 실행
// ============================================================
/*
 * 개발 모드: python으로 직접 실행
 * 빌드 모드: PyInstaller로 번들된 quest-backend.exe 실행
 *
 * 백엔드가 준비될 때까지 폴링한 후 윈도우를 로드
 */
function startBackend() {
  const isDev = !app.isPackaged;

  if (isDev) {
    // 개발 모드: python 직접 실행
    const pythonPath = path.join(__dirname, 'daily-dungeon', 'Scripts', 'python.exe');
    const serverScript = path.join(__dirname, 'backend', 'run_server.py');

    backendProcess = require('child_process').spawn(pythonPath, [serverScript], {
      cwd: path.join(__dirname, 'backend'),
      stdio: 'ignore',
      windowsHide: true,
    });
  } else {
    // 빌드 모드: PyInstaller exe 실행
    const backendExe = path.join(process.resourcesPath, 'backend', 'quest-backend.exe');

    backendProcess = require('child_process').spawn(backendExe, [], {
      cwd: path.join(process.resourcesPath, 'backend'),
      stdio: 'ignore',
      windowsHide: true,
    });
  }

  backendProcess.on('error', (err) => {
    console.error('백엔드 실행 실패:', err.message);
  });
}

function stopBackend() {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
}

// 백엔드 서버가 응답할 때까지 대기 (최대 15초)
function waitForBackend(retries = 30) {
  return new Promise((resolve) => {
    const check = (remaining) => {
      const http = require('http');
      const req = http.get('http://127.0.0.1:8000/', (res) => {
        resolve(true);
      });
      req.on('error', () => {
        if (remaining <= 0) { resolve(false); return; }
        setTimeout(() => check(remaining - 1), 500);
      });
      req.setTimeout(2000, () => { req.destroy(); });
    };
    check(retries);
  });
}

// ============================================================
//  윈도우 생성
// ============================================================
function createWindow() {
  // 모니터 작업 영역 크기를 기준으로 우측 하단에 배치
  const { width: screenWidth, height: screenHeight } = screen.getPrimaryDisplay().workAreaSize;

  mainWindow = new BrowserWindow({
    width: 360,
    height: 600,
    x: screenWidth - 380,    // 우측에서 380px 안쪽
    y: screenHeight - 620,   // 하단에서 620px 위
    frame: false,             // OS 기본 타이틀바 제거 (프레임리스)
    transparent: true,        // 배경 투명 → CSS로 반투명 글래스 효과 구현
    resizable: false,         // 크기 고정
    skipTaskbar: true,        // 작업표시줄에 표시하지 않음 (위젯답게)
    focusable: true,
    webPreferences: {
      nodeIntegration: false,   // 보안: 렌더러에서 Node.js API 직접 접근 차단
      contextIsolation: true,   // 보안: preload와 렌더러 컨텍스트 분리
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  mainWindow.loadFile('index.html');
  mainWindow.setVisibleOnAllWorkspaces(true);  // 모든 가상 데스크톱에서 표시

  // 시작 시 바탕화면 고정 모드이면 뒤쪽으로 배치
  if (isDesktopMode) pinToDesktop();

  // 포커스를 잃을 때마다 바탕화면 레벨로 다시 내림
  // → 다른 창을 클릭하면 위젯이 자연스럽게 뒤로 감
  mainWindow.on('blur', () => {
    if (isDesktopMode) pinToDesktop();
  });

  // ============================================================
  //  IPC 핸들러 - 렌더러(프론트)와 메인 프로세스 간 통신
  // ============================================================

  /*
   * 윈도우 드래그 이동
   * 렌더러에서 마우스 delta 값을 보내면 현재 위치에 더해서 이동
   * (프레임리스 윈도우라 OS 기본 드래그가 없으므로 직접 구현)
   */
  ipcMain.on('window-move', (_, { deltaX, deltaY }) => {
    const [x, y] = mainWindow.getPosition();
    mainWindow.setPosition(x + deltaX, y + deltaY);
  });

  // 위젯 표시/숨기기 토글
  ipcMain.on('toggle-visibility', () => {
    if (mainWindow.isVisible()) mainWindow.hide();
    else mainWindow.show();
  });

  /*
   * 아바타 이미지 선택 (invoke/handle 패턴 = 비동기 양방향)
   * 1. OS 파일 선택 다이얼로그를 열어 이미지 선택
   * 2. 파일을 읽어 base64 Data URL로 변환하여 렌더러에 반환
   * 3. 렌더러에서 localStorage에 저장 → 앱 재시작 시에도 유지
   */
  ipcMain.handle('select-avatar', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      title: '아바타 이미지 선택',
      filters: [{ name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'gif', 'webp'] }],
      properties: ['openFile'],
    });
    if (result.canceled || !result.filePaths.length) return null;
    const filePath = result.filePaths[0];
    const ext = path.extname(filePath).slice(1);
    const data = fs.readFileSync(filePath);
    return `data:image/${ext};base64,${data.toString('base64')}`;
  });

  /*
   * 퀘스트 증명 이미지 선택
   * 아바타와 동일한 방식이지만, 퀘스트 완료 증명용으로 별도 핸들러 분리
   * (향후 백엔드로 전송하거나 별도 저장 경로를 추가할 수 있음)
   */
  ipcMain.handle('select-proof-image', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      title: '증명 이미지 첨부',
      filters: [{ name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'gif', 'webp'] }],
      properties: ['openFile'],
    });
    if (result.canceled || !result.filePaths.length) return null;
    const filePath = result.filePaths[0];
    const ext = path.extname(filePath).slice(1);
    const data = fs.readFileSync(filePath);
    return `data:image/${ext};base64,${data.toString('base64')}`;
  });

  /*
   * 위젯 전체 투명도 조절 (0.0 ~ 1.0)
   * Electron의 setOpacity API로 윈도우 자체 투명도를 변경
   * CSS opacity와 달리 윈도우 전체(프레임 포함)에 적용됨
   */
  ipcMain.on('set-opacity', (_, opacity) => {
    mainWindow.setOpacity(opacity);
  });

  /*
   * 클릭 무시 (Click-through) 토글
   * enabled=true일 때 위젯을 통과하여 뒤에 있는 창을 클릭할 수 있음
   * { forward: true } → 마우스 hover 이벤트는 여전히 위젯에 전달
   *                      (마우스가 위젯 위에 있는지 감지 가능)
   */
  ipcMain.on('toggle-click-through', (_, enabled) => {
    isClickThrough = enabled;
    mainWindow.setIgnoreMouseEvents(enabled, { forward: true });
    mainWindow.webContents.send('click-through-changed', enabled);
  });

  /*
   * 바탕화면 고정 ↔ 플로팅 모드 전환
   * - 바탕화면 고정: 다른 창 뒤에 위치 (위젯처럼 동작)
   * - 플로팅: 항상 최상단에 표시 (alwaysOnTop)
   */
  ipcMain.on('toggle-desktop-mode', () => {
    isDesktopMode = !isDesktopMode;
    if (isDesktopMode) pinToDesktop();
    else mainWindow.setAlwaysOnTop(true, 'floating');
    mainWindow.webContents.send('desktop-mode-changed', isDesktopMode);
  });

  // 설정 탭에서 "항상 위에 표시" 토글
  ipcMain.on('set-always-on-top', (_, enabled) => {
    if (enabled) {
      isDesktopMode = false;
      mainWindow.setAlwaysOnTop(true, 'floating');
    } else {
      mainWindow.setAlwaysOnTop(false);
    }
    mainWindow.webContents.send('desktop-mode-changed', !enabled);
  });

  // ============================================================
  //  전역 단축키 등록
  //  - 앱이 포커스 상태가 아니어도 동작하는 시스템 전역 단축키
  // ============================================================

  // Ctrl+Shift+Space: 위젯 표시/숨기기
  globalShortcut.register('Ctrl+Shift+Space', () => {
    if (mainWindow.isVisible()) mainWindow.hide();
    else { mainWindow.show(); mainWindow.focus(); }
  });

  // Ctrl+Shift+T: 클릭 무시 모드 토글
  globalShortcut.register('Ctrl+Shift+T', () => {
    isClickThrough = !isClickThrough;
    mainWindow.setIgnoreMouseEvents(isClickThrough, { forward: true });
    mainWindow.webContents.send('click-through-changed', isClickThrough);
  });
}

// ============================================================
//  바탕화면 고정 (Pin to Desktop)
// ============================================================
/*
 * Windows에서 위젯을 바탕화면 바로 위 레벨에 배치하는 함수
 *
 * 동작 원리:
 * 1. 잠시 alwaysOnTop을 켜서 윈도우를 활성화시킨 뒤
 * 2. 100ms 후 alwaysOnTop을 끔 → 일반 z-order로 복귀
 * 3. PowerShell로 Win32 API(SetWindowPos)를 호출하여
 *    윈도우를 HWND_BOTTOM(맨 뒤)으로 이동
 *
 * → 다른 앱 창들 뒤에 위치하지만, 바탕화면 아이콘 위에 표시됨
 */
function pinToDesktop() {
  mainWindow.setAlwaysOnTop(true, 'screen-saver');
  setTimeout(() => {
    mainWindow.setAlwaysOnTop(false);
    // Win32 SetWindowPos API를 PowerShell 경유로 호출
    const ps = `
      Add-Type @"
      using System;
      using System.Runtime.InteropServices;
      public class WinAPI {
        [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
        public static readonly IntPtr HWND_BOTTOM = new IntPtr(1);
      }
"@
    `;
    exec(`powershell -Command "& { ${ps.replace(/\n/g, ' ')} }"`, { windowsHide: true });
  }, 100);
}

// ============================================================
//  시스템 트레이 아이콘
// ============================================================
/*
 * 우측 하단 시스템 트레이에 아이콘을 생성
 * - 좌클릭: 위젯 표시 + 포커스
 * - 우클릭: 컨텍스트 메뉴 (바탕화면 고정, 클릭 무시, 표시/숨기기, 종료)
 *
 * 아이콘은 외부 파일 없이 16x16 RGBA 버퍼로 직접 생성 (주황색 사각형)
 */
function createTray() {
  // 16x16 주황색 아이콘을 RGBA 버퍼로 생성
  const size = 16;
  const rawData = Buffer.alloc(size * size * 4);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const idx = (y * size + x) * 4;
      rawData[idx] = 255;      // R
      rawData[idx + 1] = 180;  // G
      rawData[idx + 2] = 100;  // B
      rawData[idx + 3] = 255;  // A (불투명)
    }
  }
  const icon = nativeImage.createFromBuffer(rawData, { width: 16, height: 16 });
  tray = new Tray(icon);
  tray.setToolTip('Quest Widget');

  // 트레이 우클릭 메뉴
  const contextMenu = Menu.buildFromTemplate([
    {
      label: '📌 바탕화면 고정',
      type: 'checkbox',
      checked: isDesktopMode,
      click: () => {
        isDesktopMode = !isDesktopMode;
        if (isDesktopMode) pinToDesktop();
        else mainWindow.setAlwaysOnTop(true, 'floating');
        mainWindow.webContents.send('desktop-mode-changed', isDesktopMode);
      },
    },
    {
      label: '🖱️ 클릭 무시',
      type: 'checkbox',
      checked: false,
      click: (menuItem) => {
        isClickThrough = menuItem.checked;
        mainWindow.setIgnoreMouseEvents(isClickThrough, { forward: true });
        mainWindow.webContents.send('click-through-changed', isClickThrough);
      },
    },
    { type: 'separator' },
    {
      label: '위젯 표시/숨기기 (Ctrl+Shift+Space)',
      click: () => {
        if (mainWindow.isVisible()) mainWindow.hide();
        else mainWindow.show();
      },
    },
    { type: 'separator' },
    { label: '종료', click: () => app.quit() },
  ]);

  tray.setContextMenu(contextMenu);

  // 트레이 아이콘 좌클릭 → 위젯 표시
  tray.on('click', () => { mainWindow.show(); mainWindow.focus(); });
}

// ============================================================
//  앱 생명주기
// ============================================================

// Electron 앱 준비 완료 → 백엔드 시작 → 윈도우 + 트레이 생성
app.whenReady().then(async () => {
  startBackend();
  const ready = await waitForBackend();
  if (!ready) console.error('백엔드 서버 시작 시간 초과');
  createWindow();
  createTray();
});

// 앱 종료 시 백엔드 프로세스 정리 + 전역 단축키 해제
app.on('will-quit', () => {
  stopBackend();
  globalShortcut.unregisterAll();
});

// 모든 윈도우가 닫혀도 앱을 종료하지 않음 (트레이에서 계속 실행)
app.on('window-all-closed', (e) => { e.preventDefault(); });
