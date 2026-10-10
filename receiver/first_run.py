"""First-run and phone-pairing UI for the Windows receiver."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
import winreg

from PIL import ImageTk
import qrcode

from receiver.pairing import (
    DEFAULT_PORT,
    Pairing,
    TRANSPORT_TAILCAT,
    TRANSPORT_AUTO,
    TRANSPORT_LAN,
    detect_private_addresses,
    encode_pairing,
    prepare_receiver,
    validate_host,
    validate_port,
)
from receiver.tailcat import TailcatUnavailable, find_tailcat, get_or_start


AUTOSTART_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
AUTOSTART_NAME = 'VoiceInput2PC'
BACKGROUND_ARGUMENT = '--background'


@dataclass(frozen=True)
class PairingViewModel:
    endpoint: str
    transport_label: str
    uri: str = field(repr=False)


def choose_default_address(addresses) -> str:
    """Choose a LAN address before a Tailscale address."""
    ranked = detect_private_addresses(addresses)
    if not ranked:
        raise ValueError('没有找到可供手机连接的本机地址')
    return ranked[0]


def autostart_command(executable: Path) -> str:
    return '"' + str(Path(executable)) + '" ' + BACKGROUND_ARGUMENT


def pairing_view_model(pairing: Pairing) -> PairingViewModel:
    if pairing.transport == TRANSPORT_AUTO:
        return PairingViewModel('自动连接', '本地优先 · 必要时自动切换跨网络',
                                encode_pairing(pairing))
    if pairing.transport == TRANSPORT_TAILCAT:
        return PairingViewModel('跨网络安全连接', '远程安全连接', encode_pairing(pairing))
    return PairingViewModel(f'{pairing.host}:{pairing.port}', '局域网 HTTPS', encode_pairing(pairing))


def set_autostart(enabled: bool, executable: Path) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, AUTOSTART_NAME, 0, winreg.REG_SZ,
                              autostart_command(executable))
        else:
            try:
                winreg.DeleteValue(key, AUTOSTART_NAME)
            except FileNotFoundError:
                pass


class FirstRunDialog:
    def __init__(self, root, folder: Path, executable: Path):
        self.root = root
        self.folder = Path(folder)
        self.executable = Path(executable)
        self.completed = False
        addresses = detect_private_addresses()
        self.window = tk.Toplevel(root)
        self.window.title('语音输入电脑 · 首次设置')
        self.window.resizable(False, False)
        self.window.protocol('WM_DELETE_WINDOW', self.window.destroy)
        if self.root.state() != 'withdrawn':
            self.window.transient(root)

        frame = ttk.Frame(self.window, padding=22)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='连接这台电脑',
                  font=('Microsoft YaHei UI', 18, 'bold')).grid(
                      row=0, column=0, columnspan=2, sticky='w')
        ttk.Label(frame, text='先配置本机接收端。手机只需扫码一次，之后由程序自动选择本地或跨网络连接。').grid(
            row=1, column=0, columnspan=2, sticky='w', pady=(6, 18))
        ttk.Label(frame, text='电脑地址').grid(row=2, column=0, sticky='w', pady=6)
        self.host = tk.StringVar(value=addresses[0] if addresses else '')
        ttk.Combobox(frame, textvariable=self.host, values=addresses,
                     width=31).grid(row=2, column=1, sticky='ew', padx=(12, 0), pady=6)
        ttk.Label(frame, text='监听端口').grid(row=3, column=0, sticky='w', pady=6)
        self.port = tk.StringVar(value=str(DEFAULT_PORT))
        ttk.Entry(frame, textvariable=self.port, width=33).grid(
            row=3, column=1, sticky='ew', padx=(12, 0), pady=6)
        self.autostart = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text='开机后自动启动接收端', variable=self.autostart).grid(
            row=4, column=0, columnspan=2, sticky='w', pady=(12, 18))
        ttk.Button(frame, text='生成配对码', command=self.submit).grid(
            row=5, column=1, sticky='e')
        self.window.bind('<Return>', lambda _event: self.submit())

    def submit(self):
        try:
            host = validate_host(self.host.get())
            port = validate_port(int(self.port.get()))
            prepare_receiver(self.folder, host, port)
            set_autostart(self.autostart.get(), self.executable)
        except (OSError, ValueError) as exc:
            messagebox.showerror('语音输入电脑', '设置未完成：' + str(exc), parent=self.window)
            return
        self.completed = True
        self.window.destroy()

    def run(self) -> bool:
        self.window.update_idletasks()
        width = self.window.winfo_reqwidth()
        height = self.window.winfo_reqheight()
        x = max(0, (self.window.winfo_screenwidth() - width) // 2)
        y = max(0, (self.window.winfo_screenheight() - height) // 2)
        self.window.geometry(f'+{x}+{y}')
        self.window.deiconify()
        self.window.lift()
        self.window.grab_set()
        self.window.focus_force()
        self.root.wait_window(self.window)
        return self.completed


class PairingDialog:
    def __init__(self, root, pairing: Pairing, allow_regenerate: bool,
                 on_regenerate=None, remote_enabled=True):
        self.root = root
        self.window = tk.Toplevel(root)
        self.window.title('语音输入电脑 · 配对手机')
        self.window.resizable(True, True)
        self.window.minsize(480, 440)
        self.window.geometry(f'620x{min(760, self.window.winfo_screenheight() - 100)}')
        self.window.transient(root)

        self.remote_warning = ''
        local_pairing = replace(pairing, transport=TRANSPORT_LAN, tailcat_address='')
        self.pairing = local_pairing
        if remote_enabled:
            try:
                server = get_or_start(pairing.port)
                if not server.address:
                    raise TailcatUnavailable('没有获得跨网络地址')
                self.pairing = replace(local_pairing, transport=TRANSPORT_AUTO,
                                       tailcat_address=server.address)
            except (OSError, ValueError, TailcatUnavailable):
                self.remote_warning = '跨网络连接暂不可用；本次配对仅支持局域网。'

        self.view = pairing_view_model(self.pairing)

        frame = ttk.Frame(self.window, padding=20)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='扫码连接这台电脑',
                  font=('Microsoft YaHei UI', 17, 'bold')).pack(anchor='center')
        ttk.Label(frame, text=('局域网优先；无法直连时使用跨网络备用。' if remote_enabled
                               else '仅局域网直连；跨网络连接已关闭。')).pack(
            anchor='center', pady=(5, 8))
        self.mode_label = ttk.Label(frame, text='')
        self.mode_label.pack(anchor='center', pady=(0, 8))
        self.endpoint_label = ttk.Label(frame, text='')
        self.endpoint_label.pack(anchor='center', pady=(8, 3))
        if self.remote_warning:
            warning = ttk.Label(frame, text=self.remote_warning, foreground='#a84623',
                                wraplength=360, justify='center')
            warning.pack(anchor='center', pady=(4, 4))
        ttk.Label(frame, text='配对码相当于连接密码，请勿截图公开或发给不信任的人。').pack(
            anchor='center')

        buttons = ttk.Frame(frame)
        buttons.pack(side='bottom', fill='x', pady=(14, 0))
        ttk.Button(buttons, text='复制完整配对码', command=self.copy).pack(side='left')
        if allow_regenerate and on_regenerate is not None:
            ttk.Button(buttons, text='换一组配对码', command=lambda: self.regenerate(
                on_regenerate)).pack(side='left', padx=8)
        ttk.Button(buttons, text='完成', command=self.window.destroy).pack(side='right')
        sizes = ttk.Frame(frame)
        sizes.pack(side='bottom', fill='x', pady=(10, 0))
        ttk.Label(sizes, text='二维码大小').pack(side='left')
        self.qr_size = tk.IntVar(value=360)
        ttk.Scale(sizes, from_=200, to=640, variable=self.qr_size,
                  command=lambda _value: self.render()).pack(side='left', fill='x', expand=True, padx=10)
        ttk.Button(sizes, text='恢复默认', command=self.reset_qr_size).pack(side='right')
        self.qr_size_label = ttk.Label(sizes, width=8)
        self.qr_size_label.pack(side='right')
        viewport = ttk.Frame(frame)
        viewport.pack(fill='both', expand=True, pady=8)
        viewport.rowconfigure(0, weight=1)
        viewport.columnconfigure(0, weight=1)
        self.qr_canvas = tk.Canvas(viewport, background='white', highlightthickness=0)
        self.qr_canvas.grid(row=0, column=0, sticky='nsew')
        xscroll = ttk.Scrollbar(viewport, orient='horizontal', command=self.qr_canvas.xview)
        yscroll = ttk.Scrollbar(viewport, orient='vertical', command=self.qr_canvas.yview)
        xscroll.grid(row=1, column=0, sticky='ew')
        yscroll.grid(row=0, column=1, sticky='ns')
        self.qr_canvas.configure(xscrollcommand=xscroll.set, yscrollcommand=yscroll.set)
        self.qr_canvas.bind('<Configure>', lambda _event: self.center_qr())
        self.render()

    def reset_qr_size(self):
        self.qr_size.set(360)
        self.render()

    def center_qr(self):
        if not hasattr(self, 'qr_image'):
            return
        size = self.qr_image.width()
        width = max(size, self.qr_canvas.winfo_width())
        height = max(size, self.qr_canvas.winfo_height())
        self.qr_canvas.coords('qr', (width - size) // 2, (height - size) // 2)
        self.qr_canvas.configure(scrollregion=(0, 0, width, height))

    def render(self):
        qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                           box_size=1, border=4)
        qr.add_data(self.view.uri)
        qr.make(fit=True)
        modules = len(qr.get_matrix())
        qr.box_size = max(1, int(self.qr_size.get()) // modules)
        image = qr.make_image(fill_color='black', back_color='white').convert('RGB')
        self.qr_image = ImageTk.PhotoImage(image)
        self.qr_canvas.delete('qr')
        self.qr_canvas.create_image(0, 0, image=self.qr_image, anchor='nw', tags='qr')
        self.qr_size_label.config(text=f'{image.width} 像素')
        self.center_qr()
        self.mode_label.config(text=self.view.transport_label)
        self.endpoint_label.config(text='连接方式：' + self.view.endpoint)

    def copy(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.view.uri)
        self.root.update_idletasks()
        messagebox.showinfo('语音输入电脑', '完整配对码已复制。', parent=self.window)

    def regenerate(self, callback):
        if not messagebox.askyesno(
                '更换配对码', '旧手机上的连接会立即失效，确定继续吗？', parent=self.window):
            return
        self.window.destroy()
        callback()

    def show_modal(self) -> None:
        self.window.grab_set()
        self.window.focus_force()
        self.root.wait_window(self.window)


def run_first_setup(root, folder: Path, executable: Path) -> bool:
    return FirstRunDialog(root, folder, executable).run()


def show_pairing(root, pairing: Pairing, allow_regenerate: bool,
                 on_regenerate=None, remote_enabled=True) -> None:
    PairingDialog(root, pairing, allow_regenerate, on_regenerate, remote_enabled).show_modal()
