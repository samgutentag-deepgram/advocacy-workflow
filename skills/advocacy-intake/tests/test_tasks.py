# tests/test_tasks.py
from __future__ import annotations
import sys, unittest, pathlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
from intake_core import (
    GATES, STYLES, SURFACES, blog_of, build_tasks, filer_for, gate_task_key,
    read_signals, schedule_for, surface_by_key, RENDER_KEY,
)

ALL_SURFACES = [s.key for s in SURFACES]
DERIVATIVES = [s.key for s in SURFACES if s.kind == "derivative"]
BLOGS = [s.key for s in SURFACES if s.kind == "blog"]


def gate_tasks(tasks, gate_key):
    return [t for t in tasks if t.gate == gate_key]


def by_key(tasks):
    return {t.key: t for t in tasks}


class TestTasks(unittest.TestCase):
    def setUp(self):
        self.sig = read_signals(HERE / "fixtures" / "dog_whisper")

    def test_declined_surfaces_produce_no_tasks(self):
        tasks = build_tasks(self.sig, ["personal_blog"])
        keys = [t.key for t in tasks]
        self.assertIn(gate_task_key("A", "personal_blog"), keys)
        self.assertNotIn(gate_task_key("A", "corporate_blog"), keys)

    def test_a_derivative_expands_into_a_canonical_and_four_variants(self):
        """The point of the model. "Personal thread" is not an action. The
        canonical is one, and each style variant is another."""
        tasks = build_tasks(self.sig, ["personal_blog", "personal_thread"])
        keys = [t.key for t in tasks]
        self.assertNotIn("surface:personal_thread", keys)
        self.assertIn(gate_task_key("B", "personal_thread"), keys)
        self.assertIn(gate_task_key("C", "personal_thread"), keys)
        for style in STYLES:
            self.assertIn(gate_task_key("C", "personal_thread", style), keys)

    def test_every_derivative_gets_all_four_styles_every_time(self):
        """No picking a style per surface. All four, always."""
        tasks = build_tasks(self.sig, ALL_SURFACES)
        for key in DERIVATIVES:
            variants = [t for t in tasks if t.parent == gate_task_key("C", key)]
            self.assertEqual(len(variants), len(STYLES), key)

    def test_a_blog_has_no_variants(self):
        """A blog is the source the variants come from, so it fans out to
        nothing itself."""
        tasks = build_tasks(self.sig, ALL_SURFACES)
        for key in BLOGS:
            self.assertEqual(
                [t.key for t in tasks if t.parent == gate_task_key("C", key)], [])

    def test_prep_tasks_come_before_gate_tasks(self):
        tasks = build_tasks(self.sig, ALL_SURFACES)
        first_gate = min(i for i, t in enumerate(tasks) if t.gate)
        last_prep = max(i for i, t in enumerate(tasks) if not t.gate)
        self.assertLess(last_prep, first_gate)

    def test_every_dependency_refers_to_a_real_task(self):
        tasks = build_tasks(self.sig, ALL_SURFACES)
        keys = {t.key for t in tasks}
        for t in tasks:
            for dep in t.depends_on:
                self.assertIn(dep, keys, "dangling dependency %r on %r" % (dep, t.key))

    def test_every_parent_refers_to_a_real_task(self):
        tasks = build_tasks(self.sig, ALL_SURFACES)
        keys = {t.key for t in tasks}
        for t in tasks:
            if t.parent is not None:
                self.assertIn(t.parent, keys, t.key)

    def test_subtask_depth_stops_at_two(self):
        """Asana subtasks cannot belong to a section, which is why parents
        exist at all. A subtask of a subtask would have nowhere to live."""
        tasks = build_tasks(self.sig, ALL_SURFACES)
        index = by_key(tasks)
        for t in tasks:
            if t.parent is not None:
                self.assertIsNone(index[t.parent].parent,
                                  "%s is a subtask of a subtask" % t.key)

    def test_task_keys_are_unique(self):
        tasks = build_tasks(self.sig, ALL_SURFACES)
        keys = [t.key for t in tasks]
        self.assertEqual(len(keys), len(set(keys)))

    def test_task_titles_are_unique(self):
        """reconcile matches on title, so two tasks sharing one title
        collapse into one on the next re-run."""
        tasks = build_tasks(self.sig, ALL_SURFACES)
        titles = [t.title for t in tasks]
        self.assertEqual(len(titles), len(set(titles)))

    def test_no_surfaces_kept_is_an_error(self):
        with self.assertRaises(ValueError):
            build_tasks(self.sig, [])

    def test_a_derivative_without_its_blog_is_an_error(self):
        """Nothing derives from a parent that is not there. This is not a
        smaller campaign, it is a Gate B task waiting on a Gate A task
        nobody files."""
        with self.assertRaises(ValueError):
            build_tasks(self.sig, ["personal_thread"])
        with self.assertRaises(ValueError):
            build_tasks(self.sig, ["personal_blog", "corporate_linkedin"])

    def test_an_unknown_surface_raises(self):
        with self.assertRaises(KeyError):
            build_tasks(self.sig, ["personal_blog", "newsletter"])


