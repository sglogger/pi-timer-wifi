import hashlib
import hmac
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'firmware'))
from mesh import MAGIC, MAX_PACKET, TAG, Codec  # noqa: E402
from firmware.timer_logic import Replica  # noqa: E402
from server import EPOCH, Timer, next_generation  # noqa: E402

TOKEN = 'microPythonTestToken1234'


class Clock:
    def __init__(self):
        self.now = 1000

    def __call__(self):
        return self.now


class CodecTests(unittest.TestCase):
    def setUp(self):
        self.codec = Codec(TOKEN)

    def test_tag_is_standard_hmac_sha256(self):
        data = MAGIC + b'["s", 1, null, 2, 3]'
        expected = hmac.new(TOKEN.encode(), data, hashlib.sha256).digest()[:TAG]
        self.assertEqual(self.codec.tag(data), expected)
        long_key = 'x' * 100
        self.assertEqual(Codec(long_key).tag(data),
                         hmac.new(long_key.encode(), data, hashlib.sha256).digest()[:TAG])

    def test_roundtrip(self):
        packet = self.codec.encode('a' * 36, 5, -1200, (7, 123456))
        self.assertLessEqual(len(packet), MAX_PACKET)
        self.assertEqual(self.codec.decode(packet), {'protocol': 1, 'session': 'a' * 36, 'revision': 5,
                                                     'remaining_ms': -1200, 'stamp': (7, 123456)})
        self.assertIsNone(self.codec.decode(self.codec.encode('s', 1, None, (1, 1)))['remaining_ms'])

    def test_forged_foreign_and_garbage_packets_are_ignored(self):
        packet = self.codec.encode('s', 5, 60000, (7, 100))
        tampered = packet.replace(b'60000', b'90000')
        self.assertIsNone(self.codec.decode(tampered))
        self.assertIsNone(Codec('another-token-123456789').decode(packet))
        self.assertIsNone(self.codec.decode(b'other ESP-NOW traffic'))
        self.assertIsNone(self.codec.decode(b''))
        data = MAGIC + b'not json'
        self.assertIsNone(self.codec.decode(data + self.codec.tag(data)))
        data = MAGIC + b'[1, 2]'
        self.assertIsNone(self.codec.decode(data + self.codec.tag(data)))


class MergeTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.replica = Replica(self.clock, lambda a, b: a - b)

    def state(self, stamp, revision=1, remaining=60000, session='a'):
        return dict(protocol=1, session=session, revision=revision, remaining_ms=remaining, stamp=stamp)

    def test_newest_server_contact_wins(self):
        self.assertTrue(self.replica.merge(self.state((1, 500))))
        self.assertEqual(self.replica.advance(), 60000)
        self.assertTrue(self.replica.merge(self.state((1, 900), remaining=50000)))
        self.assertEqual(self.replica.advance(), 50000)
        self.assertIsNotNone(self.replica.last_mesh)
        self.assertIsNone(self.replica.last_sync)

    def test_replayed_or_relayed_older_states_lose(self):
        self.replica.merge(self.state((1, 900), remaining=50000))
        self.assertFalse(self.replica.merge(self.state((1, 900), remaining=1)))
        self.assertFalse(self.replica.merge(self.state((1, 500), remaining=1)))
        self.assertEqual(self.replica.advance(), 50000)

    def test_new_server_generation_wins_and_old_generation_loses(self):
        self.replica.merge(self.state((1, 99999), session='old', revision=9))
        self.assertTrue(self.replica.merge(self.state((2, 10), session='new', revision=0, remaining=None)))
        self.assertFalse(self.replica.merge(self.state((1, 999999), session='old', revision=10)))
        self.assertIsNone(self.replica.advance())

    def test_lower_revision_in_same_session_is_rejected(self):
        self.replica.merge(self.state((1, 500), revision=4))
        self.assertFalse(self.replica.merge(self.state((1, 600), revision=3)))

    def test_states_without_stamp_are_not_meshed(self):
        self.assertFalse(self.replica.merge(self.state(None)))
        with self.assertRaises(ValueError):
            self.replica.merge(self.state((1, -1)))
        with self.assertRaises(ValueError):
            self.replica.merge(self.state('1,2'))

    def test_http_keeps_newer_mesh_state_of_same_session(self):
        self.replica.merge(self.state((1, 900), remaining=50000))
        self.assertFalse(self.replica.apply(self.state([1, 800], remaining=1), 10))
        self.assertTrue(self.replica.apply(self.state([1, 1000], remaining=40000), 10))
        self.assertEqual(self.replica.stamp, (1, 1000))
        # A restarted server is always authoritative over HTTP.
        self.assertTrue(self.replica.apply(self.state([0, 5], session='b', remaining=None), 10))


class StampTests(unittest.TestCase):
    def test_snapshot_stamp_grows_within_a_generation(self):
        clock = Clock()
        timer = Timer(clock, generation=42)
        first = timer.snapshot()['stamp']
        clock.now += 1.5
        self.assertEqual(first, [42, 0])
        self.assertEqual(timer.sync(dict(session=None, revision=-1, ble_connected=False,
                                         ble_status=''))['stamp'], [42, 1500])

    def test_generation_is_persisted_and_survives_a_clock_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            first = next_generation(directory, now=lambda: EPOCH + 1000)
            # Pi without RTC after a power loss: clock far behind.
            second = next_generation(directory, now=lambda: EPOCH + 10)
            self.assertEqual((first, second), (1000, 1001))
            with open(os.path.join(directory, 'generation')) as file:
                self.assertEqual(file.read(), '1001')

    def test_generation_without_state_directory_uses_clock(self):
        self.assertEqual(next_generation('', now=lambda: EPOCH + 77), 77)
        with patch('builtins.print') as warning:
            self.assertEqual(next_generation('/nonexistent/dir', now=lambda: EPOCH + 5), 5)
        warning.assert_called_once()


if __name__ == '__main__':
    unittest.main()
