import json
import math
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"
README_PATH = ROOT / "README.md"

DEFAULT_USER_SLUG = "chen_h-i"
DEFAULT_TIMEOUT = 20

GRAPHQL_URL = "https://leetcode.cn/graphql/"
NOJ_GRAPHQL_URL = "https://leetcode.cn/graphql/noj-go/"

CONTEST_QUERY = """
query userContestRankingInfo($userSlug: String!) {
  userContestRanking(userSlug: $userSlug) {
    attendedContestsCount
    rating
    globalRanking
    localRanking
    globalTotalParticipants
    localTotalParticipants
    topPercentage
  }
  userContestRankingHistory(userSlug: $userSlug) {
    attended
    totalProblems
    trendingDirection
    finishTimeInSeconds
    rating
    score
    ranking
    contest {
      title
      titleCn
      startTime
    }
  }
}
""".strip()

CALENDAR_QUERY = """
query userProfileCalendar($userSlug: String!) {
  userCalendar(userSlug: $userSlug) {
    streak
    totalActiveDays
    submissionCalendar
    activeYears
    recentStreak
  }
}
""".strip()

PROGRESS_QUERY = """
query userProfileUserQuestionProgressV2($userSlug: String!) {
  userProfileUserQuestionProgressV2(userSlug: $userSlug) {
    numAcceptedQuestions {
      count
      difficulty
    }
    numFailedQuestions {
      count
      difficulty
    }
    numUntouchedQuestions {
      count
      difficulty
    }
    userSessionBeatsPercentage {
      difficulty
      percentage
    }
    totalQuestionBeatsPercentage
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


def fetch_calendar_data(user_slug):
    payload = build_graphql_payload(
        "userProfileCalendar",
        {"userSlug": user_slug},
        CALENDAR_QUERY,
    )
    return request_graphql(NOJ_GRAPHQL_URL, payload)


def fetch_progress_data(user_slug):
    payload = build_graphql_payload(
        "userProfileUserQuestionProgressV2",
        {"userSlug": user_slug},
        PROGRESS_QUERY,
    )
    return request_graphql(GRAPHQL_URL, payload)


def build_contest_points(history):
    points = []
    for item in history or []:
        if item.get("attended") is False:
            continue
        contest = item.get("contest") or {}
        label = contest.get("titleCn") or contest.get("title")
        rating = item.get("rating")
        if not label or rating is None:
            continue
        points.append((label, float(rating)))
    return points


def normalize_difficulty_name(value):
    mapping = {
        "EASY": "Easy",
        "MEDIUM": "Medium",
        "HARD": "Hard",
    }
    return mapping.get((value or "").upper(), value.title())


def build_distribution_summary(progress_data):
    accepted = progress_data["numAcceptedQuestions"]
    failed = progress_data["numFailedQuestions"]
    untouched = progress_data["numUntouchedQuestions"]

    difficulty_counts = {}
    difficulty_totals = {}
    beat_percentages = {}

    for item in accepted:
        difficulty_counts[normalize_difficulty_name(item["difficulty"])] = int(item["count"])
    for bucket in (accepted, failed, untouched):
        for item in bucket:
            difficulty = normalize_difficulty_name(item["difficulty"])
            difficulty_totals[difficulty] = difficulty_totals.get(difficulty, 0) + int(item["count"])
    for item in progress_data.get("userSessionBeatsPercentage") or []:
            beat_percentages[normalize_difficulty_name(item["difficulty"])] = float(item["percentage"])

    total_solved = sum(difficulty_counts.values())
    overall_beats_percentage = progress_data.get("totalQuestionBeatsPercentage")
    if overall_beats_percentage is not None:
        overall_beats_percentage = float(overall_beats_percentage)
    return total_solved, difficulty_counts, difficulty_totals, beat_percentages, overall_beats_percentage


def build_heatmap_entries(submission_calendar, today=None, weeks=53):
    today = today or date.today()
    raw = json.loads(submission_calendar or "{}")
    counts_by_day = {}
    for timestamp, count in raw.items():
        day = datetime.fromtimestamp(int(timestamp), tz=timezone.utc).date()
        counts_by_day[day] = int(count)

    days = weeks * 7
    start = today - timedelta(days=days - 1)
    entries = []
    cursor = start
    while cursor <= today:
        entries.append(
            {
                "date": cursor.isoformat(),
                "count": counts_by_day.get(cursor, 0),
            }
        )
        cursor += timedelta(days=1)
    return entries


def format_number(value):
    if value is None:
        return "-"
    if isinstance(value, float):
        if math.isfinite(value) and value.is_integer():
            return f"{int(value):,}"
        if value >= 1000:
            return f"{value:,.1f}"
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{value:,}"


def format_percentage(value):
    if value is None:
        return "-"
    return f"{float(value):.2f}%"


def format_plain_number(value):
    if value is None:
        return "-"
    if isinstance(value, float):
        return str(int(round(value)))
    return str(int(value))


def clamp(value, lower, upper):
    return max(lower, min(upper, value))


def render_card_background(width, height, prefix):
    shadow_id = f"card-shadow-{prefix}"
    gradient_id = f"card-sheen-{prefix}"
    return f"""
