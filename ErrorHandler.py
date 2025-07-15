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