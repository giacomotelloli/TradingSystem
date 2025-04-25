import yaml
from .stock_state_manager import StockStateManager
from .interface_factory import get_trading_interface

class PortfolioManager:
    def __init__(self, config_path="config/portfolio.yaml"):
        self.trader = get_trading_interface()
        self.stock_state = StockStateManager()
        self._load_config(config_path)

    def _load_config(self, path):
        with open(path, 'r') as f:
            config = yaml.safe_load(f)
        self.initial_budget = config.get("initial_budget", 0)
        self.allocations = config.get("allocations", {})

    def bootstrap(self):
        print("[Portfolio] Bootstrapping portfolio from broker...")
        
        for stock in self.allocations:
            stock_name = stock.upper().replace("_", "/")
            state = self.stock_state.get_state(stock)
            if state["quantity"] > 0:
                print(f"  [✓] {stock_name} already has {state['quantity']} shares.")
            else:
                print(f"  [ ] {stock_name} has no position.")

    def buy_stock(self, stock):
        stock = stock.lower().replace("/", "_")
        if stock not in self.allocations:
            print(f"[Portfolio] {stock} not found in allocation config.")
            return

        allocation_pct = self.allocations[stock]
        budget = self.initial_budget * allocation_pct
        price = self.trader.get_last_price(stock)
        stock_name = stock.upper().replace("_", "/")
        if not price:
            print(f"[Portfolio] Failed to fetch price for {stock_name}")
            return

        qty = int(budget // price)
        if qty == 0:
            print(f"[Portfolio] Not enough budget to buy any shares of {stock_name}")
            return

        total_cost = qty * price
        self.trader.buy(stock, qty)
        self.stock_state.update_on_buy(stock, qty, total_cost)

        print(f"[Portfolio] Bought {qty} shares of {stock_name} at ${price:.2f} each. Total: ${total_cost:.2f}")


    def sell_stock(self, stock, qty):
        stock = stock.lower().replace("/", "_")
        current_state = self.stock_state.get_state(stock)
        current_qty = current_state.get("quantity", 0)
        stock_name = stock.upper().replace("_", "/")
        if qty > current_qty:
            print(f"[Portfolio] Cannot sell {qty} shares of {stock_name}. You only own {current_qty}.")
            return

        price = self.trader.get_last_price(stock)
        if not price:
            print(f"[Portfolio] Failed to fetch price for {stock_name}")
            return

        total_return = qty * price
        self.trader.sell(stock, qty)
        self.stock_state.update_on_sell(stock, qty, total_return)

        print(f"[Portfolio] Sold {qty} shares of {stock_name} at ${price:.2f} each. Total: ${total_return:.2f}")
