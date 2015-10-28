#!/usr/bin/env python
import subprocess
obsid = 1115381072
check = "/home/fkirsten/software/galaxy-scripts/scripts/checks.py -m download -o {0}".format(obsid)
with open('./check.log','w') as f:
    if subprocess.call(check, stdout=f, stderr=f, shell=True):
        subprocess.call("cat {0}".format(f), shell=True)
