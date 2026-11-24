#!/usr/bin/env python3
"""Download real bars from a vendor, run a backtest, print the summary.

Run from the python/ directory, with the package installed
(pip install reamer-research):

    # Alpaca crypto: no account or key needed. One ticker over four weeks
    # fits inside Evaluation Mode; the multi-ticker runs below need a licence.
    python3 examples/fetch_and_run.py alpaca-crypto BTC/USD \\
        --timeframe 1Hour --start 2025-01-01 --end 2025-01-29

    # Alpaca US stocks: free paper-account keys in ALPACA_API_KEY_ID and
    # ALPACA_API_SECRET_KEY (free plan: IEX feed)
    python3 examples/fetch_and_run.py alpaca-stocks AAPL MSFT \\
        --timeframe 1Day --start 2024-01-01 --end 2025-01-01

    # Databento: pip install databento, key in DATABENTO_API_KEY. Billed per
    # request; the fetcher prices it first and refuses anything over
    # --max-cost (default $1.00).
    python3 examples/fetch_and_run.py databento ES.c.0 --dataset GLBX.MDP3 \\
        --stype continuous --timeframe ohlcv-1h --start 2024-01-02 --end 2024-02-01

--csv-dir DIR also saves each ticker as a CSV that rr.write_bin (or the kit's
bin/reamer-csv-build) turns into a .bin file, so later runs read local files instead of downloading again.

The strategy is a deliberately small moving-average cross, one per ticker, to
show the shape of a multi-ticker run on vendor data. Costs come from
templates/engine_config.json; replace them with your venue's before reading
anything into the numbers.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from reamer_research import buy_market, close_position, run_backtest
from fetchers import write_csv

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, '..', 'templates', 'engine_config.json')

FAST, SLOW = 10, 30


def fetch(args):
    if args.vendor == 'alpaca-crypto':
        from fetchers.alpaca_bars import fetch_alpaca_crypto
        return fetch_alpaca_crypto(args.symbols, args.timeframe or '1Hour', args.start, args.end)
    if args.vendor == 'alpaca-stocks':
        from fetchers.alpaca_bars import fetch_alpaca_stocks
        return fetch_alpaca_stocks(args.symbols, args.timeframe or '1Day', args.start, args.end,
                                   feed=args.feed)
    from fetchers.databento_bars import fetch_databento
    if not args.dataset:
        sys.exit('databento needs --dataset, e.g. GLBX.MDP3 or XNAS.ITCH')
    return fetch_databento(args.dataset, args.symbols, args.timeframe or 'ohlcv-1d',
                           args.start, args.end, stype_in=args.stype,
                           max_cost_usd=args.max_cost)


def make_strategy(tickers, capital):
    # Each ticker may use an equal share of 90% of the capital, so one BTC at
    # ~$100k is not bought on a $10k account and rejected for margin.
    budget = 0.9 * capital / len(tickers)

    class MovingAverageCross:
        """Long when the fast average of closes is above the slow one, flat otherwise."""

        lookback = SLOW

        def __init__(self, config_path=None):
            self.long = {t: False for t in tickers}
            self.fresh = {t: 0 for t in tickers}

        def on_bar(self, data):
            orders = []
            for t in tickers:
                tv = data[t]
                if not tv.valid:
                    continue
                # Wait for SLOW real bars of this ticker before trusting the window.
                self.fresh[t] += 1
                if self.fresh[t] < SLOW:
                    continue
                close = tv.close
                fast_above = close[-FAST:].mean() > close.mean()
                if fast_above and not self.long[t]:
                    orders.append(buy_market(budget / close[-1], ticker=t))
                    self.long[t] = True
                elif not fast_above and self.long[t]:
                    orders.append(close_position(ticker=t))
                    self.long[t] = False
            return orders or None

    return MovingAverageCross


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('vendor', choices=['alpaca-crypto', 'alpaca-stocks', 'databento'])
    p.add_argument('symbols', nargs='+')
    p.add_argument('--start', required=True)
    p.add_argument('--end', required=True)
    p.add_argument('--timeframe', help="Alpaca: '1Min', '1Hour', '1Day'...; "
                                       "Databento: 'ohlcv-1s', 'ohlcv-1m', 'ohlcv-1h', 'ohlcv-1d'")
    p.add_argument('--feed', default='iex', help="alpaca-stocks: 'iex' (free) or 'sip' (paid)")
    p.add_argument('--dataset', help='databento dataset, e.g. GLBX.MDP3')
    p.add_argument('--stype', default='raw_symbol',
                   help="databento symbology: 'raw_symbol', 'continuous', 'parent'")
    p.add_argument('--max-cost', type=float, default=1.0,
                   help='databento: refuse a request priced above this many USD')
    p.add_argument('--csv-dir', help='also save each ticker as CSV for bin/reamer-csv-build')
    args = p.parse_args()

    bars = fetch(args)

    if args.csv_dir:
        os.makedirs(args.csv_dir, exist_ok=True)
        for s, b in bars.items():
            path = os.path.join(args.csv_dir, s.replace('/', '-') + '.csv')
            write_csv(b, path)
            print(f'Saved {len(b)} bars to {path}')

    with open(CONFIG_PATH) as f:
        config = json.load(f)
    result = run_backtest(make_strategy(sorted(bars), config['initial_capital']), config, bars)

    for t, b in sorted(bars.items()):
        print(f'{t:<10} {len(b)} bars')
    print(f'Net PnL:        {result.net_pnl:.4f}')
    print(f'Fees:           {result.total_fees:.4f}')
    print(f'Closed trades:  {result.closed_trades_count}')


if __name__ == '__main__':
    main()
