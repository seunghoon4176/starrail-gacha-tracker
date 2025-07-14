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
import time

# Pydantic V2 호환성 경고 숨기기
warnings.filterwarnings("ignore", message="Valid config keys have changed in V2")
warnings.filterwarnings("ignore", message=".*underscore_attrs_are_private.*", category=UserWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic._internal._config")

# PyInstaller 리소스 경로 처리
def resource_path(relative_path):
    """PyInstaller 환경에서 리소스 파일 경로를 정확히 찾기"""
    try:
        # PyInstaller가 생성한 임시 폴더
        base_path = sys._MEIPASS
    except Exception:
        # 개발 환경에서는 현재 디렉터리
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

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

class ErrorHandler:
    """에러 처리 및 메시지 관리"""
    
    @staticmethod
    def get_detailed_error_message(error_msg: str) -> str:
        """에러 메시지에 따른 상세 안내"""
        if "Check if the link is correct" in error_msg or "가챠 링크 없음" in error_msg:
            return """❌ 가챠 링크를 찾을 수 없습니다!

🔧 해결 방법:
1. Honkai: Star Rail 게임을 실행하세요
2. 게임 내 워프(가챠) → 기록 메뉴로 이동
3. 각 배너의 기록을 한 번씩 확인하세요
4. 게임을 종료하지 말고 다시 시도하세요

💡 추가 해결책:
• 게임을 관리자 권한으로 실행
• 프로그램을 관리자 권한으로 실행
• 게임 재시작 후 가챠 기록 재확인"""

        elif "'NoneType' object has no attribute 'get'" in error_msg:
            return """❌ API 응답 오류!

🔧 해결 방법:
1. 게임을 완전히 재시작하세요
2. 워프 기록을 새로 열어보세요
3. 몇 분 기다린 후 다시 시도하세요
4. 인터넷 연결을 확인하세요"""

        elif "-111" in error_msg or "game name error" in error_msg.lower():
            return """❌ 가챠 링크 파라미터 오류!

🔧 해결 방법:
1. 게임을 완전히 재시작하세요
2. 워프 기록을 다시 확인하세요
3. 브라우저 캐시를 삭제하세요
4. 몇 분 기다린 후 다시 시도하세요"""

        elif "-101" in error_msg or "authkey" in error_msg.lower():
            return """❌ 인증 키 만료!

🔧 해결 방법:
1. 게임을 재시작하세요
2. 가챠 기록을 새로 열어보세요
3. 잠시 기다린 후 다시 시도하세요"""

        elif "timeout" in error_msg.lower():
            return """❌ 연결 시간 초과!

🔧 해결 방법:
1. 인터넷 연결을 확인하세요
2. VPN을 끄고 시도하세요
3. 잠시 후 다시 시도하세요"""

        else:
            return f"""❌ 오류 발생!

🔧 문제: {error_msg}

💡 해결 방법:
1. 게임을 재시작하세요
2. 인터넷 연결을 확인하세요
3. 잠시 후 다시 시도하세요"""

# CustomTkinter 테마 설정 (초기값만, 실제 설정은 load_settings에서)
ctk.set_default_color_theme("blue")  # "blue", "green", "dark-blue"


class GachaAPI:
    """가챠 API 직접 호출 클래스 - 실제 API 구조에 맞게 수정"""
    
    # GitHub 코드의 엔드포인트 상수들 참고
    END_DEFAULT = "getGachaLog"
    END_COLLABORATION = "getLdGachaLog"
    
    # 실제로는 콜라보 배너가 특별한 엔드포인트를 사용하지 않을 수도 있음
    COLLABORATION_TYPES = {"12"}  # 실제 콜라보 배너 타입으로 수정
    
    def __init__(self, gacha_url: str):
        self.gacha_url = gacha_url
        self.parsed_url = urlparse(gacha_url)
        self.base_url = f"{self.parsed_url.scheme}://{self.parsed_url.netloc}{self.parsed_url.path}"
        self.params = parse_qs(self.parsed_url.query)
        
        # 파라미터를 딕셔너리로 변환
        self.base_params = {}
        for key, value in self.params.items():
            self.base_params[key] = value[0] if isinstance(value, list) and len(value) > 0 else value
    
    def _build_url_for_gacha_type(self, gacha_type: str) -> str:
        """가챠 타입에 따라 URL 엔드포인트 결정 - 실제로는 대부분 getGachaLog 사용"""
        # 대부분의 배너는 기본 엔드포인트 사용
        # 특별한 경우에만 getLdGachaLog 사용 (실제 확인 필요)
        if gacha_type in self.COLLABORATION_TYPES:
            return self.base_url.replace(self.END_DEFAULT, self.END_COLLABORATION)
        else:
            return self.base_url.replace(self.END_COLLABORATION, self.END_DEFAULT)
    
    async def fetch_gacha_records(self, gacha_type: str, lang: str = "kr") -> List[Dict[str, Any]]:
        """특정 배너의 가챠 기록을 모두 가져오기 - GitHub 구조 참고"""
        all_records = []
        page = 1
        end_id = "0"
        
        # 가챠 타입에 맞는 URL 선택
        request_url = self._build_url_for_gacha_type(gacha_type)
        
        async with aiohttp.ClientSession() as session:
            while True:
                params = self.base_params.copy()
                params.update({
                    "gacha_type": gacha_type,
                    "page": str(page),
                    "size": "20",
                    "end_id": end_id,
                    "lang": lang
                })
                
                try:
                    async with session.get(request_url, params=params, timeout=30) as response:
                        if response.status != 200:
                            print(f"HTTP 오류: {response.status}")
                            break
                            
                        data = await response.json()
                        
                        if data.get("retcode") != 0:
                            print(f"API 오류: {data.get('message', 'Unknown error')}")
                            break
                        
                        records = data.get("data", {}).get("list", [])
                        if not records:
                            break
                        
                        all_records.extend(records)
                        
                        # 다음 페이지 준비
                        end_id = records[-1].get("id", "0")
                        page += 1
                        
                        print(f"배너 {gacha_type} - 페이지 {page-1}: {len(records)}개 기록")
                        
                        # API 호출 간격 (과부하 방지)
                        await asyncio.sleep(0.5)
                        
                except asyncio.TimeoutError:
                    print(f"타임아웃 발생 - 페이지 {page}")
                    break
                except Exception as e:
                    print(f"요청 오류 - 페이지 {page}: {e}")
                    break
        
        return all_records
    
    async def validate_link(self) -> bool:
        """가챠 링크 유효성 검증"""
        try:
            async with aiohttp.ClientSession() as session:
                # 일반 배너로 테스트
                test_url = self._build_url_for_gacha_type("1")
                params = self.base_params.copy()
                params.update({
                    "gacha_type": "1",
                    "page": "1",
                    "size": "5",
                    "end_id": "0",
                    "lang": "kr"
                })
                
                async with session.get(test_url, params=params, timeout=10) as response:
                    if response.status != 200:
                        return False
                    
                    data = await response.json()
                    return data.get("retcode") == 0
                    
        except Exception as e:
            print(f"링크 검증 실패: {e}")
            return False

class ModernGachaViewer:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("로컬 워프 트래커")
        self.root.geometry("800x800")
        self.root.resizable(False, False)
        
        # 윈도우 아이콘 설정
        try:
            icon_paths = [
                resource_path("images/anaxa.ico"),
                resource_path("anaxa.ico"),
                "images/anaxa.ico",
                "anaxa.ico"
            ]
            
            for icon_path in icon_paths:
                if os.path.exists(icon_path):
                    self.root.iconbitmap(icon_path)
                    break
        except Exception as e:
            print(f"아이콘 로드 실패: {e}")
        
        # 데이터 저장용 - 콜라보 워프 광추 배너 추가
        # 실제 스타레일 API 배너 타입에 맞게 수정
        self.banner_data = {
            "1": {"name": "이벤트 배너", "data": [], "stats": {}},      # 캐릭터 이벤트
            "2": {"name": "광추 배너", "data": [], "stats": {}},        # 무기 배너
            "3": {"name": "상시 배너", "data": [], "stats": {}},        # 상시 배너
            "11": {"name": "초보 배너", "data": [], "stats": {}},       # 초보자 배너 (50뽑 할인)
            "12": {"name": "콜라보 워프", "data": [], "stats": {}}      # 콜라보 이벤트 (있다면)
        }
        
        # 에러 핸들러 추가
        self.error_handler = ErrorHandler()

        self.setup_ui()
        
    def setup_ui(self):
        # 메인 컨테이너
        self.main_container = ctk.CTkFrame(self.root)
        self.main_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 간단한 컨트롤 패널
        self.create_simple_control_panel()
        
        # 진행 상태
        self.create_progress_section()
        
        # 탭뷰
        self.create_tabview()
        
        # 설정 창 초기화
        self.settings_window = None
        
        # 기본 설정 변수들 (구문 오류 수정)
        self.link_method = ctk.StringVar(value="auto")  # 자동으로 기본 설정
        self.theme_var = ctk.StringVar(value="dark")  # 테마 변수 추가
        self.current_theme = "dark"  # 현재 테마 추적
        
        # 데이터 파일 초기화
        self.data_file = "gacha_records.json"
        
        # 설정 로드
        self.load_settings()
        
        self.load_existing_data()
        
        # 초기 링크 상태 확인
        self.update_link_status()
        
    def create_simple_control_panel(self):
        """간단한 컨트롤 패널 생성"""
        control_frame = ctk.CTkFrame(self.main_container)
        control_frame.pack(fill="x", padx=10, pady=(10, 20))
        
        # 상단 컨트롤 (조회 버튼과 설정 버튼만)
        top_control = ctk.CTkFrame(control_frame)
        top_control.pack(fill="x", padx=15, pady=15)
        
        # 조회 버튼을 왼쪽에 배치
        self.fetch_all_btn = ctk.CTkButton(
            top_control,
            text="🎯 모든 배너 조회",
            command=self.fetch_all_banners,
            width=180,
            height=40,
            font=ctk.CTkFont(size=16, weight="bold"),
            state="normal"
        )
        self.fetch_all_btn.pack(side="left", padx=(0, 20))
        
        # 설정 버튼을 오른쪽에 배치
        settings_btn = ctk.CTkButton(
            top_control,
            text="⚙️ 설정",
            command=self.open_settings,
            width=100,
            height=35,
            fg_color="gray50",
            hover_color="gray40"
        )
        settings_btn.pack(side="right", padx=(0, 0))
        


    def create_progress_section(self):
        """진행 상태 섹션 생성 (컴팩트하게)"""
        progress_frame = ctk.CTkFrame(self.main_container)
        progress_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        # 프로그레스 바와 상태를 한 줄에
        progress_container = ctk.CTkFrame(progress_frame)
        progress_container.pack(fill="x", padx=15, pady=10)
        
        self.progress_bar = ctk.CTkProgressBar(progress_container, height=16)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 15))
        self.progress_bar.set(0)
        
        self.status_label = ctk.CTkLabel(
            progress_container,
            text="📝 대기 중...",
            font=ctk.CTkFont(size=12),
            width=200
        )
        self.status_label.pack(side="right")
        
    def create_tabview(self):
        """탭뷰 생성"""
        self.tabview = ctk.CTkTabview(self.main_container)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # 배너별 탭 생성
        self.banner_tabs = {}
        for banner_id, banner_info in self.banner_data.items():
            self.create_banner_tab(banner_id, banner_info["name"])
        
        # 통합 통계 탭
        self.create_summary_tab()
        
    def create_banner_tab(self, banner_id, banner_name):
        """배너별 탭 생성"""
        tab = self.tabview.add(banner_name)
        
        # 통계 프레임 (더 작게)
        stats_frame = ctk.CTkFrame(tab)
        stats_frame.pack(fill="x", padx=10, pady=10)
        
        stats_label = ctk.CTkLabel(
            stats_frame,
            text="📊 통계",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        stats_label.pack(anchor="w", padx=15, pady=(15, 5))
        
        stats_text = ctk.CTkTextbox(stats_frame, height=120)
        stats_text.pack(fill="x", padx=15, pady=(0, 15))
        stats_text.configure(state="disabled")  # 사용자 입력 방지
        
        # 기록 프레임 (훨씬 더 크게)
        records_frame = ctk.CTkFrame(tab)
        records_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        records_label = ctk.CTkLabel(
            records_frame,
            text="📜 가챠 기록",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        records_label.pack(anchor="w", padx=15, pady=(15, 5))
        
        # 기록 텍스트박스를 훨씬 더 크게
        records_text = ctk.CTkTextbox(
            records_frame, 
            height=450,
            font=ctk.CTkFont(size=13)
        )
        records_text.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        records_text.configure(state="disabled")  # 사용자 입력 방지
        
        # 탭 정보 저장
        self.banner_tabs[banner_id] = {
            "tab": tab,
            "stats_text": stats_text,
            "records_text": records_text
        }
        
    def create_summary_tab(self):
        """통합 통계 탭 생성"""
        summary_tab = self.tabview.add("📈 통합 통계")
        
        summary_label = ctk.CTkLabel(
            summary_tab,
            text="📊 전체 가챠 통계",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        summary_label.pack(pady=(15, 10))
        
        self.summary_text = ctk.CTkTextbox(summary_tab, height=500)
        self.summary_text.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        self.summary_text.configure(state="disabled")  # 사용자 입력 방지
        
    def toggle_theme(self):
        """테마 토글"""
        if self.theme_switch.get() == "dark":
            ctk.set_appearance_mode("dark")
        else:
            ctk.set_appearance_mode("light")
            
    def show_help(self):
        """도움말 표시"""
        help_text = """
🔍 가챠 기록 조회 방법:

🤖 자동 링크 감지:
   이 프로그램은 게임 로그 파일에서 자동으로 가챠 링크를 찾습니다!

🎮 게임 준비:
   1. Honkai: Star Rail 게임을 실행하세요
   2. 게임 내에서 워프(가챠) 메뉴로 이동
   3. 기록 탭을 클릭하세요

📊 기록 확인:
   4. 이벤트 배너의 기록을 한 번 확인하세요
   5. 광추 배너의 기록을 한 번 확인하세요  
   6. 상시 배너의 기록을 한 번 확인하세요

🚀 조회 실행:
   7. "모든 배너 조회" 버튼을 클릭하세요
   (게임을 종료할 필요 없습니다!)

⚠️ 문제 해결:
   • 자동 감지 실패 시: 게임 재시작 후 가챠 기록 재확인
   • 브라우저 캐시 삭제 후 다시 시도
   • 글로벌 서버만 지원됩니다
   • 최근 3개월 기록만 조회 가능합니다
        """
        
        help_window = ctk.CTkToplevel(self.root)
        help_window.title("사용 방법")
        help_window.geometry("500x450")
        
        # 도움말 창에도 아이콘 적용
        try:
            icon_paths = [
                resource_path("images/anaxa.ico"),
                resource_path("anaxa.ico"),
                "images/anaxa.ico",
                "anaxa.ico"
            ]
            
            for icon_path in icon_paths:
                if os.path.exists(icon_path):
                    help_window.iconbitmap(icon_path)
                    break
        except Exception as e:
            print(f"도움말 창 아이콘 로드 실패: {e}")
        
        help_label = ctk.CTkTextbox(help_window)
        help_label.pack(fill="both", expand=True, padx=20, pady=20)
        help_label.insert("0.0", help_text)
        help_label.configure(state="disabled")
    
    def update_progress(self, value, status):
        """진행률 업데이트"""
        self.progress_bar.set(value)
        self.status_label.configure(text=status)
        self.root.update_idletasks()
    
    def fetch_all_banners(self):
        """모든 배너 조회"""
        def run_fetch():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._fetch_all_banners_async())
            loop.close()
        
        thread = threading.Thread(target=run_fetch, daemon=True)
        thread.start()
    
    async def _fetch_all_banners_async(self):
        """비동기 모든 배너 조회 - 개선된 버전"""
        try:
            self.update_progress(0, "🔄 연결 준비 중...")
            api_lang = "kr"
            
            # 가챠 링크 검색
            gacha_link = await self._find_gacha_link()
            if not gacha_link:
                error_msg = self.error_handler.get_detailed_error_message("가챠 링크 없음")
                self.update_progress(0, error_msg)
                messagebox.showerror("가챠 링크 오류", error_msg)
                return
            
            # 링크 검증
            try:
                await self._validate_gacha_link(gacha_link, api_lang)
                self.update_progress(0.15, "✅ 가챠 링크 확인 완료")
            except Exception as e:
                error_msg = self.error_handler.get_detailed_error_message(str(e))
                self.update_progress(0, error_msg)
                messagebox.showerror("가챠 링크 오류", error_msg)
                return
            
            # 배너별 조회
            await self._fetch_banners_data(gacha_link, api_lang)
            
            # 완료 처리
            self.save_data_to_file()
            self._update_summary_display()
            self.update_progress(1, "✅ 모든 배너 조회 완료!")
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ 전체 조회 실패: {error_msg}")
            detailed_error = self.error_handler.get_detailed_error_message(error_msg)
            self.update_progress(0, detailed_error)
            messagebox.showerror("오류", detailed_error)
    
    async def _find_gacha_link(self) -> Optional[str]:
        """가챠 링크 검색"""
        # 1. PowerShell 스크립트 검색 (우선순위 최고)
        self.update_progress(0.03, "🔍 PowerShell 스크립트 검색 중...")
        link = get_gacha_link_from_powershell_script()
        if link:
            return link
        
        # 2. 레지스트리 검색
        self.update_progress(0.05, "🔍 레지스트리 검색 중...")
        link = get_gacha_link_from_registry()
        if link:
            return link
        
        # 3. 로그 파일 검색
        self.update_progress(0.07, "🔍 게임 로그 검색 중...")
        link = get_gacha_link_from_logs()
        if link:
            return link
        
        # 4. 게임 캐시 검색
        self.update_progress(0.08, "🔍 게임 캐시 검색 중...")
        link = get_gacha_link_from_game_cache()
        if link:
            return link
        
        return None
    
    async def _validate_gacha_link(self, gacha_link: str, api_lang: str):
        """가챠 링크 검증"""
        print(f"링크 검증 시작: {gacha_link[:80]}...")
        
        api = GachaAPI(gacha_link)
        is_valid = await api.validate_link()
        
        if not is_valid:
            raise Exception("가챠 기록을 찾을 수 없습니다 - 게임에서 가챠 기록을 먼저 확인하세요")
        
        print(f"✅ 검증 성공")
    
    async def _fetch_banners_data(self, gacha_link: str, api_lang: str):
        """배너별 데이터 조회 - 실제 API 배너 타입 사용"""
        # 기본 배너들만 먼저 조회 (1, 2, 3, 11)
        banner_ids = ["1", "2", "3", "11"]
        
        # 콜라보 배너 확인을 위해 12도 시도
        test_banner_ids = ["12"]
        
        for i, banner_id in enumerate(banner_ids):
            banner_name = self.banner_data[banner_id]["name"]
            self.update_progress(0.2 + (i * 0.18), f"📊 {banner_name} 조회 중...")
            
            try:
                new_data = await self._fetch_banner_data(gacha_link, banner_id, api_lang)
                new_items_added = self.merge_new_data(banner_id, new_data)
                
                self._calculate_banner_stats(banner_id)
                self._update_banner_display(banner_id)
                
                total_items = len(self.banner_data[banner_id]["data"])
                self.update_progress(0.2 + (i * 0.18) + 0.04, 
                    f"📊 {banner_name}: {total_items}개 기록 (+{new_items_added}개 신규)")
                    
            except Exception as e:
                print(f"❌ {banner_name} 조회 실패: {e}")
                continue
        
        # 콜라보 배너 테스트 (있으면 조회, 없으면 무시)
        for banner_id in test_banner_ids:
            if banner_id in self.banner_data:
                try:
                    banner_name = self.banner_data[banner_id]["name"]
                    print(f"🔍 {banner_name} 존재 여부 확인 중...")
                    
                    new_data = await self._fetch_banner_data(gacha_link, banner_id, api_lang)
                    if new_data:  # 데이터가 있으면 처리
                        new_items_added = self.merge_new_data(banner_id, new_data)
                        self._calculate_banner_stats(banner_id)
                        self._update_banner_display(banner_id)
                        print(f"✅ {banner_name}: {len(new_data)}개 기록 발견")
                    else:
                        print(f"ℹ️ {banner_name}: 기록 없음")
                        
                except Exception as e:
                    print(f"ℹ️ {banner_name} 배너는 현재 존재하지 않습니다")
                    continue
    
    async def _fetch_banner_data(self, gacha_link: str, banner_id: str, api_lang: str) -> List[Any]:
        """개별 배너 데이터 조회 - 실제 API 배너 타입 매핑"""
        api = GachaAPI(gacha_link)
        
        # 실제 스타레일 API 배너 타입 매핑
        banner_type_map = {
            "1": "1",   # 이벤트 배너 (캐릭터)
            "2": "2",   # 광추 배너 (무기)
            "3": "3",   # 상시 배너
            "11": "11", # 초보자 배너
            "12": "12"  # 콜라보 배너 (있다면)
        }
        
        gacha_type = banner_type_map.get(banner_id, banner_id)
        records = await api.fetch_gacha_records(gacha_type, api_lang)
        
        # 레코드를 객체로 변환
        converted_records = []
        for record in records:
            item_obj = type('GachaItem', (), {})()
            item_obj.id = record.get("id", "")
            item_obj.name = record.get("name", "")
            item_obj.rank = int(record.get("rank_type", "3"))
            item_obj.time = record.get("time", "")
            item_obj.type = record.get("item_type", "")
            item_obj.gacha_type = record.get("gacha_type", "")
            item_obj.uid = record.get("uid", "")
            converted_records.append(item_obj)
        
        return converted_records

    def _calculate_banner_stats(self, banner_id):
        """배너 통계 계산"""
        data = self.banner_data[banner_id]["data"]
        if not data:
            self.banner_data[banner_id]["stats"] = {}
            return
        
        stats = {
            "total": len(data),
            "5star": 0,
            "4star": 0,
            "3star": 0,
            "5star_items": [],
            "4star_items": [],
            "pity_count": 0,
            "5star_intervals": []
        }
        
        last_5star_index = -1
        
        for i, item in enumerate(data):
            if not item:
                continue
                
            rank = getattr(item, 'rank', 3)
            try:
                rank_str = str(rank)
            except:
                rank_str = "3"
                
            if rank_str == "5":
                stats["5star"] += 1
                item_name = getattr(item, 'name', 'Unknown')
                item_time = str(getattr(item, 'time', ''))
                stats["5star_items"].append((item_name, item_time, i+1))
                
                if last_5star_index != -1:
                    interval = i - last_5star_index
                    stats["5star_intervals"].append(interval)
                
                last_5star_index = i
                stats["pity_count"] = 0
            elif rank_str == "4":
                stats["4star"] += 1
                item_name = getattr(item, 'name', 'Unknown')
                item_time = str(getattr(item, 'time', ''))
                stats["4star_items"].append((item_name, item_time))
                stats["pity_count"] += 1
            else:
                stats["3star"] += 1
                stats["pity_count"] += 1
        
        self.banner_data[banner_id]["stats"] = stats
    
    def _update_banner_display(self, banner_id):
        """배너 화면 업데이트"""
        tab_info = self.banner_tabs[banner_id]
        data = self.banner_data[banner_id]["data"]
        stats = self.banner_data[banner_id]["stats"]
        
        # 통계 업데이트
        if stats:
            avg_interval = sum(stats["5star_intervals"]) / len(stats["5star_intervals"]) if stats["5star_intervals"] else 0
            
            stats_text = f"""📊 {self.banner_data[banner_id]["name"]} 통계

🎯 총 가챠 횟수: {stats['total']}회
⭐ 5성: {stats['5star']}개 ({stats['5star']/stats['total']*100:.1f}%)
🌟 4성: {stats['4star']}개 ({stats['4star']/stats['total']*100:.1f}%)
✨ 3성: {stats['3star']}개 ({stats['3star']/stats['total']*100:.1f}%)

🔥 현재 천장까지: {stats['pity_count']}회
💎 평균 5성 간격: {avg_interval:.1f}회"""

            if stats["5star_intervals"]:
                min_interval = min(stats["5star_intervals"])
                max_interval = max(stats["5star_intervals"])
                stats_text += f"\n📈 최단/최장 간격: {min_interval}회 / {max_interval}회"
        else:
            stats_text = "데이터가 없습니다."
        
        tab_info["stats_text"].configure(state="normal")
        tab_info["stats_text"].delete("0.0", "end")
        tab_info["stats_text"].insert("0.0", stats_text)
        tab_info["stats_text"].configure(state="disabled")
        
        # 기록 업데이트
        if data:
            records_text = "📜 가챠 기록 (최신순)\n\n"
            
            five_star_positions = []
            for i, item in enumerate(data):
                if item:
                    item_rank = getattr(item, 'rank', 3)
                    if str(item_rank) == "5":
                        five_star_positions.append(i)
            
            for i, item in enumerate(data[:10]):
                if not item:
                    continue
                    
                item_rank = getattr(item, 'rank', 3)
                item_name = getattr(item, 'name', 'Unknown')
                item_time = getattr(item, 'time', '')
                
                try:
                    star_icon = "⭐" * int(item_rank) if isinstance(item_rank, (int, str)) else "⭐"
                except:
                    star_icon = "⭐"
                
                interval_info = ""
                if str(item_rank) == "5" and i in five_star_positions:
                    try:
                        pos_in_5star = five_star_positions.index(i)
                        if pos_in_5star > 0:
                            prev_5star_pos = five_star_positions[pos_in_5star - 1]
                            interval = i - prev_5star_pos
                            interval_info = f" [+{interval}회]"
                    except:
                        interval_info = ""
                
                if str(item_rank) == "5":
                    prefix = "🌟"
                elif str(item_rank) == "4":
                    prefix = "💜"
                else:
                    prefix = "🔹"
                
                records_text += f"{i+1:3d}. {prefix} {star_icon} {item_name}{interval_info}\n     📅 {item_time}\n\n"
            
            if len(data) > 10:
                records_text += f"... 및 {len(data)-10}개 기록 더"
        else:
            records_text = "기록이 없습니다."
        
        tab_info["records_text"].configure(state="normal")
        tab_info["records_text"].delete("0.0", "end")
        tab_info["records_text"].insert("0.0", records_text)
        tab_info["records_text"].configure(state="disabled")
    
    def _update_summary_display(self):
        """통합 통계 업데이트"""
        summary_text = "📊 전체 가챠 통계 요약\n\n"
        
        total_all = 0
        total_5star = 0
        total_4star = 0
        total_3star = 0
        
        for banner_id, banner_info in self.banner_data.items():
            stats = banner_info.get("stats", {})
            if stats:
                banner_name = banner_info["name"]
                summary_text += f"🎯 {banner_name}:\n"
                summary_text += f"  총 {stats['total']}회 | "
                summary_text += f"5성 {stats['5star']}개 | "
                summary_text += f"4성 {stats['4star']}개 | "
                summary_text += f"3성 {stats['3star']}개\n\n"
                
                total_all += stats['total']
                total_5star += stats['5star']
                total_4star += stats['4star']
                total_3star += stats['3star']
        
        if total_all > 0:
            summary_text += f"🌟 전체 통계:\n"
            summary_text += f"  총 가챠 횟수: {total_all}회\n"
            summary_text += f"  5성 비율: {total_5star/total_all*100:.2f}% ({total_5star}개)\n"
            summary_text += f"  4성 비율: {total_4star/total_all*100:.2f}% ({total_4star}개)\n"
            summary_text += f"  3성 비율: {total_3star/total_all*100:.2f}% ({total_3star}개)\n\n"
            
            summary_text += f"💎 평균 5성 획득까지: {total_all/max(total_5star,1):.1f}회\n"
            summary_text += f"💫 평균 4성 획득까지: {total_all/max(total_4star,1):.1f}회"
        
        self.summary_text.configure(state="normal")
        self.summary_text.delete("0.0", "end")
        self.summary_text.insert("0.0", summary_text)
        self.summary_text.configure(state="disabled")
        
    def run(self):
        """애플리케이션 실행"""
        self.root.mainloop()
    
    def load_existing_data(self):
        """기존 데이터 파일 로드"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, "r", encoding="utf-8") as f:
                    saved_data = json.load(f)
                    
                # 저장된 데이터를 배너별로 복원
                for banner_id in self.banner_data.keys():
                    if banner_id in saved_data:
                        # 데이터 형태 변환 (JSON에서 객체로)
                        raw_data = saved_data[banner_id]["data"]
                        converted_data = []
                        
                        for item_dict in raw_data:
                            # 간단한 객체 생성 (honkaistarrail 객체와 유사하게)
                            item_obj = type('GachaItem', (), {})()
                            item_obj.name = item_dict.get("name", "")
                            item_obj.rank = item_dict.get("rank", 3)
                            item_obj.time = item_dict.get("time", "")
                            item_obj.type = item_dict.get("type", "")
                            converted_data.append(item_obj)
                        
                        self.banner_data[banner_id]["data"] = converted_data
                        
                        # 통계 재계산
                        self._calculate_banner_stats(banner_id)
                        
                print(f"✅ 기존 데이터 로드 완료: {self.data_file}")
                
                # UI 업데이트
                for banner_id in self.banner_data.keys():
                    if self.banner_data[banner_id]["data"]:
                        self._update_banner_display(banner_id)
                self._update_summary_display()
                        
            else:
                print(f"📝 새 데이터 파일 생성: {self.data_file}")
                self.save_data_to_file()
                
        except Exception as e:
            print(f"❌ 데이터 로드 실패: {str(e)}")
            # 데이터 로드 실패 시 빈 파일 생성
            self.save_data_to_file()
    
    def save_data_to_file(self):
        """현재 데이터를 파일에 저장"""
        try:
            save_data = {}
            
            for banner_id, banner_info in self.banner_data.items():
                # 데이터를 JSON 직렬화 가능한 형태로 변환
                serializable_data = []
                for item in banner_info["data"]:
                    item_dict = {
                        "name": getattr(item, 'name', ''),
                        "rank": getattr(item, 'rank', 3),
                        "time": str(getattr(item, 'time', '')),
                        "type": getattr(item, 'type', '')
                    }
                    serializable_data.append(item_dict)
                
                save_data[banner_id] = {
                    "name": banner_info["name"],
                    "data": serializable_data,
                    "stats": banner_info.get("stats", {})
                }
            
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
                
            print(f"💾 데이터 저장 완료: {self.data_file}")
            
        except Exception as e:
            print(f"❌ 데이터 저장 실패: {str(e)}")
    
    def merge_new_data(self, banner_id, new_data):
        """새 데이터를 기존 데이터와 중복 없이 병합"""
        if not new_data:  # 새 데이터가 없으면 바로 반환
            return 0
            
        existing_data = self.banner_data[banner_id]["data"]
        
        # 기존 데이터의 ID 집합 생성 (중복 체크용)
        existing_ids = set()
        for item in existing_data:
            if item:  # 아이템이 None이 아닌지 확인
                # name+time 조합으로 식별
                item_name = getattr(item, 'name', '')
                item_time = getattr(item, 'time', '')
                composite_id = f"{item_name}_{item_time}"
                existing_ids.add(composite_id)
        
        # 새 데이터에서 중복되지 않은 항목만 추가
        new_items_added = 0
        for item in new_data:
            if item and hasattr(item, 'name'):  # 아이템이 유효한지 확인
                item_name = getattr(item, 'name', '')
                item_time = getattr(item, 'time', '')
                check_id = f"{item_name}_{item_time}"
                
                if check_id not in existing_ids and check_id != "_":  # 빈 ID도 제외
                    existing_data.append(item)
                    existing_ids.add(check_id)
                    new_items_added += 1
        
        # 시간순 정렬 (최신순) - 안전한 정렬
        try:
            existing_data.sort(key=lambda x: str(getattr(x, 'time', '')) if x else '', reverse=True)
        except Exception as sort_error:
            print(f"정렬 중 오류: {sort_error}")
        
        return new_items_added
    
    def open_settings(self):
        """설정 창 열기"""
        if self.settings_window is not None:
            try:
                if self.settings_window.winfo_exists():
                    self.settings_window.focus()
                    return
            except:
                self.settings_window = None
        
        self.settings_window = ctk.CTkToplevel(self.root)
        self.settings_window.title("설정")
        self.settings_window.geometry("600x500")
        self.settings_window.transient(self.root)
        
        # 설정 창에도 아이콘 적용
        try:
            icon_paths = [
                resource_path("images/anaxa.ico"),
                resource_path("anaxa.ico"),
                "images/anaxa.ico",
                "anaxa.ico"
            ]
            
            for icon_path in icon_paths:
                if os.path.exists(icon_path):
                    self.settings_window.iconbitmap(icon_path)
                    break
        except Exception as e:
            print(f"설정 창 아이콘 로드 실패: {e}")
        
        # 설정 제목
        settings_title = ctk.CTkLabel(
            self.settings_window,
            text="⚙️ 설정",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        settings_title.pack(pady=(20, 10))
        
        # 스크롤 가능한 프레임
        scrollable_frame = ctk.CTkScrollableFrame(self.settings_window)
        scrollable_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # 테마 설정
        theme_frame = ctk.CTkFrame(scrollable_frame)
        theme_frame.pack(fill="x", padx=10, pady=10)
        
        theme_label = ctk.CTkLabel(theme_frame, text="테마 설정:", font=ctk.CTkFont(size=16, weight="bold"))
        theme_label.pack(anchor="w", padx=15, pady=(15, 5))
        
        theme_switch_frame = ctk.CTkFrame(theme_frame)
        theme_switch_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        self.settings_theme_switch = ctk.CTkSwitch(
            theme_switch_frame,
            text="다크 모드",
            variable=self.theme_var,
            onvalue="dark",
            offvalue="light",
            command=self.toggle_theme_in_settings
        )
        self.settings_theme_switch.pack(anchor="w", padx=15, pady=10)
        
        # 현재 테마에 맞게 스위치 상태 설정
        if self.current_theme == "dark":
            self.settings_theme_switch.select()
        else:
            self.settings_theme_switch.deselect()
        
        # 가챠 링크 획득 설정
        method_frame = ctk.CTkFrame(scrollable_frame)
        method_frame.pack(fill="x", padx=10, pady=10)
        
        method_label = ctk.CTkLabel(method_frame, text="가챠 링크 획득 방법:", font=ctk.CTkFont(size=16, weight="bold"))
        method_label.pack(anchor="w", padx=15, pady=(15, 5))
        
        method_info_frame = ctk.CTkFrame(method_frame)
        method_info_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        info_label = ctk.CTkLabel(
            method_info_frame,
            text="🔍 다음 순서로 자동 검색합니다:\n1. PowerShell 스크립트 (우선)\n2. Windows 레지스트리\n3. 게임 로그 파일\n4. 게임 웹 캐시",
            font=ctk.CTkFont(size=12),
            justify="left"
        )
        info_label.pack(anchor="w", padx=15, pady=10)
        
        # PowerShell 스크립트 테스트 버튼
        test_ps_btn = ctk.CTkButton(
            method_info_frame,
            text="🔧 PowerShell 스크립트 테스트",
            command=self.test_powershell_script,
            width=200,
            height=30,
            fg_color="blue",
            hover_color="darkblue"
        )
        test_ps_btn.pack(anchor="w", padx=15, pady=(5, 10))
        
        help_btn = ctk.CTkButton(
            method_info_frame,
            text="❓ 도움말",
            command=self.show_help,
            width=100,
            height=35,
            fg_color="gray50",
            hover_color="gray40"
        )
        help_btn.pack(anchor="w", padx=15, pady=(0, 10))
        
        # 확인/취소 버튼
        button_frame = ctk.CTkFrame(self.settings_window)
        button_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        cancel_btn = ctk.CTkButton(
            button_frame,
            text="취소",
            command=self.close_settings,
            width=100,
            height=35,
            fg_color="gray50",
            hover_color="gray40"
        )
        cancel_btn.pack(side="right", padx=(10, 0), pady=10)
        
        apply_btn = ctk.CTkButton(
            button_frame,
            text="적용",
            command=self.apply_settings,
            width=100,
            height=35
        )
        apply_btn.pack(side="right", padx=(10, 0), pady=10)
        
        # 창이 닫힐 때 변수 정리
        self.settings_window.protocol("WM_DELETE_WINDOW", self.close_settings)
    
    def toggle_theme_in_settings(self):
        """설정 창에서 테마 토글 (즉시 적용하지 않음)"""
        # 테마 변수만 업데이트하고 실제 적용은 apply_settings에서 처리
        pass
    
    def apply_settings(self):
        """설정 적용"""
        try:
            # 테마 변경
            new_theme = self.theme_var.get()
            if new_theme != self.current_theme:
                ctk.set_appearance_mode(new_theme)
                self.current_theme = new_theme
                self.save_settings()
            
            self.close_settings()
        except Exception as e:
            print(f"설정 적용 중 오류: {e}")
    
    def save_settings(self):
        """설정을 파일에 저장"""
        try:
            settings = {
                "theme": self.current_theme
            }
            with open("settings.json", "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"설정 저장 중 오류: {e}")
    
    def load_settings(self):
        """설정을 파일에서 로드"""
        try:
            if os.path.exists("settings.json"):
                with open("settings.json", "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    saved_theme = settings.get("theme", "dark")
                    self.current_theme = saved_theme
                    self.theme_var.set(saved_theme)
                    ctk.set_appearance_mode(saved_theme)
            else:
                # 기본 설정
                self.current_theme = "dark"
                self.theme_var.set("dark")
                ctk.set_appearance_mode("dark")
        except Exception as e:
            print(f"설정 로드 중 오류: {e}")
            self.current_theme = "dark"
            self.theme_var.set("dark")
            ctk.set_appearance_mode("dark")
    
    def close_settings(self):
        """설정 창 닫기"""
        try:
            if hasattr(self, 'settings_window') and self.settings_window:
                self.settings_window.destroy()
        except Exception as e:
            print(f"설정 창 닫기 중 오류: {e}")
        finally:
            self.settings_window = None
    
    def update_link_status(self):
        """링크 상태 업데이트"""
        # 조회 버튼은 항상 활성화 상태로 유지
        pass
    
    def test_powershell_script(self):
        """PowerShell 스크립트 테스트"""
        def run_test():
            link = get_gacha_link_from_powershell_script()
            if link:
                messagebox.showinfo("테스트 성공", f"✅ PowerShell 스크립트로 가챠 링크를 찾았습니다!\n\n링크: {link[:150]}...")
            else:
                messagebox.showwarning("테스트 실패", "❌ PowerShell 스크립트로 가챠 링크를 찾을 수 없습니다.\n\n게임을 실행하고 가챠 기록을 확인한 후 다시 시도하세요.")
        
        # 별도 스레드에서 실행 (UI 블록킹 방지)
        thread = threading.Thread(target=run_test, daemon=True)
        thread.start()

def get_gacha_link_from_powershell_script() -> Optional[str]:
    """PowerShell 스크립트를 사용하여 가챠 링크 추출"""
    try:
        print("🔄 PowerShell 스크립트로 가챠 링크 검색 중...")
        
        # PowerShell 스크립트 명령어
        ps_command = '''
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12;
        Invoke-Expression (New-Object Net.WebClient).DownloadString("https://gist.githubusercontent.com/Star-Rail-Station/2512df54c4f35d399cc9abbde665e8f0/raw/get_warp_link_os.ps1?cachebust=srs")
        '''
        
        # PowerShell 실행
        result = subprocess.run([
            'powershell', 
            '-NoProfile', 
            '-ExecutionPolicy', 'Bypass',
            '-Command', ps_command
        ], capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')
        
        if result.returncode == 0 and result.stdout:
            output = result.stdout.strip()
            print(f"PowerShell 스크립트 출력: {output[:200]}...")
            
            # 출력에서 가챠 링크 추출 - 개선된 방법
            lines = output.split('\n')
            for i, line in enumerate(lines):
                line = line.strip()
                
                # "Warp History Url Found!" 다음 줄에서 링크 찾기
                if "Warp History Url Found!" in line:
                    # 다음 줄에서 링크 찾기
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if next_line.startswith('https://') and 'getGachaLog' in next_line:
                            print(f"✅ PowerShell 스크립트에서 링크 발견: {next_line[:100]}...")
                            return next_line
                
                # 직접 https로 시작하는 getGachaLog 링크 찾기
                if line.startswith('https://') and 'getGachaLog' in line:
                    print(f"✅ PowerShell 스크립트에서 직접 링크 발견: {line[:100]}...")
                    return line
                
                # 줄 내에서 https 링크 찾기
                if 'https://' in line and 'getGachaLog' in line:
                    # 정규식으로 URL 추출
                    url_pattern = r'https://[^\s]*getGachaLog[^\s]*'
                    url_match = re.search(url_pattern, line)
                    if url_match:
                        link = url_match.group(0)
                        print(f"✅ PowerShell 스크립트에서 패턴 매칭으로 링크 발견: {link[:100]}...")
                        return link
            
            # 전체 출력에서 URL 패턴 찾기 (마지막 시도)
            url_pattern = r'https://public-operation-hkrpg[^\s]*getGachaLog[^\s]*'
            url_matches = re.findall(url_pattern, output)
            if url_matches:
                link = url_matches[-1]  # 가장 마지막 링크 사용
                print(f"✅ PowerShell 스크립트에서 전체 패턴 매칭으로 링크 발견: {link[:100]}...")
                return link
            
            print("❌ PowerShell 스크립트 출력에서 가챠 링크를 찾을 수 없습니다")
            print(f"전체 출력:\n{output}")
            return None
        else:
            print(f"❌ PowerShell 스크립트 실행 실패: {result.stderr}")
            return None
            
    except subprocess.TimeoutExpired:
        print("❌ PowerShell 스크립트 실행 시간 초과")
        return None
    except Exception as e:
        print(f"❌ PowerShell 스크립트 실행 중 오류: {e}")
        return None


if __name__ == "__main__":
    app = ModernGachaViewer()
    app.run()
