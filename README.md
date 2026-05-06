# SurfGym

A web-based reinforcement learning environment for CUA that supports multibrowser requring tasks.

<br/>

<div align="center">
<img src="figures/architecture.png" alt="architecture" width="600">
</div>

<br/>

**Table of Contents**

<!--TOC-->

- [Setup](#setup)
  - [1. Clone this repository](#1-clone-this-repository)
  - [2. Set up environment](#2-set-up-environment)
- [Run](#run)
  - [Launch Server](#launch-server)
  - [Defining Tasks](#defining-tasks)
    - [Single Browser Task](#single-browser-task)
    - [Multi Browser Task](#multi-browser-task)
- [Testing](#testing)
  - [Manual Action Test](#manual-action-test)
  - [Parrallel Manual Action Test](#parrallel-manual-action-test)
- [Examples](#examples-1)
  - [Counter](#counter)
  - [Action](#action)
  - [Copy left to right](#copy-left-to-right)

<!--TOC-->

<!-- md_toc -s 1 --in-place github --header-levels 4 README.md -->



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

<br/>

The commands below install dependencies that are **not tied** to the Conda environment.

```bash
playwright install chromium

# Linux only
playwright install-deps chromium
```

<br/>

## Run

### Launch Server

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

### Defining Tasks

Tasks are defined in a JSON file as a list of task objects. There are two type of task objecs : `Single` and `Multi`.

<br/>


#### Single Browser Task

A single browser task opens one website and evaluates the final browser state with one evaluation block.

```json
{
  "task_id": "counter",
  "instruction": "Make the counter value 5.",
  "website": "http://127.0.0.1:8123/counter.html",
  "evaluation": {
    "operator": "and",
    "rule": {
      "selector": "#count",
      "target": "text",
      "value": "5",
      "match": "exact"
    }
  }
}
```

<br>

`evaulation` defines how each task will be rewarded.

- `operator` controls how multiple rules are combined. `and` is for all rules pass and `or` is for at least one pass. It is **omittable** and `and` is default.


<br>

`rule` defines one or more checks against the final browser state. A single rule object or a list of rule objects can be provided.


| Field | Description | Allowed values | Omittable | Default |
| --- | --- | --- | :---: | --- |
| `selector` | CSS selector for element-level checks. Omit it for page-level checks such as `url` or `title`. | Any valid CSS selector | O |  |
| `target` | Defines what to check. | `text`, `html`, `url`, `title`, `attr` | O | `text` |
| `attr` | Attribute name to inspect when `target` is `attr`, for example `value`. | Any attribute name | O |  |
| `value` | Expected value. | String |  |  |
| `match` | Controls how `value` is matched. | `contains`, `exact`, `regex` | O | `contains` |
| `normalize_space` | Controls whether whitespace is collapsed before matching. | `true`, `false` | O | `false` |
| `case_sensitive` | Controls whether matching is case-sensitive. | `true`, `false` | O | `true` |




##### Examples:

```json
{
  "selector": "#answer",
  "target": "attr",
  "attr": "value",
  "value": "hello",
  "match": "exact"
}
```

```json
{
  "target": "url",
  "value": "example.com",
  "match": "contains"
}
```

<br/>

#### Multi Browser Task

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

# ==================================================================================
# User-defined settings
# Modify only the values below for testing.
# 
# * Use the appropriate SURFGYM_CONFIG for the target test
# * Make sure to set WITH_FIXTURE_WEBSITE=true when using fixture websites
# ==================================================================================

readonly SURFGYM_CONFIG="$FIXTURE_DIR/config/config-single.json"

readonly WITH_FIXTURE_WEBSITE=true
readonly FIXTURE_WEBSITE_PORT=8123

# ==================================================================================
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

<br>

### Parrallel Manual Action Test

<br>

## Examples

We provide several examples to check the features on the manual action test. Check the task definition and websites in `tests/fixtures`.

<br/>

### Counter


<div align="center">
<img src="figures/counter.png" alt="architecture" width="600">
<img src="figures/counter-success.png" alt="architecture" width="600">
</div>

```python
TASK_ID = "counter"
ACTIONS: list[list[dict[str, Any]]] = [
    [
        {
            "action_type": "CLICK",
            "x": 1016,
            "y": 631,
        },
    ],
    [
        {"action_type": "CLICK", "num_clicks": 4},
    ]
```

<br>

### Action

<div align="center">
<img src="figures/action.png" alt="architecture" width="600">
<img src="figures/action-success.png" alt="architecture" width="600">
</div>

```python
TASK_ID = "action"
ACTIONS: list[list[dict[str, Any]]] = [
    [{"action_type": "CLICK", "x": 537, "y": 193}],
    [{"action_type": "DOUBLE_CLICK", "x": 1063, "y": 193}],
    [{"action_type": "RIGHT_CLICK", "x": 559, "y": 393}],
    [{"action_type": "CLICK", "x": 1209, "y": 393}],
    [{"action_type": "TYPING", "text": "action-lab"}],
    [{"action_type": "MOVE_TO", "x": 543, "y": 604}],
    [{"action_type": "DRAG_TO", "x": 800, "y": 710}],
    [{"action_type": "MOVE_TO", "x": 1200, "y": 700}],
    [{"action_type": "SCROLL", "dx": 0, "dy": 700}],
    [{"action_type": "CLICK", "x": 1067, "y": 715}],
]
```

<br>

### Copy left to right

<div align="center">
<img src="figures/copy_left_to_right.png" alt="architecture" width="600">
<img src="figures/copy_left_to_right-success.png" alt="architecture" width="600">
</div>

```python
TASK_ID = "copy_left_to_right"
ACTIONS: list[list[dict[str, Any]]] = [
    [
        {
            "action_type": "CLICK",
            "x": 245,
            "y": 622,
        },
    ],
    [
        {
            "action_type": "CLICK",
            "x": 1440,
            "y": 561,
        },
    ],
    [
        {
            "action_type": "HOTKEY",
            "keys": ["ControlOrMeta", "v"],
        },
    ],
]
```