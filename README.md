# Simudyne Pulse Python SDK

Python client for the [Pulse](https://pulse.simudyne.com) synthetic market data API. Returns data as [Polars](https://pola.rs/) DataFrames.

## Installation

```bash
pip install simudyne-pulse
```

The distribution is named `simudyne-pulse`; the import name is `simudyne`:

```python
from simudyne import PulseABM
```

Requires Python 3.10+.

### Development builds

The `dev` branch is a prerelease channel. Pushes to it publish prerelease
versions (e.g. `0.6.0.dev1`) that are separate from the stable versions cut on
`prod`. `pip install simudyne-pulse` always resolves to the latest **stable**
release and ignores prereleases, so dev builds can never affect a normal
install.

To install the latest dev build, opt in with `--pre`:

```bash
pip install --pre simudyne-pulse
```

Only use dev builds for testing unreleased changes; they are not guaranteed
stable. Merge `dev` into `main` to promote those changes to a stable release.

## Quick start

```python
from simudyne import PulseABM

client = PulseABM(api_key="pk_live_...")

# List available exchanges, symbols, and dates
symbols = client.data.get_symbols(year=2024)
print(symbols)

# Fetch L2 order book data
df = client.data.get_L2("HKEX", "HSIJ4", "2024-04-02T09:15:00", "2024-04-02T09:16:00")
print(df.head())
```

## API reference

### `PulseABM(api_key, base_url=None)`

| Parameter | Env variable | Default |
|-----------|-------------|---------|
| `api_key` | `SIMUDYNE_API_KEY` | required |
| `base_url` | `SIMUDYNE_BASE_URL` | Pulse API |

### `client.data`

All data methods return Polars DataFrames. Large result sets are automatically paginated.

```python
# Available exchanges, symbols, and dates
client.data.get_symbols(year=2024)

# L1: top of book (best bid/ask)
client.data.get_L1("HKEX", "HSIJ4", "2024-04-02T09:15:00", "2024-04-02T10:00:00")

# L2: full order book (all levels)
client.data.get_L2("HKEX", "HSIJ4", "2024-04-02T09:15:00", "2024-04-02T09:16:00")

# Orders: individual order events
client.data.get_orders("HKEX", "HSIJ4", "2024-04-02T09:15:00", "2024-04-02T10:00:00")

# Trades: executed trades
client.data.get_trades("HKEX", "HSIJ4", "2024-04-02T09:15:00", "2024-04-02T10:00:00")
```

**Parameters** (same for all data methods):

| Parameter | Type | Description |
|-----------|------|-------------|
| `exchange` | str | Exchange code (e.g. `HKEX`) |
| `sym` | str | Symbol name (e.g. `HSIJ4`) |
| `datetime_start` | str | Start time, ISO 8601 (e.g. `2024-04-02T09:15:00`) |
| `datetime_end` | str | End time, ISO 8601 |

### `client.profile`

```python
client.profile.get()      # Account info
client.profile.usage()    # API usage stats
```

### `client.api_keys`

```python
client.api_keys.list()                    # List active keys
client.api_keys.create(name="research")   # Create a new key
client.api_keys.revoke(key_id="key_...")  # Revoke a key
```

## Configuration

You can set your API key as an environment variable instead of passing it directly:

```bash
export SIMUDYNE_API_KEY=pk_live_...
```

```python
from simudyne import PulseABM
client = PulseABM()  # picks up SIMUDYNE_API_KEY automatically
```

## License

MIT
