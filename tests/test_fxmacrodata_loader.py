import unittest

import pandas as pd

from spectre.data import FXMacroDataLoader


class TestFXMacroDataLoader(unittest.TestCase):

    def test_fetch_formats_fxmacrodata_rows(self):
        class MockResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "data": [
                        {"date": "2026-01-02", "val": 1.2},
                        {"date": "2026-01-01", "val": 1.1},
                    ]
                }

        class MockSession:
            def __init__(self):
                self.calls = []

            def get(self, url, params, headers, timeout):
                self.calls.append((url, params, headers, timeout))
                return MockResponse()

        session = MockSession()
        df = FXMacroDataLoader.fetch(
            "EUR/USD",
            "2026-01-01",
            "2026-01-02",
            api_key="test-key",
            api_root="https://example.test/api/v1",
            session=session,
        )

        self.assertEqual(
            session.calls[0][0],
            "https://example.test/api/v1/forex/EUR/USD",
        )
        self.assertEqual(session.calls[0][2], {"X-API-Key": "test-key"})
        self.assertEqual(df.index.names, ["date", "asset"])
        self.assertEqual(df.index.get_level_values("asset").unique()[0], "EUR/USD")
        self.assertEqual(list(df["close"]), [1.1, 1.2])

    def test_loader_returns_spectre_formatted_data(self):
        class MockResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {"data": [{"date": "2026-01-01", "val": 1.1}]}

        class MockSession:
            def get(self, url, params, headers, timeout):
                return MockResponse()

        loader = FXMacroDataLoader(
            "EURUSD",
            "2026-01-01",
            "2026-01-01",
            session=MockSession(),
        )
        df = loader.load()

        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(df.index.names, ["date", "asset"])
        self.assertIn("volume", df.columns)


if __name__ == "__main__":
    unittest.main()
