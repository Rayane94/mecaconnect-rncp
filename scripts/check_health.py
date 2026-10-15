#!/usr/bin/env python3
"""MecaConnect HTTP liveness probe; no third-party dependency."""
import json
import os
import sys
import urllib.error
import urllib.request

url = os.environ.get("MECACONNECT_HEALTH_URL", "https://mecaconnect-rncp-production.up.railway.app/api/health")
request = urllib.request.Request(url, headers={"User-Agent": "MecaConnect-Health/1.0"})
try:
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError("HTTP " + str(response.status))
        payload = json.loads(response.read(4096))
        if payload.get("status") != "ok" or payload.get("service") != "mecaconnect-api":
            raise RuntimeError("Unexpected API payload")
        print("OK:", url, payload.get("time", ""))
except (urllib.error.URLError, TimeoutError, RuntimeError, ValueError, KeyError) as exc:
    print("FAIL:", url, type(exc).__name__, str(exc), file=sys.stderr)
    sys.exit(1)
