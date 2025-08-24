from pyfiglet import Figlet
from trading_system.strategy_manager import StrategyManager
from trading_system.state import PortfolioState
from trading_system.utils.portfolio_manager import PortfolioManager  #  New import
from trading_system.backtest.portfolio_backtest import PortfolioBacktester
from datetime import datetime

import os 

def show_help():
    print("""
    Available Commands:

start
    ➔ Start all strategy threads based on strategies.yaml

buy <stock>
    ➔ Manually buy a stock (e.g., buy btc_usd)

sell <stock> <quantity>
    ➔ Manually sell a quantity of a stock (e.g., sell btc_usd 2)

close <stock>
    ➔ Close a running strategy thread (e.g., close btc_usd)

status
    ➔ Show current holdings, cash available, and portfolio value

pnl
    ➔ Show the realized PnL (profit and loss)

threads
    ➔ Show running strategy threads and the associated strategy

update_strategy <stock> <new_strategy_module>
    ➔ Change the strategy used for a stock at runtime (e.g., update_strategy btc_usd mean_reversion)

help
    ➔ Show this help message

clear 
    ➔ Clear the screen 

set_reinvest <stock> <ratio 0..1>
    ➔ Imposta la quota di profitto da reinvestire per uno stock (es. set_reinvest btc_usd 0.4)

weights
    ➔ Mostra valorizzazione corrente del portafoglio, pesi attuali vs target e PnL poo
          
exit
    ➔ Exit the trading system safely
""")

def print_banner():
    f = Figlet(font='slant', width=100)
    print(f.renderText('Auto-Trading System 1.0'))

def main():
    print_banner()

    # === Shared State ===
    state = PortfolioState()
    manager = StrategyManager(state)
    portfolio = PortfolioManager()  #  New: loads portfolio config and trader

    # === Bootstrap from broker state ===
    portfolio.bootstrap()

    while True:
        cmd = input("Command (help for more): ").strip().lower()

        if cmd == "start":
            manager.start_all(portfolio)

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

        elif cmd == "backtest":
            start = input("Start date ...: ").strip()
            end   = input("End date ...  : ").strip()
            tf_s  = input("Timeframe minutes ...: ").strip()
            def _to_iso(x): return x if ("T" in x or " " in x) else x + "T00:00:00Z"
            start_iso, end_iso = _to_iso(start), _to_iso(end)
            try: timeframe_minutes = int(tf_s)
            except: timeframe_minutes = 1

            # <<< QUI >>> broker disabilitato
            portfolio = PortfolioManager(broker_enabled=False)
            portfolio.bootstrap()

            manager = StrategyManager(PortfolioState())
            strategies_map = manager.stock_to_strategy

            backtester = PortfolioBacktester(
                portfolio=portfolio,
                strategies_map=strategies_map,
                timeframe_minutes=timeframe_minutes,
                start_iso=start_iso,
                end_iso=end_iso,
            )
            print("\n[Backtest] Starting ..."); backtester.run(); print("[Backtest] Completed.\n")

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

        elif cmd == "help":
            show_help()

        elif cmd == "threads":
            manager.show_running_threads()
        
        elif cmd == "clear":
            os.system('cls' if os.name == 'nt' else 'clear')
            print_banner()

        elif cmd == "exit":
            print(" Exiting Trading System.")
            break
        
        elif cmd.startswith("set_reinvest "):
            parts = cmd.split()
            if len(parts) != 3:
                print("Usage: set_reinvest <stock> <ratio 0..1>")
            else:
                stock, r = parts[1], parts[2]
                try:
                    ratio = float(r)
                    portfolio.set_reinvest_ratio(stock, ratio)
                    print(f"Reinvest ratio per {stock} impostato a {ratio:.2f}")
                except ValueError:
                    print("Ratio non valido. Usa un numero tra 0 e 1.")

        elif cmd == "weights":
            snap = portfolio.snapshot()
            rows = snap["rows"]
            tot = snap["totals"]
            print("\n Portfolio Snapshot (valori in $):")
            print(f"  Total Holdings : {tot['total_holdings']:.2f}")
            print(f"  Cash Allocated : {tot['total_cash_alloc']:.2f}")
            print(f"  TOTAL Value    : {tot['total_value']:.2f}")
            print(f"  PnL Pool (non reinvestita): {tot['realized_pnl_pool']:.2f}\n")

            for s, r in rows.items():
                print(f"- {r['symbol']}:")
                print(f"    Qty           : {r['quantity']}")
                print(f"    Last Price    : {r['last_price']:.4f}")
                print(f"    Holding Value : {r['holding_value']:.2f}")
                print(f"    Cash Alloc    : {r['cash_alloc']:.2f}")
                print(f"    Weight (exp)  : {r['weight_exposure']*100:.2f}%")
                print(f"    Weight (tot)  : {r['weight_total']*100:.2f}%")
                print(f"    Target Weight : {r['target_weight']*100:.2f}%")
                diff = r['weight_diff']*100
                sign = "+" if diff>=0 else "-"
                print(f"    Diff vs Target: {sign}{abs(diff):.2f}%")
            print()

        else:
            print("Unknown command. Try: start, status, buy [stock], close [stock], pnl, exit.")

if __name__ == "__main__":
    main()
