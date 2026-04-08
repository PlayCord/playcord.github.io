#!/usr/bin/env python3


# disclaimer: This code is AI generated

"""Sync this site with the latest PlayCord release/tag.

What this script does:
1) Resolves latest GitHub release for quantumbagel/playcord.
   Falls back to latest tag if no release exists.
2) Clones that exact ref to a temporary directory.
3) Runs pdoc on the cloned api/ package, outputting to API/.
4) Updates content.json version + API docs button link.
5) Rebuilds index.html using generate.py.

Usage:
    python3 scripts/sync_playcord_release.py
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen


DEFAULT_REPO = "quantumbagel/playcord"


def run(cmd: list[str], cwd: Path | None = None) -> None:
    """Run a command and fail loudly if it returns non-zero."""
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def fetch_json(url: str) -> dict | list:
    with urlopen(url) as response:  # nosec B310 - trusted GitHub API URL
        return json.load(response)


def resolve_latest_ref(repo: str) -> tuple[str, str]:
    """Return (ref, source) where source is 'release' or 'tag'."""
    release_url = f"https://api.github.com/repos/{repo}/releases/latest"
    tags_url = f"https://api.github.com/repos/{repo}/tags"

    try:
        release_data = fetch_json(release_url)
        tag_name = release_data.get("tag_name")
        if tag_name:
            return str(tag_name), "release"
    except HTTPError as exc:
        if exc.code != 404:
            raise

    tags_data = fetch_json(tags_url)
    if not isinstance(tags_data, list) or not tags_data:
        raise RuntimeError(f"No tags found for {repo}")

    newest = tags_data[0].get("name")
    if not newest:
        raise RuntimeError(f"Latest tag payload for {repo} is missing a name")
    return str(newest), "tag"


def normalize_version(ref: str) -> str:
    if ref.startswith("v") and len(ref) > 1 and ref[1].isdigit():
        return ref[1:]
    return ref


def update_content_json(content_path: Path, version: str, api_href: str) -> bool:
    """Update version and API button href, return True if file changed."""
    data = json.loads(content_path.read_text(encoding="utf-8"))
    changed = False

    if data.get("version") != version:
        data["version"] = version
        changed = True

    buttons = data.get("top_buttons", [])
    for button in buttons:
        if button.get("text") == "API Docs" and button.get("href") != api_href:
            button["href"] = api_href
            changed = True

    if changed:
        content_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync PlayCord release docs and site content")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repo in owner/name format")
    parser.add_argument(
        "--site-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Path to site repository root",
    )
    args = parser.parse_args()

    site_root = Path(args.site_root).resolve()
    content_json = site_root / "content.json"
    template_html = site_root / "index.template.html"
    generate_py = site_root / "generate.py"
    api_dir = site_root / "docs"

    for required in (content_json, template_html, generate_py):
        if not required.exists():
            print(f"Missing required file: {required}", file=sys.stderr)
            return 1

    try:
        ref, ref_source = resolve_latest_ref(args.repo)
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to resolve latest ref: {exc}", file=sys.stderr)
        return 1

    version = normalize_version(ref)
    print(f"Resolved {args.repo} {ref_source}: {ref} (site version: {version})")

    with tempfile.TemporaryDirectory(prefix="playcord-release-") as tmp_dir:
        checkout_dir = Path(tmp_dir) / "playcord"

        try:
            run([
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                ref,
                f"https://github.com/{args.repo}.git",
                str(checkout_dir),
            ])
        except subprocess.CalledProcessError as exc:
            print(f"Git clone failed: {exc}", file=sys.stderr)
            return 1

        api_src = checkout_dir / "api"
        if not api_src.exists():
            print(f"Expected api directory not found: {api_src}", file=sys.stderr)
            return 1

        shutil.rmtree(api_dir, ignore_errors=True)

        try:
            run([
                sys.executable,
                "-m",
                "pdoc",
                str(api_src),
                "--output-directory",
                str(api_dir),
            ])
        except subprocess.CalledProcessError as exc:
            print(f"pdoc generation failed: {exc}", file=sys.stderr)
            return 1

    # Set API docs href to the 'docs' directory on the site (was previously "API")
    content_changed = update_content_json(content_json, version=version, api_href="docs")
    print(f"Updated {content_json.name}: {'yes' if content_changed else 'no changes'}")

    try:
        run([
            sys.executable,
            str(generate_py),
            str(content_json),
            str(template_html),
        ], cwd=site_root)
    except subprocess.CalledProcessError as exc:
        print(f"Site generation failed: {exc}", file=sys.stderr)
        return 1

    print("Done. Refreshed API docs, content.json, and index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

