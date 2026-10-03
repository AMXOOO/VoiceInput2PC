import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
import queue
import threading
import tempfile
import datetime
import sqlite3
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import pystray
from PIL import Image, ImageDraw
from receiver.core import Relay, InvalidMessage
from receiver.http_server import make_server
from receiver.file_transfer import FileTransferManager
from receiver.first_run import run_first_setup, show_pairing
from receiver.pairing import load_pairing, prepare_receiver
from receiver.win_input import type_text, capture_target, copy_text


APP_VERSION = '0.5.0'
APP_TITLE = '语音输入电脑 · 电脑接收端'
FIRST_RUN_TITLE = '语音输入电脑 · 首次设置'
PAIRING_TITLE = '语音输入电脑 · 配对手机'
ERROR_ALREADY_EXISTS = 183
SW_RESTORE = 9


def read_history(relay):
    try:
        return relay.recent(), ''
    except (sqlite3.Error, OSError):
        return None, '暂时无法读取历史记录；仍可在托盘暂停或退出，稍后重试'


def queue_clipboard_for_phone(relay, read_clipboard):
    try:
        text = read_clipboard()
    except (tk.TclError, TypeError):
        return False, '剪贴板里没有可发送的纯文字'
    if not isinstance(text, str) or not text.strip():
        return False, '剪贴板里没有可发送的纯文字'
    try:
        relay.queue_for_phone(text)
    except InvalidMessage:
        return False, '剪贴板文字过长或包含不支持的字符，未改变原待接收文字'
    except (sqlite3.Error, OSError):
        return False, '暂时无法保存待接收文字，请稍后重试'
    return True, '已准备发送到手机 · 请在手机点“接收”'


def pump_commands(commands, handle, schedule, report_error):
    running = True
    try:
        while not commands.empty():
            if handle(commands.get_nowait()) is False:
                running = False
                return
    except Exception as exc:
        report_error(exc)
    finally:
        if running:
            schedule()


def startup_error_message(exc, stage, folder, port):
    lines = ['接收端启动失败：' + stage, '配置目录：' + str(folder)]
    if port is not None:
        lines.append('监听端口：' + str(port))
    code = getattr(exc, 'winerror', None) or getattr(exc, 'errno', None)
    lines.append(type(exc).__name__ + ((' [' + str(code) + ']') if code else '') + '：' + str(exc))
    return '\n'.join(lines)


def should_show_main_window(background=False, show=False, first_setup=False):
    """Manual launches are visible; only explicit background launches stay in the tray."""
    return first_setup or show or not background


def _load_user32():
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    return user32


