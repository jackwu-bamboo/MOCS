"""嵌入外部 Windows 程序的主窗口（Win32 SetParent）。

启动外部程序后轮询其顶层窗口（含子进程），找到主窗口后去掉标题栏/边框，
挂接为本控件的子窗口，并随控件尺寸同步调整。
"""
import ctypes
import os
import subprocess
import time
from ctypes import wintypes

import psutil
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QLabel, QWidget

user32 = ctypes.WinDLL("user32", use_last_error=True)

GW_OWNER = 4
GWL_STYLE = -16
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_POPUP = 0x80000000
WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_SYSMENU = 0x00080000
WM_CLOSE = 0x0010
SW_SHOW = 5
SW_RESTORE = 9
POLL_MS = 500

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_get_style = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
_set_style = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
_get_style.restype = ctypes.c_ssize_t
_get_style.argtypes = [wintypes.HWND, ctypes.c_int]
_set_style.restype = ctypes.c_ssize_t
_set_style.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindow.restype = wintypes.HWND
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
user32.SetParent.restype = wintypes.HWND
user32.MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int,
                              ctypes.c_int, ctypes.c_int, wintypes.BOOL]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]


def _candidate_pids(exe_name, since):
    """启动器（如 pycharm64.exe）常会派生后退出，真正窗口属于同名的后续进程，按名称+启动时间匹配。"""
    pids = set()
    for p in psutil.process_iter(["pid", "name", "create_time"]):
        try:
            if p.info["name"] and p.info["name"].lower() == exe_name and p.info["create_time"] >= since:
                pids.add(p.pid)
                pids.update(c.pid for c in p.children(recursive=True))
        except psutil.Error:
            continue
    return pids


def find_main_window(pids):
    """在给定进程集合中找主窗口：可见、有标题、无所有者，优先 Java AWT 主框架并取面积最大者。"""
    found = []

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.GetWindow(hwnd, GW_OWNER):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in pids or user32.GetWindowTextLengthW(hwnd) == 0:
            return True
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        if cls.value == "SunAwtDialog":
            return True
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        area = (rect.right - rect.left) * (rect.bottom - rect.top)
        found.append((cls.value == "SunAwtFrame", area, hwnd))
        return True

    callback = WNDENUMPROC(cb)
    user32.EnumWindows(callback, 0)
    if not found:
        return None
    found.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return found[0][2]


class ExternalAppView(QWidget):
    """启动外部程序并把其主窗口嵌入到本控件中。"""

    def __init__(self, exe, args=(), parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_NativeWindow, True)
        self.setMinimumSize(320, 240)
        self.setStyleSheet("background-color: #0e211f;")
        self._hint = QLabel("正在启动外部程序…", self)
        self._hint.setAlignment(Qt.AlignCenter)
        self._hint.setStyleSheet("color: #e6fffa; font-size: 14px;")
        self._hwnd = None
        self._exe_name = os.path.basename(exe).lower()
        self._started_at = time.time()
        self._proc = subprocess.Popen([exe, *args])
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._try_embed)
        self._timer.start(POLL_MS)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._hint.setGeometry(self.rect())
        self._resize_child()

    def _try_embed(self):
        pids = _candidate_pids(self._exe_name, self._started_at - 2)
        hwnd = find_main_window(pids) if pids else None
        if hwnd:
            self._embed(hwnd)
            return
        waited = int(time.time() - self._started_at)
        self._hint.setText(f"正在等待外部程序窗口…（已等待 {waited} 秒，"
                           f"若该程序已在运行，请先关闭它）")

    def _embed(self, hwnd):
        self._timer.stop()
        user32.ShowWindow(hwnd, SW_RESTORE)
        style = _get_style(hwnd, GWL_STYLE)
        style &= ~(WS_CAPTION | WS_THICKFRAME | WS_POPUP
                   | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU)
        _set_style(hwnd, GWL_STYLE, style | WS_CHILD | WS_VISIBLE)
        user32.SetParent(hwnd, int(self.winId()))
        self._hwnd = hwnd
        self._hint.hide()
        self._resize_child()
        user32.ShowWindow(hwnd, SW_SHOW)

    def _resize_child(self):
        if self._hwnd:
            user32.MoveWindow(self._hwnd, 0, 0, self.width(), self.height(), True)

    def shutdown(self):
        """关闭嵌入的程序：先请求其正常关闭（保留未保存提示），仍在运行则结束进程。"""
        if self._hwnd:
            user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
        if self._proc.poll() is None:
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
