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

#자체 모듈
from GachaLinkFinder import GachaLinkFinder
from GachaAPI import GachaAPI
from GachaLinkFinder import get_gacha_link_from_registry, get_gacha_link_from_logs
from ErrorHandler import ErrorHandler
from CacheFileManager import get_gacha_link_from_game_cache

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
        self.current_theme = "dark"  # 현재 테마 추적
        
        # 데이터 파일 초기화
        self.data_file = "gacha_records.json"
        
        # 설정 로드
        self.load_settings()
        
        # 아래 함수가 없으면 임시로 주석 처리하거나, 아래와 같이 간단히 추가하세요.
        self.load_existing_data()
        
        # 초기 링크 상태 확인
        self.update_link_status()
        
    def setup_ui(self):
        # 메인 컨테이너
        self.main_container = ctk.CTkFrame(self.root)
        self.main_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 간단한 컨트롤 패널
        self.create_simple_control_panel()
        
        # 탭뷰
        self.create_tabview()
        
        # 설정 창 초기화
        self.settings_window = None
        
    def create_simple_control_panel(self):
        """간단한 컨트롤 패널 생성"""
        control_frame = ctk.CTkFrame(self.main_container)
        control_frame.pack(fill="x", padx=10, pady=(10, 0))

        # 한 줄에: 모든 배너 조회, 설정, 프로그레스 바
        row_frame = ctk.CTkFrame(control_frame)
        row_frame.pack(fill="x", padx=15, pady=10)

        # 조회 버튼 (왼쪽)
        self.fetch_all_btn = ctk.CTkButton(
            row_frame,
            text="🎯 모든 배너 조회",
            command=self.fetch_all_banners,
            width=180,
            height=40,
            font=ctk.CTkFont(size=16, weight="bold"),
            state="normal"
        )
        self.fetch_all_btn.pack(side="left", padx=(0, 10))

        # 설정 버튼 (중간)
        settings_btn = ctk.CTkButton(
            row_frame,
            text="⚙️ 설정",
            command=self.open_settings,
            width=100,
            height=35,
            fg_color="gray50",
            hover_color="gray40"
        )
        settings_btn.pack(side="left", padx=(0, 10))

        # 프로그레스 바 (오른쪽, 남은 공간 모두 차지)
        self.progress_bar = ctk.CTkProgressBar(row_frame, height=16)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.progress_bar.set(0)

        # 상태 라벨 (맨 오른쪽)
        self.status_label = ctk.CTkLabel(
            row_frame,
            text="📝 대기 중...",
            font=ctk.CTkFont(size=12),
            width=200
        )
        self.status_label.pack(side="left")

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

        # 기록 텍스트 (상단)
        records_text = ctk.CTkTextbox(
            records_frame, 
            height=450,
            font=ctk.CTkFont(size=13)
        )
        records_text.pack(fill="both", expand=True, padx=15, pady=(0, 5))
        records_text.configure(state="disabled")  # 사용자 입력 방지

        # 페이지네이션 컨트롤 프레임 (맨 아래, 가운데 정렬)
        pagination_frame = ctk.CTkFrame(records_frame)
        pagination_frame.pack(fill="x", padx=15, pady=(0, 10), side="bottom")
        pagination_frame.grid_columnconfigure(0, weight=1)
        pagination_frame.grid_columnconfigure(1, weight=0)
        pagination_frame.grid_columnconfigure(2, weight=1)

        prev_btn = ctk.CTkButton(
            pagination_frame,
            text="⬅ 이전",
            width=80,
            command=lambda bid=banner_id: self.change_page(bid, -1)
        )
        prev_btn.grid(row=0, column=0, sticky="e", padx=(0, 10))

        page_label = ctk.CTkLabel(
            pagination_frame,
            text="1 / 1",
            width=80
        )
        page_label.grid(row=0, column=1, sticky="nsew")

        next_btn = ctk.CTkButton(
            pagination_frame,
            text="다음 ➡",
            width=80,
            command=lambda bid=banner_id: self.change_page(bid, 1)
        )
        next_btn.grid(row=0, column=2, sticky="w", padx=(10, 0))

        # 탭 정보 저장
        self.banner_tabs[banner_id] = {
            "tab": tab,
            "stats_text": stats_text,
            "records_text": records_text,
            "prev_btn": prev_btn,
            "next_btn": next_btn,
            "page_label": page_label
        }
        self.banner_pagination[banner_id] = {"page": 1, "total_pages": 1}

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
        
        # 콜라보 배너 포함 전체 배너 타입 매핑
        banner_type_map = {
            "11": "11", # CHARACTER = '11' - 한정 캐릭터 배너 (실제 데이터 확인됨)
            "12": "12", # LIGHT_CONE = '12' - 한정 광추 배너 
            "21": "21", # 콜라보 캐릭터 배너 (Rust 코드에서 확인됨)
            "22": "22", # 콜라보 광추 배너 (Rust 코드에서 확인됨)
            "1": "1",   # STELLAR = '1' - 상시 배너 (실제 데이터 확인됨)
            "2": "2"    # DEPARTURE = '2' - 초보자 배너
        }
        
        gacha_type = banner_type_map.get(banner_id, banner_id)
        print(f"🔍 배너 {banner_id} ({self.banner_data[banner_id]['name']}) -> gacha_type {gacha_type} 조회 시작")
        
        # 모든 배너에 대해 강제로 조회 시도
        records = await api.fetch_gacha_records(gacha_type, api_lang)
        print(f"📊 배너 {banner_id}: {len(records)}개 기록 조회됨")
        
        # API 응답 상세 정보 출력
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

            # 시각적 이모지 개선
            fire_icons = "🟨" * min(int(five_star), 10) if five_star else "⬜"
            purple_icons = "🟪" * min(int(four_star) // 10, 10) if four_star else "⬜"
            white_icons = "⬜" * min(int(three_star) // 100, 10) if three_star else "⬜"
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
        items_per_page = 15
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
                    item_name = getattr(item, 'name', 'Unknown')
                    item_time = getattr(item, 'time', '')

                    if str(item_rank) == "5":
                        rank_display = "⭐⭐⭐⭐⭐"
                        prefix = "🌟"
                        name_style = f"【{item_name}】"
                        border = "╔" + "═" * 30 + "╗"
                        records_text += f"{border}\n"
                    elif str(item_rank) == "4":
                        rank_display = "⭐⭐⭐⭐"
                        prefix = "💜"
                        name_style = f"『{item_name}』"
                    else:
                        rank_display = "⭐⭐⭐"
                        prefix = "🔹"
                        name_style = item_name

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

                    # 시간 포맷팅
                    try:
                        from datetime import datetime
                        time_obj = datetime.strptime(item_time, "%Y-%m-%d %H:%M:%S")
                        time_display = time_obj.strftime("%m/%d %H:%M")
                    except:
                        time_display = str(item_time)[:16] if item_time else "알 수 없음"

                    records_text += f"{i+1:2d}. {prefix} {rank_display} {name_style}{interval_info}\n"
                    records_text += f"     📅 {time_display}\n"

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

        # 페이지네이션 컨트롤 업데이트
        tab_info["page_label"].configure(text=f"{current_page} / {total_pages}")
        tab_info["prev_btn"].configure(state="normal" if current_page > 1 else "disabled")
        tab_info["next_btn"].configure(state="normal" if current_page < total_pages else "disabled")

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

        # 가챠 링크 획득 안내만 표시 (파워쉘 관련 버튼/설명 제거)
        method_frame = ctk.CTkFrame(scrollable_frame)
        method_frame.pack(fill="x", padx=10, pady=10)

        method_label = ctk.CTkLabel(method_frame, text="가챠 링크 획득 방법:", font=ctk.CTkFont(size=16, weight="bold"))
        method_label.pack(anchor="w", padx=15, pady=(15, 5))

        method_info_frame = ctk.CTkFrame(method_frame)
        method_info_frame.pack(fill="x", padx=15, pady=(0, 15))

        info_label = ctk.CTkLabel(
            method_info_frame,
            text="🔍 다음 순서로 자동 검색합니다:\n1. Windows 레지스트리\n2. 게임 로그 파일\n3. 게임 웹 캐시",
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

    def load_existing_data(self):
        """기존 데이터 파일 로드"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, "r", encoding="utf-8") as f:
                    saved_data = json.load(f)
                # 저장된 데이터를 배너별로 복원
                for banner_id in self.banner_data.keys():
                    if banner_id in saved_data:
                        raw_data = saved_data[banner_id]["data"]
                        converted_data = []
                        for item_dict in raw_data:
                            item_obj = type('GachaItem', (), {})()
                            item_obj.name = item_dict.get("name", "")
                            item_obj.rank = item_dict.get("rank", 3)
                            item_obj.time = item_dict.get("time", "")
                            item_obj.type = item_dict.get("type", "")
                            converted_data.append(item_obj)
                        self.banner_data[banner_id]["data"] = converted_data
                        self._calculate_banner_stats(banner_id)
                # UI 업데이트
                for banner_id in self.banner_data.keys():
                    if self.banner_data[banner_id]["data"]:
                        self._update_banner_display(banner_id)
                self._update_summary_display()
            else:
                self.save_data_to_file()
        except Exception as e:
            print(f"❌ 데이터 로드 실패: {str(e)}")
            self.save_data_to_file()

    def save_data_to_file(self):
        """현재 데이터를 파일에 저장"""
        try:
            save_data = {}
            for banner_id, banner_info in self.banner_data.items():
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
        except Exception as e:
            print(f"❌ 데이터 저장 실패: {str(e)}")

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
        
if __name__ == "__main__":
    app = ModernGachaViewer()
    app.root.mainloop()