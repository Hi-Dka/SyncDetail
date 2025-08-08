import requests
import json
import os
from datetime import datetime, timedelta
from urllib.parse import quote

LOGIN_URL = "http://localhost:3000/api/v1/login/access-token" 
USERNAME = "admin"
PASSWORD = "YanGxinXINx98Z5~"
TOKEN_FILE = os.path.expanduser("~/Media/access_token.json")  # 令牌保存文件
QUERY_BASE_URL = "http://localhost:3000/api/v1/history/transfer"
QUERY_DETAIL_URL = "http://localhost:3000/api/v1/history/transfer"  # 详情查询URL
DELETE_TRANSFER_URL = "http://localhost:3000/api/v1/history/transfer"  # 删除传输记录URL

def save_token(token, expires_in=3600):
    """保存令牌到文件"""
    token_data = {
        "access_token": token,
        "expires_at": (datetime.now() + timedelta(seconds=expires_in)).isoformat()
    }
    
    try:
        with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
            json.dump(token_data, f, indent=4)
        print(f"Token saved to {TOKEN_FILE}")
    except Exception as e:
        print(f"Failed to save token: {e}")

def load_token():
    """从文件加载令牌"""
    if not os.path.exists(TOKEN_FILE):
        return None
    
    try:
        with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
            token_data = json.load(f)
        
        # 检查令牌是否过期
        expires_at = datetime.fromisoformat(token_data['expires_at'])
        if datetime.now() >= expires_at:
            print("Token has expired")
            return None
        
        print("Found valid token")
        return token_data['access_token']
    
    except Exception as e:
        print(f"Failed to load token: {e}")
        return None

def get_new_token():
    """获取新的令牌"""
    payload = {
        "username": USERNAME,
        "password": PASSWORD
    }

    try:
        print("Getting new token...")
        response = requests.post(LOGIN_URL, data=payload)

        if response.status_code == 200:
            response_data = response.json()
            access_token = response_data.get("access_token")
            expires_in = response_data.get("expires_in", 3600)  # 默认1小时过期
            
            if access_token:
                print("Token obtained successfully!")
                # 保存令牌
                save_token(access_token, expires_in)
                return access_token
            else:
                print("Access token not found in response")
                return None

        elif response.status_code == 401:
            print("Login failed: incorrect username or password")
            return None
        else:
            print(f"Failed to get token, status code: {response.status_code}")
            print(f"Error message: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Request failed: unable to connect to server. Error: {e}")
        return None

def get_valid_token():
    """获取有效的令牌（优先使用保存的令牌）"""
    # 先尝试从文件加载令牌
    token = load_token()
    
    if token:
        return token
    
    # 如果没有有效令牌，获取新的令牌
    return get_new_token()

def test_token(token):
    if not token:
        return False
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get("http://home.hidka.com:3001/api/v1/user/admin", headers=headers)
    return response.status_code == 200

def query_transfer_history(title, page=1, count=50):
    """查询传输历史记录"""
    # 获取有效令牌
    token = get_valid_token()
    if not token:
        print("❌ Unable to get valid token")
        return None
    
    # 构建请求参数
    params = {
        'page': page,
        'title': title
    }
    if count:
        params['count'] = count
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        print(f"Querying: {title}")
        response = requests.get(QUERY_BASE_URL, headers=headers, params=params)
        
        # 如果令牌过期(401)，尝试获取新令牌并重试
        if response.status_code == 401:
            print("Token may have expired, getting new token...")
            new_token = get_new_token()
            if new_token:
                headers["Authorization"] = f"Bearer {new_token}"
                response = requests.get(QUERY_BASE_URL, headers=headers, params=params)
            else:
                print("❌ Unable to get new token")
                return None
        
        if response.status_code == 200:
            result = response.json()
            # 修复：使用正确的数据结构来获取记录数量
            data = result.get('data', {})
            list_items = data.get('list', [])
            total_count = data.get('total', 0)
            print(f"✅ Query successful, found {len(list_items)} records (total: {total_count})")
            return result
        else:
            print(f"❌ Query failed, status code: {response.status_code}")
            print(f"Error message: {response.text}")
            return None
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Query request failed: {e}")
        return None

def query_transfer_detail(transfer_id):
    """根据ID查询传输详情"""
    # 获取有效令牌
    token = get_valid_token()
    if not token:
        print("❌ Unable to get valid token")
        return None
    
    headers = {"Authorization": f"Bearer {token}"}
    detail_url = f"{QUERY_DETAIL_URL}/{transfer_id}"
    
    try:
        print(f"Querying transfer detail, ID: {transfer_id}")
        response = requests.get(detail_url, headers=headers)
        
        # 如果令牌过期(401)，尝试获取新令牌并重试
        if response.status_code == 401:
            print("Token may have expired, getting new token...")
            new_token = get_new_token()
            if new_token:
                headers["Authorization"] = f"Bearer {new_token}"
                response = requests.get(detail_url, headers=headers)
            else:
                print("❌ Unable to get new token")
                return None
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Query detail successful")
            return result
        else:
            print(f"❌ Query detail failed, status code: {response.status_code}")
            print(f"Error message: {response.text}")
            return None
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Query detail request failed: {e}")
        return None

