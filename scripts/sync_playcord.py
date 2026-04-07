#!/usr/bin/env python3
"""Sync PlayCord website content from the upstream repository.

Features:
- Clone/update quantumbagel/playcord
- Upgrade pdoc and regenerate API docs
- Make /api/ resolve to API docs directly
- Inject homepage link into generated pdoc pages
- Discover available games from source and update guide readiness
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, List, Optional


DEFAULT_REPO_URL = "https://github.com/quantumbagel/playcord.git"
HOME_LINK_HTML = '<p id="playcord-home-link"><a href="/">Back to PlayCord Home</a></p>'


@dataclass(frozen=True)
class GameInfo:
    name: str
    slug: str


def run(cmd: List[str], cwd: Optional[Path] = None) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def slugify(name: str) -> str:
    normalized = name.strip().lower().replace("'", "")
    normalized = normalized.replace("!", "")
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return normalized


def ensure_repo(repo_url: str, repo_dir: Path, branch: str) -> None:
    if (repo_dir / ".git").exists():
        run(["git", "fetch", "origin", "--prune"], cwd=repo_dir)
        run(["git", "checkout", branch], cwd=repo_dir)
        run(["git", "pull", "--ff-only", "origin", branch], cwd=repo_dir)
        return

    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", "--depth", "1", "--branch", branch, repo_url, str(repo_dir)])


def ensure_pdoc(python_bin: str) -> None:
    run([python_bin, "-m", "pip", "install", "--upgrade", "pdoc"])


def copy_tree_contents(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        target = dst / child.name
        if child.is_dir():
            shutil.copytree(child, target, dirs_exist_ok=True)
        else:
            shutil.copy2(child, target)


def inject_home_link(html_path: Path) -> None:
    text = html_path.read_text(encoding="utf-8")
    if "playcord-home-link" in text:
        return
    marker = '<main class="pdoc">'
    if marker in text:
        text = text.replace(marker, marker + "\n" + HOME_LINK_HTML + "\n", 1)
        html_path.write_text(text, encoding="utf-8")


def update_api_docs(python_bin: str, repo_dir: Path, site_root: Path) -> None:
    module_path = repo_dir / "api"
    if not (module_path / "Game.py").exists():
        raise RuntimeError("Could not locate api module in cloned repo.")

    api_dir = site_root / "api"
    with TemporaryDirectory() as tmp_dir_raw:
        tmp_dir = Path(tmp_dir_raw)
        run([python_bin, "-m", "pdoc", "-o", str(tmp_dir), str(module_path)])
        copy_tree_contents(tmp_dir, api_dir)

    api_index = api_dir / "index.html"
    api_html = api_dir / "api.html"
    if api_html.exists():
        shutil.copy2(api_html, api_index)

    for html_file in [api_index, api_html]:
        if html_file.exists():
            inject_home_link(html_file)

    api_subdir = api_dir / "api"
    if api_subdir.exists():
        for html_file in api_subdir.glob("*.html"):
            inject_home_link(html_file)


def discover_games(repo_dir: Path) -> list[GameInfo]:
    candidates: list[GameInfo] = []
    seen: set[str] = set()

    for py_file in repo_dir.rglob("*.py"):
        if any(part.startswith(".") for part in py_file.parts):
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except Exception:
            continue

        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if not inherits_game(node):
                continue

            game_name = extract_class_name(node) or node.name
            slug = slugify(game_name)
            if not slug or slug in seen:
                continue
            seen.add(slug)
            candidates.append(GameInfo(name=game_name, slug=slug))

    return sorted(candidates, key=lambda g: g.name.lower())


def inherits_game(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "Game":
            return True
        if isinstance(base, ast.Attribute) and base.attr == "Game":
            return True
    return False


def extract_class_name(node: ast.ClassDef) -> Optional[str]:
    for stmt in node.body:
        if not isinstance(stmt, ast.Assign):
            continue
        for target in stmt.targets:
            if isinstance(target, ast.Name) and target.id == "name":
                if isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                    return stmt.value.value.strip()
    return None


def guide_ready(guide_path: Path) -> bool:
    if not guide_path.exists():
        return False
    text = guide_path.read_text(encoding="utf-8")
    return "will be placed here" not in text.lower()


def write_games_json(site_root: Path, games: List[GameInfo]) -> List[Dict[str, object]]:
    learn_dir = site_root / "learn"
    output: List[Dict[str, object]] = []
    for game in games:
        ready = guide_ready(learn_dir / f"{game.slug}.html")
        output.append({"name": game.name, "slug": game.slug, "ready": ready})

    data_dir = site_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "games.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    return output


def write_learn_index(site_root: Path, games_with_status: List[Dict[str, object]]) -> None:
    learn_index = site_root / "learn" / "index.html"
    lines = [
        "<!DOCTYPE html>",
        "<html lang=\"en\">",
        "<head>",
        "    <meta charset=\"UTF-8\">",
        "    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">",
        "    <title>Game Guides - PlayCord</title>",
        "    <link rel=\"stylesheet\" href=\"/assets/css/learn.css\">",
        "</head>",
        "<body>",
        "    <a href=\"/\">&larr; Back to Home</a>",
        "    <h1>Game Guides</h1>",
        "    <div class=\"content\">",
        "        <h2>Available Rules</h2>",
        "        <ul class=\"guide-list\">",
    ]

    for item in games_with_status:
        status_class = "ready" if item["ready"] else "missing"
        status_label = "Ready" if item["ready"] else "Missing"
        lines.append(
            f"            <li><a href=\"{item['slug']}.html\">{item['name']}</a>"
            f"<span class=\"status {status_class}\">{status_label}</span></li>"
        )

    lines += [
        "        </ul>",
        "    </div>",
        "</body>",
        "</html>",
        "",
    ]
    learn_index.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync PlayCord website assets and docs.")
    parser.add_argument("--site-root", default=".", help="Path to playcord.github.io workspace.")
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL)
    parser.add_argument("--repo-dir", default=".cache/playcord")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--python", default=sys.executable, help="Python interpreter for pip/pdoc.")
    parser.add_argument("--skip-repo-sync", action="store_true")
    parser.add_argument("--skip-pdoc", action="store_true")
    parser.add_argument("--skip-games-update", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    site_root = Path(args.site_root).resolve()
    repo_dir = site_root / args.repo_dir

    try:
        if not args.skip_repo_sync:
            ensure_repo(args.repo_url, repo_dir, args.branch)

        if not args.skip_pdoc:
            ensure_pdoc(args.python)
            update_api_docs(args.python, repo_dir, site_root)

        if not args.skip_games_update:
            games = discover_games(repo_dir)
            if not games:
                print("No games found from source; leaving game list unchanged.")
            else:
                status = write_games_json(site_root, games)
                write_learn_index(site_root, status)
                ready = sum(1 for item in status if item["ready"])
                print(f"Guides ready: {ready}/{len(status)}")

        return 0
    except Exception as exc:  # pragma: no cover
        print(f"Sync failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

