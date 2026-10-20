"""build_readme.py / add_conference.py を main() 経由でテストする。"""

from __future__ import annotations

import pytest

import add_conference
import build_readme
import conferences_lib as lib

# ---------------------------------------------------------------- build_readme


def test_build_writes_readme_then_reports_up_to_date(workspace, capsys):
    assert build_readme.main([]) == 0
    assert "New Conf 2025" in lib.README_PATH.read_text(encoding="utf-8")
    assert build_readme.main([]) == 0
    assert "up to date" in capsys.readouterr().out


def test_build_check_fails_when_stale(workspace, capsys):
    assert build_readme.main(["--check"]) == 1
    assert "out of date" in capsys.readouterr().err
    assert "old content" in lib.README_PATH.read_text(encoding="utf-8")  # --check は書き換えない


def test_build_reports_validation_error(workspace, capsys):
    lib.DATA_PATH.write_text(
        "- name: broken\n  url: https://x\n  date: nope\n  roles: [staff]\n", encoding="utf-8"
    )
    assert build_readme.main([]) == 2
    assert "YYYY-MM-DD" in capsys.readouterr().err


# ---------------------------------------------------------------- add_conference


def run_add(monkeypatch, *argv: str) -> int:
    monkeypatch.setattr("sys.argv", ["add_conference.py", *argv])
    return add_conference.main()


def test_add_non_interactive_appends_and_rebuilds(workspace, monkeypatch):
    rc = run_add(
        monkeypatch,
        "--yes",
        "--name",
        "PHPerKaigi 2026",
        "--url",
        "https://phperkaigi.jp/2026/",
        "--date",
        "2026-03-20",
        "--end",
        "2026-03-22",
        "--roles",
        "core,noc",
        "--note",
        "[資料](https://example.com/deck)",
    )
    assert rc == 0
    entries = lib.load()
    assert entries[-1] == {
        "name": "PHPerKaigi 2026",
        "url": "https://phperkaigi.jp/2026/",
        "date": "2026-03-20",
        "end": "2026-03-22",
        "roles": ["core", "noc"],
        "note": "[資料](https://example.com/deck)",
    }
    readme = lib.README_PATH.read_text(encoding="utf-8")
    assert "PHPerKaigi 2026" in readme
    assert '<a href="https://example.com/deck">資料</a>' in readme


def test_add_treats_empty_optional_flags_as_absent(workspace, monkeypatch):
    # Actions からは end / note が空文字で渡ってくる
    rc = run_add(
        monkeypatch,
        "--yes",
        "--name",
        "X",
        "--url",
        "https://x.test/",
        "--date",
        "2026-01-01",
        "--end",
        "",
        "--roles",
        "attendee",
        "--note",
        "",
    )
    assert rc == 0
    assert set(lib.load()[-1]) == {"name", "url", "date", "roles"}


def test_add_rejects_duplicate_url_and_date(workspace, monkeypatch, capsys):
    rc = run_add(
        monkeypatch,
        "--yes",
        "--name",
        "dup",
        "--url",
        "https://example.com/2025/",
        "--date",
        "2025-09-19",
        "--roles",
        "staff",
    )
    assert rc == 2
    assert "既にあります" in capsys.readouterr().err
    assert len(lib.load()) == 2


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["--date", "2026-02-30", "--roles", "staff"], "YYYY-MM-DD"),
        (["--date", "2026-01-01", "--roles", "boss"], "不明な値"),
        (["--date", "2026-01-01", "--end", "2025-01-01", "--roles", "staff"], "end は date 以降"),
    ],
)
def test_add_rejects_invalid_input_without_writing(workspace, monkeypatch, capsys, argv, message):
    before = lib.DATA_PATH.read_text(encoding="utf-8")
    rc = run_add(monkeypatch, "--yes", "--name", "bad", "--url", "https://x.test/", *argv)
    assert rc == 2
    assert message in capsys.readouterr().err
    assert lib.DATA_PATH.read_text(encoding="utf-8") == before


def test_add_interactive_flow(workspace, monkeypatch, capsys):
    answers = iter(
        [
            "YAPC::Fukuoka 2026",  # name
            "https://yapcjapan.org/2026/",  # url
            "2026-03-14",  # date
            "",  # end
            "1, 5",  # roles by number
            "[talk](https://example.com/t)",  # note
            "y",  # confirm
            "n",  # create PR?
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    assert run_add(monkeypatch) == 0
    last = lib.load()[-1]
    assert last["name"] == "YAPC::Fukuoka 2026"
    assert last["roles"] == ["speaker", "attendee"]
    assert "end" not in last
    assert "YAPC::Fukuoka 2026" in lib.README_PATH.read_text(encoding="utf-8")


def test_add_interactive_reprompts_on_bad_date_and_roles(workspace, monkeypatch):
    answers = iter(["C", "https://c.test/", "bad-date", "2026-01-01", "", "9", "boss", "2", "", "y", "n"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    assert run_add(monkeypatch) == 0
    assert lib.load()[-1]["roles"] == ["core"]


def test_add_interactive_abort_writes_nothing(workspace, monkeypatch):
    answers = iter(["C", "https://c.test/", "2026-01-01", "", "3", "", "n"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    before = lib.DATA_PATH.read_text(encoding="utf-8")
    assert run_add(monkeypatch) == 1
    assert lib.DATA_PATH.read_text(encoding="utf-8") == before
