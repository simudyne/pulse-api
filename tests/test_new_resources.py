"""Payload tests for the 0.8.0 surface: validation.run_upload, the fm and fix
resources, and simulation.get_job_logs / run_lrm.

No network — same recorder pattern as test_validation.py. These pin the wire
contract the docs describe: field names, which flags are omitted when unset,
and the client-side sim_files limit that must fail before any bytes move.
"""

import json

import pytest

from simudyne.resources.fix import FixResource
from simudyne.resources.fm import FmResource, TERMINAL_STATUSES
from simudyne.resources.simulation import SimulationResource
from simudyne.resources.validation import ValidationResource


class FakeClient:
    def __init__(self, responses=None):
        self.calls = []
        self._responses = list(responses or [])

    def _request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return self._responses.pop(0) if self._responses else {}


class TestRunUpload:
    def test_rejects_empty_before_any_request(self):
        client = FakeClient()
        with pytest.raises(ValueError, match="empty"):
            ValidationResource(client).run_upload(
                "700.HK", "2025-09-01", "omd", "hkex_securities", sim_files=[]
            )
        assert client.calls == []

    def test_rejects_more_than_25_before_any_request(self):
        client = FakeClient()
        files = [(f"sim_{i}.parquet", b"x") for i in range(26)]
        with pytest.raises(ValueError, match="25"):
            ValidationResource(client).run_upload(
                "700.HK", "2025-09-01", "omd", "hkex_securities", sim_files=files
            )
        assert client.calls == []

    def test_multipart_payload_shape(self):
        client = FakeClient([{"job_id": "v1", "status": "pending"}])
        ValidationResource(client).run_upload(
            "700.HK", "2025-09-01", "omd", "hkex_securities",
            sim_files=[("sim_0000.parquet", b"PARQ")],
            ticksize=0.5,
            run_metrics=False,
        )
        method, path, kwargs = client.calls[0]
        assert (method, path) == ("POST", "/validation/run/upload")
        data = kwargs["data"]
        assert data["provider"] == "omd" and data["exchange"] == "hkex_securities"
        assert data["ticksize"] == "0.5"
        config = json.loads(data["config"])
        # explicit False sent; unset tri-state flags omitted (tier default)
        assert config["run_metrics"] is False
        for flag in ("run_impact", "run_stylised_facts", "plot_data"):
            assert flag not in config
        assert config["run_fid"] is True
        [(field, (filename, content, mime))] = kwargs["files"]
        assert field == "sim_files" and filename == "sim_0000.parquet"
        assert content == b"PARQ" and mime == "application/octet-stream"

    def test_reads_paths_from_disk(self, tmp_path):
        p = tmp_path / "sim_0001.parquet"
        p.write_bytes(b"BYTES")
        client = FakeClient([{}])
        ValidationResource(client).run_upload(
            "700.HK", "2025-09-01", "omd", "hkex_securities", sim_files=[p]
        )
        [(_, (filename, content, _))] = client.calls[0][2]["files"]
        assert filename == "sim_0001.parquet" and content == b"BYTES"


class TestFmResource:
    def test_terminal_statuses_are_the_two_documented(self):
        assert TERMINAL_STATUSES == {"complete", "failed"}

    def test_models_and_status_paths(self):
        client = FakeClient([{}, {}])
        fm = FmResource(client)
        fm.models()
        fm.job_status("j1")
        assert client.calls[0][:2] == ("GET", "/fm/models")
        assert client.calls[1][:2] == ("GET", "/fm/jobs/j1/status")

    def test_available_data_omits_unset_filters(self):
        client = FakeClient([{}])
        FmResource(client).available_data(model_id="tradefm-hkex", limit=5)
        _, path, kwargs = client.calls[0]
        assert path == "/fm/available-data"
        assert kwargs["params"] == {"model_id": "tradefm-hkex", "limit": 5, "offset": 0}

    def test_run_sends_only_what_is_set(self):
        client = FakeClient([{}])
        FmResource(client).run(
            "tradefm-hkex", "700", "2025-09-02", "bmll", "hkex_securities",
            duration_minutes=30, n_runs=4, model_args={"temperature": 0.8},
        )
        _, path, kwargs = client.calls[0]
        body = kwargs["json"]
        assert path == "/fm/run"
        assert body["duration_minutes"] == 30 and body["n_runs"] == 4
        assert body["model_args"] == {"temperature": 0.8}
        for absent in ("horizon", "device", "exec_algos"):
            assert absent not in body


class TestFixResource:
    def test_usage_path(self):
        client = FakeClient([{}])
        FixResource(client).usage()
        assert client.calls[0][:2] == ("GET", "/fix/usage")


class TestSimulationAdditions:
    def test_run_lrm_payload(self):
        client = FakeClient([{}])
        SimulationResource(client).run_lrm(
            "700", "2025-09-02", "omd", "hkex_securities",
            order_sizes=[10, 50, 100], side="buy",
        )
        method, path, kwargs = client.calls[0]
        assert (method, path) == ("POST", "/simulation/lrm/run")
        body = kwargs["json"]
        assert body["order_sizes"] == [10, 50, 100]
        assert body["strategy"] == "vwap" and body["side"] == "buy"

    def test_get_job_logs_returns_plain_text(self):
        class TextClient(FakeClient):
            base_url = "https://api.test"

            def _request_with_retries(self, method, url, **kwargs):
                self.calls.append((method, url, kwargs))

                class R:
                    text = "engine log line"

                return R()

        client = TextClient()
        out = SimulationResource(client).get_job_logs("job-1")
        assert out == "engine log line"
        assert client.calls[0][1].endswith("/simulation/jobs/job-1/logs")
