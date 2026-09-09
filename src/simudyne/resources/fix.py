"""
FIX Resource for the Pulse SDK.

Pulse simulations can be consumed over the FIX protocol by a market-data
session instead of the REST download endpoints. The FIX connection itself is
provisioned per organisation (see the FIX docs page); this resource covers
what the SDK can usefully do about it — reporting what your account has run
over FIX.
"""

USAGE_PATH = "/fix/usage"


class FixResource:
    def __init__(self, client):
        self._client = client

    def usage(self) -> dict:
        """FIX simulation statistics: what was run over FIX, and how often.

        Returns:
            dict with ``total_runs``, ``simulated_seconds``, and ``runs`` — one
            entry per distinct configuration, each with its ``symbol``,
            ``cal_date``, ``scenario`` and ``runs`` count.

        Example:
            >>> usage = client.fix.usage()
            >>> print(f"{usage['total_runs']} FIX runs")
        """
        return self._client._request("GET", USAGE_PATH)
