"""Print a pass/fail table for the gold set (needs the index and ANTHROPIC_API_KEY)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.gold_eval import run_gold  # noqa: E402


def main() -> int:
    rows = run_gold()
    print(f"{'id':<24}{'expect':<10}{'got':<10}{'result'}")
    for item, response, problems in rows:
        print(f"{item['id']:<24}{item['expect_type']:<10}{response['type']:<10}"
              f"{'PASS' if not problems else 'FAIL: ' + '; '.join(problems)}")
    passed = sum(1 for _, _, p in rows if not p)
    print(f"\n{passed}/{len(rows)} passed ({100 * passed // len(rows)}%); target >= 80%")
    return 0 if passed * 10 >= len(rows) * 8 else 1


if __name__ == "__main__":
    raise SystemExit(main())
