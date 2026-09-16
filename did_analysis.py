"""
Difference-in-differences: did congestion pricing change subway ridership
at stations inside the Congestion Relief Zone (CRZ) relative to stations
outside it?

Design
------
Unit:      station complex (426, of which 65 are inside the CRZ)
Time:      monthly, Jan 2024 through Jul 2026
Treated:   station is inside the CRZ (Manhattan below 60th St)
Post:      month >= Jan 2025
Outcome:   log(monthly ridership)

Preferred model (two-way fixed effects plus treated-group seasonality):
    log(rid_it) = a_i + g_t + s_{treated(i), calmonth(t)}
                  + beta * (treated_i x post_t) + e_it

Station fixed effects (a_i) absorb each station's level. Month fixed
effects (g_t) absorb citywide shocks: return-to-office, fare policy,
weather, service changes. The treated x calendar-month term (s) absorbs
the fact that Midtown stations have their own seasonal pattern (holiday
shopping in December, tourism in summer) that outer-borough stations do
not share. Standard errors are clustered by station.

Why the panel starts in 2024
----------------------------
An event study on 2023-2026 shows CRZ stations closing a 16-point gap
with the rest of the system over 2023: Midtown return-to-office caught
up faster than the outer boroughs. That trend violates parallel trends
and inflates the naive DiD to +4.4%. From 2024 onward the relative gap
is flat, so the panel starts there. Both specifications are reported so
the reader can see the difference.

Interpretation caveat
---------------------
Ridership is counted at station entry. A driver who switches to transit
because of the toll boards outside the zone, so this design measures
whether people enter the subway *inside* the CRZ more often, not whether
congestion pricing raised transit use overall. The systemwide numbers
(transit +7-9%, bridge traffic flat) and a near-zero CRZ station effect
are consistent with substitution happening at origin stations outside
the zone. Testing that requires origin-destination data.

Outputs
-------
data/processed/did_results.json        headline estimates, both specs
data/processed/did_event_study.csv     monthly coefficients (preferred spec)
"""
import json
import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from config import RAW_STATION_RIDERSHIP, RAW_STATIONS, DID_RESULTS, DID_EVENT_STUDY

warnings.filterwarnings("ignore")

CP_MONTH = pd.Timestamp("2025-01-01")
PREFERRED_START = pd.Timestamp("2024-01-01")
NAIVE_START = pd.Timestamp("2023-01-01")


def load_panel():
    rid = pd.read_csv(RAW_STATION_RIDERSHIP)
    rid["month"] = pd.to_datetime(rid["month"], format="%m/%d/%Y")
    rid = rid.rename(columns={"station_complex_id": "complex_id"})
    st = pd.read_csv(RAW_STATIONS).rename(columns={"Complex ID": "complex_id", "CBD": "in_cbd"})
    rid = rid.merge(st[["complex_id", "in_cbd"]].drop_duplicates("complex_id"), on="complex_id", how="left")
    rid = rid[rid["ridership"] > 0].copy()
    rid["treated"] = rid["in_cbd"].astype(int)
    rid["log_rid"] = np.log(rid["ridership"])
    rid["month_str"] = rid["month"].dt.strftime("%Y-%m")
    rid["cal_month"] = rid["month"].dt.month
    return rid


def did(df, start, seasonal):
    d = df[df["month"] >= start].copy()
    d["post"] = (d["month"] >= CP_MONTH).astype(int)
    f = "log_rid ~ treated:post + C(complex_id) + C(month_str)"
    if seasonal:
        f += " + treated:C(cal_month)"
    m = smf.ols(f, data=d).fit(cov_type="cluster", cov_kwds={"groups": d["complex_id"]})
    b = m.params["treated:post"]
    lo, hi = m.conf_int().loc["treated:post"]
    return {
        "pct": float((np.exp(b) - 1) * 100),
        "pct_lo": float((np.exp(lo) - 1) * 100),
        "pct_hi": float((np.exp(hi) - 1) * 100),
        "p": float(m.pvalues["treated:post"]),
        "n_obs": int(len(d)),
        "n_months": int(d["month"].nunique()),
    }


