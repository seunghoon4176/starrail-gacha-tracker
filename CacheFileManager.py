import customtkinter as ctk
from tkinter import messagebox
import asyncio
import threading
import aiohttp
import json
import os
import sys
import warnings
import subprocess
import re
import winreg
import tempfile
import shutil
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import urlparse, parse_qs
from collections import OrderedDict
import time
from GachaLinkFinder import GachaLinkFinder

class CacheFileManager:
    """게임 캐시 파일 관리 클래스"""
    
    @staticmethod
    def find_game_path() -> Optional[str]:
        """로그에서 게임 경로 찾기"""
        finder = GachaLinkFinder()
        
        for log_path in finder.get_log_paths():
            if not os.path.exists(log_path):
                continue
                
            try:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for i in range(11):  # 처음 11줄만 확인
                        line = f.readline()
                        if not line:
                            break
                            
                        line = line.strip()
                        if line.startswith("Loading player data from "):
                            game_path = line.replace("Loading player data from ", "").replace("data.unity3d", "").strip()
                            if game_path and os.path.exists(game_path):
                                print(f"✅ 게임 경로 발견: {game_path}")
                                return game_path
            except Exception as e:
                print(f"로그 읽기 실패 {log_path}: {e}")
                continue
        
        return None
    
    @staticmethod
    def find_cache_path(game_path: str) -> Optional[str]:
        """최신 캐시 경로 찾기"""
        cache_base = os.path.join(game_path, "webCaches")
        if not os.path.exists(cache_base):
            return None
        
        cache_path = os.path.join(cache_base, "Cache", "Cache_Data", "data_2")
        max_version = 0
        
        try:
            for folder_name in os.listdir(cache_base):
                folder_path = os.path.join(cache_base, folder_name)
                if not os.path.isdir(folder_path):
                    continue
                    
                if re.match(r'^\d+\.\d+\.\d+\.\d+$', folder_name):
                    try:
                        version_num = int(folder_name.replace('.', ''))
                        if version_num >= max_version:
                            max_version = version_num
                            cache_path = os.path.join(cache_base, folder_name, "Cache", "Cache_Data", "data_2")
                    except ValueError:
                        continue
        except Exception as e:
            print(f"버전 폴더 확인 실패: {e}")
        
        return cache_path if os.path.exists(cache_path) else None
    
    @staticmethod
    def copy_cache_file(cache_path: str) -> Optional[str]:
        """캐시 파일을 임시 위치에 복사"""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='_cache_copy') as temp_file:
                temp_path = temp_file.name
            
            # 직접 복사 시도
            try:
                shutil.copy2(cache_path, temp_path)
                return temp_path
            except Exception:
                pass
            
            # robocopy 시도
            try:
                cache_dir = os.path.dirname(cache_path)
                cache_filename = os.path.basename(cache_path)
                temp_dir = os.path.dirname(temp_path)
                
                result = subprocess.run([
                    'robocopy', cache_dir, temp_dir, cache_filename, 
                    '/COPY:DAT', '/R:1', '/W:1'
                ], capture_output=True, text=True, timeout=30)
                
                copied_file = os.path.join(temp_dir, cache_filename)
                if os.path.exists(copied_file):
                    shutil.move(copied_file, temp_path)
                    return temp_path
            except Exception:
                pass
            
            # PowerShell 시도
            try:
                ps_script = f'''
                try {{ Copy-Item -Path "{cache_path}" -Destination "{temp_path}" -Force }}
                catch {{ Write-Output "FAILED" }}
                '''
                
                result = subprocess.run([
                    'powershell', '-NoProfile', '-Command', ps_script
                ], capture_output=True, text=True, timeout=30)
                
                if "SUCCESS" in result.stdout and os.path.exists(temp_path):
                    return temp_path
            except Exception:
                pass
            
            # 모든 복사 방법 실패
            try:
                os.unlink(temp_path)
            except:
                pass
            return None
            
        except Exception as e:
            print(f"캐시 파일 복사 실패: {e}")
            return None

def get_gacha_link_from_game_cache() -> Optional[str]:
    """게임 웹캐시에서 가챠 링크 추출"""
    manager = CacheFileManager()
    
    # 게임 경로 찾기
    game_path = manager.find_game_path()
    if not game_path:
        print("❌ 게임 경로를 찾을 수 없습니다")
        return None
    
    # 캐시 경로 찾기
    cache_path = manager.find_cache_path(game_path)
    if not cache_path:
        print("❌ 캐시 파일을 찾을 수 없습니다")
        return None
    
    print(f"캐시 파일 분석: {cache_path}")
    
    # 캐시 파일 읽기
    cache_data = None
    temp_path = None
    
    try:
        with open(cache_path, 'rb') as f:
            cache_data = f.read()
    except PermissionError:
        print("❌ 권한 부족 - 임시 복사 시도")
        temp_path = manager.copy_cache_file(cache_path)
        if temp_path:
            try:
                with open(temp_path, 'rb') as f:
                    cache_data = f.read()
                print(f"✅ 복사본에서 읽기 성공: {len(cache_data):,} bytes")
            except Exception as e:
                print(f"❌ 복사본 읽기 실패: {e}")
        else:
            print("❌ 모든 복사 방법 실패")
            return None
    except Exception as e:
        print(f"❌ 캐시 파일 읽기 실패: {e}")
        return None
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass
    
    if not cache_data:
        return None
    
    # 캐시 데이터 분석
    try:
        cache_text = cache_data.decode('utf-8', errors='ignore')
        cache_parts = cache_text.split('1/0/')
        
        # 역순으로 검색 (최신 데이터부터)
        for part in reversed(cache_parts):
            if part and part.startswith('http') and ('getGachaLog' in part or 'getLdGachaLog' in part):
                url = part.split('\0')[0]
                if url and len(url.strip()) > 0:
                    print(f"✅ 캐시에서 URL 발견: {url[:100]}...")
                    return url
        
        print("❌ 캐시에서 가챠 URL을 찾을 수 없습니다")
        return None
        
    except Exception as e:
        print(f"❌ 캐시 분석 실패: {e}")
        return None