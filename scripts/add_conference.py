#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml>=6"]
# ///
"""カンファレンス履歴を1件追加し、README を再生成し、必要なら PR まで作る。

対話モード (質問に答えるだけ):
  uv run scripts/add_conference.py
  uv run scripts/add_conference.py --pr        # 最後にブランチ作成 → push → gh pr create まで実行

非対話モード (GitHub Actions やワンライナー用):
  uv run scripts/add_conference.py --yes \
      --name "PHPerKaigi 2026" --url https://phperkaigi.jp/2026/ \
      --date 2026-03-20 --end 2026-03-22 --roles core,noc --note "..."
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
    normalize,
    render_readme,
    save,
)

BOLD, DIM, GREEN, CYAN, RED, RESET = "\033[1m", "\033[2m", "\033[32m", "\033[36m", "\033[31m", "\033[0m"


# ---------------------------------------------------------------- prompts

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
        print(f"  {RED}必須項目です{RESET}")


def ask_date(label: str, required: bool, hint: str) -> str:
    while True:
        v = ask(label, required=required, hint=hint)
        if not v:
            return v
        try:
            return dt.date.fromisoformat(v).isoformat()
        except ValueError:
            print(f"  {RED}YYYY-MM-DD の形式で入力してください{RESET}")


def ask_roles() -> list[str]:
    keys = list(ROLES)
    for i, r in enumerate(keys, 1):
        print(f"  {CYAN}{i}{RESET}) {r:<9}{DIM}{ROLES[r][1]}{RESET}")
    while True:
        v = ask("roles", required=True, hint="番号をカンマ区切り。例: 2,4")
        picked = []
        for tok in re.split(r"[,\s]+", v):
            if tok.isdigit() and 1 <= int(tok) <= len(keys):
                picked.append(keys[int(tok) - 1])
            elif tok in keys:
                picked.append(tok)
            elif tok:
                picked = None
                break
        if picked:
            return picked
        print(f"  {RED}1〜{len(keys)} の番号か {', '.join(keys)} で指定してください{RESET}")


# ---------------------------------------------------------------- git / PR

def slugify(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s or dt.date.today().strftime("%Y%m%d")


def run(cmd: list[str]) -> None:
    print(f"{DIM}$ {' '.join(cmd)}{RESET}")
    subprocess.run(cmd, cwd=ROOT, check=True, text=True)


def create_pr(entry: dict) -> None:
    if subprocess.run(["gh", "auth", "status"], cwd=ROOT, capture_output=True).returncode != 0:
        sys.exit("gh にログインしていません。`gh auth login` を実行してから --pr を使ってください")
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
    changed = {line[3:] for line in status.splitlines()}
    allowed = {str(DATA_PATH.relative_to(ROOT)), str(README_PATH.relative_to(ROOT))}
    if changed - allowed:
        sys.exit(f"他の未コミット変更があります。先に片付けてください: {sorted(changed - allowed)}")

    branch = f"conference/{slugify(entry['name'])}-{entry['date']}"
    title = f"Add conference: {entry['name']} ({', '.join(entry['roles'])})"
    body = "\n".join(
        [f"- **{k}**: {', '.join(v) if isinstance(v, list) else v}" for k, v in entry.items()]
        + ["", "Created by `scripts/add_conference.py`."]
    )
    run(["git", "switch", "-c", branch])
    run(["git", "add", str(DATA_PATH), str(README_PATH)])
    run(["git", "commit", "-q", "-m", title])
    run(["git", "push", "-u", "origin", branch])
    run(["gh", "pr", "create", "--title", title, "--body", body])


# ---------------------------------------------------------------- main

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", help="カンファレンス名")
    p.add_argument("--url", help="リンク先 URL")
    p.add_argument("--date", help="開催日 (初日) YYYY-MM-DD")
    p.add_argument("--end", help="最終日 YYYY-MM-DD (複数日開催のとき)")
    p.add_argument("--roles", help=f"カンマ区切り: {', '.join(ROLES)}")
    p.add_argument("--note", help="補足。登壇タイトルや記事・スライドのリンク ([text](url) 可)")
    p.add_argument("--yes", "-y", action="store_true", help="確認をスキップ (非対話)")
    p.add_argument("--pr", action="store_true", help="ブランチ作成・push・PR 作成まで行う")
    a = p.parse_args()

    interactive = not a.yes
    if interactive:
        print(f"\n{GREEN}▸ カンファレンス履歴を追加します{RESET}  {DIM}(Ctrl-C で中断){RESET}\n")

    raw = {
        "name": a.name or ask("name", required=True, hint="カンファレンス名"),
        "url": a.url or ask("url", required=True, hint="https://..."),
        "date": a.date or ask_date("date", required=True, hint="開催日 YYYY-MM-DD。複数日なら初日"),
        "end": a.end if a.end is not None else (ask_date("end", required=False, hint="最終日 YYYY-MM-DD, 1日開催なら空") if interactive else ""),
        "roles": a.roles or ask_roles(),
        "note": a.note if a.note is not None else (ask("note", hint="登壇タイトル / 記事やスライドのリンク, 任意") if interactive else ""),
    }
    raw = {k: v for k, v in raw.items() if v}

    try:
        entry = normalize(raw)
        entries = load()
    except ValidationError as e:
        print(f"{RED}error:{RESET} {e}", file=sys.stderr)
        return 2
    if any(e["url"] == entry["url"] and e["date"] == entry["date"] for e in entries):
        print(f"{RED}error:{RESET} 同じ url と date のエントリが既にあります", file=sys.stderr)
        return 2

    if interactive:
        print(f"\n{BOLD}追加内容:{RESET}")
        for k, v in entry.items():
            print(f"  {k:<6}{', '.join(v) if isinstance(v, list) else v}")
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