class TestNothingDerivesFromAnUnapprovedParent(unittest.TestCase):
    """The rule the whole model exists to enforce."""

    def setUp(self):
        self.tasks = build_tasks(
            read_signals(HERE / "fixtures" / "dog_whisper"), ALL_SURFACES)
        self.index = by_key(self.tasks)

    def test_each_canonical_waits_on_its_branch_blog(self):
        for key in DERIVATIVES:
            branch = surface_by_key(key).branch
            task = self.index[gate_task_key("B", key)]
            self.assertEqual(task.depends_on,
                             (gate_task_key("A", blog_of(branch)),))

    def test_each_variant_parent_waits_on_its_canonical(self):
        for key in DERIVATIVES:
            task = self.index[gate_task_key("C", key)]
            self.assertIn(gate_task_key("B", key), task.depends_on)

    def test_each_variant_waits_on_its_parent(self):
        for key in DERIVATIVES:
            parent = gate_task_key("C", key)
            for style in STYLES:
                self.assertIn(parent,
                              self.index[gate_task_key("C", key, style)].depends_on)

    def test_the_branches_never_cross(self):
        """A personal surface must never wait on a corporate one. They are
        peers, not a pipeline."""
        for key in DERIVATIVES:
            branch = surface_by_key(key).branch
            other = "corporate" if branch == "personal" else "personal"
            for task in self.tasks:
                if not task.key.endswith(key) and ":%s" % key not in task.key:
                    continue
                for dep in task.depends_on:
                    self.assertNotIn(blog_of(other), dep,
                                     "%s reaches into %s" % (task.key, dep))


class TestGatesLandOnTheBlogsOnly(unittest.TestCase):
    """A legal block on the blog stops the branch through the chain. Wiring
    it to every item would say the same thing four more times."""

    def test_gate_is_on_the_blogs_and_nothing_else(self):
        sig = read_signals(HERE / "fixtures" / "dog_whisper")   # no LICENSE
        tasks = build_tasks(sig, ALL_SURFACES)
        carrying = sorted(t.key for t in tasks if "gate" in t.depends_on)
        self.assertEqual(carrying,
                         sorted(gate_task_key("A", b) for b in BLOGS))

    def test_gate_doc_is_on_the_blogs_and_nothing_else(self):
        sig = read_signals(HERE / "fixtures" / "gated")         # legal.md, LICENSE
        tasks = build_tasks(sig, ["corporate_blog", "corporate_thread"])
        carrying = [t.key for t in tasks if "gate_doc" in t.depends_on]
        self.assertEqual(carrying, [gate_task_key("A", "corporate_blog")])

    def test_both_gates_land_together_when_both_apply(self):
        sig = read_signals(HERE / "fixtures" / "gated_private")
        tasks = build_tasks(sig, ["personal_blog"])
        blog = by_key(tasks)[gate_task_key("A", "personal_blog")]
        self.assertIn("gate", blog.depends_on)
        self.assertIn("gate_doc", blog.depends_on)

    def test_a_repo_with_no_gate_wires_none(self):
        sig = read_signals(HERE / "fixtures" / "webapp")        # LICENSE, no gate doc
        tasks = build_tasks(sig, ["personal_blog", "personal_thread"])
        for task in tasks:
            self.assertNotIn("gate", task.depends_on)
            self.assertNotIn("gate_doc", task.depends_on)


