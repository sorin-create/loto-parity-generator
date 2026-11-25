%%writefile generator.py
from pathlib import Path
import urllib.request
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CSV_PATH = BASE_DIR / "arhiva.loto.2014-noi.2026.csv"

NUM_COLS = ["n1", "n2", "n3", "n4", "n5", "n6"]
DAYS_RO = ["Luni", "Marti", "Miercuri", "Joi", "Vineri", "Sambata", "Duminica"]

PARITY_A = 0.29213
PARITY_B = round(1.0 - PARITY_A, 5)

GITHUB_CSV_RAW_URL = (
    "https://raw.githubusercontent.com/sorin-create/arhiva_loto.csv/main/"
    "arhiva.loto.2014-noi.2026.csv"
)


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    rename_map = {}
    for col in out.columns:
        c_clean = str(col).strip().lower()
        if c_clean == "data":
            rename_map[col] = "Data"
        elif c_clean in {"n1", "nr1"}:
            rename_map[col] = "n1"
        elif c_clean in {"n2", "nr2"}:
            rename_map[col] = "n2"
        elif c_clean in {"n3", "nr3"}:
            rename_map[col] = "n3"
        elif c_clean in {"n4", "nr4"}:
            rename_map[col] = "n4"
        elif c_clean in {"n5", "nr5"}:
            rename_map[col] = "n5"
        elif c_clean in {"n6", "nr6"}:
            rename_map[col] = "n6"
        elif c_clean == "zi":
            rename_map[col] = "Zi"
        elif c_clean in {"tip_tragere", "tip"}:
            rename_map[col] = "Tip_Tragere"
    return out.rename(columns=rename_map)


def _clean_archive_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Data", "Zi", "Tip_Tragere"] + NUM_COLS)

    out = _normalize_columns(df)
    if "Data" not in out.columns:
        return pd.DataFrame(columns=["Data", "Zi", "Tip_Tragere"] + NUM_COLS)

    for col in NUM_COLS:
        if col not in out.columns:
            out[col] = np.nan
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out["Data"] = out["Data"].astype(str).str.strip()
    out = out.dropna(subset=NUM_COLS)
    out = out[out["Data"].str.match(r"^\d{4}-\d{2}-\d{2}$", na=False)]

    for col in NUM_COLS:
        out[col] = out[col].astype(int)
        out = out[(out[col] >= 1) & (out[col] <= 49)]

    if out.empty:
        return pd.DataFrame(columns=["Data", "Zi", "Tip_Tragere"] + NUM_COLS)

    valid_mask = out[NUM_COLS].apply(lambda r: len(set(r)) == 6, axis=1)
    out = out[valid_mask].copy()

    dt_series = pd.to_datetime(out["Data"], format="%Y-%m-%d", errors="coerce")
    if "Zi" not in out.columns:
        out["Zi"] = dt_series.dt.weekday.map(
            lambda idx: DAYS_RO[int(idx)] if pd.notna(idx) else ""
        )
    if "Tip_Tragere" not in out.columns:
        out["Tip_Tragere"] = ""

    return out[["Data", "Zi", "Tip_Tragere"] + NUM_COLS].reset_index(drop=True)


def _sort_archive_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["_dt"] = pd.to_datetime(out["Data"], format="%Y-%m-%d", errors="coerce")
    if "Tip_Tragere" in out.columns:
        order_map = {"Principala": 0, "Suplimentara": 1}
        out["_tip_ord"] = out["Tip_Tragere"].map(order_map).fillna(9)
        out = out.sort_values(["_dt", "_tip_ord", "Data"], na_position="last").drop(
            columns=["_dt", "_tip_ord"]
        )
    else:
        out = out.sort_values(["_dt", "Data"], na_position="last").drop(columns=["_dt"])
    return out.reset_index(drop=True)


