import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"

DEFAULT_USER_SLUG = "chen_h-i"
DEFAULT_TIMEOUT = 20
NOJ_GRAPHQL_URL = "https://leetcode.cn/graphql/noj-go/"

CONTEST_QUERY = """
query userContestRankingInfo($userSlug: String!) {
  userContestRanking(userSlug: $userSlug) {
    rating
  }
}
""".strip()


def build_graphql_payload(operation_name, variables, query):
    return {
        "operationName": operation_name,
        "variables": variables,
        "query": query,
    }


def request_graphql(url, payload, timeout=DEFAULT_TIMEOUT):
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{url} HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"{url} network error: {exc.reason}") from exc

    data = json.loads(body)
    if data.get("errors"):
        raise RuntimeError(f"{url} GraphQL errors: {json.dumps(data['errors'], ensure_ascii=False)}")
    return data["data"]


def fetch_contest_data(user_slug):
    payload = build_graphql_payload(
        "userContestRankingInfo",
        {"userSlug": user_slug},
        CONTEST_QUERY,
    )
    return request_graphql(NOJ_GRAPHQL_URL, payload)


def format_plain_number(value):
    if value is None:
        return "-"
    return str(int(round(float(value))))


def render_readme(user_slug, contest_rating, total_solved=None, difficulty_counts=None, difficulty_totals=None):
    return "\n".join(
        [
            f"[![LeetCode Rating](https://img.shields.io/badge/LeetCode_Rating-{format_plain_number(contest_rating)}-orange?logo=leetcode)](https://leetcode.cn/u/{user_slug}/)",
            "",
            f"![LeetCode Heatmap](https://leetcard.jacoblin.cool/{user_slug}?ext=heatmap&theme=light&site=cn)",
            "",
        ]
    )


def write_if_changed(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = path.read_text(encoding="utf-8") if path.exists() else None
    if previous == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def build_outputs(user_slug):
    contest_data = fetch_contest_data(user_slug)
    ranking = contest_data.get("userContestRanking") or {}
    return {
        "README.md": render_readme(
            user_slug=user_slug,
            contest_rating=ranking.get("rating"),
        )
    }


def main():
    user_slug = os.environ.get("LEETCODE_CN_USER_SLUG", DEFAULT_USER_SLUG).strip() or DEFAULT_USER_SLUG
    changed = write_if_changed(README_PATH, build_outputs(user_slug)["README.md"])

    print(f"user: {user_slug}")
    print("updated: README.md" if changed else "updated: none")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise
