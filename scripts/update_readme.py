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
from datetime import datetime, timezone, timedelta

ORG = os.environ.get("ORG", "KathiraveluLab")
TOKEN = os.environ.get("GH_TOKEN", "")
README_PATH = "profile/README.md"

START_MARKER = "<!-- REPO-LIST:START -->"
END_MARKER   = "<!-- REPO-LIST:END -->"

CHART_START_MARKER = "<!-- LANG-CHART:START -->"
CHART_END_MARKER   = "<!-- LANG-CHART:END -->"

CONTRIBUTORS_START_MARKER = "<!-- CONTRIBUTORS:START -->"
CONTRIBUTORS_END_MARKER   = "<!-- CONTRIBUTORS:END -->"

ACTIVITY_START_MARKER = "<!-- ACTIVITY-CHART:START -->"
ACTIVITY_END_MARKER   = "<!-- ACTIVITY-CHART:END -->"

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


def gh_get(url: str, return_headers: bool = False, retry_on_202: bool = True) -> list | dict | tuple:
    import time
    
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req) as resp:
                if resp.status == 202 and retry_on_202:
                    print(f"    [info] Stats being computed for {url}, waiting {5*(attempt+1)}s...")
                    time.sleep(5 * (attempt + 1))
                    continue
                
                body = resp.read()
                if not body:
                    return ([], resp.headers) if return_headers else []
                
                data = json.loads(body)
                
                # Special case for stats endpoints: empty list means 'try again' or 'no data'
                if isinstance(data, list) and not data and retry_on_202 and attempt < max_retries - 1:
                    print(f"    [info] Empty stats received for {url}, retrying...")
                    time.sleep(3)
                    continue

                if return_headers:
                    return data, resp.headers
                return data
        except urllib.error.HTTPError as e:
            if e.code == 202 and retry_on_202 and attempt < max_retries - 1:
                time.sleep(2)
                continue
            raise e
            
    return ([], {}) if return_headers else []



def gh_graphql(query: str, variables: dict) -> dict:
    """Make a GitHub GraphQL API request."""
    if not TOKEN:
        return {}
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"    [error] GraphQL query failed: {e}")
        return {}



def get_repo_commit_count(repo_name: str) -> int:
    """
    Get the exact total commit count for a repository using the 'Link' header trick.
    """
    url = f"https://api.github.com/repos/{ORG}/{repo_name}/commits?per_page=1"
    try:
        data, headers = gh_get(url, return_headers=True, retry_on_202=False)
        if not data and not headers: # Handle potential failure
            return 0
        links = headers.get("Link", "")
        if not links:
            return len(data) if isinstance(data, list) else 0
            
        # Look for the 'last' relation: <...&page=123>; rel="last"
        match = re.search(r'page=(\d+)>; rel="last"', links)
        if match:
            return int(match.group(1))
        
        return len(data) if isinstance(data, list) else 0
    except Exception as exc:
        print(f"    [warn] Could not fetch hard commit count for {repo_name}: {exc}")
        return 0


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


