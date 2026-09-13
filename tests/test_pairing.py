import base64
import unittest

from receiver.pairing import Pairing, decode_pairing, encode_pairing


class PairingTests(unittest.TestCase):
    def test_known_vector_round_trips_and_redacts_secrets(self):
        value = Pairing('192.168.1.20', 23337, 'A' * 43, 'ab' * 32)

        uri = encode_pairing(value)

        expected_raw = ('1\n192.168.1.20\n23337\n' + 'A' * 43 + '\n' + 'ab' * 32).encode()
        expected_payload = base64.urlsafe_b64encode(expected_raw).decode().rstrip('=')
        self.assertEqual('voiceinput2pc://pair?p=' + expected_payload, uri)
        self.assertEqual(value, decode_pairing(uri))
        self.assertNotIn(value.token, repr(value))
        self.assertNotIn(value.fingerprint, repr(value))

    def test_invalid_pairing_is_rejected(self):
        valid = Pairing('pc.lan', 23337, 'aB_-' * 10, '12' * 32)
        invalid_values = (
            Pairing('bad host', 23337, valid.token, valid.fingerprint),
            Pairing('pc.lan', 0, valid.token, valid.fingerprint),
            Pairing('pc.lan', 23337, 'short', valid.fingerprint),
            Pairing('pc.lan', 23337, valid.token, 'not-a-fingerprint'),
        )
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    encode_pairing(value)

        for raw in ('', 'https://example.com', 'voiceinput2pc://pair?p=bad',
                    'voiceinput2pc://pair?p=' + ('A' * 5000)):
            with self.subTest(raw=raw[:40]):
                with self.assertRaises(ValueError):
                    decode_pairing(raw)


if __name__ == '__main__':
    unittest.main()
