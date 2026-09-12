import re
import sqlite3
import threading
import time
import secrets
from contextlib import contextmanager


class InvalidMessage(ValueError):
    pass


def validate_message(data):
    if not isinstance(data, dict):
        raise InvalidMessage('消息格式无效')
    key, text = data.get('id'), data.get('text')
    if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', key):
        raise InvalidMessage('消息编号无效')
    if not isinstance(text, str) or not text or len(text) > 20000:
        raise InvalidMessage('文字为空或超过两万字')
    if any(ord(c) < 32 and c not in '\r\n\t' for c in text):
        raise InvalidMessage('文字包含无效控制字符')
    try:
        text.encode('utf-8', errors='strict')
    except UnicodeError:
        raise InvalidMessage('文字编码无效') from None
    return key, text


class Relay:
    """Persist before injection; never replay an uncertain OS side effect."""

    def __init__(self, database, injector, *, target_provider=None, clock=time.monotonic):
        self.database = str(database)
        self.injector = injector
        self.lock = threading.RLock()
        self._paused = False
        self.target_provider = target_provider
        self.clock = clock
        self.session = None
        with self._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS messages '
                       '(id TEXT PRIMARY KEY, text TEXT NOT NULL, status TEXT NOT NULL, '
                       'note TEXT NOT NULL, created REAL NOT NULL)')
            db.execute("UPDATE messages SET status='saved', note='程序曾中断，请在电脑历史中核对' WHERE status='pending'")

    @property
    def paused(self):
        return self._paused

    @paused.setter
    def paused(self, value):
        with self.lock:
            self._paused = bool(value)
            if self._paused:
                self.session = None

    def begin_session(self):
        with self.lock:
            self.session = None
            if self.paused or self.target_provider is None:
                return {'ok': False, 'note': '请先在电脑托盘恢复自动输入'}
            try:
                target = self.target_provider()
            except RuntimeError as exc:
                return {'ok': False, 'note': str(exc)}
            token = secrets.token_urlsafe(32)
            self.session = (token, target, self.clock() + 120)
            return {'ok': True, 'session': token, 'note': '已连接当前电脑窗口，可以使用手机输入法'}

    def _target_for(self, data):
        session = self.session
        if session is None or data.get('session') != session[0]:
            raise RuntimeError('输入会话已失效，请选中电脑输入框后重新开始')
        if self.clock() >= session[2]:
            self.session = None
            raise RuntimeError('两分钟未输入，会话已暂停，请重新开始')
        try:
            if self.target_provider() != session[1]:
                raise RuntimeError('电脑输入窗口已改变，请选中目标后重新开始')
        except Exception:
            self.session = None
            raise
        return session[1]

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @contextmanager
    def _disarm_on_failure(self, data):
        try:
            yield
        except Exception:
            if self.session is not None and data.get('session') == self.session[0]:
                self.session = None
            raise

    def accept(self, data):
        key, text = validate_message(data)
        with self.lock, self._disarm_on_failure(data):
            with self._connect() as db:
                row = db.execute('SELECT * FROM messages WHERE id=?', (key,)).fetchone()
                if row:
                    if row['text'] != text:
                        raise InvalidMessage('同一消息编号对应了不同文字')
                    if row['status'] == 'pending':
                        note = '上次输入结果未能记录，请核对电脑；不会自动重复输入'
                        db.execute("UPDATE messages SET status='saved', note=? WHERE id=?", (note, key))
                        return {'ok': True, 'id': key, 'status': 'saved', 'note': note}
                    return {'ok': True, 'id': key, 'status': row['status'], 'note': row['note']}
                db.execute('INSERT INTO messages VALUES (?,?,?,?,?)',
                           (key, text, 'pending', '', time.time()))
            status, note = 'saved', '电脑已暂停自动输入，文字保存在历史中'
            if not self.paused:
                try:
                    if self.target_provider is None:
                        self.injector(text)
                    else:
                        target = self._target_for(data)
                        try:
                            # Text-only v2: no Enter/Tab or clipboard shortcuts.
                            plain = text.replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ').replace('\t', ' ')
                            self.injector(plain, target)
                        except Exception:
                            self.session = None
                            raise
                        token, target, _ = self.session
                        self.session = (token, target, self.clock() + 120)
                    status, note = 'inserted', '已交给电脑输入，请以目标窗口显示为准'
                except Exception as exc:
                    # Only controlled error descriptions, never include message text.
                    note = '已保存，请核对电脑：' + str(exc)[:180]
            with self._connect() as db:
                db.execute('UPDATE messages SET status=?, note=? WHERE id=?', (status, note, key))
            return {'ok': True, 'id': key, 'status': status, 'note': note}

    def recent(self, limit=100):
        with self.lock, self._connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM messages ORDER BY created DESC LIMIT ?', (limit,))]
