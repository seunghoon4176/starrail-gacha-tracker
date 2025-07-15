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

class GachaLinkFinder:
    """가챠 링크 검색을 담당하는 클래스"""
    
    @staticmethod
    def get_log_paths() -> List[str]:
        """가능한 로그 파일 경로들 반환"""
        return [
            os.path.expanduser("~/AppData/LocalLow/Cognosphere/Star Rail/Player.log"),
            os.path.expanduser("~/AppData/LocalLow/miHoYo/Star Rail/Player.log"),
            os.path.expanduser("~/AppData/LocalLow/HoYoverse/Star Rail/Player.log"),
            os.path.expanduser("~/AppData/LocalLow/Cognosphere/Star Rail/Player-prev.log"),
            os.path.expanduser("~/AppData/LocalLow/miHoYo/Star Rail/Player-prev.log"),
            os.path.expanduser("~/AppData/LocalLow/HoYoverse/Star Rail/Player-prev.log"),
        ]
    
    @staticmethod
    def extract_gacha_patterns(content: str) -> Optional[str]:
        """텍스트에서 가챠 링크 패턴 추출"""
        patterns = [
            r'https://[^\s"\'<>\[\]{}|\\^`]*getGachaLog[^\s"\'<>\[\]{}|\\^`]*',
            r'https://[^\s]*?public-operation-hkrpg[^\s]*?getGachaLog[^\s]*',
            r'https://[^\s]*?hkrpg-api[^\s]*?getGachaLog[^\s]*',
            r'https://[^\s]*?api-os-takumi[^\s]*?getGachaLog[^\s]*',
            r'https://[^\s]*?hoyoverse[^\s]*?getGachaLog[^\s]*',
            r'https://[^\s]*?mihoyo[^\s]*?getGachaLog[^\s]*'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                latest_link = matches[-1].strip('",\'()[]{}')
                if latest_link and 'getGachaLog' in latest_link:
                    return latest_link
        
        # 수동 검색
        lines = content.split('\n')
        for line in lines:
            if 'getGachaLog' in line and 'https://' in line:
                url_match = re.search(r'https://[^\s"\'<>\[\]{}|\\^`]*', line)
                if url_match:
                    url = url_match.group(0).strip('",\'()[]{}')
                    if url and 'getGachaLog' in url:
                        return url
        
        return None

def get_gacha_link_from_logs() -> Optional[str]:
    """게임 로그 파일에서 가챠 링크 추출"""
    finder = GachaLinkFinder()
    
    for log_path in finder.get_log_paths():
        if not os.path.exists(log_path):
            continue
            
        print(f"로그 파일 확인: {log_path}")
        file_size = os.path.getsize(log_path)
        print(f"파일 크기: {file_size:,} bytes")
        
        if file_size == 0:
            continue
        
        encodings = ['utf-8', 'utf-16', 'cp949', 'latin-1']
        
        for encoding in encodings:
            try:
                with open(log_path, 'r', encoding=encoding, errors='ignore') as f:
                    content = f.read()
                    
                if 'getGachaLog' not in content:
                    continue
                    
                print(f"✅ getGachaLog 발견 ({encoding})")
                link = finder.extract_gacha_patterns(content)
                if link:
                    print(f"✅ 링크 추출 성공: {link[:100]}...")
                    return link
                    
            except Exception as e:
                print(f"❌ {encoding} 인코딩 실패: {e}")
                continue
    
    print("❌ 로그에서 가챠 링크를 찾을 수 없습니다")
    return None

def get_gacha_link_from_registry() -> Optional[str]:
    """레지스트리에서 가챠 링크 추출"""
    registry_paths = [
        (winreg.HKEY_CURRENT_USER, r"Software\miHoYo\崩坏：星穹铁道"),
        (winreg.HKEY_CURRENT_USER, r"Software\miHoYo\Honkai: Star Rail"),
        (winreg.HKEY_CURRENT_USER, r"Software\Cognosphere\Star Rail"),
        (winreg.HKEY_CURRENT_USER, r"Software\HoYoverse\Star Rail"),
    ]
    
    for hkey, subkey in registry_paths:
        try:
            with winreg.OpenKey(hkey, subkey) as key:
                print(f"레지스트리 키 확인: {subkey}")
                
                i = 0
                while True:
                    try:
                        name, value, reg_type = winreg.EnumValue(key, i)
                        if isinstance(value, str) and 'getGachaLog' in value:
                            print(f"✅ 레지스트리 링크 발견: {value[:100]}...")
                            return value
                        i += 1
                    except WindowsError:
                        break
                        
        except (FileNotFoundError, PermissionError):
            continue
        except Exception as e:
            print(f"레지스트리 오류 {subkey}: {e}")
            continue
    
    print("❌ 레지스트리에서 링크를 찾을 수 없습니다")
    return None