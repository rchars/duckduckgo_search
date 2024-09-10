#/bin/bash

LOCATION="$(dirname "$(readlink -f "$0")")"
source "$LOCATION/venv/bin/activate"
python3 -B -OO "$LOCATION/duckduckgo_search/mymain.py" "$@"