<defs>
  <filter id="{shadow_id}" x="-10%" y="-10%" width="130%" height="140%">
    <feDropShadow dx="0" dy="8" stdDeviation="12" flood-color="#cbd5e1" flood-opacity="0.22"/>
  </filter>
  <linearGradient id="{gradient_id}" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" stop-color="#ffffff"/>
    <stop offset="100%" stop-color="#fbfcfe"/>
  </linearGradient>
</defs>
<rect x="10" y="10" width="{width - 20}" height="{height - 20}" rx="22" fill="url(#{gradient_id})" stroke="#edf1f6" filter="url(#{shadow_id})"/>
""".strip()


def extract_svg_body(svg):
    start = svg.find(">")
    end = svg.rfind("</svg>")
    if start == -1 or end == -1:
        return svg
    return svg[start + 1:end].strip()


def polar_to_cartesian(cx, cy, radius, angle_degrees):
    angle_radians = math.radians(angle_degrees - 90)
    return (
        cx + radius * math.cos(angle_radians),
        cy + radius * math.sin(angle_radians),
    )


def describe_arc(cx, cy, radius, start_angle, end_angle):
    start_x, start_y = polar_to_cartesian(cx, cy, radius, end_angle)
    end_x, end_y = polar_to_cartesian(cx, cy, radius, start_angle)
    large_arc_flag = 1 if (end_angle - start_angle) > 180 else 0
    return (
        f"M {start_x:.2f} {start_y:.2f} "
        f"A {radius:.2f} {radius:.2f} 0 {large_arc_flag} 0 {end_x:.2f} {end_y:.2f}"
    )


def contest_level_label(rating):
    if rating is None:
        return "Unrated"
    if rating >= 2200:
        return "Guardian"
    if rating >= 2000:
        return "Knight"
    if rating >= 1800:
        return "Specialist"
    if rating >= 1600:
        return "Pupil"
    return "Newbie"


def build_contest_timeline_labels(history):
    attended = [item for item in history or [] if item.get("attended") is not False]
    if not attended:
        return ("-", "-")

    def extract_year(item):
        contest = item.get("contest") or {}
        start_time = contest.get("startTime") or item.get("finishTimeInSeconds")
        if not start_time:
            return None
        return str(datetime.fromtimestamp(int(start_time), tz=timezone.utc).year)

    first = extract_year(attended[0])
    last = extract_year(attended[-1])
    return (first or "-", last or "-")


def top_percentage_from_beats(overall_beats_percentage):
    if overall_beats_percentage is None:
        return None
    return clamp(100.0 - float(overall_beats_percentage), 0.0, 100.0)


def render_contest_svg(points, ranking, timeline_labels=None):
    width = 560
    height = 250
    left = 34
    top = 126
    chart_width = 492
    chart_height = 72
    right = left + chart_width
    bottom = top + chart_height

    text = "#1f2937"
    strong = "#111827"
    muted = "#8a94a6"
    faint = "#a8b2c2"
    border = "#eef2f7"
    line = "#f59e0b"
    line_soft = "#f9d89a"
    background = render_card_background(width, height, "contest")

    if not points:
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="LeetCode 竞赛分">
{background}
<text x="32" y="42" font-size="13" fill="{muted}">竞赛分数</text>
<text x="32" y="80" font-size="30" font-weight="700" fill="{strong}">-</text>
<text x="32" y="108" font-size="14" fill="{muted}">暂无公开竞赛记录</text>
</svg>"""

    ratings = [value for _, value in points]
    min_rating = min(ratings)
    max_rating = max(ratings)
    if math.isclose(min_rating, max_rating):
        min_rating -= 50
        max_rating += 50
    padding = max(30.0, (max_rating - min_rating) * 0.12)
    min_rating -= padding
    max_rating += padding

    def x_scale(index):
        if len(points) == 1:
            return left + chart_width / 2
        return left + (chart_width * index / (len(points) - 1))

    def y_scale(value):
        ratio = (value - min_rating) / (max_rating - min_rating)
        return bottom - ratio * chart_height

    coordinates = [(x_scale(index), y_scale(value)) for index, (_, value) in enumerate(points)]
    line_points = " ".join(f"{x:.2f},{y:.2f}" for x, y in coordinates)
    soft_line_points = " ".join(f"{x:.2f},{y + 10:.2f}" for x, y in coordinates)

    grid_lines = []
    for marker in (min_rating, (min_rating + max_rating) / 2, max_rating):
        y = y_scale(marker)
        grid_lines.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{right}" y2="{y:.2f}" stroke="{border}" stroke-dasharray="2 6"/>'
        )

    circles = []
    if coordinates:
        x, y = coordinates[-1]
        circles.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.5" fill="{line}" stroke="#fff" stroke-width="2"/>')

    current = ranking or {}
    current_rating = current.get("rating")
    current_rating_label = format_number(round(current_rating)) if current_rating is not None else "-"
    badge_label = contest_level_label(current_rating)
    total_contests = current.get("attendedContestsCount") or len(points)
    global_ranking = current.get("globalRanking")
    global_total = current.get("globalTotalParticipants")
    local_ranking = current.get("localRanking")
    local_total = current.get("localTotalParticipants")
    start_label, end_label = timeline_labels or ("起点", "最近")
    end_x, end_y = coordinates[-1]
    bubble_x = clamp(end_x - 18, 96, width - 86)
    bubble_y = clamp(end_y - 34, 92, bottom - 24)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="LeetCode 竞赛分">
{background}
<text x="32" y="42" font-size="13" fill="{muted}">竞赛分数</text>
<text x="32" y="83" font-size="36" font-weight="700" fill="{strong}">{escape(current_rating_label)}</text>
<g transform="translate(144 28)">
  <rect x="0" y="0" width="36" height="36" rx="18" fill="#e9f7ef"/>
  <path d="M18 8 L26 12 V18 C26 24 22 28 18 30 C14 28 10 24 10 18 V12 Z" fill="#16a34a"/>
