#!/usr/bin/env python3
"""
Update profile/README.md with a table of all KathiraveluLab org repositories
and their primary programming languages, plus a Mermaid pie chart of language
distribution.

Reads:  GH_TOKEN  — GitHub token (GITHUB_TOKEN from Actions is sufficient)
        ORG       — GitHub organization name (e.g. KathiraveluLab)

Replaces the sections between:
    <!-- REPO-LIST:START --> ... <!-- REPO-LIST:END -->
    <!-- LANG-CHART:START --> ... <!-- LANG-CHART:END -->
in profile/README.md with fresh generated content.
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

CHART_START_MARKER = "<!-- LANG-CHART:START -->"
CHART_END_MARKER   = "<!-- LANG-CHART:END -->"

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
        forks = r.get("forks_count", 0)
        star_str = f"⭐ {stars}" if stars else ""
        fork_str = f"🍴 {forks}" if forks else ""
        rows.append(f"| {name} | {badge} | {desc} | {star_str} | {fork_str} |")

    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = [
        f"> Last updated: {updated} · {len(rows)} active public repositories\n",
        "| Repository | Language | Description | Stars | Forks |",
        "| --- | :---: | --- | :---: | :---: |",
    ]
    return "\n".join(header + rows)


def build_pie_chart(repos: list[dict]) -> str:
    """Return a Mermaid pie chart block for language distribution."""
    from collections import Counter

    lang_counts: Counter = Counter()
    for r in repos:
        if r.get("archived") or r.get("fork"):
            continue
        lang = r.get("language")
        if lang:
            lang_counts[lang] += 1
        else:
            lang_counts["Other / Unknown"] += 1

    # Sort by count descending; fold tiny slices (<2 repos) into "Other"
    other = 0
    lines = []
    for lang, count in lang_counts.most_common():
        if count < 2:
            other += count
        else:
            lines.append(f'    "{lang}" : {count}')
    if other:
        lines.append(f'    "Other" : {other}')

    chart = "```mermaid\npie title Primary Languages Across Projects\n" + "\n".join(lines) + "\n```"
    return chart


def _replace_marker_section(content: str, start: str, end: str, body: str) -> str:
    """Replace content between start/end markers, or append a new section."""
    new_block = f"{start}\n{body}\n{end}"
    if start in content:
        pattern = re.escape(start) + ".*?" + re.escape(end)
        return re.sub(pattern, new_block, content, flags=re.DOTALL)
    # Markers missing — append at end
    return content + f"\n\n{new_block}\n"


def inject_into_readme(table: str, chart: str) -> None:
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    content = _replace_marker_section(content, START_MARKER, END_MARKER, table)
    content = _replace_marker_section(content, CHART_START_MARKER, CHART_END_MARKER, chart)

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def main() -> None:
    print(f"Fetching repositories for org: {ORG}")
    repos = fetch_all_repos()
    print(f"  → Found {len(repos)} total repos")

    table = build_table(repos)
    chart = build_pie_chart(repos)
    inject_into_readme(table, chart)
    print("README updated successfully.")


if __name__ == "__main__":
    main()
