import pathlib, shutil, subprocess, sys, tempfile, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def run(cwd, *args):
    return subprocess.run([sys.executable, str(cwd / "scripts/check_privacy.py"), *args],
                          cwd=cwd, capture_output=True, text=True)


class PrivacyCheck(unittest.TestCase):
    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp())
        (self.d / "scripts").mkdir()
        shutil.copy(ROOT / "scripts/check_privacy.py", self.d / "scripts/check_privacy.py")
        (self.d / ".gitignore").write_text(".env\ndata/real/\n")
        (self.d / "README.md").write_text("ダミー\n")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def git(self, *a):
        subprocess.run(["git", *a], cwd=self.d, check=True, capture_output=True)

    def test_git_ignored_env_is_not_flagged(self):
        (self.d / ".env").write_text("NOTION_TOKEN=x\n")
        (self.d / "data/real").mkdir(parents=True)
        (self.d / "data/real/daily.json").write_text("[]")
        self.git("init", "-q")
        r = run(self.d)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_tracked_env_is_flagged(self):
        (self.d / ".env").write_text("NOTION_TOKEN=x\n")
        self.git("init", "-q")
        self.git("add", "-f", ".env")
        r = run(self.d)
        self.assertEqual(r.returncode, 1)
        self.assertIn("追跡してはいけない", r.stdout)

    def test_non_git_folder_warns_but_passes(self):
        (self.d / ".env").write_text("NOTION_TOKEN=x\n")
        r = run(self.d)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("含めないでください", r.stdout)

    def test_token_like_text_is_flagged(self):
        (self.d / "README.md").write_text("ntn_" + "A" * 30 + "\n")
        r = run(self.d)
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("A" * 30, r.stdout)  # 値は表示しない


    def test_listed_public_link_is_allowed_but_other_ids_are_not(self):
        link = "https://x-y.notion.site/" + "a" * 32
        other = "https://x-y.notion.site/" + "b" * 32
        (self.d / "config").mkdir()
        (self.d / "config/public_links.txt").write_text("# メモ\n" + link + "\n")
        (self.d / "README.md").write_text("公開: " + link + "\n")
        self.git("init", "-q")
        r = run(self.d)
        self.assertEqual(r.returncode, 0, r.stdout)
        (self.d / "README.md").write_text("公開: " + link + " 自分用: " + other + "\n")
        r = run(self.d)
        self.assertEqual(r.returncode, 1, r.stdout)


if __name__ == "__main__":
    unittest.main()
