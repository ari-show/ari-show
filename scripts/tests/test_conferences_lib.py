from __future__ import annotations

import datetime as dt

import pytest
from conftest import valid_entry

import conferences_lib as lib

# ---------------------------------------------------------------- normalize


def test_normalize_minimal_entry():
    out = lib.normalize(valid_entry())
    assert out == {"name": "Conf", "url": "https://example.com/", "date": "2026-01-10", "roles": ["attendee"]}


def test_normalize_accepts_date_objects_and_strings():
    out = lib.normalize(valid_entry(date=dt.date(2026, 1, 10), end="2026-01-12"))
    assert out["date"] == "2026-01-10"
    assert out["end"] == "2026-01-12"


def test_normalize_roles_from_string_dedup_and_canonical_order():
    out = lib.normalize(valid_entry(roles="noc, core,noc speaker"))
    assert out["roles"] == ["speaker", "core", "noc"]


def test_normalize_strips_and_drops_empty_note():
    assert "note" not in lib.normalize(valid_entry(note=""))
    assert lib.normalize(valid_entry(note="  x  "))["note"] == "x"


@pytest.mark.parametrize(
    ("over", "message"),
    [
        ({"name": ""}, "name は必須"),
        ({"url": "example.com"}, r"http\(s\)://"),
        ({"date": "2026-13-01"}, "YYYY-MM-DD"),
        ({"date": "2026/01/10"}, "YYYY-MM-DD"),
        ({"end": "2025-12-31"}, "end は date 以降"),
        ({"roles": ["boss"]}, "不明な値"),
        ({"roles": []}, "roles は必須"),
        ({"talk": "x"}, "不明なフィールド"),
    ],
)
def test_normalize_rejects_invalid(over, message):
    with pytest.raises(lib.ValidationError, match=message):
        lib.normalize(valid_entry(**over))


def test_normalize_error_includes_location():
    with pytest.raises(lib.ValidationError, match=r"^#3: "):
        lib.normalize(valid_entry(url="nope"), where="#3")


# ---------------------------------------------------------------- load / save


def test_load_returns_normalized_entries(workspace):
    entries = lib.load()
    assert [e["name"] for e in entries] == ["Old Conf 2024", "New Conf 2025"]
    assert entries[1]["roles"] == ["core", "noc"]
    assert entries[0]["date"] == "2024-03-07"


def test_save_keeps_header_inline_roles_and_unquoted_dates(workspace):
    entries = lib.load()
    entries.append(lib.normalize(valid_entry(name="Added", roles=["speaker", "staff"], end="2026-01-11")))
    lib.save(entries)
    text = lib.DATA_PATH.read_text(encoding="utf-8")
    assert text.startswith("# header comment line 1\n# header comment line 2\n\n- name:")
    assert "  roles: [speaker, staff]\n" in text
    assert "  date: 2026-01-10\n  end: 2026-01-11\n" in text
    assert "'2026-01-10'" not in text
    assert text.count("\n\n- name:") == 3  # ヘッダー直後 + エントリ間 2 箇所
    assert "\n\n\n" not in text


def test_save_then_load_round_trip_is_stable(workspace):
    lib.save(lib.load())
    first = lib.DATA_PATH.read_text(encoding="utf-8")
    lib.save(lib.load())
    assert lib.DATA_PATH.read_text(encoding="utf-8") == first


# ---------------------------------------------------------------- render helpers


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ({"date": "2025-06-28"}, "2025-06-28"),
        ({"date": "2025-03-21", "end": "2025-03-23"}, "2025-03-21~23"),
        ({"date": "2025-03-30", "end": "2025-04-01"}, "2025-03-30~04-01"),
        ({"date": "2025-12-31", "end": "2026-01-01"}, "2025-12-31~2026-01-01"),
    ],
)
def test_fmt_date(entry, expected):
    assert lib._fmt_date(entry) == expected


def test_note_html_converts_markdown_links_and_escapes_rest():
    out = lib._note_html("see [a <b>](https://x.test/?q=1&r=2) & [c](https://y.test)")
    assert out == (
        'see <a href="https://x.test/?q=1&amp;r=2">a &lt;b&gt;</a> &amp; <a href="https://y.test">c</a>'
    )


def test_note_html_ignores_non_http_links():
    assert lib._note_html("[x](javascript:alert(1))") == "[x](javascript:alert(1))"


# ---------------------------------------------------------------- render_table / render_readme


def test_render_table_sorted_newest_first_with_badges_and_summary(workspace):
    table = lib.render_table(lib.load())
    assert table.index("New Conf 2025") < table.index("Old Conf 2024")
    assert "2025-09-19~21" in table
    assert 'alt="コアスタッフ"' in table and 'alt="NOC"' in table
    assert table.index("Core%20Staff") < table.index("-NOC-")  # ロールは canonical 順
    assert "コアスタッフ 1 ・ 当日スタッフ 1 ・ NOC 1" in table
    assert "登壇者" not in table.split("<table>")[0]  # 0 件のロールはサマリに出ない
    assert '<a href="https://example.com/slides">slides</a> and more' in table


def test_render_readme_replaces_only_marker_section(workspace):
    readme = lib.README_PATH.read_text(encoding="utf-8")
    out = lib.render_readme(readme, lib.load())
    assert out.startswith("# Title\n\n## 🎤 Conferences\n\n<!-- CONFERENCES:START -->\n")
    assert out.endswith("<!-- CONFERENCES:END -->\n\nfooter\n")
    assert "old content" not in out
    assert "New Conf 2025" in out


def test_render_readme_is_idempotent(workspace):
    entries = lib.load()
    once = lib.render_readme(lib.README_PATH.read_text(encoding="utf-8"), entries)
    assert lib.render_readme(once, entries) == once


def test_render_readme_requires_markers():
    with pytest.raises(lib.ValidationError, match="CONFERENCES:START"):
        lib.render_readme("no markers here", [])
