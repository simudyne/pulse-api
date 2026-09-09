# CHANGELOG


## v0.7.0-dev.3 (2026-09-09)

### Bug Fixes

- Accept the documented filter params — get_available_symbols(q), get_jobs(limit)
  ([`7ea5010`](https://github.com/simudyne/pulse-sdk/commit/7ea5010e90c68e40956b650feb25027e5bc20ee4))

The docs suite's Response Shapes job checks the SDK against the live API and found two documented
  parameters the SDK did not accept: the q substring search on /data/available-symbols (docs:
  "searches ticker and company name") and the limit on /simulation/jobs (docs promise
  jobs/total/returned paging). Both routes already support them; the SDK just never passed them
  through.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>


## v0.7.0-dev.2 (2026-09-09)

### Documentation

- **validation**: Mind/fid reach every tier as of pulse-api-pod 1.56.0
  ([`fb92309`](https://github.com/simudyne/pulse-sdk/commit/fb923093bad9664b77e61adb7e277b27f6bd8efe))

The scores were demo-only; the API now shares them with every validation tier since they are
  aggregate scalars. Docstrings and the empty-score error message updated to say so.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>

### Features

- Complete the documented 0.8.0 surface — fm, fix, run_upload, job logs, LRM
  ([`2cc74ee`](https://github.com/simudyne/pulse-sdk/commit/2cc74eec77cd21a664f1e93feaa6269893bd744f))

The website docs (and its docs code-block suite) describe SDK methods that did not exist yet, which
  is what the suite's simudyne-pulse>=0.8.0 tripwire pin guards against. This adds the missing
  surface, matching the docs pages and the pulse-api-pod routes each method wraps:

- validation.run_upload(): multipart POST /validation/run/upload for frames not stored in Pulse.
  sim_files takes paths or (filename, bytes) pairs; 1-25 enforced client-side with ValueError before
  any bytes move; same tri-state run flags as run() via a shared _build_config(). -
  simulation.get_job_logs(): GET /simulation/jobs/{id}/logs, returned as the plain text it is (via
  the retrying transport, not the JSON helper). - simulation.run_lrm(): POST /simulation/lrm/run,
  mirroring LRMRunRequest — one algo per order size over a shared baseline. - fm resource: models(),
  available_data() (registry search with server-side filters, None params omitted), run()
  (duration_minutes/horizon, n_runs 1-8, model_args, device, exec_algos — unset fields omitted so
  server defaults hold), live(), job_status(), job_logs(), and TERMINAL_STATUSES = {complete,
  failed}, which the foundation-models docs page imports. - fix resource: usage().

Also refreshes validation docstrings for the impact-response tier change (pulse 2.17.0 /
  pulse-api-pod 1.62.0): the pass runs at every tier, the simulated curves are returned everywhere,
  the historical block stays demo/plot_data-only, and get_job() documents impact_response_error.

13 new payload tests in the existing recorder style; the 10 pre-existing test_simulator_gym failures
  locally are a missing websocket-client in the local env, unchanged by this commit.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>


## v0.7.0-dev.1 (2026-08-19)

### Chores

- **validation**: Take prod's validation.py (run_stylised_facts tri-state)
  ([`d83e31b`](https://github.com/simudyne/pulse-sdk/commit/d83e31b8eac4e1d2898ca276554513c18215d424))

dev is 4 commits behind prod and its validation.py lacks the run_stylised_facts tri-state added
  there. Bringing that one file forward first so the inception-distance work below builds on it
  instead of reverting it.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>

### Features

- **validation**: Mind/fid via run_inception_distances, drop dead params
  ([`99cd8ba`](https://github.com/simudyne/pulse-sdk/commit/99cd8bad9f10b2cb8ef98a9518a4e258156ad77f))

pulse-check 1.8.0 replaced the raw-feature FID with MIND and FID on DeepLOB embeddings — one
  embedding pass computes both — and removed rescale_volumes/lot_size, since simudyne format is
  always denominated in shares. The API (>= 1.55.1) returns mind_scores alongside fid_scores.

- run_fid -> run_inception_distances, default True: the old name described one of the two metrics it
  gates, so run_fid=False silently disabled MIND too. Still sent as the API's run_fid config field,
  which keeps its name for existing HTTP clients. The old kwarg now raises TypeError rather than
  being quietly ignored. - inception_distances(): one call returning {mind, fid, sim_ids, job_id},
  forcing the other passes off so the job does a single embedding pass. Raises when the scores are
  absent — a skipped pass and a non-demo key are both silent in the raw response. -
  run_metrics/run_impact join run_stylised_facts and plot_data as tri-state (None = tier default,
  omitted from the payload). Previously the SDK always sent run_impact=False, opting demo keys out
  of a pass they are entitled to. - rescale_volumes/lot_size removed; l2_only, provider and exchange
  added to match the API. get_job() documents mind_scores, the demo-tier rule, and that fid_scores
  is now the embedding-space FID, not comparable with values stored by older jobs. -
  tests/test_validation.py: 9 tests pinning the wire payload, the rename and the score handling.
  None existed before.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>


## v0.6.1 (2026-08-05)

### Bug Fixes

- **simulation**: Correct stale flash_crash/buy_panic scenario defaults
  ([`af10951`](https://github.com/simudyne/pulse-sdk/commit/af1095184277f593aeadded35fac34ac8d598823))

- both advertised 22.0/0.19/500ms while the engine has used 150.0/0.02/100ms since pulse 2.4.7
  (07c176e1), so anyone sizing a scenario from get_scenario_defaults got ~7x the impact shown - note
  the mirroring requirement against EIB/calcs/scenarios.py, whose builder signatures SimulationRun
  backfills from

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>


## v0.6.0 (2026-08-05)


## v0.6.0-dev.2 (2026-08-04)

### Documentation

- **sdk**: Permanent group membership semantics for the download quota
  ([`b7c6584`](https://github.com/simudyne/pulse-sdk/commit/b7c6584854afa55e2b4d518ed47aa6b9cf0becf7))

- downloads() documents downloaded_groups and new-groups-per-window counting -
  get_sim_data/get_bulk_data note the per-file quota and free re-fetches

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

### Features

- **data**: Forward catalog filters from get_available_symbols
  ([`675d98d`](https://github.com/simudyne/pulse-sdk/commit/675d98d26e88a52a313ea1043321019946e8e5ec))

- Accept optional symbol/exchange/provider/date/limit/offset and pass them as query params to GET
  /data/available-symbols - No-argument calls behave exactly as before

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>


## v0.6.0-dev.1 (2026-07-16)

### Chores

- **ci**: Add manual test workflow and sync dev with prod rename
  ([`7233349`](https://github.com/simudyne/pulse-sdk/commit/7233349592a65932a508827979d26c703b9b872f))

- Add .github/workflows/test.yml with workflow_dispatch trigger running pytest - Add optional "test"
  dependency group (pytest) to pyproject.toml - Bring dev up to date with the main->prod rename and
  PyPI publish step

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

- **release**: Add dev prerelease channel alongside stable main
  ([`d5b0943`](https://github.com/simudyne/pulse-sdk/commit/d5b094353afa50cc40f6df0ff1ac9bff2e13d724))

- Configure semantic-release branches: main (stable) + dev (-dev.N prereleases) - Trigger release
  workflow on pushes to dev as well as main - Document `pip install git+...@dev` dev builds in
  README

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>

- **release**: Rename stable branch main -> prod
  ([`1e3ad4b`](https://github.com/simudyne/pulse-sdk/commit/1e3ad4bfa2744508885cc97a61b3cbd90de5b7d8))

- Point semantic-release stable channel at prod (was main) - Trigger release workflow on prod
  instead of main - Update README promote-to-stable note

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>

### Features

- **profile**: Add downloads() for the bulk-download quota endpoint
  ([`873893c`](https://github.com/simudyne/pulse-sdk/commit/873893c6e1d724fc334ec85b4f7ac750b23b759a))

- client.profile.downloads() wraps GET /profile/downloads (limit/used/remaining) - document
  free-tier quota semantics and 429 behaviour on get_bulk_data

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>


## v0.5.2 (2026-06-17)

### Bug Fixes

- Update client to catch connection errors
  ([`e26d3bf`](https://github.com/simudyne/pulse-sdk/commit/e26d3bf4b54e8849b2cdb1f2e07a52f4e28daedc))

### Documentation

- **sdk**: Use provider="omd" in examples (was "hkex")
  ([`687061b`](https://github.com/simudyne/pulse-sdk/commit/687061bc6dc2e4c74654208448c87f51341f4336))

The HKEX provider was renamed to 'omd'; run()/calibrate() docstring examples now match the API's
  valid providers.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>


## v0.5.1 (2026-06-05)


## v0.5.0 (2026-06-03)

### Features

- Add PlotDisplay with distributions/distances/impact_response methods
  ([`dc69de4`](https://github.com/simudyne/pulse-sdk/commit/dc69de435f56f5c0deabcfb68e2c526d74826032))


## v0.4.1 (2026-06-03)

### Bug Fixes

- Add rescale_volumes and lot_size to run_pipeline
  ([`890c47f`](https://github.com/simudyne/pulse-sdk/commit/890c47ff87382aa06de5feafe3c52772927fa573))


## v0.4.0 (2026-06-03)

### Features

- Change naming of val function
  ([`1302a4c`](https://github.com/simudyne/pulse-sdk/commit/1302a4caf945aacff02c94c95c7ddf7f061004a6))


## v0.3.0 (2026-06-02)

### Documentation

- Fix exec_algos documentation to match actual API
  ([`fe22ee8`](https://github.com/simudyne/pulse-sdk/commit/fe22ee8e1db47e6acc312c5fbd8e59d12752d744))

- Changed `horizon (timedelta)` to `horizon: SECONDS` (int) - Documented order_size sign convention:
  negative=buy, positive=sell - Fixed example: `horizon_mins: 60` → `horizon: 3600` - Added buy
  order example

Addresses UAT issues #2 (kwarg mismatch) and #5 (sign convention).

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

### Features

- Adding validation endpoints to the SDK
  ([`d5e6708`](https://github.com/simudyne/pulse-sdk/commit/d5e6708c2ef2947ce959089a5cb44a82899cf9e4))


## v0.2.0 (2026-05-14)

### Bug Fixes

- Align sample data with pulse-api-pod
  ([`c79b372`](https://github.com/simudyne/pulse-sdk/commit/c79b372a114102a423bf78c93bffe81545d7ffad))


## v0.1.3 (2026-05-05)

### Bug Fixes

- Error logging
  ([`7b488b0`](https://github.com/simudyne/pulse-sdk/commit/7b488b0cff6b53194cd93992c62e78e83e678b9b))

### Features

- Add l2_by_second parquets
  ([`51d6d2a`](https://github.com/simudyne/pulse-sdk/commit/51d6d2ac81327037e520bdd621797e9231755850))


## v0.1.2 (2026-05-05)


## v0.1.1 (2026-05-05)

### Bug Fixes

- @main for release
  ([`247a6da`](https://github.com/simudyne/pulse-sdk/commit/247a6daa064fd3664dc2cef78f35219d8639074a))

- Added exponetial backoff and timeout.
  ([`f6810f0`](https://github.com/simudyne/pulse-sdk/commit/f6810f061ddd540379eee668210eea81d3ce74cd))

- Error logging
  ([`806720d`](https://github.com/simudyne/pulse-sdk/commit/806720d09058050749e5b0b98d3f899d9db25b11))

- Resolve build failure and clean up release workflow
  ([`40f5fb4`](https://github.com/simudyne/pulse-sdk/commit/40f5fb47d6c81d27eba27d352d935d0fdb4d9c85))

- Serialise the exec_algo params
  ([`05cf196`](https://github.com/simudyne/pulse-sdk/commit/05cf196c43e2d477f73f71623e501fa469385c15))

- Updated to improve the security pratices
  ([`824fc2b`](https://github.com/simudyne/pulse-sdk/commit/824fc2bef1295d3d88e6c6c42d99dcffa7e08d21))

- Updating api to include rl gym and point at the new cluster
  ([`01e9f08`](https://github.com/simudyne/pulse-sdk/commit/01e9f082f178b5cb8f1d6940e0d91502fa06aa24))

- Updating the new base url
  ([`df9b3f8`](https://github.com/simudyne/pulse-sdk/commit/df9b3f80e0edd186e5602ec7655d00ed9de4fdb5))


## v0.1.0 (2026-02-19)
