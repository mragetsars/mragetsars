"""Regression tests for public-only data, safe rendering and failed refreshes."""

from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update_profile as profile


def api_repo(ident=1, name="example", **changes):
    return {"id": ident, "name": name, "owner": {"login": "mragetsars"},
            "private": False, "fork": False, "archived": False,
            "description": "A useful project.", "language": "Python", "stargazers_count": 4,
            "pushed_at": "2026-09-01T12:00:00Z", **changes}


USER = {"login": "mragetsars", "bio": "Computer Engineering Student", "company": "University of Tehran",
        "location": "Tehran, Iran", "blog": "https://t.me/mragetsars_bot", "followers": 30}
CONFIG = {"username": "mragetsars", "featured": [{"id": 1, "label": "Example"}], "recent_limit": 3}


def snapshot(*repos):
    return {"schema_version": 1, "updated_on": "2026-09-23", "user": deepcopy(USER),
            "repositories": [profile.normalize_repo(r, "mragetsars") for r in repos]}


def template():
    return "# Handwritten introduction\n\n" + "\n\n".join(
        f"<!-- {name}:START -->\nOld data\n<!-- {name}:END -->" for name in profile.BLOCKS
    ) + "\n\nPersonal footer stays here.\n"


class ProfileTests(unittest.TestCase):
    def test_pagination_keeps_repositories_beyond_first_page(self):
        first = [api_repo(i, f"project-{i}") for i in range(1, 101)]
        with patch.object(profile, "get_json", side_effect=[USER, first, [api_repo(101, "last-project")]]) as request:
            data = profile.collect(CONFIG)
        self.assertEqual(len(data["repositories"]), 101)
        self.assertIn("page=2", request.call_args[0][0])

    def test_private_and_foreign_repositories_never_enter_snapshot(self):
        rows = [api_repo(), api_repo(2, "secret", private=True),
                api_repo(3, "someone-elses", owner={"login": "elsewhere"})]
        with patch.object(profile, "get_json", side_effect=[USER, rows]):
            data = profile.collect(CONFIG)
        self.assertEqual([r["name"] for r in data["repositories"]], ["example"])

    def test_missing_visibility_fails_closed(self):
        raw = api_repo()
        del raw["private"]
        with self.assertRaises(profile.ProfileError):
            profile.normalize_repo(raw, "mragetsars")

    def test_stars_exclude_forks_and_profile(self):
        data = snapshot(api_repo(), api_repo(2, "fork", fork=True, stargazers_count=1000),
                        api_repo(3, "mragetsars", stargazers_count=100))
        activity = profile.render_blocks(data, CONFIG)["ACTIVITY"]
        self.assertIn("**4 stars received**", activity)
        self.assertIn("**3 public repositories**", activity)
        self.assertIn("1 public non-fork project", activity)

    def test_repository_rename_keeps_featured_selection_and_updates_url(self):
        projects = profile.render_blocks(snapshot(api_repo(name="renamed")), CONFIG)["PROJECTS"]
        self.assertIn("https://github.com/mragetsars/renamed", projects)

    def test_removed_featured_repo_does_not_leave_a_stale_link(self):
        projects = profile.render_blocks(snapshot(), CONFIG)["PROJECTS"]
        self.assertNotIn("https://github.com", projects)

    def test_api_text_cannot_inject_html_markdown_or_markers(self):
        raw = api_repo(description='x | [click](https://bad.test) <script>alert(1)</script>\n<!-- PROJECTS:END -->')
        rendered = profile.render_blocks(snapshot(raw), CONFIG)["PROJECTS"]
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("[click]", rendered)
        self.assertNotIn("<!-- PROJECTS:END -->", rendered)
        self.assertIn("&#124;", rendered)

    def test_website_link_rejects_unsafe_schemes_and_credentials(self):
        for value in ("javascript:alert(1)", "https://user:pass@example.org", "//example.org", "https://a b.org"):
            with self.subTest(value=value):
                self.assertIsNone(profile.website_link(value))
        self.assertIn("%29", profile.website_link("https://example.org/a)[x]"))

    def test_archived_and_selected_projects_do_not_duplicate_in_recent(self):
        data = snapshot(api_repo(), api_repo(2, "archive", archived=True), api_repo(3, "other"))
        activity = profile.render_blocks(data, CONFIG)["ACTIVITY"]
        self.assertIn("/other)", activity)
        self.assertNotIn("/example)", activity)
        self.assertNotIn("/archive)", activity)

    def test_recent_uses_push_time_not_metadata_update_time(self):
        data = snapshot(api_repo(2, "old", pushed_at="2025-01-01T00:00:00Z"),
                        api_repo(3, "new", pushed_at="2026-01-01T00:00:00Z"))
        activity = profile.render_blocks(data, CONFIG)["ACTIVITY"]
        self.assertLess(activity.index("/new)"), activity.index("/old)"))

    def test_missing_optional_data_still_renders(self):
        data = snapshot(api_repo(description=None, language=None, pushed_at=None))
        data["user"].update(bio="", company="", location="", blog="")
        blocks = profile.render_blocks(data, CONFIG)
        self.assertIn("No push recorded", blocks["PROJECTS"])
        self.assertNotIn("None", blocks["PROJECTS"])
        self.assertNotIn("****", blocks["PROFILE"])

    def test_description_summary_preserves_project_and_drops_repeated_context(self):
        self.assertEqual(profile.description_summary("a RISC-V processor . Developed as an assignment."),
                         "A RISC-V processor.")
        self.assertEqual(profile.description_summary("Version 2.0 supports C++20."),
                         "Version 2.0 supports C++20.")

    def test_duplicate_repository_pages_abort(self):
        first = [api_repo(i, f"project-{i}") for i in range(1, 101)]
        with patch.object(profile, "get_json", side_effect=[USER, first, [api_repo(1)]]):
            with self.assertRaises(profile.ProfileError):
                profile.collect(CONFIG)

    def test_wrong_user_and_invalid_counts_abort(self):
        for changes in ({"login": "someone-else"}, {"followers": -1}, {"followers": True}):
            with self.subTest(changes=changes), self.assertRaises(profile.ProfileError):
                profile.normalize_user({**USER, **changes}, "mragetsars")

    def test_preserves_manual_text_and_second_render_is_identical(self):
        blocks = profile.render_blocks(snapshot(api_repo()), CONFIG)
        result = profile.replace_blocks(template(), blocks)
        self.assertTrue(result.startswith("# Handwritten introduction\n"))
        self.assertTrue(result.endswith("Personal footer stays here.\n"))
        self.assertEqual(result, profile.replace_blocks(result, blocks))

    def test_missing_duplicate_reversed_and_nested_markers_abort(self):
        cases = [template().replace("<!-- PROFILE:END -->", ""),
                 template() + "<!-- PROJECTS:START -->",
                 template().replace("<!-- PROFILE:START -->", "TEMP").replace("<!-- PROFILE:END -->", "<!-- PROFILE:START -->").replace("TEMP", "<!-- PROFILE:END -->"),
                 template().replace("<!-- PROFILE:END -->", "").replace("<!-- PROJECTS:END -->", "<!-- PROJECTS:END -->\n<!-- PROFILE:END -->")]
        blocks = profile.render_blocks(snapshot(api_repo()), CONFIG)
        for case in cases:
            with self.subTest(case=case), self.assertRaises(profile.ProfileError):
                profile.replace_blocks(case, blocks)

    def test_failed_api_refresh_keeps_both_saved_files_unchanged(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / "profile.json").write_text(json.dumps(CONFIG))
            (root / "README.md").write_text(template())
            (root / "data/profile.json").write_text(json.dumps(snapshot(api_repo())))
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            with patch.object(profile, "get_json", side_effect=[USER, profile.ProfileError("API unavailable")]):
                with self.assertRaises(profile.ProfileError):
                    profile.update(root)
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob("*") if p.is_file()})

    def test_check_is_read_only_and_same_snapshot_is_idempotent(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / "profile.json").write_text(json.dumps(CONFIG))
            (root / "README.md").write_text(template())
            (root / "data/profile.json").write_text(json.dumps(snapshot(api_repo())))
            original = (root / "README.md").read_bytes()
            self.assertTrue(profile.update(root, offline=True, check=True))
            self.assertEqual(original, (root / "README.md").read_bytes())
            self.assertTrue(profile.update(root, offline=True))
            self.assertFalse(profile.update(root, offline=True))
            self.assertFalse(profile.update(root, offline=True, check=True))

    def test_network_errors_are_retried_with_a_bound(self):
        with patch.object(profile, "build_opener") as build, patch.object(profile.time, "sleep"):
            build.return_value.open.side_effect = URLError("offline")
            with self.assertRaises(profile.ProfileError):
                profile.get_json("/users/mragetsars")
            self.assertEqual(build.return_value.open.call_count, 3)

    def test_auth_failure_is_not_retried_or_dumped(self):
        with patch.object(profile, "build_opener") as build, patch.object(profile.time, "sleep") as sleep:
            build.return_value.open.side_effect = HTTPError("https://api.github.com", 401, "secret response", {}, None)
            with self.assertRaisesRegex(profile.ProfileError, "HTTP 401"):
                profile.get_json("/users/mragetsars")
            sleep.assert_not_called()

    def test_credentials_are_not_forwarded_on_redirect(self):
        self.assertIsNone(profile.NoRedirect().redirect_request(None, None, 302, "", {}, "https://elsewhere.test"))

    def test_snapshot_validation_rejects_duplicates_and_bad_dates(self):
        data = snapshot(api_repo(), api_repo())
        with self.assertRaises(profile.ProfileError):
            profile.validate_snapshot(data, "mragetsars")
        data = snapshot(api_repo())
        data["updated_on"] = "2026-02-30"
        with self.assertRaises(ValueError):
            profile.validate_snapshot(data, "mragetsars")


if __name__ == "__main__":
    unittest.main()
