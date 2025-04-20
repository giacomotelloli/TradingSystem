from utils.config_loader import load_strategy_config
from state import PortfolioState
import importlib
import queue
import threading 

class StrategyManager:
    def __init__(self, state: PortfolioState):
        self.state = state
        self.threads = {}
        self.command_queues = {}
        self.stock_to_strategy = load_strategy_config()

    def start_strategy(self, stock):
        if stock not in self.stock_to_strategy:
            print(f"[Manager] No strategy configured for stock '{stock}'")
            return

        strategy_module = self.stock_to_strategy[stock]
        try:
            module = importlib.import_module(f"strategies.{strategy_module}")
            strategy_func = getattr(module, "strategy_main_loop")
        except (ModuleNotFoundError, AttributeError) as e:
            print(f"[Manager] Error loading strategy '{strategy_module}': {e}")
            return

        cmd_queue = queue.Queue()
        self.command_queues[stock] = cmd_queue

        def wrapper():
            self.state.update_status(stock, "running")
            pnl = strategy_func(stock, self.state, cmd_queue)
            self.state.update_pnl(stock, pnl)
            self.state.update_status(stock, "completed")

        thread = threading.Thread(target=wrapper, name=stock)
        self.threads[stock] = thread
        thread.start()

    def start_all(self):
        for stock in self.stock_to_strategy:
            self.start_strategy(stock)

    def send_command(self, stock, command):
        if stock in self.command_queues:
            self.command_queues[stock].put(command)
        else:
            print(f"[Manager] No active strategy thread for stock '{stock}'")
