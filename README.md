# webgym-rl

A web-based reinforcement learning environment for CUA.

<br/>

## Setup


### 1. Clone the repository

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

<br/>

## Run

To start the server, you need to run both the Gateway and the Omnibox Server.
For easier log monitoring, we recommend running them in separate terminal sessions.

You can configure both servers by editing `config.json`.
There is no need to modify `setting.sh`.

```bash
bash omnibox_launch.bash
```

```bash
bash webgym_rl_launch.bash
```

<br/>

Check if the servers are properly launched using `health_check.bash`

```bash
bash health_check.bash
```

<br/>

## Testing

### Manual E2E Test

You can manually test tasks using the command below.

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
# * Use the appropriate WEBGYM_RL_CONFIG for the target test
# * Make sure to set WITH_FIXTURE_WEBSITE=true when using fixture websites
# =============================================================================================

readonly WEBGYM_RL_CONFIG="$FIXTURE_DIR/CHANGE_HERE"

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