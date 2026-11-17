#!/usr/bin/env python3
"""Save the user's own public starred repositories, newest star first."""
import json
from pathlib import Path
import sys
from update_profile import ProfileError, REPO_NAME, atomic_write, get_json, load_config

ROOT = Path(__file__).resolve().parents[1]

def collect_starred(username, fetch=get_json):
    names, seen = [], set()
    for page in range(1, 101):
        batch = fetch(f'/users/{username}/starred?sort=created&direction=desc&per_page=100&page={page}')
        if not isinstance(batch, list):
            raise ProfileError('Invalid starred repositories response.')
        for repo in batch:
            if not isinstance(repo, dict) or not isinstance(repo.get('owner'), dict) or type(repo.get('private')) is not bool:
                raise ProfileError('Invalid starred repository record.')
            owner = repo['owner'].get('login')
            if not isinstance(owner, str):
                raise ProfileError('Invalid starred repository owner.')
            if repo['private'] or owner.lower() != username.lower():
                continue
            name = repo.get('name')
            if not isinstance(name, str) or not REPO_NAME.fullmatch(name) or name in ('.', '..'):
                raise ProfileError('Invalid starred repository name.')
            if name.lower() in seen:
                raise ProfileError('Duplicate starred repository across pages.')
            seen.add(name.lower())
            names.append(name)
        if len(batch) < 100:
            return names
    raise ProfileError('Starred repository pagination limit reached.')

def main():
    names = collect_starred(load_config(ROOT)['username'])
    path = ROOT / 'data/starred.json'
    content = json.dumps(names, ensure_ascii=False, indent=2) + '\n'
    if not path.exists() or path.read_text(encoding='utf-8') != content:
        atomic_write(path, content)

if __name__ == '__main__':
    try:
        main()
    except (ProfileError, ValueError, OSError) as exc:
        print(f'Star refresh failed: {exc}', file=sys.stderr)
        sys.exit(1)
