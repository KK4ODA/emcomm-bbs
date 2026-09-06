"""
Offline unit tests for Emcomm BBS. No network access is required.

    python -m unittest discover -s tests -v
"""

import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aggregator import WelfareAggregator  # noqa: E402
from app_config import AppConfig  # noqa: E402
from data_sources import PowerOutageFetcher, SpaceWeatherFetcher  # noqa: E402
from nextdoor_module import NextdoorFetcher  # noqa: E402
from output_generator import OutputGenerator  # noqa: E402
from plaintext_generators import PlainTextGenerator, wrap  # noqa: E402
from validator import WelfareValidator  # noqa: E402
from welfare_parser import WelfareParser  # noqa: E402

WELFARE_CONFIG = {
    'time_windows': [{'name': 'All Day', 'start': '00:00', 'end': '23:59'}],
    'validation': {'require_callsign': False, 'require_name': True, 'require_location': True,
                   'require_status': True, 'valid_statuses': ['SAFE', 'NEED ASSISTANCE', 'TRAFFIC']},
}


class ParserTests(unittest.TestCase):

    def parse(self, text):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "checkin.txt"
            path.write_text(text, encoding="utf-8")
            return WelfareParser().parse_file(path)

    def test_full_checkin(self):
        data = self.parse("CALLSIGN: W1ABC\nNAME: Jane Doe\nLOCATION: Boston, MA\n"
                          "STATUS: NEED ASSISTANCE\nPOWER: OFF\nCONTACT: 555-123-4567\n"
                          "MESSAGE: Power out since noon.\nNeed insulin.\n")
        self.assertEqual(data['callsign'], 'W1ABC')
        self.assertEqual(data['status'], 'NEED ASSISTANCE')
        self.assertEqual(data['power'], 'OFF')
        self.assertEqual(data['message'], "Power out since noon.\nNeed insulin.")

    def test_template_hints_are_treated_as_blank(self):
        data = self.parse("CALLSIGN: (or leave blank if not a licensed ham)\nNAME: Sam\n"
                          "LOCATION: Here\nSTATUS: (SAFE / NEED ASSISTANCE / TRAFFIC)\n"
                          "POWER: (ON / OFF / GENERATOR)\nMESSAGE:\n")
        self.assertIsNone(data['callsign'])
        self.assertIsNone(data['status'])
        self.assertIsNone(data['power'])

    def test_blank_field_does_not_swallow_next_line(self):
        data = self.parse("CALLSIGN:\nNAME: Sam\nLOCATION: Here\nSTATUS: SAFE\n")
        self.assertIsNone(data['callsign'])
        self.assertEqual(data['name'], 'Sam')


class ValidatorTests(unittest.TestCase):

    def setUp(self):
        self.v = WelfareValidator(WELFARE_CONFIG)

    def test_non_ham_checkin_is_valid(self):
        ok, errors = self.v.validate({'callsign': None, 'name': 'Sam', 'location': 'Here', 'status': 'SAFE'})
        self.assertTrue(ok, errors)

    def test_bad_callsign_and_status(self):
        ok, errors = self.v.validate({'callsign': '12345', 'name': 'Sam', 'location': 'Here',
                                      'status': 'FINE'})
        self.assertFalse(ok)
        self.assertEqual(len(errors), 2)

    def test_contact_format(self):
        self.assertTrue(self.v.validate_contact('jane@example.com')[0])
        self.assertTrue(self.v.validate_contact('(555) 123-4567')[0])
        self.assertFalse(self.v.validate_contact('call me')[0])


class AggregatorTests(unittest.TestCase):

    def setUp(self):
        self.agg = WelfareAggregator(WELFARE_CONFIG)
        self.base = {'callsign': 'W1ABC', 'name': 'Jane', 'location': 'Boston', 'status': 'SAFE',
                     'message': 'ok', 'received_time': datetime.now()}

    def test_window_detection(self):
        self.assertIsNotNone(self.agg.get_current_window())
        closed = WelfareAggregator({'time_windows': [{'name': 'x', 'start': '03:00', 'end': '03:01'}]})
        self.assertIsNone(closed.get_current_window(datetime(2026, 1, 1, 12, 0)))

    def test_duplicate_then_update(self):
        ok, msg, window = self.agg.add_checkin(dict(self.base))
        self.assertTrue(ok)
        ok, msg, _ = self.agg.add_checkin(dict(self.base))
        self.assertFalse(ok)
        self.assertIn('identical', msg)
        ok, msg, _ = self.agg.add_checkin({**self.base, 'status': 'TRAFFIC'})
        self.assertTrue(ok)
        self.assertIn('update #1', msg)
        checkins = self.agg.get_window_checkins(window['key'])
        self.assertEqual(len(checkins), 1)
        self.assertEqual(checkins[0]['history'][0]['status'], 'SAFE')


