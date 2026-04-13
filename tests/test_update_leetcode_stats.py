import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "update_leetcode_stats.py"


def load_module():
    spec = importlib.util.spec_from_file_location("update_leetcode_stats", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class UpdateLeetCodeStatsTests(unittest.TestCase):
    def test_render_readme_keeps_only_badge_and_light_heatmap(self):
        module = load_module()

        readme = module.render_readme(
            user_slug="chen_h-i",
            contest_rating=2008.7066775837377,
            total_solved=671,
            difficulty_counts={"Easy": 143, "Medium": 393, "Hard": 135},
            difficulty_totals={"Easy": 1057, "Medium": 2239, "Hard": 993},
        )

        self.assertIn("## LeetCode", readme)
        self.assertIn(
            "[![LeetCode Rating](https://img.shields.io/badge/LeetCode_Rating-2009-orange?logo=leetcode)]",
            readme,
        )
        self.assertIn(
            "![LeetCode Heatmap](https://leetcard.jacoblin.cool/chen_h-i?ext=heatmap&theme=light&site=cn)",
            readme,
        )
        self.assertNotIn("当前做题进度", readme)
        self.assertNotIn("总:", readme)
        self.assertNotIn("简单:", readme)
        self.assertNotIn("中等:", readme)
        self.assertNotIn("困难:", readme)

    def test_build_contest_points_from_history(self):
        module = load_module()
        history = [
            {"contest": {"titleCn": "第 1 场周赛", "title": "Weekly 1"}, "rating": 1500},
            {"contest": {"titleCn": "第 2 场周赛", "title": "Weekly 2"}, "rating": 1600},
        ]

        points = module.build_contest_points(history)

        self.assertEqual(points, [("第 1 场周赛", 1500.0), ("第 2 场周赛", 1600.0)])

    def test_render_contest_svg_uses_dashboard_card_style(self):
        module = load_module()

        svg = module.render_contest_svg(
            points=[("第 1 场周赛", 1888.0), ("第 2 场周赛", 2009.0)],
            ranking={
                "rating": 2009,
                "globalRanking": 19978,
                "globalTotalParticipants": 886599,
                "localRanking": 6100,
                "localTotalParticipants": 154571,
            },
            timeline_labels=("2022", "2026"),
        )

        self.assertIn("竞赛分数", svg)
        self.assertIn("Knight", svg)
        self.assertIn("当前段位", svg)
        self.assertIn("全球排名", svg)
        self.assertIn("全国排名", svg)
        self.assertIn("2,009", svg)
        self.assertIn("2026", svg)
        self.assertIn("filter=\"url(#card-shadow-contest)\"", svg)

    def test_render_distribution_svg_contains_ring_card_style(self):
        module = load_module()

        svg = module.render_distribution_svg(
            total_solved=671,
            difficulty_counts={"Easy": 143, "Medium": 393, "Hard": 135},
            difficulty_totals={"Easy": 1057, "Medium": 2239, "Hard": 993},
            overall_beats_percentage=96.09,
        )

        self.assertIn("671", svg)
        self.assertIn("4289", svg)
        self.assertIn("已解答", svg)
        self.assertIn("简单", svg)
        self.assertIn("中等", svg)
        self.assertIn("困难", svg)
        self.assertIn("393/2239", svg)
        self.assertIn("<circle", svg)
        self.assertIn("filter=\"url(#card-shadow-distribution)\"", svg)

    def test_render_heatmap_svg_contains_horizontal_summary_layout(self):
        module = load_module()

        svg = module.render_heatmap_svg(
            [
                {"date": "2026-04-01", "count": 3},
                {"date": "2026-04-02", "count": 0},
            ],
            total_active_days=1,
            streak=2,
            range_label="过去一年",
        )

        self.assertIn("<rect", svg)
        self.assertIn("2026-04-01", svg)
        self.assertIn("提交热力图", svg)
        self.assertIn("过去一年", svg)
        self.assertIn("总提交", svg)
        self.assertIn("活跃天数", svg)
        self.assertIn("连续天数", svg)
        self.assertIn("4月", svg)
        self.assertNotIn("▾", svg)

    def test_render_dashboard_svg_arranges_three_panels(self):
        module = load_module()

        dashboard_svg = module.render_dashboard_svg(
            contest_svg=module.render_contest_svg(
                points=[("第 1 场周赛", 1888.0), ("第 2 场周赛", 2009.0)],
                ranking={
                    "rating": 2009,
                    "globalRanking": 19978,
                    "globalTotalParticipants": 886599,
                    "localRanking": 6100,
                    "localTotalParticipants": 154571,
                },
                timeline_labels=("2022", "2026"),
            ),
            distribution_svg=module.render_distribution_svg(
                total_solved=671,
                difficulty_counts={"Easy": 143, "Medium": 393, "Hard": 135},
                difficulty_totals={"Easy": 1057, "Medium": 2239, "Hard": 993},
                overall_beats_percentage=96.09,
            ),
            heatmap_svg=module.render_heatmap_svg(
                [
                    {"date": "2026-04-01", "count": 3},
                    {"date": "2026-04-02", "count": 0},
                ],
                total_active_days=1,
                streak=2,
            ),
        )

        self.assertIn("竞赛分数", dashboard_svg)
        self.assertIn("做题分布", dashboard_svg)
        self.assertIn("提交热力图", dashboard_svg)
        self.assertIn('viewBox="0 0 1160 550"', dashboard_svg)
        self.assertNotIn("▾", dashboard_svg)

    def test_build_graphql_payload_includes_variables(self):
        module = load_module()

        payload = module.build_graphql_payload(
            "userProfileCalendar",
            {"userSlug": "chen_h-i", "year": 2026},
            "query userProfileCalendar($userSlug: String!, $year: Int) { userCalendar(userSlug: $userSlug, year: $year) { streak } }",
        )

        self.assertEqual(payload["operationName"], "userProfileCalendar")
        self.assertEqual(payload["variables"]["userSlug"], "chen_h-i")
        self.assertEqual(payload["variables"]["year"], 2026)

    def test_write_if_changed_skips_identical_content(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "a.svg"
            path.write_text("same", encoding="utf-8")

            changed = module.write_if_changed(path, "same")

            self.assertFalse(changed)


if __name__ == "__main__":
    unittest.main()
