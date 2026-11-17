#!/usr/bin/env python3
"""Render the profile card from the same public snapshot as the README."""
import json
import gzip
import textwrap
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / 'data/profile.json').read_text(encoding='utf-8'))
repos = data['repositories']
own = [r for r in repos if not r['fork'] and r['name'].lower() != data['user']['login'].lower()]
logo = (ROOT / 'assets/mardas-binary.txt').read_text(encoding='utf-8').splitlines()
starred = json.loads((ROOT / 'data/starred.json').read_text(encoding='utf-8'))
languages = Counter(r['language'] for r in own if r['language'])
rows = [(label, data['user'][key]) for label, key in
        [('Bio', 'bio'), ('Company', 'company')]
        if data['user'][key]]
recent = max((r for r in own if r['pushed_at'] and not r['archived']),
             key=lambda r: (r['pushed_at'], r['name']), default=None)
if recent:
    name = recent['name']
    name = name if len(name) <= 31 else name[:30] + '…'
    rows.append(('Last push', f"{name} / {recent['pushed_at'][:10]}"))
rows += [
    ('Languages', ' / '.join(name for name, _ in sorted(languages.items(), key=lambda p: (-p[1], p[0]))[:4]) or 'Not reported'),
    ('Repositories', f"{len(repos)} public"),
    ('Community', f"{data['user']['followers']} followers / {sum(r['stars'] for r in own)} stars"),
]
project_lines = [part for name in starred for part in
                 textwrap.wrap(name, width=45, break_on_hyphens=False)]
rows += ([('Projects' if i == 0 else ' ', line) for i, line in enumerate(project_lines)]
         if project_lines else [('Projects', 'No self-starred projects yet')])

def fit(value, limit=38):
    return value if len(value) <= limit else value[:limit-1] + '…'

with gzip.open(ROOT / 'assets/terminal-glyphs.json.gz', 'rt', encoding='utf-8') as f:
    glyphs = json.load(f)

def render(dark):
    bg, fg, muted, green = (('#0c0c0c', '#cccccc', '#cccccc', '#4ec95a') if dark else ('#ffffff', '#24292f', '#57606a', '#1a7f37'))
    # Glyph paths use the same metrics on every viewer, including GitHub's SVG
    # image renderer, without depending on fonts installed on the viewer.
    scale = 16 / 2048
    advance = 1233 * scale
    start_x, first_baseline, leading = 10, 19, 19

    def draw(text, column, row, color):
        chunks = []
        for offset, char in enumerate(text):
            path = glyphs.get(char, glyphs.get('?', ''))
            if path:
                x = start_x + (column + offset) * advance
                y = first_baseline + row * leading
                chunks.append(f'<path d="{path}" transform="translate({x:.3f} {y}) scale({scale:.8f} {-scale:.8f})"/>')
        return f'<g fill="{color}">' + ''.join(chunks) + '</g>'

    username = data['user']['login']
    title = f'github@{username}'
    output = [(None, title), (None, '-' * len(title))] + rows
    lines = []
    colors = ['#0c0c0c', '#c50f1f', '#13a10e', '#c19c00', '#0037da', '#881798', '#3a96dd', '#cccccc',
              '#767676', '#e74856', '#16c60c', '#f9f1a5', '#3b78ff', '#b4009e', '#61d6d6', '#f2f2f2']
    for i in range(max(len(logo), len(output) + 3)):
        line = logo[i] if i < len(logo) else ''
        lines.append(draw(line, 0, i, green))
        if i < len(output):
            label, value = output[i]
            if label is None:
                lines.append(draw(value, 50, i, green if i == 0 else muted))
            else:
                prefix = f'{label}: ' if label.strip() else '          '
                lines.append(draw(prefix, 50, i, green))
                lines.append(draw(fit(value, 55-len(prefix)), 50 + len(prefix), i, fg))
        elif i in (len(output) + 1, len(output) + 2):
            palette_row = i - len(output) - 1
            for j in range(8):
                x = start_x + (50 + j * 3) * advance
                y = first_baseline + i * leading - 15
                lines.append(f'<rect x="{x:.3f}" y="{y}" width="{3*advance:.3f}" height="{leading}" fill="{colors[palette_row*8+j]}"/>')
    terminal = ''.join(lines)
    height = 25 + (max(len(logo), len(output) + 3) - 1) * leading + 12
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="{height}" viewBox="0 0 1040 {height}" role="img" aria-labelledby="title desc">
<title id="title">github@mragetsars — neofetch profile</title><desc id="desc">Mardas ASCII logo beside a terminal profile with public GitHub information and self-starred projects.</desc>
<rect width="1040" height="{height}" fill="{bg}"/>{terminal}</svg>\n'''

changed = False
for theme in ('dark', 'light'):
    path = ROOT / 'assets' / f'profile-neofetch-{theme}.svg'
    content = render(theme == 'dark')
    if not path.exists() or path.read_text(encoding='utf-8') != content:
        changed = True
        if '--check' not in sys.argv:
            path.write_text(content, encoding='utf-8')
if changed and '--check' in sys.argv:
    raise SystemExit('Neofetch cards differ; run python3 scripts/render_neofetch.py')
