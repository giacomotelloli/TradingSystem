import yaml
import threading
import queue
import importlib
from .utils.interface_factory import get_trading_interface
from .utils.stock_state_manager import StockStateManager
from .strategies.strategy_runner import StrategyRunner
from trading_system.utils.portfolio_manager import PortfolioManager

class StrategyManager:
    def __init__(self, state, config_path="config/strategies.yaml"):
        self.state = state
        self.config_path = config_path
        self.stock_to_strategy = self._load_strategies(config_path)
        self.command_queues = {}
        self.threads = {}
        self.trader = get_trading_interface()
        self.stock_state = StockStateManager()

    def _load_strategies(self, path):
        with open(path, 'r') as f:
            config = yaml.safe_load(f)
        return config.get('strategies', {})

    def start_all(self,portfolio:PortfolioManager):
        for stock, strategy_module in self.stock_to_strategy.items():
            initial_stock_buget = portfolio.allocations[stock]*portfolio.initial_budget
            self.start_strategy(stock,initial_stock_buget)

    def start_strategy(self, stock,initial_capital):
        stock = stock.lower().replace("/", "_")
        strategy_module_name = self.stock_to_strategy.get(stock)
        
        try:
            strategy_module = importlib.import_module(f"trading_system.strategies.{strategy_module_name}")
            strategy_class = getattr(strategy_module, "Strategy")
        except Exception as e:
            print(f"[Manager] Failed to load strategy {strategy_module_name} for {stock}: {e}")
            return

        cmd_queue = queue.Queue()

        runner = StrategyRunner(
            stock=stock,
            strategy_cls=strategy_class,
            strategy_initial_capital=initial_capital,
            trader=self.trader,
            stock_state=self.stock_state,
            command_queue=cmd_queue,
            state=self.state,
            frequency=3600
        )

        thread = threading.Thread(target=runner.run, daemon=True)
        thread.start()

        self.command_queues[stock] = cmd_queue
        self.threads[stock] = thread

        print(f"[Manager] Started strategy thread for {stock.upper()}")


    def show_running_threads(self):
        print("\n Active Strategy Threads:")

        for stock, thread in self.threads.items():
            strategy_module = self.stock_to_strategy.get(stock, "Unknown")
            is_alive = "Yes" if thread.is_alive() else "No"
            real_stock = stock.upper().replace("_", "/")

            print(f"- {real_stock}: Strategy = {strategy_module}, Running = {is_alive}")
        print()
