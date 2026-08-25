#!/usr/bin/env sh
# Print the URLs for the end-to-end user-flow walkthrough.
#
# IDs change every time the backend is re-seeded, so derive them rather than
# writing them down. Needs the backend on :8000 and demo-data/seed.py already
# run.
#
#   sh scripts/flow-urls.sh
set -eu

API=${API:-http://localhost:8000}
WEB=${WEB:-http://localhost:5173}

json() { python3 -c "import sys,json;$1" ; }

ASSET=$(curl -s "$API/api/v1/assets" | json 'd=json.load(sys.stdin);m=[x for x in d if "Pompa" in x["name"]];print(m[0]["id"] if m else "")')
if [ -z "$ASSET" ]; then
  echo "No PUMP-01 asset found. Run demo-data/seed.py first." >&2
  exit 1
fi

RUNS=$(curl -s "$API/api/v1/assets/$ASSET/analyses" | json 'd=json.load(sys.stdin);print(" ".join(x["id"] for x in d))')
RUN_LATEST=$(echo "$RUNS" | cut -d" " -f1)
RUN_PREV=$(echo "$RUNS" | cut -d" " -f2)
WO=$(curl -s "$API/api/v1/work-orders" | json 'd=json.load(sys.stdin);print(d[0]["id"] if d else "")')

echo "asset  PUMP-01     $ASSET"
echo "run    latest      ${RUN_LATEST:-<none: run an analysis>}"
echo "run    previous    ${RUN_PREV:-<none: run a second analysis>}"
echo "wo     newest      ${WO:-<none: create a work order>}"
echo
echo "01  $WEB/setup"
echo "02  $WEB/machines/new"
echo "03  $WEB/qc-model"
echo "04  $WEB/business-context"
echo "05  $WEB/analyze"
echo "06  $WEB/analysis/$RUN_LATEST"
echo "07  $WEB/analysis/$RUN_LATEST/compare?with=$RUN_PREV"
echo "08  $WEB/work-orders"
echo "09  $WEB/work-orders/$WO"
echo "10  $WEB/work-orders/$WO/execute"
echo "11  $WEB/work-orders/$WO/report"
