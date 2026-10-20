#!/usr/bin/env bash
# The rules script (standards.py), by the path the git hooks and the Compliance check call.
exec python3 "$(dirname "$0")/standards.py" "$@"
