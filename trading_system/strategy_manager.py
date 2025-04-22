from utils.config_loader import load_strategy_config
from state import PortfolioState
import importlib
import queue
import threading 
import yaml 

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


    def update_strategy(self, stock: str, new_strategy_module: str):
        stock = stock.lower()

        if stock in self.command_queues:
            print(f"[Manager] Stopping current strategy for {stock.upper()}...")
            self.send_command(stock, "close_position")

            thread = self.threads[stock]
            thread.join(timeout=10)

        print(f"[Manager] Updating strategy for {stock.upper()} to {new_strategy_module}")
        self.stock_to_strategy[stock] = new_strategy_module

        self.persist_strategy_mapping()  #  persist to YAML

        self.start_strategy(stock)


    def persist_strategy_mapping(self, config_path="config/strategies.yaml"):
        try:
            with open(config_path, "w") as f:
                yaml.dump({"strategies": self.stock_to_strategy}, f, sort_keys=False)
            print("[Manager] Strategy mapping persisted to strategies.yaml")
        except Exception as e:
            print(f"[Manager] Failed to write strategies.yaml: {e}")
