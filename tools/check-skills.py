#!/usr/bin/env python3
"""Read-only audit dependency check. No installs, edits, or network requests."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

RELEASE = '2026-09-22.1'
# SHA-256 of UTF-8 files with LF line endings, generated from published packages.
PUBLISHED = {'ai-seo-better-than-corey-haines': {'agents/openai.yaml': '1042ee2b71388a7cd3438eca10d092514c428d8f1cd4078082ff61e17522348a', 'evals/evals.json': '96ede0c1e8c1593e05259c91b861c06b2388d34bd005d75378cefa1df43699d0', 'LICENSE': '3fa6ae47be8c0c0bbb5c084855b5a89dd847b924887d5290929d709f532b083e', 'references/comparison.md': '1eac6a913c4f30d37734e708ae426114a4e8eadc388edfd35efeb266427c73a3', 'references/content-patterns.md': 'e9db9bb341f2568d443875f3c07aa702b72db38fb513af29207d08fa1fbce895', 'references/platform-verification.md': '38236f2daf757e1d18d19121ed9e64b4ab68398b1838a534e10d1fd35f32399b', 'scripts/claim_check.py': 'a70cccf4afef073741942d649bebf2dd265b391f6fee4f1f7f6d3d3af8789c28', 'SKILL.md': '683bff79dbfe25bcfb8e0eb8b75dbf8dbd8d2fa8c5a440fe29754e2fbc5998d9'}, 'claim-check': {'scripts/claim_check.py': 'a70cccf4afef073741942d649bebf2dd265b391f6fee4f1f7f6d3d3af8789c28', 'SKILL.md': '6cfdae2fc10c8135e065c364e0d0890f6cb62f4ccd03e63e801b5eb1c6982358'}, 'remove-ai-slop-without-removing-ctas-and-good-marketing-copy': {'agents/openai.yaml': '7e2cf7822362e917ffa58fb7868cc4de3a65a002efe6e4d1627d91dd86b1df33', 'references/final-eval.md': '21f1e8cf20a4cf70cffc21342594ccdc6aba0890350e67eef8091163e264fa01', 'references/prose-rubric.md': '88fa82653daec7aca8df39db6ba9770ccb502ea1fb1d974aca6d3956d2b6fe9e', 'scripts/conversion_guard.py': '6c7445f3bb3c1ec1a84ebc5413499679f38fcbf48cf4d4fb8ee7b00113e61f09', 'SKILL.md': '2f8e33f641a2b748a59e2cf942c3793362095b054b4073811562b9adc201b9d4'}, 'schema-markup-better-than-corey-haines': {'agents/openai.yaml': '3d34c67c639992452ee9e4305284717f54d210bbdcc43ef731d8ab03fc339a47', 'evals/evals.json': '82443711091c1aaf7ad1d1fb1e1bde16596db5a8f5eb1b7f274dbd9fc0531ea3', 'LICENSE': '3fa6ae47be8c0c0bbb5c084855b5a89dd847b924887d5290929d709f532b083e', 'references/comparison.md': '85d950851e68dbf1e209c3065303eca7a49bece7603a9d480cb06279e9313e24', 'references/eligibility.md': '25e2c0e819fb084cedb44c2a244455b9ec2b6b5ca16a8105a638d84647d0f65d', 'references/schema-examples.md': '36cafe6c53da462e3aa66e20d3d201a0cb08416912fedf7db9c862521bfa2806', 'SKILL.md': '1083ad8a7c6c0667e7f889a2dfc82c15a16db6d6178daaa0fc05d28fdf775bb0'}, 'trend-scan': {'scripts/trend_scan.py': 'b9bc5d29d0d203eb4f7adb801e0c729107d1850cbc70166893bb5bcbb66899a5', 'SKILL.md': 'abbef4125f025bf194b3bdccd8c51026cda179b476f44293c2c7642bf21d5e84'}}
UPSTREAM = ['programmatic-seo', 'site-architecture', 'competitors']


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def check_optional(roots, name, seo_bundle=None):
    """Check the selected skill and its managed upstream bundle without setup."""
    folders = list(dict.fromkeys((root / name).resolve() for root in roots if (root / name).is_dir()))
    errors = []
    row = {'skill': name, 'path': str(folders[0]) if len(folders) == 1 else None, 'errors': errors}
    if len(folders) != 1:
        errors.append('missing SKILL.md or ambiguous skill copies; select the agent-loaded root with --skills-dir')
        return row
    entry = folders[0] / 'SKILL.md'
    if not entry.is_file():
        errors.append('missing SKILL.md')
        return row
    text = entry.read_text(encoding='utf-8-sig')
    row['sha256'] = digest(entry)
    if not re.search(r'^name:\s*[\"\']?' + re.escape(name) + r'[\"\']?\s*$', text, re.M):
        errors.append('frontmatter name does not match invocation')
    for relative in set(re.findall(r'references/[\w./-]+\.(?:md|json)', text)):
        if not (folders[0] / relative).is_file():
            errors.append('missing referenced resource ' + relative)
    if seo_bundle is None:
        candidates = list(dict.fromkeys(p.resolve() for root in roots for p in (root / name, root / 'seo')
                                        if (p / 'scripts/runtime.py').is_file()))
        if len(candidates) != 1:
            errors.append('select the complete upstream repository root with --seo-bundle PATH; a skill-only install is insufficient')
            return row
        seo_bundle = candidates[0]
    bundle = seo_bundle.expanduser().resolve()
    row['bundle'] = str(bundle)
    needed = ['fetch_page.py', 'parse_html.py', 'render_page.py']
    if name == 'seo-drift':
        needed += ['drift_baseline.py', 'drift_compare.py']
    for relative in ['requirements.txt', 'scripts/runtime.py'] + ['scripts/' + f for f in needed]:
        if not (bundle / relative).is_file():
            errors.append('missing bundle file ' + relative)
    if errors:
        return row
    runtime = [sys.executable, str(bundle / 'scripts/runtime.py')]
    try:
        proc = subprocess.run(runtime + ['doctor', '--json'], capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=30)
        state = json.loads(proc.stdout)
        if not isinstance(state, dict):
            raise ValueError('doctor returned a non-object')
        # Doctor can return zero with browser_ready=false. Require both flags.
        row['runtime_ready'] = state.get('ready') is True
        row['browser_ready'] = state.get('browser_ready') is True
        if proc.returncode or not row['runtime_ready']:
            errors.append('managed runtime is not ready; run upstream setup, then doctor --json')
        if not row['browser_ready']:
            errors.append('Chromium is not ready; run upstream setup without --skip-browser')
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        errors.append('runtime doctor failed: ' + type(exc).__name__)
    if errors:
        return row
    for script in needed:
        try:
            proc = subprocess.run(runtime + ['run', script, '--help'], capture_output=True, timeout=30)
            if proc.returncode:
                errors.append(script + ' --help failed in managed runtime; inspect its imports with the same runtime')
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(script + ' --help failed: ' + type(exc).__name__)
    row['scope'] = 'Files, doctor readiness, and script startup only; verify a rendered fetch and actual baseline/compare separately.'
    return row


def check(roots, standalone=False, with_sxo=False, with_drift=False, seo_bundle=None):
    results = []
    required = list(PUBLISHED) + UPSTREAM + (['seo-audit'] if standalone else [])
    for name in required:
        seen = set()
        found = False
        for root in roots:
            folder = root / name
            if not folder.exists() or folder.resolve() in seen:
                continue
            seen.add(folder.resolve())
            found = True
            errors = []
            entry = folder / 'SKILL.md'
            if not entry.is_file():
                errors.append('missing SKILL.md')
                text = ''
            else:
                text = entry.read_text(encoding='utf-8-sig')
                if not re.search(r'^name:\s*[\"\']?' + re.escape(name) + r'[\"\']?\s*$', text, re.M):
                    errors.append('frontmatter name does not match invocation')
            if name in PUBLISHED:
                for relative, expected in PUBLISHED[name].items():
                    path = folder / relative
                    if not path.is_file():
                        errors.append('missing ' + relative)
                    elif digest(path) != expected:
                        errors.append('different from checked publication: ' + relative)
            else:
                for relative in set(re.findall(r'(?:references|scripts)/[\w./-]+\.(?:md|py|json)', text)):
                    if not (folder / relative).is_file():
                        errors.append('missing referenced resource ' + relative)
            if not errors and name in PUBLISHED:
                for relative in PUBLISHED[name]:
                    if relative.startswith('scripts/') and relative.endswith('.py'):
                        try:
                            proc = subprocess.run([sys.executable, str(folder / relative), '--help'], capture_output=True, timeout=20)
                            if proc.returncode:
                                errors.append(relative + ' --help failed')
                        except (OSError, subprocess.TimeoutExpired) as exc:
                            errors.append(relative + ': ' + str(exc))
            results.append({'skill': name, 'path': str(folder.resolve()), 'sha256': digest(entry) if entry.is_file() else None, 'errors': errors})
        if not found:
            results.append({'skill': name, 'path': None, 'errors': ['not installed in checked roots']})
    for requested, name in [(with_sxo, 'seo-sxo'), (with_drift, 'seo-drift')]:
        if requested:
            results.append(check_optional(roots, name, seo_bundle))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path.cwd())
    parser.add_argument('--skills-dir', type=Path, action='append', help='Check only these roots; repeat for multiple roots. Otherwise inspect project and user roots.')
    parser.add_argument('--standalone', action='store_true', help='Also require seo-audit for the standalone runbook.')
    parser.add_argument('--with-sxo', action='store_true', help='Check SXO files, managed runtime readiness, and script startup.')
    parser.add_argument('--with-drift', action='store_true', help='Check drift files, managed runtime readiness, and baseline/compare script startup.')
    parser.add_argument('--seo-bundle', type=Path, help='Complete upstream claude-seo repository root, including requirements.txt and scripts/.')
    args = parser.parse_args()
    roots = args.skills_dir or [args.project / '.claude/skills', args.project / '.agents/skills', Path.home() / '.claude/skills', Path.home() / '.agents/skills']
    results = check(roots, args.standalone, args.with_sxo, args.with_drift, args.seo_bundle)
    failed = any(row['errors'] for row in results)
    print(json.dumps({'release': RELEASE, 'status': 'BLOCKED' if failed else 'FILES_VERIFIED', 'checked_roots': [str(p.resolve()) for p in roots], 'skills': results, 'session_note': 'Disk verification does not prove an existing agent session reloaded its skill text. Start a fresh session after installation; confirm the selected skill and bundle paths. Optional checks do not fetch pages: verify rendered fetching and baseline/compare on the actual target separately.'}, indent=2))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
