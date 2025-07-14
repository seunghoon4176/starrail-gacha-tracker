from introspectors.GameIntrospector import GameIntrospector


class HsrGameIntrospector(GameIntrospector):
    """
    Introspects the gacha records of the game Honkai: Star Rail
    """
    def sniff_data(self):
        """게임 데이터를 추출하는 메서드 (구현 필수)"""
        pass