import logging
from pathlib import Path
import threading

import pytest

import file_watcher
from file_watcher import FileWatcher

class DummyObserver:
    def __init__(self):
        self.scheduled = False
        self.stopped = False
    def schedule(self, handler, path, recursive=True):
        self.scheduled = True
    def start(self):
        # no-op for tests
        return
    def stop(self):
        self.stopped = True

class DummyThread:
    def __init__(self, target=None, daemon=False):
        self._target = target
        self.join_called = False
    def start(self):
        # call target synchronously to avoid background thread in tests
        if self._target:
            self._target()
    def join(self, timeout=None):
        self.join_called = True

class DummySync:
    def __init__(self):
        self.calls = []
    def sync_to_workings(self, p):
        self.calls.append(str(p))
        return True

class DummyEvent:
    def __init__(self, src, dest, is_dir=False):
        self.src_path = src
        self.dest_path = dest
        self.is_directory = is_dir


def test_on_moved_triggers_sync(tmp_path):
    proj = tmp_path / 'proj'; proj.mkdir()
    old = proj / 'old.html'; old.write_text('<main>o</main><footer></footer>')
    new = proj / 'new.html'
    fake_sync = DummySync()
    handler = file_watcher.HtmlSyncHandler(proj, fake_sync, lambda p: None)
    handler.last_mtimes[old.resolve()] = old.stat().st_mtime

    e = DummyEvent(str(old), str(new), is_dir=False)
    # create destination file to simulate actual move
    new.write_text('<main>n</main><footer></footer>')
    handler.on_moved(e)
    assert len(fake_sync.calls) == 1
    assert old.resolve() not in handler.last_mtimes


def test_start_preloads_mtime_and_uses_dummy_observer(tmp_path, monkeypatch):
    proj = tmp_path / 'proj'; proj.mkdir()
    (proj / 'index.html').write_text('<main>i</main><footer></footer>')
    (proj / 'workings').mkdir()
    (proj / 'workings' / 'w.html').write_text('<main>w</main><footer></footer>')

    # monkeypatch Observer and threading.Thread in module
    monkeypatch.setattr(file_watcher, 'Observer', DummyObserver)
    monkeypatch.setattr(file_watcher, 'threading', file_watcher.threading)
    # monkeypatch Thread class used in file_watcher to our DummyThread
    monkeypatch.setattr(file_watcher.threading, 'Thread', DummyThread)

    watcher = FileWatcher(proj, logging.getLogger('t'), lambda p: None)
    watcher.start()
    # event_handler should have preloaded index.html but not workings/w.html
    keys = list(watcher.event_handler.last_mtimes.keys())
    assert any(str(k).endswith('index.html') for k in keys)
    assert not any('workings' in str(k) for k in keys)


def test_stop_calls_stop_and_join(monkeypatch):
    # setup watcher as in start test
    proj = Path('.')
    monkeypatch.setattr(file_watcher, 'Observer', DummyObserver)
    monkeypatch.setattr(file_watcher.threading, 'Thread', DummyThread)

    watcher = FileWatcher(proj, logging.getLogger('t'), lambda p: None)
    # create dummy observer and thread
    watcher.observer = DummyObserver()
    watcher.observer_thread = DummyThread(target=watcher.observer.start)
    watcher.event_handler = None
    watcher.synchronizer = None

    watcher.stop()
    assert watcher.observer is None
    assert watcher.observer_thread is None
