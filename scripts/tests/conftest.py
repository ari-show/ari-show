from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import conferences_lib as lib  # noqa: E402

SAMPLE_YAML = """\
# header comment line 1
# header comment line 2

- name: Old Conf 2024
  url: https://example.com/2024/
  date: 2024-03-07
  end: 2024-03-09
  roles: [staff]

- name: New Conf 2025
  url: https://example.com/2025/
  date: 2025-09-19
  end: 2025-09-21
  roles: [noc, core]
  note: "[slides](https://example.com/slides) and more"
"""

SAMPLE_README = """\
# Title

## 🎤 Conferences

<!-- CONFERENCES:START -->
old content
<!-- CONFERENCES:END -->

footer
"""


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """DATA_PATH / README_PATH を一時ディレクトリに差し替えたサンプル環境。"""
    data = tmp_path / "data" / "conferences.yml"
    data.parent.mkdir()
    data.write_text(SAMPLE_YAML, encoding="utf-8")
    readme = tmp_path / "README.md"
    readme.write_text(SAMPLE_README, encoding="utf-8")
    monkeypatch.setattr(lib, "ROOT", tmp_path)
    monkeypatch.setattr(lib, "DATA_PATH", data)
    monkeypatch.setattr(lib, "README_PATH", readme)
    return tmp_path


def valid_entry(**over) -> dict:
    e = {"name": "Conf", "url": "https://example.com/", "date": "2026-01-10", "roles": ["attendee"]}
    e.update(over)
    return e
