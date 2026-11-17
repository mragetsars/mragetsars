import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from update_pins import parse_response
from update_profile import ProfileError

class PinsTests(unittest.TestCase):
    def test_preserves_pin_order(self):
        nodes = [{'nameWithOwner': 'a/one', 'isPrivate': False},
                 {'nameWithOwner': 'b/two', 'isPrivate': False}]
        self.assertEqual(parse_response({'data': {'user': {'pinnedItems': {'nodes': nodes}}}}), ['a/one', 'b/two'])

    def test_errors_and_private_items_fail_closed(self):
        with self.assertRaises(ProfileError):
            parse_response({'errors': [{'message': 'unavailable'}]})
        with self.assertRaises(ProfileError):
            parse_response({'data': {'user': {'pinnedItems': {'nodes': [{'nameWithOwner': 'a/secret', 'isPrivate': True}]}}}})

if __name__ == '__main__':
    unittest.main()
