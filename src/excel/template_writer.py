"""Populate the TPR Excel template with country data, or build from scratch."""
from __future__ import annotations

import io
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
import pandas as pd
from loguru import logger

if TYPE_CHECKING:
    from src.viz.profile import CountryProfile

# ── Sheet configuration ───────────────────────────────────────────────────────
# Each entry: (profile_attribute, sheet_name_hint, ordered_columns_to_write)
SHEET_CONFIG: list[tuple[str, str, list[str]]] = [
    ("patent_applications",        "Patent Applications",              ["year", "resident", "non_resident", "total"]),
    ("patent_grants",              "Patent Grants",                    ["year", "resident", "non_resident", "total"]),
    ("trademark_applications",     "Trademark Applications",           ["year", "resident", "non_resident", "total"]),
    ("trademark_registrations",    "Trademark Registrations",          ["year", "resident", "non_resident", "total"]),
    ("design_applications",        "Industrial Design Applications",   ["year", "resident", "non_resident", "total"]),
    ("design_registrations",       "Industrial Design Registrations",  ["year", "resident", "non_resident", "total"]),
    ("utility_model_applications", "Utility Model Applications",       ["year", "resident", "non_resident", "total"]),
    ("utility_model_grants",       "Utility Model Grants",             ["year", "resident", "non_resident", "total"]),
    ("geographical_indications",   "Geographical Indications",         ["year", "total"]),
    ("ip_services",                "(BOP) Charges for the Use of IP",  ["year", "imports_usd", "exports_usd"]),
]

_HEADER_FONT = Font(bold=True, color="FFFFFF")
_HEADER_FILL = PatternFill("solid", fgColor="005A8C")
_HEADER_ALIGN = Alignment(horizontal="center")

# Summary sheet: (row, title label, source type)
_SUMMARY_ROW_MAP: list[tuple[int, str, str]] = [
    (2,  "Patent Applications",                    "WIPO"),
    (3,  "Patent Grants",                           "WIPO"),
    (4,  "Trademark Applications",                  "WIPO"),
    (5,  "Trademark Registrations",                 "WIPO"),
    (6,  "Industrial Design Applications",          "WIPO"),
    (7,  "Industrial Design Registrations",         "WIPO"),
    (8,  "Utility Model Applications",              "WIPO"),
    (9,  "Utility Model Grants",                    "WIPO"),
    (10, "Geographical Indications",                "WIPO"),
    (11, "Charges for the Use of IP (USD million)", "WTO"),
]
_WIPO_SOURCE = "WIPO IP Statistics Data Center. Viewed at: https://www3.wipo.int/ipstats ({date})."
_WTO_SOURCE  = "WTO Stats Portal. Viewed at: https://stats.wto.org/ ({date})."


# ── Public entry point ────────────────────────────────────────────────────────

def write_country_workbook(
    profile: "CountryProfile",
    template_path: Path | None = None,
) -> io.BytesIO:
    """Populate the TPR template and return a BytesIO ready for download.

    Falls back to building a workbook from scratch if the template is absent.
    """
    tp = template_path or Path("templates") / "TPR_IP_Template.xlsx"

    if tp.exists():
        logger.info(f"Opening template: {tp}")
        wb = openpyxl.load_workbook(tp)
        _populate_template(wb, profile)
    else:
        logger.warning("Template not found — building workbook from scratch")
        wb = _build_scratch(profile)

    return _to_buffer(wb)


# ── Template population ───────────────────────────────────────────────────────

_YEARS_TO_WRITE = 7


def _populate_template(wb: openpyxl.Workbook, profile: "CountryProfile") -> None:
    display_start = profile.end_year - (_YEARS_TO_WRITE - 1)
    _populate_summary(wb, profile, start_year=display_start)
    data_map = _build_data_map(profile)
    for sheet_idx, (attr, hint, columns) in enumerate(SHEET_CONFIG, start=1):
        ws = _find_sheet(wb, sheet_idx, hint)
        if ws is None:
            logger.warning(f"Sheet {sheet_idx} ({hint!r}) not found — skipping")
            continue
        df = _latest_years(data_map.get(attr, pd.DataFrame()), _YEARS_TO_WRITE)
        _clear_rows(ws, start_row=2)
        if not df.empty:
            _write_rows(ws, df, columns, start_row=2)
            logger.info(f"Sheet '{ws.title}': wrote {len(df)} rows")


def _populate_summary(
    wb: openpyxl.Workbook,
    profile: "CountryProfile",
    start_year: int | None = None,
) -> None:
    if "Summary" not in wb.sheetnames:
        logger.warning("Summary sheet not found — skipping title population")
        return
    ws = wb["Summary"]
    pulled = date.today().strftime("%d/%m/%Y")
    year_range = f"{start_year or profile.start_year}-{profile.end_year}"

    for row, label, source_type in _SUMMARY_ROW_MAP:
        ws[f"D{row}"] = f"{profile.country_name} {label}: {year_range}"
        source_tmpl = _WIPO_SOURCE if source_type == "WIPO" else _WTO_SOURCE
        ws[f"E{row}"] = source_tmpl.format(date=pulled)

    logger.info(f"Summary sheet: populated titles for {profile.country_name} ({year_range}, pulled {pulled})")


