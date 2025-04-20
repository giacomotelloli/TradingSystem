import time
import random
from utils.trading_interface import AlpacaTradingInterface
from utils.stock_state_manager import StockStateManager

def strategy_main_loop(stock, state, command_queue):
    trader = AlpacaTradingInterface()
    stock_state = StockStateManager()

    # 1. Read existing state
    current_state = stock_state.get_state(stock)
    print(f"[{stock.upper()}] Resuming with state: {current_state}")


    pnl = 0
    position_open = True
    print(f"[{stock}] Position opened: Buying stock...")

    while True:
        if not command_queue.empty():
            command = command_queue.get()
            if command == "close_position":
                print(f"[{stock}] Received command to close position.")
                position_open = False
                break

        time.sleep(60)
        # BLOCCO DI CODICE DELLA STRATEGIA 
        # UPDATE DEI DATI BASATI SUI PREZZI
        # ESECUZIONE DELLA DECISIONE DELLA STRATEGIA
        # (si interfaccia attraverso l'oggetto trader)


        pnl += random.uniform(-5, 5)
        print(f"[{stock}] Trading... Current PnL: {pnl:.2f}")

    if position_open:
        print(f"[{stock}] Closing position after completion.")
    else:
        print(f"[{stock}] Position closed manually.")

    return pnl
