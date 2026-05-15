#!/usr/bin/env python3
"""Patch metrics-0.23.0 to compile on Rust 1.94.0+.

Rust 1.94.0 introduced E0521 for lifetime escapes via raw pointer coercions
of trait objects. In metrics-0.23.0/src/recorder/mod.rs line 75:

    let recorder_ptr = unsafe { NonNull::new_unchecked(recorder as *const _ as *mut _) };

The fix: explicitly transmute the reference lifetime to 'static before
creating the raw pointer. This matches what the original code was implicitly
(unsoundly) doing, but satisfies Rust 1.94's stricter lifetime checker.
"""
import glob
import os
import sys

# Cargo home: respect $CARGO_HOME, fall back to $HOME/.cargo, also try /.cargo
cargo_home = os.environ.get("CARGO_HOME") or os.path.join(os.path.expanduser("~"), ".cargo")
search_roots = list({cargo_home, os.path.join(os.path.expanduser("~"), ".cargo"),
                     "/.cargo", "/root/.cargo"})

files = []
for root in search_roots:
    files.extend(glob.glob(
        os.path.join(root, "registry/src/*/metrics-0.23.*/src/recorder/mod.rs")
    ))
files = list(set(files))

if not files:
    print("metrics-0.23.x recorder/mod.rs not found in:", search_roots)
    print("Skipping patch — build may fail with Rust >=1.94.0.")
    sys.exit(0)

# The exact problematic expression from line 75 of metrics-0.23.0.
# Replace it with an explicit lifetime transmute so Rust 1.94+ accepts it.
OLD = "let recorder_ptr = unsafe { NonNull::new_unchecked(recorder as *const _ as *mut _) };"
# The function takes &dyn Recorder (not generic R), so use _ for type inference.
# Transmuting the reference lifetime to 'static satisfies Rust 1.94's E0521 check.
NEW = ("let recorder_static: &'static dyn Recorder = unsafe { ::std::mem::transmute(recorder) };\n"
       "        let recorder_ptr = unsafe { NonNull::new_unchecked(recorder_static as *const _ as *mut _) };")

patched_any = False
for f in files:
    text = open(f).read()
    if OLD in text:
        open(f, "w").write(text.replace(OLD, NEW))
        print(f"Patched: {f}")
        patched_any = True
    else:
        print(f"Pattern not found in: {f}")

if not patched_any:
    print("WARNING: no files patched — metrics may already be fixed or pattern changed")
