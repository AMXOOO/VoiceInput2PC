"""Unicode keyboard packets in the current interactive session; never steal focus."""
import ctypes as C
from ctypes import wintypes as W
import time
from dataclasses import dataclass

user32 = C.WinDLL('user32', use_last_error=True)
kernel32 = C.WinDLL('kernel32', use_last_error=True)
ULONG_PTR = W.WPARAM


class KEYBDINPUT(C.Structure):
    _fields_ = [('wVk', W.WORD), ('wScan', W.WORD), ('dwFlags', W.DWORD),
                ('time', W.DWORD), ('dwExtraInfo', ULONG_PTR)]


class MOUSEINPUT(C.Structure):
    _fields_ = [('dx', W.LONG), ('dy', W.LONG), ('mouseData', W.DWORD),
                ('dwFlags', W.DWORD), ('time', W.DWORD), ('dwExtraInfo', ULONG_PTR)]


class INPUTUNION(C.Union):
    _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT)]


class INPUT(C.Structure):
    _anonymous_ = ('u',)
    _fields_ = [('type', W.DWORD), ('u', INPUTUNION)]


user32.GetForegroundWindow.restype = W.HWND
user32.GetAsyncKeyState.argtypes = [C.c_int]
user32.GetAsyncKeyState.restype = C.c_short
user32.SendInput.argtypes = [W.UINT, C.POINTER(INPUT), C.c_int]
user32.SendInput.restype = W.UINT
user32.OpenClipboard.argtypes = [W.HWND]
user32.SetClipboardData.argtypes = [W.UINT, W.HANDLE]
user32.SetClipboardData.restype = W.HANDLE
kernel32.GlobalAlloc.argtypes = [W.UINT, C.c_size_t]
kernel32.GlobalAlloc.restype = W.HANDLE
kernel32.GlobalLock.argtypes = [W.HANDLE]
kernel32.GlobalLock.restype = C.c_void_p
kernel32.GlobalUnlock.argtypes = [W.HANDLE]
kernel32.GlobalFree.argtypes = [W.HANDLE]
kernel32.GlobalFree.restype = W.HANDLE
user32.CreateWindowExW.argtypes = [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD,
                                   C.c_int, C.c_int, C.c_int, C.c_int,
                                   W.HWND, W.HMENU, W.HINSTANCE, C.c_void_p]
user32.CreateWindowExW.restype = W.HWND
user32.DestroyWindow.argtypes = [W.HWND]


class GUITHREADINFO(C.Structure):
    _fields_ = [('cbSize', W.DWORD), ('flags', W.DWORD), ('hwndActive', W.HWND),
                ('hwndFocus', W.HWND), ('hwndCapture', W.HWND), ('hwndMenuOwner', W.HWND),
                ('hwndMoveSize', W.HWND), ('hwndCaret', W.HWND), ('rcCaret', W.RECT)]


user32.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
user32.GetWindowThreadProcessId.restype = W.DWORD
user32.GetGUIThreadInfo.argtypes = [W.DWORD, C.POINTER(GUITHREADINFO)]
user32.GetGUIThreadInfo.restype = W.BOOL
@dataclass(frozen=True)
class InputTarget:
    window: int
    focus: int
    process: int


def capture_target():
    window = user32.GetForegroundWindow()
    pid = W.DWORD()
    thread = user32.GetWindowThreadProcessId(window, C.byref(pid)) if window else 0
    info = GUITHREADINFO()
    info.cbSize = C.sizeof(info)
    if not thread or not user32.GetGUIThreadInfo(thread, C.byref(info)) or not info.hwndFocus:
        raise RuntimeError('请先在电脑点击需要输入的位置')
    if window != user32.GetForegroundWindow():
        raise RuntimeError('电脑窗口正在切换，请稍后重新开始')
    return InputTarget(window, info.hwndFocus, pid.value)


