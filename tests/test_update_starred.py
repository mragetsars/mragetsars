import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from update_starred import collect_starred
from update_profile import ProfileError

def repo(owner, name, private=False):
    return {'owner': {'login': owner}, 'name': name, 'private': private}

class StarredTests(unittest.TestCase):
    def test_pagination_filters_and_keeps_star_order(self):
        page1 = [repo('other', f'x{i}') for i in range(98)] + [repo('Me', 'first'), repo('me', 'second')]
        page2 = [repo('me', 'private', True), repo('other', 'foreign'), repo('ME', 'third')]
        result = collect_starred('me', lambda path: page2 if 'page=2' in path else page1)
        self.assertEqual(result, ['first', 'second', 'third'])

    def test_bad_or_duplicate_data_fails(self):
        with self.assertRaises(ProfileError):
            collect_starred('me', lambda path: [repo('me', 'same'), repo('Me', 'same')])
        with self.assertRaises(ProfileError):
            collect_starred('me', lambda path: [{'owner': {'login': 'me'}}])

    def test_empty_list_is_valid(self):
        self.assertEqual(collect_starred('me', lambda path: []), [])
