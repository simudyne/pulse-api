"""
Foundation Models Resource for the Pulse SDK.

A foundation-model (FM) run generates limit order book activity by continuing
from real market data rather than simulating agents. The platform slices the
model's required context out of the chosen market's data, runs inference, and
writes the output using the same conventions as an agent-based run — so the
ordinary simulation results and download endpoints work unchanged.

Workflow:
    1. Discover models with models() — each entry lists the markets it
       supports and the model_args it accepts
    2. Find a promptable symbol/date with available_data(model_id=...)
    3. Submit inference with run() -> returns job_id and sim_ids
    4. Poll job_status(job_id) until it reaches a TERMINAL_STATUSES value;
       read job_logs(job_id) when it failed
    5. Download with client.simulation.get_sim_data(sim_id) — an FM sim_id is
       an ordinary sim_id

The output file contains the model's prompt context as well as its generated
frames: the leading rows of sim_data.parquet are real market data. The split
is recorded in the parquet file-level metadata (``pulse_fm.n_historical``,
``pulse_fm.n_generated``, ``pulse_fm.segments``) — drop the context rows
before computing statistics on the generated activity.
"""

MODELS_PATH = "/fm/models"
AVAILABLE_DATA_PATH = "/fm/available-data"
RUN_PATH = "/fm/run"
LIVE_PATH = "/fm/live"
JOBS_PATH = "/fm/jobs"

#: The only statuses a job never leaves. Everything else (queued,
#: provisioning, starting, running) means "keep polling".
TERMINAL_STATUSES = {"complete", "failed"}


class FmResource:
    def __init__(self, client):
        self._client = client

    def models(self) -> dict:
        """Active foundation models in this environment.

        The pre-run discovery call: each entry carries the model's id and
        version, the markets its ``supported_data`` declares (empty = any),
        ``min_prompt_rows``, and the ``model_args`` descriptors for the knobs
        run() will accept. Pro tier.

        Returns:
            dict with a ``models`` list.
        """
        return self._client._request("GET", MODELS_PATH)

    def available_data(
        self,
        model_id: str = None,
        symbol: str = None,
        q: str = None,
        provider: str = None,
        exchange: str = None,
        date: str = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """What a foundation model can be prompted with: the raw-data registry.

        An FM prompt is the first rows of a REAL trading day, not a
        calibration, so this searches the raw-data catalog rather than the
        calibrated list at data.get_available_symbols(). Passing ``model_id``
        restricts the result to the (provider, exchange) markets that model's
        ``supported_data`` declares — exactly what run() will accept.

        Args:
            model_id: Registered model (see models()). Unknown id -> 404.
            symbol: Exact symbol, e.g. "TSCO" or "700".
            q: Case-insensitive substring match over the symbol.
            provider: Data provider, e.g. "bmll".
            exchange: Protocol, e.g. "lse" or "hkex_securities".
            date: Trading date YYYY-MM-DD; keeps only symbols with data on it,
                and only that date.
            limit: Max symbols to return (default 50, max 200).
            offset: Symbols to skip, for paging.

        Returns:
            dict with ``symbols`` (each with its provider, exchange and dates)
            and ``total``, paged by symbol identity.
        """
        params = {"limit": limit, "offset": offset}
        for key, value in (
            ("model_id", model_id), ("symbol", symbol), ("q", q),
            ("provider", provider), ("exchange", exchange), ("date", date),
        ):
            if value is not None:
                params[key] = value
        return self._client._request("GET", AVAILABLE_DATA_PATH, params=params)

    def run(
        self,
        model_id: str,
        symbol: str,
        cal_date: str,
        provider: str,
        exchange: str,
        duration_minutes: float = None,
        horizon: int = None,
        n_runs: int = 1,
        seed: int = 42,
        model_args: dict = None,
        device: str = None,
        exec_algos: list = None,
    ) -> dict:
        """Submit a foundation-model inference job. Pro tier.

        Args:
            model_id: A model from models().
            symbol: Symbol whose real data becomes the prompt context.
            cal_date: Trading date of the prompt, YYYY-MM-DD.
            provider: Data provider, e.g. "bmll".
            exchange: Exchange protocol, e.g. "hkex_securities".
            duration_minutes: Sim horizon as wall-clock minutes measured from
                the first row of the context. The resulting frame count is
                reported in the run's output rather than requested up front.
            horizon: Raw frame count — the older form; applies only when
                duration_minutes is unset.
            n_runs: Monte Carlo runs, 1-8 (per-run seeds derived from ``seed``
                exactly as the ABM derives them).
            seed: Random seed (default 42).
            model_args: Overrides for the model's declared knobs (see
                models()); unknown or out-of-range keys are rejected with 400.
            device: "cpu" or "gpu"; None uses the model's default.
            exec_algos: Execution algorithms, the ABM's config shape. At most
                one per job; market runs only.

        Returns:
            dict with job_id, the model version, and the queued sim_ids.
        """
        payload = {
            "model_id": model_id,
            "symbol": symbol,
            "cal_date": cal_date,
            "provider": provider,
            "exchange": exchange,
            "n_runs": n_runs,
            "seed": seed,
        }
        if duration_minutes is not None:
            payload["duration_minutes"] = duration_minutes
        if horizon is not None:
            payload["horizon"] = horizon
        if model_args is not None:
            payload["model_args"] = model_args
        if device is not None:
            payload["device"] = device
        if exec_algos is not None:
            payload["exec_algos"] = exec_algos
        return self._client._request("POST", RUN_PATH, json=payload)

    def live(
        self,
        model_id: str,
        horizon: int = None,
        seed: int = 42,
        model_args: dict = None,
    ) -> dict:
        """Start a live streaming session instead of a batch job. Pro tier.

        Returns:
            dict with ``token`` (used to connect to the live chart),
            ``job_id`` and ``model_id``.
        """
        payload = {"model_id": model_id, "seed": seed}
        if horizon is not None:
            payload["horizon"] = horizon
        if model_args is not None:
            payload["model_args"] = model_args
        return self._client._request("POST", LIVE_PATH, json=payload)

    def job_status(self, job_id: str) -> dict:
        """Foundation-model job status.

        Returns:
            dict with job_id, ``status``, ``message``, ``detail``,
            ``started_at`` and ``completed_at``. ``status`` is one of queued,
            provisioning, starting, running, complete or failed — only the
            last two are terminal (see TERMINAL_STATUSES), so poll until one
            of those appears. ``message`` is the human label for the state and
            ``detail`` says what the run is waiting on (a GPU stockout reads
            as the scheduler's own reason).
        """
        return self._client._request("GET", f"{JOBS_PATH}/{job_id}/status")

    def job_logs(self, job_id: str) -> dict:
        """Foundation-model job pod logs.

        Returns:
            dict with ``logs`` — the thing to read when a job failed.
        """
        return self._client._request("GET", f"{JOBS_PATH}/{job_id}/logs")
