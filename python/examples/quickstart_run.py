#!/usr/bin/env python3
"""End-to-end quickstart: load a CSV, run a backtest, print the summary.

Run from the python/ directory, with the package installed
(pip install reamer-research):

    python3 examples/quickstart_run.py

This is the shortest complete path from a CSV file to a result. It uses only
sample_data/SAMPLE_5min.csv (synthetic bars that fit inside Evaluation Mode),
the reamer_research package, and templates/engine_config.json.

templates/engine_config.json models commission, slippage and spread with
illustrative non-zero defaults, so this run is a costed fill rather than a
frictionless one. They are not your venue's numbers -- EXECUTION_SPEC.md
defines every field, and §1 covers why slippage is not floored at zero
(price improvement is by design, and aggregate slippage cost can be
negative). Because price_volatility is non-zero, the run also exercises the
stochastic slippage/spread path: rerun it and the output is byte-identical
for the fixed rng_seed.
"""
import csv
import datetime
import json
import os


from reamer_research import buy_market
from reamer_research import run_backtest

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, '..', 'sample_data', 'SAMPLE_5min.csv')
CONFIG_PATH = os.path.join(HERE, '..', 'templates', 'engine_config.json')

TICKER = 'SAMPLE'


def load_bars(path):
    """Read an OHLCV CSV into the bar tuples run_backtest() expects.

    Each bar is (ts, open, high, low, close, volume, notional, tick_count).
    ts is an integer epoch. notional 0.0 and tick_count -1 mean "not supplied":
    the engine derives its intrabar tick count from the gap to the next bar.
    """
    bars = []
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            stamp = datetime.datetime.strptime(
                f"{row['Date']} {row['Time']}", '%Y-%m-%d %H:%M:%S'
            ).replace(tzinfo=datetime.timezone.utc)
            bars.append((
                int(stamp.timestamp()),
                float(row['Open']),
                float(row['High']),
                float(row['Low']),
                float(row['Close']),
                float(row['Volume']),
                0.0,
                -1,
            ))
    return bars


class BuyAndHold:
    """Buy one unit on the first valid bar, then hold to the end of the data."""

    lookback = 1
    ticker = TICKER

    def __init__(self, config_path=None):
        self.bought = False

    def on_bar(self, data):
        tv = data[self.ticker]
        if self.bought or not tv.valid:
            return None
        self.bought = True
        return buy_market(1.0, ticker=self.ticker)


def main():
    bars = load_bars(CSV_PATH)
    with open(CONFIG_PATH) as f:
        config = json.load(f)

    # BuyAndHold enters on the first valid bar, so that bar's close is the
    # reference price the entry fill should be measured against.
    entry_reference_price = bars[0][4]  # (ts, open, high, low, close, ...)

    result = run_backtest(BuyAndHold, config, {TICKER: bars})

    if not (config.get('commission_per_unit') or config.get('slippage') or config.get('spread')):
        print('Note: commission, slippage, and spread are all 0 in this config --')
        print('      this run is a frictionless fill, which no live execution will')
        print('      reproduce. Set commission_per_unit, slippage and spread to your')
        print('      own venue assumptions; EXECUTION_SPEC.md defines each one.')
        print()
    else:
        print(f'Costs modelled: commission {config.get("commission_per_unit", 0.0)}/unit'
              f' ({config.get("commission_mode", "round_trip")}),'
              f' slippage {config.get("slippage", 0.0)},'
              f' spread {config.get("spread", 0.0)},'
              f' price_volatility {config.get("price_volatility", 0.0)}.')
        print('      These are illustrative defaults, not your venue. See EXECUTION_SPEC.md.')
        print()

    print(f'Bars loaded:    {len(bars)}')
    print(f'Net PnL:        {result.net_pnl:.4f}')
    print(f'Gross PnL:      {result.gross_pnl:.4f}')
    print(f'Fees:           {result.total_fees:.4f}')
    print(f'Slippage cost (excl. spread): {result.total_slippage_cost:.4f}')
    print(f'Trades:         {result.trades}')
    print(f'Closed trades:  {result.closed_trades_count}')

    for i, trade in enumerate(result.closed_trades, start=1):
        print(
            f'  {i}. {trade["ticker"]} {trade["side"]} '
            f'{trade["qty"]:g} @ {trade["entry_price"]:.4f} '
            f'-> {trade["exit_price"]:.4f}  net {trade["net_pnl"]:.4f}'
        )

    # total_slippage_cost above deliberately excludes spread (EXECUTION_SPEC.md
    # §3) -- it is NOT the total transaction cost. Derive that from fill_price
    # against a reference price instead: see BacktestResult.total_cost, which
    # sums |entry_price - reference_price| * qty over closed_trades. Do not
    # size off total_slippage_cost alone.
    entry_cost = abs(result.closed_trades[0]['entry_price'] - entry_reference_price) * result.closed_trades[0]['qty']
    print(f'Entry cost (fill vs. bar close): {entry_cost:.4f}')


if __name__ == '__main__':
    main()
