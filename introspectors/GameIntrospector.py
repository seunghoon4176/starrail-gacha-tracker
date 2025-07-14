from abc import ABC, abstractmethod

class GameIntrospector(ABC):
    def sniff_data(self):
        """게임 데이터를 추출하는 메서드 (구현 필수)"""
        pass