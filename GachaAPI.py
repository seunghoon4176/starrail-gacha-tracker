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

class GachaAPI:
    """가챠 API 직접 호출 클래스 - 실제 API 구조에 맞게 수정"""
    
    # GitHub 코드의 엔드포인트 상수들 참고
    END_DEFAULT = "getGachaLog"
    END_COLLABORATION = "getLdGachaLog"
    
    # Rust 코드에서 확인된 콜라보 배너 타입들
    COLLABORATION_TYPES = {"21", "22"}  # 실제 콜라보 배너 타입
    
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
        """가챠 타입에 따라 URL 엔드포인트 결정 - 콜라보 배너는 특별 엔드포인트 사용 가능"""
        # 콜라보 배너는 특별한 엔드포인트를 사용할 수 있음
        if gacha_type in self.COLLABORATION_TYPES:
            # 먼저 콜라보 엔드포인트 시도, 실패하면 기본 엔드포인트 사용
            return self.base_url.replace(self.END_DEFAULT, self.END_COLLABORATION)
        else:
            # 일반 배너는 기본 엔드포인트 사용
            return self.base_url.replace(self.END_COLLABORATION, self.END_DEFAULT)
    
    async def fetch_gacha_records(self, gacha_type: str, lang: str = "ko") -> List[Dict[str, Any]]:
        """특정 배너의 가챠 기록을 모두 가져오기 - 콜라보 배너 지원"""
        all_records = []
        page = 1
        end_id = "0"
        
        # 가챠 타입에 맞는 URL 선택
        request_url = self._build_url_for_gacha_type(gacha_type)
        
        async with aiohttp.ClientSession() as session:
            # 콜라보 배너의 경우 두 가지 엔드포인트 모두 시도
            urls_to_try = [request_url]
            if gacha_type in self.COLLABORATION_TYPES:
                # 기본 엔드포인트도 추가로 시도
                fallback_url = self.base_url.replace(self.END_COLLABORATION, self.END_DEFAULT)
                if fallback_url != request_url:
                    urls_to_try.append(fallback_url)
            
            for url_to_try in urls_to_try:
                page = 1
                end_id = "0"
                all_records = []
                
                print(f"🔗 URL 시도: {url_to_try.split('/')[-1]} (gacha_type={gacha_type})")
                
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
                        async with session.get(url_to_try, params=params, timeout=30) as response:
                            if response.status != 200:
                                print(f"HTTP 오류: {response.status}")
                                break
                                
                            data = await response.json()
                            
                            if data.get("retcode") != 0:
                                print(f"API 오류: retcode={data.get('retcode')}, message={data.get('message', 'Unknown error')}")
                                break
                        
                            records = data.get("data", {}).get("list", [])
                            if not records:
                                print(f"더 이상 데이터 없음 - 총 {len(all_records)}개 기록")
                                break
                        
                            all_records.extend(records)
                        
                            # 다음 페이지 준비
                            end_id = records[-1].get("id", "0")
                            page += 1
                        
                            print(f"배너 {gacha_type} - 페이지 {page-1}: {len(records)}개 기록 (누적: {len(all_records)}개)")
                        
                            # API 호출 간격 (과부하 방지)
                            await asyncio.sleep(0.5)
                        
                    except asyncio.TimeoutError:
                        print(f"타임아웃 발생 - 페이지 {page}")
                        break
                    except Exception as e:
                        print(f"요청 오류 - 페이지 {page}: {e}")
                        break
                
                # 데이터를 성공적으로 가져왔으면 중단
                if all_records:
                    print(f"✅ {url_to_try.split('/')[-1]}에서 성공: {len(all_records)}개 기록")
                    break
                else:
                    print(f"❌ {url_to_try.split('/')[-1]}에서 실패")
        
        return all_records
    
    async def validate_link(self) -> bool:
        """가챠 링크 유효성 검증 - 더 관대한 검증"""
        try:
            async with aiohttp.ClientSession() as session:
                # 일반 배너로 테스트 - 기존 URL 파라미터 그대로 사용
                params = self.base_params.copy()
                params.update({
                    "gacha_type": "1",
                    "page": "1",
                    "size": "5",
                    "end_id": "0"
                    # lang 파라미터는 기존 것 유지
                })
                
                # 기본 URL 사용 (엔드포인트 변경 없이)
                async with session.get(self.base_url, params=params, timeout=15) as response:
                    print(f"검증 응답 상태: {response.status}")
                    
                    if response.status != 200:
                        return False
                    
                    data = await response.json()
                    print(f"API 응답: retcode={data.get('retcode')}, message={data.get('message', 'N/A')}")
                    
                    # retcode가 0이면 성공, -101은 인증키 만료, -111은 파라미터 오류
                    return data.get("retcode") == 0
                    
        except Exception as e:
            print(f"링크 검증 실패: {e}")
            return False