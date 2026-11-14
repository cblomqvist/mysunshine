"""Solar Era Ingestion & Empirical Baseline Calibration Module.

Ingests:
1. SMA Inverter solar PV yield logs from Sunny Portal CSV (2021–2026).
2. EEM official export meter readings (UTF-16LE CSV, meter 7359992924582514P).

Calculates exact empirical self-consumption rates (32.0% in 2021, 22.6% in 2022)
and synthesizes daily operational records for the Solar Only era (2021-2022).
"""

import calendar
import csv
import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SolarEraMetrics:
    """Empirical solar yield, grid export, and self-consumption metrics for a period."""
    year: int
    month: Optional[int]
    produced_kwh: float
    exported_kwh: float
    self_consumed_kwh: float
    self_consumption_pct: float


class SMAInverterIngestor:
    """Ingests historical solar generation yield from Sunny Portal SMA Inverter CSV export."""

    def __init__(self, filepath: str):
        self.filepath = filepath

    def parse_monthly_yields(self) -> Dict[int, Dict[int, float]]:
        """Parse the Sunny Portal CSV and return monthly solar PV yield by year and month.

        Returns:
            Dict[year, Dict[month, yield_kwh]]
        """
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"Sunny Portal file not found: {self.filepath}")

        yields_by_year: Dict[int, Dict[int, float]] = {}

        with open(self.filepath, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f, delimiter=";")
            for row in reader:
                if not row or len(row) < 13:
                    continue
                first_cell = row[0].strip().strip('"')
                if first_cell.isdigit() and len(first_cell) == 4:
                    year = int(first_cell)
                    month_data: Dict[int, float] = {}
                    for m in range(1, 13):
                        val_str = row[m].strip().strip('"')
                        if val_str and val_str != "-":
                            # Handle thousand separators e.g. "1,212.76"
                            clean_val = val_str.replace(",", "")
                            try:
                                month_data[m] = float(clean_val)
                            except ValueError:
                                month_data[m] = 0.0
                        else:
                            month_data[m] = 0.0
                    yields_by_year[year] = month_data

        return yields_by_year

    def get_annual_yield(self, year: int) -> float:
        """Return total annual solar yield for a given year in kWh."""
        data = self.parse_monthly_yields()
        if year not in data:
            raise KeyError(f"Year {year} not found in Sunny Portal data")
        return sum(data[year].values())


class EEMMeterIngestor:
    """Ingests official utility meter export readings from Eskilstuna Energi & Miljö (EEM)."""

    TARGET_METER = "7359992924582514P"

    def __init__(self, filepath: str):
        self.filepath = filepath

    def parse_monthly_exports(self) -> Dict[int, Dict[int, float]]:
        """Parse UTF-16LE EEM meter readings CSV and return exported kWh per month.

        Maps 1st-of-the-month meter readings to the preceding calendar month:
        e.g., 2021-02-01 reading represents January 2021 export;
              2022-01-01 reading represents December 2021 export.

        Returns:
            Dict[year, Dict[month, exported_kwh]]
        """
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"EEM meter readings file not found: {self.filepath}")

        # Map each reading date to (stand, diff, note)
        readings_by_date: Dict[str, Tuple[float, float, str]] = {}

        with open(self.filepath, "r", encoding="utf-16le") as f:
            reader = csv.reader(f, delimiter=";")
            for row in reader:
                if not row or len(row) < 7:
                    continue
                meter_id = row[0].strip()
                if meter_id != self.TARGET_METER:
                    continue

                date_str = row[1].strip()
                try:
                    stand = float(row[2].replace(",", "."))
                    diff = float(row[4].replace(",", "."))
                    note = row[6].strip()
                    readings_by_date[date_str] = (stand, diff, note)
                except ValueError:
                    continue

        exports_by_year: Dict[int, Dict[int, float]] = {}

        # Scan across recorded years (2021 through 2026)
        for year in range(2021, 2027):
            month_exports: Dict[int, float] = {}
            for m in range(1, 13):
                # The reading date for month m is (m+1)-01 in year, or 01-01 of (year+1) for December
                if m < 12:
                    reading_date = f"{year}-{m + 1:02d}-01"
                else:
                    reading_date = f"{year + 1}-01-01"

                if reading_date in readings_by_date:
                    month_exports[m] = readings_by_date[reading_date][1]
                else:
                    month_exports[m] = 0.0

            # Only include year if there was non-zero export recorded
            if any(v > 0 for v in month_exports.values()):
                exports_by_year[year] = month_exports

        return exports_by_year

    def get_annual_export(self, year: int) -> float:
        """Return total annual exported energy for a given year in kWh."""
        data = self.parse_monthly_exports()
        if year not in data:
            raise KeyError(f"Year {year} not found in EEM export meter readings")
        return sum(data[year].values())


