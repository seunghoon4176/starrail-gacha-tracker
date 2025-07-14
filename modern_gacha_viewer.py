import customtkinter as ctk
from tkinter import messagebox
import asyncio
import threading
from honkaistarrail import starrail
import json
import os
import sys
import warnings
import subprocess
import re
import winreg

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

def get_gacha_link_from_logs():
    """게임 로그 파일에서 가챠 링크 추출"""
    try:
        # Honkai Star Rail 로그 파일 경로들
        possible_paths = [
            os.path.expanduser("~/AppData/LocalLow/Cognosphere/Star Rail/Player.log"),
            os.path.expanduser("~/AppData/LocalLow/miHoYo/Star Rail/Player.log"),
            os.path.expanduser("~/AppData/LocalLow/HoYoverse/Star Rail/Player.log"),
        ]
        
        for log_path in possible_paths:
            if os.path.exists(log_path):
                print(f"로그 파일 발견: {log_path}")
                
                # 파일 크기 확인
                file_size = os.path.getsize(log_path)
                print(f"로그 파일 크기: {file_size} bytes")
                
                # 로그 파일에서 가챠 링크 찾기 - 여러 인코딩 시도
                encodings = ['utf-8', 'utf-16', 'cp949', 'latin-1']
                
                for encoding in encodings:
                    try:
                        with open(log_path, 'r', encoding=encoding, errors='ignore') as f:
                            content = f.read()
                            
                            # getGachaLog가 포함된 줄만 찾기
                            if 'getGachaLog' in content:
                                print(f"✅ getGachaLog 텍스트 발견 ({encoding} 인코딩)")
                                
                                # 더 포괄적인 가챠 링크 패턴 찾기
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
                                        # 가장 최근 링크 반환
                                        latest_link = matches[-1]
                                        # URL 정리 (특수문자 제거)
                                        latest_link = latest_link.strip('",\'()[]{}')
                                        if latest_link and 'getGachaLog' in latest_link:
                                            print(f"✅ 가챠 링크 발견: {latest_link[:100]}...")
                                            return latest_link
                                
                                # 패턴이 안 맞으면 수동으로 getGachaLog 주변 텍스트 찾기
                                lines = content.split('\n')
                                for line in lines:
                                    if 'getGachaLog' in line and 'https://' in line:
                                        # URL 추출 시도
                                        url_match = re.search(r'https://[^\s"\'<>\[\]{}|\\^`]*', line)
                                        if url_match:
                                            url = url_match.group(0).strip('",\'()[]{}')
                                            if url and 'getGachaLog' in url:
                                                print(f"✅ 수동 검색으로 가챠 링크 발견: {url[:100]}...")
                                                return url
                            else:
                                print(f"❌ getGachaLog 텍스트가 없음 ({encoding} 인코딩)")
                    except Exception as enc_error:
                        print(f"❌ {encoding} 인코딩 실패: {enc_error}")
                        continue
        
        print("❌ 로그 파일에서 가챠 링크를 찾을 수 없습니다")
        return None
        
    except Exception as e:
        print(f"❌ 로그 파일 읽기 실패: {str(e)}")
        return None

def get_gacha_link_from_registry():
    """레지스트리에서 가챠 링크 추출 (PowerShell 스크립트와 같은 방법)"""
    try:
        print("레지스트리에서 가챠 링크 검색 중...")
        
        # 가능한 레지스트리 경로들
        registry_paths = [
            (winreg.HKEY_CURRENT_USER, r"Software\miHoYo\崩坏：星穹铁道"),
            (winreg.HKEY_CURRENT_USER, r"Software\miHoYo\Honkai: Star Rail"),
            (winreg.HKEY_CURRENT_USER, r"Software\Cognosphere\Star Rail"),
            (winreg.HKEY_CURRENT_USER, r"Software\HoYoverse\Star Rail"),
        ]
        
        for hkey, subkey in registry_paths:
            try:
                with winreg.OpenKey(hkey, subkey) as key:
                    print(f"레지스트리 키 발견: {subkey}")
                    
                    # 모든 값들을 확인
                    i = 0
                    while True:
                        try:
                            name, value, reg_type = winreg.EnumValue(key, i)
                            if isinstance(value, str) and value and 'getGachaLog' in value:
                                print(f"✅ 레지스트리에서 가챠 링크 발견: {value[:100]}...")
                                return value
                            i += 1
                        except WindowsError:
                            break
                            
            except FileNotFoundError:
                continue
            except Exception as e:
                print(f"레지스트리 키 {subkey} 접근 실패: {e}")
                continue
        
        print("❌ 레지스트리에서 가챠 링크를 찾을 수 없습니다")
        return None
        
    except Exception as e:
        print(f"❌ 레지스트리 검색 실패: {str(e)}")
        return None

