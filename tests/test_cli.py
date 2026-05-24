from __future__ import annotations

from pathlib import Path

from memorizerepo.cli import DEFAULT_MEMORY_PATH, build_parser, repo_name


def test_repo_name_uses_resolved_repo_folder(tmp_path: Path) -> None:
    repo = tmp_path / "myGitRepo"
    repo.mkdir()

    assert repo_name(str(repo)) == "myGitRepo"


def test_parser_defaults_to_current_repo_and_memory_path() -> None:
    args = build_parser().parse_args([])

    assert args.repo_path == "."
    assert args.memory_path == DEFAULT_MEMORY_PATH

