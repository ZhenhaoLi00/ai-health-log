"""Static checks for AI skill discovery and documentation."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / ".agents/skills/health-log-coach/SKILL.md"
CLAUDE_ENTRY = ROOT / ".claude/skills/health-log-coach/SKILL.md"


class HealthCoachSkillTests(unittest.TestCase):
    def test_agent_skill_frontmatter(self):
        for path in (CANONICAL, CLAUDE_ENTRY):
            source = path.read_text(encoding="utf-8")
            self.assertTrue(source.startswith("---\n"))
            header = source.split("---", 2)[1]
            self.assertRegex(header, r"(?m)^name: health-log-coach$")
            self.assertRegex(header, r"(?m)^description: \S")
            self.assertTrue(len(header.splitlines()) < 12)

    def test_claude_uses_one_canonical_skill(self):
        entry = CLAUDE_ENTRY.read_text(encoding="utf-8")
        self.assertIn(".agents/skills/health-log-coach/SKILL.md", entry)
        self.assertIn("AGENTS.md", entry)

    def test_skill_contains_safety_and_workflows(self):
        source = CANONICAL.read_text(encoding="utf-8").lower()
        for term in ("synfit", "daily review", "weekly review",
                     "before-and-after", "privacy", "third-party api"):
            self.assertIn(term, source)

    def test_readmes_link_to_skill(self):
        for filename in ("README.md", "README.zh-CN.md"):
            source = (ROOT / filename).read_text(encoding="utf-8")
            self.assertIn(".agents/skills/health-log-coach/SKILL.md", source)
            self.assertIn(".claude/skills/", source)


if __name__ == "__main__":
    unittest.main()
