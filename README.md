# Reamer Research examples

Example strategies, strategy templates, data ingestion scripts and
market-data fetchers for
[Reamer Research](https://reamerlabs.com/products/reamer-research), a
backtesting engine for Python and C++ that also trades live. The code here
is MIT licensed. The engine is commercial software, and it runs without a
key in Evaluation Mode.

## Speed

In [What a Backtest Costs](https://reamerlabs.com/papers/what-a-backtest-costs.pdf),
on one AMD EPYC 9575F with Reamer Research 4.6.0, 500,000 bars of the
paper's realistic strategy ran at 148,000 bars per second through the
Python path and 1.39 million through the C++ path. Backtrader,
NautilusTrader and QuantConnect LEAN ran the same strategy on the same data
at 6,500 to 37,000. Versions are pinned and the raw results are public.

## Get the engine

The engine is on PyPI as
[reamer-research](https://pypi.org/project/reamer-research/), free and with
no key. With Python 3.9 or later, on Linux x86_64 (and Windows under WSL2)
or macOS on Apple silicon:

```bash
pip install reamer-research
git clone https://github.com/reamerlabs/reamer-research-examples
cd reamer-research-examples/python
python3 examples/quickstart.py
```

Everything in `python/` runs on that package. The C++ examples need the
Reamer Research kit, which holds the C++ header and library and the
`reamer-license` tool that activates a licence, free from
**[reamerlabs.com/download](https://reamerlabs.com/download)**.
Documentation: [reamerlabs.com/docs](https://reamerlabs.com/docs).

`quickstart.py` runs an ATR band reversion with a bracket on every entry
over `sample_data/SAMPLE_5min.csv`, prints the summary and opens the run in
the visual trade diagnostics tool. Run it twice: the output is identical.

## Three ways to write a strategy

`rr.backtest` takes the strategy as a function, a class or an object:

```python
rr.backtest(on_bar, 'AAPL.csv', lookback=20)     # a function on_bar(data)
rr.backtest(AtrBands, 'AAPL.csv')                # a class with on_bar, instantiated once
rr.backtest(AtrBands(k=2.5), 'AAPL.csv')         # an object with on_bar, configured by you
```

```python
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
```

The same rule gives the same result in every form. A function suits a rule
that keeps no state; a class or object keeps settings and state across bars
on `self`, and an object can be read after the run (`strategy.entries`).
`quickstart.py` has the strategy in all three:

```bash
python3 examples/quickstart.py            # the function
python3 examples/quickstart.py --class    # the class
python3 examples/quickstart.py --object   # an object, read after the run
```

Most strategies in `examples/` and `templates/` are classes. In C++ a
strategy is a lambda, a function or an object with `on_bar(rr::Data&)`.

## Getting data in

One short script per source. Each one runs a strategy on what it loads, and
each fits inside Evaluation Mode.

| Script | Source | What it shows |
|---|---|---|
| [`data_csv.py`](python/examples/data_csv.py) | CSV | Pass the path to `rr.backtest`, or `rr.load_csv` it first. Date and Time columns or one timestamp column (epoch s/ms or a date string), any header case, MetaTrader headers, comma, semicolon or tab. |
| [`data_bin.py`](python/examples/data_bin.py) | `.bin` | `rr.write_bin` once; every later run memory-maps the file, with `start=`/`end=` picking a range inside it. |
| [`data_parquet.py`](python/examples/data_parquet.py) | Parquet, pandas | `pd.read_parquet` and pass the DataFrame. A DatetimeIndex or a time column, timezone-aware or UTC. Anything pandas reads works the same way. |
| [`data_alpaca.py`](python/examples/data_alpaca.py) | Alpaca | Crypto with no key, US stocks with free paper keys; trade counts and VWAP notional filled from Alpaca. |
| [`data_databento.py`](python/examples/data_databento.py) | Databento | A DBN file you already have, or a download priced first and refused above $1.00. |

The CSV, `.bin` and Parquet scripts load the same sample bars and print the
same result, bar for bar.

The short version:

```python
import reamer_research as rr
from fetchers.alpaca_bars import fetch_alpaca_crypto   # python/fetchers/

rr.backtest(on_bar, 'AAPL.csv')                   # CSV path, ticker 'AAPL'
rr.backtest(on_bar, 'AAPL.bin')                   # memory-mapped
rr.backtest(on_bar, {'AAPL': df})                 # pandas DataFrame
rr.backtest(on_bar, {'AAPL': numpy_bars})         # numpy array
rr.backtest(on_bar, fetch_alpaca_crypto(['BTC/USD'], '1Hour', '2025-01-01', '2025-01-29'))
```

## Evaluation Mode

Without a licence, each backtest is limited to:

| Limit | Value |
|---|---|
| Tickers per run | 1 |
| Bar time per run | 30 days (last bar timestamp minus first) |
| Bars per run | 50,000 |

The first limit reached applies. A run past a limit stops with an error that
names the limit; nothing is silently cut. Monte Carlo and the visual trade
diagnostics tool work within the limits. Live and paper trading through
`rr.Relay` need a licence.

A [Reamer Research licence](https://reamerlabs.com/pricing) is $20 a month
and removes every limit. The same code runs unchanged.

## Going live

Reamer Research trades live without Reamer Server. Your loop feeds each
closed bar to your strategy, `rr.Relay` sends the orders it returns over a
Unix socket, and a receiver you run places them with your broker and sends
the fills back. `python/live/` has all of it, standard library only, and
`cpp/live/` runs the same paper trade from C++:

| Path | What it is |
|---|---|
| [`live/relay_receiver.py`](python/live/relay_receiver.py) | A complete receiver: the relay's wire format, a socket server, and `PaperBroker`, which fills orders against your bars. Swap `PaperBroker` for your broker's API to trade for real. |
| [`live/live_paper.py`](python/live/live_paper.py) | The quickstart's `on_bar`, unchanged, run live against `PaperBroker`: a CSV replayed bar by bar, or Alpaca's free 1-minute crypto bars with no key. |
| [`cpp/live/live_paper.cpp`](cpp/live/live_paper.cpp) | The quickstart's rule in C++ through `rr::Relay`, against the same receiver, which it starts itself. It reports the same fills and position as `live_paper.py`. |

```bash
python3 live/live_paper.py                   # replay sample_data/SAMPLE_5min.csv
python3 live/live_paper.py --alpaca BTC/USD  # live 1-minute bars, Ctrl-C to stop
```

From C++, with the kit unpacked at `$KIT`, from the repository root:

```bash
c++ -std=c++20 -O2 cpp/live/live_paper.cpp -I$KIT/include -L$KIT/lib -lreamer_research \
  -Wl,-rpath,$KIT/lib -o live_paper
./live_paper                                 # replay python/sample_data/SAMPLE_5min.csv
```

The relay needs a licence; Evaluation Mode has no live trading. Linux and
macOS, and Windows through WSL2. The steps, the wire format and what the
relay sends are in
[Live trading with Reamer Research](https://reamerlabs.com/docs/research-live).

## Strategies and templates

| Path | What it is |
|---|---|
| `python/examples/quickstart.py` | The smallest complete run, opened in the visual trade diagnostics tool. |
| `python/examples/quickstart_run.py` | A costed run with `templates/engine_config.json`, which also measures entry cost against the bar. |
| `python/examples/fetch_and_run.py` | A command-line downloader for Alpaca or Databento that runs a moving-average cross on the bars. |
| `python/examples/*_strategy.py`, `atr_*_bracket.py` | Single-ticker strategies: market, limit and stop entries, brackets, GTD and IOC expiry, risk sizing, console logging. |
| `python/examples/execution_test_suite.py`, `position_stress_test.py` | Strategies that exercise every order kind, time in force, bracket, partial close and reversal, to check fills against the [execution spec](https://reamerlabs.com/docs/execution-spec). |
| `python/examples/multi_asset_*.py` | Multi-ticker strategies. They need a licence. |
| `python/templates/` | Starting points to copy: buy and hold, mean reversion, ATR limit and stop brackets, and two multi-ticker templates (`multi_asset.py`, `replay_verify.py`) that need a licence. `engine_config.json` holds illustrative costs. |
| `python/fetchers/` | Alpaca and Databento bar fetchers that return arrays `rr.backtest` takes directly. |
| `python/sample_data/` | Synthetic bars; see its README. |
| `cpp/examples/` | The same ideas in C++ with the one-header wrapper, in all three strategy forms (a lambda, a function, an object with `on_bar`), plus `data_csv.cpp` and `data_bin.cpp` for getting bars in. Each runs on the sample bars in Evaluation Mode, built against the header and library in the kit: `c++ -std=c++20 -O2 cpp/examples/quickstart.cpp -I$KIT/include -L$KIT/lib -lreamer_research -Wl,-rpath,$KIT/lib -o quickstart && ./quickstart`. |

Strategy classes run with `rr.backtest(StrategyClass, 'bars.csv', open_viewer=True)`, or as an object with `rr.backtest(StrategyClass(), 'bars.csv')`.

## Documentation

- [Python package](https://reamerlabs.com/docs/python-package)
- [C++ wrapper](https://reamerlabs.com/docs/cpp-wrapper)
- [Execution spec](https://reamerlabs.com/docs/execution-spec): fills, slippage, spread, commission and margin
- [Visual trade diagnostics](https://reamerlabs.com/docs/trade-viewer)
- [Live trading](https://reamerlabs.com/docs/research-live): the relay, a receiver and its wire format
- [Licensing and Evaluation Mode](https://reamerlabs.com/docs/licensing)
- [What a Backtest Costs](https://reamerlabs.com/papers/what-a-backtest-costs.pdf): throughput, memory, scaling and reproducibility of four engines

Questions: support@reamerlabs.com.

## Licence

The code in this repository is under the MIT License (`LICENSE`).

The engine (the reamer-research package and the kit) is not: it is under
the Reamer Labs Software License Agreement (`LICENSE.txt` in the kit, and in
the wheel's `.dist-info/licenses/`), whose Section 2B grants Evaluation Mode
without payment or a key.
