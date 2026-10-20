"""data/conferences.yml から README.md の Conferences セクションを再生成する。

使い方:
  uv run build_readme.py          # README.md を書き換える
  uv run build_readme.py --check  # 最新かどうかだけ確認 (CI 用)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import conferences_lib as lib
from conferences_lib import ValidationError


def main(argv: list[str]) -> int:
    check = "--check" in argv
    try:
        entries = lib.load()
        current = lib.README_PATH.read_text(encoding="utf-8")
        updated = lib.render_readme(current, entries)
    except ValidationError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if current == updated:
        print("README.md is up to date")
        return 0
    if check:
        print("README.md is out of date. run: uv run scripts/build_readme.py", file=sys.stderr)
        return 1
    lib.README_PATH.write_text(updated, encoding="utf-8")
    print(f"README.md updated ({len(entries)} conferences)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