def delete_transfer(transfer_id, deletesrc=False, deletedest=False):
    """根据ID删除传输记录"""
    # 获取有效令牌
    token = get_valid_token()
    if not token:
        print("❌ Unable to get valid token")
        return None
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 构建请求参数
    params = {
        'deletesrc': str(deletesrc).lower(),
        'deletedest': str(deletedest).lower()
    }
    
    # 构建请求体，只需要传递id
    data = {
        "id": transfer_id,
        "src": "",
        "dest": "",
        "mode": "",
        "type": "",
        "category": "",
        "title": "",
        "year": "",
        "tmdbid": 0,
        "imdbid": "",
        "tvdbid": 0,
        "doubanid": "",
        "seasons": "",
        "episodes": "",
        "image": "",
        "download_hash": "",
        "episode_group": "",
        "status": True,
        "errmsg": "",
        "date": ""
    }
    
    try:
        print(f"Deleting transfer record, ID: {transfer_id}")
        response = requests.delete(DELETE_TRANSFER_URL, headers=headers, params=params, json=data)
        
        # 如果令牌过期(401)，尝试获取新令牌并重试
        if response.status_code == 401:
            print("Token may have expired, getting new token...")
            new_token = get_new_token()
            if new_token:
                headers["Authorization"] = f"Bearer {new_token}"
                response = requests.delete(DELETE_TRANSFER_URL, headers=headers, params=params, json=data)
            else:
                print("❌ Unable to get new token")
                return None
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Delete successful")
            return result
        else:
            print(f"❌ Delete failed, status code: {response.status_code}")
            print(f"Error message: {response.text}")
            return None
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Delete request failed: {e}")
        return None

def extract_ids_from_query_result(query_result, title_filter=None):
    """从查询结果中提取所有ID，支持严格文件名匹配"""
    if not query_result or not query_result.get('success'):
        return []
    
    data = query_result.get('data', {})
    items = data.get('list', [])
    
    ids = []
    for item in items:
        if not item.get('id'):
            continue
            
        # 如果提供了title_filter，进行严格匹配
        if title_filter:
            dest_fileitem = item.get('dest_fileitem', {})
            file_name = dest_fileitem.get('name', '')
            
            # 严格匹配文件名
            if file_name == title_filter:
                ids.append(item.get('id'))
                print(f"✅ Found matching file: {file_name} (ID: {item.get('id')})")
            else:
                print(f"❌ Filename mismatch: {file_name}")
        else:
            # 如果没有提供过滤器，添加所有ID
            ids.append(item.get('id'))
    
    return ids

def cleanup_transfer_task(title, deletesrc=False, deletedest=False, page=1, count=50):
    """删除整理任务接口 - 包含完整的token验证和清理流程"""
    print(f"=== Starting cleanup task: {title} ===")
    
    # 第一步：获取并验证token
    print("Verifying access token...")
    access_token = get_valid_token()
    
    if not access_token:
        print("❌ Unable to get access token")
        return {"success": False, "message": "Unable to get access token", "deleted_count": 0}
    
    # 验证token是否有效
    if not test_token(access_token):
        print("❌ Token verification failed, trying to get new token...")
        access_token = get_new_token()
        if not access_token:
            print("❌ Unable to get new token")
            return {"success": False, "message": "Token verification failed and unable to get new token", "deleted_count": 0}
    
    print("✅ Token verification passed")
    
    # 第二步：查询传输记录
    result = query_transfer_history(title, page, count)
    
    if not result:
        print("❌ Query failed, cannot execute cleanup task")
        return {"success": False, "message": "Query failed", "deleted_count": 0}
    
    # 第三步：提取ID列表（使用严格匹配）
    ids = extract_ids_from_query_result(result, title)
    
    if not ids:
        print("✅ No strictly matching transfer records found, cleanup task finished")
        return {"success": True, "message": "No strictly matching records found", "deleted_count": 0, "deleted_ids": []}
    
    print(f"Found {len(ids)} strictly matching records: {ids}")
    
    # 第四步：批量删除
    deleted_ids = []
    failed_ids = []
    
    for transfer_id in ids:
        print(f"\nDeleting ID: {transfer_id}")
        delete_result = delete_transfer(transfer_id, deletesrc, deletedest)
        
        if delete_result and delete_result.get('success', False):
            deleted_ids.append(transfer_id)
            print(f"✅ ID {transfer_id} deleted successfully")
        else:
            failed_ids.append(transfer_id)
            print(f"❌ ID {transfer_id} delete failed")
    
    # 返回清理结果
    cleanup_result = {
        "success": len(failed_ids) == 0,
        "message": f"Successfully deleted {len(deleted_ids)} records" + (f", {len(failed_ids)} failed" if failed_ids else ""),
        "total_found": len(ids),
        "deleted_count": len(deleted_ids),
        "failed_count": len(failed_ids),
        "deleted_ids": deleted_ids,
        "failed_ids": failed_ids
    }
    
    print(f"\n=== Cleanup task completed ===")
    print(f"Total found: {cleanup_result['total_found']} records")
    print(f"Successfully deleted: {cleanup_result['deleted_count']} records") 
    print(f"Delete failed: {cleanup_result['failed_count']} records")
    
    return cleanup_result