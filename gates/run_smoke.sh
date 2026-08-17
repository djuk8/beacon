#!/bin/bash
set -e
python3 exchange/pricer_v1.py --selftest
python3 -c "import tools.fastmake" 2>/dev/null || python3 -c "import sys; sys.path.insert(0,'tools'); import fastmake; print('fastmake imports')"
python3 -m py_compile tools/*.py exchange/*.py theater/*/*.py
echo "SMOKE PASS"
