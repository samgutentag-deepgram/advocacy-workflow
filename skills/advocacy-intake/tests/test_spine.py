# tests/test_spine.py
from __future__ import annotations
import sys, unittest, pathlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
from intake_core import read_signals, derive_spine


class TestSpine(unittest.TestCase):
    def test_no_deploy_drops_the_solidify_task(self):
        spine = derive_spine(read_signals(HERE / "fixtures" / "dog_whisper"))
        self.assertNotIn("solidify", [t.key for t in spine])

    def test_deploy_adds_the_solidify_task(self):
        spine = derive_spine(read_signals(HERE / "fixtures" / "webapp"))
        self.assertIn("solidify", [t.key for t in spine])

    def test_existing_capture_plan_is_linked_not_rewritten(self):
        spine = derive_spine(read_signals(HERE / "fixtures" / "dog_whisper"))
        capture = [t for t in spine if t.key == "capture"][0]
        self.assertIn(".hub/capture-plan.md", capture.why)

    def test_private_repo_without_license_is_the_publishing_gate(self):
        spine = derive_spine(read_signals(HERE / "fixtures" / "dog_whisper"))
        gate = [t for t in spine if t.key == "gate"][0]
        self.assertIn("LICENSE", gate.why)

    def test_the_two_repos_produce_different_spines(self):
        """The whole point. If these ever match, the read has become a
        template and the skill is broken."""
        a = [t.key for t in derive_spine(read_signals(HERE / "fixtures" / "dog_whisper"))]
        b = [t.key for t in derive_spine(read_signals(HERE / "fixtures" / "webapp"))]
        self.assertNotEqual(a, b)

    def test_verify_numbers_is_always_present(self):
        for name in ("dog_whisper", "webapp"):
            spine = derive_spine(read_signals(HERE / "fixtures" / name))
            self.assertIn("verify", [t.key for t in spine])

    def test_gate_doc_with_a_license_still_yields_a_gate_task(self):
        """A LICENSE present and a legal gate doc present: the gate_doc
        branch must fire on its own, not get silently dropped by an elif
        that only ever checked has_license."""
        spine = derive_spine(read_signals(HERE / "fixtures" / "gated"))
        gate_doc_task = [t for t in spine if t.key == "gate_doc"][0]
        self.assertIn("docs/legal.md", gate_doc_task.why)
        self.assertNotIn("gate", [t.key for t in spine if t.key != "gate_doc"])

    def test_gate_doc_and_missing_license_both_fire(self):
        """A private repo (no LICENSE) that also has a legal gate doc must
        get both prep tasks, not just whichever the old if/elif found first."""
        spine = derive_spine(read_signals(HERE / "fixtures" / "gated_private"))
        keys = [t.key for t in spine]
        self.assertIn("gate_doc", keys)
        self.assertIn("gate", keys)
        gate_doc_task = [t for t in spine if t.key == "gate_doc"][0]
        gate_task = [t for t in spine if t.key == "gate"][0]
        self.assertIn("docs/legal.md", gate_doc_task.why)
        self.assertIn("LICENSE", gate_task.why)


if __name__ == "__main__":
    unittest.main()
