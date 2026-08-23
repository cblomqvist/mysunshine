"""Swedish electricity tariff and tax calculation engine.

Calculates exact import costs and export revenues for SE3 bidding zone
under Tibber dynamic spot contract and Eskilstuna Energi & Miljö (EEM) grid.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TariffConfig:
    """Configuration parameters for Swedish electricity pricing model.

    All currency amounts are in SEK unless specified otherwise.
    """
    # Grid Import variable components (SEK/kWh ex. moms)
    energiskatt_sek_per_kwh: float = 0.428        # Swedish energy tax (42.8 öre/kWh ex. moms)
    eem_transfer_fee_sek_per_kwh: float = 0.176   # EEM överföringsavgift (~17.6 öre/kWh ex. moms)
    tibber_markup_sek_per_kwh: float = 0.020      # Tibber variable markup + elcertifikat (~2.0 öre/kWh)

    # VAT / Moms
    moms_rate: float = 0.25                       # 25% Swedish VAT applied to import components

    # Grid Export variable components (SEK/kWh)
    eem_grid_benefit_sek_per_kwh: float = 0.080   # EEM nätnytta (~8.0 öre/kWh, tax-free for microproducers)
    tax_reduction_sek_per_kwh: float = 0.600      # Skattereduktion för mikroproduktion (60 öre/kWh, 2021-2025)
    enable_tax_reduction: bool = True             # Toggle skattereduktion (60 öre/kWh)
    tax_reduction_end_date: Optional[str] = "2026-01-01"  # Abolished effective 1 January 2026

    # Fixed monthly costs (SEK/month incl. moms)
    tibber_monthly_fee_sek: float = 49.0          # Tibber subscription (49 SEK/mo incl. moms)
    eem_monthly_fee_sek: float = 0.0              # EEM grid connection fuse base fee (if separated)


class SwedishTariff:
    """Calculates Swedish import costs and export revenues based on spot prices."""

    def __init__(self, config: Optional[TariffConfig] = None):
        self.config = config or TariffConfig()

    def get_import_price(self, spot_price_sek_per_kwh: float) -> float:
        """Calculate the total consumer import price in SEK/kWh (incl. all taxes, grid fees, and VAT).

        Formula:
            (SpotPrice + TibberMarkup + Energiskatt + EEMTransferFee) * (1 + Moms)
        """
        ex_vat = (
            spot_price_sek_per_kwh
            + self.config.tibber_markup_sek_per_kwh
            + self.config.energiskatt_sek_per_kwh
            + self.config.eem_transfer_fee_sek_per_kwh
        )
        return ex_vat * (1.0 + self.config.moms_rate)

    def get_import_price_ore(self, spot_price_ore_per_kwh: float) -> float:
        """Calculate total import price in öre/kWh."""
        spot_sek = spot_price_ore_per_kwh / 100.0
        return self.get_import_price(spot_sek) * 100.0

    def get_export_price(
        self,
        spot_price_sek_per_kwh: float,
        include_tax_reduction: Optional[bool] = None,
        date_str: Optional[str] = None,
    ) -> float:
        """Calculate total export revenue per kWh in SEK/kWh.

        Formula:
            SpotPrice + EEMGridBenefit + (Skattereduktion if enabled and date < 2026-01-01)
        """
        use_reduction = (
            self.config.enable_tax_reduction
            if include_tax_reduction is None
            else include_tax_reduction
        )
        if use_reduction and date_str and self.config.tax_reduction_end_date:
            if date_str >= self.config.tax_reduction_end_date:
                use_reduction = False

        tax_red = self.config.tax_reduction_sek_per_kwh if use_reduction else 0.0
        return spot_price_sek_per_kwh + self.config.eem_grid_benefit_sek_per_kwh + tax_red

    def get_export_price_ore(
        self,
        spot_price_ore_per_kwh: float,
        include_tax_reduction: Optional[bool] = None,
        date_str: Optional[str] = None,
    ) -> float:
        """Calculate total export revenue in öre/kWh."""
        spot_sek = spot_price_ore_per_kwh / 100.0
        return self.get_export_price(spot_sek, include_tax_reduction, date_str) * 100.0

    def calculate_import_cost(
        self,
        imported_kwh: float,
        spot_price_sek_per_kwh: float,
    ) -> float:
        """Calculate total grid import cost in SEK."""
        return imported_kwh * self.get_import_price(spot_price_sek_per_kwh)

    def calculate_export_revenue(
        self,
        exported_kwh: float,
        spot_price_sek_per_kwh: float,
        include_tax_reduction: Optional[bool] = None,
        date_str: Optional[str] = None,
    ) -> float:
        """Calculate total grid export revenue in SEK."""
        return exported_kwh * self.get_export_price(
            spot_price_sek_per_kwh, include_tax_reduction, date_str
        )

    def calculate_fixed_costs(self, months: float = 1.0) -> float:
        """Calculate fixed monthly subscription costs in SEK."""
        return (
            self.config.tibber_monthly_fee_sek + self.config.eem_monthly_fee_sek
        ) * months
