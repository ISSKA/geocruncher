import os
from pathlib import Path
import sys

# take path as first argument
stub_pyi = sys.argv[1] if len(sys.argv) > 1 else os.getenv('PYKARSTNSIM_STUB_PYI')
if not stub_pyi:
    raise RuntimeError("Environment variable PYKARSTNSIM_STUB_PYI not set")
p = Path(stub_pyi)

s = p.read_text(encoding='utf-8')
# remove self-qualification ("pykarstnsim_core.") so type checkers resolve local symbols
# This fixes a bug with pybind11_stubgen and std::optional
s2 = s.replace('pykarstnsim_core.', '')
if s2 != s:
    p.write_text(s2, encoding='utf-8')
