#!/usr/bin/env python3
"""Check tracked documentation layout and the reviewed usage README digest."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys

MARKDOWN = {'.md', '.markdown', '.mdown', '.mkd', '.mkdn', '.mdwn', '.mdx', '.rmd', '.qmd'}
OTHER_DOCS = {'.rst', '.adoc', '.asciidoc'}


def check(root, include_history=True, history_required=False):
    raw = subprocess.check_output(['git', 'ls-files', '--stage', '-z'], cwd=root)
    entries = {}
    errors = []
    for record in raw.split(b'\0'):
        if not record:
            continue
        metadata, encoded = record.split(b'\t', 1)
        mode, _oid, stage = metadata.decode().split()
        name = encoded.decode('utf-8', 'surrogateescape')
        if stage != '0':
            errors.append('unmerged index entry: ' + name)
        entries[name] = mode
        path = PurePosixPath(name)
        if name != 'README.md' and (path.suffix.lower() in MARKDOWN | OTHER_DOCS
                                    or path.name.lower().startswith('readme.')):
            errors.append('documentation must live in the private docs repository: ' + name)
    if entries.get('README.md') != '100644' and entries.get('README.md') != '100755':
        errors.append('a regular, tracked root README.md is required')
    else:
        readme = root / 'README.md'
        if readme.is_symlink() or not readme.is_file():
            errors.append('root README.md must be a regular file')
        else:
            try:
                body = readme.read_bytes()
                if not any(line.startswith('# ') for line in body.decode('utf-8').splitlines()):
                    errors.append('root README.md needs a product heading')
                policy_path = root / '.github/readme-source.json'
                if policy_path.is_symlink():
                    raise ValueError('README source policy cannot be a symlink')
                policy = json.loads(policy_path.read_text())
                if policy.get('version') != 1:
                    raise ValueError('unsupported README source policy')
                if hashlib.sha256(body).hexdigest() != policy.get('sha256'):
                    errors.append('README differs from its reviewed publication; update the private source first')
                history = policy.get('history')
                if history_required and history is None:
                    raise ValueError('public repositories require a history boundary')
                if include_history and history is not None:
                    if set(history) != {'forbidden_commits'} or not isinstance(history['forbidden_commits'], list) or not history['forbidden_commits']:
                        raise ValueError('invalid public history boundary')
                    forbidden = set(history['forbidden_commits'])
                    if any(not isinstance(oid, str) or len(oid) != 40 or any(c not in '0123456789abcdef' for c in oid) for oid in forbidden):
                        raise ValueError('invalid original history identity')
                    shallow = subprocess.check_output(['git', 'rev-parse', '--is-shallow-repository'], cwd=root, text=True).strip()
                    if shallow != 'false':
                        raise ValueError('public history verification requires fetch-depth: 0')
                    ancestors = set(subprocess.check_output(['git', 'rev-list', 'HEAD'], cwd=root, text=True).splitlines())
                    if ancestors & forbidden:
                        errors.append('original history was reintroduced; transplant changes onto the cleaned main history')
                    patterns = [':(icase)*'+suffix for suffix in sorted(MARKDOWN)]
                    past = subprocess.check_output(['git', 'log', '--format=', '--name-only', '-z', 'HEAD', '--', *patterns], cwd=root)
                    extra = {name.decode('utf-8', 'surrogateescape') for name in past.split(b'\0') if name and name != b'README.md'}
                    errors.extend('historical Markdown must remain in private docs: '+name for name in sorted(extra))

            except (OSError, ValueError, UnicodeError) as error:
                errors.append('invalid README source policy or README: ' + str(error))
    return errors


def main():
    root = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip())
    errors = check(root, history_required=os.environ.get('REQUIRE_CLEAN_HISTORY') == 'true')
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        return 1
    print('Documentation policy passed: one root README.md, reviewed source digest matches.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
