"""
Simulation Resource for the Pulse SDK.

This module provides methods for running agent-based market simulations,
tracking job status, and retrieving results.

Workflow:
    1. Submit a simulation with run() -> returns job_id and sim_ids
    2. Track progress with get_job_status(job_id)
    3. View all past jobs with get_jobs()
    4. Once complete, retrieve results with get_job_results() or get_sim_data()
"""

import io

from simudyne.exceptions import PulseAPIError

RUN_PATH = "/simulation/run"
JOBS_PATH = "/simulation/jobs"
RESULTS_PATH = "/simulation/results"
CACHED_PATH = "/simulation/cached"
SAMPLE_PATH = "/simulation/sample"
CALIBRATE_PATH = "/calibrate"
LRM_PATH = "/simulation/lrm/run"

# Available market scenarios
SCENARIOS = {
    "normal": "No scenario injection - background agents only",
    "flash_crash": "Large rapid SELL depleting bid-side liquidity",
    "buy_panic": "Large rapid BUY depleting ask-side liquidity",
    "gradual_selloff": "Slow sustained SELL over an extended period",
    "trending_up": "Small steady BUY flow producing a persistent uptrend",
    "trending_down": "Small steady SELL flow producing a persistent downtrend",
}

# Scenario parameter defaults.
#
# MUST mirror the builder signatures in the engine's EIB/calcs/scenarios.py —
# SimulationRun backfills any omitted key from those defaults via
# inspect.signature, so a stale copy here misreports what a run will actually
# do. flash_crash/buy_panic drifted once already (22.0/0.19/500ms lingered here
# after the engine moved to 150.0/0.02/100ms), so re-check both when either side
# changes.
SCENARIO_DEFAULTS = {
    "flash_crash": {
        "impact_multiplier": 150.0,
        "order_size_ratio": 0.02,
        "order_freq": "100ms",
        "start_time": "10:30:00",
    },
    "buy_panic": {
        "impact_multiplier": 150.0,
        "order_size_ratio": 0.02,
        "order_freq": "100ms",
        "start_time": "10:30:00",
    },
    "gradual_selloff": {
        "impact_multiplier": 10.0,
        "order_size_ratio": 0.05,
        "order_freq": "5s",
        "start_time": "10:30:00",
    },
    "trending_up": {
        "impact_multiplier": 5.0,
        "order_size_ratio": 0.03,
        "order_freq": "30s",
        "start_time": "10:30:00",
    },
    "trending_down": {
        "impact_multiplier": 5.0,
        "order_size_ratio": 0.03,
        "order_freq": "30s",
        "start_time": "10:30:00",
    },
}


