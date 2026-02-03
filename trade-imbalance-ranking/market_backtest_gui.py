import os
import sys
import time
import queue
import random
import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import tkinter as tk
from tkinter import ttk, messagebox

import requests

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # type: ignore
    from matplotlib.figure import Figure  # type: ignore
except ImportError as exc:
    print("ERROR: matplotlib is required. Install with: pip install matplotlib", file=sys.stderr)
    raise

ET = ZoneInfo("America/New_York")
BASE = "https://data.alpaca.markets"

DEFAULT_SYMBOLS = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA","AMD","NFLX","INTC",
    "JPM","BAC","XOM","CVX","AVGO","ORCL","COST","ADBE","CRM","QCOM",
    "MU","CSCO","PEP","KO","T","VZ","SPY","QQQ","IWM","DIA",
    "UBER","SHOP","SNOW","PANW","ADP","TXN","WMT","HD","LOW","CAT",
    "GE","BA","DIS","PFE","MRK","UNH","LLY","JNJ","ABBV","CVS"
]


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def chunked(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def fetch_bars(symbols, start_utc, end_utc, timeframe, headers, sleep_s, max_pages):
    bars_map = {s: [] for s in symbols}
    page_token = None
    pages = 0
    while True:
        params = {
            "symbols": ",".join(symbols),
            "timeframe": timeframe,
            "start": iso(start_utc),
            "end": iso(end_utc),
            "limit": 10000,
            "adjustment": "raw",
        }
        if page_token:
            params["page_token"] = page_token
        r = requests.get(f"{BASE}/v2/stocks/bars", headers=headers, params=params, timeout=30)
        if r.status_code >= 400:
            raise requests.HTTPError(f"{r.status_code} {r.text}", response=r)
        data = r.json()
        for sym, bars in data.get("bars", {}).items():
            bars_map.setdefault(sym, []).extend(bars)
        page_token = data.get("next_page_token")
        pages += 1
        if not page_token:
            break
        if max_pages and pages >= max_pages:
            break
        time.sleep(sleep_s)
    return bars_map


def to_series(bars_map):
    series = {}
    for sym, bars in bars_map.items():
        if not bars:
            continue
        bars_sorted = sorted(bars, key=lambda b: b.get("t", ""))
        times = []
        prices = []
        volumes = []
        for b in bars_sorted:
            t = b.get("t")
            c = b.get("c")
            v = b.get("v", 0)
            if t is None or c is None:
                continue
            dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
            times.append(dt)
            prices.append(float(c))
            volumes.append(int(v))
        if times:
            series[sym] = {"times": times, "prices": prices, "volumes": volumes}
    return series


def top_symbols_by_volume(series, top_n):
    volumes = {s: sum(series[s]["volumes"]) for s in series}
    top = sorted(volumes.keys(), key=lambda s: volumes[s], reverse=True)[:top_n]
    return top, volumes


def generate_synthetic_series(
    num_symbols,
    num_steps,
    step_minutes,
    seed,
    start_price,
    drift,
    volatility,
    mean_reversion,
    shock_prob,
    shock_scale,
):
    random.seed(seed)
    base_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    series = {}
    for i in range(num_symbols):
        sym = f"SYM{i+1:02d}"
        price = start_price * (1.0 + random.uniform(-0.2, 0.2))
        mean_price = price
        times = []
        prices = []
        volumes = []
        for step in range(num_steps):
            dt = base_time + timedelta(minutes=step_minutes * step)
            shock = 0.0
            if random.random() < shock_prob:
                shock = random.gauss(0.0, shock_scale)
            mr = -mean_reversion * ((price - mean_price) / max(mean_price, 1e-9))
            noise = random.gauss(0.0, volatility)
            ret = drift + mr + noise + shock
            price = max(0.05, price * (1.0 + ret))
            mean_price = mean_price * (1.0 + drift * 0.1)
            vol = int(max(1, random.gauss(1_000_000, 250_000)))
            times.append(dt)
            prices.append(price)
            volumes.append(vol)
        series[sym] = {"times": times, "prices": prices, "volumes": volumes}
    return series


def grid_simulation(times, prices, step_pct, max_units, initial_cash, fee_per_trade, slippage_bps):
    if not prices:
        return {
            "trades": [],
            "equity": [],
            "pnl": 0.0,
            "return_pct": 0.0,
            "final_cash": initial_cash,
            "final_units": 0,
        }
    cash = float(initial_cash)
    units = 0
    reference = prices[0]
    equity = []
    trades = []
    for t, price in zip(times, prices):
        if price >= reference * (1.0 + step_pct) and units < max_units:
            fill = price * (1.0 + slippage_bps / 10_000.0)
            cash -= fill + fee_per_trade
            units += 1
            reference = price
            trades.append((t, "BUY", price))
        elif price <= reference * (1.0 - step_pct) and units > 0:
            fill = price * (1.0 - slippage_bps / 10_000.0)
            cash += fill - fee_per_trade
            units -= 1
            reference = price
            trades.append((t, "SELL", price))
        equity.append((t, cash + units * price))
    final_value = cash + units * prices[-1]
    pnl = final_value - initial_cash
    return_pct = (pnl / initial_cash * 100.0) if initial_cash else 0.0
    return {
        "trades": trades,
        "equity": equity,
        "pnl": pnl,
        "return_pct": return_pct,
        "final_cash": cash,
        "final_units": units,
    }


class BacktestApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Backtest Simulator (No Live Trading)")
        self.queue = queue.Queue()
        self.current = None

        self.source_var = tk.StringVar(value="Synthetic")
        self.symbols_var = tk.StringVar(value=",".join(DEFAULT_SYMBOLS))
        self.top_n_var = tk.StringVar(value="30")
        self.start_date_var = tk.StringVar(value=(datetime.now(ET).date() - timedelta(days=5)).isoformat())
        self.end_date_var = tk.StringVar(value=(datetime.now(ET).date() - timedelta(days=1)).isoformat())
        self.timeframe_var = tk.StringVar(value="1Min")
        self.sleep_var = tk.StringVar(value="0.35")
        self.max_pages_var = tk.StringVar(value="10")

        self.num_symbols_var = tk.StringVar(value="30")
        self.num_steps_var = tk.StringVar(value="390")
        self.step_minutes_var = tk.StringVar(value="1")
        self.seed_var = tk.StringVar(value="42")
        self.start_price_var = tk.StringVar(value="100")
        self.drift_var = tk.StringVar(value="0.00005")
        self.volatility_var = tk.StringVar(value="0.002")
        self.mean_reversion_var = tk.StringVar(value="0.05")
        self.shock_prob_var = tk.StringVar(value="0.002")
        self.shock_scale_var = tk.StringVar(value="0.03")

        self.step_pct_var = tk.StringVar(value="0.0015")
        self.max_units_var = tk.StringVar(value="5")
        self.initial_cash_var = tk.StringVar(value="10000")
        self.fee_var = tk.StringVar(value="0.0")
        self.slippage_var = tk.StringVar(value="0.0")

        self.symbol_select_var = tk.StringVar(value="")

        self._build_ui()
        self.root.after(200, self._poll_queue)

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=8)
        main.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        controls = ttk.Frame(main)
        controls.grid(row=0, column=0, sticky="nsw", padx=(0, 8))
        plot = ttk.Frame(main)
        plot.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        ttk.Label(controls, text="Data Source").grid(row=0, column=0, sticky="w")
        ttk.Combobox(controls, textvariable=self.source_var, values=["Synthetic", "Alpaca Historical"], width=20, state="readonly").grid(row=0, column=1, sticky="w")

        ttk.Label(controls, text="Top N by Volume").grid(row=1, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.top_n_var, width=10).grid(row=1, column=1, sticky="w")

        ttk.Separator(controls, orient="horizontal").grid(row=2, column=0, columnspan=2, sticky="ew", pady=6)

        ttk.Label(controls, text="Symbols (CSV)").grid(row=3, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.symbols_var, width=45).grid(row=3, column=1, sticky="w")

        ttk.Label(controls, text="Start Date").grid(row=4, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.start_date_var, width=12).grid(row=4, column=1, sticky="w")
        ttk.Label(controls, text="End Date").grid(row=5, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.end_date_var, width=12).grid(row=5, column=1, sticky="w")
        ttk.Label(controls, text="Timeframe").grid(row=6, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.timeframe_var, width=12).grid(row=6, column=1, sticky="w")
        ttk.Label(controls, text="API Sleep (s)").grid(row=7, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.sleep_var, width=12).grid(row=7, column=1, sticky="w")
        ttk.Label(controls, text="Max Pages").grid(row=8, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.max_pages_var, width=12).grid(row=8, column=1, sticky="w")

        ttk.Separator(controls, orient="horizontal").grid(row=9, column=0, columnspan=2, sticky="ew", pady=6)

        ttk.Label(controls, text="Synthetic: Symbols").grid(row=10, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.num_symbols_var, width=12).grid(row=10, column=1, sticky="w")
        ttk.Label(controls, text="Synthetic: Steps").grid(row=11, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.num_steps_var, width=12).grid(row=11, column=1, sticky="w")
        ttk.Label(controls, text="Synthetic: Step Minutes").grid(row=12, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.step_minutes_var, width=12).grid(row=12, column=1, sticky="w")
        ttk.Label(controls, text="Seed").grid(row=13, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.seed_var, width=12).grid(row=13, column=1, sticky="w")
        ttk.Label(controls, text="Start Price").grid(row=14, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.start_price_var, width=12).grid(row=14, column=1, sticky="w")
        ttk.Label(controls, text="Drift").grid(row=15, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.drift_var, width=12).grid(row=15, column=1, sticky="w")
        ttk.Label(controls, text="Volatility").grid(row=16, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.volatility_var, width=12).grid(row=16, column=1, sticky="w")
        ttk.Label(controls, text="Mean Reversion").grid(row=17, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.mean_reversion_var, width=12).grid(row=17, column=1, sticky="w")
        ttk.Label(controls, text="Shock Prob").grid(row=18, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.shock_prob_var, width=12).grid(row=18, column=1, sticky="w")
        ttk.Label(controls, text="Shock Scale").grid(row=19, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.shock_scale_var, width=12).grid(row=19, column=1, sticky="w")

        ttk.Separator(controls, orient="horizontal").grid(row=20, column=0, columnspan=2, sticky="ew", pady=6)

        ttk.Label(controls, text="Step %").grid(row=21, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.step_pct_var, width=12).grid(row=21, column=1, sticky="w")
        ttk.Label(controls, text="Max Units").grid(row=22, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.max_units_var, width=12).grid(row=22, column=1, sticky="w")
        ttk.Label(controls, text="Initial Cash").grid(row=23, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.initial_cash_var, width=12).grid(row=23, column=1, sticky="w")
        ttk.Label(controls, text="Fee / Trade").grid(row=24, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.fee_var, width=12).grid(row=24, column=1, sticky="w")
        ttk.Label(controls, text="Slippage (bps)").grid(row=25, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.slippage_var, width=12).grid(row=25, column=1, sticky="w")

        ttk.Separator(controls, orient="horizontal").grid(row=26, column=0, columnspan=2, sticky="ew", pady=6)

        self.run_btn = ttk.Button(controls, text="Run Simulation", command=self.run)
        self.run_btn.grid(row=27, column=0, sticky="w")
        self.speed_btn = ttk.Button(controls, text="API Speed Test", command=self.speed_test)
        self.speed_btn.grid(row=27, column=1, sticky="w")

        ttk.Label(controls, text="Plot Symbol").grid(row=28, column=0, sticky="w", pady=(6, 0))
        self.symbol_menu = ttk.OptionMenu(controls, self.symbol_select_var, "")
        self.symbol_menu.grid(row=28, column=1, sticky="w", pady=(6, 0))

        self.log = tk.Text(controls, width=45, height=10, state="disabled")
        self.log.grid(row=29, column=0, columnspan=2, sticky="we", pady=(6, 0))

        self.table = ttk.Treeview(plot, columns=("symbol", "volume", "start", "end", "chg", "trades", "pnl", "ret"), show="headings", height=8)
        for col, title in [
            ("symbol", "Symbol"),
            ("volume", "Volume"),
            ("start", "Start"),
            ("end", "End"),
            ("chg", "%Chg"),
            ("trades", "Trades"),
            ("pnl", "PnL"),
            ("ret", "Return%"),
        ]:
            self.table.heading(col, text=title)
            width = 80 if col != "symbol" else 70
            anchor = "center" if col == "symbol" else "e"
            self.table.column(col, width=width, anchor=anchor)
        self.table.grid(row=0, column=0, sticky="ew")
        plot.columnconfigure(0, weight=1)

        self.fig = Figure(figsize=(7, 6), dpi=100)
        self.ax_price = self.fig.add_subplot(2, 1, 1)
        self.ax_equity = self.fig.add_subplot(2, 1, 2)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot)
        self.canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew")
        plot.rowconfigure(1, weight=1)

        self.symbol_select_var.trace_add("write", self._on_symbol_change)

    def _log(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_symbol_options(self, symbols):
        menu = self.symbol_menu["menu"]
        menu.delete(0, "end")
        for sym in symbols:
            menu.add_command(label=sym, command=lambda s=sym: self.symbol_select_var.set(s))
        if symbols:
            self.symbol_select_var.set(symbols[0])

    def _on_symbol_change(self, *_):
        if not self.current:
            return
        sym = self.symbol_select_var.get()
        if sym in self.current["series"]:
            self._plot_symbol(sym)

    def _plot_symbol(self, sym):
        series = self.current["series"][sym]
        sim = self.current["sims"][sym]
        times = series["times"]
        prices = series["prices"]
        equity = sim["equity"]

        self.ax_price.clear()
        self.ax_equity.clear()

        self.ax_price.plot(times, prices, color="tab:blue", linewidth=1.2)
        for t, side, price in sim["trades"][:500]:
            color = "green" if side == "BUY" else "red"
            self.ax_price.scatter([t], [price], s=12, color=color)
        self.ax_price.set_title(f"{sym} Price")
        self.ax_price.grid(True, alpha=0.2)

        if equity:
            eq_times = [t for t, _ in equity]
            eq_vals = [v for _, v in equity]
            self.ax_equity.plot(eq_times, eq_vals, color="tab:orange", linewidth=1.2)
        self.ax_equity.set_title("Simulated Equity")
        self.ax_equity.grid(True, alpha=0.2)

        self.fig.tight_layout()
        self.canvas.draw_idle()

    def _poll_queue(self):
        try:
            while True:
                item = self.queue.get_nowait()
                if item["type"] == "log":
                    self._log(item["msg"])
                elif item["type"] == "result":
                    self._apply_result(item["data"])
                elif item["type"] == "error":
                    messagebox.showerror("Error", item["msg"])
                    self._log(f"ERROR: {item['msg']}")
                elif item["type"] == "done":
                    self.run_btn.configure(state="normal")
                    self.speed_btn.configure(state="normal")
        except queue.Empty:
            pass
        self.root.after(200, self._poll_queue)

    def _apply_result(self, data):
        self.current = data
        self.table.delete(*self.table.get_children())
        for sym in data["top_symbols"]:
            row = data["rows"][sym]
            self.table.insert("", "end", values=(
                sym,
                f"{row['volume']:,}",
                f"{row['start']:.2f}",
                f"{row['end']:.2f}",
                f"{row['chg_pct']:.2f}",
                f"{row['trades']}",
                f"{row['pnl']:.2f}",
                f"{row['ret_pct']:.2f}",
            ))
        self._set_symbol_options(data["top_symbols"])
        if data["top_symbols"]:
            self._plot_symbol(data["top_symbols"][0])

    def _parse_float(self, name, value):
        try:
            return float(value)
        except ValueError:
            raise ValueError(f"Invalid {name}: {value}")

    def _parse_int(self, name, value):
        try:
            return int(value)
        except ValueError:
            raise ValueError(f"Invalid {name}: {value}")

    def run(self):
        self.run_btn.configure(state="disabled")
        self.speed_btn.configure(state="disabled")
        thread = threading.Thread(target=self._run_worker, daemon=True)
        thread.start()

    def _run_worker(self):
        try:
            self.queue.put({"type": "log", "msg": "Starting simulation..."})
            data_source = self.source_var.get()
            step_pct = self._parse_float("Step %", self.step_pct_var.get())
            max_units = self._parse_int("Max Units", self.max_units_var.get())
            initial_cash = self._parse_float("Initial Cash", self.initial_cash_var.get())
            fee = self._parse_float("Fee / Trade", self.fee_var.get())
            slippage = self._parse_float("Slippage", self.slippage_var.get())
            top_n = self._parse_int("Top N", self.top_n_var.get())

            if data_source == "Synthetic":
                num_symbols = self._parse_int("Synthetic Symbols", self.num_symbols_var.get())
                num_steps = self._parse_int("Synthetic Steps", self.num_steps_var.get())
                step_minutes = self._parse_int("Step Minutes", self.step_minutes_var.get())
                seed = self._parse_int("Seed", self.seed_var.get())
                start_price = self._parse_float("Start Price", self.start_price_var.get())
                drift = self._parse_float("Drift", self.drift_var.get())
                volatility = self._parse_float("Volatility", self.volatility_var.get())
                mean_reversion = self._parse_float("Mean Reversion", self.mean_reversion_var.get())
                shock_prob = self._parse_float("Shock Prob", self.shock_prob_var.get())
                shock_scale = self._parse_float("Shock Scale", self.shock_scale_var.get())

                series = generate_synthetic_series(
                    num_symbols,
                    num_steps,
                    step_minutes,
                    seed,
                    start_price,
                    drift,
                    volatility,
                    mean_reversion,
                    shock_prob,
                    shock_scale,
                )
            else:
                key = os.getenv("ALPACA_KEY_ID")
                secret = os.getenv("ALPACA_SECRET_KEY")
                if not key or not secret:
                    raise RuntimeError("Set ALPACA_KEY_ID and ALPACA_SECRET_KEY in your environment.")
                headers = {
                    "APCA-API-KEY-ID": key,
                    "APCA-API-SECRET-KEY": secret,
                }
                start_date = datetime.fromisoformat(self.start_date_var.get()).date()
                end_date = datetime.fromisoformat(self.end_date_var.get()).date()
                if end_date < start_date:
                    raise ValueError("End date must be after start date.")
                start_et = datetime(start_date.year, start_date.month, start_date.day, 0, 0, tzinfo=ET)
                end_et = datetime(end_date.year, end_date.month, end_date.day, 23, 59, tzinfo=ET)

                symbols = [s.strip().upper() for s in self.symbols_var.get().split(",") if s.strip()]
                if not symbols:
                    raise ValueError("Provide at least one symbol.")
                sleep_s = self._parse_float("API Sleep", self.sleep_var.get())
                max_pages = self._parse_int("Max Pages", self.max_pages_var.get())
                timeframe = self.timeframe_var.get().strip() or "1Min"

                series = {}
                for chunk in chunked(symbols, 200):
                    self.queue.put({"type": "log", "msg": f"Fetching {len(chunk)} symbols..."})
                    bars_map = fetch_bars(
                        chunk,
                        start_et.astimezone(timezone.utc),
                        end_et.astimezone(timezone.utc),
                        timeframe,
                        headers,
                        sleep_s,
                        max_pages,
                    )
                    series.update(to_series(bars_map))
                if not series:
                    raise RuntimeError("No bars returned. Check symbols/date range.")

            top_symbols, volumes = top_symbols_by_volume(series, top_n)
            if not top_symbols:
                raise RuntimeError("No data for top symbols.")

            sims = {}
            rows = {}
            for sym in top_symbols:
                s = series[sym]
                sim = grid_simulation(
                    s["times"],
                    s["prices"],
                    step_pct,
                    max_units,
                    initial_cash,
                    fee,
                    slippage,
                )
                sims[sym] = sim
                start_price = s["prices"][0]
                end_price = s["prices"][-1]
                chg_pct = (end_price - start_price) / start_price * 100.0
                rows[sym] = {
                    "volume": volumes.get(sym, 0),
                    "start": start_price,
                    "end": end_price,
                    "chg_pct": chg_pct,
                    "trades": len(sim["trades"]),
                    "pnl": sim["pnl"],
                    "ret_pct": sim["return_pct"],
                }

            self.queue.put({"type": "result", "data": {
                "series": series,
                "sims": sims,
                "rows": rows,
                "top_symbols": top_symbols,
            }})
            self.queue.put({"type": "log", "msg": "Simulation complete."})
        except Exception as exc:
            self.queue.put({"type": "error", "msg": str(exc)})
        finally:
            self.queue.put({"type": "done"})

    def speed_test(self):
        self.run_btn.configure(state="disabled")
        self.speed_btn.configure(state="disabled")
        thread = threading.Thread(target=self._speed_worker, daemon=True)
        thread.start()

    def _speed_worker(self):
        try:
            key = os.getenv("ALPACA_KEY_ID")
            secret = os.getenv("ALPACA_SECRET_KEY")
            if not key or not secret:
                raise RuntimeError("Set ALPACA_KEY_ID and ALPACA_SECRET_KEY in your environment.")
            headers = {
                "APCA-API-KEY-ID": key,
                "APCA-API-SECRET-KEY": secret,
            }
            now = datetime.now(ET)
            start = (now - timedelta(minutes=30)).astimezone(timezone.utc)
            end = now.astimezone(timezone.utc)
            latencies = []
            errors = 0
            for i in range(5):
                t0 = time.perf_counter()
                r = requests.get(
                    f"{BASE}/v2/stocks/bars",
                    headers=headers,
                    params={
                        "symbols": "AAPL",
                        "timeframe": "1Min",
                        "start": iso(start),
                        "end": iso(end),
                        "limit": 10000,
                        "adjustment": "raw",
                    },
                    timeout=30,
                )
                dt = time.perf_counter() - t0
                if r.status_code >= 400:
                    errors += 1
                latencies.append(dt)
                time.sleep(0.2)
            avg = sum(latencies) / len(latencies)
            self.queue.put({"type": "log", "msg": f"API speed test: avg {avg*1000:.0f} ms, errors {errors}/5"})
        except Exception as exc:
            self.queue.put({"type": "error", "msg": str(exc)})
        finally:
            self.queue.put({"type": "done"})


def main():
    root = tk.Tk()
    app = BacktestApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
