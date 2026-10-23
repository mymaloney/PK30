"""No plain call or jp from one switchable ROM bank into another: rgbds
doesn't catch them, and moving a file to a new bank can leave one behind (the
boulder dust froze the game that way; test_boulder_dust.py). Reads the
sources and the Red build's symbol file."""

import os
import re
import subprocess
import unittest

from harness import REPO_ROOT

CALL = re.compile(r"^\s*(call|jp)\s+(?:(?:nz|z|nc|c)\s*,\s*)?([A-Za-z_][\w.]*)\s*$")
LABEL = re.compile(r"^([A-Za-z_]\w*)::?")


class CrossBankTest(unittest.TestCase):
    def test_no_plain_cross_bank_calls(self):
        sym = {}
        with open(os.path.join(REPO_ROOT, "pokered.sym")) as f:
            for line in f:
                if line.startswith(";") or ":" not in line:
                    continue
                where, name = line.split()
                sym[name] = int(where.split(":")[0], 16)
        files = subprocess.run(["git", "-C", REPO_ROOT, "ls-files", "*.asm"],
                               capture_output=True, text=True, check=True).stdout.split()
        bad, checked = [], 0
        for name in files:
            current = None
            with open(os.path.join(REPO_ROOT, name), errors="ignore") as f:
                for number, line in enumerate(f, 1):
                    code = line.split(";")[0]
                    label = LABEL.match(code)
                    if label:
                        current = label.group(1)
                        continue
                    call = CALL.match(code)
                    if not call or current not in sym or call.group(2) not in sym:
                        continue
                    here, there = sym[current], sym[call.group(2)]
                    if here and there:
                        checked += 1
                        if here != there:
                            bad.append(f"{name}:{number} {current} -> {call.group(2)}")
        self.assertGreater(checked, 1000)  # the scan found the calls
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
