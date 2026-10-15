"""Generate Chinese profile cards using GitHub's API and authenticated gh CLI."""
import json
import os
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGIN = os.environ.get("GITHUB_REPOSITORY_OWNER", "MingWangD")
QUERY = """query($login: String!, $cursor: String) {
  user(login: $login) {
    contributionsCollection {
      commitContributionsByRepository(maxRepositories: 100) {
        repository { isPrivate } contributions { totalCount }
      }
      issueContributionsByRepository(maxRepositories: 100) {
        repository { isPrivate } contributions { totalCount }
      }
      pullRequestContributionsByRepository(maxRepositories: 100) {
        repository { isPrivate } contributions { totalCount }
      }
      pullRequestReviewContributionsByRepository(maxRepositories: 100) {
        repository { isPrivate } contributions { totalCount }
      }
    }
    repositories(first: 100, after: $cursor, privacy: PUBLIC,
                 isFork: false, ownerAffiliations: OWNER) {
      nodes { name stargazerCount
        languages(first: 100, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}"""

def fetch():
    repositories, cursor = [], None
    while True:
        command = ["gh", "api", "graphql", "-f", f"query={QUERY}", "-f", f"login={LOGIN}"]
        if cursor:
            command.extend(["-f", f"cursor={cursor}"])
        response = json.loads(subprocess.check_output(command, text=True))
        if response.get("errors"):
            raise RuntimeError("GitHub GraphQL returned errors")
        user = response["data"]["user"]
        if not user:
            raise RuntimeError("GitHub user not found")
        repositories.extend(user["repositories"]["nodes"])
        page = user["repositories"]["pageInfo"]
        if not page["hasNextPage"]:
            return user["contributionsCollection"], repositories
        cursor = page["endCursor"]

def text(x, y, value, size=14, color="#c9d1d9", weight="400"):
    return (f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" '
            f'font-weight="{weight}">{escape(str(value))}</text>')

def card(title, subtitle, body):
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return "\n".join([
        '<svg xmlns="http://www.w3.org/2000/svg" width="480" height="228" viewBox="0 0 480 228" role="img">',
        f"<title>{escape(title)}</title><desc>{escape(subtitle)}</desc>",
        '<rect x="0.5" y="0.5" width="479" height="227" rx="12" fill="#0d1117" stroke="#30363d"/>',
        '<g font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Noto Sans CJK SC,Microsoft YaHei,sans-serif">',
        text(24, 35, title, 20, "#e6edf3", "600"),
        text(24, 58, subtitle, 12, "#8b949e"),
        *body,
        text(24, 210, f"更新于 {date} UTC", 11, "#8b949e"),
        "</g></svg>\n",
    ])

def main():
    contributions, repositories = fetch()
    def public_count(field):
        return sum(item["contributions"]["totalCount"] for item in contributions[field]
                   if not item["repository"]["isPrivate"])

    statistics = [
        ("代码提交", public_count("commitContributionsByRepository")),
        ("Pull Request", public_count("pullRequestContributionsByRepository")),
        ("Issue", public_count("issueContributionsByRepository")),
        ("代码审查", public_count("pullRequestReviewContributionsByRepository")),
        ("仓库获星", sum(repo["stargazerCount"] for repo in repositories)),
        ("公开原创仓库", len(repositories)),
    ]
    body = []
    for index, (label, value) in enumerate(statistics):
        x, y = 24 + (index % 2) * 238, 92 + (index // 2) * 42
        body.extend([text(x, y, label), text(x + 160, y, value, 18, "#a5d6ff", "600")])
    stats = card("GitHub 统计", "提交 / PR / Issue / 审查：过去一年公开贡献", body)
    sizes, colors = defaultdict(int), {}
    for repository in repositories:
        if repository["name"].lower() == LOGIN.lower():
            continue  # Exclude the profile card generator from the language breakdown.
        for edge in repository["languages"]["edges"]:
            name = edge["node"]["name"]
            sizes[name] += edge["size"]
            colors[name] = edge["node"]["color"] or "#8b949e"
    ranked = sorted(sizes.items(), key=lambda item: (-item[1], item[0]))
    shown = ranked[:5]
    if len(ranked) > 5:
        shown.append(("其他", sum(size for _, size in ranked[5:])))
        colors["其他"] = "#8b949e"
    total, body, x = sum(sizes.values()), [], 24.0
    for name, size in shown:
        width = size / total * 432
        body.append(f'<rect x="{x:.3f}" y="78" width="{width:.3f}" height="10" fill="{colors[name]}"/>')
        x += width
    for index, (name, size) in enumerate(shown):
        x, y = 24 + (index % 2) * 222, 120 + (index // 2) * 30
        body.append(f'<circle cx="{x + 4}" cy="{y - 5}" r="4" fill="{colors[name]}"/>')
        body.append(text(x + 16, y, f"{name} {size / total:.1%}", 13))
    if not total:
        body.append(text(24, 120, "暂无公开代码语言数据"))
    languages = card("常用语言分布", "公开原创仓库 · 按代码字节数 · 排除主页仓库", body)
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    (assets / "stats.svg").write_text(stats, encoding="utf-8")
    (assets / "languages.svg").write_text(languages, encoding="utf-8")
    print(f"Generated cards for {LOGIN}: {len(repositories)} public original repositories")

if __name__ == "__main__":
    main()