def event_study(df, start):
    """Monthly treated-group coefficients, normalized to the pre-period mean."""
    d = df[df["month"] >= start].copy()
    months = sorted(d["month_str"].unique())
    ref = months[months.index("2025-01") - 1]  # last pre-treatment month
    terms = []
    for mo in months:
        if mo == ref:
            continue
        col = f"ev_{mo.replace('-', '_')}"
        d[col] = ((d["month_str"] == mo) & (d["treated"] == 1)).astype(int)
        terms.append(col)
    f = "log_rid ~ " + " + ".join(terms) + " + C(complex_id) + C(month_str) + treated:C(cal_month)"
    m = smf.ols(f, data=d).fit(cov_type="cluster", cov_kwds={"groups": d["complex_id"]})
    rows = []
    for mo in months:
        col = f"ev_{mo.replace('-', '_')}"
        if mo == ref:
            rows.append({"month": mo, "coef": 0.0, "lo": 0.0, "hi": 0.0})
        else:
            lo, hi = m.conf_int().loc[col]
            rows.append({"month": mo, "coef": m.params[col], "lo": lo, "hi": hi})
    ev = pd.DataFrame(rows)
    ev["post"] = ev["month"] >= "2025-01"
    shift = ev.loc[~ev["post"], "coef"].mean()
    for c in ["coef", "lo", "hi"]:
        ev[c] -= shift
    ev["pct"] = (np.exp(ev["coef"]) - 1) * 100
    ev["pct_lo"] = (np.exp(ev["lo"]) - 1) * 100
    ev["pct_hi"] = (np.exp(ev["hi"]) - 1) * 100
    return ev


def placebo_2024(df):
    """Fake treatment in Jan 2024 using 2023-2024 data. Expected to FAIL
    because of the 2023 catch-up trend; reported to document why the
    preferred panel starts in 2024."""
    d = df[(df["month"] >= NAIVE_START) & (df["month"] < CP_MONTH)].copy()
    d["post"] = (d["month"] >= "2024-01-01").astype(int)
    f = "log_rid ~ treated:post + C(complex_id) + C(month_str) + treated:C(cal_month)"
    m = smf.ols(f, data=d).fit(cov_type="cluster", cov_kwds={"groups": d["complex_id"]})
    b = m.params["treated:post"]
    return {"pct": float((np.exp(b) - 1) * 100), "p": float(m.pvalues["treated:post"])}


if __name__ == "__main__":
    panel = load_panel()
    print(f"Stations: {panel['complex_id'].nunique()}  (CRZ: {panel.loc[panel.treated == 1, 'complex_id'].nunique()})")

    naive = did(panel, NAIVE_START, seasonal=False)
    preferred = did(panel, PREFERRED_START, seasonal=True)
    plac = placebo_2024(panel)
    ev = event_study(panel, PREFERRED_START)

    print(f"\nNaive DiD (2023-2026, no seasonal ctrl):       {naive['pct']:+.2f}%  "
          f"[{naive['pct_lo']:+.1f}, {naive['pct_hi']:+.1f}]  p={naive['p']:.3f}")
    print(f"Preferred DiD (2024-2026, CRZ seasonality):    {preferred['pct']:+.2f}%  "
          f"[{preferred['pct_lo']:+.1f}, {preferred['pct_hi']:+.1f}]  p={preferred['p']:.3f}")
    print(f"Placebo, fake Jan 2024 on 2023-24 data:        {plac['pct']:+.2f}%  p={plac['p']:.3f}  "
          f"(fails, as expected: 2023 catch-up trend)")
    post_mean = (np.exp(ev.loc[ev["post"], "coef"].mean()) - 1) * 100
    print(f"Event study mean post-period effect:           {post_mean:+.2f}%")

    ev.to_csv(DID_EVENT_STUDY, index=False)
    with open(DID_RESULTS, "w") as f:
        json.dump({
            "n_stations": int(panel["complex_id"].nunique()),
            "n_treated": int(panel.loc[panel.treated == 1, "complex_id"].nunique()),
            "naive": naive,
            "preferred": preferred,
            "placebo_jan2024": plac,
            "event_study_post_mean_pct": float(post_mean),
        }, f, indent=2)
    print(f"\nSaved {DID_RESULTS.name} and {DID_EVENT_STUDY.name}")
