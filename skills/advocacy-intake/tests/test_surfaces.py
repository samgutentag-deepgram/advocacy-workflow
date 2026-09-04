from __future__ import annotations
import sys, unittest, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
from intake_core import SURFACES, STYLES, blog_of, surface_by_key


class TestSurfaces(unittest.TestCase):
    def test_seven_surfaces_across_two_branches(self):
        self.assertEqual(
            [s.key for s in SURFACES],
            ["personal_blog", "personal_thread", "personal_linkedin",
             "personal_video_script",
             "corporate_blog", "corporate_thread", "corporate_linkedin"],
        )

    def test_lookup_by_key(self):
        self.assertEqual(surface_by_key("personal_blog").label, "Personal blog")

    def test_unknown_key_raises(self):
        with self.assertRaises(KeyError):
            surface_by_key("newsletter")

    def test_each_branch_has_exactly_one_blog(self):
        for branch in ("personal", "corporate"):
            blogs = [s for s in SURFACES
                     if s.branch == branch and s.kind == "blog"]
            self.assertEqual([s.key for s in blogs], [blog_of(branch)])

    def test_video_is_personal_only(self):
        """The one asymmetry between the branches. Those go to the advocate's own
        channels, so corporate never earns a video surface."""
        video = [s for s in SURFACES if s.needs_capture]
        self.assertEqual([s.key for s in video], ["personal_video_script"])
        self.assertEqual(video[0].branch, "personal")

    def test_no_corporate_surface_needs_capture(self):
        for surface in SURFACES:
            if surface.branch == "corporate":
                self.assertFalse(surface.needs_capture, surface.key)

    def test_blog_of_names_a_real_surface(self):
        for branch in ("personal", "corporate"):
            self.assertEqual(surface_by_key(blog_of(branch)).branch, branch)


class TestStyles(unittest.TestCase):
    def test_the_four_style_keys(self):
        """These are the `key` frontmatter values in script-to-video/styles/,
        verbatim, and the filename suffix a variant carries. One name per
        style: a second naming system is the one that drifts."""
        self.assertEqual(list(STYLES),
                         ["technical", "build-it-too", "fun", "user-demo"])

    def test_style_keys_are_filename_safe(self):
        for style in STYLES:
            self.assertRegex(style, r"^[a-z][a-z0-9-]*$")


if __name__ == "__main__":
    unittest.main()
