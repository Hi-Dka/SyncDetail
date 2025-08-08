import argparse
import os
import signal
import sys
import time
from typing import List

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from db import Database
from scanner import full_refresh
from watcher import start_watch

# ---------------- CONFIG ----------------
MEDIA_PATH = os.path.expanduser('~/Media/plex')  # 要监听的路径
SOURCE_PATH = '~/Media/source'               # 源文件路径
DB_PATH = os.path.expanduser('~/Media/file_links.db')  # 确保 ~ 被正确解析为主目录

def _norm_dirs(dirs: List[str]) -> List[str]:
    out = []
    for d in dirs:
        p = os.path.abspath(os.path.expanduser(d))
        if os.path.isdir(p):
            out.append(p.rstrip(os.sep))
    # 去重并按长度降序，便于前缀匹配更准确（长前缀优先）
    return sorted(list(set(out)), key=lambda x: (-len(x), x))

def make_categorizer(src_dirs: List[str], media_dirs: List[str]):
    # 返回函数：path -> 'source' | 'media' | None
    def is_under(path: str, root: str) -> bool:
        try:
            path_abs = os.path.abspath(path)
            root_abs = root
            return path_abs == root_abs or path_abs.startswith(root_abs + os.sep)
        except Exception:
            return False

    def categorize(path: str):
        for r in media_dirs:
            if is_under(path, r): return "media"
        for r in src_dirs:
            if is_under(path, r): return "source"
        return None
    return categorize

def parse_args():
    ap = argparse.ArgumentParser(description="Inotify-based indexer for source/media with SQLite sync.")
    ap.add_argument("--db", default=os.path.abspath("./index.db"), help="SQLite db path (default: ./index.db)")
    ap.add_argument("--source", action="append", default=[], help="Source directory (repeatable)")
    ap.add_argument("--media", action="append", default=[], help="Media directory (repeatable)")
    return ap.parse_args()

# ---------------- MAIN ----------------
def main():
    args = parse_args()
    src_dirs = _norm_dirs(args.source)
    media_dirs = _norm_dirs(args.media)
    if not src_dirs and not media_dirs:
        print("No directories provided. Use --source and/or --media.", file=sys.stderr)
        sys.exit(2)

    db = Database(args.db)
    categorize = make_categorizer(src_dirs, media_dirs)

    # 启动时全量刷新
    full_refresh(db, src_dirs, media_dirs, categorize)

    # 启动监控
    observer, q, t = start_watch(db, src_dirs, media_dirs, categorize)

    # 优雅退出
    def shutdown(signum, frame):
        try:
            observer.stop()
            observer.join(timeout=5)
        finally:
            q.put(None)
            t.join(timeout=5)
            sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # 阻塞主线程
    try:
        signal.pause()
    except AttributeError:
        # Windows 无 signal.pause，循环等待（虽然本项目偏 Linux）
        while True:
            signal.sigwait({signal.SIGINT, signal.SIGTERM})

if __name__ == "__main__":
    # 确保当前目录在 sys.path 中
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # 使用新的Database类
    db = Database(DB_PATH)
    
    # 设置源文件和媒体文件目录
    src_dirs = [os.path.expanduser(SOURCE_PATH)]
    media_dirs = [MEDIA_PATH]
    
    print(f"[INFO] Source directories: {src_dirs}")
    print(f"[INFO] Media directories: {media_dirs}")
    
    # 检查目录是否存在
    for src_dir in src_dirs:
        if not os.path.exists(src_dir):
            print(f"[WARNING] Source directory does not exist: {src_dir}")
            os.makedirs(src_dir, exist_ok=True)
            print(f"[INFO] Created source directory: {src_dir}")
        else:
            print(f"[INFO] Source directory exists: {src_dir}")
    
    for media_dir in media_dirs:
        if not os.path.exists(media_dir):
            print(f"[WARNING] Media directory does not exist: {media_dir}")
            os.makedirs(media_dir, exist_ok=True)
            print(f"[INFO] Created media directory: {media_dir}")
        else:
            print(f"[INFO] Media directory exists: {media_dir}")
    
    categorize = make_categorizer(src_dirs, media_dirs)

    print("[SCAN] Starting full refresh scan...")
    try:
        # 使用新的全量刷新逻辑
        full_refresh(db, src_dirs, media_dirs, categorize)
        print("[SCAN] Full refresh completed successfully")
    except Exception as e:
        print(f"[ERROR] Full refresh failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print(f"[WATCHING] Starting file watcher...")
    try:
        # 使用新的监控逻辑
        observer, q, t = start_watch(db, src_dirs, media_dirs, categorize)
        print(f"[WATCHING] Now watching: {', '.join(src_dirs + media_dirs)}")
    except Exception as e:
        print(f"[ERROR] Failed to start watcher: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # 优雅退出
    def shutdown(signum, frame):
        print("[INFO] Shutting down...")
        try:
            observer.stop()
            observer.join(timeout=5)
        finally:
            q.put(None)
            t.join(timeout=5)
            print("[INFO] Shutdown complete")
            sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("[INFO] Program is running. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown(None, None)