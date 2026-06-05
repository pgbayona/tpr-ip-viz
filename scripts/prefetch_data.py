"""Pre-fetch WIPO and WTO IP data for all WTO members into the disk cache.

First run (no cache):  python scripts/prefetch_data.py
Monthly refresh:       python scripts/prefetch_data.py --force
Faster (more threads): python scripts/prefetch_data.py --workers 8
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    _env = _ROOT / ".env"
    load_dotenv(_env if _env.exists() else _ROOT / ".env.txt")
except ImportError:
    pass

from src.transform.cleaning import WTO_MEMBERS, get_alpha3
from src.extract.wipo import WIPOExtractor
from src.extract.wto import WTOExtractor

_CACHE_META = _ROOT / "data" / "last_refreshed.json"
_LOCK_FILE  = _ROOT / "data" / ".prefetch_running"
_WIPO_CACHE = _ROOT / "data" / "raw" / "wipo"
_WTO_CACHE  = _ROOT / "data" / "raw" / "wto"


def _fetch_one(name: str, alpha2: str, alpha3: str | None, start: int, end: int) -> list[str]:
    """Fetch all indicators for one country. Returns list of error strings (empty = success)."""
    errors: list[str] = []
    extractor = WIPOExtractor()

    try:
        if alpha2 == "EU":
            # Combined EU: patents from EPO (EP), everything else from EUIPO (EM)
            from src.viz.profile import _EU_WIPO_SOURCES, _fetch_wipo_eu
            _fetch_wipo_eu(start, end)
        else:
            extractor.get_all_ip_data(alpha2, start, end)
    except Exception as exc:
        errors.append(f"WIPO: {exc}")

    if alpha3:
        try:
            WTOExtractor().get_ip_services(alpha3, start, end)
        except Exception as exc:
            errors.append(f"WTO: {exc}")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pre-fetch IP data for all WTO members into the disk cache."
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Clear existing cache and re-fetch everything (use for monthly refresh).",
    )
    parser.add_argument(
        "--workers", type=int, default=4,
        help="Number of countries to fetch in parallel (default: 4). "
             "Increase cautiously — each country already spawns 9 WIPO threads internally.",
    )
    parser.add_argument("--start", type=int, default=2010, help="Start year (default: 2010).")
    parser.add_argument("--end",   type=int, default=2024, help="End year (default: 2024).")
    args = parser.parse_args()

    if _LOCK_FILE.exists():
        print("Another prefetch is already running. Exiting.")
        sys.exit(0)

    _LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    _LOCK_FILE.touch()

    try:
        if args.force:
            print("--force: clearing existing raw cache…")
            shutil.rmtree(_WIPO_CACHE, ignore_errors=True)
            shutil.rmtree(_WTO_CACHE,  ignore_errors=True)
            print("Cache cleared.\n")

        countries: list[tuple[str, str, str | None]] = [
            (name, alpha2, get_alpha3(name))
            for name, alpha2 in WTO_MEMBERS.items()
        ]
        total = len(countries)
        print(f"Prefetching {total} WTO members | years {args.start}–{args.end} | {args.workers} parallel workers\n")

        done = 0
        failed: list[str] = []

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(_fetch_one, name, a2, a3, args.start, args.end): name
                for name, a2, a3 in countries
            }
            for future in as_completed(futures):
                name = futures[future]
                done += 1
                try:
                    errors = future.result()
                    if errors:
                        print(f"  WARN  [{done:>3}/{total}] {name}: {'; '.join(errors)}")
                        failed.append(name)
                    else:
                        print(f"  OK    [{done:>3}/{total}] {name}")
                except Exception as exc:
                    print(f"  FAIL  [{done:>3}/{total}] {name}: {exc}")
                    failed.append(name)

        meta = {
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
            "start_year": args.start,
            "end_year": args.end,
            "total_countries": total,
            "failed_countries": failed,
            "success_count": total - len(failed),
        }
        _CACHE_META.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_META.write_text(json.dumps(meta, indent=2))

        print(f"\n{'='*60}")
        print(f"Done: {total - len(failed)}/{total} countries succeeded.")
        if failed:
            print(f"Failed ({len(failed)}): {', '.join(failed)}")
        print(f"Metadata saved → {_CACHE_META.relative_to(_ROOT)}")

    finally:
        _LOCK_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
