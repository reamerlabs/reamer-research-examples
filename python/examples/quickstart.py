"""The smallest complete run: ATR band reversion over a CSV, opened in the visual
trade diagnostics tool.

Fades a close more than two ATRs from its 20-bar mean, targets the mean and
stops two ATRs further out.

    pip install reamer-research           (once: from PyPI, or the wheel in the
                                           kit's python/)
    python3 python/examples/quickstart.py [bars.csv] [--class | --object]

rr.backtest takes a strategy in any of three forms, and this script has the
same strategy in each:

    rr.backtest(on_bar, csv, lookback=20)    a function on_bar(data)
    rr.backtest(AtrBands, csv)               a class with an on_bar method,
                                             instantiated once for the run
    rr.backtest(AtrBands(k=2), csv)          an object with an on_bar method,
                                             built and configured by you

All three print the same summary. A function suits a rule that keeps no
state; a class or object keeps settings and state across bars on self, and
an object can be read after the run.

With no file it runs on sample_data/SAMPLE_5min.csv, synthetic bars that fit
inside Evaluation Mode, so it runs before a licence is activated.
"""
import sys, pathlib
import numpy as np
import reamer_research as rr


# 1. A function.
def on_bar(d):
    c, h, l = d.close, d.high[1:], d.low[1:]
    if c[0] == 0: return               # warm-up: the window is still filling
    atr = (np.maximum(h, c[:-1]) - np.minimum(l, c[:-1])).mean()
    mid, px = c.mean(), c[-1]
    if d.position() == 0 and px < mid - 2 * atr:
        return rr.buy_market(10, take_profit=mid, stop_loss=px - 2 * atr)
    if d.position() == 0 and px > mid + 2 * atr:
        return rr.sell_market(10, take_profit=mid, stop_loss=px + 2 * atr)


# 2 and 3. A class, passed as it is or as an object you built.
class AtrBands:
    lookback = 20                      # bars per window, read off the class or object

    def __init__(self, k=2.0, qty=10):
        self.k, self.qty = k, qty      # settings
        self.entries = 0               # state kept across bars

    def on_bar(self, d):
        c, h, l = d.close, d.high[1:], d.low[1:]
        if c[0] == 0: return
        atr = (np.maximum(h, c[:-1]) - np.minimum(l, c[:-1])).mean()
        mid, px, band = c.mean(), c[-1], self.k * atr
        if d.position() == 0 and px < mid - band:
            self.entries += 1
            return rr.buy_market(self.qty, take_profit=mid, stop_loss=px - band)
        if d.position() == 0 and px > mid + band:
            self.entries += 1
            return rr.sell_market(self.qty, take_profit=mid, stop_loss=px + band)


args = [a for a in sys.argv[1:] if not a.startswith('--')]
csv = args[0] if args else pathlib.Path(__file__).parent.parent / 'sample_data' / 'SAMPLE_5min.csv'

if '--class' in sys.argv:
    print(rr.backtest(AtrBands, csv, open_viewer=True))
elif '--object' in sys.argv:
    strategy = AtrBands(k=2.0, qty=10)
    print(rr.backtest(strategy, csv, open_viewer=True))
    print(f'Entries sent     {strategy.entries:>12}')   # the object, read after the run
else:
    print(rr.backtest(on_bar, csv, lookback=20, open_viewer=True))
