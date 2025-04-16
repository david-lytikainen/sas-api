#!/bin/bash
cd "$(dirname "$0")/.."
source venv/bin/activate
export FLASK_APP=run.py
export FLASK_ENV=development
export FLASK_DEBUG=1
python start.py
