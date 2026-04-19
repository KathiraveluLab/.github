#!/usr/bin/env python3
"""
Update profile/README.md with a table of repositories, language distribution chart,
and a highlight of top organization contributors.

Reads:  GH_TOKEN  — GitHub token (GITHUB_TOKEN from Actions is sufficient)
        ORG       — GitHub organization name (e.g. KathiraveluLab)

Replaces the sections between:
    <!-- REPO-LIST:START -->    ... <!-- REPO-LIST:END -->
    <!-- LANG-CHART:START -->   ... <!-- LANG-CHART:END -->
    <!-- CONTRIBUTORS:START --> ... <!-- CONTRIBUTORS:END -->
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

CONTRIBUTORS_START_MARKER = "<!-- CONTRIBUTORS:START -->"
CONTRIBUTORS_END_MARKER   = "<!-- CONTRIBUTORS:END -->"

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


def fetch_language_bytes(repos: list[dict]) -> dict[str, int]:
    """
    Call /repos/{org}/{repo}/languages for every active repo and aggregate
    byte counts across the entire org. This captures *all* languages in each
    repo, not just the GitHub-detected primary language.
    """
    from collections import defaultdict

    total: dict[str, int] = defaultdict(int)
    active = [r for r in repos if not r.get("archived") and not r.get("fork")]
    print(f"  → Fetching per-repo language breakdown for {len(active)} repos…")
    for r in active:
        try:
            lang_data = gh_get(
                f"https://api.github.com/repos/{ORG}/{r['name']}/languages"
            )
            for lang, byte_count in lang_data.items():
                total[lang] += byte_count
        except Exception as exc:
            print(f"    [warn] Could not fetch languages for {r['name']}: {exc}")
    return dict(total)


def build_lang_chart(repos: list[dict]) -> str:
    """
    Return a Mermaid xychart-beta horizontal bar chart of language distribution.
    Each language gets its own row — labels never overlap regardless of count.
    Values are in KB; percentages are embedded in axis labels.
    """
    lang_bytes = fetch_language_bytes(repos)

    if not lang_bytes:
        return "<!-- no language data available -->"

    total_bytes = sum(lang_bytes.values())
    # Sort largest → smallest
    ranked = sorted(lang_bytes.items(), key=lambda x: -x[1])

    labels = []
    values = []
    for lang, byte_count in ranked:
        kb = round(byte_count / 1024, 2)
        pct = byte_count / total_bytes * 100
        labels.append(f'"{lang} ({pct:.1f}%)"')
        values.append(str(kb))

    x_axis = "[" + ", ".join(labels) + "]"
    y_vals  = "[" + ", ".join(values) + "]"

    chart = (
        "```mermaid\n"
        "xychart-beta horizontal\n"
        '    title "Language Distribution by Code Volume (KB)"\n'
        f"    x-axis {x_axis}\n"
        '    y-axis "KB"\n'
        f"    bar {y_vals}\n"
        "```"
    )
    return chart


def fetch_contributors(repos: list[dict]) -> dict:
    """
    Fetch and aggregate contributors across all public repos.
    Excludes bots.
    """
    from collections import defaultdict

    stats = defaultdict(lambda: {"count": 0, "avatar": "", "url": ""})
    active = [r for r in repos if not r.get("archived") and not r.get("fork")]
    
    print(f"  → Fetching contributors for {len(active)} repos…")
    for r in active:
        try:
            # per_page=100 is usually enough for most org repos
            data = gh_get(f"https://api.github.com/repos/{ORG}/{r['name']}/contributors?per_page=100")
            for c in data:
                login = c["login"]
                if "[bot]" in login.lower():
                    continue
                
                stats[login]["count"] += c["contributions"]
                stats[login]["avatar"] = c["avatar_url"]
                stats[login]["url"] = c["html_url"]
        except Exception as exc:
            print(f"    [warn] Could not fetch contributors for {r['name']}: {exc}")
            
    return dict(stats)


def build_contributors_section(stats: dict, limit: int = 20) -> str:
    """
    Build a grid of top contributors.
    """
    top = sorted(stats.items(), key=lambda x: x[1]["count"], reverse=True)[:limit]
    
    if not top:
        return "<!-- No contributors found -->"
        
    html = ['<table style="border-collapse: collapse; border: none;">']
    row_count = 0
    items_per_row = 5
    
    for login, info in top:
        if row_count % items_per_row == 0:
            if row_count > 0:
                html.append("  </tr>")
            html.append("  <tr>")
            
        cell = (
            f'    <td align="center" style="border: none; padding: 10px;">'
            f'<a href="{info["url"]}">'
            f'<img src="{info["avatar"]}" width="100px;" alt="{login}" style="border-radius: 50%;"/><br />'
            f'<sub><b>{login}</b></sub>'
            f'</a><br />'
            f'<sub>{info["count"]} contributions</sub>'
            f'</td>'
        )
        html.append(cell)
        row_count += 1
        
    # Fill empty cells in last row if needed
    while row_count % items_per_row != 0:
        html.append('    <td style="border: none;"></td>')
        row_count += 1
        
    html.append("  </tr>")
    html.append("</table>")
    
    return "\n".join(html)


def _replace_marker_section(content: str, start: str, end: str, body: str) -> str:
    """Replace content between start/end markers, or append a new section."""
    new_block = f"{start}\n{body}\n{end}"
    if start in content:
        pattern = re.escape(start) + ".*?" + re.escape(end)
        return re.sub(pattern, new_block, content, flags=re.DOTALL)
    # Markers missing — append at end
    return content + f"\n\n{new_block}\n"


def inject_into_readme(table: str, chart: str, contributors: str) -> None:
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    content = _replace_marker_section(content, START_MARKER, END_MARKER, table)
    content = _replace_marker_section(content, CHART_START_MARKER, CHART_END_MARKER, chart)
    content = _replace_marker_section(content, CONTRIBUTORS_START_MARKER, CONTRIBUTORS_END_MARKER, contributors)

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def main() -> None:
    print(f"Fetching repositories for org: {ORG}")
    repos = fetch_all_repos()
    print(f"  → Found {len(repos)} total repos")

    table = build_table(repos)
    chart = build_lang_chart(repos)
    
    contrib_stats = fetch_contributors(repos)
    contributors = build_contributors_section(contrib_stats, limit=20)
    
    inject_into_readme(table, chart, contributors)
    print("README updated successfully.")


if __name__ == "__main__":
    main()
