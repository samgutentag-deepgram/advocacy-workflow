from __future__ import annotations
import sys, unittest, pathlib, tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import config as c


class TestSchema(unittest.TestCase):
    def test_no_workspace_specific_value_is_hardcoded(self):
        """The whole point of the file. A gid baked into the skill is one
        person's workspace and nobody else can run it."""
        for f in c.FIELDS:
            self.assertNotRegex(f.how, r"\b\d{12,}\b", f.key)
        for v in c.DEFAULTS.values():
            self.assertNotRegex(str(v), r"\b\d{12,}\b")

    def test_every_field_says_how_to_find_its_answer(self):
        for f in c.FIELDS:
            self.assertTrue(f.how.strip(), f.key)
            self.assertTrue(f.label.strip(), f.key)

    def test_field_keys_are_unique(self):
        keys = [f.key for f in c.FIELDS]
        self.assertEqual(len(keys), len(set(keys)))


class TestParseAndRender(unittest.TestCase):
    def test_round_trip(self):
        vals = {f.key: "v-%s" % f.key for f in c.FIELDS}
        self.assertEqual(c.parse(c.render(vals)), vals)

    def test_comments_and_blanks_are_ignored(self):
        self.assertEqual(c.parse("# a comment\n\nlab_root: ~/LABS\n"),
                         {"lab_root": "~/LABS"})

    def test_quotes_are_stripped(self):
        self.assertEqual(c.parse('asana_workspace: "411927538413705"\n'),
                         {"asana_workspace": "411927538413705"})

    def test_an_unknown_key_survives_a_round_trip(self):
        """A newer version may have written something this one does not know
        about. Dropping it on save is worse than carrying it."""
        vals = dict({f.key: "x" for f in c.FIELDS}, future_setting="keep me")
        self.assertEqual(c.parse(c.render(vals))["future_setting"], "keep me")


class TestMissing(unittest.TestCase):
    def test_an_empty_config_needs_every_field(self):
        self.assertEqual(len(c.missing({})), len(c.FIELDS))

    def test_defaults_answer_three_of_them(self):
        still = [f.key for f in c.missing(c.with_defaults({}))]
        self.assertNotIn("lab_root", still)
        self.assertNotIn("voice_personal", still)
        self.assertNotIn("voice_corporate", still)

    def test_only_the_asana_facts_must_be_asked(self):
        """Everything the interview cannot guess is a fact about the user's
        own Asana workspace."""
        for key in (f.key for f in c.missing(c.with_defaults({}))):
            self.assertTrue(key.startswith("asana_"), key)

    def test_a_present_but_empty_value_counts_as_missing(self):
        self.assertIn("asana_workspace",
                      [f.key for f in c.missing({"asana_workspace": "   "})])

    def test_a_filled_config_needs_nothing(self):
        vals = {f.key: "set" for f in c.FIELDS}
        self.assertEqual(c.missing(vals), [])

    def test_a_users_own_answer_beats_the_default(self):
        vals = c.with_defaults({"voice_personal": "my-own-voice"})
        self.assertEqual(vals["voice_personal"], "my-own-voice")


class TestLoadAndLabPath(unittest.TestCase):
    def test_a_config_that_was_never_written_loads_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(c.load(str(pathlib.Path(tmp) / "nope.yml")), {})

    def test_load_reads_what_render_wrote(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "cfg.yml"
            p.write_text(c.render({"lab_root": "~/WORK"}))
            self.assertEqual(c.load(str(p))["lab_root"], "~/WORK")

    def test_the_lab_suffix_is_added(self):
        self.assertTrue(str(c.lab_path({"lab_root": "/tmp/l"}, "thing")).endswith("/thing-lab"))

    def test_a_name_that_already_has_the_suffix_is_not_doubled(self):
        self.assertTrue(str(c.lab_path({"lab_root": "/tmp/l"}, "thing-lab")).endswith("/thing-lab"))
        self.assertNotIn("lab-lab", str(c.lab_path({"lab_root": "/tmp/l"}, "thing-lab")))

    def test_lab_root_is_configurable_and_expands(self):
        self.assertTrue(str(c.lab_path({"lab_root": "~/WORK"}, "x")).startswith("/"))


if __name__ == "__main__":
    unittest.main()