class TestVerifyAndCapture(unittest.TestCase):
    def setUp(self):
        self.tasks = build_tasks(
            read_signals(HERE / "fixtures" / "dog_whisper"), ALL_SURFACES)

    def test_verify_lands_on_the_blogs_only(self):
        """The blog is where a number appears first, and the last point
        before four surfaces repeat it."""
        carrying = sorted(t.key for t in self.tasks if "verify" in t.depends_on)
        self.assertEqual(carrying,
                         sorted(gate_task_key("A", b) for b in BLOGS))

    def test_the_limit_is_quoted_on_every_gated_surface(self):
        index = by_key(self.tasks)
        for key in BLOGS:
            surface = surface_by_key(key)
            self.assertIn("Limit is %s %s" % (surface.limit, surface.limit_kind),
                          index[gate_task_key("A", key)].why)
        for key in DERIVATIVES:
            surface = surface_by_key(key)
            self.assertIn("Limit is %s %s" % (surface.limit, surface.limit_kind),
                          index[gate_task_key("B", key)].why)

    def test_capture_lands_on_the_render_batch_only(self):
        """Footage exists before the camera step, not before the surface."""
        carrying = [t.key for t in self.tasks if "capture" in t.depends_on]
        self.assertEqual(carrying, [gate_task_key("D", RENDER_KEY)])


class TestGateD(unittest.TestCase):
    def setUp(self):
        self.sig = read_signals(HERE / "fixtures" / "dog_whisper")

    def test_renders_appear_only_when_the_video_script_is_kept(self):
        tasks = build_tasks(self.sig, ["personal_blog", "personal_video_script"])
        self.assertTrue(gate_tasks(tasks, "D"))

    def test_no_video_script_means_no_renders(self):
        tasks = build_tasks(self.sig, ["personal_blog", "personal_thread",
                                       "corporate_blog", "corporate_thread"])
        self.assertEqual(gate_tasks(tasks, "D"), [])

    def test_one_render_per_style(self):
        tasks = build_tasks(self.sig, ["personal_blog", "personal_video_script"])
        parent = gate_task_key("D", RENDER_KEY)
        self.assertEqual(len([t for t in tasks if t.parent == parent]),
                         len(STYLES))

    def test_renders_wait_on_the_video_script_variants(self):
        tasks = build_tasks(self.sig, ["personal_blog", "personal_video_script"])
        parent = by_key(tasks)[gate_task_key("D", RENDER_KEY)]
        self.assertIn(gate_task_key("C", "personal_video_script"),
                      parent.depends_on)


class TestFilers(unittest.TestCase):
    """intake files A and B at promotion. cycle files C and D on its first
    run, because a variant of a canonical that does not exist yet is a
    guess, not a task."""

    def setUp(self):
        self.tasks = build_tasks(
            read_signals(HERE / "fixtures" / "dog_whisper"), ALL_SURFACES)

    def test_gate_filers(self):
        self.assertEqual({g.key: g.filer for g in GATES},
                         {"A": "intake", "B": "intake",
                          "C": "cycle", "D": "cycle"})

    def test_prep_tasks_belong_to_intake(self):
        for task in self.tasks:
            if task.gate is None:
                self.assertEqual(filer_for(task), "intake", task.key)

    def test_every_task_has_exactly_one_filer(self):
        for task in self.tasks:
            self.assertIn(filer_for(task), ("intake", "cycle"), task.key)


class TestSchedule(unittest.TestCase):
    def test_every_gate_task_has_a_schedule_and_prep_tasks_have_none(self):
        tasks = build_tasks(
            read_signals(HERE / "fixtures" / "dog_whisper"), ALL_SURFACES)
        for task in tasks:
            schedule = schedule_for(task.key)
            if task.gate:
                self.assertIsNotNone(schedule, task.key)
            else:
                self.assertIsNone(schedule, task.key)

    def test_drop_days_ascend_through_the_gates(self):
        days = [g.drop_day for g in GATES]
        self.assertEqual(days, sorted(days))
        self.assertEqual(len(set(days)), len(days))

    def test_a_subtask_drops_with_its_parent(self):
        tasks = build_tasks(
            read_signals(HERE / "fixtures" / "dog_whisper"), ALL_SURFACES)
        index = by_key(tasks)
        for task in tasks:
            if task.parent is not None:
                self.assertEqual(schedule_for(task.key),
                                 schedule_for(index[task.parent].key), task.key)


if __name__ == "__main__":
    unittest.main()
