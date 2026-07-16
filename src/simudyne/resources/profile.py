class ProfileResource:
    def __init__(self, client):
        self._client = client

    def get(self):
        return self._client._request("GET", "/profile")
    
    def usage(self):
        return self._client._request("GET", "/profile/usage")

    def downloads(self):
        """Bulk-download quota usage for the current rolling 24-hour window.

        Returns a dict with ``limit``, ``used``, ``remaining`` and
        ``window_hours``. ``limit`` and ``remaining`` are ``None`` on the
        pro and demo tiers (unlimited); on the free tier they reflect the
        account's daily download allowance. A "download" is one simulation
        group (all Monte Carlo runs of one scenario) — re-fetching a group
        already downloaded in the window, in any file format, is free.

        Example:
            >>> quota = client.profile.downloads()
            >>> print(f"{quota['used']}/{quota['limit']} used, {quota['remaining']} left")
        """
        return self._client._request("GET", "/profile/downloads")