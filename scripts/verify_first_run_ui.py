"""Verify the packaged receiver exposes first-run UI and reactivates it.

The test uses a fresh temporary configuration directory, never completes setup,
and closes the dialog cleanly when verification finishes.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from pathlib import Path
import subprocess
import tempfile
import time


FIRST_RUN_TITLE = '手机万能输入法 · 首次设置'
SW_HIDE = 0
WM_CLOSE = 0x0010


def load_user32():
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW.restype = wintypes.BOOL
    return user32


def wait_until(predicate, timeout, message):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError(message)


def stop_process_tree(process):
    if process.poll() is not None:
        return
    process.kill()
    try:
        process.wait(timeout=5)
        return
    except subprocess.TimeoutExpired:
        pass
    subprocess.run(
        ['taskkill.exe', '/PID', str(process.pid), '/T', '/F'],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=10,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('executable', type=Path)
    parser.add_argument('--timeout', type=float, default=20)
    args = parser.parse_args()
    executable = args.executable.resolve()
    if not executable.is_file():
        raise FileNotFoundError(executable)

    user32 = load_user32()
    with tempfile.TemporaryDirectory(prefix='VoiceInput2PC-first-run-') as folder:
        command = [str(executable), '--config-dir', folder]
        process = subprocess.Popen(command)
        window = 0
        try:
            window = wait_until(
                lambda: user32.FindWindowW(None, FIRST_RUN_TITLE),
                args.timeout,
                'The first-run window was not created.',
            )
            wait_until(
                lambda: user32.IsWindowVisible(window),
                args.timeout,
                'The first-run window exists but is not visible.',
            )

            user32.ShowWindow(window, SW_HIDE)
            wait_until(
                lambda: not user32.IsWindowVisible(window),
                5,
                'The test could not hide the first-run window before reactivation.',
            )

            second = subprocess.run(command, timeout=args.timeout, check=False)
            if second.returncode != 0:
                raise AssertionError(f'The second launch exited with {second.returncode}.')
            wait_until(
                lambda: user32.IsWindowVisible(window),
                args.timeout,
                'A second manual launch did not reveal the existing first-run window.',
            )
            print('PASS: packaged first-run window is visible and a second launch reveals it.')
        finally:
            if window:
                user32.PostMessageW(window, WM_CLOSE, 0, 0)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                stop_process_tree(process)


if __name__ == '__main__':
    main()
