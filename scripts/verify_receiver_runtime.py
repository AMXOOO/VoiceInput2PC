"""Verify packaged background startup, HTTPS health, and manual reactivation."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
from http.client import HTTPSConnection
import json
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from receiver.pairing import prepare_receiver


APP_TITLE = '语音输入电脑 · 电脑接收端'


def load_user32():
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    return user32


def windows_for_process(user32, process_id):
    windows = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def collect(window, _parameter):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(window, ctypes.byref(owner))
        if owner.value == process_id:
            length = user32.GetWindowTextLengthW(window)
            title = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(window, title, length + 1)
            windows.append((window, title.value, bool(user32.IsWindowVisible(window))))
        return True

    user32.EnumWindows(callback_type(collect), 0)
    return windows


def wait_until(predicate, timeout, message):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError(message)


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def verify_health(folder, port, token, fingerprint, timeout):
    context = ssl.create_default_context(cafile=str(folder / 'cert.pem'))
    context.check_hostname = False

    def request_health():
        connection = HTTPSConnection('127.0.0.1', port, timeout=1, context=context)
        try:
            connection.connect()
            actual = hashlib.sha256(connection.sock.getpeercert(binary_form=True)).hexdigest()
            if actual != fingerprint:
                raise AssertionError('Certificate fingerprint mismatch.')
            connection.request('GET', '/health', headers={'Authorization': 'Bearer ' + token})
            response = connection.getresponse()
            data = json.loads(response.read())
            return response.status == 200 and data.get('ok') and data.get('app') == 'VoiceInput2PC'
        except (ConnectionError, OSError, ssl.SSLError):
            return False
        finally:
            connection.close()

    wait_until(request_health, timeout, 'The packaged HTTPS receiver did not become healthy.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('executable', type=Path)
    parser.add_argument('--timeout', type=float, default=20)
    args = parser.parse_args()
    executable = args.executable.resolve()
    if not executable.is_file():
        raise FileNotFoundError(executable)

    user32 = load_user32()
    with tempfile.TemporaryDirectory(prefix='VoiceInput2PC-runtime-') as temporary:
        folder = Path(temporary)
        pairing = prepare_receiver(folder, '127.0.0.1', free_port())
        command = [str(executable), '--config-dir', str(folder)]
        process = subprocess.Popen(command + ['--background'])
        try:
            def main_window():
                for window, title, visible in windows_for_process(user32, process.pid):
                    if title == APP_TITLE:
                        return window, visible
                return None

            window, visible = wait_until(
                main_window,
                args.timeout,
                'The configured receiver did not create its main window.',
            )
            if visible:
                raise AssertionError('Background startup unexpectedly displayed the main window.')
            verify_health(folder, pairing.port, pairing.token, pairing.fingerprint, args.timeout)

            second = subprocess.run(command, timeout=args.timeout, check=False)
            if second.returncode != 0:
                raise AssertionError(f'The manual reactivation launch exited with {second.returncode}.')
            wait_until(
                lambda: bool(user32.IsWindowVisible(window)),
                args.timeout,
                'A manual launch did not reveal the background receiver window.',
            )
            print('PASS: background startup stayed hidden, HTTPS was healthy, and manual launch revealed the window.')
        finally:
            if process.poll() is None:
                # The receiver owns an embedded Tailcat child process. Kill the
                # whole test process tree while the parent PID still exists;
                # terminating only the parent would orphan tailcat.exe and keep
                # the extracted package directory locked.
                subprocess.run(
                    ['taskkill.exe', '/PID', str(process.pid), '/T', '/F'],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                )
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == '__main__':
    main()
