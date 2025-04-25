from pyfiglet import Figlet
from trading_system.strategy_manager import StrategyManager
from trading_system.state import PortfolioState
from trading_system.utils.portfolio_manager import PortfolioManager  #  New import

def main():
    f = Figlet(font='slant',width=100)
    print(f.renderText('Trading System 1.0'))

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
            account = portfolio.trader.get_account()
            cash = float(account.cash) if account else 0.0

            print("\n Portfolio Status:")
            print(f"Available Cash: ${cash:,.2f}\n")
            
            market_value = 0.0
            
            for stock, data in holdings.items():
                qty = data.get("quantity", 0)
                invested = data.get("money_invested", 0.0)
                realized = data.get("realized_pnl", 0.0)
                avg_price = (invested / qty) if qty else 0.0

                current_price = portfolio.trader.get_last_price(stock)
                stock_value = qty * current_price if current_price else 0.0
                market_value += stock_value

                print(f"\n- {stock.upper()}:")
                print(f"    Quantity Owned     : {qty}")
                print(f"    Avg Buy Price      : ${avg_price:.2f}")
                print(f"    Current Price      : ${current_price:.2f}" if current_price else "    Current Price      : N/A")
                print(f"    Market Value       : ${stock_value:.2f}")
                print(f"    Money Invested     : ${invested:.2f}")
                print(f"    Realized PnL       : ${realized:.2f}")

            total_value = cash + market_value
            print(f"\n Market Value of Holdings : ${market_value:,.2f}")
            print(f" Total Portfolio Value     : ${total_value:,.2f}")

        elif cmd == "pnl":
            print(" Strategy PnL:", state.get_pnl())

        elif cmd.startswith("close "):
            stock = cmd.split(" ", 1)[1].strip()
            manager.send_command(stock, "close_position")

        elif cmd.startswith("sell "):
            parts = cmd.split(" ")
            if len(parts) != 3:
                print("Usage: sell <stock> <quantity>")
            else:
                stock = parts[1]
                try:
                    qty = int(parts[2])
                    if qty <= 0:
                        raise ValueError()
                    portfolio.sell_stock(stock, qty)
                except ValueError:
                    print("Quantity must be a positive integer.")

        elif cmd.startswith("update_strategy "):
            parts = cmd.split()
            if len(parts) != 3:
                print("Usage: update_strategy <stock> <new_strategy_module>")
            else:
                stock = parts[1]
                new_strategy = parts[2]
                manager.update_strategy(stock, new_strategy)

        elif cmd == "exit":
            print(" Exiting Trading System.")
            break

        else:
            print("Unknown command. Try: start, status, buy [stock], close [stock], pnl, exit.")

if __name__ == "__main__":
    main()