def unicode_packets(text):
    if not text or len(text) > 20000 or any(ord(c) < 32 or ord(c) == 127 for c in text):
        raise ValueError('仅支持普通文字，不发送回车、Tab 或控制按键')
    raw = text.encode('utf-16-le', errors='strict')
    units = [int.from_bytes(raw[i:i+2], 'little') for i in range(0, len(raw), 2)]
    packets = (INPUT * (2 * len(units)))()
    for index, unit in enumerate(units):
        for offset, flags in ((0, 4), (1, 6)):
            packets[index * 2 + offset].type = 1
            packets[index * 2 + offset].ki = KEYBDINPUT(0, unit, flags, 0, 0)
    return packets


def type_text(text, target):
    packets = unicode_packets(text)
    if capture_target() != target:
        raise RuntimeError('输入位置已改变，已停止本次输入')
    if any(user32.GetAsyncKeyState(k) & 0x8000 for k in (0x10, 0x11, 0x12, 0x5B, 0x5C)):
        raise RuntimeError('电脑正按着修饰键，已停止本次输入')
    # One batch, no sleeps/focus activation/clipboard mutation, and no replay.
    C.set_last_error(0)
    count = user32.SendInput(len(packets), packets, C.sizeof(INPUT))
    if count != len(packets):
        error = C.get_last_error()
        detail = f'系统接受了 {count}/{len(packets)} 个键盘事件，Windows 错误码 {error}。'
        raise RuntimeError(detail + '可能已输入部分文字，请核对电脑后继续；不会自动重试。')


def copy_text(text):
    # Last received text intentionally remains available for manual Ctrl+V.
    data = (text.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n') + '\0').encode('utf-16-le')
    handle = kernel32.GlobalAlloc(0x42, len(data))
    if not handle:
        raise RuntimeError('剪贴板内存不足')
    ptr = kernel32.GlobalLock(handle)
    if not ptr:
        kernel32.GlobalFree(handle)
        raise RuntimeError('无法访问剪贴板内存')
    C.memmove(ptr, data, len(data))
    kernel32.GlobalUnlock(handle)
    owner = user32.CreateWindowExW(0, 'STATIC', 'VoiceInput2PCClipboard', 0, 0, 0, 0, 0, None, None, None, None)
    try:
        for _ in range(15):
            if user32.OpenClipboard(owner):
                break
            time.sleep(0.02)
        else:
            raise RuntimeError('剪贴板正被其他程序使用')
        try:
            if not user32.EmptyClipboard() or not user32.SetClipboardData(13, handle):
                raise RuntimeError('写入剪贴板失败')
            handle = None  # Ownership transferred to Windows.
        finally:
            user32.CloseClipboard()
    finally:
        if handle:
            kernel32.GlobalFree(handle)
        if owner:
            user32.DestroyWindow(owner)


def paste_text(text):
    target = user32.GetForegroundWindow()
    if not target:
        raise RuntimeError('请先在电脑选中输入框')
    if any(user32.GetAsyncKeyState(k) & 0x8000 for k in (0x10, 0x11, 0x12, 0x5B, 0x5C)):
        raise RuntimeError('电脑正按着修饰键，请从历史中复制')
    copy_text(text)
    if user32.GetForegroundWindow() != target:
        raise RuntimeError('电脑窗口刚刚切换，可按 Ctrl+V 粘贴')
    keys = (INPUT * 4)()
    for index, (key, flags) in enumerate(((0x11, 0), (0x56, 0), (0x56, 2), (0x11, 2))):
        keys[index].type = 1
        keys[index].ki = KEYBDINPUT(key, 0, flags, 0, 0)
    count = user32.SendInput(4, keys, C.sizeof(INPUT))
    if count != 4:
        # Avoid a stuck modifier after a partial insertion. Never retry the paste.
        releases = (INPUT * 2)()
        for i, key in enumerate((0x56, 0x11)):
            releases[i].type = 1
            releases[i].ki = KEYBDINPUT(key, 0, 2, 0, 0)
        user32.SendInput(2, releases, C.sizeof(INPUT))
        raise RuntimeError('当前窗口不允许自动输入，可按 Ctrl+V 粘贴')
