import os
import sys
import threading
import asyncio
import tempfile
import subprocess
import webbrowser
import warnings
import customtkinter as ctk
from tkinter import filedialog, messagebox  # messagebox 추가
import json
import requests  # 추가: 자동 업데이트 체크용
from collections import OrderedDict  # OrderedDict 추가
from typing import Optional, List, Any  # Optional, List, Any 추가
import pandas as pd  # pandas가 설치되어 있다면 사용, 없으면 아래 except에서 안내

#자체 모듈
from GachaLinkFinder import GachaLinkFinder
from GachaAPI import GachaAPI
from GachaLinkFinder import get_gacha_link_from_registry, get_gacha_link_from_logs
from ErrorHandler import ErrorHandler
from CacheFileManager import get_gacha_link_from_game_cache

CURRENT_VERSION = "1.0.2"  # 실제 배포시 버전 문자열로 관리
GITHUB_API = "https://api.github.com/repos/seunghoon4176/starrail-gacha-tracker/releases/latest"

# Pydantic V2 호환성 경고 숨기기
warnings.filterwarnings("ignore", message="Valid config keys have changed in V2")
warnings.filterwarnings("ignore", message=".*underscore_attrs_are_private.*", category=UserWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic._internal._config")

# CustomTkinter 테마 설정 (초기값만, 실제 설정은 load_settings에서)
ctk.set_default_color_theme("blue")  # "blue", "green", "dark-blue"

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

class ModernGachaViewer:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("로컬 워프 트래커 V1.0.1")
        self.root.geometry("700x950")  # ← 창 크기(고정)
        self.root.resizable(False, False)  # ← 리사이즈 가능 여부
        
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
        
        # 실제 스타레일 배너 타입 전체 포함 (콜라보 배너 포함)
        self.banner_data = OrderedDict([
            ("11", {"name": "한정 캐릭터 배너", "data": [], "stats": {}}),    # CHARACTER = '11' (실제 데이터 확인됨: 917개)
            ("12", {"name": "한정 광추 배너", "data": [], "stats": {}}),      # LIGHT_CONE = '12' (광추 UP 배너)
            ("21", {"name": "콜라보 캐릭터 배너", "data": [], "stats": {}}), # 콜라보 캐릭터 배너 (Rust 코드에서 확인됨)
            ("22", {"name": "콜라보 광추 배너", "data": [], "stats": {}}),   # 콜라보 광추 배너 (Rust 코드에서 확인됨)
            ("1", {"name": "상시 배너", "data": [], "stats": {}}),          # STELLAR = '1' (실제 데이터 확인됨: 222개)
            ("2", {"name": "초보자 배너", "data": [], "stats": {}})         # DEPARTURE = '2' (초보자 배너)
        ])
        
        # 에러 핸들러 추가
        self.error_handler = ErrorHandler()

        # 배너 페이지네이션 정보 초기화 (setup_ui보다 먼저!)
        self.banner_pagination = {}  # {banner_id: {"page": int, "total_pages": int}}
        self.setup_ui()
        
        # 기본 설정 변수들 (구문 오류 수정)
        self.link_method = ctk.StringVar(value="auto")  # 자동으로 기본 설정
        self.theme_var = ctk.StringVar(value="dark")  # 테마 변수 추가
        self.lang_var = ctk.StringVar(value="kr")     # 언어 변수 추가 (기본 kr)
        self.current_theme = "dark"  # 현재 테마 추적
        self.current_lang = "kr"     # 현재 언어 추적
        
        # 데이터 파일 초기화
        self.data_file = "gacha_records.json"
        
        # 설정 로드
        self.load_settings()
        
        # 아래 함수가 없으면 임시로 주석 처리하거나, 아래와 같이 간단히 추가하세요.
        self.load_existing_data()
        
        # 초기 링크 상태 확인
        self.update_link_status()
        
        # self.check_update_on_startup()  # 자동 업데이트 체크
        # 메뉴바 생성
        self.create_menu_bar()
        # 자동 업데이트 체크는 메뉴바 생성 이후에 호출
        self.check_update_on_startup()

    def check_update_on_startup(self):
        """GitHub 릴리즈에서 최신 버전 확인 및 자동 다운로드/실행 안내"""
        try:
            resp = requests.get(GITHUB_API, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                latest_ver = data.get("tag_name", "")
                body = data.get("body", "")
                if latest_ver and latest_ver != CURRENT_VERSION:
                    assets = data.get("assets", [])
                    exe_asset = None
                    for asset in assets:
                        if asset["name"].endswith(".exe"):
                            exe_asset = asset
                            break
                    if exe_asset:
                        url = exe_asset["browser_download_url"]
                        msg = f"새 버전이 있습니다: {latest_ver}\n\n지금 자동으로 다운로드할까요?"
                        if messagebox.askyesno("업데이트 알림", msg):
                            local_path = os.path.join(tempfile.gettempdir(), exe_asset["name"])
                            try:
                                with requests.get(url, stream=True, timeout=30) as r:
                                    r.raise_for_status()
                                    with open(local_path, "wb") as f:
                                        for chunk in r.iter_content(chunk_size=8192):
                                            f.write(chunk)
                                messagebox.showinfo("다운로드 완료", f"새 버전이 다운로드되었습니다.\n프로그램을 종료하고 새 버전을 실행합니다.")
                                # 업데이트 공지(릴리즈 노트) 표시
                                self.show_update_notice_after_update(body, latest_ver)
                                subprocess.Popen([local_path])
                                self.root.destroy()
                            except Exception as e:
                                messagebox.showerror("업데이트 실패", f"다운로드 또는 실행 중 오류 발생:\n{e}")
                    else:
                        url = data.get("html_url", "https://github.com/seunghoon4176/starrail-gacha-tracker/releases")
                        msg = f"새 버전이 있습니다: {latest_ver}\n\n업데이트 페이지로 이동할까요?"
                        if messagebox.askyesno("업데이트 알림", msg):
                            webbrowser.open(url)
        except Exception as e:
            print(f"업데이트 확인 실패: {e}")

    def show_update_notice_after_update(self, body, latest_ver):
        """업데이트 후에만 공지(릴리즈 노트) 표시"""
        msg = f"업데이트 공지 (v{latest_ver})\n\n{body or '공지 없음'}"
        notice_win = ctk.CTkToplevel(self.root)
        notice_win.title("업데이트 공지")
        notice_win.geometry("520x420")
        try:
            icon_paths = [
                resource_path("images/anaxa.ico"),
                resource_path("anaxa.ico"),
                "images/anaxa.ico",
                "anaxa.ico"
            ]
            for icon_path in icon_paths:
                if os.path.exists(icon_path):
                    notice_win.iconbitmap(icon_path)
                    break
        except Exception:
            pass
        notice_text = ctk.CTkTextbox(notice_win)
        notice_text.pack(fill="both", expand=True, padx=20, pady=20)
        notice_text.insert("0.0", msg)
        notice_text.configure(state="disabled")

    def create_menu_bar(self):
        """상단 메뉴바 생성 (기존 워프 트래커 불러오기/업데이트 공지/개발자 문의)"""
        menubar = ctk.CTkFrame(self.root, height=28)
        menubar.pack(fill="x", padx=0, pady=(0, 2))
        # 기존 워프 트래커 불러오기 버튼
        import_btn = ctk.CTkButton(
            menubar,
            text="📂 기존 워프 트래커 불러오기",
            width=180,
            height=24,
            font=ctk.CTkFont(size=13),
            command=self.import_old_tracker_file
        )
        import_btn.pack(side="left", padx=(8, 4), pady=2)
        # 업데이트 공지 보기 버튼
        notice_btn = ctk.CTkButton(
            menubar,
            text="📰 업데이트 공지 보기",
            width=150,
            height=24,
            font=ctk.CTkFont(size=13),
            command=self.show_update_notice
        )
        notice_btn.pack(side="left", padx=(4, 4), pady=2)
        # 개발자 도와주기 버튼 추가
        support_btn = ctk.CTkButton(
            menubar,
            text="개발자에게 문의하기(오픈채팅)",
            width=150,
            height=24,
            font=ctk.CTkFont(size=13),
            command=lambda: webbrowser.open("https://open.kakao.com/o/sE05H3Vf")
        )
        support_btn.pack(side="left", padx=(4, 4), pady=2)

        # 120 FPS 언락 버튼 추가
        unlock_fps_btn = ctk.CTkButton(
            menubar,
            text="🎮 120 FPS 언락",
            width=130,
            height=24,
            font=ctk.CTkFont(size=13),
            command=self.unlock_120fps
        )
        unlock_fps_btn.pack(side="left", padx=(4, 8), pady=2)

    def show_update_notice(self):
        """깃허브 릴리즈에서 공지(릴리즈 노트) 불러와서 표시"""
        # 이미 창이 열려 있으면 기존 창을 앞으로 가져오고 새로 만들지 않음
        if hasattr(self, "_update_notice_window") and self._update_notice_window is not None:
            try:
                if self._update_notice_window.winfo_exists():
                    self._update_notice_window.lift()
                    self._update_notice_window.focus_force()
                    return
            except Exception:
                self._update_notice_window = None

        try:
            resp = requests.get(GITHUB_API, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                latest_ver = data.get("tag_name", "")
                body = data.get("body", "")
                if latest_ver and latest_ver != CURRENT_VERSION:
                    msg = f"새 버전: {latest_ver}\n\n{body}"
                else:
                    msg = f"현재 프로그램 버전은({CURRENT_VERSION})입니다.\n\n{body or '공지 없음'}"
            else:
                msg = "공지 불러오기 실패"
        except Exception as e:
            msg = f"공지 불러오기 오류: {e}"

        notice_win = ctk.CTkToplevel(self.root)
        notice_win.title("업데이트 공지")
        notice_win.geometry("520x420")
        notice_win.transient(self.root)
        notice_win.lift()
        notice_win.focus_force()
        # 창이 닫힐 때 변수 해제
        def on_close():
            self._update_notice_window = None
            notice_win.destroy()
        notice_win.protocol("WM_DELETE_WINDOW", on_close)
        self._update_notice_window = notice_win

        try:
            icon_paths = [
                resource_path("images/anaxa.ico"),
                resource_path("anaxa.ico"),
                "images/anaxa.ico",
                "anaxa.ico"
            ]
            for icon_path in icon_paths:
                if os.path.exists(icon_path):
                    notice_win.iconbitmap(icon_path)
                    break
        except Exception:
            pass
        notice_text = ctk.CTkTextbox(notice_win)
        notice_text.pack(fill="both", expand=True, padx=20, pady=20)
        notice_text.insert("0.0", msg)
        notice_text.configure(state="disabled")

    def import_old_tracker_file(self):
        """기존 워프 트래커/백업 파일 불러오기 (json/csv/xlsx/dat)"""
        file_path = filedialog.askopenfilename(
            title="기존 워프 트래커/백업 파일 선택",
            filetypes=[
                ("지원되는 파일", "*.json;*.csv;*.xlsx;*.dat"),
                ("JSON 파일", "*.json"),
                ("CSV 파일", "*.csv"),
                ("Excel 파일", "*.xlsx"),
                ("DAT 파일", "*.dat"),
                ("모든 파일", "*.*"),
            ]
        )
        if not file_path:
            return
        try:
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".json":
                with open(file_path, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                self._import_old_tracker_json(old_data)
                msg = "기존 워프 트래커(JSON) 데이터를 성공적으로 불러왔습니다."
            elif ext == ".csv":
                try:
                    import pandas as pd
                except ImportError:
                    messagebox.showerror("불러오기 실패", "pandas 라이브러리가 필요합니다.\n\npip install pandas")
                    return
                df = pd.read_csv(file_path)
                self._import_backup_dataframe(df)
                msg = "CSV 백업 데이터를 성공적으로 불러왔습니다."
            elif ext == ".xlsx":
                try:
                    import pandas as pd
                except ImportError:
                    messagebox.showerror("불러오기 실패", "pandas 라이브러리가 필요합니다.\n\npip install pandas openpyxl")
                    return
                df = pd.read_excel(file_path)
                self._import_backup_dataframe(df)
                msg = "Excel 백업 데이터를 성공적으로 불러왔습니다."
            elif ext == ".dat":
                # dat 파일은 바이너리/텍스트 모두 시도
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        text = f.read()
                    # json 형식이면 json으로 시도
                    if text.strip().startswith("{"):
                        old_data = json.loads(text)
                        self._import_old_tracker_json(old_data)
                        msg = "DAT(JSON) 데이터를 성공적으로 불러왔습니다."
                    else:
                        messagebox.showinfo("불러오기 안내", "DAT 파일은 자동 변환을 지원하지 않습니다.\nCSV 또는 Excel로 변환 후 불러오세요.")
                        return
                except Exception:
                    messagebox.showinfo("불러오기 안내", "DAT 파일은 자동 변환을 지원하지 않습니다.\nCSV 또는 Excel로 변환 후 불러오세요.")
                    return
            else:
                messagebox.showerror("불러오기 실패", "지원하지 않는 파일 형식입니다.")
                return

            self.save_data_to_file()
            self._update_summary_display()
            for banner_id in self.banner_data:
                self._calculate_banner_stats(banner_id)
                self._update_banner_display(banner_id)
            messagebox.showinfo("불러오기 완료", msg)
        except Exception as e:
            messagebox.showerror("불러오기 실패", f"파일을 불러오지 못했습니다:\n{e}")

    def _import_backup_dataframe(self, df):
        """
        starrailstation 등 외부 서비스 백업(csv/xlsx) → 내부 데이터 변환
        컬럼 예시: uid,id,rarity,time,banner,type,manual
        """
        # id→이름 매핑은 저장하지 않고, 데이터에는 id만 저장
        # 이름은 UI 표시 시에만 언어 설정에 따라 변환해서 보여줌

        # 기존 데이터 초기화 (중복 방지)
        for banner_id in self.banner_data:
            self.banner_data[banner_id]["data"] = []

        # 컬럼명 소문자 변환 및 공백 제거
        df.columns = [str(col).strip().lower() for col in df.columns]

        # 컬럼명 매핑 (유연하게)
        colmap = {
            "uid": "uid",
            "id": "id",
            "name": "name",
            "rarity": "rarity",
            "rank": "rarity",
            "time": "time",
            "datetime": "time",
            "banner": "banner",
            "type": "type",
            "manual": "manual"
        }

        def getval(row, key):
            for k in [key, key.lower(), key.upper()]:
                if k in row:
                    return row[k]
            return ""

        # 배너 매핑: banner/type 값에 따라 내부 배너ID 결정
        banner_map = {
            ("1001", "1"): "1",    # 상시
            ("2063", "11"): "11",  # 한정캐릭
            ("3078", "12"): "12",  # 한정광추
            # 필요시 추가
        }
        # 기본: type이 1이면 상시("1"), 11이면 한정캐릭("11"), 12면 한정광추("12")
        for _, row in df.iterrows():
            row = {str(k).strip().lower(): v for k, v in row.items()}
            banner = str(getval(row, "banner"))
            type_ = str(getval(row, "type"))
            rarity = int(getval(row, "rarity") or 3)
            id_val = str(getval(row, "id"))
            name = str(getval(row, "name") or "")  # name은 저장하지 않음
            time = str(getval(row, "time") or getval(row, "datetime"))
            # 배너ID 결정 (더 간결하게)
            banner_id = banner_map.get((banner, type_))
            if not banner_id:
                banner_id = {"1": "1", "11": "11", "12": "12"}.get(type_, "1")
            # 객체 생성
            item_obj = type('GachaItem', (), {})()
            item_obj.id = id_val
            item_obj.rank = rarity
            # ISO8601 → "YYYY-MM-DD HH:MM:SS"
            try:
                from datetime import datetime
                item_obj.time = datetime.fromisoformat(time.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                item_obj.time = time
            item_obj.type = ""
            item_obj.gacha_type = type_
            item_obj.uid = str(getval(row, "uid"))
            # 배너에 추가
            # 중복 방지: 같은 time, id, rank가 이미 있으면 추가하지 않음
            exists = False
            for exist in self.banner_data[banner_id]["data"]:
                if (
                    getattr(exist, "time", None) == item_obj.time and
                    getattr(exist, "id", None) == item_obj.id and
                    getattr(exist, "rank", None) == item_obj.rank
                ):
                    exists = True
                    break
            if not exists:
                self.banner_data[banner_id]["data"].append(item_obj)
        # 최신순 정렬
        for banner_id in self.banner_data:
            self.banner_data[banner_id]["data"] = sorted(
                self.banner_data[banner_id]["data"],
                key=lambda x: (getattr(x, "time", ""), getattr(x, "id", "")),
                reverse=True
            )

    def _get_item_name_by_id(self, item_id, lang="kr"):
        """
        item_id로 이름을 반환 (언어별)
        hakushin_data/character.json, lightcone.json을 모두 참조
        """
        # 캐시: (item_id, lang) -> name
        if not hasattr(self, "_item_name_cache"):
            self._item_name_cache = {}
        cache = self._item_name_cache

        # json 파일 전체 캐시 (프로세스 내 1회만)
        # 파일 대신 원격 API에서 불러옴
        if not hasattr(self, "_character_json_cache"):
            try:
                url = "https://api.hakush.in/hsr/data/character.json"
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                self._character_json_cache = resp.json()
            except Exception:
                self._character_json_cache = {}
        if not hasattr(self, "_lightcone_json_cache"):
            try:
                url = "https://api.hakush.in/hsr/data/lightcone.json"
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                self._lightcone_json_cache = resp.json()
            except Exception:
                self._lightcone_json_cache = {}

        key = (item_id, lang)
        if key in cache:
            return cache[key]

        name = ""
        # 디버깅: 어떤 id/lang이 들어오는지 출력
        #print(f"[DEBUG] _get_item_name_by_id: item_id={item_id!r}, lang={lang!r}")

        # 1. 캐릭터에서 id로 바로 찾기
        chars = self._character_json_cache
        if isinstance(chars, dict) and str(item_id) in chars:
            c = chars[str(item_id)]
            #print(f"[DEBUG] 캐릭터에서 찾음: {item_id}")
            if lang == "kr":
                name = c.get("kr") or c.get("name_kr") or c.get("ko") or c.get("name") or c.get("en")
            elif lang == "en":
                name = c.get("en") or c.get("name_en") or c.get("name") or c.get("kr")
            elif lang == "jp":
                name = c.get("jp") or c.get("name_jp") or c.get("name") or c.get("en")
            elif lang == "cn":
                name = c.get("cn") or c.get("name_cn") or c.get("name") or c.get("en")
            else:
                name = c.get("name") or c.get("kr") or c.get("en")
            if not name:
                name = c.get(lang)
        # 2. 광추에서 id로 바로 찾기
        if not name:
            cones = self._lightcone_json_cache
            if isinstance(cones, dict) and str(item_id) in cones:
                c = cones[str(item_id)]
                #print(f"[DEBUG] 광추에서 찾음: {item_id}")
                if lang == "kr":
                    name = c.get("kr") or c.get("name_kr") or c.get("ko") or c.get("name") or c.get("en")
                elif lang == "en":
                    name = c.get("en") or c.get("name_en") or c.get("name") or c.get("kr")
                elif lang == "jp":
                    name = c.get("jp") or c.get("name_jp") or c.get("name") or c.get("en")
                elif lang == "cn":
                    name = c.get("cn") or c.get("name_cn") or c.get("name") or c.get("en")
                else:
                    name = c.get("name") or c.get("kr") or c.get("en")
                if not name:
                    name = c.get(lang)
        if not name:
            #print(f"[DEBUG] 이름 매칭 실패: item_id={item_id!r}, lang={lang!r}")
            name = ""  # fallback을 빈 문자열로
        cache[key] = name
        return name

    def setup_ui(self):
        # 메인 컨테이너 (여백 조정)
        self.main_container = ctk.CTkFrame(self.root)
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 간단한 컨트롤 패널
        self.create_simple_control_panel()
        
        # 탭뷰 (스크롤 가능하게)
        self.create_tabview()
        
        # 설정 창 초기화
        self.settings_window = None
        
    def create_simple_control_panel(self):
        """간단한 컨트롤 패널 생성"""
        control_frame = ctk.CTkFrame(self.main_container)
        control_frame.pack(fill="x", padx=5, pady=(5, 0))

        row_frame = ctk.CTkFrame(control_frame)
        row_frame.pack(fill="x", padx=10, pady=8)

        # 조회 버튼 (왼쪽)
        self.fetch_all_btn = ctk.CTkButton(
            row_frame,
            text="🎯 모든 배너 조회",
            command=self.fetch_all_banners,
            width=180,
            height=38,
            font=ctk.CTkFont(size=15, weight="bold"),
            state="normal"
        )
        self.fetch_all_btn.pack(side="left", padx=(0, 8))

        # 설정 버튼 (중간)
        settings_btn = ctk.CTkButton(
            row_frame,
            text="⚙️ 설정",
            command=self.open_settings,
            width=90,
            height=32,
            fg_color="gray50",
            hover_color="gray40"
        )
        settings_btn.pack(side="left", padx=(0, 8))

        # 프로그레스 바 (오른쪽, 남은 공간 모두 차지)
        self.progress_bar = ctk.CTkProgressBar(row_frame, height=14)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.progress_bar.set(0)

        # 상태 라벨 (맨 오른쪽)
        self.status_label = ctk.CTkLabel(
            row_frame,
            text="📝 대기 중...",
            font=ctk.CTkFont(size=12),
            width=180
        )
        self.status_label.pack(side="left")

    def create_tabview(self):
        """탭뷰 생성 (스크롤 프레임 제거, 탭뷰만 사용)"""
        self.tabview = ctk.CTkTabview(self.main_container)
        self.tabview.pack(fill="both", expand=True, padx=0, pady=0)
        
        # 배너별 탭 생성
        self.banner_tabs = {}
        for banner_id, banner_info in self.banner_data.items():
            self.create_banner_tab(banner_id, banner_info["name"])
        
        # 통합 통계 탭
        self.create_summary_tab()
        
    def create_banner_tab(self, banner_id, banner_name):
        """배너별 탭 생성"""
        tab = self.tabview.add(banner_name)

        # 통계 프레임 (상단)
        stats_frame = ctk.CTkFrame(tab)
        # fill="both", expand=True로 변경하여 통계 영역이 최대한 확장되도록 함
        stats_frame.pack(fill="both", expand=True, padx=10, pady=(10, 5))

        stats_label = ctk.CTkLabel(
            stats_frame,
            text="📊 통계",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        stats_label.pack(anchor="w", padx=15, pady=(10, 2))

        # height를 크게 하고, fill="both", expand=True로 확장
        stats_text = ctk.CTkTextbox(stats_frame, height=200)
        stats_text.pack(fill="both", expand=True, padx=15, pady=(0, 8))
        stats_text.configure(state="disabled")

        # 페이지네이션 컨트롤 (통계와 기록 사이에 위치)
        pagination_frame = ctk.CTkFrame(tab)
        pagination_frame.pack(fill="x", padx=15, pady=(0, 5))
        center_frame = ctk.CTkFrame(pagination_frame, fg_color="transparent")
        center_frame.pack(anchor="center", expand=True)

        # 맨앞으로 버튼 추가
        first_btn = ctk.CTkButton(
            center_frame,
            text="⏮ 맨앞",
            width=70,
            command=lambda bid=banner_id: self.goto_page(bid, 1)
        )
        first_btn.pack(side="left", padx=(0, 5))

        prev_btn = ctk.CTkButton(
            center_frame,
            text="⬅ 이전",
            width=80,
            command=lambda bid=banner_id: self.change_page(bid, -1)
        )
        prev_btn.pack(side="left", padx=(0, 10))

        page_label = ctk.CTkLabel(
            center_frame,
            text="1 / 1",
            width=80
        )
        page_label.pack(side="left")

        next_btn = ctk.CTkButton(
            center_frame,
            text="다음 ➡",
            width=80,
            command=lambda bid=banner_id: self.change_page(bid, 1)
        )
        next_btn.pack(side="left", padx=(10, 0))

        # 맨뒤로 버튼 추가
        last_btn = ctk.CTkButton(
            center_frame,
            text="맨뒤 ⏭",
            width=70,
            command=lambda bid=banner_id: self.goto_last_page(bid)
        )
        last_btn.pack(side="left", padx=(5, 0))

        # 기록 프레임 (중간)
        records_frame = ctk.CTkFrame(tab)
        records_frame.pack(fill="x", padx=10, pady=(0, 5))

        records_label = ctk.CTkLabel(
            records_frame,
            text="📜 가챠 기록",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        records_label.pack(anchor="w", padx=15, pady=(10, 2))

        records_text = ctk.CTkTextbox(
            records_frame,
            height=400,
            font=ctk.CTkFont(size=14)
        )
        # pack 옵션에서 expand=True를 제거하고 fill="x"로 제한
        records_text.pack(fill="x", padx=15, pady=(0, 5))
        records_text.configure(state="disabled")

        # records_frame의 pack 옵션에서 expand=True도 제거
        records_frame.pack(fill="x", padx=10, pady=(0, 5))

        self.banner_tabs[banner_id] = {
            "tab": tab,
            "stats_text": stats_text,
            "records_text": records_text,
            "prev_btn": prev_btn,
            "next_btn": next_btn,
            "page_label": page_label,
            "first_btn": first_btn,
            "last_btn": last_btn
        }
        self.banner_pagination[banner_id] = {"page": 1, "total_pages": 1}

    def goto_page(self, banner_id, page):
        pag = self.banner_pagination[banner_id]
        if 1 <= page <= pag["total_pages"]:
            pag["page"] = page
            self._update_banner_display(banner_id)

    def goto_last_page(self, banner_id):
        pag = self.banner_pagination[banner_id]
        self.goto_page(banner_id, pag["total_pages"])

    def change_page_current_tab(self, delta):
        """현재 선택된 탭의 페이지를 변경"""
        current_tab = self.tabview.get()
        # 탭 이름에서 banner_id 찾기
        for banner_id, tabinfo in self.banner_tabs.items():
            if self.tabview.tab(banner_id) == current_tab:
                self.change_page(banner_id, delta)
                break

    def change_page(self, banner_id, delta):
        pag = self.banner_pagination[banner_id]
        new_page = pag["page"] + delta
        if 1 <= new_page <= pag["total_pages"]:
            pag["page"] = new_page
            self._update_banner_display(banner_id)

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
        # 조회 중에는 버튼 비활성화
        self.fetch_all_btn.configure(state="disabled")
        def run_fetch():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._fetch_all_banners_async())
            loop.close()
            # 조회 완료 후 버튼 다시 활성화 (메인스레드에서 실행)
            self.root.after(0, lambda: self.fetch_all_btn.configure(state="normal"))
        thread = threading.Thread(target=run_fetch, daemon=True)
        thread.start()
    
    async def _fetch_all_banners_async(self):
        """비동기 모든 배너 조회 - 개선된 버전"""
        try:
            self.update_progress(0, "🔄 연결 준비 중...")
            api_lang = "ko"  # kr에서 ko로 변경
            
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
        # 1. 레지스트리 검색
        self.update_progress(0.05, "🔍 레지스트리 검색 중...")
        link = get_gacha_link_from_registry()
        if link:
            return link
        
        # 2. 로그 파일 검색
        self.update_progress(0.07, "🔍 게임 로그 검색 중...")
        link = get_gacha_link_from_logs()
        if link:
            return link
        
        # 3. 게임 캐시 검색
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
            # retcode -101은 인증키 만료(유효기간 초과)임을 사용자에게 안내
            message = (
                "가챠 기록을 찾을 수 없습니다 - 게임에서 가챠 기록을 먼저 확인하세요.\n\n"
                "또는 인증키(authkey)가 만료되었습니다.\n"
                "게임을 실행한 후 워프(가챠) 기록을 한 번 열고 다시 시도하세요."
            )
            raise Exception(message)
        
        print(f"✅ 검증 성공")
    
    async def _fetch_banners_data(self, gacha_link: str, api_lang: str):
        """배너별 데이터 조회 - 콜라보 배너 포함 전체 6개 배너 조회"""
        # 전체 배너를 순서대로 조회 (콜라보 배너 포함)
        all_banner_ids = ["11", "12", "21", "22", "1", "2"]  # CHARACTER, LIGHT_CONE, 콜라보캐릭, 콜라보광추, STELLAR, DEPARTURE
        
        for i, banner_id in enumerate(all_banner_ids):
            banner_name = self.banner_data[banner_id]["name"]
            progress_value = 0.2 + (i * 0.12)  # 6개 배너에 맞게 진행률 조정
            self.update_progress(progress_value, f"📊 {banner_name} 조회 중...")
            
            try:
                print(f"\n🔍 === {banner_name} (타입 {banner_id}) 조회 시작 ===")
                new_data = await self._fetch_banner_data(gacha_link, banner_id, api_lang)
                new_items_added = self.merge_new_data(banner_id, new_data)
                
                self._calculate_banner_stats(banner_id)
                self._update_banner_display(banner_id)
                
                total_items = len(self.banner_data[banner_id]["data"])
                
                if total_items > 0:
                    status_msg = f"✅ {banner_name}: {total_items}개 기록 (+{new_items_added}개 신규)"
                    print(f"✅ {banner_name} 조회 완료: {total_items}개 기록")
                else:
                    status_msg = f"ℹ️ {banner_name}: 기록 없음"
                    print(f"ℹ️ {banner_name}: 기록 없음")
                    
                self.update_progress(progress_value + 0.02, status_msg)
                
                # API 호출 간격을 늘려서 -110 오류 방지
                await asyncio.sleep(1.5)
                    
            except Exception as e:
                print(f"❌ {banner_name} 조회 실패: {e}")
                self.update_progress(progress_value + 0.02, f"❌ {banner_name}: 조회 실패")
                continue

    async def _fetch_banner_data(self, gacha_link: str, banner_id: str, api_lang: str) -> List[Any]:
        """개별 배너 데이터 조회 - 콜라보 배너 포함 전체 배너 매핑"""
        api = GachaAPI(gacha_link)
        banner_type_map = {
            "11": "11",
            "12": "12",
            "21": "21",
            "22": "22",
            "1": "1",
            "2": "2"
        }
        gacha_type = banner_type_map.get(banner_id, banner_id)
        print(f"🔍 배너 {banner_id} ({self.banner_data[banner_id]['name']}) -> gacha_type {gacha_type} 조회 시작")
        records = await api.fetch_gacha_records(gacha_type, api_lang)
        print(f"📊 배너 {banner_id}: {len(records)}개 기록 조회됨")
        if records:
            actual_gacha_type = records[0].get("gacha_type", "unknown")
            first_item_name = records[0].get("name", "unknown")
            first_item_rank = records[0].get("rank_type", "unknown")
            print(f"✅ 실제 API 응답 - gacha_type: {actual_gacha_type}, 첫 아이템: {first_item_name} ({first_item_rank}성)")
        else:
            # 빈 결과도 시도해보기 위해 다른 언어로 재시도
            if api_lang != "en":
                print(f"🔄 언어를 'en'으로 변경하여 재시도...")
                records = await api.fetch_gacha_records(gacha_type, "en")
                print(f"📊 영어로 재시도 결과: {len(records)}개 기록")
        
        # 레코드를 객체로 변환
        converted_records = []
        for record in records:
            item_obj = type('GachaItem', (), {})()
            # 아이템 id 필드 우선순위: item_id > itemId > id
            item_obj.id = (
                record.get("item_id")
                or record.get("itemId")
                or record.get("id")
                or ""
            )
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
    
    def merge_new_data(self, banner_id, new_data):
        """새로 조회한 데이터를 기존 데이터와 병합(중복 제거)하고 추가된 개수 반환"""
        existing = self.banner_data[banner_id]["data"]
        # id가 없는 데이터는 name+time으로 중복 체크
        def item_key(item):
            return (getattr(item, "id", None) or "", getattr(item, "name", ""), getattr(item, "time", ""))
        existing_keys = set(item_key(item) for item in existing)
        added = 0
        for item in new_data:
            key = item_key(item)
            if key not in existing_keys:
                existing.append(item)
                existing_keys.add(key)
                added += 1
        # 최신순 정렬 (time, id 기준)
        self.banner_data[banner_id]["data"] = sorted(
            existing, key=lambda x: (getattr(x, "time", ""), getattr(x, "id", "")), reverse=True
        )
        return added

    def _update_banner_display(self, banner_id):
        """배너 화면 업데이트 - 시각적으로 개선된 버전 (타입 안전성 강화)"""
        tab_info = self.banner_tabs[banner_id]
        data = self.banner_data[banner_id]["data"]
        stats = self.banner_data[banner_id]["stats"]

        # 통계 업데이트 - 더 시각적으로 (타입 체크 추가)
        if stats and stats.get('total', 0) > 0:
            total = stats.get('total', 0)
            five_star = stats.get('5star', 0)
            four_star = stats.get('4star', 0)
            three_star = stats.get('3star', 0)

            avg_interval = 0
            if stats.get("5star_intervals"):
                avg_interval = sum(stats["5star_intervals"]) / len(stats["5star_intervals"])

            # 별 색상: 5성(노랑), 4성(보라), 3성(회색)
            def color_star(star, color):
                # CTkTextbox는 색상 지원 안함, 유니코드 이모지로 대체
                if color == "yellow":
                    return "⭐"
                elif color == "purple":
                    return "🟣"
                elif color == "gray":
                    return "⚪"
                return star

            fire_icons = color_star("★", "yellow") * min(int(five_star), 10) if five_star else "⚪"
            purple_icons = color_star("★", "purple") * min(int(four_star) // 10, 10) if four_star else "⚪"
            white_icons = color_star("★", "gray") * min(int(three_star) // 100, 10) if three_star else "⚪"
            pity_count = stats.get('pity_count', 0)
            green_bars = "🟩" * max(0, (90 - int(pity_count)) // 10)
            yellow_bars = "🟨" * min(int(pity_count) // 10, 9)

            stats_text = f"""📊 {self.banner_data[banner_id]["name"]} 통계

🎯 총 가챠 횟수: {total:,}회

⭐ 5성: {five_star}개 ({(five_star / max(total, 1)) * 100:.1f}%) {fire_icons}
💜 4성: {four_star}개 ({(four_star / max(total, 1)) * 100:.1f}%) {purple_icons}
✨ 3성: {three_star}개 ({(three_star / max(total, 1)) * 100:.1f}%) {white_icons}

🔥 현재 천장까지: {pity_count}회 {green_bars + yellow_bars}
💎 평균 5성 간격: {avg_interval:.1f}회"""

            if stats.get("5star_intervals"):
                min_interval = min(stats["5star_intervals"])
                max_interval = max(stats["5star_intervals"])
                stats_text += f"\n📈 최단/최장 간격: {min_interval}회 / {max_interval}회"

            # 운 평가 추가 (안전한 계산)
            if total > 0:
                try:
                    luck_score = (five_star / max(total, 1)) * 100
                    if luck_score >= 2.0:
                        luck_emoji = "🌈✨ 대박 운!"
                    elif luck_score >= 1.6:
                        luck_emoji = "🍀 좋은 운!"
                    elif luck_score >= 1.0:
                        luck_emoji = "😊 평균 운"
                    else:
                        luck_emoji = "😢 아쉬운 운..."
                    stats_text += f"\n\n🎰 운빨 지수: {luck_emoji}"
                except (TypeError, ValueError):
                    stats_text += f"\n\n🎰 운빨 지수: 😊 계산 중..."
        else:
            stats_text = (
                f"📊 {self.banner_data[banner_id]['name']} 통계\n\n"
                "❌ 가챠 기록이 없습니다.\n"
                "게임에서 해당 배너의 가챠 기록을 한 번 열어주세요!\n"
                "가챠를 뽑고 기록을 확인한 뒤 다시 조회해보세요.\n"
                "행운을 빕니다! 🍀"
            )

        tab_info["stats_text"].configure(state="normal")
        tab_info["stats_text"].delete("0.0", "end")
        tab_info["stats_text"].insert("0.0", stats_text)
        tab_info["stats_text"].configure(state="disabled")

        # 페이지네이션 계산
        items_per_page = 10  # 기존 15 → 10개로 변경
        total_items = len(data)
        total_pages = max(1, (total_items + items_per_page - 1) // items_per_page)
        pag = self.banner_pagination[banner_id]
        if pag["page"] > total_pages:
            pag["page"] = 1
        pag["total_pages"] = total_pages
        current_page = pag["page"]

        # 기록 업데이트 - 페이지네이션 적용
        if data:
            records_text = f"🎊 가챠 기록 (최신순, {current_page}/{total_pages}페이지)\n" + "="*50 + "\n\n"
            five_star_positions = []
            for i, item in enumerate(data):
                if item:
                    try:
                        item_rank = getattr(item, 'rank', 3)
                        if str(item_rank) == "5":
                            five_star_positions.append(i)
                    except:
                        continue

            start_idx = (current_page - 1) * items_per_page
            end_idx = min(start_idx + items_per_page, total_items)
            for i in range(start_idx, end_idx):
                item = data[i]
                if not item:
                    continue

                try:
                    item_rank = getattr(item, 'rank', 3)
                    item_id = getattr(item, 'id', '')
                    # 이름은 언어 설정에 따라 동적으로 변환 (hakushin_data 활용)
                    lang_code = getattr(self, "current_lang", "kr")
                    item_name = self._get_item_name_by_id(item_id, lang=lang_code)
                    item_time = getattr(item, 'time', '')

                    # 시간 포맷팅
                    try:
                        from datetime import datetime
                        time_obj = datetime.strptime(item_time, "%Y-%m-%d %H:%M:%S")
                        time_display = time_obj.strftime("%m/%d %H:%M")
                    except:
                        time_display = str(item_time)[:16] if item_time else "알 수 없음"

                    # 이름이 id와 같거나 매핑 실패시 id만 보이지 않게, 매핑 성공시만 이름 표시
                    if item_name and item_name != item_id and item_name.strip() != "":
                        item_name_display = item_name
                    else:
                        item_name_display = "알 수 없음"

                    if str(item_rank) == "5":
                        rank_display = "⭐⭐⭐⭐⭐"
                        prefix = "🌟"
                        name_style = f"【{item_name_display}】"
                        border = "╔" + "═" * 30 + "╗"
                        records_text += f"{border}\n"
                    elif str(item_rank) == "4":
                        rank_display = "⭐⭐⭐⭐"
                        prefix = "💜"
                        name_style = f"『{item_name_display}』"
                    else:
                        rank_display = "⭐⭐⭐"
                        prefix = "🔹"
                        name_style = item_name_display  # 3성은 그냥 이름

                    # interval_info 계산
                    interval_info = ""
                    if str(item_rank) == "5" and i in five_star_positions:
                        try:
                            pos_in_5star = five_star_positions.index(i)
                            if pos_in_5star > 0:
                                prev_5star_pos = five_star_positions[pos_in_5star - 1]
                                interval = i - prev_5star_pos
                                if interval <= 10:
                                    interval_info = f" 🍀 초대박 {interval}뽑!"
                                elif interval <= 30:
                                    interval_info = f" 🎉 대박 {interval}뽑!"
                                elif interval <= 60:
                                    interval_info = f" 😊 {interval}뽑"
                                else:
                                    interval_info = f" 😭 {interval}뽑..."
                        except (ValueError, IndexError):
                            interval_info = ""

                    # 한 줄에 시간, 이름, 등급, 운 정보 등 표시 (uid는 표시하지 않음)
                    records_text += f"{i+1:2d}. {prefix} {rank_display} {name_style}  ⏰ {time_display}{interval_info}\n"

                    if str(item_rank) == "5":
                        records_text += "╚" + "═" * 30 + "╝\n"

                    records_text += "\n"
                except Exception as e:
                    print(f"기록 표시 중 오류 (항목 {i}): {e}")
                    continue
        else:
            records_text = (
                "❌ 가챠 기록이 없습니다.\n"
                "게임에서 해당 배너의 가챠 기록을 한 번 열어주세요!\n"
                "가챠를 뽑고 기록을 확인한 뒤 다시 조회해보세요.\n"
                "행운을 빕니다! 🍀"
            )

        tab_info["records_text"].configure(state="normal")
        tab_info["records_text"].delete("0.0", "end")
        tab_info["records_text"].insert("0.0", records_text)
        tab_info["records_text"].configure(state="disabled")

        # 페이지네이션 컨트롤 업데이트 (각 탭별)
        tab_info["page_label"].configure(text=f"{current_page} / {total_pages}")
        tab_info["prev_btn"].configure(state="normal" if current_page > 1 else "disabled")
        tab_info["next_btn"].configure(state="normal" if current_page < total_pages else "disabled")
        tab_info["first_btn"].configure(state="normal" if current_page > 1 else "disabled")
        tab_info["last_btn"].configure(state="normal" if current_page < total_pages else "disabled")

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

        # 언어 설정 추가
        lang_frame = ctk.CTkFrame(scrollable_frame)
        lang_frame.pack(fill="x", padx=10, pady=10)

        lang_label = ctk.CTkLabel(lang_frame, text="이름 표시 언어:", font=ctk.CTkFont(size=16, weight="bold"))
        lang_label.pack(anchor="w", padx=15, pady=(15, 5))

        lang_switch_frame = ctk.CTkFrame(lang_frame)
        lang_switch_frame.pack(fill="x", padx=15, pady=(0, 15))

        lang_options = [("한국어", "kr"), ("영어", "en")]
        lang_dropdown = ctk.CTkOptionMenu(
            lang_switch_frame,
            variable=self.lang_var,
            values=[v for _, v in lang_options],
            command=lambda _: None
        )
        lang_dropdown.set(self.lang_var.get())
        lang_dropdown.pack(anchor="w", padx=15, pady=10)

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
            # 언어 변경
            new_lang = self.lang_var.get()
            if new_lang != getattr(self, "current_lang", "kr"):
                self.current_lang = new_lang
                # 모든 배너/요약 갱신
                for banner_id in self.banner_data:
                    self._update_banner_display(banner_id)
                self._update_summary_display()
            self.save_settings()
            self.close_settings()
        except Exception as e:
            print(f"설정 적용 중 오류: {e}")

    def save_settings(self):
        """설정을 파일에 저장"""
        try:
            settings = {
                "theme": self.current_theme,
                "lang": self.lang_var.get()
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
                    saved_lang = settings.get("lang", "kr")
                    self.current_theme = saved_theme
                    self.theme_var.set(saved_theme)
                    ctk.set_appearance_mode(saved_theme)
                    self.current_lang = saved_lang
                    self.lang_var.set(saved_lang)
            else:
                self.current_theme = "dark"
                self.theme_var.set("dark")
                ctk.set_appearance_mode("dark")
                self.current_lang = "kr"
                self.lang_var.set("kr")
        except Exception as e:
            print(f"설정 로드 중 오류: {e}")
            self.current_theme = "dark"
            self.theme_var.set("dark")
            ctk.set_appearance_mode("dark")
            self.current_lang = "kr"
            self.lang_var.set("kr")

    def load_existing_data(self):
        """CSV 파일에서 기존 데이터 로드 (name 없이)"""
        try:
            csv_path = "data.csv"
            if os.path.exists(csv_path):
                import pandas as pd
                df = pd.read_csv(csv_path)
                # 컬럼명 강제 지정
                df.columns = [c.strip().lower() for c in df.columns]
                # 기존 데이터 초기화
                for banner_id in self.banner_data:
                    self.banner_data[banner_id]["data"] = []
                # 각 row를 객체로 변환
                for _, row in df.iterrows():
                    banner_id = str(row.get("banner", "1"))
                    item_obj = type('GachaItem', (), {})()
                    item_obj.uid = str(row.get("uid", ""))
                    item_obj.id = str(row.get("id", ""))
                    item_obj.rank = int(row.get("rarity", 3))
                    item_obj.time = str(row.get("time", ""))
                    item_obj.gacha_type = str(row.get("type", ""))
                    item_obj.manual = row.get("manual", False)
                    if banner_id in self.banner_data:
                        self.banner_data[banner_id]["data"].append(item_obj)
                for banner_id in self.banner_data.keys():
                    self._calculate_banner_stats(banner_id)
                    if self.banner_data[banner_id]["data"]:
                        self._update_banner_display(banner_id)
                self._update_summary_display()
            else:
                self.save_data_to_file()  # 최초 실행 시 빈 파일 생성
        except Exception as e:
            print(f"❌ CSV 데이터 로드 실패: {str(e)}")
            self.save_data_to_file()

    def save_data_to_file(self):
        """현재 데이터를 data.csv로 저장 (CSV 포맷, name 없이)"""
        try:
            rows = []
            for banner_id, banner_info in self.banner_data.items():
                for item in banner_info["data"]:
                    # uid, id, rarity, time, banner, type, manual
                    rows.append({
                        "uid": getattr(item, 'uid', ''),
                        "id": getattr(item, 'id', ''),
                        "rarity": getattr(item, 'rank', 3),
                        "time": str(getattr(item, 'time', '')),
                        "banner": banner_id,
                        "type": getattr(item, 'gacha_type', ''),
                        "manual": getattr(item, 'manual', False)
                    })
            if rows:
                import pandas as pd
                df = pd.DataFrame(rows)
                df.to_csv("data.csv", index=False, encoding="utf-8-sig", columns=["uid","id","rarity","time","banner","type","manual"])
            else:
                import pandas as pd
                pd.DataFrame(columns=["uid","id","rarity","time","banner","type","manual"]).to_csv("data.csv", index=False, encoding="utf-8-sig")
        except Exception as e:
            print(f"❌ CSV 데이터 저장 실패: {str(e)}")

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
        """링크 상태를 UI에 표시 (조회 버튼 활성/비활성 등)"""
        # 예시: 링크가 있으면 버튼 활성화, 없으면 비활성화 등
        # 실제 구현에서는 self.fetch_all_btn.configure(state="normal"/"disabled") 등으로 제어
        self.fetch_all_btn.configure(state="normal")
        # 필요하다면 상태 라벨 등도 업데이트

    def _update_summary_display(self):
        """통합 통계 탭에 전체 요약 통계 표시"""
        total_count = 0
        total_5star = 0
        total_4star = 0
        total_3star = 0
        summary_lines = []
        for banner_id, banner in self.banner_data.items():
            stats = banner.get("stats", {})
            if not stats or not stats.get("total"):
                continue
            total = stats.get("total", 0)
            five = stats.get("5star", 0)
            four = stats.get("4star", 0)
            three = stats.get("3star", 0)
            total_count += total
            total_5star += five
            total_4star += four
            total_3star += three
            summary_lines.append(
                f"【{banner['name']}】\n"
                f"  총 {total:,}회 | 5성 {five}개 | 4성 {four}개 | 3성 {three}개\n"
            )
        if total_count > 0:
            rate_5 = (total_5star / total_count) * 100
            rate_4 = (total_4star / total_count) * 100
            rate_3 = (total_3star / total_count) * 100
            summary = (
                f"📈 전체 가챠 통계\n"
                f"총 {total_count:,}회\n"
                f"⭐ 5성: {total_5star}개 ({rate_5:.2f}%)\n"
                f"💜 4성: {total_4star}개 ({rate_4:.2f}%)\n"
                f"✨ 3성: {total_3star}개 ({rate_3:.2f}%)\n\n"
                + "\n".join(summary_lines)
            )
        else:
            summary = "아직 데이터가 없습니다.\n가챠를 조회해 주세요."
        self.summary_text.configure(state="normal")
        self.summary_text.delete("0.0", "end")
        self.summary_text.insert("0.0", summary)
        self.summary_text.configure(state="disabled")
        
    def unlock_120fps(self):
        """Star Rail FPS 제한을 120으로 언락 (레지스트리 수정)"""
        try:
            import winreg
            reg_path = r"Software\Cognosphere\Star Rail"
            value_name_prefix = "GraphicsSettings_Model_"
            # 하위 키에서 GraphicsSettings_Model_* 찾기
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_READ) as key:
                i = 0
                found_name = None
                while True:
                    try:
                        name, val, typ = winreg.EnumValue(key, i)
                        if name.startswith(value_name_prefix):
                            found_name = name
                            break
                        i += 1
                    except OSError:
                        break
            if not found_name:
                messagebox.showerror("120 FPS 언락 실패", "GraphicsSettings_Model_* 값을 찾을 수 없습니다.\n게임 내 그래픽 설정을 '커스텀'으로 변경 후 다시 시도하세요.")
                return
            # 값 읽기
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
                val, typ = winreg.QueryValueEx(key, found_name)
                if typ != winreg.REG_BINARY:
                    messagebox.showerror("120 FPS 언락 실패", "알 수 없는 레지스트리 값 형식입니다.")
                    return
                # 바이너리 → bytearray
                b = bytearray(val)
                # ASCII로 변환해서 "FPS":60 찾기
                s = b.decode("latin1")
                import re
                m = re.search(r'"FPS":(\d+)', s)
                if not m:
                    messagebox.showerror("120 FPS 언락 실패", '"FPS":60 값을 찾을 수 없습니다.')
                    return
                fps_val = m.group(1)
                if fps_val == "120":
                    messagebox.showinfo("120 FPS 언락", "이미 120 FPS로 설정되어 있습니다!")
                    return
                # 60 → 120 치환
                s_new = s.replace(f'"FPS":{fps_val}', '"FPS":120', 1)
                # 다시 바이너리로 변환
                b_new = s_new.encode("latin1")
                # 길이 맞추기 (PyInstaller 환경 호환)
                if len(b_new) < len(b):
                    b_new += b[len(b_new):]
                elif len(b_new) > len(b):
                    b_new = b_new[:len(b)]
                # 레지스트리 값 쓰기
                winreg.SetValueEx(key, found_name, 0, winreg.REG_BINARY, bytes(b_new))
            messagebox.showinfo("120 FPS 언락 완료", "성공적으로 120 FPS로 설정했습니다!\n게임을 재시작하세요.\n(설정 메뉴에는 30으로 보일 수 있으나 실제로는 120 FPS로 동작합니다.)")
        except Exception as e:
            messagebox.showerror("120 FPS 언락 실패", f"오류 발생: {e}")

        
if __name__ == "__main__":
    app = ModernGachaViewer()
    app.root.mainloop()