python3 - <<'PY'
from pathlib import Path
from src.config import Config

Config.model_validate_json(
    Path("tests/fixtures/config/config-test.json").read_text()
)
print("OK")
PY