def get_gacha_link_from_game_cache():
    """게임 웹캐시에서 가챠 링크 추출 (PowerShell 스크립트 방식)"""
    try:
        print("게임 웹캐시에서 가챠 링크 검색 중...")
        
        # 1. 로그 파일에서 게임 경로 찾기
        log_paths = [
            os.path.expanduser("~/AppData/LocalLow/Cognosphere/Star Rail/Player.log"),
            os.path.expanduser("~/AppData/LocalLow/Cognosphere/Star Rail/Player-prev.log"),
            os.path.expanduser("~/AppData/LocalLow/miHoYo/Star Rail/Player.log"),
            os.path.expanduser("~/AppData/LocalLow/miHoYo/Star Rail/Player-prev.log"),
            os.path.expanduser("~/AppData/LocalLow/HoYoverse/Star Rail/Player.log"),
            os.path.expanduser("~/AppData/LocalLow/HoYoverse/Star Rail/Player-prev.log"),
        ]
        
        game_path = None
        for log_path in log_paths:
            if os.path.exists(log_path):
                print(f"로그 파일 확인: {log_path}")
                try:
                    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                        # 처음 11줄만 읽기 (PowerShell 스크립트와 동일)
                        lines = []
                        for i in range(11):
                            line = f.readline()
                            if not line:
                                break
                            lines.append(line.strip())
                        
                        for line in lines:
                            if line and line.startswith("Loading player data from "):
                                game_path = line.replace("Loading player data from ", "").replace("data.unity3d", "").strip()
                                if game_path and os.path.exists(game_path):
                                    print(f"✅ 게임 경로 발견: {game_path}")
                                    break
                        
                        if game_path:
                            break
                except Exception as e:
                    print(f"로그 파일 읽기 실패: {e}")
                    continue
        
        if not game_path:
            print("❌ 게임 경로를 찾을 수 없습니다")
            return None
        
        # 2. 웹캐시 경로 찾기 (최신 버전)
        cache_base = os.path.join(game_path, "webCaches")
        if not os.path.exists(cache_base):
            print(f"❌ 웹캐시 폴더가 없습니다: {cache_base}")
            return None
        
        print(f"웹캐시 폴더 확인: {cache_base}")
        
        # 기본 캐시 경로
        cache_path = os.path.join(game_path, "webCaches", "Cache", "Cache_Data", "data_2")
        max_version = 0
        
        # 버전 폴더들 확인
        try:
            for folder_name in os.listdir(cache_base):
                folder_path = os.path.join(cache_base, folder_name)
                if os.path.isdir(folder_path):
                    # 버전 형식 확인 (예: 2.7.0.1)
                    if re.match(r'^\d+\.\d+\.\d+\.\d+$', folder_name):
                        try:
                            version_num = int(folder_name.replace('.', ''))
                            if version_num >= max_version:
                                max_version = version_num
                                cache_path = os.path.join(game_path, "webCaches", folder_name, "Cache", "Cache_Data", "data_2")
                                print(f"최신 버전 캐시 경로: {cache_path}")
                        except:
                            continue
        except Exception as e:
            print(f"버전 폴더 확인 실패: {e}")
        
        # 3. 캐시 파일에서 URL 찾기
        if not os.path.exists(cache_path):
            print(f"❌ 캐시 파일이 없습니다: {cache_path}")
            return None
        
        print(f"캐시 파일 분석 중: {cache_path}")
        file_size = os.path.getsize(cache_path)
        print(f"캐시 파일 크기: {file_size} bytes")
        
        try:
            with open(cache_path, 'rb') as f:
                cache_data = f.read()
        except PermissionError:
            print(f"❌ 권한 부족: {cache_path}")
            print("💡 해결 방법: 프로그램을 관리자 권한으로 실행하거나 게임을 종료하세요")
            
            # 대안: 복사본을 만들어서 읽기 시도
            try:
                import shutil
                import tempfile
                import subprocess
                
                print("🔄 임시 복사본 생성 시도...")
                with tempfile.NamedTemporaryFile(delete=False, suffix='_cache_copy') as temp_file:
                    temp_path = temp_file.name
                
                # 방법 1: shutil로 직접 복사 시도
                try:
                    shutil.copy2(cache_path, temp_path)
                    print(f"✅ 직접 복사 성공: {temp_path}")
                    copy_success = True
                except Exception as direct_copy_error:
                    print(f"❌ 직접 복사 실패: {direct_copy_error}")
                    copy_success = False
                
                # 방법 2: robocopy를 사용한 복사 시도 (Windows 내장)
                if not copy_success:
                    try:
                        print("🔄 robocopy 시도...")
                        cache_dir = os.path.dirname(cache_path)
                        cache_filename = os.path.basename(cache_path)
                        temp_dir = os.path.dirname(temp_path)
                        
                        result = subprocess.run([
                            'robocopy', cache_dir, temp_dir, cache_filename, 
                            '/COPY:DAT', '/R:1', '/W:1'
                        ], capture_output=True, text=True, timeout=30)
                        
                        copied_file = os.path.join(temp_dir, cache_filename)
                        if os.path.exists(copied_file):
                            print(f"✅ robocopy 복사 성공: {copied_file}")
                            shutil.move(copied_file, temp_path)
                            copy_success = True
                        else:
                            print(f"❌ robocopy 실패: {result.stderr}")
                            
                    except Exception as robocopy_error:
                        print(f"❌ robocopy 오류: {robocopy_error}")
                
                # 방법 3: PowerShell을 사용한 복사 시도
                if not copy_success:
                    try:
                        print("🔄 PowerShell 복사 시도...")
                        ps_script = f'''
                        try {{
                            Copy-Item -Path "{cache_path}" -Destination "{temp_path}" -Force
                            if (Test-Path "{temp_path}") {{
                                Write-Output "SUCCESS"
                            }} else {{
                                Write-Output "FAILED: File not created"
                            }}
                        }} catch {{
                            Write-Output "FAILED: $($_.Exception.Message)"
                        }}
                        '''
                        
                        result = subprocess.run([
                            'powershell', '-NoProfile', '-Command', ps_script
                        ], capture_output=True, text=True, timeout=30)
                        
                        if "SUCCESS" in result.stdout and os.path.exists(temp_path):
                            print(f"✅ PowerShell 복사 성공: {temp_path}")
                            copy_success = True
                        else:
                            print(f"❌ PowerShell 복사 실패: {result.stdout}")
                            
                    except Exception as ps_error:
                        print(f"❌ PowerShell 복사 오류: {ps_error}")
                
                if copy_success and os.path.exists(temp_path):
                    with open(temp_path, 'rb') as f:
                        cache_data = f.read()
                    print(f"✅ 캐시 데이터 로드 성공: {len(cache_data)} bytes")
                else:
                    raise Exception("모든 복사 방법 실패")
                
                # 임시 파일 정리
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except:
                    pass
                    
            except Exception as copy_error:
                print(f"❌ 복사본 생성 실패: {copy_error}")
                print("🛡️ 권한 문제 해결 방법:")
                print("  1. 프로그램을 관리자 권한으로 실행하세요")
                print("  2. 게임을 완전히 종료한 후 다시 시도하세요")
                print("  3. 게임 브라우저 캐시를 삭제하고 가챠 기록을 다시 확인하세요")
                return None
        except Exception as read_error:
            print(f"❌ 캐시 파일 읽기 실패: {read_error}")                
            return None
        
        # UTF-8로 디코딩
        cache_text = cache_data.decode('utf-8', errors='ignore')
        
        # '1/0/'로 분할 (PowerShell 스크립트와 동일)
        cache_parts = cache_text.split('1/0/')
        print(f"캐시 파트 개수: {len(cache_parts)}")
        
        # 역순으로 검색 (최신 데이터부터)
        for i in range(len(cache_parts) - 1, -1, -1):
                part = cache_parts[i]
                
                # getGachaLog 또는 getLdGachaLog 포함된 http URL 찾기
                if part and part.startswith('http') and ('getGachaLog' in part or 'getLdGachaLog' in part):
                    # null 문자로 분할해서 첫 번째 부분만 가져오기
                    url = part.split('\0')[0]
                    
                    if url and len(url.strip()) > 0:
                        print(f"✅ 캐시에서 가챠 URL 발견: {url[:100]}...")
                        
                        # URL 검증 (간단한 방법으로 시도)
                        try:
                            # urllib를 사용해서 간단히 검증
                            import urllib.request
                            import urllib.error
                            import urllib.parse
                            import json
                            
                            print(f"URL 검증 시도: {url[:80]}...")
                            
                            # URL 파라미터 확인 및 수정
                            parsed_url = urllib.parse.urlparse(url)
                            query_params = urllib.parse.parse_qs(parsed_url.query)
                            
                            # 필요한 파라미터 확인 및 추가
                            if 'game' not in query_params:
                                query_params['game'] = ['hkrpg']  # Honkai Star Rail
                                print("✅ 'game=hkrpg' 파라미터 추가")
                            
                            if 'gacha_type' not in query_params:
                                query_params['gacha_type'] = ['1']  # 기본 배너 타입
                                print("✅ 'gacha_type=1' 파라미터 추가")
                            
                            if 'page' not in query_params:
                                query_params['page'] = ['1']
                                print("✅ 'page=1' 파라미터 추가")
                            
                            if 'size' not in query_params:
                                query_params['size'] = ['20']
                                print("✅ 'size=20' 파라미터 추가")
                            
                            # URL 재구성
                            new_query = urllib.parse.urlencode(query_params, doseq=True)
                            corrected_url = urllib.parse.urlunparse((
                                parsed_url.scheme,
                                parsed_url.netloc,
                                parsed_url.path,
                                parsed_url.params,
                                new_query,
                                parsed_url.fragment
                            ))
                            
                            print(f"수정된 URL로 검증: {corrected_url[:80]}...")
                            
                            req = urllib.request.Request(corrected_url)
                            with urllib.request.urlopen(req, timeout=10) as response:
                                if response.status == 200:
                                    response_text = response.read().decode('utf-8')
                                    try:
                                        data = json.loads(response_text)
                                        retcode = data.get('retcode') if data else None
                                        message = data.get('message', '') if data else ''
                                        
                                        print(f"API 응답: retcode={retcode}, message='{message}'")
                                        
                                        if retcode == 0:
                                            print("✅ URL 검증 성공!")
                                            return corrected_url
                                        elif retcode == -111:
                                            print("❌ 게임 이름 오류 - 파라미터 문제")
                                        elif retcode == -101:
                                            print("❌ 인증 키 만료 또는 유효하지 않음")
                                        else:
                                            print(f"❌ API 오류: retcode={retcode}, message='{message}'")
                                    except (json.JSONDecodeError, AttributeError) as json_error:
                                        print(f"❌ JSON 파싱 실패: {json_error}")
                                        # JSON 파싱 실패해도 수정된 URL은 반환
                                        return corrected_url
                                else:
                                    print(f"❌ HTTP 상태 오류: {response.status}")
                        except Exception as verify_error:
                            print(f"❌ URL 검증 실패: {verify_error}")
                            # 검증 실패해도 원본 URL은 반환 (네트워크 문제일 수 있음)
                            return url
            
            print("❌ 캐시에서 가챠 URL을 찾을 수 없습니다")
            return None
            
        except Exception as e:
            print(f"❌ 캐시 파일 읽기 실패: {e}")
            return None
        
    except Exception as e:
        print(f"❌ 게임 캐시 검색 실패: {str(e)}")
        return None

