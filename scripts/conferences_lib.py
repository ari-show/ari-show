"""data/conferences.yml の読み書き・検証と README の Conferences セクション生成。"""

from __future__ import annotations

import datetime as dt
import html
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "conferences.yml"
README_PATH = ROOT / "README.md"

START_MARK = "<!-- CONFERENCES:START -->"
END_MARK = "<!-- CONFERENCES:END -->"

# 表示順もこの順 (登壇 > コア > 当日 > NOC > 参加)
ROLES: dict[str, tuple[str, str, str]] = {
    #  key        (バッジ表記,   日本語,         色)
    "speaker": ("Speaker", "登壇者", "bf91f3"),
    "core": ("Core%20Staff", "コアスタッフ", "70a5fd"),
    "staff": ("Staff", "当日スタッフ", "7aa2f7"),
    "noc": ("NOC", "NOC", "ff9e64"),
    "attendee": ("Attendee", "参加者", "38bdae"),
}
REQUIRED = ("name", "url", "date", "roles")
OPTIONAL = ("end", "note")
FIELD_ORDER = ("name", "url", "date", "end", "roles", "note")


class ValidationError(Exception):
    pass


# ---------------------------------------------------------------- I/O


def load() -> list[dict]:
    data = yaml.safe_load(DATA_PATH.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        raise ValidationError("conferences.yml はリストである必要があります")
    entries = [normalize(e, where=f"#{i + 1}") for i, e in enumerate(data)]
    return entries


def save(entries: list[dict]) -> None:
    header = []
    for line in DATA_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            header.append(line)
        else:
            break
    ordered = [{k: _dump_value(k, e[k]) for k in FIELD_ORDER if k in e} for e in entries]
    body = yaml.safe_dump(ordered, allow_unicode=True, sort_keys=False, width=1000)
    body = re.sub(r"\n(- name:)", r"\n\n\1", body)
    body = re.sub(r"roles:\n((?:  *- \w+\n)+)", _inline_roles, body)
    body = re.sub(r"^(  (?:date|end): )'(\d{4}-\d{2}-\d{2})'$", r"\1\2", body, flags=re.M)
    DATA_PATH.write_text("\n".join(header).rstrip("\n") + "\n\n" + body, encoding="utf-8")


def _dump_value(key: str, value):
    if key in ("date", "end"):
        return str(value)  # yaml が date 型に戻してしまうので文字列のまま
    return value


def _inline_roles(m: re.Match) -> str:
    roles = re.findall(r"- (\w+)", m.group(1))
    return f"roles: [{', '.join(roles)}]\n"


# ---------------------------------------------------------------- validation


def normalize(e: dict, where: str = "") -> dict:
    """型をそろえつつ検証する。date/end は 'YYYY-MM-DD' 文字列、roles は list に統一。"""
    prefix = f"{where}: " if where else ""
    if not isinstance(e, dict):
        raise ValidationError(f"{prefix}エントリはマップである必要があります")
    for k in REQUIRED:
        if k not in e or e[k] in (None, "", []):
            raise ValidationError(f"{prefix}{k} は必須です")
    unknown = set(e) - set(REQUIRED) - set(OPTIONAL)
    if unknown:
        raise ValidationError(f"{prefix}不明なフィールド: {sorted(unknown)}")

    out = {"name": str(e["name"]).strip(), "url": str(e["url"]).strip()}
    if not re.match(r"^https?://", out["url"]):
        raise ValidationError(f"{prefix}url は http(s):// で始めてください")

    out["date"] = _to_date_str(e["date"], f"{prefix}date")
    if e.get("end"):
        out["end"] = _to_date_str(e["end"], f"{prefix}end")
        if out["end"] < out["date"]:
            raise ValidationError(f"{prefix}end は date 以降の日付にしてください")

    roles = e["roles"]
    if isinstance(roles, str):
        roles = [r for r in re.split(r"[,\s]+", roles) if r]
    roles = [str(r).strip().lower() for r in roles]
    bad = [r for r in roles if r not in ROLES]
    if bad:
        raise ValidationError(f"{prefix}roles に不明な値 {bad}。使えるのは {', '.join(ROLES)}")
    if not roles:
        raise ValidationError(f"{prefix}roles は1つ以上指定してください")
    out["roles"] = sorted(set(roles), key=list(ROLES).index)

    if e.get("note"):
        out["note"] = str(e["note"]).strip()
    return out


def _to_date_str(v, label: str) -> str:
    if isinstance(v, dt.date):
        return v.isoformat()
    s = str(v).strip()
    try:
        return dt.date.fromisoformat(s).isoformat()
    except ValueError:
        raise ValidationError(f"{label} は YYYY-MM-DD 形式にしてください (got {s!r})") from None


# ---------------------------------------------------------------- render


def _badge(role: str) -> str:
    label, ja, color = ROLES[role]
    src = f"https://img.shields.io/badge/-{label}-{color}?style=flat-square"
    return f'<img src="{src}" alt="{ja}" title="{ja}" />'


def _fmt_date(e: dict) -> str:
    if not e.get("end"):
        return e["date"]
    # 同じ年月なら日だけ、同じ年なら月日だけ省略表記
    d, en = e["date"], e["end"]
    if d[:7] == en[:7]:
        return f"{d}~{en[8:]}"
    if d[:4] == en[:4]:
        return f"{d}~{en[5:]}"
    return f"{d}~{en}"


_MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def _note_html(note: str) -> str:
    """Markdown のリンク記法だけ <a> に変換し、残りはエスケープする。"""
    out, pos = [], 0
    for m in _MD_LINK.finditer(note):
        out.append(html.escape(note[pos : m.start()]))
        out.append(f'<a href="{html.escape(m.group(2), quote=True)}">{html.escape(m.group(1))}</a>')
        pos = m.end()
    out.append(html.escape(note[pos:]))
    return "".join(out)


def render_table(entries: list[dict]) -> str:
    ordered = sorted(entries, key=lambda e: e["date"], reverse=True)
    rows = []
    for e in ordered:
        rows.append(
            "    <tr>\n"
            f"      <td nowrap>{_fmt_date(e)}</td>\n"
            f'      <td><a href="{html.escape(e["url"], quote=True)}">{html.escape(e["name"])}</a></td>\n'
            f"      <td nowrap>{' '.join(_badge(r) for r in e['roles'])}</td>\n"
            f"      <td>{_note_html(e.get('note', ''))}</td>\n"
            "    </tr>"
        )
    counts = {r: sum(1 for e in entries if r in e["roles"]) for r in ROLES}
    summary = " ・ ".join(f"{ROLES[r][1]} {counts[r]}" for r in ROLES if counts[r])
    return (
        "<!-- このセクションは data/conferences.yml から scripts/build_readme.py で自動生成されます。"
        "直接編集しないでください。 -->\n"
        f'<p align="center"><sub>{summary}</sub></p>\n\n'
        "<table>\n"
        "  <thead>\n"
        "    <tr>\n"
        '      <th align="left">Date</th>\n'
        '      <th align="left">Conference</th>\n'
        '      <th align="left">Role</th>\n'
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
