from pyfiglet import Figlet
from strategy_manager import StrategyManager
from state import PortfolioState
from utils.stock_state_manager import StockStateManager
def main():
    f = Figlet(font='small slant')  # You can also try 'big', 'banner', 'doom', etc.
    print(f.renderText('Trading System v0.0'))

    state = PortfolioState()
    manager = StrategyManager(state)
    stock_state = StockStateManager()

    while True:
        cmd = input("Command (start/status/pnl/close <strategy>/exit): ").strip().lower()

        if cmd == "start":
            manager.start_all()
        elif cmd == "status":
            holdings = stock_state.get_all_states()
            print("\n Current Holdings:")
            for stock, data in holdings.items():
                qty = data.get("quantity", 0)
                invested = data.get("money_invested", 0.0)
                realized = data.get("realized_pnl", 0.0)
                avg_price = (invested / qty) if qty else 0.0

                print(f"- {stock.upper()}:")
                print(f"    Quantity Owned   : {qty}")
                print(f"    Money Invested   : ${invested:.2f}")
                print(f"    Avg Buy Price    : ${avg_price:.2f}")
                print(f"    Realized PnL     : ${realized:.2f}")
            print()
        elif cmd == "pnl":
            print("PnL:", state.get_pnl())
        elif cmd.startswith("close "):
            strategy_name = cmd.split(" ", 1)[1]
            manager.send_command(strategy_name, "close_position")
        elif cmd == "exit":
            print("Exiting.")
            break
        else:
            print("Unknown command.")

if __name__ == "__main__":
    main()