# CustomTkinter 테마 설정 (초기값만, 실제 설정은 load_settings에서)
ctk.set_default_color_theme("blue")  # "blue", "green", "dark-blue"


class ModernGachaViewer:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("로컬 워프 트래커")
        self.root.geometry("800x800")
        self.root.resizable(False, False)  # 창 크기 조절 비활성화
        
        # 윈도우 아이콘 설정
        try:
            # PyInstaller 환경에서도 작동하는 아이콘 경로
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
        
        # 데이터 저장용
        self.banner_data = {
            "1": {"name": "이벤트 배너", "data": [], "stats": {}},
            "2": {"name": "광추 배너", "data": [], "stats": {}},
            "3": {"name": "상시 배너", "data": [], "stats": {}}
        }
        
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
        
        # 기본 설정 변수들 (글로벌/한국어로 고정)
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
        """비동기 모든 배너 조회"""
        try:
            self.update_progress(0, "🔄 연결 준비 중...")
            
            # 언어 설정 (한국어 고정)
            api_lang = "kr"
            
            # 링크 확인 및 디버깅
            self.update_progress(0.05, "🔍 가챠 링크 자동 검색 중...")
            
            gacha_link = None
            
            # 1. 레지스트리에서 링크 검색 (PowerShell 방식)
            self.update_progress(0.06, "🔍 레지스트리에서 가챠 링크 검색 중...")
            try:
                gacha_link = get_gacha_link_from_registry()
                if gacha_link and isinstance(gacha_link, str) and len(gacha_link.strip()) > 0:
                    print(f"레지스트리에서 링크 발견: {gacha_link[:50]}...")
                else:
                    gacha_link = None
            except Exception as e:
                print(f"레지스트리 검색 오류: {e}")
                gacha_link = None
            
            if not gacha_link:
                # 2. 게임 로그 파일에서 링크 검색
                self.update_progress(0.07, "🔍 게임 로그에서 가챠 링크 검색 중...")
                try:
                    gacha_link = get_gacha_link_from_logs()
                    if gacha_link and isinstance(gacha_link, str) and len(gacha_link.strip()) > 0:
                        print(f"로그에서 링크 발견: {gacha_link[:50]}...")
                    else:
                        gacha_link = None
                except Exception as e:
                    print(f"로그 검색 오류: {e}")
                    gacha_link = None
            
            if not gacha_link:
                # 3. 게임 웹캐시에서 링크 검색 (PowerShell 방식)
                self.update_progress(0.08, "🔍 게임 웹캐시에서 가챠 링크 검색 중...")
                try:
                    gacha_link = get_gacha_link_from_game_cache()
                    if gacha_link and isinstance(gacha_link, str) and len(gacha_link.strip()) > 0:
                        print(f"게임 캐시에서 링크 발견: {gacha_link[:50]}...")
                    else:
                        gacha_link = None
                except Exception as e:
                    print(f"게임 캐시 검색 오류: {e}")
                    gacha_link = None
            
            # 링크 확인
            if gacha_link and isinstance(gacha_link, str) and len(gacha_link.strip()) > 0:
                self.update_progress(0.1, "✅ 가챠 링크 발견! 연결 테스트 중...")
                print(f"사용할 링크: {gacha_link[:50]}...")
            else:
                self.update_progress(0.1, "🔍 자동 링크 감지 시도 중...")
                gacha_link = ""  # 빈 링크로 자동 감지 시도
            
            # 링크 테스트
            try:
                print(f"테스트 시작: {gacha_link[:80] if gacha_link else '빈 링크'}...")
                
                # 빈 링크인 경우 자동 감지 모드로 시도
                if not gacha_link or gacha_link.strip() == "":
                    print("🔍 빈 링크 - 자동 감지 모드로 시도...")
                    test_link = None  # None을 전달해서 자동 감지 시도
                else:
                    test_link = gacha_link
                
                async with starrail.Jump(link=test_link, banner=1, lang=api_lang) as test_hist:
                    # 테스트로 첫 번째 배치만 가져오기
                    test_success = False
                    batch_count = 0
                    try:
                        async for batch in test_hist.get_history():
                            batch_count += 1
                            print(f"배치 {batch_count}: {type(batch)}, 길이: {len(batch) if batch and hasattr(batch, '__len__') else 'N/A'}")
                            
                            if batch and isinstance(batch, (list, tuple)) and len(batch) > 0:  # 데이터가 있으면 성공
                                print(f"✅ 첫 번째 아이템: {getattr(batch[0], 'name', 'Unknown') if hasattr(batch[0], 'name') else batch[0]}")
                                test_success = True
                                
                                # 자동 감지 성공 시 실제 링크 업데이트
                                if not gacha_link or gacha_link.strip() == "":
                                    try:
                                        # Jump 객체에서 실제 사용된 링크 추출 시도
                                        actual_link = getattr(test_hist, 'link', None) or getattr(test_hist, 'url', None)
                                        if actual_link:
                                            gacha_link = actual_link
                                            print(f"✅ 자동 감지된 링크 사용: {gacha_link[:50]}...")
                                    except Exception as link_extract_error:
                                        print(f"링크 추출 실패: {link_extract_error}")
                                
                                break
                            elif batch_count > 3:  # 3번 시도 후 중단
                                print("❌ 3번 시도 후에도 유효한 데이터 없음")
                                break
                                
                    except Exception as test_error:
                        error_str = str(test_error)
                        print(f"테스트 기록 조회 오류: {error_str}")
                        
                        # 더 구체적인 오류 분석
                        if "Check if the link is correct" in error_str:
                            raise Exception("가챠 링크 없음 - 게임에서 가챠 기록을 먼저 확인하세요")
                        elif "'NoneType' object has no attribute 'get'" in error_str:
                            raise Exception("API 응답 형식 오류 - 서버에서 올바르지 않은 응답을 반환했습니다")
                        elif "game name error" in error_str.lower():
                            raise Exception("게임 파라미터 오류 - URL에 필요한 파라미터가 누락되었습니다")
                        elif "retcode" in error_str.lower() and "-111" in error_str:
                            raise Exception("API 게임 이름 오류 (retcode: -111)")
                        elif "retcode" in error_str.lower() and "-101" in error_str:
                            raise Exception("인증 키 만료 또는 유효하지 않음 (retcode: -101)")
                        elif "authkey" in error_str.lower():
                            raise Exception("인증 키 오류 - 가챠 링크가 만료되었거나 유효하지 않습니다")
                        elif "timeout" in error_str.lower():
                            raise Exception("연결 시간 초과 - 네트워크 상태를 확인하세요")
                        else:
                            raise Exception(f"API 연결 오류: {error_str}")
                    
                    if not test_success:
                        raise Exception("가챠 기록을 찾을 수 없습니다 - 게임에서 가챠 기록을 먼저 확인하세요")
                        
                self.update_progress(0.15, "✅ 가챠 링크 확인 완료")
                
            except Exception as link_error:
                error_msg = str(link_error)
                print(f"링크 테스트 오류: {error_msg}")
                
                if "Check if the link is correct" in error_msg or "가챠 링크 없음" in error_msg:
                    detailed_error = """❌ 가챠 링크를 찾을 수 없습니다!

🔧 문제: 자동 링크 검색에 실패했습니다.

💡 해결 방법:
1. Honkai: Star Rail 게임을 실행하세요
2. 게임 내에서 워프(가챠) → 기록 메뉴로 이동
3. 각 배너(이벤트/광추/상시)의 기록을 한 번씩 확인
4. 게임을 종료하지 말고 다시 시도하세요

🔧 추가 해결책:
• 게임을 관리자 권한으로 실행
• 프로그램을 관리자 권한으로 실행
• 게임 재시작 후 가챠 기록 재확인
• 브라우저 캐시 삭제

⚠️ 주의: 반드시 게임 내 가챠 기록을 먼저 열어봐야 합니다!"""
                elif "'NoneType' object has no attribute 'get'" in error_msg:
                    detailed_error = """❌ API 응답 오류!

🔧 문제: 서버에서 예상과 다른 응답을 받았습니다.

💡 해결 방법:
1. 게임을 완전히 재시작하세요
2. 게임 내에서 워프(가챠) → 기록을 새로 열어보세요
3. 모든 배너의 기록을 한 번씩 확인하세요
4. 몇 분 기다린 후 다시 시도하세요
5. 인터넷 연결 상태를 확인하세요

⚠️ 주의: 가챠 서버가 일시적으로 불안정할 수 있습니다."""
                elif "API 응답 형식 오류" in error_msg:
                    detailed_error = """❌ 서버 응답 오류!

🔧 문제: 가챠 서버에서 올바르지 않은 응답을 받았습니다.

💡 해결 방법:
1. 잠시 기다린 후 다시 시도하세요
2. 게임을 재시작하고 가챠 기록을 새로 확인하세요
3. VPN을 사용 중이라면 끄고 시도하세요

⚠️ 참고: 서버 점검 시간이거나 일시적 장애일 수 있습니다."""
                elif "game name error" in error_msg.lower() or "-111" in error_msg:
                    detailed_error = """❌ 가챠 링크 파라미터 오류!

🔧 문제: URL에 필요한 게임 파라미터가 누락되었습니다.

💡 해결 방법:
1. 게임을 완전히 재시작하세요
2. 게임 내에서 워프(가챠) → 기록 메뉴로 이동
3. 각 배너의 기록을 다시 한 번씩 확인
4. 브라우저 캐시를 완전히 삭제하세요
5. 몇 분 기다린 후 다시 시도하세요

⚠️ 주의: 게임 재시작 후 반드시 가챠 기록을 새로 열어봐야 합니다!"""
                elif "-101" in error_msg or "authkey" in error_msg.lower():
                    detailed_error = """❌ 인증 키 만료!

🔧 문제: 가챠 링크의 인증 키가 만료되었습니다.

💡 해결 방법:
1. 게임을 재시작하세요
2. 게임 내 가챠 기록을 새로 열어보세요
3. 몇 분 기다린 후 다시 시도하세요"""
                elif "timeout" in error_msg.lower():
                    detailed_error = """❌ 연결 시간 초과!

🔧 문제: 서버 연결이 시간 초과되었습니다.

💡 해결 방법:
1. 인터넷 연결 상태를 확인하세요
2. VPN 사용 중이라면 끄고 시도하세요
3. 잠시 후 다시 시도하세요"""
                elif "가챠 기록을 찾을 수 없습니다" in error_msg:
                    detailed_error = """❌ 가챠 기록 없음!

🔧 해결 방법:
1. Honkai: Star Rail 게임을 실행하세요
2. 게임 내에서 워프(가챠) → 기록 메뉴로 이동
3. 각 배너(이벤트/광추/상시)의 기록을 한 번씩 확인
4. 게임을 종료하지 말고 다시 시도하세요

💡 추가 해결책:
• 게임 재시작 후 가챠 기록 재확인
• 브라우저 캐시 삭제
• 다른 브라우저로 게임 실행

⚠️ 주의: 게임 내 가챠 기록을 먼저 열어봐야 합니다!"""
                else:
                    detailed_error = f"""❌ 연결 오류!

🔧 문제: {error_msg}

💡 해결 방법:
1. 게임을 재시작하세요
2. 인터넷 연결을 확인하세요
3. 잠시 후 다시 시도하세요"""
                
                self.update_progress(0, detailed_error)
                messagebox.showerror("가챠 링크 오류", detailed_error)
                return
            
            total_banners = 3
            
            for i, banner_id in enumerate(["1", "2", "3"]):
                banner_name = self.banner_data[banner_id]["name"]
                self.update_progress(0.2 + (i * 0.25), f"📊 {banner_name} 조회 중...")
                
                try:
                    # Jump 클라이언트 사용 (발견된 링크 또는 자동 감지)
                    print(f"배너 {banner_id} ({banner_name}) 조회 시작...")
                    async with starrail.Jump(link=gacha_link, banner=int(banner_id), lang=api_lang) as hist:
                        new_data = []
                        batch_count = 0
                        error_count = 0
                        max_errors = 3
                        
                        try:
                            async for batch in hist.get_history():
                                batch_count += 1
                                
                                if batch and isinstance(batch, (list, tuple)):  # 배치가 유효한지 확인
                                    valid_items = 0
                                    for item in batch:
                                        if item and hasattr(item, 'name'):  # 아이템이 유효한지 확인
                                            new_data.append(item)
                                            valid_items += 1
                                    
                                    if valid_items > 0:
                                        print(f"배치 {batch_count}: {valid_items}개 유효 아이템 추가")
                                    else:
                                        print(f"배치 {batch_count}: 유효하지 않은 아이템들")
                                        error_count += 1
                                elif batch is None:
                                    print(f"배치 {batch_count}: None 배치 (정상 종료 신호일 수 있음)")
                                    break
                                else:
                                    print(f"배치 {batch_count}: 유효하지 않은 배치 타입 - {type(batch)}")
                                    error_count += 1
                                
                                # 너무 많은 오류가 발생하면 중단
                                if error_count >= max_errors:
                                    print(f"❌ 연속 오류 {max_errors}회 발생, 배너 조회 중단")
                                    break
                                
                                # 진행 상황 업데이트
                                if batch_count % 5 == 0:  # 5배치마다 업데이트
                                    self.update_progress(0.2 + (i * 0.25) + 0.05, 
                                        f"📊 {banner_name}: {len(new_data)}개 기록 로딩 중...")
                                    
                        except Exception as history_error:
                            error_str = str(history_error)
                            print(f"❌ {banner_name} 기록 읽기 중 오류: {error_str}")
                            
                            # 특정 오류에 대한 처리
                            if "'NoneType' object has no attribute 'get'" in error_str:
                                print(f"API 응답 형식 오류 - {banner_name} 건너뜀")
                            elif "authkey" in error_str.lower() or "-101" in error_str:
                                print(f"인증 키 오류 - {banner_name} 건너뜀")
                            elif "-111" in error_str:
                                print(f"게임 파라미터 오류 - {banner_name} 건너뜀")
                        
                        print(f"✅ {banner_name}: {len(new_data)}개 기록 조회 완료")
                        
                except Exception as banner_error:
                    error_str = str(banner_error)
                    print(f"❌ {banner_name} 조회 실패: {error_str}")
                    
                    # 특정 배너 실패 시 빈 데이터로 계속 진행
                    new_data = []
                    
                    # 오류 유형별 로그
                    if "'NoneType' object has no attribute 'get'" in error_str:
                        print(f"💡 {banner_name} API 응답 오류 - 다음 배너로 계속...")
                    elif "authkey" in error_str.lower():
                        print(f"💡 {banner_name} 인증 오류 - 다음 배너로 계속...")
                    elif "timeout" in error_str.lower():
                        print(f"💡 {banner_name} 시간 초과 - 다음 배너로 계속...")
                
                # 새 데이터 병합 (중복 제거)
                new_items_added = self.merge_new_data(banner_id, new_data)
                
                # 통계 계산 및 UI 업데이트
                self._calculate_banner_stats(banner_id)
                self._update_banner_display(banner_id)
                
                # 진행 상황 업데이트
                total_items = len(self.banner_data[banner_id]["data"])
                self.update_progress(0.2 + (i * 0.25) + 0.08, 
                    f"📊 {banner_name}: {total_items}개 기록 (+{new_items_added}개 신규)")
            
            # 데이터 파일에 저장
            self.save_data_to_file()
            
            self._update_summary_display()
            self.update_progress(1, "✅ 모든 배너 조회 완료!")
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ 전체 조회 실패: {error_msg}")
            self.update_progress(0, f"❌ 오류: {error_msg}")
            messagebox.showerror("오류", f"데이터 조회 실패:\n{error_msg}")
    
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
            "5star_intervals": []  # 5성 간격 저장
        }
        
        last_5star_index = -1
        
        for i, item in enumerate(data):
            if not item:  # None 체크
                continue
                
            rank = getattr(item, 'rank', 3)  # 안전한 속성 접근
            try:
                rank_str = str(rank)
            except:
                rank_str = "3"  # 기본값
                
            if rank_str == "5":
                stats["5star"] += 1
                item_name = getattr(item, 'name', 'Unknown')
                item_time = str(getattr(item, 'time', ''))
                stats["5star_items"].append((item_name, item_time, i+1))  # 인덱스도 저장
                
                # 5성 간격 계산
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
        
        # 기록 업데이트 (5성 간격 포함)
        if data:
            records_text = "📜 가챠 기록 (최신순)\n\n"
            
            five_star_positions = []
            for i, item in enumerate(data):
                if item:  # None 체크
                    item_rank = getattr(item, 'rank', 3)
                    if str(item_rank) == "5":
                        five_star_positions.append(i)
            
            for i, item in enumerate(data[:10]):  # 10개 기록만 표시
                if not item:  # None 체크
                    continue
                    
                item_rank = getattr(item, 'rank', 3)
                item_name = getattr(item, 'name', 'Unknown')
                item_time = getattr(item, 'time', '')
                
                try:
                    star_icon = "⭐" * int(item_rank) if isinstance(item_rank, (int, str)) else "⭐"
                except:
                    star_icon = "⭐"
                
                # 5성인 경우 간격 정보 추가
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
                
                # 색상 구분을 위한 프리픽스
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
                # 창이 이미 파괴된 경우
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
        
        # 자동 획득 설정 (수동 입력 제거)
        method_frame = ctk.CTkFrame(scrollable_frame)
        method_frame.pack(fill="x", padx=10, pady=10)
        
        method_label = ctk.CTkLabel(method_frame, text="가챠 링크 획득:", font=ctk.CTkFont(size=16, weight="bold"))
        method_label.pack(anchor="w", padx=15, pady=(15, 5))
        
        method_info_frame = ctk.CTkFrame(method_frame)
        method_info_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        info_label = ctk.CTkLabel(
            method_info_frame,
            text="✅ 자동 획득 모드가 활성화되어 있습니다.\n게임을 실행하고 워프 기록을 한 번 확인한 후 조회하세요.",
            font=ctk.CTkFont(size=12),
            justify="left"
        )
        info_label.pack(anchor="w", padx=15, pady=10)
        
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


if __name__ == "__main__":
    app = ModernGachaViewer()
    app.run()
