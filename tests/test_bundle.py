import pathlib, subprocess, sys, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


class Bundle(unittest.TestCase):
    def test_bundle_is_up_to_date(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts/make_bundle.py"), "--check"],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_bundle_has_no_personal_files(self):
        text = (ROOT / "chatgpt-bundle.txt").read_text(encoding="utf-8")
        for bad in (".env\n", ".local.json ===", "data/real", "data/snapshot"):
            self.assertNotIn("=== FILE: " + bad, text)

    def test_every_file_in_bundle_exists_and_is_marked(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make_bundle
        text = (ROOT / "chatgpt-bundle.txt").read_text(encoding="utf-8")
        for rel in make_bundle.FILES:
            self.assertTrue((ROOT / rel).exists(), rel)
            self.assertIn("=== FILE: %s ===\n" % rel, text)
        self.assertTrue(text.endswith("=== END ===\n"))


if __name__ == "__main__":
    unittest.main()