</g>
<text x="190" y="42" font-size="12" fill="{muted}">当前段位</text>
<text x="190" y="62" font-size="18" font-weight="700" fill="#4f67d8">{escape(badge_label)}</text>
<text x="332" y="42" font-size="12" fill="{faint}">全球排名</text>
<text x="332" y="63" font-size="16" font-weight="700" fill="{text}">{escape(format_number(global_ranking))}<tspan font-size="11" font-weight="400" fill="{muted}">/{escape(format_number(global_total))}</tspan></text>
<text x="332" y="88" font-size="12" fill="{faint}">全国排名</text>
<text x="332" y="109" font-size="16" font-weight="700" fill="{text}">{escape(format_number(local_ranking))}<tspan font-size="11" font-weight="400" fill="{muted}">/{escape(format_number(local_total))}</tspan></text>
<text x="466" y="42" font-size="12" fill="{faint}">参赛场次</text>
<text x="466" y="63" font-size="16" font-weight="700" fill="{text}">{escape(str(total_contests))}</text>
{''.join(grid_lines)}
<line x1="{left}" y1="{bottom:.2f}" x2="{right}" y2="{bottom:.2f}" stroke="{border}"/>
<polyline points="{soft_line_points}" fill="none" stroke="{line_soft}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" opacity="0.55"/>
<polyline points="{line_points}" fill="none" stroke="{line}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
{''.join(circles)}
<rect x="{bubble_x:.2f}" y="{bubble_y:.2f}" width="64" height="26" rx="13" fill="#ffffff" stroke="#e5e9f0"/>
<text x="{bubble_x + 32:.2f}" y="{bubble_y + 17:.2f}" font-size="12" text-anchor="middle" fill="{muted}">{escape(current_rating_label)}</text>
<text x="{left}" y="{height - 28}" font-size="11" fill="{muted}">{escape(start_label)}</text>
<text x="{right}" y="{height - 28}" font-size="11" text-anchor="end" fill="{muted}">{escape(end_label)}</text>
</svg>"""


def render_distribution_svg(
    total_solved,
    difficulty_counts,
    difficulty_totals,
    beat_percentages=None,
    overall_beats_percentage=None,
):
    beat_percentages = beat_percentages or {}
    width = 560
    height = 250

    text = "#1f2937"
    muted = "#8a94a6"
    faint = "#a8b2c2"
    accent = {"Easy": "#22c55e", "Medium": "#f59e0b", "Hard": "#ef4444"}
    accent_cn = {"Easy": "简单", "Medium": "中等", "Hard": "困难"}
    background = render_card_background(width, height, "distribution")
    top_percentage = top_percentage_from_beats(overall_beats_percentage)
    difficulties = ["Easy", "Medium", "Hard"]
    total_questions = sum(difficulty_totals.get(difficulty, 0) for difficulty in difficulties)
    solved_ratio = (float(total_solved) / total_questions) if total_questions else 0.0

    arc_center_x = 148
    arc_center_y = 126
    arc_radius = 79
    start_angle = 228
    total_sweep = 264
    gap_angle = 5
    colored_sweep = total_sweep * solved_ratio
    current_angle = start_angle
    ring_segments = []

    track_segments = [
        (228, 302, "#f6c451"),
        (316, 420, "#f3e2ae"),
        (432, 474, "#f3b7be"),
        (486, 546, "#c5eef0"),
    ]
    for track_start, track_end, color in track_segments:
        ring_segments.append(
            f'<path d="{describe_arc(arc_center_x, arc_center_y, arc_radius, track_start, track_end)}" fill="none" stroke="{color}" stroke-width="8" stroke-linecap="round" opacity="0.9"/>'
        )

    for difficulty in difficulties:
        solved = difficulty_counts.get(difficulty, 0)
        sweep = 0.0
        if total_questions:
            sweep = colored_sweep * solved / total_solved if total_solved else 0.0
        if sweep <= 0:
            continue
        end_angle = current_angle + max(4.0, sweep - gap_angle)
        ring_segments.append(
            f'<path d="{describe_arc(arc_center_x, arc_center_y, arc_radius, current_angle, end_angle)}" fill="none" stroke="{accent[difficulty]}" stroke-width="8" stroke-linecap="round"/>'
        )
        current_angle += sweep

    rows = []
    row_y = 56
    for difficulty in difficulties:
        solved = difficulty_counts.get(difficulty, 0)
        total = difficulty_totals.get(difficulty, 0)
        beats = beat_percentages.get(difficulty)
        beats_text = f"击败 {beats:.1f}%" if beats is not None else "题库覆盖"
        rows.append(
            f'<rect x="390" y="{row_y}" width="134" height="44" rx="12" fill="#fafbfc" stroke="#edf1f6"/>'
            f'<text x="406" y="{row_y + 17}" font-size="12" font-weight="700" fill="{accent[difficulty]}">{accent_cn[difficulty]}</text>'
            f'<text x="406" y="{row_y + 35}" font-size="15" font-weight="700" fill="{text}">{solved}/{total}</text>'
            f'<text x="508" y="{row_y + 35}" font-size="11" text-anchor="end" fill="{muted}">{escape(beats_text)}</text>'
        )
        row_y += 52

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="LeetCode 做题分布">
{background}
<text x="32" y="42" font-size="13" fill="{muted}">做题分布</text>
<circle cx="{arc_center_x}" cy="{arc_center_y}" r="{arc_radius}" fill="none" stroke="#f7f4e8" stroke-width="10"/>
{''.join(ring_segments)}
<text x="{arc_center_x}" y="120" font-size="34" font-weight="700" text-anchor="middle" fill="{text}">{escape(format_number(total_solved))}</text>
<text x="{arc_center_x + 30}" y="120" font-size="15" text-anchor="start" fill="{muted}">/{escape(str(total_questions))}</text>
<text x="{arc_center_x}" y="144" font-size="13" text-anchor="middle" fill="{muted}">已解答</text>
<text x="{arc_center_x}" y="166" font-size="12" text-anchor="middle" fill="#16a34a">✓ 覆盖题库 {solved_ratio * 100:.2f}%</text>
<text x="{arc_center_x}" y="188" font-size="12" text-anchor="middle" fill="{faint}">Top {escape(format_percentage(top_percentage))}</text>
{''.join(rows)}
</svg>"""


