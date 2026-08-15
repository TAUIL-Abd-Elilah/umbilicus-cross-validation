#!/bin/sh
# Automatic lasagna-based umbilicus estimate for every eligible scroll.
for s in PHerc0125 PHerc0191 PHerc0211 PHerc0257 PHerc0268 PHerc0358 PHerc0800 \
         PHerc0813 PHerc0826 PHerc1203 PHerc1218 PHerc1447 PHerc1545; do
  out="seeds/${s}_umbilicus_estimated.json"
  if [ -f "$out" ] && [ "$s" != "PHerc0211" ]; then
    echo "$s: present, skipping"; continue
  fi
  C:/Users/PC/miniconda3/envs/vesuvius/python.exe estimate_umbilicus.py "$s" --n 40 || echo "$s FAILED"
done
