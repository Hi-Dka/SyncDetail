import os
import sqlite3
from contextlib import contextmanager
from typing import Optional, Iterable, Dict, Any, Tuple
from datetime import datetime
from qb import get_torrent_hash_from_file
from config import QB_ENABLED

class Database:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self._init_pragmas()
        self.init_schema()

    def _init_pragmas(self):
        cur = self.conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.execute("PRAGMA foreign_keys=ON;")
        cur.close()

    def init_schema(self):
        cur = self.conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS files (
            dev     INTEGER NOT NULL,
            ino     INTEGER NOT NULL,
            path    TEXT    NOT NULL,
            category TEXT   NOT NULL CHECK (category IN ('source','media')),
            size    INTEGER NOT NULL,
            mtime   REAL    NOT NULL,
            mtime_readable TEXT NOT NULL,
            PRIMARY KEY (dev, ino, path)
        );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_files_devino ON files(dev, ino);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);")
        cur.close()

    @contextmanager
    def tx(self):
        try:
            self.conn.execute("BEGIN;")
            yield
            self.conn.execute("COMMIT;")
        except Exception:
            self.conn.execute("ROLLBACK;")
            raise

    def row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        return dict(row) if row else {}

    def upsert_from_stat(self, path: str, category: str):
        st = os.stat(path, follow_symlinks=False)
        dev, ino, size, mtime = st.st_dev, st.st_ino, st.st_size, st.st_mtime
        mtime_readable = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        
        cur = self.conn.cursor()
        # 如果已经存在同 dev,ino,但 path 不同，允许并存（硬链接）
        cur.execute("""
            INSERT INTO files(dev, ino, path, category, size, mtime, mtime_readable)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(dev, ino, path) DO UPDATE SET
                category=excluded.category,
                size=excluded.size,
                mtime=excluded.mtime,
                mtime_readable=excluded.mtime_readable
        """, (dev, ino, path, category, size, mtime, mtime_readable))
        cur.close()
        return (dev, ino)

    def get_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM files WHERE path = ?", (path,))
        row = cur.fetchone()
        cur.close()
        return self.row_to_dict(row) if row else None

    def delete_by_path(self, path: str):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM files WHERE path = ?", (path,))
        cur.close()

    def get_by_devino(self, dev: int, ino: int, category: Optional[str] = None) -> Iterable[Dict[str, Any]]:
        cur = self.conn.cursor()
        if category:
            cur.execute("SELECT * FROM files WHERE dev=? AND ino=? AND category=?", (dev, ino, category))
        else:
            cur.execute("SELECT * FROM files WHERE dev=? AND ino=?", (dev, ino))
        rows = [self.row_to_dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    def replace_path_record(self, old_path: str, new_path: str, new_category: str):
        # 重命名/移动：删除旧记录，按新路径 stat 后写入
        self.delete_by_path(old_path)
        return self.upsert_from_stat(new_path, new_category)

    def clear_all(self):
        self.conn.execute("DELETE FROM files;")

    # 业务动作封装：
    def handle_create_or_modify(self, path: str, category: str):
        if not os.path.isfile(path):
            return
        self.upsert_from_stat(path, category)

    def handle_move(self, src_path: str, dst_path: str, dst_category: str):
        if os.path.isfile(dst_path):
            existing = self.get_by_path(src_path)
            if existing:
                self.replace_path_record(src_path, dst_path, dst_category)
            else:
                self.upsert_from_stat(dst_path, dst_category)

    def handle_delete(self, path: str):
        row = self.get_by_path(path)
        if not row:
            return
        dev, ino, category = row["dev"], row["ino"], row["category"]
        # 删除本条记录
        self.delete_by_path(path)

        # 若删除媒体文件，同步删除具有相同 inode 的源文件（硬链接）
        if category == "media":
            sources = list(self.get_by_devino(dev, ino, "source"))
            for s in sources:
                spath = s["path"]
                try:
                    if os.path.exists(spath) and os.path.isfile(spath):
                        # 在删除源文件前，先处理 qBittorrent 任务（如果启用）
                        if QB_ENABLED:
                            print(f"[QB] Processing qBittorrent task for file: {os.path.basename(spath)}")
                            try:
                                result = get_torrent_hash_from_file(spath)
                                if result[0]:  # 如果找到了对应的种子
                                    torrent_hash, file_index, torrent_deleted = result
                                    if torrent_deleted:
                                        print(f"[QB] Successfully removed torrent task: {torrent_hash[:8]}...")
                                    else:
                                        print(f"[QB] Set file priority to 0 for torrent: {torrent_hash[:8]}... (torrent kept - has other files)")
                                else:
                                    print(f"[QB] No matching torrent found for file: {os.path.basename(spath)}")
                            except Exception as qb_error:
                                print(f"[QB] Error processing qBittorrent task: {qb_error}")
                        
                        print(f"[DELETE] Removing source file: {os.path.basename(spath)}")
                        os.remove(spath)
                        print(f"[DELETE] Source file removed successfully")
                except Exception:
                    # 文件可能已不存在或权限问题，继续清理 DB
                    pass
                self.delete_by_path(spath)
