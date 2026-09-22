"""Offline regressions for incomplete optional SEO installations."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
CHECKER = REPO / 'tools/check-skills.py'


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skills = self.root / 'skills'
        shutil.copytree(REPO / 'skills', self.skills)
        for name in ('programmatic-seo', 'site-architecture', 'competitors', 'seo-sxo', 'seo-drift'):
            folder = self.skills / name
            folder.mkdir(exist_ok=True)
            (folder / 'SKILL.md').write_text(f'---\nname: {name}\n---\n', encoding='utf-8')
        self.bundle = self.root / 'upstream bundle'
        self.scripts = self.bundle / 'scripts'
        self.scripts.mkdir(parents=True)
        (self.bundle / 'requirements.txt').write_text('# fixture\n', encoding='utf-8')
        for name in ('fetch_page.py', 'parse_html.py', 'render_page.py', 'drift_baseline.py', 'drift_compare.py'):
            (self.scripts / name).write_text('print("usage: fixture --help")\n', encoding='utf-8')
        self.runtime()

    def runtime(self, ready=True, browser=True, broken_help=False):
        # A local process fixture for the upstream doctor/run CLI contract.
        source = ('import json, runpy, sys\nfrom pathlib import Path\n'
                  'if sys.argv[1] == "doctor":\n'
                  f'    print(json.dumps({{"ready": {ready!r}, "browser_ready": {browser!r}}}))\n'
                  f'    sys.exit({0 if ready else 3})\n'
                  f'if {broken_help!r}: sys.exit(1)\n'
                  'runpy.run_path(str(Path(__file__).parent / sys.argv[2]), run_name="__main__")\n')
        (self.scripts / 'runtime.py').write_text(source, encoding='utf-8')

    def run_check(self, *args, expected=0):
        proc = subprocess.run([sys.executable, str(CHECKER), '--skills-dir', str(self.skills), *args],
                              capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(proc.returncode, expected, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def optional(self, name, expected=0):
        data = self.run_check('--with-' + name, '--seo-bundle', str(self.bundle), expected=expected)
        return next(row for row in data['skills'] if row['skill'] == 'seo-' + name)

    def test_base_audit_does_not_require_optional_bundle(self):
        self.run_check()

    def test_three_sxo_files_do_not_prove_runtime_ready(self):
        folder = self.skills / 'seo-sxo/scripts'
        folder.mkdir()
        for name in ('fetch_page.py', 'parse_html.py', 'render_page.py'):
            shutil.copyfile(self.scripts / name, folder / name)
        self.run_check('--with-sxo', expected=1)

    def test_complete_drift_bundle_passes(self):
        self.assertFalse(self.optional('drift')['errors'])

    def test_complete_sxo_bundle_passes(self):
        self.assertFalse(self.optional('sxo')['errors'])

    def test_missing_compare_script_blocks_drift(self):
        (self.scripts / 'drift_compare.py').unlink()
        self.assertIn('drift_compare.py', str(self.optional('drift', expected=1)['errors']))

    def test_scripts_only_copy_is_rejected(self):
        (self.bundle / 'requirements.txt').unlink()
        self.assertIn('requirements.txt', str(self.optional('drift', expected=1)['errors']))

    def test_doctor_can_exit_zero_without_chromium(self):
        self.runtime(browser=False)
        self.assertIn('Chromium', str(self.optional('sxo', expected=1)['errors']))

    def test_unready_runtime_blocks_drift(self):
        self.runtime(ready=False)
        self.assertIn('runtime', str(self.optional('drift', expected=1)['errors']).lower())

    def test_script_import_failure_blocks_drift(self):
        (self.scripts / 'drift_compare.py').write_text('import nonexistent_preflight_dependency\n', encoding='utf-8')
        self.assertIn('drift_compare.py', str(self.optional('drift', expected=1)['errors']))

    def test_missing_skill_is_not_hidden_by_complete_bundle(self):
        (self.skills / 'seo-drift/SKILL.md').unlink()
        self.assertIn('SKILL.md', str(self.optional('drift', expected=1)['errors']))

    def test_invalid_doctor_output_is_reported_as_json(self):
        (self.scripts / 'runtime.py').write_text('print("invalid doctor output")\n', encoding='utf-8')
        self.assertIn('doctor', str(self.optional('drift', expected=1)['errors']))


if __name__ == '__main__':
    unittest.main()