def color_for_heatmap(count, max_count):
    if count <= 0:
        return "#ebedf0"
    if max_count <= 1:
        return "#9be9a8"
    ratio = count / max_count
    if ratio < 0.25:
        return "#9be9a8"
    if ratio < 0.5:
        return "#40c463"
    if ratio < 0.75:
        return "#30a14e"
    return "#216e39"


def render_heatmap_svg(entries, total_active_days=None, streak=None, range_label="过去一年"):
    width = 1140
    height = 250
    left = 130
    top = 104
    cell = 12
    gap = 5

    text = "#1f2937"
    muted = "#8a94a6"
    faint = "#a8b2c2"
    background = render_card_background(width, height, "heatmap")

    if not entries:
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="LeetCode 提交热力图">
{background}
<text x="32" y="42" font-size="13" fill="{muted}">提交热力图</text>
<text x="32" y="72" font-size="14" fill="{muted}">暂无提交数据</text>
</svg>"""

    parsed = []
    for entry in entries:
        day = datetime.strptime(entry["date"], "%Y-%m-%d").date()
        parsed.append((day, int(entry["count"])))

    max_count = max(count for _, count in parsed)
    cells = []
    month_labels = {}
    for index, (day, count) in enumerate(parsed):
        week = index // 7
        weekday = day.weekday()
        x = left + week * (cell + gap)
        y = top + weekday * (cell + gap)
        title = f"{day.isoformat()}: {count} 次提交"
        cells.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{color_for_heatmap(count, max_count)}">'
            f"<title>{escape(title)}</title></rect>"
        )
        month_key = (day.year, day.month)
        if day.day <= 7 and month_key not in month_labels:
            month_labels[month_key] = x

    month_text = []
    for (year, month), x in sorted(month_labels.items()):
        month_text.append(
            f'<text x="{x}" y="92" font-size="11" fill="{muted}">{month}月</text>'
        )

    total_submissions = sum(count for _, count in parsed)
    active_days = total_active_days if total_active_days is not None else sum(1 for _, count in parsed if count > 0)
    streak_days = streak if streak is not None else 0
    weekday_labels = [
        '<text x="96" y="124" font-size="11" fill="#b1bac8">一</text>',
        '<text x="96" y="158" font-size="11" fill="#b1bac8">三</text>',
        '<text x="96" y="192" font-size="11" fill="#b1bac8">五</text>',
    ]
    legend_x = width - 170
    legend = []
    for index, color in enumerate(["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]):
        legend.append(
            f'<rect x="{legend_x + index * 18}" y="214" width="12" height="12" rx="3" fill="{color}"/>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="LeetCode 提交热力图">
{background}
<text x="32" y="42" font-size="13" fill="{muted}">提交热力图</text>
<text x="32" y="72" font-size="12" fill="{faint}">{escape(range_label)}</text>
<rect x="172" y="30" width="128" height="40" rx="14" fill="#fafbfc" stroke="#edf1f6"/>
<text x="188" y="47" font-size="12" fill="{muted}">总提交</text>
<text x="188" y="63" font-size="15" font-weight="700" fill="{text}">{escape(format_number(total_submissions))}</text>
<rect x="314" y="30" width="128" height="40" rx="14" fill="#fafbfc" stroke="#edf1f6"/>
<text x="330" y="47" font-size="12" fill="{muted}">活跃天数</text>
<text x="330" y="63" font-size="15" font-weight="700" fill="{text}">{escape(format_number(active_days))}</text>
<rect x="456" y="30" width="128" height="40" rx="14" fill="#fafbfc" stroke="#edf1f6"/>
<text x="472" y="47" font-size="12" fill="{muted}">连续天数</text>
<text x="472" y="63" font-size="15" font-weight="700" fill="{text}">{escape(format_number(streak_days))}</text>
{''.join(month_text)}
{''.join(weekday_labels)}
{''.join(cells)}
<text x="{legend_x - 26}" y="224" font-size="11" fill="{muted}">少</text>
{''.join(legend)}
<text x="{legend_x + 96}" y="224" font-size="11" fill="{muted}">多</text>
</svg>"""


