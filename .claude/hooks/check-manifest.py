import sys
import json

data = json.load(sys.stdin)
file_path = data.get("tool_input", {}).get("file_path", "")

if "manifest.json" in file_path:
    print("REMINDER: Did you bump the 'version' field in manifest.json for this release?")

sys.exit(0)
