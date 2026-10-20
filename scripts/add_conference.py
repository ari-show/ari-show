#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml>=6"]
# ///
"""カンファレンス履歴を1件追加し、README を再生成し、必要なら PR まで作る。

対話モード (terraform init 風に質問に答えるだけ):
  uv run scripts/add_conference.py
  uv run scripts/add_conference.py --pr        # 最後にブランチ作成 → push → gh pr create まで実行

非対話モード (GitHub Actions やワンライナー用):
  uv run scripts/add_conference.py --name "PHPerKaigi 2026" --url https://phperkaigi.jp/2026/ \
      --year 2026 --role staff --note core --yes
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conferences_lib import (  # noqa: E402
    DATA_PATH,
    README_PATH,
    ROLES,
    ROOT,
    ValidationError,
    load,
    render_readme,
    save,
    validate,
)

BOLD, DIM, GREEN, CYAN, RESET = "\033[1m", "\033[2m", "\033[32m", "\033[36m", "\033[0m"


def ask(label: str, default: str | None = None, required: bool = False, hint: str = "") -> str:
    suffix = f" {DIM}[{default}]{RESET}" if default else ""
    hint_s = f" {DIM}({hint}){RESET}" if hint else ""
    while True:
        try:
            value = input(f"{BOLD}{label}{RESET}{hint_s}{suffix}: ").strip()
        except EOFError:
            value = ""
        if not value and default is not None:
            return default
        if value or not required:
            return value
        print("  必須項目です")


def ask_role(default: str | None) -> str:
    labels = {"speaker": "登壇", "staff": "スタッフ", "attendee": "参加"}
    for i, r in enumerate(ROLES, 1):
        print(f"  {CYAN}{i}{RESET}) {r:<9}{DIM}{labels[r]}{RESET}")
    while True:
        v = ask("role", default=default, required=True, hint="番号 or 名前")
        if v.isdigit() and 1 <= int(v) <= len(ROLES):
            return ROLES[int(v) - 1]
        if v in ROLES:
            return v
        print(f"  {', '.join(ROLES)} のいずれかを選んでください")


def slugify(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s or dt.date.today().strftime("%Y%m%d")


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print(f"{DIM}$ {' '.join(cmd)}{RESET}")
    return subprocess.run(cmd, cwd=ROOT, check=True, text=True, **kw)


def create_pr(entry: dict) -> None:
    if subprocess.run(["gh", "auth", "status"], cwd=ROOT, capture_output=True).returncode != 0:
        sys.exit("gh にログインしていません。`gh auth login` を実行してから --pr を使ってください")
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
    changed = {line[3:] for line in status.splitlines()}
    allowed = {str(DATA_PATH.relative_to(ROOT)), str(README_PATH.relative_to(ROOT))}
    if changed - allowed:
        sys.exit(f"他の未コミット変更があります。先に片付けてください: {sorted(changed - allowed)}")

    branch = f"conference/{slugify(entry['name'])}-{entry['role']}"
    title = f"Add conference: {entry['name']} ({entry['role']})"
    body = "\n".join(
        [f"- **{k}**: {entry[k]}" for k in ("name", "url", "year", "role", "date", "note", "talk") if entry.get(k)]
        + ["", "Created by `scripts/add_conference.py`."]
    )
    run(["git", "switch", "-c", branch])
    run(["git", "add", str(DATA_PATH), str(README_PATH)])
    run(["git", "commit", "-q", "-m", title])
    run(["git", "push", "-u", "origin", branch])
    run(["gh", "pr", "create", "--title", title, "--body", body])


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name")
    p.add_argument("--url")
    p.add_argument("--year", type=int)
    p.add_argument("--role", choices=ROLES)
    p.add_argument("--date", help="YYYY-MM-DD")
    p.add_argument("--note")
    p.add_argument("--talk", help="登壇タイトル (speaker のとき)")
    p.add_argument("--yes", "-y", action="store_true", help="確認をスキップ (非対話)")
    p.add_argument("--pr", action="store_true", help="ブランチ作成・push・PR 作成まで行う")
    a = p.parse_args()

    interactive = not a.yes
    if interactive:
        print(f"\n{GREEN}▸ カンファレンス履歴を追加します{RESET}  {DIM}(Ctrl-C で中断){RESET}\n")

    entry = {
        "name": a.name or ask("name", required=True, hint="カンファレンス名"),
        "url": a.url or ask("url", required=True, hint="https://..."),
        "year": a.year or int(ask("year", default=str(dt.date.today().year), required=True)),
        "role": a.role or ask_role(default=None),
    }
    date = a.date if a.date is not None else (ask("date", hint="YYYY-MM-DD, 任意") if interactive else "")
    talk = a.talk if a.talk is not None else (
        ask("talk", hint="登壇タイトル, 任意") if interactive and entry["role"] == "speaker" else ""
    )
    note = a.note if a.note is not None else (ask("note", hint="core / NOC / サブタイトル など, 任意") if interactive else "")
    for k, v in (("date", date), ("talk", talk), ("note", note)):
        if v:
            entry[k] = v
    entry["year"] = int(entry["year"])

    try:
        validate(entry)
        entries = load()
    except ValidationError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if any(e["url"] == entry["url"] and e["role"] == entry["role"] for e in entries):
        print("error: 同じ url と role のエントリが既にあります", file=sys.stderr)
        return 2

    if interactive:
        print(f"\n{BOLD}追加内容:{RESET}")
        for k, v in entry.items():
            print(f"  {k:<5} {v}")
        if ask("\nこの内容で追加しますか?", default="y", hint="y/n").lower() not in ("y", "yes"):
            print("中断しました")
            return 1

    entries.append(entry)
    save(entries)
    README_PATH.write_text(render_readme(README_PATH.read_text(encoding="utf-8"), entries), encoding="utf-8")
    print(f"\n{GREEN}✔{RESET} {DATA_PATH.relative_to(ROOT)} と README.md を更新しました")

    do_pr = a.pr or (interactive and ask("PR を作成しますか?", default="n", hint="y/n").lower() in ("y", "yes"))
    if do_pr:
        create_pr(entry)
    else:
        print(f"{DIM}次のステップ: git diff で確認して commit、または --pr で PR 作成{RESET}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n中断しました")
        raise SystemExit(130)
