"""data/conferences.yml の読み書きと README 生成の共通処理。"""
from __future__ import annotations

import html
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "conferences.yml"
README_PATH = ROOT / "README.md"

START_MARK = "<!-- CONFERENCES:START -->"
END_MARK = "<!-- CONFERENCES:END -->"

ROLES = ("speaker", "staff", "attendee")
ROLE_BADGE = {
    "speaker": ("Speaker", "bf91f3"),
    "staff": ("Staff", "70a5fd"),
    "attendee": ("Attendee", "38bdae"),
}
REQUIRED = ("name", "url", "year", "role")


class ValidationError(Exception):
    pass


def load() -> list[dict]:
    data = yaml.safe_load(DATA_PATH.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        raise ValidationError("conferences.yml はリストである必要があります")
    for i, e in enumerate(data):
        validate(e, where=f"#{i + 1}")
    return data


def save(entries: list[dict]) -> None:
    header_lines = []
    for line in DATA_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or line.strip() == "":
            header_lines.append(line)
        else:
            break
    body = yaml.safe_dump(
        entries, allow_unicode=True, sort_keys=False, default_flow_style=False, width=1000
    )
    # エントリ間に空行を入れて読みやすくする
    body = re.sub(r"\n(- name:)", r"\n\n\1", body)
    DATA_PATH.write_text("\n".join(header_lines).rstrip("\n") + "\n\n" + body, encoding="utf-8")


def validate(e: dict, where: str = "") -> None:
    prefix = f"{where}: " if where else ""
    for k in REQUIRED:
        if not e.get(k) and e.get(k) != 0:
            raise ValidationError(f"{prefix}{k} は必須です")
    if e["role"] not in ROLES:
        raise ValidationError(f"{prefix}role は {', '.join(ROLES)} のいずれかにしてください (got {e['role']!r})")
    if not re.match(r"^https?://", str(e["url"])):
        raise ValidationError(f"{prefix}url は http(s):// で始めてください")
    if not re.fullmatch(r"\d{4}", str(e["year"])):
        raise ValidationError(f"{prefix}year は4桁の西暦にしてください")
    if e.get("date") is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(e["date"])):
        raise ValidationError(f"{prefix}date は YYYY-MM-DD 形式にしてください")


def _badge(role: str) -> str:
    label, color = ROLE_BADGE[role]
    return f'<img src="https://img.shields.io/badge/-{label}-{color}?style=flat-square" alt="{label}" />'


def _sort_key(indexed: tuple[int, dict]):
    i, e = indexed
    # 新しいものを上に。date があれば優先、なければ year とファイル内の順序
    return (-int(e["year"]), str(e.get("date") or ""), -i)


def render_table(entries: list[dict]) -> str:
    rows = []
    for role in ROLES:
        group = [(i, e) for i, e in enumerate(entries) if e["role"] == role]
        for _, e in sorted(group, key=_sort_key, reverse=False):
            note_parts = []
            if e.get("talk"):
                note_parts.append(f"🎙️ {html.escape(str(e['talk']))}")
            if e.get("note"):
                note_parts.append(html.escape(str(e["note"])))
            rows.append(
                "    <tr>\n"
                f"      <td>{_badge(role)}</td>\n"
                f"      <td>{e['year']}</td>\n"
                f'      <td><a href="{html.escape(str(e["url"]), quote=True)}">{html.escape(str(e["name"]))}</a></td>\n'
                f"      <td>{' / '.join(note_parts)}</td>\n"
                "    </tr>"
            )
    counts = {r: sum(1 for e in entries if e["role"] == r) for r in ROLES}
    summary = " ・ ".join(f"{ROLE_BADGE[r][0]} {counts[r]}" for r in ROLES)
    return (
        f"<!-- このセクションは data/conferences.yml から scripts/build_readme.py で自動生成されます。直接編集しないでください。 -->\n"
        f"<p align=\"center\"><sub>{summary}</sub></p>\n\n"
        "<table>\n"
        "  <thead>\n"
        "    <tr>\n"
        '      <th align="left">Role</th>\n'
        '      <th align="left">Year</th>\n'
        '      <th align="left">Conference</th>\n'
        '      <th align="left">Note</th>\n'
        "    </tr>\n"
        "  </thead>\n"
        "  <tbody>\n" + "\n".join(rows) + "\n"
        "  </tbody>\n"
        "</table>"
    )


def render_readme(readme: str, entries: list[dict]) -> str:
    if START_MARK not in readme or END_MARK not in readme:
        raise ValidationError(f"README.md に {START_MARK} / {END_MARK} が見つかりません")
    pattern = re.compile(re.escape(START_MARK) + r".*?" + re.escape(END_MARK), re.S)
    return pattern.sub(lambda _: f"{START_MARK}\n{render_table(entries)}\n{END_MARK}", readme, count=1)