def render_readme(user_slug, contest_rating, total_solved, difficulty_counts, difficulty_totals):
    lines = [
        f"[![LeetCode Rating](https://img.shields.io/badge/LeetCode_Rating-{format_plain_number(contest_rating)}-orange?logo=leetcode)](https://leetcode.cn/u/{user_slug}/)",
        "",
        f"![LeetCode Heatmap](https://leetcard.jacoblin.cool/{user_slug}?ext=heatmap&theme=light&site=cn)",
        "",
    ]
    return "\n".join(lines)


def render_dashboard_svg(contest_svg, distribution_svg, heatmap_svg):
    width = 1160
    height = 550
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="LeetCode Dashboard">
<svg x="10" y="10" width="560" height="250" viewBox="0 0 560 250">
{extract_svg_body(contest_svg)}
</svg>
<svg x="590" y="10" width="560" height="250" viewBox="0 0 560 250">
{extract_svg_body(distribution_svg)}
</svg>
<svg x="10" y="280" width="1140" height="250" viewBox="0 0 1140 250">
{extract_svg_body(heatmap_svg)}
</svg>
</svg>"""


def write_if_changed(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = path.read_text(encoding="utf-8") if path.exists() else None
    if previous == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def build_outputs(user_slug):
    contest_data = fetch_contest_data(user_slug)
    progress_data = fetch_progress_data(user_slug)

    ranking = contest_data["userContestRanking"] or {}
    history = contest_data["userContestRankingHistory"]
    points = build_contest_points(history)
    timeline_labels = build_contest_timeline_labels(history)
    total_solved, difficulty_counts, difficulty_totals, beat_percentages, overall_beats_percentage = build_distribution_summary(
        progress_data["userProfileUserQuestionProgressV2"]
    )
    readme = render_readme(
        user_slug=user_slug,
        contest_rating=ranking.get("rating"),
        total_solved=total_solved,
        difficulty_counts=difficulty_counts,
        difficulty_totals=difficulty_totals,
    )

    return {
        "README.md": readme,
    }


def main():
    user_slug = os.environ.get("LEETCODE_CN_USER_SLUG", DEFAULT_USER_SLUG).strip() or DEFAULT_USER_SLUG
    outputs = build_outputs(user_slug)
    changed = []

    for filename, content in outputs.items():
        if filename == "README.md":
            path = README_PATH
        else:
            path = ASSETS_DIR / filename
        if write_if_changed(path, content):
            changed.append(path)

    print(f"user: {user_slug}")
    if changed:
        for path in changed:
            print(f"updated: {path.relative_to(ROOT)}")
    else:
        print("updated: none")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise
