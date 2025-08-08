import os
from typing import Callable, Iterable
from db import Database  # 修改为绝对导入

def default_should_include(path: str) -> bool:
    # 仅索引常规文件
    return os.path.isfile(path)

def full_refresh(db: Database, roots_source: Iterable[str], roots_media: Iterable[str], categorize: Callable[[str], str]):
    print("[SCAN] Starting database refresh...")
    with db.tx():
        db.clear_all()
        print("[SCAN] Database cleared")
        
        roots = list(set(list(roots_source) + list(roots_media)))
        file_count = 0
        
        for root in roots:
            print(f"[SCAN] Scanning directory: {root}")
            if not os.path.exists(root):
                print(f"[SCAN] Directory does not exist, skipping: {root}")
                continue
                
            for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
                # 可按需过滤目录/文件
                for name in filenames:
                    fpath = os.path.join(dirpath, name)
                    if not default_should_include(fpath):
                        continue
                    cat = categorize(fpath)
                    if not cat:
                        continue
                    try:
                        db.handle_create_or_modify(fpath, cat)
                        file_count += 1
                        if file_count % 100 == 0:  # 每100个文件输出一次进度
                            print(f"[SCAN] Processed {file_count} files...")
                    except FileNotFoundError:
                        # 扫描过程中可能被删除，忽略
                        pass
                    except Exception as e:
                        print(f"[SCAN] Error processing {fpath}: {e}")
        
        print(f"[SCAN] Completed. Total files processed: {file_count}")
