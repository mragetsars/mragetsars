import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

class RenderTests(unittest.TestCase):
    def test_transparency_and_versioned_images_follow_updated_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ('assets', 'data', 'scripts'):
                shutil.copytree(ROOT / folder, root / folder)
            shutil.copy(ROOT / 'README.md', root / 'README.md')
            def run(*args):
                return subprocess.run([sys.executable, str(root / 'scripts/render_neofetch.py'), *args],
                                      capture_output=True, text=True)
            self.assertEqual(run('--check').returncode, 0)
            before = (root / 'README.md').read_text()
            data = json.loads((root / 'data/starred.json').read_text())
            data.append('test-unique-repository')
            (root / 'data/starred.json').write_text(json.dumps(data))
            self.assertNotEqual(run('--check').returncode, 0)
            self.assertEqual(run().returncode, 0)
            after = (root / 'README.md').read_text()
            self.assertNotEqual(before, after)
            names = re.findall(r'assets/(profile-neofetch-[^"\s]+\.svg)', after)
            self.assertEqual(len(names), 2)
            for name in names:
                image = ET.parse(root / 'assets' / name).getroot()
                self.assertFalse(any(element.tag.endswith('rect') and element.get('width') == '1040'
                                     for element in image))
            self.assertEqual(len(list((root / 'assets').glob('profile-neofetch-*.svg'))), 2)
            self.assertEqual(run('--check').returncode, 0)
