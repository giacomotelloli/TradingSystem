import threading

class PortfolioState:
    def __init__(self):
        self.lock = threading.Lock()
        self.threads_status = {}
        self.realized_pnl = {}

    def update_status(self, strategy_name, status):
        with self.lock:
            self.threads_status[strategy_name] = status

    def update_pnl(self, strategy_name, pnl):
        with self.lock:
            self.realized_pnl[strategy_name] = pnl

    def get_status(self):
        with self.lock:
            return self.threads_status.copy()

    def get_pnl(self):
        with self.lock:
            return self.realized_pnl.copy()
