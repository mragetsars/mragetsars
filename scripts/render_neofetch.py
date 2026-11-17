#!/usr/bin/env python3
"""Render the profile card from the same public snapshot as the README."""
import html
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / 'data/profile.json').read_text(encoding='utf-8'))
repos = data['repositories']
own = [r for r in repos if not r['fork'] and r['name'].lower() != data['user']['login'].lower()]
logo = [
    '       +%.           .-++**+-.',
    '     :#@@+        :+#%@@@@@@@%=',
    '    +%@@@%-     -*@@@@@@@@@@@@@-',
    '   *@@@@@@%-  .*@@@@@@@@@@@@@@%:',
    '  *@@@@@@@@@*=%@@@@@@@@@@@@@@%:',
    ' *@@@@@@@@@@@@@@@@@@@@@@@@@%+',
    '-@@@@@@@@@@@@@@@@@@@@@@@@@@%#=',
    '#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@#.',
    '@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@#',
    '%@@@@@@@@@@@@@@@#*+*#@@@@@@@@@@@',
    '*@@@@@@@@@@@@@*:     =%@@@@@@@@#',
    ':%@@@@@@@@@@#-        #@@@@@@@%.',
    ' :#@@@@@@@%=         .%@@@@@@*.',
    '   :+***+-          :#@@@@%*-',
    '                 .=#%%#*+-.',
]
pins = json.loads((ROOT / 'data/pinned.json').read_text(encoding='utf-8'))
languages = Counter(r['language'] for r in own if r['language'])
rows = [(label, data['user'][key]) for label, key in
        [('Bio', 'bio'), ('Company', 'company'), ('Location', 'location')]
        if data['user'][key]]
rows += [
    ('Languages', ' / '.join(name for name, _ in sorted(languages.items(), key=lambda p: (-p[1], p[0]))[:4]) or 'Not reported'),
    ('Repositories', f"{len(repos)} public"),
    ('Community', f"{data['user']['followers']} followers / {sum(r['stars'] for r in own)} stars"),
]
rows += [('Pinned' if i == 0 else ' ', name.split('/', 1)[1] if name.lower().startswith(data['user']['login'].lower() + '/') else name)
         for i, name in enumerate(pins[:2])]

def fit(value, limit=38):
    return value if len(value) <= limit else value[:limit-1] + '…'

def render(dark):
    bg, bar, border, fg, muted, green = (('#0d1117', '#161b22', '#30363d', '#e6edf3', '#8b949e', '#56d364') if dark else ('#ffffff', '#f6f8fa', '#d0d7de', '#1f2328', '#656d76', '#1a7f37'))
    e = html.escape
    username = data['user']['login']
    title = f'github@{username}'
    output = [(None, title), (None, '-' * len(title))] + rows
    lines = []
    colors = ['#1e5f2d', '#267637', '#2e8d41', '#35a54b', '#3fb950', '#5ccc69', '#79dc85', '#9aebab']
    for i, line in enumerate(logo):
        # One text element per terminal row: both columns share baseline,
        # font and character grid, just like monospaced terminal output.
        left = e(line.ljust(36))
        right = ''
        if i < len(output):
            label, value = output[i]
            if label is None:
                right = f'<tspan fill="{green if i == 0 else muted}">{e(value)}</tspan>'
            else:
                prefix = f'{label}: ' if label.strip() else '        '
                right = (f'<tspan fill="{green}">{e(prefix)}</tspan>'
                         f'<tspan fill="{fg}">{e(fit(value, 49-len(prefix)))}</tspan>')
        elif i == len(output) + 1:
            right = ''.join(f'<tspan fill="{c}">██</tspan>' for c in colors)
        lines.append(f'<text x="40" y="{120+i*20}" xml:space="preserve"><tspan fill="{green}">{left}</tspan>{right}</text>')
    terminal = ''.join(lines)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="470" viewBox="0 0 960 470" role="img" aria-labelledby="title desc">
<title id="title">github@mragetsars — neofetch profile</title><desc id="desc">Mardas ASCII logo beside a terminal profile with public GitHub information and pinned repositories.</desc>
<rect x="1" y="1" width="958" height="468" rx="14" fill="{bg}" stroke="{border}"/>
<path d="M15 1H945A14 14 0 0 1 959 15V47H1V15A14 14 0 0 1 15 1Z" fill="{bar}"/><path d="M1 47H959" stroke="{border}"/>
<g fill="{muted}"><circle cx="24" cy="24" r="4"/><circle cx="40" cy="24" r="4"/><circle cx="56" cy="24" r="4"/></g>
<g font-family="DejaVu Sans Mono,Consolas,monospace"><text x="80" y="29" font-size="12" fill="{muted}">mragetsars@github: ~</text><text x="40" y="80" font-size="15" fill="{green}">❯ <tspan fill="{fg}">neofetch</tspan></text>
<g font-size="16">{terminal}</g>
<text x="40" y="448" font-size="14" fill="{green}">❯ <tspan fill="{muted}">_</tspan></text></g></svg>\n'''

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
