# NYC Transit Ridership: Recovery and Congestion Pricing

Interactive Streamlit dashboard and difference-in-differences analysis of
MTA ridership from the March 2020 collapse through September 2026, with a
station-level look at congestion pricing (launched January 5, 2025).

## Headline findings

- Subway ridership sits at roughly 72 to 80% of its 2019 level on recent
  weekdays; LIRR and Metro-North have recovered furthest, buses least.
- In the 12 months after congestion pricing began, weekday subway, bus,
  and LIRR ridership each rose 7 to 9% year over year, while Bridges and
  Tunnels traffic was flat (+0.8%).
- Stations inside the Congestion Relief Zone show no detectable relative
  change in ridership after the toll: a difference-in-differences
  estimate of +1.3% (95% CI -1.7% to +4.4%, p = 0.41) on the full panel,
  or +1.7% (95% CI -1.3% to +4.7%, p = 0.27) excluding one flagged
  station (see below); the two are close, so the flagged station isn't
  driving the result either way. A naive version of the regression
  gives +4.4%, but that number is driven by Midtown's faster
  return-to-office recovery during 2023, not by the toll.
- These are consistent with each other: ridership is counted at station
  entry, so drivers who switched to transit board outside the zone.
  Isolating that effect needs origin-destination data.

## Project layout

```
app.py                  Streamlit dashboard
config.py               all file paths in one place
clean_data.py           daily systemwide data + reconstructed 2019 baseline
build_geo_data.py       station snapshot + pre/post comparison for the maps
did_analysis.py         difference-in-differences with event study and placebo
data/raw/               raw downloads (gitignored; see data/raw/README.md)
data/processed/         outputs of the three scripts (committed)
```

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py          # works immediately using data/processed/
```

To rebuild from raw data, drop the four source files into `data/raw/`
(names in `config.py`) and run:

```bash
python clean_data.py
python build_geo_data.py
python did_analysis.py
```

## Data

All from MTA Open Data via data.ny.gov:

| Dataset | ID | Used for |
|---|---|---|
| MTA Daily Ridership and Traffic: Beginning 2020 | `sayj-mze2` | Daily counts by mode, CRZ/CBD entries |
| MTA Daily Ridership Data (deprecated) | `vxuj-8kew` | MTA's published pre-pandemic ratios, used to reconstruct the 2019 baseline |
| MTA Subway Station Monthly Ridership | `ak4z-sape` | Station panel for maps and DiD |
| MTA Subway Stations and Complexes | `5f5g-n3cz` | Congestion Relief Zone flag, coordinates |

## Methodology

**Pre-pandemic baseline.** The current daily dataset no longer ships a
"% of comparable pre-pandemic day" figure; the deprecated version did,
through January 9, 2025. Since that ratio equals ridership divided by the
matched 2019 day, the implied 2019 baseline is `ridership / ratio`. The
pipeline takes the median implied baseline by mode, calendar month, and
day of week over 2022 to 2024 and applies it forward. On the overlap
period the reconstructed index is within 1 to 3 percentage points of
MTA's published figure (mean absolute error: subway 0.017, bus 0.015,
LIRR 0.032, Metro-North 0.023, Bridges and Tunnels 0.009).

**Difference-in-differences.** Monthly panel of station complexes (65
inside the CRZ), January 2024 through July 2026. Outcome is log
ridership. Station fixed effects absorb levels; month fixed effects
absorb citywide shocks; a treated-group by calendar-month term absorbs
Midtown's distinct holiday and summer seasonality. Standard errors are
clustered by station. Reported both on the full 426-station panel and
excluding one flagged station (425 stations); see below.

The panel starts in 2024 because an event study on 2023 to 2026 shows
CRZ stations closing a 16-point relative gap during 2023 as Midtown
return-to-office caught up, which violates parallel trends. A placebo
test that pretends the toll began in January 2024 (using only 2023 to
2024 data) finds a spurious +6.2% effect, confirming the problem. From
2024 onward the relative gap is flat.

**Flagged station: Canarsie-Rockaway Pkwy, reported both ways rather
than dropped.** This station (complex 138, outside the CRZ) shows a
~390% ridership jump starting May 2025. This is a documented, dated
event, not a data or code error: the MTA closed a fare-evasion loophole
there, an unfenced bus-to-subway side entrance that let riders walk
onto the platform without tapping, with new turnstiles taking effect
May 16, 2025 that require everyone to tap. Since ridership is measured
from tap data, this mechanically counts riders who were always
physically present but previously invisible to the count; it is not a
real change in foot traffic and is unrelated to congestion pricing.

Rather than exclude it outright, both specifications are reported: the
full 426-station panel (+1.3%) and the 425-station panel excluding this
one (+1.7%). The two are close, which is itself evidence it was not
driving the headline result either way, so reporting both is more
defensible than a single number with the exclusion buried in a code
comment. It remains visible on the station-level map, flagged in the
caption, with the color scale capped at ±40% so this one point doesn't
wash out every other station's much smaller change.

**Known limitations.** Station ridership is estimated from OMNY and
MetroCard entries and excludes fare evasion that has not yet been
addressed by enforcement (the Canarsie-Rockaway Pkwy case above shows
this isn't hypothetical). The CRZ flag is binary; a distance-to-boundary
design would be more informative. Return-to-office and OMNY fare-capping
changes overlap the study window and are absorbed only to the extent
they hit all stations equally.

## Next steps

- Origin-destination analysis: use the MTA O-D dataset to test whether
  trips *ending* inside the CRZ rose after the toll, which is the
  outcome this design cannot see.
- Distance-to-boundary heterogeneity within the CRZ.
- Bridge-and-tunnel crossing-level data, to see which crossings lost
  traffic.
- Check whether other stations had similar fare-gate/enforcement changes
  during the study window that could contaminate the panel the same way
  Canarsie-Rockaway Pkwy did.