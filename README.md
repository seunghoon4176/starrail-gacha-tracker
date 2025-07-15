# Honkai: Star Rail 가챠 기록 조회기

Honkai: Star Rail의 가챠 기록을 게임에 접속하지 않고도 조회할 수 있는 GUI 애플리케이션입니다.

## 📋 기능

- 🎯 **가챠 기록 조회**: 게임 내 가챠 기록을 실시간으로 불러오기
- 📊 **통계 분석**: 5성/4성 확률, 보장 카운트 등 자동 계산
- 💾 **결과 저장**: 조회한 기록을 텍스트 파일로 저장
- 🌐 **다국어 지원**: 한국어, 영어, 일본어, 중국어 지원
- 🎨 **직관적 UI**: 사용하기 쉬운 그래픽 인터페이스

## 🚀 빠른 시작

### 실행 파일 사용 (권장)
1. [Releases]([https://github.com/your-repo/releases](https://github.com/seunghoon4176/starrail-gacha-tracker/releases))에서 `StarRail_Gacha_Viewer.exe` 다운로드
2. 실행 파일을 더블클릭하여 실행

### Python으로 직접 실행
```bash
# 필요한 패키지 설치
pip install honkaistarrail tkinter pyinstaller

# 프로그램 실행
python gacha_viewer.py
```

## 📖 사용 방법

### 1. 가챠 기록 링크 획득
1. Honkai: Star Rail 게임 실행
2. 게임 내에서 워프(가챠) 기록 화면 열기
3. 브라우저에서 개발자 도구 열기 (F12)
4. Network 탭에서 `gacha` 관련 요청 찾기
5. 해당 요청의 URL 복사

### 2. 애플리케이션 사용
1. 프로그램 실행
2. 가챠 기록 URL 입력
3. 배너 타입 선택 (이벤트/광추/상시)
4. 언어 선택
5. "가챠 기록 조회" 버튼 클릭
6. 결과 확인 및 필요시 저장

## 🎯 배너 타입
- **이벤트 배너 (1)**: 캐릭터 가챠
- **광추 배너 (2)**: 라이트콘 가챠  
- **상시 배너 (3)**: 상시 가챠

## 📊 통계 정보
- 총 가챠 횟수
- 등급별 개수 및 확률
- 마지막 5성 이후 카운트
- 보장까지 남은 횟수

## 🔧 개발자 정보

### 빌드 방법
```bash
# exe 파일 빌드
python build.py

# spec 파일 생성 (고급 설정)
python build.py --spec
```

### 의존성
- `honkaistarrail`: API 통신
- `tkinter`: GUI 인터페이스
- `asyncio`: 비동기 처리
- `pyinstaller`: exe 빌드

## ⚠️ 주의사항
- 가챠 기록 링크는 일정 시간 후 만료됩니다
- 게임 계정 정보는 저장되지 않습니다
- miHoYo/HoYoverse의 API 정책 변경에 따라 작동하지 않을 수 있습니다

## 📝 라이선스
MIT License

## 🤝 기여하기
버그 리포트나 기능 제안은 Issues에 올려주세요.

---
Made with ❤️ for Honkai: Star Rail players

