from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from subprocess import CompletedProcess
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template/scripts"
sys.path.insert(0, str(SCRIPTS))
from _platform_modules import load_platform_module  # noqa: E402

cache = load_platform_module("github_read_cache", SCRIPTS / "github_read_cache.py")
workers = load_platform_module("lifecycle_workers", SCRIPTS / "lifecycle_workers.py")

URL = "repos/o/r/issues/7/comments?per_page=2"
NEXT = "https://api.github.com/repositories/1/issues/7/comments?per_page=2&page=2"


class FakeGitHub:
    """Serves versioned pages with ETags and 304s; counts conditional and unconditional requests."""

    def __init__(self) -> None:
        self.pages: dict[str, list] = {}
        self.counted = 0
        self.conditional = 0
        self.fail: str | None = None

    def __call__(self, command, *, cwd, **_):
        url = command[-1]
        if self.fail:
            return CompletedProcess(command, 1, "", self.fail)
        etag = '"' + hashlib.sha256(json.dumps(self.pages[url]).encode()).hexdigest() + '"'  # the ETag follows the body only
        link = f'Link: <{NEXT}>; rel="next"\n' if url == URL and NEXT in self.pages else ""
        if "-H" in command and command[command.index("-H") + 1] == f"If-None-Match: {etag}":
            self.conditional += 1
            return CompletedProcess(command, 1, "HTTP/2.0 304 Not Modified\nEtag: " + etag + "\n\n", "gh: HTTP 304")
        self.counted += 1
        return CompletedProcess(command, 0, f"HTTP/2.0 200 OK\nEtag: {etag}\n{link}\n" + json.dumps(self.pages[url]), "")


class ReadCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "dev-platform" / "github-read-cache.json"
        patcher = mock.patch.object(cache, "cache_path", return_value=self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.gh = FakeGitHub()
        self.gh.pages = {URL: [{"id": 1}, {"id": 2}], NEXT: [{"id": 3}]}
        self.root = Path(self.tmp.name)

    def read(self):
        return cache.get_json(self.root, URL, paginate=True, run=self.gh)

    def test_warm_read_is_conditional_and_equals_cold_and_deleted_cache(self) -> None:
        cold = self.read()
        self.assertEqual((self.gh.counted, self.gh.conditional), (2, 0))
        warm = self.read()
        self.assertEqual((self.gh.counted, self.gh.conditional), (2, 2))
        self.path.unlink()
        deleted = self.read()
        self.assertEqual(cold, warm)
        self.assertEqual(cold, deleted)
        self.assertEqual([row["id"] for row in cold], [1, 2, 3])

    def test_a_change_after_the_previous_read_is_never_hidden_by_a_304(self) -> None:
        self.read()
        self.gh.pages[NEXT] = [{"id": 3}, {"id": 4}]
        self.assertEqual([row["id"] for row in self.read()], [1, 2, 3, 4])
        self.assertEqual([row["id"] for row in self.read()], [1, 2, 3, 4])

    def test_growth_past_a_full_last_page_is_not_hidden(self) -> None:
        self.gh.pages = {URL: [{"id": 1}, {"id": 2}]}
        self.assertEqual([row["id"] for row in self.read()], [1, 2])
        # Page 1 is unchanged, so its ETag still matches, but it now has a next page.
        self.gh.pages = {URL: [{"id": 1}, {"id": 2}], NEXT: [{"id": 3}]}
        self.assertEqual([row["id"] for row in self.read()], [1, 2, 3])
        self.assertEqual([row["id"] for row in self.read()], [1, 2, 3])

    def test_warm_single_page_lists_and_objects_make_only_conditional_requests(self) -> None:
        single = "repos/o/r/issues/7/comments?per_page=100"
        obj = "repos/o/r/issues/7"
        default = "repos/o/r/pulls?state=open"
        self.gh.pages.update({single: [{"id": 1}], obj: {"number": 7}, default: [{"number": 1}]})
        for endpoint, paginate in ((single, True), (obj, False), (default, True)):
            with self.subTest(endpoint):
                cold = cache.get_json(self.root, endpoint, paginate=paginate, run=self.gh)
                before = (self.gh.counted, self.gh.conditional)
                warm = cache.get_json(self.root, endpoint, paginate=paginate, run=self.gh)
                self.assertEqual(warm, cold)
                self.assertEqual((self.gh.counted, self.gh.conditional), (before[0], before[1] + 1))

    def test_full_last_page_is_read_unconditionally_and_undeterminable_size_is_an_error(self) -> None:
        self.gh.pages = {URL: [{"id": 1}, {"id": 2}]}
        self.read()
        before = (self.gh.counted, self.gh.conditional)
        self.read()
        self.assertEqual((self.gh.counted, self.gh.conditional), (before[0] + 1, before[1]))
        self.assertEqual(cache.page_size("repos/o/r/x"), 30)
        self.assertEqual(cache.page_size("repos/o/r/x?per_page=100"), 100)
        for bad in ("per_page=abc", "per_page=0", "per_page=101", "per_page=5&per_page=6"):
            with self.subTest(bad), self.assertRaises(cache.GithubReadError):
                cache.page_size("repos/o/r/x?" + bad)

    def test_failed_read_keeps_the_previous_entry(self) -> None:
        self.read()
        before = self.path.read_text()
        self.gh.fail = "gh: HTTP 502"
        with self.assertRaises(cache.GithubReadError):
            self.read()
        self.assertEqual(self.path.read_text(), before)

    def test_unrecognised_response_is_an_error_not_a_hit(self) -> None:
        with self.assertRaises(cache.GithubReadError):
            cache.get_json(self.root, URL, run=lambda command, **_: CompletedProcess(command, 0, "garbage", ""))

    def test_corrupt_cache_fails_naming_the_file_and_reset(self) -> None:
        self.read()
        good = json.loads(self.path.read_text())
        digest_broken = json.loads(self.path.read_text())
        digest_broken["pages"][URL]["body"] = [{"id": 99}]
        cases = {
            "not json": "{",
            "wrong version": json.dumps({**good, "version": 99}),
            "pages not an object": json.dumps({**good, "pages": []}),
            "entry fields": json.dumps({**good, "pages": {URL: {"etag": "x"}}}),
            "digest mismatch": json.dumps(digest_broken),
        }
        for name, text in cases.items():
            with self.subTest(name):
                self.path.write_text(text)
                before = self.gh.counted
                with self.assertRaises(cache.GithubReadCacheError) as raised:
                    self.read()
                self.assertIn(str(self.path), str(raised.exception))
                self.assertIn(f"rm {self.path}", str(raised.exception))
                self.assertEqual(self.gh.counted, before, "a corrupt cache must not be replaced by a silent re-read")

    def test_non_array_page_cannot_be_paginated(self) -> None:
        self.gh.pages[URL] = {"id": 1}
        with self.assertRaises(cache.GithubReadError):
            self.read()

    def test_only_plain_api_reads_are_served(self) -> None:
        for args in (("repo", "view"), ("api", "-X", "POST", "x"), ("api", "a", "b")):
            with self.subTest(args), self.assertRaises(cache.GithubReadError):
                cache.cached_gh_json(self.root, *args)

    def test_worker_reads_fail_the_run_on_a_corrupt_cache_and_never_cache_writes(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{")
        with mock.patch("subprocess.run") as sub, self.assertRaises(cache.GithubReadCacheError):
            workers._gh_json("api", "--paginate", URL)
        sub.assert_not_called()
        self.assertFalse(workers._is_plain_api_read(("api", f"repos/o/r/issues/7/comments", "-f", "body=x")))
        self.assertTrue(workers._is_plain_api_read(("api", "--paginate", URL)))


if __name__ == "__main__":
    unittest.main()
