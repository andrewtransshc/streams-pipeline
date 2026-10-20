#!/bin/zsh
cd /Users/andrewtran/Documents/Claude/Streams
export PATH="$PWD/bin:$PATH"
.venv/bin/python -u stream_edit.py sp2 docs && .venv/bin/python -u stream_edit.py sp2 shorts && .venv/bin/python -u stream_edit.py sp2 main \
 && .venv/bin/python -u stream_edit.py sp1 docs && .venv/bin/python -u stream_edit.py sp1 shorts && .venv/bin/python -u stream_edit.py sp1 main && echo ALL_DONE
