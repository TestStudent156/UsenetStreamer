import sys
import json
import subprocess

data = json.load(sys.stdin)
file_path = data.get("tool_input", {}).get("file_path", "")

if not any(x in file_path for x in ["custom_components", "tests"]):
    sys.exit(0)

result = subprocess.run(
    [sys.executable, "-m", "pytest", "--tb=short", "-q"],
    capture_output=True,
    text=True,
)
output = (result.stdout + result.stderr)[-3000:]
if output.strip():
    print(output)
sys.exit(0)
