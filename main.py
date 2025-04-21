from pyfiglet import Figlet
from trading_system.strategy_manager import StrategyManager
from trading_system.state import PortfolioState
from trading_system.utils.portfolio_manager import PortfolioManager  #  New import

def main():
    f = Figlet(font='small slant')
    print(f.renderText('Trading System v0.0'))

    # === Shared State ===
    state = PortfolioState()
    manager = StrategyManager(state)
    portfolio = PortfolioManager()  #  New: loads portfolio config and trader

    # === Bootstrap from broker state ===
    portfolio.bootstrap()

    while True:
        cmd = input("Command (start/status/pnl/buy [stock]/close [stock]/exit): ").strip().lower()

        if cmd == "start":
            manager.start_all()

        elif cmd.startswith("buy "):
            stock = cmd.split(" ", 1)[1].strip()
            portfolio.buy_stock(stock)

        elif cmd == "status":
            holdings = portfolio.stock_state.get_all_states()
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
            print(" Strategy PnL:", state.get_pnl())

        elif cmd.startswith("close "):
            stock = cmd.split(" ", 1)[1].strip()
            manager.send_command(stock, "close_position")

        elif cmd == "exit":
            print(" Exiting Trading System.")
            break

        else:
            print("Unknown command. Try: start, status, buy [stock], close [stock], pnl, exit.")

if __name__ == "__main__":
    main()
