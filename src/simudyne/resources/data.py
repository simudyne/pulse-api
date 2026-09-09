AVAILABLE_SYMBOLS_PATH = "/data/available-symbols"


class DataResource:
    def __init__(self, client):
        self._client = client

    def get_available_symbols(
        self,
        symbol: str | None = None,
        exchange: str | None = None,
        provider: str | None = None,
        date: str | None = None,
        q: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ):
        """List calibrated instruments and the dates available for each.

        All arguments are optional filters; with none passed the whole catalog
        comes back, as before.

        Args:
            symbol: Exact symbol, e.g. "700.HK".
            exchange: Exchange protocol, e.g. "hkex_securities".
            provider: Data provider, e.g. "omd" or "bmll".
            date: Calibration date "YYYY-MM-DD". Keeps only instruments
                  calibrated on that date, and narrows each instrument's
                  available_dates to it.
            q: Case-insensitive substring match over ticker and company name.
            limit: Max instruments to return.
            offset: Instruments to skip (for paging alongside limit).

        Returns:
            list of instrument dicts, each with available_dates.
        """
        params = {
            k: v for k, v in {
                "symbol": symbol,
                "exchange": exchange,
                "provider": provider,
                "date": date,
                "q": q,
                "limit": limit,
                "offset": offset,
            }.items() if v is not None
        }
        return self._client._request("GET", AVAILABLE_SYMBOLS_PATH, params=params or None)
