#!/usr/bin/env python
"""Refresh the local sector/concept database.

Usage:
    python scripts/refresh_sector_db.py              # Full refresh (industry + concepts)
    python scripts/refresh_sector_db.py --fast       # Concepts only (skip industry)
    python scripts/refresh_sector_db.py --status     # Show current status

Recommended: run weekly via cron or before analysis sessions.
Takes ~5-15 minutes depending on network speed.
"""

import argparse
import sys
import time

sys.path.insert(0, ".")

from tradingagents.dataflows.sector_db import SectorDB, IMPACT_CONCEPTS


def main():
    parser = argparse.ArgumentParser(description="Refresh sector/concept local DB")
    parser.add_argument("--fast", action="store_true", help="Skip industry boards (faster)")
    parser.add_argument("--status", action="store_true", help="Show DB status and exit")
    args = parser.parse_args()

    db = SectorDB()

    if args.status:
        last = db.get_last_refresh()
        count = db.stock_count()
        concepts = db.get_all_concepts()
        stale = db.is_stale()
        print(f"Last refresh:  {last or 'Never'}")
        print(f"Stocks cached: {count}")
        print(f"Concepts:      {len(concepts)}")
        print(f"Is stale:      {stale}")
        if concepts:
            print(f"\nCached concepts ({len(concepts)}):")
            for c in concepts:
                print(f"  - {c}")
        return

    print(f"Refreshing sector DB...")
    print(f"  Mode: {'fast (curated concepts only)' if args.fast else 'full (all ~483 concepts + industries)'}")
    print()

    t0 = time.time()

    def progress(current, total, msg):
        pct = current / total * 100 if total > 0 else 0
        print(f"  [{current}/{total}] {pct:5.1f}% {msg}")

    stats = db.refresh(
        concepts=IMPACT_CONCEPTS if args.fast else None,  # None = fetch all from API
        include_industry=not args.fast,
        progress_callback=progress,
    )

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s")
    print(f"  Industries: {stats['industries']}")
    print(f"  Concepts:   {stats['concepts']}")
    print(f"  Stocks:     {stats['stocks']}")


if __name__ == "__main__":
    main()
