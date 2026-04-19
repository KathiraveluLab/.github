#!/usr/bin/env python3
"""
Update profile/README.md with a table of all KathiraveluLab org repositories
and their primary programming languages.

Reads:  GH_TOKEN  — GitHub token (GITHUB_TOKEN from Actions is sufficient)
        ORG       — GitHub organization name (e.g. KathiraveluLab)

Replaces the section between:
    <!-- REPO-LIST:START -->
    ...
    <!-- REPO-LIST:END -->
in profile/README.md with a fresh Markdown table.
"""

import json
import os
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone

ORG = os.environ.get("ORG", "KathiraveluLab")
TOKEN = os.environ.get("GH_TOKEN", "")
README_PATH = "profile/README.md"

START_MARKER = "<!-- REPO-LIST:START -->"
END_MARKER   = "<!-- REPO-LIST:END -->"

LANGUAGE_BADGE_COLORS = {
    "Python":     "3572A5",
    "Mojo":       "FF6700",
    "Go":         "00ACD7",
    "JavaScript": "F1E05A",
    "TypeScript": "2B7489",
    "Java":       "B07219",
    "Rust":       "DEA584",
    "C":          "555555",
    "C++":        "F34B7D",
    "Elixir":     "6E4A7E",
    "Shell":      "89E051",
    "HTML":       "E34C26",
    "CSS":        "563D7C",
    "Jupyter Notebook": "DA5B0B",
}

DEFAULT_COLOR = "8A8A8A"


def gh_get(url: str) -> list | dict:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def fetch_all_repos() -> list[dict]:
    repos = []
    page = 1
    while True:
        data = gh_get(
            f"https://api.github.com/orgs/{ORG}/repos"
            f"?per_page=100&page={page}&sort=name&type=public"
        )
        if not data:
            break
        repos.extend(data)
        page += 1
    return repos


def language_badge(lang: str) -> str:
    """Return a shields.io badge img tag for the given language."""
    if not lang or lang == "—":
        return "—"
    color = LANGUAGE_BADGE_COLORS.get(lang, DEFAULT_COLOR)
    label = lang.replace("-", "--").replace(" ", "_")
    return (
        f"![{lang}](https://img.shields.io/badge/{label}-{color}"
        f"?style=flat-square&logo={lang.lower().replace(' ', '')}&logoColor=white)"
    )


def build_table(repos: list[dict]) -> str:
    rows = []
    for r in sorted(repos, key=lambda x: x["name"].lower()):
        if r.get("archived") or r.get("fork"):
            continue
        name = f"[**{r['name']}**]({r['html_url']})"
        lang = r.get("language") or "—"
        badge = language_badge(lang)
        desc = (r.get("description") or "").replace("|", "\\|")
        stars = r.get("stargazers_count", 0)
        star_str = f"⭐ {stars}" if stars else ""
        rows.append(f"| {name} | {badge} | {desc} | {star_str} |")

    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = [
        f"> Last updated: {updated} · {len(rows)} active public repositories\n",
        "| Repository | Language | Description | Stars |",
        "| --- | :---: | --- | :---: |",
    ]
    return "\n".join(header + rows)


def inject_into_readme(table: str) -> None:
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    new_block = f"{START_MARKER}\n{table}\n{END_MARKER}"

    if START_MARKER in content:
        pattern = re.escape(START_MARKER) + ".*?" + re.escape(END_MARKER)
        content = re.sub(pattern, new_block, content, flags=re.DOTALL)
    else:
        # Append section at the end if markers are missing
        content += f"\n\n## 🔬 Projects\n\n{new_block}\n"

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def main() -> None:
    print(f"Fetching repositories for org: {ORG}")
    repos = fetch_all_repos()
    print(f"  → Found {len(repos)} total repos")

    table = build_table(repos)
    inject_into_readme(table)
    print("README updated successfully.")


if __name__ == "__main__":
    main()
