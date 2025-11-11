from pathlib import Path


def test_chinese_text_not_garbled() -> None:
    """Ensure key UI files still contain Chinese characters."""

    checkpoints = [
        ("src/app/ui/components.py", "打开时间轴文件"),
        ("src/app/ui/components.py", "自动计时"),
        ("src/app/ui/state.py", "运行中"),
    ]
    for rel_path, phrase in checkpoints:
        text = Path(rel_path).read_text(encoding="utf-8")
        assert phrase in text, f"{rel_path} lost '{phrase}'"


def test_no_question_mark_garble() -> None:
    """Ensure we didn't accidentally commit '??' artifacts."""

    bad_files = []
    for path in Path("src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "??" in text:
            bad_files.append(str(path))
    assert not bad_files, f"Suspicious '??' found in: {bad_files}"

