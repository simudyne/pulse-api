"""
Validation Resource for the Pulse SDK.

This module provides methods for validating simulation quality by comparing
simulated LOB data against historical data using distributional metrics,
impact response analysis, stylised facts, and the MIND/FID inception distances
on DeepLOB embeddings.

Workflow:
    1. Submit a validation job with run() -> returns job_id
    2. Poll status with get_job(job_id) or use run_pipeline() for blocking
    3. View results including distances and plots
    4. List past jobs with list_jobs()

For the inception distances alone, inception_distances() is a one-call
shortcut that returns just the MIND and FID scores.

Tri-state run flags
-------------------
``run_metrics`` / ``run_impact`` / ``run_stylised_facts`` / ``plot_data``
default to ``None``, meaning "use the default for my tier" — resolved
server-side. Demo turns everything on; other tiers get metrics and stylised
facts. Only flags you set explicitly are sent, so a demo key is not silently
opted out of the passes it is entitled to. Pass ``False`` to skip an expensive
pass, or ``True`` to force one on.

``run_inception_distances`` is the exception: it defaults to ``True``, so MIND
and FID are computed unless you opt out. It maps to the API's ``run_fid``
config field, which gates both metrics because they share one DeepLOB
embedding pass. As of pulse-api-pod 1.56.0 the scores are returned to every
validation tier; on older API deployments they reach the demo tier only.
"""

import base64
import time


RUN_PATH = "/validation/run"
JOBS_PATH = "/validation/jobs"

#: Flags the API resolves from the caller's tier when left unset.
_TRI_STATE_FLAGS = (
    "run_metrics",
    "run_impact",
    "run_stylised_facts",
    "plot_data",
)

#: SDK name -> API config field. The API kept ``run_fid`` for compatibility;
#: the SDK spells out what it actually gates.
_INCEPTION_WIRE_FIELD = "run_fid"