def activate_existing_window(user32=None):
    """Reveal the active setup, pairing, or main window for a second manual launch."""
    user32 = user32 or _load_user32()
    for title in (FIRST_RUN_TITLE, PAIRING_TITLE, APP_TITLE):
        window = user32.FindWindowW(None, title)
        if window:
            user32.ShowWindow(window, SW_RESTORE)
            user32.SetForegroundWindow(window)
            return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config-dir', default=str(Path(os.environ['LOCALAPPDATA']) / 'VoiceInput2PC'))
    parser.add_argument('--show', action='store_true', help='show the receiver window (kept for compatibility)')
    parser.add_argument('--background', action='store_true', help='start in the notification area')
    parser.add_argument('--version', action='version', version=f'VoiceInput2PCReceiver {APP_VERSION}')
    parser.add_argument('--diagnostic-report', default=str(Path(tempfile.gettempdir()) / 'VoiceInput2PC-startup.json'))
    args = parser.parse_args()
    folder = Path(args.config_dir)
    # Enforce one process before opening/recovering the message database.
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    identity = hashlib.sha256(str(folder.resolve()).lower().encode()).hexdigest()[:16]
    mutex = kernel.CreateMutexW(None, False, 'Local\\VoiceInput2PC-' + identity)
    if not mutex:
        return
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        if not args.background:
            activate_existing_window()
        kernel.CloseHandle(mutex)
        return
    root = tk.Tk()
    root.withdraw()
    root.title(APP_TITLE)
    root.geometry('680x470')
    root.protocol('WM_DELETE_WINDOW', root.withdraw)
    stage, port = '读取配置', None
    first_setup = False
    try:
        if not (folder / 'config.json').is_file():
            stage = '首次设置'
            if not run_first_setup(root, folder, Path(sys.executable)):
                root.destroy()
                kernel.CloseHandle(mutex)
                return
            first_setup = True
        current_pairing = load_pairing(folder)
        port = current_pairing.port
        stage = '打开本机消息记录'
        relay = Relay(folder / 'messages.db', type_text, target_provider=capture_target)
        file_manager = FileTransferManager(folder)
        stage = '启动监听'
        server = make_server(('0.0.0.0', current_pairing.port), relay, current_pairing.token,
                             folder / 'cert.pem', folder / 'key.pem', file_manager=file_manager)
    except Exception as exc:
        detail = startup_error_message(exc, stage, folder, port)
        try:
            Path(args.diagnostic_report).write_text(json.dumps({
                'time': datetime.datetime.now().isoformat(), 'ok': False,
                'stage': stage, 'detail': detail}, ensure_ascii=False), encoding='utf-8')
        except OSError:
            pass
        messagebox.showerror('语音输入电脑', detail)
        root.destroy()
        kernel.CloseHandle(mutex)
        return

    commands = queue.Queue()
    image = Image.new('RGBA', (64, 64), '#16705b')
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((10, 16, 54, 47), radius=5, outline='white', width=4)
    for y in (25, 34):
        for x in (19, 29, 39):
            draw.rectangle((x, y, x+4, y+3), fill='white')
    icon = pystray.Icon('VoiceInput2PC', image, '语音输入电脑 · 正在接收文字', menu=pystray.Menu(
        pystray.MenuItem('查看状态和最近文字', lambda *_: commands.put('show'), default=True),
        pystray.MenuItem('暂停自动输入', lambda *_: commands.put('pause'), checked=lambda _: relay.paused),
        pystray.MenuItem('退出', lambda *_: commands.put('exit'))))

    container = ttk.Frame(root, padding=18)
    container.pack(fill='both', expand=True)
    ttk.Label(container, text='语音输入电脑', font=('Microsoft YaHei UI', 20, 'bold')).pack(anchor='w')
    status = ttk.Label(container, text='正在接收 · 手机可通过局域网或跨网络安全连接')
    status.pack(anchor='w', pady=(6, 4))
    ttk.Label(container, text='电脑点中输入位置 → 手机开始输入 → 使用手机输入法的语音按钮。').pack(anchor='w')
    ttk.Label(container, text='无需逐条发送；不按回车、不改剪贴板。切换输入位置前请先暂停。').pack(anchor='w')
    ttk.Label(container, text='最近收到的文字（仅保存在本机，显示最近 100 条）').pack(anchor='w', pady=(20, 5))
    listing = tk.Listbox(container, height=6, font=('Microsoft YaHei UI', 10), exportselection=False)
    listing.pack(fill='x')
    preview = tk.Text(container, height=5, wrap='word', font=('Microsoft YaHei UI', 11))
    preview.pack(fill='both', expand=True, pady=8)
    rows = []

    def refresh():
        nonlocal rows
        snapshot, error = read_history(relay)
        if snapshot is None:
            status.config(text=error)
            return
        rows = snapshot
        listing.delete(0, 'end')
        for row in rows:
            prefix = '已发送' if row['status'] == 'inserted' else '仅保存'
            listing.insert('end', prefix + '  ' + row['text'].replace('\n', ' ')[:65])
        if rows:
            listing.selection_set(0)
            select()
        status.config(text='已暂停自动输入 · 新文字仍会保存' if relay.paused else '正在接收 · 手机可通过局域网或跨网络安全连接')

    def select(*_):
        sel = listing.curselection()
        preview.delete('1.0', 'end')
        if sel and sel[0] < len(rows):
            preview.insert('1.0', rows[sel[0]]['text'])

    def copy_selected():
        sel = listing.curselection()
        if sel:
            copy_text(rows[sel[0]]['text'])
            status.config(text='已复制，可切换到目标窗口按 Ctrl+V')

    def send_clipboard_to_phone():
        _, note = queue_clipboard_for_phone(relay, root.clipboard_get)
        status.config(text=note)

    listing.bind('<<ListboxSelect>>', select)
    buttons = ttk.Frame(container)
    buttons.pack(fill='x')
    ttk.Button(buttons, text='复制选中文字', command=copy_selected).pack(side='left')
    ttk.Button(buttons, text='发送剪贴板到手机', command=send_clipboard_to_phone).pack(side='left', padx=(8, 0))
    ttk.Button(buttons, text='刷新', command=refresh).pack(side='left', padx=8)
    ttk.Button(buttons, text='配对手机', command=lambda: open_pairing()).pack(side='left')
    ttk.Button(buttons, text='收起到托盘', command=root.withdraw).pack(side='right')

    def regenerate_pairing():
        nonlocal server, current_pairing, port
        previous_pause = relay.paused
        relay.paused = True
        status.config(text='正在更换配对码…')
        root.update_idletasks()
        server.shutdown()
        server.server_close()
        try:
            current_pairing = prepare_receiver(
                folder, current_pairing.host, current_pairing.port, regenerate=True)
            port = current_pairing.port
            server = make_server(('0.0.0.0', current_pairing.port), relay,
                                 current_pairing.token, folder / 'cert.pem', folder / 'key.pem',
                                 file_manager=file_manager)
            threading.Thread(target=server.serve_forever, daemon=True).start()
        except Exception as exc:
            detail = startup_error_message(exc, '更换配对码', folder, port)
            status.config(text='更换配对码失败，请退出后重新打开接收端')
            messagebox.showerror('语音输入电脑', detail, parent=root)
            return
        finally:
            relay.paused = previous_pause
            icon.update_menu()
        refresh()
        show_pairing(root, current_pairing, allow_regenerate=True,
                     on_regenerate=regenerate_pairing)

    def open_pairing():
        show_pairing(root, current_pairing, allow_regenerate=True,
                     on_regenerate=regenerate_pairing)

    def handle_command(command):
        if command == 'show':
            refresh()
            root.deiconify()
            root.lift()
            root.focus_force()
        elif command == 'pause':
            relay.paused = not relay.paused
            icon.update_menu()
            refresh()
        elif command == 'exit':
            icon.stop()
            threading.Thread(target=server.shutdown, daemon=True).start()
            root.destroy()
            return False
        return True

    def poll():
        pump_commands(commands, handle_command, lambda: root.after(200, poll),
                      lambda exc: status.config(text='界面操作暂未成功，可在托盘重试或退出'))

    threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Thread(target=icon.run, daemon=True).start()
    if should_show_main_window(args.background, args.show, first_setup):
        commands.put('show')
    if first_setup:
        root.after(250, lambda: show_pairing(
            root, current_pairing, allow_regenerate=True,
            on_regenerate=regenerate_pairing))
    try:
        Path(args.diagnostic_report).write_text(json.dumps({
            'time': datetime.datetime.now().isoformat(), 'ok': True,
            'config_dir': str(folder), 'port': port}, ensure_ascii=False), encoding='utf-8')
    except OSError:
        pass
    poll()
    root.mainloop()
    server.server_close()
    kernel.CloseHandle(mutex)


if __name__ == '__main__':
    main()
