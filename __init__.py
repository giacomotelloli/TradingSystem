"""
TradingSystem - A modular trading framework for broker integration.

Author: Giacomo Telloli 
License: GNU
"""

__version__ = "0.1.0"

# Expose key components
from .trading_system.strategy_manager import StrategyManager
from .trading_system.state import PortfolioState
from .trading_system.utils.stock_state_manager import StockStateManager
from .trading_system.utils.interface_factory import get_trading_interface