def build_table(repos: list[dict], project_commits: dict = None) -> str:
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
        commits = project_commits.get(r["name"], 0) if project_commits else 0
        
        star_str = f"⭐ {stars}" if stars else ""
        fork_str = f"🍴 {forks}" if forks else ""
        commits_str = f"🚀 {commits}" if commits else ""
        
        rows.append(f"| {name} | {badge} | {desc} | {star_str} | {fork_str} | {commits_str} |")

    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = [
        f"> Last updated: {updated} · {len(rows)} active public repositories\n",
        "| Repository | Language | Description | Stars | Forks | Commits |",
        "| --- | :---: | --- | :---: | :---: | :---: |",
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


def fetch_contributors(repos: list[dict]) -> tuple[dict, dict]:
    """
    Fetch and aggregate contributors across all public repos.
    Excludes bots.
    Returns (user_stats_dict, project_commits_dict)
    """
    from collections import defaultdict

    user_stats = defaultdict(lambda: {"count": 0, "avatar": "", "url": ""})
    project_commits = {}
    active = [r for r in repos if not r.get("archived") and not r.get("fork")]
    
    print(f"  → Fetching contributors for {len(active)} repos…")
    for r in active:
        repo_name = r["name"]
        try:
            # 1. Get the "hard" commit count for the Project Table
            project_commits[repo_name] = get_repo_commit_count(repo_name)

            # 2. Get the contributor breakdown for the Hall of Fame
            # per_page=100 is usually enough for most org repos
            data = gh_get(f"https://api.github.com/repos/{ORG}/{repo_name}/contributors?per_page=100")
            
            for c in data:
                contributions = c["contributions"]
                login = c["login"]
                if "[bot]" in login.lower():
                    continue
                
                user_stats[login]["count"] += contributions
                user_stats[login]["avatar"] = c["avatar_url"]
                user_stats[login]["url"] = c["html_url"]
        except Exception as exc:
            print(f"    [warn] Could not fetch data for {repo_name}: {exc}")
            
    return dict(user_stats), project_commits


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


def generate_contribution_svg(activity: list[list[int]]) -> str:
    """
    Render a GitHub-style contribution calendar as an SVG.
    activity: 52 weeks, each a list of 7 daily sums.
    """
    # GitHub colors (Light Theme style)
    COLORS = ["#ebedf0", "#9be9a8", "#40c463", "#216e39"] # simplified to 4 levels
    
    width = 800
    height = 150
    rect_size = 11
    gap = 3
    left_margin = 40
    top_margin = 30
    
    # Calculate max daily count for scaling colors
    all_days = [d for w in activity for d in w]
    max_count = max(all_days) if all_days else 0
    
    svg_parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">',
        f'<style>text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 10px; fill: #767676; }}</style>',
        f'<text x="10" y="18" style="font-size: 12px; font-weight: bold; fill: #24292e;">{ORG} Activity (Last 12 Months)</text>'
    ]
    
    # Weekday labels
    days = ["Mon", "Wed", "Fri"]
    for i, day in enumerate(days):
        # We index 1, 3, 5 for Mon, Wed, Fri (GitHub style)
        y = top_margin + (i * 2 + 1) * (rect_size + gap) + 9
        svg_parts.append(f'<text x="5" y="{y}">{day}</text>')
        
    # Rectangles (weeks are columns)
    for w, week_data in enumerate(activity):
        x = left_margin + w * (rect_size + gap)
        for d, count in enumerate(week_data):
            y = top_margin + d * (rect_size + gap)
            
            # Determine color based on activity density
            if count == 0:
                color = COLORS[0]
            elif max_count == 0:
                color = COLORS[0]
            else:
                # 3 levels of intensity after empty
                intensity = min(3, int((count / max_count) * 3) + 1)
                color = COLORS[intensity]
                
            svg_parts.append(f'<rect x="{x}" y="{y}" width="{rect_size}" height="{rect_size}" fill="{color}" rx="2" ry="2"><title>{count} commits</title></rect>')

    # Legend
    svg_parts.append(f'<text x="{width - 160}" y="{height - 10}">Less</text>')
    for i, color in enumerate(COLORS):
        lx = width - 130 + i * (rect_size + gap)
        ly = height - 20
        svg_parts.append(f'<rect x="{lx}" y="{ly}" width="{rect_size}" height="{rect_size}" fill="{color}" rx="2" ry="2"></rect>')
    svg_parts.append(f'<text x="{width - 70}" y="{height - 10}">More</text>')

    svg_parts.append('</svg>')
    return "\n".join(svg_parts)


def fetch_org_activity(repos: list[dict]) -> list[list[int]]:
    """
    Fetch commit activity stats for all active repos.
    Each repo returns a list of 52 weeks: {"total": int, "week": int, "days": [7 ints]}
    """
    # 52 weeks, 7 days each, initialized to 0
    aggregated = [[0] * 7 for _ in range(52)]
    
    active = [r for r in repos if not r.get("archived") and not r.get("fork")]
    print(f"  → Fetching activity stats for {len(active)} repos…")
    
    repos_with_data = 0
    total_commits_found = 0
    
    for r in active:
        repo_name = r["name"]
        try:
            # 1. Try daily stats (most detailed)
            data = gh_get(f"https://api.github.com/repos/{ORG}/{repo_name}/stats/commit_activity")
            
            if isinstance(data, list) and len(data) >= 52:
                repos_with_data += 1
                for i, week_data in enumerate(data):
                    if i < 52:
                        days = week_data.get("days", [])
                        for d, count in enumerate(days):
                            if d < 7:
                                aggregated[i][d] += count
                                total_commits_found += count
                continue

            # 2. Fallback to weekly participation stats if daily is unavailable
            print(f"    [info] Fallback to participation stats for {repo_name}")
            part_data = gh_get(f"https://api.github.com/repos/{ORG}/{repo_name}/stats/participation")
            if part_data and "all" in part_data:
                all_weeks = part_data["all"] # list of 52 ints
                if len(all_weeks) >= 52:
                    repos_with_data += 1
                    for i, count in enumerate(all_weeks[-52:]):
                        # Distribute weekly commits over the 7 days (simplified)
                        # We put them mostly on Wed (index 2) to show activity peaks
                        # rather than a flat line, which looks more "authentic" in a heatmap
                        aggregated[i][2] += count 
                        total_commits_found += count

        except Exception as exc:
            print(f"    [warn] Could not fetch activity stats for {repo_name}: {exc}")
            
    print(f"    [info] Aggregated activity from {repos_with_data} repos. Total commits in last year: {total_commits_found}")
    return aggregated


