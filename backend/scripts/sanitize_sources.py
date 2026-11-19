"""Знеособлення вихідних XLSX → CSV у backend/data (одна команда).

    python scripts/sanitize_sources.py [--src "D:/.../Трек 2 Енергетичний менеджмент"]

- Лічильники.xlsx → data/meters.csv — БЕЗ заводських номерів лічильників і без аркуша «Інформація» (email);
- «Інформація щодо впровадження СЕМ ….xlsx» → data/sem_status.csv — БЕЗ ПІБ, телефонів, email і посилань.

Сирі XLSX у репозиторій не копіюються.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import meters, sem  # noqa: E402

DEFAULT_SRC = ROOT.parents[1] / "drive" / "Трек 2 Енергетичний менеджмент"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC, help="тека з вихідними XLSX")
    ap.add_argument("--out", type=Path, default=ROOT / "data", help="куди писати CSV")
    a = ap.parse_args(argv)

    m_src = a.src / "Лічильники.xlsx"
    s_src = next(iter(sorted(a.src.glob("Інформація щодо впровадження СЕМ*.xlsx"))), None)
    if not m_src.exists() or s_src is None:
        print(f"Не знайдено вихідних файлів у {a.src}", file=sys.stderr)
        return 1

    rows = meters.sanitize_meters(m_src)
    meters.write_csv(rows, a.out / meters.METERS_CSV)
    print(f"{meters.METERS_CSV}: {len(rows)} лічильників, {len({r['building_id'] for r in rows})} будівель")

    srows = sem.sanitize_sem(s_src)
    sem.write_csv(srows, a.out / sem.SEM_CSV)
    print(f"{sem.SEM_CSV}: {len(srows)} рядків, {len({r['edrpou'] for r in srows})} ЄДРПОУ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
