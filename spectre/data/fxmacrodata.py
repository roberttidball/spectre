"""
FXMacroData daily FX reference-rate loader.
"""
import os

import pandas as pd
import requests

from .dataloader import DataLoader


FXMACRODATA_API_ROOT = "https://api.fxmacrodata.com/v1"


def _split_pair(pair):
    pair = pair.upper().replace("/", "").replace("-", "").replace("_", "")
    if len(pair) != 6:
        raise ValueError("FX pair must be formatted like 'EURUSD' or 'EUR/USD'")
    return pair[:3], pair[3:]


class FXMacroDataLoader(DataLoader):
    """Load FXMacroData daily reference rates as Spectre OHLCV data.

    FXMacroData publishes one official reference value per currency pair and
    date. The value is copied into open, high, low, and close with zero volume
    so it can be consumed by Spectre's normal daily-price data path.
    """

    def __init__(
        self,
        pair,
        start_date,
        end_date,
        api_key=None,
        api_root=FXMACRODATA_API_ROOT,
        session=None,
    ):
        self.pair = pair
        self.start_date = start_date
        self.end_date = end_date
        df = self.fetch(
            pair,
            start_date,
            end_date,
            api_key=api_key,
            api_root=api_root,
            session=session,
        )
        super().__init__("", ohlcv=("open", "high", "low", "close", "volume"), adjustments=None)
        self.df = self._format_fxmacrodata(df)
        self.test_load()

    @property
    def last_modified(self) -> float:
        return 1

    def _load(self):
        return self.df

    def _format_fxmacrodata(self, df):
        df = df.rename_axis(["date", "asset"]).reset_index()
        assets = sorted(pd.unique(df["asset"].astype(object)))
        asset_type = pd.api.types.CategoricalDtype(categories=assets, ordered=True)
        df["asset"] = df["asset"].astype(asset_type)
        df.set_index(["date", "asset"], inplace=True)
        if df.index.levels[0].tzinfo is None:
            df = df.tz_localize("UTC", level=0, copy=False)
        else:
            df = df.tz_convert("UTC", level=0, copy=False)
        df.sort_index(level=[0, 1], inplace=True)
        unique_date = df.index.get_level_values(0).unique()
        time_cat = dict(zip(unique_date, range(len(unique_date))))
        df[self.time_category] = df.index.get_level_values(0).map(time_cat)
        return df

    @classmethod
    def fetch(
        cls,
        pair,
        start_date,
        end_date,
        api_key=None,
        api_root=FXMACRODATA_API_ROOT,
        session=None,
    ):
        base, quote = _split_pair(pair)
        api_key = api_key or os.environ.get("FXMACRODATA_API_KEY")
        headers = {"X-API-Key": api_key} if api_key else {}
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "limit": 5000,
        }
        client = session or requests
        url = "{}/forex/{}/{}".format(api_root.rstrip("/"), base, quote)
        response = client.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        rows = response.json().get("data", [])

        records = []
        asset = "{}/{}".format(base, quote)
        for row in rows:
            value = float(row["val"])
            records.append(
                {
                    "date": pd.to_datetime(row["date"]),
                    "asset": asset,
                    "open": value,
                    "high": value,
                    "low": value,
                    "close": value,
                    "volume": 0.0,
                }
            )

        df = pd.DataFrame.from_records(records)
        if df.empty:
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "volume"],
                index=pd.MultiIndex.from_arrays([[], []], names=["date", "asset"]),
            )
        df["asset"] = df["asset"].astype(object)
        return df.set_index(["date", "asset"]).sort_index()