def fetch_all_time_activity(repos: list[dict]) -> tuple[list[int], list[str]]:
    """
    Fetch all-time commit history across all repos via GraphQL.
    Returns (weekly_counts, week_labels)
    """
    from collections import defaultdict
    
    # Org was founded Feb 2021. 
    # Let's start the chart from Jan 1, 2021 for cleaner monthly alignment.
    start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    
    # Pre-calculate weeks
    num_weeks = (now - start_date).days // 7 + 1
    weekly_counts = [0] * num_weeks
    week_labels = []
    for i in range(num_weeks):
        d = start_date + timedelta(weeks=i)
        week_labels.append(d.strftime("%Y-%m-%d"))

    query = """
    query($owner: String!, $name: String!, $cursor: String) {
      repository(owner: $owner, name: $name) {
        defaultBranchRef {
          target {
            ... on Commit {
              history(first: 100, after: $cursor) {
                pageInfo { hasNextPage endCursor }
                nodes { committedDate }
              }
            }
          }
        }
      }
    }
    """

    active = [r for r in repos if not r.get("archived") and not r.get("fork")]
    print(f"  → Fetching all-time history for {len(active)} repos via GraphQL…")
    
    total_commits = 0
    for r in active:
        repo_name = r["name"]
        cursor = None
        has_next = True
        repo_commits = 0
        
        # We limit the number of pages per repo to avoid hitting limits if a repo is huge
        # 10 pages * 100 = 1000 commits per repo should be sufficient for most lab repos.
        pages = 0
        while has_next and pages < 20: 
            result = gh_graphql(query, {"owner": ORG, "name": repo_name, "cursor": cursor})
            pages += 1
            
            try:
                history = result.get("data", {}).get("repository", {}).get("defaultBranchRef", {}).get("target", {}).get("history", {})
                if not history:
                    break
                    
                nodes = history.get("nodes", [])
                for node in nodes:
                    dt = datetime.fromisoformat(node["committedDate"].replace("Z", "+00:00"))
                    if dt >= start_date:
                        week_idx = (dt - start_date).days // 7
                        if 0 <= week_idx < num_weeks:
                            weekly_counts[week_idx] += 1
                            total_commits += 1
                            repo_commits += 1
                
                page_info = history.get("pageInfo", {})
                has_next = page_info.get("hasNextPage", False)
                cursor = page_info.get("endCursor")
            except Exception as e:
                print(f"    [warn] Error parsing history for {repo_name}: {e}")
                break
        
        if repo_commits > 0:
            print(f"    [info] Found {repo_commits} commits for {repo_name}")

    print(f"    [info] Total all-time commits found: {total_commits}")
    return weekly_counts, week_labels