def download_csv_from_github(
    csv_path: Path, raw_url: str = GITHUB_CSV_RAW_URL, timeout: int = 15
) -> bool:
    if "UTILIZATOR/NUME_REPO" in raw_url:
        return False
    try:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(raw_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
        csv_path.write_text(content, encoding="utf-8")
        return csv_path.exists()
    except Exception as e:
        print(f"Eroare descarcare CSV: {e}")
        return False


def load_archive(
    csv_path: Path = DEFAULT_CSV_PATH, allow_github_download: bool = True
) -> pd.DataFrame:
    if not csv_path.exists() and allow_github_download:
        download_csv_from_github(csv_path)

    if not csv_path.exists():
        return pd.DataFrame(columns=["Data", "Zi", "Tip_Tragere"] + NUM_COLS)

    raw_df = pd.read_csv(csv_path)
    return _sort_archive_df(_clean_archive_df(raw_df))


def get_hot_cold_stats(
    hist_df: pd.DataFrame, recent_draws: int = 20
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if hist_df.empty:
        return (
            pd.DataFrame(columns=["Numar", "Aparitii"]),
            pd.DataFrame(columns=["Numar", "Extrageri absente"]),
        )

    vals = hist_df[NUM_COLS].to_numpy(dtype=int)
    n_total = len(vals)

    recent_slice = vals[-min(recent_draws, n_total) :].ravel()
    counts = np.bincount(recent_slice, minlength=50)
    hot_list = [{"Numar": num, "Aparitii": int(counts[num])} for num in range(1, 50)]
    hot_df = (
        pd.DataFrame(hot_list)
        .sort_values(by=["Aparitii", "Numar"], ascending=[False, True])
        .head(10)
    )

    cold_list = []
    for num in range(1, 50):
        draws_since = n_total
        for i in range(n_total - 1, -1, -1):
            if num in vals[i]:
                draws_since = (n_total - 1) - i
                break
        cold_list.append({"Numar": num, "Extrageri absente": draws_since})
    cold_df = (
        pd.DataFrame(cold_list)
        .sort_values(by=["Extrageri absente", "Numar"], ascending=[False, True])
        .head(10)
    )

    return hot_df, cold_df


def compute_dynamic_sum_bounds(
    hist_df: pd.DataFrame,
    rolling_window: int = 50,
    std_mult: float = 1.0,
    fallback_bounds: tuple[int, int] = (90, 215),
) -> tuple[float, float]:
    if hist_df.empty or len(hist_df) < 10:
        return float(fallback_bounds[0]), float(fallback_bounds[1])

    vals = hist_df[NUM_COLS].to_numpy(dtype=float)
    sums = vals.sum(axis=1)
    arr = sums[-max(10, min(rolling_window, len(sums))) :]
    mean_s = float(arr.mean())
    std_s = float(arr.std())
    low = max(21.0, mean_s - std_mult * std_s)
    high = min(279.0, mean_s + std_mult * std_s)
    return low, high


def compute_ranked_numbers(
    hist_df: pd.DataFrame,
    window: int = 5,
    decay: float = 0.98,
    weights: tuple[float, float, float] = (-0.25, 0.60, 0.15),
) -> tuple[list[int], dict[int, float]]:
    if hist_df.empty:
        return list(range(1, 50)), {x: 0.0 for x in range(1, 50)}

    w_win, w_glob, w_rec = weights
    vals = hist_df[NUM_COLS].to_numpy(dtype=int)
    n_rows = len(vals)
    win_vals = vals[-min(window, n_rows) :]

    win_counts = np.bincount(win_vals.ravel(), minlength=50)
    glob_counts = np.bincount(vals.ravel(), minlength=50)

    row_weights = decay ** np.arange(n_rows - 1, -1, -1, dtype=float)
    rec_arr = np.bincount(vals.ravel(), weights=np.repeat(row_weights, 6), minlength=50)

    max_w = max(int(win_counts[1:].max()), 1)
    max_g = max(int(glob_counts[1:].max()), 1)
    max_r = max(float(rec_arr[1:].max()), 1e-9)

    scores = {
        x: (
            w_win * (win_counts[x] / max_w)
            + w_glob * (glob_counts[x] / max_g)
            + w_rec * (rec_arr[x] / max_r)
        )
        for x in range(1, 50)
    }

    ranked = sorted(range(1, 50), key=lambda x: (-scores[x], x))
    return ranked, scores


def evaluate_substrate_parity(
    comb: list[int],
    scores: dict[int, float],
    sum_bounds: tuple[float, float],
    threshold_a: float = PARITY_A,
) -> dict[str, float | str | bool]:
    low_s, high_s = sum_bounds
    span = max(high_s - low_s, 1e-6)
    center = 0.5 * (low_s + high_s)
    sum_dev = min(1.0, abs(sum(comb) - center) / (0.5 * span))

    comb_scores = np.array([scores.get(x, 0.0) for x in comb], dtype=float)
    score_spread = min(1.0, float(np.std(comb_scores)) * 2.0)

    friction_a = round(float(PARITY_A * (0.6 * sum_dev + 0.4 * score_spread) * 1.4), 4)
    regime = "PANIC_JAMMING" if friction_a >= threshold_a else "NULL_DRIFT"
    marginal_stability = (friction_a < threshold_a) and (low_s <= sum(comb) <= high_s)

    return {
        "friction_a": friction_a,
        "passive_b": round(max(0.0, 1.0 - friction_a), 4),
        "regime": regime,
        "marginal_stability": marginal_stability,
    }


def sort_variants(
    variants: list[tuple[list[int], float, int, int]],
    scores: dict[int, float],
    sum_bounds: tuple[float, float],
    sort_by: str = "score_parity",
    threshold_a: float = PARITY_A,
) -> list[tuple[list[int], float, int, int]]:
    if not variants or sort_by == "none":
        return variants

    def _sort_key(item: tuple[list[int], float, int, int]):
        comb, avg_sc, _, _ = item
        info = evaluate_substrate_parity(comb, scores, sum_bounds, threshold_a)
        a_val = float(info["friction_a"])
        is_stable = 0 if bool(info["marginal_stability"]) else 1

        if sort_by == "friction":
            return (a_val, -avg_sc, comb)
        if sort_by == "score":
            return (-avg_sc, a_val, comb)
        return (is_stable, a_val, -avg_sc, comb)

    return sorted(variants, key=_sort_key)


def generate_random_variants_from_pool(
    pool: list[int],
    scores: dict[int, float],
    n_variants: int = 5,
    max_overlap: int = 3,
    max_num_freq: int = 4,
    sum_bounds: tuple[float, float] = (107.6, 179.3),
    seed: int | None = None,
    max_attempts: int = 10000,
    sort_by: str = "score_parity",
) -> list[tuple[list[int], float, int, int]]:
    if len(pool) < 6 or n_variants <= 0:
        return []

    rng = np.random.default_rng(seed)
    low_sum, high_sum = sum_bounds
    pool_arr = np.array(pool, dtype=int)

    raw_scores = np.array([scores.get(int(x), 0.0) for x in pool_arr], dtype=float)
    min_sc = float(raw_scores.min())
    weights = (raw_scores - min_sc) + 0.15
    probs = weights / weights.sum()

    selected: list[tuple[list[int], float, int, int]] = []
    selected_sets: list[set[int]] = []
    freq: dict[int, int] = {int(x): 0 for x in pool_arr}

    stages = [
        (True, max_overlap, max_num_freq),
        (True, max_overlap + 1, max_num_freq + 1),
        (False, 5, n_variants),
    ]

    for strict_filter, ov_limit, freq_limit in stages:
        attempts = 0
        while len(selected) < n_variants and attempts < max_attempts:
            attempts += 1
            pick = rng.choice(pool_arr, size=6, replace=False, p=probs)
            comb_sorted = sorted(int(x) for x in pick)
            c_set = set(comb_sorted)

            if any(c_set == prev for prev in selected_sets):
                continue

            evens = sum(1 for x in comb_sorted if x % 2 == 0)
            s = sum(comb_sorted)

            if strict_filter:
                if not (2 <= evens <= 4 and low_sum <= s <= high_sum):
                    continue
            else:
                if not (1 <= evens <= 5 and 60 <= s <= 240):
                    continue

            if any(freq[x] >= freq_limit for x in comb_sorted):
                continue
            if not all(len(c_set & prev_set) <= ov_limit for prev_set in selected_sets):
                continue

            avg_score = float(np.mean([scores.get(x, 0.0) for x in comb_sorted]))
            selected.append((comb_sorted, avg_score, evens, s))
            selected_sets.append(c_set)
            for x in comb_sorted:
                freq[x] += 1

        if len(selected) >= n_variants:
            break

    return sort_variants(selected, scores, sum_bounds, sort_by=sort_by)


def walk_forward_backtest(
    df: pd.DataFrame,
    window: int = 5,
    decay: float = 0.98,
    weights: tuple[float, float, float] = (-0.25, 0.60, 0.15),
    k_list: tuple[int, ...] = (6, 9, 12, 15),
    start_date: str | None = None,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if len(df) <= window:
        return pd.DataFrame(), pd.DataFrame()

    rng = np.random.default_rng(seed)
    universe = np.arange(1, 50)

    start_dt = (
        pd.to_datetime(start_date, format="%Y-%m-%d", errors="raise")
        if start_date
        else None
    )
    row_dts = pd.to_datetime(df["Data"], format="%Y-%m-%d", errors="coerce")

    hits = {k: [] for k in k_list}
    rand_hits = {k: [] for k in k_list}
    step_records = []

    for t in range(window, len(df)):
        if start_dt is not None and (
            pd.isna(row_dts.iloc[t]) or row_dts.iloc[t] < start_dt
        ):
            continue

        hist = df.iloc[:t]
        actual = set(int(v) for v in df.iloc[t][NUM_COLS].values)
        ranked, _ = compute_ranked_numbers(
            hist, window=window, decay=decay, weights=weights
        )

        rec = {"Step": t, "Data": df.iloc[t]["Data"]}
        for k in k_list:
            safe_k = min(k, 49)
            h = len(set(ranked[:safe_k]) & actual)
            rand_pick = set(int(x) for x in rng.choice(universe, size=safe_k, replace=False))
            rh = len(rand_pick & actual)

            hits[k].append(h)
            rand_hits[k].append(rh)
            rec[f"Top_{k}"] = h
            rec[f"Rand_{k}"] = rh
        step_records.append(rec)

    if not step_records:
        return pd.DataFrame(), pd.DataFrame()

    summary_rows = []
    for k in k_list:
        arr = np.array(hits[k], dtype=float)
        rand_arr = np.array(rand_hits[k], dtype=float)
        mean_score = float(arr.mean())
        mean_rand = float(rand_arr.mean())
        summary_rows.append(
            {
                "Top_K": k,
                "Semnale": len(arr),
                "Medie_Ghicite": round(mean_score, 4),
                "Random_Medie": round(mean_rand, 4),
                "Delta_Medie": round(mean_score - mean_rand, 4),
                "Max_Ghicite": int(arr.max()),
                "Rata_Hit>=1_%": round(float((arr >= 1).mean() * 100), 2),
                "Rata_Hit>=2_%": round(float((arr >= 2).mean() * 100), 2),
            }
        )

    return pd.DataFrame(summary_rows), pd.DataFrame(step_records)


def save_backtest_results(
    summary_df: pd.DataFrame,
    steps_df: pd.DataFrame,
    summary_csv: Path | str = BASE_DIR / "backtest_rezumat.csv",
    steps_csv: Path | str = BASE_DIR / "backtest_detalii.csv",
) -> None:
    if not summary_df.empty:
        summary_df.to_csv(Path(summary_csv), index=False, encoding="utf-8")
    if not steps_df.empty:
        steps_df.to_csv(Path(steps_csv), index=False, encoding="utf-8")


if __name__ == "__main__":
    BACKTEST_START_DATE = "2026-01-01"
    df_arhiva = load_archive(DEFAULT_CSV_PATH, allow_github_download=True)

    if df_arhiva.empty:
        print(f"Nu s-au putut incarca datele din {DEFAULT_CSV_PATH}.")
    else:
        print(f"Extrageri: {len(df_arhiva)}")
        print(
            f"Ultima: {df_arhiva.iloc[-1]['Data']} -> "
            f"{[int(df_arhiva.iloc[-1][c]) for c in NUM_COLS]}\n"
        )

        hot_20, cold_df = get_hot_cold_stats(df_arhiva, recent_draws=20)
        hot_50, _ = get_hot_cold_stats(df_arhiva, recent_draws=50)

        print("Top 5 Fierbinti (20 trageri):")
        print(hot_20.head(5).to_string(index=False), "\n")

        print("Top 5 Fierbinti (50 trageri):")
        print(hot_50.head(5).to_string(index=False), "\n")

        print("Top 5 Reci (absente):")
        print(cold_df.head(5).to_string(index=False), "\n")

        ranked_nums, num_scores = compute_ranked_numbers(df_arhiva)
        low_b, high_b = compute_dynamic_sum_bounds(df_arhiva)
        variants = generate_random_variants_from_pool(
            pool=ranked_nums[:18],
            scores=num_scores,
            n_variants=5,
            sum_bounds=(low_b, high_b),
            seed=None,
            sort_by="score_parity",
        )

        print(f"Suma: {low_b:.1f}-{high_b:.1f} | Prag a={PARITY_A}")
        for idx, (comb, sc, ev, s) in enumerate(variants, 1):
            p_info = evaluate_substrate_parity(
                comb, num_scores, (low_b, high_b), threshold_a=PARITY_A
            )
            print(f"V{idx}: {comb} | Sc:{sc:.3f} P:{ev} S:{s}")
            print(f"    a(t)={p_info['friction_a']:.4f} [{p_info['regime']}]")

        summary_bt, steps_bt = walk_forward_backtest(
            df_arhiva, start_date=BACKTEST_START_DATE
        )
        if not summary_bt.empty:
            save_backtest_results(summary_bt, steps_bt)
            label_start = BACKTEST_START_DATE if BACKTEST_START_DATE else "inceput"
            print(f"\nBacktest (din {label_start}):")
            print(summary_bt.to_string(index=False))
            print("\nSalvat: backtest_rezumat.csv, backtest_detalii.csv")
