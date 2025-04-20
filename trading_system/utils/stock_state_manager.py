import yaml
import threading
import os

STATE_FILE = "data/stock_state.yaml"

class StockStateManager:
    """
        Class that manages to save the state of the transactions 
        and keep track of it 
    """


    def __init__(self):
        self.lock = threading.Lock()
        self.state = self._load_state()

    def _load_state(self):
        if not os.path.exists(STATE_FILE):
            return {}
        with open(STATE_FILE, 'r') as f:
            return yaml.safe_load(f) or {}

    def _save_state(self):
        with open(STATE_FILE, 'w') as f:
            yaml.dump(self.state, f)

    def update_on_buy(self, stock, qty, total_cost):
        with self.lock:
            s = self.state.get(stock, {"money_invested": 0.0, "quantity": 0})
            s["money_invested"] += total_cost
            s["quantity"] += qty
            self.state[stock] = s
            self._save_state()

    def update_on_sell(self, stock, qty, total_return):
        with self.lock:
            s = self.state.get(stock, {"money_invested": 0.0, "quantity": 0})
            if qty > s["quantity"]:
                print(f"[Warning] Selling more than owned for {stock}")
            avg_cost_per_share = s["money_invested"] / s["quantity"] if s["quantity"] > 0 else 0
            s["money_invested"] -= avg_cost_per_share * qty
            s["quantity"] -= qty
            self.state[stock] = s
            self._save_state()

    def get_state(self, stock):
        with self.lock:
            return self.state.get(stock, {"money_invested": 0.0, "quantity": 0})

    def get_all_states(self):
        with self.lock:
            return self.state.copy()

    def update_on_buy(self, stock, qty, total_cost):
        with self.lock:
            s = self.state.get(stock, {"money_invested": 0.0, "quantity": 0, "realized_pnl": 0.0})
            s["money_invested"] += total_cost
            s["quantity"] += qty
            self.state[stock] = s
            self._save_state()

    def update_on_sell(self, stock, qty, total_return):
        with self.lock:
            s = self.state.get(stock, {"money_invested": 0.0, "quantity": 0, "realized_pnl": 0.0})
            if qty > s["quantity"]:
                print(f"[Warning] Selling more than owned for {stock}")

            avg_cost = s["money_invested"] / s["quantity"] if s["quantity"] > 0 else 0
            cost_basis = avg_cost * qty
            realized_pnl = total_return - cost_basis

            s["money_invested"] -= cost_basis
            s["quantity"] -= qty
            s["realized_pnl"] += realized_pnl

            self.state[stock] = s
            self._save_state()
