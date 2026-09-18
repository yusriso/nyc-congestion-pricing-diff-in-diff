"""
MTA Ridership Recovery Dashboard
Run with: streamlit run app.py
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
 
from config import CLEAN_DAILY, STATION_SNAPSHOT, STATION_COMPARISON, DID_RESULTS, DID_EVENT_STUDY
 
st.set_page_config(page_title="MTA Ridership Recovery", page_icon="🚇", layout="wide")
 
CP_START = pd.Timestamp("2025-01-05")
 
MODES = {
    "Subway": "subway",
    "Bus": "bus",
    "LIRR": "lirr",
    "Metro-North": "metro_north",
    "Access-A-Ride": "access_a_ride",
    "Bridges and Tunnels": "bridges_tunnels",
    "Staten Island Railway": "sir",
}
 
# Loosely inspired by MTA line colors, one per mode
MODE_COLORS = {
    "Subway": "#0039A6",
    "Bus": "#FF6319",
    "LIRR": "#00985F",
    "Metro-North": "#B933AD",
    "Access-A-Ride": "#FCCC0A",
    "Bridges and Tunnels": "#EE352E",
    "Staten Island Railway": "#6CBE45",
}
 
 
@st.cache_data
def load_daily():
    return pd.read_csv(CLEAN_DAILY, parse_dates=["Date"])
 
 
@st.cache_data
def load_geo():
    return (
        pd.read_csv(STATION_SNAPSHOT),
        pd.read_csv(STATION_COMPARISON),
    )
 
 
df = load_daily()
snapshot, comparison = load_geo()
 
# ---------------- Sidebar ----------------
st.sidebar.header("Filters")
date_range = st.sidebar.date_input(
    "Date range",
    value=(df["Date"].min().date(), df["Date"].max().date()),
    min_value=df["Date"].min().date(),
    max_value=df["Date"].max().date(),
)
selected_modes = st.sidebar.multiselect(
    "Transit modes", list(MODES), default=["Subway", "Bus", "LIRR", "Metro-North"]
)
view_type = st.sidebar.radio("Trend view", ["Total ridership / traffic", "% of pre-pandemic baseline"])
smooth = st.sidebar.checkbox("7-day rolling average", value=True)
 
if len(date_range) == 2:
    start, end = date_range
    filtered = df[(df["Date"].dt.date >= start) & (df["Date"].dt.date <= end)]
else:
    filtered = df
 
# ---------------- Header ----------------
st.title("🚇 NYC Transit Ridership: Recovery and Congestion Pricing")
st.markdown(
    "Daily ridership across the MTA system from March 2020 through "
    f"{df['Date'].max().strftime('%B %d, %Y')}, with a station-level look at how "
    "congestion pricing (launched January 5, 2025) has played out. "
    "Source: MTA Open Data via data.ny.gov."
)
 
# ---------------- KPIs ----------------
if len(filtered) and selected_modes:
    latest = filtered.iloc[-1]
    cols = st.columns(len(selected_modes))
    for i, m in enumerate(selected_modes):
        k = MODES[m]
        with cols[i]:
            pct = latest[f"{k}_pct_prepandemic"]
            st.metric(
                f"{m}", f"{latest[k]:,.0f}",
                delta=f"{pct*100:.0f}% of pre-pandemic" if pd.notna(pct) else None,
                delta_color="off",
            )
    st.caption(f"Latest day in selected range: {latest['Date'].strftime('%A, %B %d, %Y')}")
 
st.divider()
 
# ---------------- Trend chart ----------------
st.subheader("Ridership over time")
if selected_modes:
    is_pct = view_type.startswith("%")
    cols_to_plot = [f"{MODES[m]}_pct_prepandemic" if is_pct else MODES[m] for m in selected_modes]
    plot_df = filtered[["Date"] + cols_to_plot].copy()
    plot_df.columns = ["Date"] + selected_modes
    if smooth:
        plot_df[selected_modes] = plot_df[selected_modes].rolling(7, min_periods=1).mean()
    long = plot_df.melt(id_vars="Date", var_name="Mode", value_name="Value")
    if is_pct:
        long["Value"] *= 100
 
    fig = px.line(
        long, x="Date", y="Value", color="Mode",
        color_discrete_map=MODE_COLORS,
        labels={"Value": "% of comparable pre-pandemic day" if is_pct else "Daily ridership / traffic"},
    )
    if is_pct:
        fig.add_hline(y=100, line_dash="dash", line_color="gray", annotation_text="2019 baseline")
    if filtered["Date"].min() <= CP_START <= filtered["Date"].max():
        fig.add_vline(x=CP_START.timestamp() * 1000, line_dash="dot", line_color="black",
                      annotation_text="Congestion pricing begins", annotation_position="top left")
    fig.update_layout(hovermode="x unified", legend_title_text="", margin=dict(t=30))
    st.plotly_chart(fig, use_container_width=True)
 
    with st.expander("How the pre-pandemic baseline is computed"):
        st.markdown(
            "MTA's current daily dataset no longer publishes a \"% of comparable pre-pandemic day\" "
            "figure. The deprecated version of the dataset did, through January 9, 2025. Since that "
            "ratio equals ridership divided by the matched 2019 day, the implied 2019 baseline can be "
            "recovered as ridership / ratio. This dashboard takes the median implied baseline by mode, "
            "calendar month, and day of week over 2022 to 2024, then applies it forward. On the overlap "
            "period the reconstructed index lands within 1 to 3 percentage points of MTA's published figure."
        )
else:
    st.info("Select at least one mode in the sidebar.")
 
st.divider()
 
# ---------------- Day of week ----------------
st.subheader("Average ridership by day of week")
if selected_modes:
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow = filtered.groupby("day_of_week")[[MODES[m] for m in selected_modes]].mean().reindex(order)
    dow.columns = selected_modes
    dow_long = dow.reset_index().melt(id_vars="day_of_week", var_name="Mode", value_name="Avg")
    fig2 = px.bar(dow_long, x="day_of_week", y="Avg", color="Mode", barmode="group",
                  color_discrete_map=MODE_COLORS, labels={"day_of_week": "", "Avg": "Average daily count"},
                  category_orders={"day_of_week": order})
    fig2.update_layout(legend_title_text="", margin=dict(t=30))
    st.plotly_chart(fig2, use_container_width=True)
 
st.divider()
 
# ---------------- Congestion pricing ----------------
st.header("Congestion pricing")
cp = df[df["crz_entries"].notna()].copy()
st.markdown(
    f"Vehicle entries into the Congestion Relief Zone (CRZ, Manhattan below 60th Street) and the "
    f"broader Central Business District (CBD), from launch through {cp['Date'].max().strftime('%B %d, %Y')}."
)
 
# Weekly averages so the chart isn't dominated by weekday/weekend noise
cp["week"] = cp["Date"].dt.to_period("W").dt.start_time
weekly = cp.groupby("week")[["crz_entries", "cbd_entries"]].mean().reset_index()
fig3 = px.line(weekly, x="week", y=["crz_entries", "cbd_entries"],
               labels={"value": "Avg daily entries", "week": "", "variable": ""},
               color_discrete_map={"crz_entries": "#EE352E", "cbd_entries": "#0039A6"})
fig3.for_each_trace(lambda t: t.update(name={"crz_entries": "CRZ entries", "cbd_entries": "CBD entries"}[t.name]))
fig3.update_layout(hovermode="x unified", margin=dict(t=30))
st.plotly_chart(fig3, use_container_width=True)
 
# Transit response: 12 months before vs 12 months after, weekday only
pre = df[(df["Date"] >= CP_START - pd.DateOffset(months=12)) & (df["Date"] < CP_START) & (~df["is_weekend"])]
post = df[(df["Date"] >= CP_START) & (df["Date"] < CP_START + pd.DateOffset(months=12)) & (~df["is_weekend"])]
st.markdown("**Weekday averages, 12 months before vs. 12 months after launch**")
cmp_cols = st.columns(4)
for i, m in enumerate(["Subway", "Bus", "LIRR", "Bridges and Tunnels"]):
    k = MODES[m]
    before, after = pre[k].mean(), post[k].mean()
    with cmp_cols[i]:
        st.metric(m, f"{after:,.0f}", delta=f"{(after/before - 1)*100:+.1f}% vs. prior year")
 
st.divider()
 
# ---------------- Station map ----------------
st.header("Station-level view")
geo_view = st.radio("Map", ["Ridership by station (latest month)", "Change since congestion pricing"], horizontal=True)
 
if geo_view.startswith("Ridership"):
    st.caption(f"Monthly ridership by station complex for the most recent month ({snapshot.shape[0]} stations). Red = inside the Congestion Relief Zone.")
    fig_map = px.scatter_map(
        snapshot, lat="latitude", lon="longitude", size="ridership", color="in_cbd",
        hover_name="display_name",
        hover_data={"borough": True, "ridership": ":,", "latitude": False, "longitude": False, "in_cbd": False},
        color_discrete_map={True: "#EE352E", False: "#0039A6"},
        labels={"in_cbd": "In CRZ"}, size_max=28, zoom=9.7,
        center={"lat": 40.73, "lon": -73.94}, map_style="carto-positron", height=650,
    )
    fig_map.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig_map, use_container_width=True)
else:
    st.caption("Average monthly ridership, 12 months before vs. 12 months after January 5, 2025. Blue = grew more, red = grew less or fell.")
    comp = comparison.dropna(subset=["pct_change"]).copy()
 
    # Canarsie-Rockaway Pkwy (complex 138) shows a ~390% jump starting May
    # 2025. This is a known, dated event, not a data or code error: the MTA
    # closed a fare-evasion loophole there (an unfenced bus-to-subway side
    # entrance) with new turnstiles that went into effect May 16, 2025, so
    # riders who previously walked in untapped are now captured in the tap-
    # based ridership count for the first time. It inflates measured
    # ridership without reflecting a real jump in foot traffic, and it lands
    # inside the post-congestion-pricing window, so this station is flagged
    # rather than folded into the comparison at face value.
    COLOR_CAP = 40
    comp["size"] = comp["pct_change"].abs().clip(lower=1, upper=60)
    outliers = comp[comp["pct_change"].abs() > COLOR_CAP]
 
    fig_map2 = px.scatter_map(
        comp, lat="latitude", lon="longitude", size="size", color="pct_change",
        hover_name="display_name",
        hover_data={"borough": True, "avg_monthly_ridership_pre": ":,.0f",
                    "avg_monthly_ridership_post": ":,.0f", "pct_change": ":.1f",
                    "latitude": False, "longitude": False, "size": False},
        color_continuous_scale="RdBu", color_continuous_midpoint=0,
        range_color=[-COLOR_CAP, COLOR_CAP],
        labels={"pct_change": "% change"}, size_max=24, zoom=9.7,
        center={"lat": 40.73, "lon": -73.94}, map_style="carto-positron", height=650,
    )
    fig_map2.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig_map2, use_container_width=True)
 
    cbd_avg = comp.loc[comp["in_cbd"] == True, "pct_change"].mean()
    non_avg = comp.loc[comp["in_cbd"] == False, "pct_change"].mean()
    a, b = st.columns(2)
    a.metric("Avg change, stations inside CRZ", f"{cbd_avg:+.1f}%")
    b.metric("Avg change, stations outside CRZ", f"{non_avg:+.1f}%")
    st.caption(
        "Descriptive comparison only. See the difference-in-differences section below for an estimate "
        "that controls for citywide trends and Midtown-specific seasonality."
    )
    if len(outliers):
        names = ", ".join(f"{r.display_name} ({r.pct_change:+.0f}%)" for r in outliers.itertuples())
        st.caption(
            f"Color scale capped at \u00b1{COLOR_CAP}% so typical stations stay visible. "
            f"Outside that range: {names}."
        )
        if (comp["display_name"] == "Canarsie-Rockaway Pkwy (L)").any():
            st.caption(
                "Canarsie-Rockaway Pkwy's +390% is a known, dated event, not a data error: the MTA "
                "closed a fare-evasion loophole there (an unfenced bus-to-subway side entrance) with "
                "new turnstiles effective May 16, 2025. Riders who previously walked in untapped are "
                "now captured in the tap-based ridership count for the first time, which mechanically "
                "inflates measured ridership without a comparable real change in foot traffic. The "
                "difference-in-differences analysis below reports estimates both with and without this "
                "station, since it falls inside the post-congestion-pricing window."
            )
 
st.divider()
 
# ---------------- Difference-in-differences ----------------
st.header("Did congestion pricing change ridership inside the zone?")
 
import json
with open(DID_RESULTS) as f:
    did = json.load(f)
ev = pd.read_csv(DID_EVENT_STUDY)
 
pref_full, naive_full = did["preferred_full"], did["naive_full"]
pref_excl, naive_excl = did["preferred_excl"], did["naive_excl"]
 
st.markdown(
    f"A difference-in-differences comparison of the {did['n_treated']} stations inside the Congestion "
    f"Relief Zone against those outside it, monthly from January 2024 through July 2026, with station and "
    f"month fixed effects plus a CRZ-specific seasonal adjustment. Reported two ways: the full panel of "
    f"{did['n_stations_full']} stations, and excluding one flagged station (see note below)."
)
 
t1, t2 = st.columns(2)
with t1:
    st.markdown(f"**Full panel ({did['n_stations_full']} stations)**")
    st.metric("Estimate", f"{pref_full['pct']:+.1f}%")
    st.caption(f"95% CI: {pref_full['pct_lo']:+.1f}% to {pref_full['pct_hi']:+.1f}%, p = {pref_full['p']:.2f}")
with t2:
    st.markdown(f"**Excluding {did['flagged_complex_name']} ({did['n_stations_excl']} stations)**")
    st.metric("Estimate", f"{pref_excl['pct']:+.1f}%")
    st.caption(f"95% CI: {pref_excl['pct_lo']:+.1f}% to {pref_excl['pct_hi']:+.1f}%, p = {pref_excl['p']:.2f}")
 
st.markdown(
    f"**Reading:** the two estimates are close, {pref_full['pct']:+.1f}% vs. {pref_excl['pct']:+.1f}%, which "
    f"means the flagged station isn't driving the result either way. Both are statistically indistinguishable "
    f"from zero after controlling for citywide trends and Midtown's own seasonality. A naive version of the "
    f"same regression that starts in 2023 and skips the seasonal adjustment gives {naive_full['pct']:+.1f}% "
    f"(p = {naive_full['p']:.3f}); that larger number is driven by Midtown's faster return-to-office recovery "
    f"during 2023, not by congestion pricing."
)
 
ev_plot = ev.copy()
ev_plot["month"] = pd.to_datetime(ev_plot["month"])
fig_ev = go.Figure()
fig_ev.add_trace(go.Scatter(
    x=pd.concat([ev_plot["month"], ev_plot["month"][::-1]]),
    y=pd.concat([ev_plot["pct_hi"], ev_plot["pct_lo"][::-1]]),
    fill="toself", fillcolor="rgba(0,57,166,0.15)", line=dict(width=0),
    hoverinfo="skip", showlegend=True, name="95% CI",
))
fig_ev.add_trace(go.Scatter(
    x=ev_plot["month"], y=ev_plot["pct"], mode="lines+markers",
    line=dict(color="#0039A6"), name="CRZ vs. non-CRZ, % difference",
))
fig_ev.add_hline(y=0, line_color="gray", line_dash="dash")
fig_ev.add_vline(x=pd.Timestamp("2025-01-01").timestamp() * 1000, line_dash="dot", line_color="black",
                 annotation_text="Congestion pricing", annotation_position="top left")
fig_ev.update_layout(
    yaxis_title="% difference vs. 2024 average",
    xaxis_title="", hovermode="x unified", margin=dict(t=30),
    legend=dict(orientation="h", y=-0.2),
)
st.plotly_chart(fig_ev, use_container_width=True)
st.caption(
    "Event study: each point is the relative ridership of CRZ stations in that month, normalized so the "
    "2024 average is zero. Flat pre-2025 points support the parallel-trends assumption; post-2025 points "
    "show the dynamic effect."
)
 
with st.expander("Why this is the right way to read the station map above"):
    st.markdown(
        "Station ridership counts entries. A driver who switches to the subway because of the toll boards "
        "in Brooklyn, Queens, the Bronx, or on the LIRR and Metro-North, not in Midtown. So the systemwide "
        "numbers (transit up 7 to 9%, bridge traffic flat) and a near-zero effect at CRZ stations are "
        "consistent with each other: substitution shows up at origin stations outside the zone, which this "
        "design cannot isolate. Testing that directly needs MTA's origin-destination dataset, which is the "
        "planned next step.\n\n"
        f"Diagnostics: a placebo test that pretends the toll started in January 2024 (using only 2023 to 2024 "
        f"data) finds a spurious {did['placebo_jan2024']['pct']:+.1f}% effect, which is why the preferred "
        "panel starts in 2024, after the 2023 catch-up trend had flattened.\n\n"
        "**Flagged station, reported both ways:** Canarsie-Rockaway Pkwy shows a ~390% ridership jump "
        "starting May 2025. This traces to the MTA closing a fare-evasion loophole there: an unfenced "
        "bus-to-subway side entrance let riders walk onto the platform without tapping, and new "
        "turnstiles effective May 16, 2025 now require everyone to tap. Since ridership is measured "
        "from tap data, this newly counts riders who were always physically there; it is not a real "
        "change in foot traffic and has nothing to do with congestion pricing. Rather than pick one "
        f"spec, both are reported above: {did['preferred_full']['pct']:+.1f}% with this station included, "
        f"{did['preferred_excl']['pct']:+.1f}% excluding it. The two are close, which is itself evidence "
        "it wasn't driving the headline result."
    )
 
