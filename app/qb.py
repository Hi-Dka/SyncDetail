import requests
import json
import os
from config import QB_URL, QB_USER, QB_PASS, QB_SIMILARITY_THRESHOLD, QB_EXCLUDE_CATEGORIES

def get_filename_from_path(path):
    return os.path.basename(path)

def calculate_similarity(str1, str2):
    """简单的字符串相似度计算"""
    str1_lower = str1.lower()
    str2_lower = str2.lower()
    
    # 如果完全匹配，返回100%
    if str1_lower == str2_lower:
        return 100
    
    # 如果一个字符串包含另一个，返回较高的相似度
    if str1_lower in str2_lower or str2_lower in str1_lower:
        return 80
    
    # 简单的单词匹配检查
    words1 = set(str1_lower.split())
    words2 = set(str2_lower.split())
    
    if not words1 or not words2:
        return 0
    
    common_words = words1.intersection(words2)
    total_words = words1.union(words2)
    
    return int((len(common_words) / len(total_words)) * 100)

def set_file_priority(session, torrent_hash, file_index, priority=0):
    """设置指定文件的优先级"""
    data = {
        "hash": torrent_hash,
        "id": str(file_index),
        "priority": str(priority)
    }
    
    response = session.post(f"{QB_URL}/api/v2/torrents/filePrio", data=data)
    return response.status_code == 200

def check_all_files_priority_zero(session, torrent_hash):
    """检查种子中所有文件的优先级是否都为0"""
    files_res = session.get(f"{QB_URL}/api/v2/torrents/files", params={"hash": torrent_hash})
    files_list = files_res.json()
    
    for file_info in files_list:
        if file_info.get('priority', 1) != 0:  # 如果有任何文件优先级不为0
            return False
    
    return True

def delete_torrent(session, torrent_hash, delete_files=False):
    """删除种子任务"""
    data = {
        "hashes": torrent_hash,
        "deleteFiles": str(delete_files).lower()  # 是否删除文件
    }
    
    response = session.post(f"{QB_URL}/api/v2/torrents/delete", data=data)
    return response.status_code == 200

def logout_session(session):
    """退出登录会话"""
    try:
        response = session.post(f"{QB_URL}/api/v2/auth/logout")
        if response.status_code == 200:
            print("Successfully logged out from qBittorrent")
            return True
        else:
            print("Failed to logout")
            return False
    except Exception as e:
        print(f"Error occurred during logout: {e}")
        return False

# ===== 获取 torrent hash =====
def get_torrent_hash_from_file(file_path, similarity_threshold=None):
    # 如果没有传入相似度阈值，使用配置文件中的默认值
    if similarity_threshold is None:
        similarity_threshold = QB_SIMILARITY_THRESHOLD
        
    session = requests.Session()

    try:
        # 登录
        login_data = {
            "username": QB_USER,
            "password": QB_PASS
        }
        r = session.post(f"{QB_URL}/api/v2/auth/login", data=login_data)
        if r.text != "Ok.":
            raise Exception("Failed to login to qBittorrent, please check username and password")

        target_filename = get_filename_from_path(file_path)

        # 获取所有任务
        torrents = session.get(f"{QB_URL}/api/v2/torrents/info").json()
        
        # 过滤掉指定分类的种子
        filtered_torrents = []
        for torrent in torrents:
            category = torrent.get('category', '')
            if category not in QB_EXCLUDE_CATEGORIES:
                filtered_torrents.append(torrent)
            else:
                print(f"Skipping {category} torrent: {torrent.get('name', 'Unknown')}")
        
        # 获取过滤后的hash列表
        all_hashes = [torrent['hash'] for torrent in filtered_torrents]
        print(f"Found {len(all_hashes)} non-excluded torrent hashes (excluded {len(torrents) - len(filtered_torrents)} torrents)")

        # 遍历每个hash，获取对应的文件列表
        for torrent_hash in all_hashes:
            print(f"Checking hash: {torrent_hash}")
            
            # 获取该hash对应的文件列表
            files_res = session.get(f"{QB_URL}/api/v2/torrents/files", params={"hash": torrent_hash})
            files_list = files_res.json()

            # 检查文件列表中是否有匹配的文件
            for file_index, file_info in enumerate(files_list):
                file_name = get_filename_from_path(file_info['name'])
                
                # 使用自定义的相似度计算检查文件名相似度
                similarity = calculate_similarity(target_filename, file_name)
                if similarity >= similarity_threshold:
                    print(f"Found matching file: {file_info['name']} (similarity: {similarity}%)")
                    print(f"File index: {file_index}")
                    
                    # 设置文件优先级为0（不下载）
                    if set_file_priority(session, torrent_hash, file_index, priority=0):
                        print("Successfully set file priority to 0 (do not download)")
                        
                        # 检查该种子中所有文件的优先级是否都为0
                        print("Checking priority of all files in torrent...")
                        if check_all_files_priority_zero(session, torrent_hash):
                            print("All files have priority 0, preparing to delete torrent...")
                            if delete_torrent(session, torrent_hash, delete_files=False):
                                print("Torrent successfully deleted")
                                logout_session(session)
                                return torrent_hash, file_index, True  # True表示已删除种子
                            else:
                                print("Failed to delete torrent")
                                logout_session(session)
                                return torrent_hash, file_index, False
                        else:
                            print("Other files in torrent still need downloading, keeping torrent")
                            logout_session(session)
                            return torrent_hash, file_index, False
                    else:
                        print("Failed to set file priority")
                        logout_session(session)
                        return torrent_hash, file_index, False

        # 没有找到匹配文件
        logout_session(session)
        return None, None, False
        
    except Exception as e:
        print(f"Error occurred during operation: {e}")
        logout_session(session)
        raise
