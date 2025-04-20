from abc import ABC, abstractmethod

class TradingInterface(ABC):
    @abstractmethod
    def buy(self, symbol: str, qty: int): pass

    @abstractmethod
    def sell(self, symbol: str, qty: int): pass

    @abstractmethod
    def get_position(self, symbol: str): pass

    @abstractmethod
    def get_last_price(self, symbol: str): pass

    @abstractmethod
    def get_account(self): pass
