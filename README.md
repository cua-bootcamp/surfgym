# SurfGym

A web-based reinforcement learning environment for CUA that supports multibrowser requring tasks.

<br/>

<div align="center">
<img src="figures/architecture.png" alt="architecture" width="600">
</div>


<br/>

## Setup


### 1. Clone this repository

```bash
git clone https://github.com/cua-bootcamp/surfgym
cd surfgym
```

<br/>

### 2. Set up environment

```bash
conda create -n surfgym python=3.10 -y
conda activate surfgym

pip install -U pip uv
uv pip install -r requirements.txt
```

The commands below install system-level dependencies and are not tied to the Conda environment.

```bash
playwright install chromium

# Linux only
playwright install-deps chromium
```

<br/>

## Run

To start the server, you need to run 1. Gateway and 2. WavePool  Server.
For easier log monitoring, we recommend running them in separate terminal sessions.

You can configure both servers by editing `config.json`.
There is no need to modify `setting.sh`.

```bash
bash scripts/wavepool_launch.bash
```

```bash
bash scripts/gateway_launch.bash
```

<br/>

Check if the servers are properly launched using `health_check.bash`

```bash
bash scripts/health_check.bash
```

<br/>

## Testing

### Manual Action Test

You can test a single task based on manually written action sequence.

```bash
bash tests/manual_test.sh
```

<br/>

Before running the test, make sure to check the following settings in `tests/setting.sh` and `tests/runners/manual/run.py`.

<br/>

```bash
# tests/setting.sh

# =============================================================================================
# User-defined settings
# Modify only the values below for testing.
# 
# * Use the appropriate SURFGYM_CONFIG for the target test
# * Make sure to set WITH_FIXTURE_WEBSITE=true when using fixture websites
# =============================================================================================

readonly SURFGYM_CONFIG="$FIXTURE_DIR/config/config-single.json"

readonly WITH_FIXTURE_WEBSITE=true
readonly FIXTURE_WEBSITE_PORT=8123

# =============================================================================================
```

```python
# tests/runners/manual/run.py

# ============================================================
# User-defined settings
# Modify only the values below for testing.
# ============================================================
TASK_ID = "form"
ACTIONS: list[list[dict[str, Any]]] = [
    [
        {
            "action_type": "CLICK",
            "button": "left",
            "num_clicks": 5,
            "x": 849,
            "y": 303,
        },
    ]
]
```

## TODO

- [ ] Key 관련 (에러에 어떻게 반응)
- [ ] Multi Browser