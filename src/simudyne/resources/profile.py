class ProfileResource:
    def __init__(self, client):
        self._client = client

    def get(self):
        return self._client._request("GET", "/profile")
    
    def usage(self):
        return self._client._request("GET", "/profile/usage")

    def downloads(self):
        """Download quota usage for the current rolling 24-hour window.

        Returns a dict with ``limit``, ``used``, ``remaining``,
        ``window_hours`` and ``downloaded_groups``. ``limit`` and
        ``remaining`` are ``None`` on the pro and demo tiers (unlimited); on
        the free tier they reflect the account's daily download allowance.

        A "download" is one simulation group (all Monte Carlo runs of one
        scenario). ``used`` counts NEW groups added in the window;
        ``downloaded_groups`` lists every group you have ever downloaded —
        membership is permanent, so those are free to re-fetch forever in any
        run or file format.

        Example:
            >>> quota = client.profile.downloads()
            >>> print(f"{quota['used']}/{quota['limit']} used, {quota['remaining']} left")
            >>> print(f"{len(quota['downloaded_groups'])} groups owned")
        """
        return self._client._request("GET", "/profile/downloads")