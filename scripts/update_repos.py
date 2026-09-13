#!/usr/bin/env python3
import json
import os
import re
import urllib.request

USERNAME = os.getenv("GITHUB_USERNAME", "7oSkaaa")
TOKEN = os.getenv("GITHUB_TOKEN")
LIMIT = int(os.getenv("REPO_LIMIT", "6"))
THEME = os.getenv("CARD_THEME", "tokyonight")
README_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "readme.md"))

REPOS_START_MARKER = "<!-- REPOS-START -->"
REPOS_END_MARKER = "<!-- REPOS-END -->"

ACTIVITY_START_MARKER = "<!-- ACTIVITY-START -->"
ACTIVITY_END_MARKER = "<!-- ACTIVITY-END -->"


def fetch_json(url):
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "update-repos-script",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def fetch_repos():
    repos = []
    page = 1
    while True:
        url = f"https://api.github.com/users/{USERNAME}/repos?per_page=100&page={page}&type=owner"
        data = fetch_json(url)
        if not data:
            break
        repos.extend(data)
        if len(data) < 100:
            break
        page += 1

    return repos


def get_top_repos(repos, limit=6):
    filtered = [
        r
        for r in repos
        if not r.get("fork")
        and not r.get("private", False)
        and r.get("name", "").lower() != USERNAME.lower()
    ]
    # Sort by stargazers_count descending, then repo name
    filtered.sort(
        key=lambda r: (r.get("stargazers_count", 0), r.get("name", "")),
        reverse=True,
    )
    return filtered[:limit]


def generate_table_html(repos):
    rows = []
    # 2 columns per row
    for i in range(0, len(repos), 2):
        pair = repos[i : i + 2]
        cells = []
        for repo in pair:
            name = repo["name"]
            cell = (
                f'    <td align="center" width="50%">\n'
                f'      <a href="https://github/{USERNAME}/{name}">\n'
                f'        <img src="https://github-stats-extended.vercel.app/api/pin/?username={USERNAME}&repo={name}&theme={THEME}" alt="{name}" />\n'
                f"      </a>\n"
                f"    </td>"
            ).replace("https://github/", "https://github.com/")
            cells.append(cell)

        # If odd number of repos, fill with empty cell
        if len(cells) == 1:
            cells.append('    <td align="center" width="50%"></td>')

        row_str = "  <tr>\n" + "\n".join(cells) + "\n  </tr>"
        rows.append(row_str)

    table_content = "\n".join(rows)
    return f'<table align="center">\n{table_content}\n</table>'


def fetch_recent_activity(limit=5):
    url = f"https://api.github.com/users/{USERNAME}/events/public?per_page=30"
    try:
        events = fetch_json(url)
    except Exception as e:
        print(f"Warning: could not fetch public events: {e}")
        return ""

    icons = {
        "PushEvent": "⚡",
        "CreateEvent": "🌱",
        "PullRequestEvent": "🔀",
        "IssuesEvent": "📌",
        "WatchEvent": "⭐",
        "ReleaseEvent": "🚀",
        "ForkEvent": "🍴",
    }

    seen = set()
    items = []

    for ev in events:
        etype = ev.get("type", "")
        repo_name = ev.get("repo", {}).get("name", "")
        created = ev.get("created_at", "")[:10]

        key = (etype, repo_name, created)
        if key in seen:
            continue
        seen.add(key)

        icon = icons.get(etype, "🔹")
        repo_url = f"https://github.com/{repo_name}"

        if etype == "PushEvent":
            desc = f"Pushed to [{repo_name}]({repo_url})"
        elif etype == "CreateEvent":
            ref_type = ev.get("payload", {}).get("ref_type", "repository")
            desc = f"Created {ref_type} on [{repo_name}]({repo_url})"
        elif etype == "PullRequestEvent":
            action = ev.get("payload", {}).get("action", "opened")
            desc = f"{action.capitalize()} pull request in [{repo_name}]({repo_url})"
        elif etype == "WatchEvent":
            desc = f"Starred [{repo_name}]({repo_url})"
        elif etype == "ReleaseEvent":
            desc = f"Published release in [{repo_name}]({repo_url})"
        else:
            desc = f"Activity on [{repo_name}]({repo_url})"

        items.append(f"- {icon} {desc} `({created})`")
        if len(items) >= limit:
            break

    return "\n".join(items)


def update_section(content, start_marker, end_marker, replacement_body):
    pattern = re.compile(
        rf"({re.escape(start_marker)})(.*?)({re.escape(end_marker)})",
        re.DOTALL,
    )
    replacement = f"{start_marker}\n\n{replacement_body}\n\n{end_marker}"
    if pattern.search(content):
        return pattern.sub(replacement, content)
    return content


def update_readme():
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Update Repos
    repos = fetch_repos()
    top_repos = get_top_repos(repos, limit=LIMIT)
    new_table = generate_table_html(top_repos)
    content = update_section(content, REPOS_START_MARKER, REPOS_END_MARKER, new_table)

    # Update Activity if marker exists
    if ACTIVITY_START_MARKER in content:
        activity_md = fetch_recent_activity(limit=5)
        if activity_md:
            content = update_section(content, ACTIVITY_START_MARKER, ACTIVITY_END_MARKER, activity_md)

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Successfully updated {README_PATH}:")
    print(f"- {len(top_repos)} top repositories synced")


if __name__ == "__main__":
    update_readme()
