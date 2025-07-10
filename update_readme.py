import requests
import datetime
import re

GITHUB_USERNAME = "your-github-username"
GITHUB_TOKEN = "your-github-token"  # Optional, but recommended for higher rate limits

START_MARKER = "<!-- GITHUB_SUMMARY_START -->"
END_MARKER = "<!-- GITHUB_SUMMARY_END -->"

def fetch_yearly_events(username, token=None):
    headers = {"Authorization": f"token {token}"} if token else {}
    events = []
    page = 1
    this_year = datetime.datetime.now().year

    while True:
        url = f"https://api.github.com/users/{username}/events/public?page={page}&per_page=100"
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            break
        data = resp.json()
        if not data:
            break
        for event in data:
            event_year = datetime.datetime.strptime(event["created_at"], "%Y-%m-%dT%H:%M:%SZ").year
            if event_year == this_year:
                events.append(event)
        if any(datetime.datetime.strptime(e["created_at"], "%Y-%m-%dT%H:%M:%SZ").year < this_year for e in data):
            break
        page += 1
    return events

def summarize_events(events):
    repos = set(event["repo"]["name"] for event in events)
    return {
        "total_events": len(events),
        "unique_repos": len(repos),
        "repos": repos
    }

def generate_summary_text(summary):
    lines = [
        f"**Total public events this year:** {summary['total_events']}",
        f"**Repositories contributed to:** {summary['unique_repos']}",
        "## Repositories:"
    ]
    lines += [f"- {repo}" for repo in summary["repos"]]
    return "\n".join(lines)

def update_readme(summary, readme_path="README.md"):
    with open(readme_path, "r") as f:
        content = f.read()

    summary_text = generate_summary_text(summary)
    pattern = re.compile(
        f"{START_MARKER}.*?{END_MARKER}", re.DOTALL
    )
    replacement = f"{START_MARKER}\n{summary_text}\n{END_MARKER}"

    if pattern.search(content):
        new_content = pattern.sub(replacement, content)
    else:
        # If markers not found, append at the end
        new_content = content + f"\n\n{replacement}"

    with open(readme_path, "w") as f:
        f.write(new_content)

if __name__ == "__main__":
    events = fetch_yearly_events(GITHUB_USERNAME, GITHUB_TOKEN)
    summary = summarize_events(events)
    update_readme(summary)
    print("README.md updated with yearly summary section!")
