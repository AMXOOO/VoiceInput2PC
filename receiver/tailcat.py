"""Internal Tailcat runtime for VoiceInput2PC cross-network pairing.

Tailcat is an implementation detail. VoiceInput2PC always launches it with an
ephemeral identity so the app never depends on, reads, or mutates a user's
standalone Tailcat configuration.
"""

from __future__ import annotations

import atexit
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import time


_ADDRESS = re.compile(r'\b(tc[A-Za-z0-9_-]{20,4094})\b')


class TailcatUnavailable(RuntimeError):
    pass


def find_tailcat() -> Path | None:
    override = os.environ.get('VOICEINPUT2PC_TAILCAT')
    candidates = []
    if override:
        candidates.append(Path(override))
    bundle_root = Path(getattr(sys, '_MEIPASS', Path(sys.executable).resolve().parent))
    candidates.append(bundle_root / 'tailcat' / 'tailcat.exe')
    candidates.append(Path(__file__).resolve().parents[1] / 'vendor' / 'tailcat' / 'windows' / 'tailcat.exe')
    command = shutil.which('tailcat')
    if command:
        candidates.append(Path(command))
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue
    return None


def _safe_diagnostic(line: str) -> str:
    text = _ADDRESS.sub('tc<redacted>', (line or '').strip())
    # Keep UI diagnostics useful while avoiding giant network dumps.
    return text[:400]


class TailcatServer:
    def __init__(self, port: int, key_path: Path):
        self.port = int(port)
        self.key_path = Path(key_path)
        self.process: subprocess.Popen[str] | None = None
        self.address: str | None = None
        self._lines: queue.Queue[str] = queue.Queue()
        self._reader: threading.Thread | None = None
        self._diagnostics: list[str] = []

    @staticmethod
    def available() -> bool:
        return find_tailcat() is not None

    def start(self, timeout: float = 15.0) -> str:
        if self.process is not None and self.process.poll() is None and self.address:
            return self.address
        binary = find_tailcat()
        if binary is None:
            raise TailcatUnavailable('当前接收端未包含跨网络组件')

        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        self._ensure_key(binary, flags)
        self.process = subprocess.Popen(
            [str(binary), '--key=' + str(self.key_path), '--json', 'serve', str(self.port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding='utf-8',
            errors='replace',
            creationflags=flags,
        )
        self._reader = threading.Thread(target=self._drain, daemon=True)
        self._reader.start()

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            code = self.process.poll()
            if code is not None:
                if self._reader is not None:
                    self._reader.join(timeout=0.3)
                detail = self._diagnostic_summary()
                suffix = f'（退出码 {code}' + (f'：{detail}' if detail else '') + '）'
                raise TailcatUnavailable('跨网络组件启动失败' + suffix)
            try:
                line = self._lines.get(timeout=0.25)
            except queue.Empty:
                continue
            match = _ADDRESS.search(line)
            if match:
                self.address = match.group(1)
                return self.address
        self.stop()
        detail = self._diagnostic_summary()
        raise TailcatUnavailable(
            '跨网络连接建立超时' + (f'：{detail}' if detail else ''))

    def _ensure_key(self, binary: Path, flags: int):
        if self.key_path.is_file():
            return
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            [str(binary), 'genkey', '--fixed-region', '--key=' + str(self.key_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding='utf-8',
            errors='replace',
            creationflags=flags,
            timeout=30,
        )
        if completed.returncode != 0 or not self.key_path.is_file():
            detail = _safe_diagnostic(completed.stderr)
            raise TailcatUnavailable(
                '跨网络身份初始化失败' + (f'：{detail}' if detail else ''))

    def _drain(self):
        stream = self.process.stdout if self.process is not None else None
        if stream is None:
            return
        try:
            for line in stream:
                safe = _safe_diagnostic(line)
                if safe:
                    self._diagnostics.append(safe)
                    if len(self._diagnostics) > 6:
                        del self._diagnostics[0]
                self._lines.put(line)
        except (OSError, ValueError):
            return

    def _diagnostic_summary(self) -> str:
        return ' | '.join(self._diagnostics[-3:])

    def stop(self):
        process = self.process
        self.process = None
        self.address = None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass


_ACTIVE: dict[tuple[int, str], TailcatServer] = {}


def get_or_start(port: int, key_path: Path) -> TailcatServer:
    key = (int(port), str(Path(key_path).resolve()))
    existing = _ACTIVE.get(key)
    if existing is not None and existing.process is not None and existing.process.poll() is None:
        if existing.address is None:
            existing.start()
        return existing
    server = TailcatServer(port, Path(key_path))
    server.start()
    _ACTIVE[key] = server
    return server


def stop_all():
    while _ACTIVE:
        _, server = _ACTIVE.popitem()
        server.stop()


atexit.register(stop_all)
