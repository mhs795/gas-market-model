"""
Extract AEMO 2026 GSOO *Step Change* demand data into tidy intermediate CSVs.

Source workbooks (downloaded into data/other data/2026 GSOO/2026-gsoo-supply-data/):
  - 2026-gsoo-report-figures-and-data.xlsx   annual sector consumption + GPG seasonal max
  - 2026-gsoo-daily-maximum-demand-summary.xlsx  regional summer/winter peak demand

The GSOO GPG/RC&I/Industrial/LNG forecasts are built on the Draft 2026 ISP optimal
development path (gas-regionalised, calendar year, weather-averaged). We take the
Step Change scenario as the central case for the gas market model; the model's own
scenario levers (Winter, LNG, ADGSM) then layer on top.

Outputs (data/gsoo/):
  - annual_sector_stepchange.csv   Year, Sector, PJ_per_year   (NEM/ECGM national totals)
  - gpg_seasonal_max_stepchange.csv Year, SummerMax_TJd, WinterMax_TJd  (NEM+NT)
  - regional_peak_stepchange.csv   Year, Region, Season, GPG_TJd, RCI_TJd
"""
import os
import pandas as pd

BASE = os.path.dirname(__file__)
DATA = os.path.join(BASE, "data")
SRC = os.path.join(DATA, "other data", "2026 GSOO", "2026-gsoo-supply-data")
FIG = os.path.join(SRC, "2026-gsoo-report-figures-and-data.xlsx")
DMX = os.path.join(SRC, "2026-gsoo-daily-maximum-demand-summary.xlsx")
OUT = os.path.join(DATA, "gsoo")

REGIONS = ["NSW", "NT", "QLD", "SA", "TAS", "VIC"]


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def extract_annual_sectors():
    """Annual national consumption (PJ/y), Step Change, by sector."""
    rows = []

    # Figure 2 & 22 -- GPG. col1=year, col7=2026 GSOO NEM PJ/y, col8=NT PJ/y,
    # col9=summer max TJ/d, col10=winter max TJ/d.
    f2 = pd.read_excel(FIG, sheet_name="Figure 2 & 22", header=None)
    seasonal = []
    for i in range(len(f2)):
        yr = _num(f2.iat[i, 1])
        if yr is None or not (2019 <= yr <= 2050):
            continue
        nem = _num(f2.iat[i, 7])
        nt = _num(f2.iat[i, 8])
        if nem is not None:
            rows.append((int(yr), "GPG_NEM", nem))
        if nt is not None:
            rows.append((int(yr), "GPG_NT", nt))
        smax, wmax = _num(f2.iat[i, 9]), _num(f2.iat[i, 10])
        if smax is not None or wmax is not None:
            seasonal.append((int(yr), smax, wmax))

    # Figures 17 (res/comm), 18 (industrial), 19 (LNG): col1=year, col4=2026 GSOO Step Change.
    for sheet, hdr, sector in [("Figure 17", 21, "ResComm"),
                               ("Figure 18", 23, "Industrial"),
                               ("Figure 19", 23, "LNG")]:
        df = pd.read_excel(FIG, sheet_name=sheet, header=None)
        assert "Step Change" in str(df.iat[hdr, 4]), f"{sheet}: col4 not Step Change"
        for i in range(hdr + 1, len(df)):
            yr = _num(df.iat[i, 1])
            val = _num(df.iat[i, 4])
            if yr is not None and 2019 <= yr <= 2050 and val is not None:
                rows.append((int(yr), sector, val))

    annual = pd.DataFrame(rows, columns=["Year", "Sector", "PJ_per_year"])
    seasonal_df = pd.DataFrame(seasonal, columns=["Year", "SummerMax_TJd", "WinterMax_TJd"])
    return annual, seasonal_df


def extract_regional_peaks():
    """Regional summer/winter peak GPG and RC&I (TJ/d), Step Change scenario block."""
    def _read_sheet(sheet):
        raw = pd.read_excel(DMX, sheet_name=sheet, header=None)
        # Find the "Step Change" banner; data years start 2 rows below the GPG/RC&I header.
        sc_row = next(i for i in range(len(raw))
                      if str(raw.iat[i, 0]).strip() == "Step Change")
        # header rows: season banner, region row, GPG/RC&I row -> data begins after.
        # Locate the GPG/RC&I sub-header row after sc_row.
        sub = next(i for i in range(sc_row, sc_row + 8)
                   if str(raw.iat[i, 2]).strip() == "GPG")
        recs = []
        for i in range(sub + 1, sub + 1 + 20):  # 2026..2045
            yr = _num(raw.iat[i, 1])
            if yr is None or not (2026 <= yr <= 2045):
                break
            # Summer block: regions at cols 2,4,6,8,10,12 (GPG); winter at 14,16,...,24
            for season, base in [("Summer", 2), ("Winter", 14)]:
                for r, reg in enumerate(REGIONS):
                    gpg = _num(raw.iat[i, base + 2 * r])
                    rci = _num(raw.iat[i, base + 2 * r + 1])
                    recs.append((int(yr), reg, season, gpg, rci))
        return pd.DataFrame(recs, columns=["Year", "Region", "Season", "GPG_TJd", "RCI_TJd"])

    # "Regional GPG Max" = demand at the time each region's GPG peaks (best basis for GPG peak).
    return _read_sheet("Regional GPG Max")


def main():
    os.makedirs(OUT, exist_ok=True)
    annual, seasonal = extract_annual_sectors()
    regional = extract_regional_peaks()

    annual.to_csv(os.path.join(OUT, "annual_sector_stepchange.csv"), index=False)
    seasonal.to_csv(os.path.join(OUT, "gpg_seasonal_max_stepchange.csv"), index=False)
    regional.to_csv(os.path.join(OUT, "regional_peak_stepchange.csv"), index=False)

    print("=== Annual national consumption (PJ/y), Step Change ===")
    piv = annual.pivot(index="Year", columns="Sector", values="PJ_per_year")
    print(piv.round(1).to_string())
    print("\n=== GPG NEM+NT seasonal max (TJ/d) ===")
    print(seasonal.set_index("Year").round(0).to_string())
    print("\n=== Regional GPG peak (TJ/d), winter, sample years ===")
    w = regional[regional.Season == "Winter"].pivot(index="Year", columns="Region", values="GPG_TJd")
    print(w.round(0).to_string())
    print("\nWrote 3 CSVs to", OUT)


if __name__ == "__main__":
    main()
