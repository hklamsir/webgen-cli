import logging
import os
from pathlib import Path
import time

import pytest

from sync_handler import HtmlSynchronizer, HtmlSyncHandler

class DummySync:
    def __init__(self):
        self.calls = []
    def sync_to_workings(self, p):
        self.calls.append(str(p))
        return True


def test_sync_main_extracted(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    src = proj / "index.html"
    src.write_text("<html><main><p>Hi</p></main><footer>f</footer></html>", encoding="utf-8")

    syncer = HtmlSynchronizer(proj, logging.getLogger("t"))
    assert syncer.sync_to_workings(src) is True
    out = proj / "workings" / "index.html"
    assert out.exists()
    assert "<p>Hi</p>" in out.read_text(encoding="utf-8")


def test_sync_body_fallback(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    src = proj / "page.html"
    src.write_text("<html><body><div>BodyContent</div></body></html>", encoding="utf-8")

    syncer = HtmlSynchronizer(proj, logging.getLogger("t"))
    assert syncer.sync_to_workings(src) is True
    out = proj / "workings" / "page.html"
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "BodyContent" in content
    assert "自動同步" in content or "同步失敗" not in content


def test_sync_retries_on_permission(tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    proj.mkdir()
    src = proj / "index.html"
    src.write_text("<main>ok</main><footer></footer>", encoding="utf-8")

    calls = {"n": 0}
    def fake_read_text(self, encoding='utf-8'):
        calls['n'] += 1
        if calls['n'] == 1:
            raise PermissionError("locked")
        return Path(self).read_text(encoding=encoding) if isinstance(self, str) else Path(self).read_text(encoding=encoding)

    # monkeypatch Path.read_text to simulate first-call PermissionError
    orig = Path.read_text
    def wrapper(self, encoding='utf-8'):
        calls['n'] += 1
        if calls['n'] == 1:
            raise PermissionError("locked")
        return orig(self, encoding=encoding)
    monkeypatch.setattr(Path, 'read_text', wrapper)

    syncer = HtmlSynchronizer(proj, logging.getLogger("t"))
    assert syncer.sync_to_workings(src) is True
    out = proj / 'workings' / 'index.html'
    assert out.exists()


def test_handle_event_mtime_ignored(tmp_path):
    proj = tmp_path / 'proj'; proj.mkdir()
    src = proj / 'a.html'; src.write_text('<main>x</main><footer></footer>')
    fake_sync = DummySync()
    handler = HtmlSyncHandler(proj, fake_sync, lambda p: None)
    rp = src.resolve()
    handler.last_mtimes[rp] = rp.stat().st_mtime

    # calling _handle_event with same mtime should not call sync
    handler._handle_event(str(src))
    assert fake_sync.calls == []


def test_handle_event_delete_and_remove_lastmtime(tmp_path):
    proj = tmp_path / 'proj'; proj.mkdir()
    src = proj / 'b.html'; src.write_text('<main>b</main><footer></footer>')
    fake_sync = DummySync()
    handler = HtmlSyncHandler(proj, fake_sync, lambda p: None)
    rp = src.resolve()
    handler.last_mtimes[rp] = rp.stat().st_mtime

    # delete file then call event
    src.unlink()
    handler._handle_event(str(src))
    assert rp not in handler.last_mtimes


def test_resume_preloads(tmp_path):
    proj = tmp_path / 'proj'; proj.mkdir()
    # create files
    (proj / 'index.html').write_text('<main>i</main><footer></footer>')
    (proj / 'sub').mkdir()
    (proj / 'sub' / 'page.html').write_text('<main>p</main><footer></footer>')
    # workings should be ignored
    w = proj / 'workings'; w.mkdir(); (w / 'w.html').write_text('<main>w</main><footer></footer>')

    handler = HtmlSyncHandler(proj, DummySync(), lambda p: None)
    # clear any preloaded
    handler.last_mtimes.clear()
    handler.resume()
    # ensure last_mtimes contains non-workings files
    keys = list(handler.last_mtimes.keys())
    assert any(str(k).endswith('index.html') for k in keys)
    assert not any('workings' in str(k) for k in keys)
