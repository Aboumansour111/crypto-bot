from typing import Any

import requests

from app.config.settings import settings


class BitpinClient:
    def __init__(self):
        self.base_url = settings.bitpin_base_url

        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "crypto-bot/0.1",
        })

    def _get(
        self,
        path: str,
        params: dict | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"

        response = self.session.get(
            url,
            params=params,
            timeout=settings.timeout,
        )

        response.raise_for_status()
        return response.json()

    def markets(self) -> list:
        data = self._get(settings.markets_path)

        if not isinstance(data, list):
            raise ValueError(
                "Bitpin markets response is not a list"
            )

        return data

    def get_bars(
        self,
        symbol: str,
        resolution: str,
        from_ts: int,
        to_ts: int,
    ) -> list:
        data = self._get(
            settings.bars_path,
            params={
                "symbol": symbol,
                "res": resolution,
                "from": from_ts,
                "to": to_ts,
            },
        )

        if not isinstance(data, list):
            raise ValueError(
                f"Bitpin bars response is not a list: {symbol} {resolution}"
            )

        return data
