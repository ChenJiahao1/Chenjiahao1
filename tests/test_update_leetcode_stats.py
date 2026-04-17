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

        self.assertIn(
            "[![LeetCode Rating](https://img.shields.io/badge/LeetCode_Rating-2009-orange?logo=leetcode)]",
            readme,
        )
        self.assertIn(
            "![LeetCode Heatmap](https://leetcard.jacoblin.cool/chen_h-i?ext=heatmap&theme=light&site=cn)",
            readme,
        )
        self.assertNotIn("## LeetCode", readme)
        self.assertNotIn("当前做题进度", readme)
        self.assertNotIn("总:", readme)
        self.assertNotIn("简单:", readme)
        self.assertNotIn("中等:", readme)
        self.assertNotIn("困难:", readme)

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
            path = Path(tmpdir) / "README.md"
            path.write_text("same", encoding="utf-8")

            changed = module.write_if_changed(path, "same")

            self.assertFalse(changed)

    def test_script_is_readme_only_without_svg_helpers(self):
        module = load_module()

        self.assertFalse(hasattr(module, "ASSETS_DIR"))
        self.assertFalse(hasattr(module, "render_contest_svg"))
        self.assertFalse(hasattr(module, "render_distribution_svg"))
        self.assertFalse(hasattr(module, "render_heatmap_svg"))
        self.assertFalse(hasattr(module, "render_dashboard_svg"))


if __name__ == "__main__":
    unittest.main()