class OutputTests(unittest.TestCase):

    def test_html_escapes_operator_text(self):
        with tempfile.TemporaryDirectory() as d:
            gen = OutputGenerator({'directories': {'output': d}, 'output': {}})
            window = {'name': 'Net', 'start': '00:00', 'end': '23:59', 'date': datetime.now().date(),
                      'key': 'k'}
            checkins = [{'callsign': 'W1ABC', 'name': '<b>Jane</b>', 'location': 'x', 'status': 'SAFE',
                         'message': 'a & b', 'received_time': datetime.now()}]
            files = gen.generate_all(window, checkins)
            html = Path(files['html']).read_text(encoding='utf-8')
            self.assertIn('&lt;b&gt;Jane&lt;/b&gt;', html)
            self.assertIn('a &amp; b', html)
            self.assertTrue(Path(files['text']).exists() and Path(files['csv']).exists())


class PlainTextTests(unittest.TestCase):

    def test_wrap_keeps_long_words_and_indents(self):
        lines = wrap("word " * 30 + "https://example.com/a/very/long/url/that/should/not/be/split",
                     width=40, indent="  ", first_indent="* ")
        self.assertTrue(lines[0].startswith("* "))
        self.assertTrue(all(l.startswith("  ") for l in lines[1:]))
        self.assertTrue(any("https://example.com" in l for l in lines))

    def test_power_report(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "p.txt"
            PlainTextGenerator.create_power_txt(str(path), {
                'timestamp': 't', 'total_outages': 5, 'utility_count': 2, 'utilities_with_outages': 1,
                'national_summary': 'summary', 'states': [{'state': 'GA', 'outages': 5, 'utilities': 1}],
                'top_utilities': [{'state': 'GA', 'name': 'Util', 'outages': 5}]})
            text = path.read_text(encoding='utf-8')
            self.assertIn("TOTAL OUTAGES : 5", text)
            self.assertIn("END POWER OUTAGE REPORT", text)


class DataSourceTests(unittest.TestCase):

    def test_state_lookup(self):
        self.assertEqual(PowerOutageFetcher.get_state("14354", "whatever"), "UT")
        self.assertEqual(PowerOutageFetcher.get_state("0", "Some Coop (WV)"), "WV")
        self.assertEqual(PowerOutageFetcher.get_state("0", "West Virginia Power"), "WV")
        self.assertIsNone(PowerOutageFetcher.get_state("0", "Mystery Utility"))

    def test_band_estimate(self):
        self.assertEqual(SpaceWeatherFetcher.estimate_bands(160, 1)['10m'], 'Excellent')
        self.assertEqual(SpaceWeatherFetcher.estimate_bands(80, 6)['20m'], 'Poor')
        self.assertEqual(SpaceWeatherFetcher.estimate_bands(None, None), SpaceWeatherFetcher.FALLBACK_BANDS)

    def test_nextdoor_keyword_escalation(self):
        self.assertEqual(NextdoorFetcher.classify("Gas leak on Main St", "low"), "high")
        self.assertEqual(NextdoorFetcher.classify("Evacuate now", "low"), "critical")
        self.assertEqual(NextdoorFetcher.classify("Bake sale Saturday", "low"), "low")


class ConfigTests(unittest.TestCase):

    def test_roundtrip_and_tolerance(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "cfg.json"
            cfg = AppConfig(save_directory=d, anthropic_api_key="k", weather_regions=[1, 4])
            cfg.checkboxes['news'] = False
            cfg.save(path)
            loaded = AppConfig.load(path)
            self.assertEqual(loaded.anthropic_api_key, "k")
            self.assertEqual(loaded.weather_regions, [1, 4])
            self.assertFalse(loaded.checkboxes['news'])

            path.write_text(json.dumps({"unknown": 1, "main_interval_hours": "abc",
                                        "checkboxes": {"bogus": True, "space": False}}))
            loaded = AppConfig.load(path)
            self.assertEqual(loaded.main_interval_hours, 6)
            self.assertFalse(loaded.checkboxes['space'])
            self.assertNotIn('bogus', loaded.checkboxes)


if __name__ == "__main__":
    unittest.main()
