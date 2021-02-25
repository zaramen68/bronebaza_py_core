#!/usr/bin/env bash
fname="/var/spread/core/version.py"
mask="BUILD = "
b=$(cat ${fname} | grep ^"BUILD = ")
b=${b::-1}
b=${b#* = }
bi=$((b+1))

pip3 wheel --wheel-dir=spread-wheels -e lom/
pip3 wheel --wheel-dir=spread-wheels --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
python3 setup.py bdist_wheel
sed -i -e "s@^BUILD = ${b}\\b@BUILD = ${bi}@g" ${fname}