class SimulationResource:
    """
    Run agent-based market simulations and track job status.
    
    Example workflow:
        >>> # Submit a simulation
        >>> result = client.simulation.run(
        ...     symbol="9999.HK",
        ...     cal_date="2025-09-01",
        ...     provider="omd",
        ...     exchange="hkex_securities",
        ...     n_runs=10,
        ...     scenario="flash_crash"
        ... )
        >>> job_id = result["job_id"]
        >>> print(f"Submitted job: {job_id}")
        
        >>> # Check status
        >>> status = client.simulation.get_job_status(job_id)
        >>> print(f"Progress: {status['status_summary']}")
        >>> print(f"Complete: {status['is_complete']}")
        
        >>> # View all jobs
        >>> jobs = client.simulation.get_jobs()
        >>> print(f"Total jobs: {jobs['total']}")
    """
    
    def __init__(self, client):
        self._client = client

    def _pro_request(self, method: str, endpoint: str, **kwargs):
        """Wrapper for pro-only endpoints — passes errors through from the server."""
        return self._client._request(method, endpoint, **kwargs)

    def run(
        self,
        symbol: str,
        cal_date: str,
        provider: str,
        exchange: str,
        n_runs: int = 100,
        seed: int = 42,
        scenario: str = "normal",
        scenario_params: dict = None,
        exec_algos: list = None,
    ):
        """
        Submit a simulation run to be executed asynchronously.

        The simulation will run n_runs independent Monte Carlo samples. Each run
        produces a unique sim_id that can be used to retrieve results once complete.
        The user_id is automatically set from your API key.

        A symbol is identified by four fields: ``provider``, ``exchange``,
        ``symbol`` and ``cal_date``.

        Args:
            symbol: Trading symbol (e.g., "9999.HK", "0005.HK")
            cal_date: Calibration date in YYYY-MM-DD format (e.g., "2025-09-01")
            provider: Data provider the symbol is sourced from (e.g., "omd", "bmll")
            exchange: Exchange protocol name (e.g., "hkex_securities", "hkex_derivatives")
            n_runs: Number of independent Monte Carlo runs (default: 100)
            seed: Master random seed for reproducibility (default: 42)
            scenario: Market scenario to simulate. Options:
                - "normal": No scenario injection (default)
                - "flash_crash": Large rapid SELL depleting bid-side liquidity
                - "buy_panic": Large rapid BUY depleting ask-side liquidity
                - "gradual_selloff": Slow sustained SELL over extended period
                - "trending_up": Small steady BUY producing uptrend
                - "trending_down": Small steady SELL producing downtrend
            scenario_params: Override scenario defaults. Keys:
                - impact_multiplier (float): Total volume as multiple of resting liquidity
                - order_size_ratio (float): Child order size as fraction of liquidity
                - order_freq (str): Child order spacing (e.g., "500ms", "5s", "30s")
                - start_time (str): Time to begin orders (e.g., "10:30:00")
            exec_algos: List of execution algorithm configs. Each dict must have "type".
                Supported types: "twap", "vwap", "css"

                For TWAP/VWAP:
                - type: "twap" or "vwap" (required)
                - order_size: Total shares. Negative = BUY, positive = SELL (required)
                - horizon: Execution window in SECONDS, e.g. 3600 for 1 hour (required)
                - start_time: When to start, e.g. "09:30:00" (optional, defaults to market open)

                For CSS (Custom Static Schedule):
                - type: "css" (required)
                - orders: Dict mapping timestamps to quantities (required)

                Multiple exec_algos can be submitted in one simulation.
                
        Returns:
            dict: Submission result containing:
                - job_id (str): Unique job identifier for tracking
                - queued_sim_ids (list): List of simulation IDs that will be run
                - run_offset (int): Starting run index
                - n_runs (int): Number of runs queued
                
        Example - Basic run:
            >>> result = client.simulation.run(
            ...     symbol="9999.HK",
            ...     cal_date="2025-09-01",
            ...     provider="omd",
            ...     exchange="hkex_securities",
            ...     n_runs=10
            ... )
            >>> print(result["job_id"])

        Example - Flash crash scenario:
            >>> result = client.simulation.run(
            ...     symbol="9999.HK",
            ...     cal_date="2025-09-01",
            ...     provider="omd",
            ...     exchange="hkex_securities",
            ...     n_runs=50,
            ...     scenario="flash_crash",
            ...     scenario_params={
            ...         "start_time": "11:00:00",
            ...         "impact_multiplier": 15.0
            ...     }
            ... )

        Example - With TWAP execution algo (sell 50k shares over 1 hour):
            >>> result = client.simulation.run(
            ...     symbol="9999.HK",
            ...     cal_date="2025-09-01",
            ...     provider="omd",
            ...     exchange="hkex_securities",
            ...     n_runs=20,
            ...     exec_algos=[{
            ...         "type": "twap",
            ...         "order_size": 50000,  # positive = sell
            ...         "horizon": 3600,  # seconds (1 hour)
            ...         "start_time": "09:30:00"
            ...     }]
            ... )

        Example - With TWAP buy order:
            >>> result = client.simulation.run(
            ...     symbol="9999.HK",
            ...     cal_date="2025-09-01",
            ...     provider="omd",
            ...     exchange="hkex_securities",
            ...     n_runs=20,
            ...     exec_algos=[{
            ...         "type": "twap",
            ...         "order_size": -50000,  # negative = buy
            ...         "horizon": 3600
            ...     }]
            ... )
        """
        payload = {
            "symbol": symbol,
            "cal_date": cal_date,
            "provider": provider,
            "exchange": exchange,
            "n_runs": n_runs,
            "seed": seed,
            "scenario": scenario,
        }

        if scenario_params:
            payload["scenario_params"] = scenario_params
        if exec_algos:
            payload["exec_algos"] = self._serialize_exec_algos(exec_algos)

        return self._pro_request("POST", RUN_PATH, json=payload)

    @staticmethod
    def _serialize_exec_algos(exec_algos: list) -> list:
        """Convert pd.Series orders in CSS configs to JSON-serializable dicts."""
        result = []
        for algo in exec_algos:
            algo = dict(algo)
            if algo.get("type") == "css" and "orders" in algo:
                orders = algo["orders"]
                if hasattr(orders, "items"):
                    algo["orders"] = {str(k): int(v) for k, v in orders.items()}
            result.append(algo)
        return result

    def calibrate(
        self,
        symbol: str,
        cal_date: str,
        provider: str,
        exchange: str,
        simulations: int = None,
        batch_size: int = None,
        optimize_adj_params: bool = True,
    ):
        """
        Trigger model calibration for a symbol and date.

        Calibration runs asynchronously to fit model parameters to observed
        market data for the given symbol and date.

        A symbol is identified by four fields: ``provider``, ``exchange``,
        ``symbol`` and ``cal_date``.

        Args:
            symbol: Trading symbol (e.g., "9999.HK")
            cal_date: Calibration date in YYYY-MM-DD format
            provider: Data provider the symbol is sourced from (e.g., "omd", "bmll")
            exchange: Exchange protocol name (e.g., "hkex_securities", "hkex_derivatives")
            simulations: Number of simulations to run during calibration
            batch_size: Batch size for calibration runs
            optimize_adj_params: Whether to optimise adjustment parameters (default: True)

        Returns:
            dict: Calibration job submission result
        """
        payload: dict = {
            "symbol": symbol,
            "cal_date": cal_date,
            "provider": provider,
            "exchange": exchange,
            "optimize_adj_params": optimize_adj_params,
        }
        if simulations is not None:
            payload["simulations"] = simulations
        if batch_size is not None:
            payload["batch_size"] = batch_size
        return self._pro_request("POST", CALIBRATE_PATH, json=payload)

    def get_jobs(self):
        """
        Get all simulation jobs submitted by the authenticated user.
        
        Returns a list of jobs with their associated simulation IDs. Use this
        to find job IDs for past runs or to see what simulations are pending.
        
        Returns:
            dict: Contains:
                - jobs (list): List of job objects, each with:
                    - job_id (str): Unique job identifier
                    - sim_ids (list): List of simulation IDs in this job
                    - created_at (str): Timestamp when job was submitted
                - total (int): Total number of jobs
                
        Example:
            >>> result = client.simulation.get_jobs()
            >>> print(f"You have {result['total']} jobs")
            >>> 
            >>> for job in result["jobs"]:
            ...     print(f"Job {job['job_id']}: {len(job['sim_ids'])} simulations")
            ...     print(f"  Created: {job['created_at']}")
        """
        return self._pro_request("GET", JOBS_PATH)

    def get_job_status(self, job_id: str):
        """
        Get the status of all simulations in a job.
        
        Use this to track simulation progress. Each simulation in the job goes
        through states: queued -> running -> completed (or error).
        
        Args:
            job_id: The job ID from run() or get_jobs()
            
        Returns:
            dict: Job status containing:
                - job_id (str): The job identifier
                - total_simulations (int): Number of simulations in the job
                - status_summary (dict): Count by status (e.g., {"running": 2, "completed": 8})
                - is_complete (bool): True if all simulations are completed
                - has_errors (bool): True if any simulation failed
                - simulations (list): Individual simulation statuses with:
                    - sim_id (str): Simulation identifier
                    - status (str): Current status (queued/running/completed/error)
                    - error_message (str): Error details if failed
                    - symbol_id (str): Full symbol identifier
                    - timestamp (str): Last status update time
                    
        Example - Check if job is done:
            >>> status = client.simulation.get_job_status("2103533f15ab0893")
            >>> if status["is_complete"]:
            ...     print("All simulations finished!")
            ... else:
            ...     print(f"Progress: {status['status_summary']}")
                    
        Example - Poll for completion:
            >>> import time
            >>> 
            >>> result = client.simulation.run(symbol="9999.HK", cal_date="2025-09-01", provider="omd", exchange="hkex_securities", n_runs=10)
            >>> job_id = result["job_id"]
            >>> 
            >>> while True:
            ...     status = client.simulation.get_job_status(job_id)
            ...     print(f"Status: {status['status_summary']}")
            ...     
            ...     if status["is_complete"]:
            ...         print("Done!")
            ...         break
            ...     elif status["has_errors"]:
            ...         print("Some simulations failed")
            ...         break
            ...     
            ...     time.sleep(30)  # Check every 30 seconds
        """
        return self._pro_request("GET", f"{JOBS_PATH}/{job_id}/status")
    
    @staticmethod
    def list_scenarios():
        """
        List available market scenarios and their descriptions.
        
        Returns:
            dict: Scenario names mapped to descriptions
            
        Example:
            >>> scenarios = client.simulation.list_scenarios()
            >>> for name, desc in scenarios.items():
            ...     print(f"{name}: {desc}")
        """
        return SCENARIOS.copy()
    
    @staticmethod
    def get_scenario_defaults(scenario: str):
        """
        Get default parameters for a scenario.
        
        Args:
            scenario: Scenario name (e.g., "flash_crash")
            
        Returns:
            dict: Default parameter values, or empty dict for "normal"
            
        Example:
            >>> defaults = client.simulation.get_scenario_defaults("flash_crash")
            >>> print(defaults)
            {'impact_multiplier': 150.0, 'order_size_ratio': 0.02, ...}
        """
        return SCENARIO_DEFAULTS.get(scenario, {}).copy()

    def get_job_results(self, job_id: str):
        """
        Get aggregated results for all simulations in a job.
        
        Returns params, metrics, and available files for each completed simulation.
        
        Args:
            job_id: The job ID from run() or get_jobs()
            
        Returns:
            dict: Contains:
                - job_id (str): The job identifier
                - total_simulations (int): Total simulations in job
                - completed (int): Number of completed simulations
                - simulations (list): Per-simulation results with:
                    - sim_id (str): Simulation identifier
                    - status (str): Completion status
                    - available_files (list): Files available for download
                    - params (dict): Simulation parameters
                    - metrics (dict): Result metrics
                    
        Example:
            >>> results = client.simulation.get_job_results(job_id)
            >>> for sim in results["simulations"]:
            ...     if sim["status"] == "completed":
            ...         print(f"{sim['sim_id']}: {sim['metrics']}")
        """
        return self._pro_request("GET", f"{JOBS_PATH}/{job_id}/results")

    def get_job_logs(self, job_id: str) -> str:
        """Fetch the engine run log for one of your jobs, as plain text.

        The worker writes a diagnostic log per job — this is the thing to read
        when a run fails or finishes with nothing plottable, and the thing to
        attach when sending a problem to support@simudyne.com.

        Args:
            job_id: The job ID from run() or get_jobs()

        Returns:
            str: The log text.

        Raises:
            PulseAPIError: 404 when the job does not exist, is not yours, or
                wrote no log.

        Example:
            >>> status = client.simulation.get_job_status(job_id)
            >>> if status["has_errors"]:
            ...     print(client.simulation.get_job_logs(job_id)[:2000])
        """
        # Plain text, not JSON — go through the retrying transport directly.
        url = f"{self._client.base_url}{JOBS_PATH}/{job_id}/logs"
        response = self._client._request_with_retries("GET", url)
        return response.text

    def run_lrm(
        self,
        symbol: str,
        cal_date: str,
        provider: str,
        exchange: str,
        order_sizes: list,
        n_runs: int = 50,
        seed: int = 42,
        horizon_mins: int = 60,
        strategy: str = "vwap",
        side: str = None,
    ):
        """Run a liquidity-risk grid: market impact across a ladder of order sizes.

        One execution algo is built per entry in order_sizes, and all of them
        share a single baseline, so the cost is ``n_runs * (1 + len(order_sizes))``
        simulations rather than one baseline per size. Poll the returned job_id
        through the usual job endpoints.

        Args:
            symbol: Trading symbol (e.g. "700")
            cal_date: Calibration date in YYYY-MM-DD format
            provider: Data provider (e.g. "omd", "bmll")
            exchange: Exchange protocol (e.g. "hkex_securities")
            order_sizes: Order sizes in LOTS — one algo per entry
            n_runs: Monte Carlo runs per arm (default 50)
            seed: Random seed (default 42)
            horizon_mins: Execution horizon in minutes (default 60)
            strategy: "vwap" or "twap" (default "vwap")
            side: "buy" or "sell"; defaults to the sign of each order size

        Returns:
            dict with job_id and the queued sim_ids
        """
        payload = {
            "symbol": symbol,
            "cal_date": cal_date,
            "provider": provider,
            "exchange": exchange,
            "order_sizes": order_sizes,
            "n_runs": n_runs,
            "seed": seed,
            "horizon_mins": horizon_mins,
            "strategy": strategy,
        }
        if side is not None:
            payload["side"] = side
        return self._pro_request("POST", LRM_PATH, json=payload)

    def list_sim_files(self, sim_id: str):
        """
        List available files for a specific simulation.

        Args:
            sim_id: The simulation ID

        Returns:
            dict: Contains:
                - sim_id (str): The simulation identifier
                - files (list): List of available filenames
                - has_sim_data (bool): Whether sim_data.parquet exists
                - has_params (bool): Whether params.json exists
                - has_results (bool): Whether results.json exists
                - has_mid_price (bool): Whether mid_price_by_min.parquet exists
                - has_l2_by_second (bool): Whether l2_by_second.parquet exists
                - has_exec_schedule (bool): Whether exec_schedule.parquet exists
                - has_schedule_by_min (bool): Whether schedule_by_min.parquet exists

        Example:
            >>> files = client.simulation.list_sim_files(sim_id)
            >>> print(f"Available: {files['files']}")
        """
        return self._client._request("GET", f"{RESULTS_PATH}/{sim_id}/files")

    def get_sim_params(self, sim_id: str):
        """
        Get simulation parameters for a specific simulation.
        
        Args:
            sim_id: The simulation ID
            
        Returns:
            dict: Simulation parameters including:
                - sim_id (str)
                - calibration_params (dict)
                - scenario_params (dict)
                - exec_algo_params (dict)
                - sim_params (dict)
                
        Example:
            >>> params = client.simulation.get_sim_params(sim_id)
            >>> print(f"Scenario: {params['scenario_params']['scenario_name']}")
        """
        return self._client._request("GET", f"{RESULTS_PATH}/{sim_id}/params")

    def get_sim_metrics(self, sim_id: str):
        """
        Get result metrics for a specific simulation.
        
        Args:
            sim_id: The simulation ID
            
        Returns:
            dict: Simulation result metrics
            
        Example:
            >>> metrics = client.simulation.get_sim_metrics(sim_id)
            >>> print(metrics)
        """
        return self._client._request("GET", f"{RESULTS_PATH}/{sim_id}/metrics")

    def get_sim_data(self, sim_id: str, filename: str = "sim_data.parquet"):
        """
        Download simulation data as a Polars DataFrame.

        Free-tier quota: downloading from a cached simulation group you haven't
        downloaded before consumes one unit of the daily allowance (HTTP 429
        once exhausted). Groups you've already downloaded — via this method,
        the bulk ZIP, or the web explorer — stay free forever, any run or file
        format. Your own job runs are never charged. See
        ``client.profile.downloads()``.

        Args:
            sim_id: The simulation ID
            filename: File to download. Options:
                - "sim_data.parquet": Full simulation output (LOB + orders)
                - "mid_price_by_min.parquet": Mid-price by minute
                - "l2_by_second.parquet": L2 order book (10 levels) sampled per second
                - "exec_schedule.parquet": Execution schedule (if algo)
                - "schedule_by_min.parquet": Algo schedule by minute (if algo)
                - "exec_results.parquet": Execution cost metrics (if algo)

        Returns:
            polars.DataFrame: The simulation data
            
        Example:
            >>> df = client.simulation.get_sim_data(sim_id)
            >>> print(df.shape)
            >>> print(df.head())
            
            >>> # Get mid-price data
            >>> mid_df = client.simulation.get_sim_data(sim_id, "mid_price_by_min.parquet")
        """
        import polars as pl
        
        url = f"{self._client.base_url}{RESULTS_PATH}/{sim_id}/data/{filename}"
        response = self._client.session.get(url)

        if not response.ok:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise PulseAPIError(response.status_code, detail)

        return pl.read_parquet(io.BytesIO(response.content))

    def list_cached(
        self,
        symbol: str = None,
        date: str = None,
        scenario: str = None,
    ):
        """
        List cached baseline simulations available to free tier users.
        
        Returns aggregated simulation metadata for baseline (non-exec algo) simulations.
        Use the returned sim_id to retrieve data via get_sim_data(), get_sim_params(), etc.
        
        Free tier users can only access baseline simulations - no execution algorithms.
        
        Args:
            symbol: Filter by symbol (e.g., "700.HK", "9999.HK")
            date: Filter by date (e.g., "2025-09-02")
            scenario: Filter by scenario (e.g., "normal", "flash_crash")
            
        Returns:
            dict: Contains:
                - simulations (list): List of cached simulation groups, each with:
                    - example_sim_id (str): A sim_id from this group (use with get_sim_data)
                    - symbol (str): Trading symbol
                    - date (str): Calibration date
                    - scenario (str): Scenario name
                    - n_runs (int): Number of available runs
                    - cal_hash (str): Calibration parameter hash
                    - sim_hash (str): Simulation parameter hash
                    - time_range (str): Trading time range
                - total (int): Number of unique symbol/date/scenario combinations
                
        Example - List all cached simulations:
            >>> cached = client.simulation.list_cached()
            >>> print(f"Found {cached['total']} cached simulation groups")
            >>> 
            >>> for sim in cached["simulations"]:
            ...     print(f"{sim['symbol']} {sim['date']} {sim['scenario']}: {sim['n_runs']} runs")
            ...     print(f"  Use sim_id: {sim['example_sim_id']}")
            
        Example - Filter by symbol:
            >>> cached = client.simulation.list_cached(symbol="700.HK")
            >>> for sim in cached["simulations"]:
            ...     print(f"{sim['date']} {sim['scenario']}: {sim['n_runs']} runs")
            
        Example - Get data from a cached simulation:
            >>> cached = client.simulation.list_cached(symbol="9999.HK", scenario="flash_crash")
            >>> if cached["simulations"]:
            ...     sim_id = cached["simulations"][0]["example_sim_id"]
            ...     df = client.simulation.get_sim_data(sim_id)
            ...     print(df.head())
        """
        params = {}
        if symbol:
            params["symbol"] = symbol
        if date:
            params["date"] = date
        if scenario:
            params["scenario"] = scenario
        
        return self._client._request("GET", CACHED_PATH, params=params)

    def get_sample_data(self, path: str = "simulation_sample.zip"):
        """
        Download a sample dataset for 700.HK — 5 Monte Carlo runs, no configuration needed.

        The server picks the best available scenario (normal preferred) and returns
        sim_data.parquet and mid_price_by_min.parquet for each run as a ZIP.

        Args:
            path: File path to save the ZIP to (default: "simulation_sample.zip").
                  Pass None to return raw bytes instead.

        Returns:
            bytes: ZIP file content if path is None, otherwise None (file written to disk).

        Example - Save to disk:
            >>> client.simulation.get_sample_data()
            # writes simulation_sample.zip to current directory

        Example - Load directly into DataFrames:
            >>> import zipfile, io
            >>> import polars as pl
            >>>
            >>> data = client.simulation.get_sample_data(path=None)
            >>> with zipfile.ZipFile(io.BytesIO(data)) as zf:
            ...     for name in zf.namelist():
            ...         df = pl.read_parquet(io.BytesIO(zf.read(name)))
            ...         print(f"{name}: {df.shape}")
        """
        url = f"{self._client.base_url}{SAMPLE_PATH}"
        response = self._client.session.get(url)

        if not response.ok:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise PulseAPIError(response.status_code, detail)

        if path is None:
            return response.content

        with open(path, "wb") as f:
            f.write(response.content)

    def get_bulk_data(
        self,
        sim_ids: list,
        include_sim_data: bool = True,
        include_mid_price: bool = False,
        include_l2_by_second: bool = False,
    ):
        """
        Download data for multiple simulations as a ZIP file.

        Args:
            sim_ids: List of simulation IDs to download
            include_sim_data: Include sim_data.parquet files (default: True)
            include_mid_price: Include mid_price_by_min.parquet files (default: False)
            include_l2_by_second: Include l2_by_second.parquet files (default: False)

        Returns:
            bytes: ZIP file content containing requested parquet files

        Free-tier quota: at most N NEW simulation groups per rolling 24-hour
        window (default 3). One unit is consumed per distinct group (all Monte
        Carlo runs of one scenario) — not per call, run, or file format — and
        membership is permanent: a group you've downloaded before is free to
        re-fetch forever. The API returns HTTP 429 (charging nothing) when a
        request would exceed the allowance. Check your quota and owned groups
        with ``client.profile.downloads()``. Pro and demo tiers are unlimited.

        Example - Download sim_data for multiple sims:
            >>> cached = client.simulation.list_cached(symbol="700.HK")
            >>> sim_ids = [s["example_sim_id"] for s in cached["simulations"]]
            >>>
            >>> zip_bytes = client.simulation.get_bulk_data(sim_ids)
            >>> with open("simulation_data.zip", "wb") as f:
            ...     f.write(zip_bytes)

        Example - Download with L2 order book data:
            >>> zip_bytes = client.simulation.get_bulk_data(
            ...     sim_ids=["sim_id_1", "sim_id_2"],
            ...     include_sim_data=True,
            ...     include_l2_by_second=True
            ... )

        Example - Extract and load into DataFrames:
            >>> import zipfile
            >>> import polars as pl
            >>>
            >>> zip_bytes = client.simulation.get_bulk_data(sim_ids)
            >>> with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            ...     for name in zf.namelist():
            ...         if name.endswith('.parquet'):
            ...             df = pl.read_parquet(io.BytesIO(zf.read(name)))
            ...             print(f"{name}: {df.shape}")
        """
        payload = {
            "sim_ids": sim_ids,
            "include_sim_data": include_sim_data,
            "include_mid_price": include_mid_price,
            "include_l2_by_second": include_l2_by_second,
        }
        
        url = f"{self._client.base_url}{RESULTS_PATH}/bulk"
        response = self._client.session.post(url, json=payload)

        if not response.ok:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise PulseAPIError(response.status_code, detail)

        return response.content