class SolarEraSynthesizer:
    """Calibrates empirical self-consumption and synthesizes daily Sonnen-format CSV files.

    Enables seamless ingestion of Day-1 historical years (2021-2022) into the MultiYearEngine.
    """

    # Typical seasonal monthly consumption (kWh) for a Swedish detached house (~8,000 kWh/year)
    # Calibrated from actual 2024 (8,462 kWh) & 2025 (7,515 kWh) residential load profiles
    CALIBRATED_MONTHLY_CONSUMPTION: Dict[int, float] = {
        1: 746.7,   # Jan (high winter heating)
        2: 599.9,   # Feb
        3: 633.1,   # Mar
        4: 559.8,   # Apr
        5: 605.4,   # May
        6: 842.2,   # Jun
        7: 797.4,   # Jul
        8: 754.2,   # Aug
        9: 644.7,   # Sep
        10: 577.9,  # Oct
        11: 567.4,  # Nov
        12: 660.6,  # Dec
    }

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.sma_path = os.path.join(data_dir, "sunnyportal-sma-inverter-data-2026-10-24.csv")
        self.eem_path = os.path.join(data_dir, "EEM-meter-readings-402520-2026-10-24-20-10-44-5195.csv")
        self.sma_ingestor = SMAInverterIngestor(self.sma_path)
        self.eem_ingestor = EEMMeterIngestor(self.eem_path)

    def get_empirical_metrics(self, year: int) -> Dict[int, SolarEraMetrics]:
        """Compute exact monthly and annual empirical self-consumption metrics for a given year."""
        yields = self.sma_ingestor.parse_monthly_yields().get(year, {})
        exports = self.eem_ingestor.parse_monthly_exports().get(year, {})

        metrics: Dict[int, SolarEraMetrics] = {}
        for m in range(1, 13):
            prod = yields.get(m, 0.0)
            exp = exports.get(m, 0.0)
            sc = max(0.0, prod - exp)
            pct = (sc / prod * 100.0) if prod > 0 else 0.0
            metrics[m] = SolarEraMetrics(
                year=year,
                month=m,
                produced_kwh=round(prod, 2),
                exported_kwh=round(exp, 2),
                self_consumed_kwh=round(sc, 2),
                self_consumption_pct=round(pct, 2),
            )
        return metrics

    def get_annual_empirical_summary(self, year: int) -> SolarEraMetrics:
        """Compute the full-year empirical solar generation, export, and self-consumption."""
        monthly = self.get_empirical_metrics(year)
        tot_prod = sum(m.produced_kwh for m in monthly.values())
        tot_exp = sum(m.exported_kwh for m in monthly.values())
        tot_sc = max(0.0, tot_prod - tot_exp)
        pct = (tot_sc / tot_prod * 100.0) if tot_prod > 0 else 0.0
        return SolarEraMetrics(
            year=year,
            month=None,
            produced_kwh=round(tot_prod, 2),
            exported_kwh=round(tot_exp, 2),
            self_consumed_kwh=round(tot_sc, 2),
            self_consumption_pct=round(pct, 2),
        )

    def synthesize_year_csv(self, year: int, output_filepath: Optional[str] = None) -> str:
        """Synthesize daily Sonnen-format CSV for a Solar Only year (2021 or 2022).

        Distributes exact monthly solar yields and export meter readings across days of each month,
        setting battery charge and discharge strictly to 0 Wh.

        Returns:
            Path to the written CSV file.
        """
        metrics = self.get_empirical_metrics(year)
        target_path = output_filepath or os.path.join(self.data_dir, f"sonnen_energy_data_{year}.csv")

        rows = []
        is_leap = calendar.isleap(year)

        for m in range(1, 13):
            days_in_month = calendar.monthrange(year, m)[1]
            m_metrics = metrics[m]
            prod_month = m_metrics.produced_kwh
            exp_month = m_metrics.exported_kwh
            cons_month = self.CALIBRATED_MONTHLY_CONSUMPTION.get(m, 666.0)

            # Daily base values (in Wh)
            base_prod_wh = int((prod_month * 1000.0) // days_in_month)
            rem_prod_wh = int(round((prod_month * 1000.0) - (base_prod_wh * days_in_month)))

            base_exp_wh = int((exp_month * 1000.0) // days_in_month)
            rem_exp_wh = int(round((exp_month * 1000.0) - (base_exp_wh * days_in_month)))

            base_cons_wh = int((cons_month * 1000.0) // days_in_month)
            rem_cons_wh = int(round((cons_month * 1000.0) - (base_cons_wh * days_in_month)))

            for d in range(1, days_in_month + 1):
                # Distribute remainder Wh across first days
                d_prod_wh = base_prod_wh + (1 if d <= rem_prod_wh else 0)
                d_exp_wh = base_exp_wh + (1 if d <= rem_exp_wh else 0)
                d_cons_wh = base_cons_wh + (1 if d <= rem_cons_wh else 0)

                d_sc_wh = max(0, d_prod_wh - d_exp_wh)
                d_imp_wh = max(0, d_cons_wh - d_sc_wh)

                # Determine Swedish local timezone offset (+02:00 for CEST, +01:00 for CET)
                # Daylight saving time runs from last Sunday in March to last Sunday in October
                if m in (4, 5, 6, 7, 8, 9):
                    tz_str = "+02:00"
                elif m in (1, 2, 11, 12):
                    tz_str = "+01:00"
                elif m == 3:
                    tz_str = "+02:00" if d >= 28 else "+01:00"
                else:  # October
                    tz_str = "+02:00" if d < 25 else "+01:00"

                ts_str = f"{year}-{m:02d}-{d:02d}T00:00:00{tz_str}"

                rows.append({
                    "timestamp": ts_str,
                    "measurements_count": 1440,
                    "produced_energy": d_prod_wh,
                    "consumed_energy": d_cons_wh,
                    "battery_charged_energy": 0,
                    "battery_discharged_energy": 0,
                    "grid_feedin_energy": d_exp_wh,
                    "grid_purchase_energy": d_imp_wh,
                })

        fieldnames = [
            "timestamp",
            "measurements_count",
            "produced_energy",
            "consumed_energy",
            "battery_charged_energy",
            "battery_discharged_energy",
            "grid_feedin_energy",
            "grid_purchase_energy",
        ]

        with open(target_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        expected_days = 366 if is_leap else 365
        logger.info("Synthesized %d daily records for Year %d into %s", len(rows), year, target_path)
        assert len(rows) == expected_days, f"Expected {expected_days} days for {year}, got {len(rows)}"
        return target_path
