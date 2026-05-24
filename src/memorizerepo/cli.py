from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence


DEFAULT_MEMORY_PATH = "./.RepoMemory"


def repo_name(repo_path: str) -> str:
    """Return the display name for a repository path."""
    return Path(repo_path).expanduser().resolve().name


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="memorizerepo",
        description="Build memory for a code repository.",
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Path to the repository. Defaults to the current directory.",
    )
    parser.add_argument(
        "memory_path",
        nargs="?",
        default=DEFAULT_MEMORY_PATH,
        help="Path to the repository memory directory. Defaults to ./.RepoMemory.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    print(f"Hello from {repo_name(args.repo_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

