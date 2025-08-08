import os
import threading
import queue
from typing import Callable, Iterable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent, FileMovedEvent, FileDeletedEvent

from db import Database  # 修改为绝对导入

class _Handler(FileSystemEventHandler):
    def __init__(self, q: queue.Queue):
        super().__init__()
        self.q = q

    def on_created(self, event):
        if event.is_directory: return
        print(f"[WATCH] File created: {event.src_path}")
        self.q.put(("create", event.src_path))

    def on_modified(self, event):
        if event.is_directory: return
        print(f"[WATCH] File modified: {event.src_path}")
        self.q.put(("modify", event.src_path))

    def on_moved(self, event: FileMovedEvent):
        if event.is_directory: return
        print(f"[WATCH] File moved: {event.src_path} -> {event.dest_path}")
        self.q.put(("move", event.src_path, event.dest_path))

    def on_deleted(self, event):
        if event.is_directory: return
        print(f"[WATCH] File deleted: {event.src_path}")
        self.q.put(("delete", event.src_path))

def start_watch(db: Database, roots_source: Iterable[str], roots_media: Iterable[str], categorize: Callable[[str], str]):
    q: queue.Queue = queue.Queue()
    handler = _Handler(q)
    observer = Observer()
    roots = set(list(roots_source) + list(roots_media))
    
    print(f"[WATCH] Setting up watchers for {len(roots)} directories")
    for r in roots:
        print(f"[WATCH] Adding watch for: {r}")
        observer.schedule(handler, r, recursive=True)

    def worker():
        print("[WATCH] Worker thread started")
        while True:
            item = q.get()
            if item is None:  # stop signal
                print("[WATCH] Worker thread stopping")
                break
            try:
                kind = item[0]
                if kind in ("create", "modify"):
                    path = item[1]
                    cat = categorize(path)
                    if not cat: 
                        continue
                    if os.path.isfile(path):
                        print(f"[WATCH] Processing {kind}: {path} ({cat})")
                        db.handle_create_or_modify(path, cat)
                elif kind == "move":
                    src, dst = item[1], item[2]
                    dst_cat = categorize(dst)
                    if dst_cat and os.path.exists(dst) and os.path.isfile(dst):
                        print(f"[WATCH] Processing move: {src} -> {dst} ({dst_cat})")
                        db.handle_move(src, dst, dst_cat)
                    else:
                        # 目标不在监控范围或目标已不存在，按删除源处理
                        print(f"[WATCH] Move target out of scope, treating as delete: {src}")
                        db.handle_delete(src)
                elif kind == "delete":
                    path = item[1]
                    print(f"[WATCH] Processing delete: {path}")
                    db.handle_delete(path)
            except Exception as e:
                print(f"[WATCH] Error processing event {item}: {e}")
            finally:
                q.task_done()

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    observer.start()
    print("[WATCH] Observer started")
    return observer, q, t