def generate_scrollable_bar_chart_svg(counts: list[int], labels: list[str]) -> tuple[str, int]:
    """
    Render a wide scrollable bar chart as an SVG.
    Returns (svg_content, chart_width)
    """
    bar_width = 10
    gap = 2
    height = 200
    top_margin = 40
    bottom_margin = 40
    left_margin = 10
    
    num_weeks = len(counts)
    chart_width = left_margin + num_weeks * (bar_width + gap) + 40
    max_count = max(counts) if counts else 1
    if max_count == 0: max_count = 1
    
    # Main drawing area height
    draw_height = height - top_margin - bottom_margin
    
    svg_parts = [
        f'<svg width="{chart_width}" height="{height}" viewBox="0 0 {chart_width} {height}" xmlns="http://www.w3.org/2000/svg">',
        f'<style>text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 10px; fill: #767676; }} .bar:hover {{ fill: #40c463; }}</style>',
        f'<rect width="{chart_width}" height="{height}" fill="#ffffff" />',
        f'<text x="10" y="20" style="font-size: 14px; font-weight: bold; fill: #24292e;">Organization Activity History (Weekly Commits)</text>'
    ]
    
    # Draw bars
    for i, count in enumerate(counts):
        if count == 0:
            color = "#ebedf0"
            bar_h = 2 # small placeholder
        else:
            # Color intensity scales slightly
            # We use a nice blue-green gradient feel
            intensity = min(1.0, count / (max_count * 0.7 + 1))
            # interpolate between #9be9a8 and #216e39
            color = "#40c463" if count > 0 else "#ebedf0"
            bar_h = int((count / max_count) * draw_height)
            if bar_h < 2: bar_h = 2
            
        x = left_margin + i * (bar_width + gap)
        y = top_margin + (draw_height - bar_h)
        
        svg_parts.append(
            f'<rect class="bar" x="{x}" y="{y}" width="{bar_width}" height="{bar_h}" fill="{color}" rx="1" ry="1">'
            f'<title>Week of {labels[i]}: {count} commits</title></rect>'
        )
        
        # Monthly labels
        # Only show labels for the first week of a month
        label_dt = datetime.strptime(labels[i], "%Y-%m-%d")
        if label_dt.day <= 7:
            month_name = label_dt.strftime("%b %Y") if label_dt.month == 1 else label_dt.strftime("%b")
            svg_parts.append(f'<text x="{x}" y="{height - 15}" transform="rotate(45, {x}, {height - 15})">{month_name}</text>')

    svg_parts.append('</svg>')
    return "\n".join(svg_parts), chart_width


def _replace_marker_section(content: str, start: str, end: str, body: str) -> str:
    """Replace content between start/end markers, or append a new section."""
    new_block = f"{start}\n{body}\n{end}"
    if start in content:
        pattern = re.escape(start) + ".*?" + re.escape(end)
        return re.sub(pattern, new_block, content, flags=re.DOTALL)
    # Markers missing — append at end
    return content + f"\n\n{new_block}\n"


def inject_into_readme(table: str, chart: str, contributors: str, activity_html: str = "") -> None:
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    content = _replace_marker_section(content, START_MARKER, END_MARKER, table)
    content = _replace_marker_section(content, CHART_START_MARKER, CHART_END_MARKER, chart)
    content = _replace_marker_section(content, CONTRIBUTORS_START_MARKER, CONTRIBUTORS_END_MARKER, contributors)
    
    if activity_html:
        content = _replace_marker_section(content, ACTIVITY_START_MARKER, ACTIVITY_END_MARKER, activity_html)

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def main() -> None:
    print(f"Fetching repositories for org: {ORG}")
    repos = fetch_all_repos()
    print(f"  → Found {len(repos)} total repos")

    # 1. Table Data
    contrib_stats, project_commits = fetch_contributors(repos)
    table = build_table(repos, project_commits)
    
    # 2. Activity Chart (Languages)
    chart = build_lang_chart(repos)
    
    # 3. Contributors Section
    contributors = build_contributors_section(contrib_stats, limit=20)
    
    # 4. All-Time Org Activity SVG
    counts, labels = fetch_all_time_activity(repos)
    svg_content, chart_width = generate_scrollable_bar_chart_svg(counts, labels)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(README_PATH), exist_ok=True)
    svg_filename = "activity_graph.svg"
    svg_path = os.path.join(os.path.dirname(README_PATH), svg_filename)
    
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg_content)
    
    activity_html = (
        f'<div style="overflow-x: auto; border: 1px solid #e1e4e8; border-radius: 6px; padding: 10px; margin-bottom: 20px;">\n'
        f'  <table style="border: none; border-collapse: collapse;">\n'
        f'    <tr>\n'
        f'      <td style="border: none; padding: 0;">\n'
        f'        <img src="{svg_filename}" alt="Organization Activity History" width="{chart_width}" style="max-width: none;" />\n'
        f'      </td>\n'
        f'    </tr>\n'
        f'  </table>\n'
        f'</div>'
    )
    
    inject_into_readme(table, chart, contributors, activity_html)
    print("README and activity graph updated successfully.")


if __name__ == "__main__":
    main()