def _find_sheet(
    wb: openpyxl.Workbook, index: int, hint: str
) -> openpyxl.worksheet.worksheet.Worksheet | None:
    names = wb.sheetnames
    # Exact name match (most reliable)
    if hint in names:
        return wb[hint]
    # Keyword fallback
    hint_words = hint.lower().split()
    for name in names:
        if any(w in name.lower() for w in hint_words):
            return wb[name]
    # Index-based last resort: 1-based, skipping Summary at position 0
    if 1 <= index <= len(names) - 1:
        return wb[names[index]]
    return None


# ── Scratch workbook ──────────────────────────────────────────────────────────

def _build_scratch(profile: "CountryProfile") -> openpyxl.Workbook:
    """Create a plain workbook with data + styled headers (no charts)."""
    wb = openpyxl.Workbook()
    # Remove default empty sheet
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]

    data_map = _build_data_map(profile)
    sheet_display_names = [
        "Patent Applications",
        "Patent Grants",
        "Trademark Applications",
        "Trademark Registrations",
        "Industrial Design Applications",
        "Industrial Design Registrations",
        "Utility Model Applications",
        "Utility Model Grants",
        "Geographical Indications",
        "(BOP) Charges for the Use of IP",
    ]

    for (attr, _hint, columns), sheet_name in zip(SHEET_CONFIG, sheet_display_names):
        ws = wb.create_sheet(title=sheet_name)
        df = data_map.get(attr, pd.DataFrame())
        available = [c for c in columns if not df.empty and c in df.columns] or columns

        # Write styled header row
        for col_idx, col_name in enumerate(available, start=1):
            cell = ws.cell(row=1, column=col_idx, value=_header_label(col_name))
            cell.font = _HEADER_FONT
            cell.fill = _HEADER_FILL
            cell.alignment = _HEADER_ALIGN

        if not df.empty:
            _write_rows(ws, df, available, start_row=2)

        # Auto-width
        for col_idx in range(1, len(available) + 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = 18

    return wb


def _header_label(col_name: str) -> str:
    return col_name.replace("_", " ").title().replace("Usd", "USD")


# ── Low-level write helpers ───────────────────────────────────────────────────

def _latest_years(df: pd.DataFrame, n: int) -> pd.DataFrame:
    if df.empty or "year" not in df.columns:
        return df
    return df.sort_values("year").tail(n).reset_index(drop=True)


def _clear_rows(ws: openpyxl.worksheet.worksheet.Worksheet, start_row: int = 2) -> None:
    if ws.max_row < start_row:
        return
    for row in ws.iter_rows(min_row=start_row, max_row=ws.max_row):
        for cell in row:
            cell.value = None


def _write_rows(
    ws: openpyxl.worksheet.worksheet.Worksheet,
    df: pd.DataFrame,
    columns: list[str],
    start_row: int = 2,
) -> None:
    available = [c for c in columns if c in df.columns]
    for row_offset, (_, row_data) in enumerate(df[available].iterrows()):
        for col_idx, col_name in enumerate(available, start=1):
            val = row_data[col_name]
            ws.cell(
                row=start_row + row_offset,
                column=col_idx,
                value=None if pd.isna(val) else val,
            )


# ── Data map builder ──────────────────────────────────────────────────────────

def _build_data_map(profile: "CountryProfile") -> dict[str, pd.DataFrame]:
    return {
        "patent_applications":        getattr(profile, "patent_applications",        pd.DataFrame()),
        "patent_grants":              getattr(profile, "patent_grants",              pd.DataFrame()),
        "trademark_applications":     getattr(profile, "trademark_applications",     pd.DataFrame()),
        "trademark_registrations":    getattr(profile, "trademark_registrations",    pd.DataFrame()),
        "design_applications":        getattr(profile, "design_applications",        pd.DataFrame()),
        "design_registrations":       getattr(profile, "design_registrations",       pd.DataFrame()),
        "utility_model_applications": getattr(profile, "utility_model_applications", pd.DataFrame()),
        "utility_model_grants":       getattr(profile, "utility_model_grants",       pd.DataFrame()),
        "geographical_indications":   getattr(profile, "geographical_indications",   pd.DataFrame()),
        "ip_services":                getattr(profile, "ip_services",                pd.DataFrame()),
    }


# ── Utility ───────────────────────────────────────────────────────────────────

def _to_buffer(wb: openpyxl.Workbook) -> io.BytesIO:
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