class ValidationResource:
    def __init__(self, client):
        self._client = client

    def run(
        self,
        symbol: str,
        date: str,
        sim_ids: list[str],
        ticksize: float = 1.0,
        run_metrics: bool = None,
        run_impact: bool = None,
        run_inception_distances: bool = True,
        run_stylised_facts: bool = None,
        plot_data: bool = None,
        n_levels: int = 10,
        l2_only: bool = False,
        provider: str = None,
        exchange: str = None,
    ) -> dict:
        """Submit a validation job.

        Compares simulation output against historical market data using
        distributional distance metrics (L1, Wasserstein), impact response
        curves, Cont stylised facts, and the MIND/FID inception distances.

        Historical data is fetched automatically based on symbol and date.
        Simulation data is fetched from each sim_id's sim_data.parquet.

        Args:
            symbol: Trading symbol (e.g. "700.HK")
            date: Calibration date in YYYY-MM-DD format (e.g. "2025-09-01")
            sim_ids: List of simulation IDs to validate (max 25)
            ticksize: Tick size for the symbol
            run_metrics: Compute L1/Wasserstein distributional distances
                (None = tier default)
            run_impact: Compute impact response curves (None = tier default).
                Only computed when plot_data is on — it has no verdict-only form.
            run_inception_distances: Compute MIND *and* FID on DeepLOB
                embeddings (default True). One flag gates both — they share a
                single embedding pass. Sent as the API's ``run_fid`` field.
                Scores are returned to every validation tier (API >= 1.56.0;
                demo-only before that).
            run_stylised_facts: Compute the 11 Cont stylised facts
                (None = tier default)
            plot_data: Store the raw data behind every plot — distribution
                histograms, full stylised-fact payloads, impact curves.
                **Demo tier only**; an explicit True from any other tier is
                rejected with 403. When off, the job returns distances and the
                per-fact verdicts only.
            n_levels: Number of L2 book levels to use. The inception distances
                need all 10.
            l2_only: Restrict to metrics that need only bid/ask price+size.
                Disables the impact response.
            provider: Data provider (e.g. "omd"). Defaults to the prefix parsed
                from sim_ids[0].
            exchange: Exchange protocol (e.g. "hkex_securities"). Defaults to
                the prefix parsed from sim_ids[0].

        Returns:
            dict with job_id, status, message
        """
        config = {
            "n_levels": n_levels,
            "l2_only": l2_only,
            _INCEPTION_WIRE_FIELD: run_inception_distances,
        }
        for flag, value in zip(
            _TRI_STATE_FLAGS,
            (run_metrics, run_impact, run_stylised_facts, plot_data),
        ):
            # Omitted rather than sent as None: the API reads absence as "use my
            # tier's default", and sending an explicit null would not do that.
            if value is not None:
                config[flag] = value

        payload = {
            "symbol": symbol,
            "date": date,
            "sim_ids": sim_ids,
            "ticksize": ticksize,
            "config": config,
        }
        if provider is not None:
            payload["provider"] = provider
        if exchange is not None:
            payload["exchange"] = exchange

        return self._client._request("POST", RUN_PATH, json=payload)

    def get_job(self, job_id: str) -> dict:
        """Get validation job status and results.

        Args:
            job_id: The job ID returned by run()

        Returns:
            dict with:
            - status: "pending", "running", "completed", or "failed"
            - distances: {metric: {l1: [...], w: [...]}} — every entitled tier
            - stylised_fact_verdicts: {fact: {historical: bool | None,
              simulated: [bool | None, ...]}} — every entitled tier
            - mind_scores: one Monge Inception Distance per sim run, in sim_ids
              order; None where a run could not be embedded. Every validation
              tier (API >= 1.56.0)
            - fid_scores: one Frechet Inception Distance per sim run, same
              ordering and tier rule. Since pulse-check 1.8.0 this is the
              embedding-space FID — not comparable with values stored by older
              jobs
            - distributions / impact_response / stylised_facts: the full
              historical-derived payloads. Demo tier, plot_data jobs only
            - plots: {distributions: [...], distances: [...],
              impact_response: [...]} of {name, content_base64}
            - metadata: dict with run parameters
            - error: error message (when failed)

        Lower MIND/FID = closer to the historical day. Neither is meaningful as
        a bare number — see inception_distances() for how to read them.
        """
        return self._client._request("GET", f"{JOBS_PATH}/{job_id}")

    def list_jobs(self, limit: int = 50) -> dict:
        """List validation jobs for the current user.

        Args:
            limit: Max number of jobs to return (default 50, max 200)

        Returns:
            dict with jobs list and total count
        """
        return self._client._request("GET", JOBS_PATH, params={"limit": limit})

    def run_pipeline(
        self,
        symbol: str,
        date: str,
        sim_ids: list[str],
        ticksize: float = 1.0,
        run_metrics: bool = None,
        run_impact: bool = None,
        run_inception_distances: bool = True,
        run_stylised_facts: bool = None,
        plot_data: bool = None,
        n_levels: int = 10,
        l2_only: bool = False,
        provider: str = None,
        exchange: str = None,
        poll_interval: float = 3.0,
        timeout: float = 600.0,
    ) -> dict:
        """Submit a validation job and block until it completes.

        Combines run() + polling get_job() into a single call.
        Prints progress to stderr.

        Args:
            symbol: Trading symbol (e.g. "700.HK")
            date: Calibration date in YYYY-MM-DD format
            sim_ids: List of simulation IDs to validate (max 25)
            ticksize: Tick size for the symbol
            run_metrics: Compute L1/Wasserstein distances (None = tier default)
            run_impact: Compute impact response curves (None = tier default)
            run_inception_distances: Compute MIND *and* FID on DeepLOB
                embeddings (default True) — one flag gates both
            run_stylised_facts: Compute the Cont stylised facts
                (None = tier default)
            plot_data: Store the raw plottable data (demo tier only)
            n_levels: Number of L2 book levels to use
            l2_only: Restrict to L2-only metrics
            provider: Data provider; defaults to the sim_id prefix
            exchange: Exchange protocol; defaults to the sim_id prefix
            poll_interval: Seconds between status checks (default 3)
            timeout: Max seconds to wait (default 600)

        Returns:
            dict with full validation results — see get_job() for the fields

        Raises:
            RuntimeError: If the validation job fails
            TimeoutError: If the job doesn't complete within timeout
        """
        import sys

        job = self.run(
            symbol=symbol,
            date=date,
            sim_ids=sim_ids,
            ticksize=ticksize,
            run_metrics=run_metrics,
            run_impact=run_impact,
            run_inception_distances=run_inception_distances,
            run_stylised_facts=run_stylised_facts,
            plot_data=plot_data,
            n_levels=n_levels,
            l2_only=l2_only,
            provider=provider,
            exchange=exchange,
        )
        job_id = job["job_id"]
        print(f"Validation job submitted: {job_id}", file=sys.stderr)

        start = time.time()
        while True:
            result = self.get_job(job_id)
            status = result["status"]

            if status == "completed":
                elapsed = time.time() - start
                print(f"Completed in {elapsed:.1f}s", file=sys.stderr)
                return result
            elif status == "failed":
                raise RuntimeError(f"Validation failed: {result.get('error')}")

            if time.time() - start > timeout:
                raise TimeoutError(
                    f"Validation job {job_id} timed out after {timeout}s"
                )

            time.sleep(poll_interval)

    def inception_distances(
        self,
        symbol: str,
        date: str,
        sim_ids: list[str],
        ticksize: float = 1.0,
        n_levels: int = 10,
        provider: str = None,
        exchange: str = None,
        poll_interval: float = 3.0,
        timeout: float = 600.0,
    ) -> dict:
        """MIND and FID for each simulation, and nothing else.

        A focused shortcut over run_pipeline(): keeps the inception distances
        on and forces every other pass off, so the job does one DeepLOB embedding pass
        and skips the metric, impact and stylised-fact work.

        Both metrics are computed on 96-dim DeepLOB embeddings of 100-row L2
        windows and need 10 book levels in the data.

        Args:
            symbol: Trading symbol (e.g. "700.HK")
            date: Calibration date in YYYY-MM-DD format
            sim_ids: List of simulation IDs to score (max 25)
            ticksize: Tick size for the symbol
            n_levels: Number of L2 book levels (10 required for the embeddings)
            provider: Data provider; defaults to the sim_id prefix
            exchange: Exchange protocol; defaults to the sim_id prefix
            poll_interval: Seconds between status checks
            timeout: Max seconds to wait

        Returns:
            dict with:
            - mind: list of MIND scores, one per sim_id, None where a run could
              not be embedded
            - fid: list of FID scores, same ordering and convention
            - sim_ids: the ids, so scores can be zipped back to their runs
            - job_id: the underlying validation job

        Raises:
            RuntimeError: If the job fails, or if the scores come back empty —
                which means the pipeline skipped them (missing torch, fewer
                than 10 levels, unreachable checkpoint), or the API predates
                1.56.0 and the key is not demo tier; both are silent in the
                raw response.

        Interpreting the scores:
            Lower = closer to the historical day, but neither number means
            anything on its own — only relative to a noise floor. Score a
            real-vs-real control too (two slices of genuine market data) and
            read a generator as a multiple of that floor. ~1x means the metric
            cannot separate it from ordinary intraday variation.
        """
        result = self.run_pipeline(
            symbol=symbol,
            date=date,
            sim_ids=sim_ids,
            ticksize=ticksize,
            run_inception_distances=True,
            run_metrics=False,
            run_impact=False,
            run_stylised_facts=False,
            n_levels=n_levels,
            provider=provider,
            exchange=exchange,
            poll_interval=poll_interval,
            timeout=timeout,
        )

        mind = result.get("mind_scores")
        fid = result.get("fid_scores")
        if not mind and not fid:
            raise RuntimeError(
                "no inception distances in the response. Either the pipeline "
                "skipped them (torch missing, fewer than 10 book levels, or "
                "the DeepLOB checkpoint unreachable), or the API predates "
                "1.56.0 and this key is not demo tier."
            )

        return {
            "mind": mind,
            "fid": fid,
            "sim_ids": list(sim_ids),
            "job_id": result.get("job_id"),
        }

    def display_plots(self, result: dict) -> "PlotDisplay":
        """Return a PlotDisplay object for displaying validation plots.

        Usage:
            plots = client.validation.display_plots(result)
            plots.distributions()    # show distribution histograms
            plots.distances()        # show spider plots
            plots.impact_response()  # show impact response plots

        Args:
            result: The result dict from run_pipeline() or get_job()
        """
        return PlotDisplay(result)


class PlotDisplay:
    """Displays categorized validation plots inline in Jupyter notebooks."""

    def __init__(self, result: dict):
        plots = result.get("plots") or {}
        self._distributions = plots.get("distributions", [])
        self._distances = plots.get("distances", [])
        self._impact_response = plots.get("impact_response", [])

    def _show(self, plot_list, title):
        from IPython.display import display, Image

        if not plot_list:
            print(f"No {title} plots available")
            return

        for plot in plot_list:
            print(f"\n--- {plot['name']} ---")
            display(Image(data=base64.b64decode(plot["content_base64"])))

    def distributions(self):
        """Display distribution histogram plots."""
        self._show(self._distributions, "distribution")

    def distances(self):
        """Display spider plots (L1 and Wasserstein distances)."""
        self._show(self._distances, "distance")

    def impact_response(self):
        """Display impact response plots."""
        self._show(self._impact_response, "impact response")

    def all(self):
        """Display all plots."""
        self.distances()
        self.distributions()
        self.impact_response()
