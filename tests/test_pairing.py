import base64
import unittest

from receiver.pairing import (
    Pairing,
    TRANSPORT_AUTO,
    TRANSPORT_TAILCAT,
    decode_pairing,
    encode_pairing,
)


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

    def test_tailcat_pairing_uses_v2_and_redacts_address(self):
        address = 'tc' + ('A' * 64)
        value = Pairing(
            '192.168.1.20', 23337, 'B' * 43, 'cd' * 32,
            transport=TRANSPORT_TAILCAT,
            tailcat_address=address,
        )

        uri = encode_pairing(value)
        decoded = decode_pairing(uri)

        self.assertEqual(value, decoded)
        self.assertNotIn(address, repr(value))
        raw = base64.urlsafe_b64decode(
            uri.split('p=', 1)[1] + '=' * (-len(uri.split('p=', 1)[1]) % 4)
        ).decode()
        self.assertTrue(raw.startswith('2\ntailcat\n'))
        self.assertTrue(raw.endswith(address))

    def test_unified_v3_pairing_round_trip(self):
        address = 'tc' + ('Z' * 64)
        value = Pairing(
            '192.168.1.20', 23337, 'C' * 43, 'ef' * 32,
            transport=TRANSPORT_AUTO,
            tailcat_address=address,
            device_id='0123456789abcdef0123456789abcdef',
            device_name='Office PC',
        )

        uri = encode_pairing(value)
        decoded = decode_pairing(uri)

        self.assertEqual(value, decoded)
        self.assertTrue(uri.startswith('voiceinput2pc://pair?p='))
        raw = base64.urlsafe_b64decode(
            uri.split('p=', 1)[1] + '=' * (-len(uri.split('p=', 1)[1]) % 4)
        ).decode()
        fields = raw.split('\n')
        self.assertEqual('3', fields[0])
        self.assertEqual('auto', fields[1])
        self.assertEqual('0123456789abcdef0123456789abcdef', fields[2])
        self.assertEqual('Office PC', fields[3])
        self.assertEqual('192.168.1.20', fields[4])
        self.assertEqual('23337', fields[5])
        self.assertEqual(address, fields[8])
        self.assertNotIn(value.token, repr(value))
        self.assertNotIn(value.fingerprint, repr(value))
        self.assertNotIn(address, repr(value))

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
                    'voiceinput2pc://pair?p=' + ('A' * 9000)):
            with self.subTest(raw=raw[:40]):
                with self.assertRaises(ValueError):
                    decode_pairing(raw)

        with self.assertRaises(ValueError):
            encode_pairing(Pairing(
                'pc.lan', 23337, valid.token, valid.fingerprint,
                transport=TRANSPORT_TAILCAT,
                tailcat_address='bad',
            ))


if __name__ == '__main__':
    unittest.main()
