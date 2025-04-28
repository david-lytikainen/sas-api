#!/bin/bash
cd "$(dirname "$0")/.."
source venv/bin/activate
python3 start.py 2>&1 | tee logs/api.log
