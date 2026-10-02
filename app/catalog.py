"""Static catalog of the five in-scope HDFC schemes (PRD §5.1)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scheme:
    scheme_id: str
    display_name: str
    category: str
    aliases: tuple[str, ...]
    factsheet_url: str


# Official HDFC AMC documents (verified during Phase 3). Hosts must be allowlisted.
# Never use groww.in.
HDFC_FACTSHEET_HUB = "https://www.hdfcfund.com/mutual-funds/factsheets"

SCHEMES: tuple[Scheme, ...] = (
    Scheme(
        scheme_id="hdfc_large_cap_direct_growth",
        display_name="HDFC Large Cap Fund – Direct Growth",
        category="large_cap",
        aliases=(
            "hdfc large cap fund",
            "hdfc large cap",
            "hdfc large-cap",
            "large cap fund",
            "large-cap fund",
        ),
        factsheet_url=(
            "https://files.hdfcfund.com/s3fs-public/Others/2026-09/"
            "Fund%20Facts%20-%20HDFC%20Large%20Cap%20Fund_August%2026.pdf"
        ),
    ),
    Scheme(
        scheme_id="hdfc_equity_fund_direct_growth",
        display_name="HDFC Flexi Cap Fund – Direct Growth",
        category="flexi_cap",
        aliases=(
            "hdfc equity fund",
            "hdfc flexi cap",
            "hdfc flexi-cap",
            "flexi cap fund",
            "flexi-cap fund",
        ),
        factsheet_url=(
            "https://files.hdfcfund.com/s3fs-public/Others/2026-09/"
            "Fund%20Facts%20-%20HDFC%20Flexi%20Cap%20Fund_August%2026.pdf"
        ),
    ),
    Scheme(
        scheme_id="hdfc_elss_direct_growth",
        display_name="HDFC ELSS Tax Saver Fund – Direct Plan Growth",
        category="elss",
        aliases=(
            "hdfc elss tax saver",
            "hdfc elss",
            "elss tax saver",
            "tax saver fund",
            "elss",
        ),
        factsheet_url=(
            "https://files.hdfcfund.com/s3fs-public/KIM/2025-11/"
            "KIM%20-%20HDFC%20ELSS%20Tax%20Saver%20dated%20November%2021,%202025.pdf"
        ),
    ),
    Scheme(
        scheme_id="hdfc_small_cap_direct_growth",
        display_name="HDFC Small Cap Fund – Direct Growth",
        category="small_cap",
        aliases=(
            "hdfc small cap fund",
            "hdfc small cap",
            "hdfc small-cap",
            "small cap fund",
            "small-cap fund",
        ),
        factsheet_url=(
            "https://files.hdfcfund.com/s3fs-public/Others/2026-09/"
            "Fund%20Facts%20-%20HDFC%20Small%20Cap%20Fund_August%2026.pdf"
        ),
    ),
    Scheme(
        scheme_id="hdfc_balanced_advantage_direct_growth",
        display_name="HDFC Balanced Advantage Fund – Direct Growth",
        category="hybrid",
        aliases=(
            "hdfc balanced advantage fund",
            "hdfc balanced advantage",
            "balanced advantage fund",
            "hdfc baf",
        ),
        factsheet_url=(
            "https://files.hdfcfund.com/s3fs-public/Others/2026-09/"
            "Fund%20Facts%20-%20HDFC%20Balanced%20Advantage%20Fund_Aug%2026.pdf"
        ),
    ),
)

FLEXI_CAP_SCHEME_ID = "hdfc_equity_fund_direct_growth"
SMALL_CAP_SCHEME_ID = "hdfc_small_cap_direct_growth"
LARGE_CAP_SCHEME_ID = "hdfc_large_cap_direct_growth"
ELSS_SCHEME_ID = "hdfc_elss_direct_growth"


def all_schemes() -> tuple[Scheme, ...]:
    return SCHEMES


def get_scheme(scheme_id: str) -> Scheme | None:
    for scheme in SCHEMES:
        if scheme.scheme_id == scheme_id:
            return scheme
    return None
