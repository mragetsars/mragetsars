#!/usr/bin/env python3
"""Fetch public pinned repositories via GitHub GraphQL."""
import json
import os
from pathlib import Path
import sys
from urllib.request import Request, build_opener

from update_profile import NoRedirect, ProfileError, atomic_write, load_config

ROOT = Path(__file__).resolve().parents[1]
QUERY = '''query($login: String!) { user(login: $login) {
  pinnedItems(first: 6, types: REPOSITORY) {
    nodes { ... on Repository { nameWithOwner isPrivate } }
  }
} }'''

def parse_response(payload):
    if not isinstance(payload, dict) or payload.get('errors'):
        raise ProfileError('GitHub GraphQL returned errors; pins were not changed.')
    try:
        nodes = payload['data']['user']['pinnedItems']['nodes']
        if not isinstance(nodes, list) or len(nodes) > 6:
            raise ValueError()
        names = []
        for node in nodes:
            name = node['nameWithOwner']
            if node['isPrivate'] is not False or not isinstance(name, str):
                raise ValueError()
            import re
            if not re.fullmatch(r'[A-Za-z0-9-]+/[A-Za-z0-9_.-]+', name):
                raise ValueError()
            names.append(name)
        return names
    except (KeyError, TypeError, ValueError):
        raise ProfileError('Invalid pinned repository data; pins were not changed.') from None

def main():
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        raise ProfileError('GITHUB_TOKEN is required to refresh pins via GraphQL.')
    login = load_config(ROOT)['username']
    body = json.dumps({'query': QUERY, 'variables': {'login': login}}).encode()
    request = Request('https://api.github.com/graphql', data=body, headers={
        'Authorization': f'Bearer {token}', 'Content-Type': 'application/json',
        'Accept': 'application/vnd.github+json', 'User-Agent': 'mragetsars-profile'})
    try:
        with build_opener(NoRedirect()).open(request, timeout=20) as response:
            payload = json.load(response)
    except Exception as exc:
        raise ProfileError(f'Could not refresh pinned repositories: {type(exc).__name__}.') from None
    names = parse_response(payload)
    content = json.dumps(names, ensure_ascii=False, indent=2) + '\n'
    path = ROOT / 'data/pinned.json'
    if not path.exists() or path.read_text(encoding='utf-8') != content:
        atomic_write(path, content)

if __name__ == '__main__':
    try:
        main()
    except ProfileError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
