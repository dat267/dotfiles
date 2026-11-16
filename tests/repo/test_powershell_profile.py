"""The profile's script resolver builds a scriptblock from a path string.

`Resolve-ScriptCommand` splices the interpreter and the script path into
`"& '<interpreter>' '<path>' $args"` and hands it to `[scriptblock]::Create`.
A single quote inside either string ends the literal early, and Windows allows
one in a user name, so the quoting has to survive that.
"""

import pathlib
import shutil
import subprocess
import tempfile
import unittest

import _loader

PROFILE = (_loader.SOURCE / "dot_config/powershell"
           / "executable_Microsoft.PowerShell_profile.ps1")

HARNESS = """\
function global:Get-ScriptResolvers {{ [ordered]@{{ '.py' = 'python3' }} }}
{function_text}
$plain = @{{ Command = $null }}
Resolve-ScriptCommand "C:\\tools\\demo.py" $plain
$quoted = @{{ Command = $null }}
Resolve-ScriptCommand "C:\\Users\\O'Brien\\bin\\demo.py" $quoted
if (-not $plain.Command) {{ throw 'plain path did not resolve' }}
if (-not $quoted.Command) {{ throw 'quoted path did not resolve' }}
'plain={{0}} quoted={{1}}' -f $plain.Command.Name, $quoted.Command.Name
"""


def function_source():
    """The function's own lines, from its `function` line to its closing brace."""
    lines = PROFILE.read_text().splitlines()
    start = next(i for i, line in enumerate(lines)
                 if line.startswith("        function global:Resolve-ScriptCommand {"))
    end = next(i for i in range(start + 1, len(lines)) if lines[i] == "        }")
    return "\n".join(lines[start:end + 1])


@unittest.skipUnless(shutil.which("pwsh"), "requires pwsh")
class ResolveScriptCommandTest(unittest.TestCase):
    def test_paths_with_a_single_quote_still_resolve(self):
        with tempfile.TemporaryDirectory() as temp:
            harness = pathlib.Path(temp, "harness.ps1")
            harness.write_text(HARNESS.format(function_text=function_source()))
            result = subprocess.run(
                [shutil.which("pwsh"), "-NoProfile", "-File", str(harness)],
                capture_output=True, text=True, timeout=60,
            )
        self.assertEqual(result.returncode, 0, result.stderr[-800:])
        self.assertIn("plain=script_handler_", result.stdout)
        self.assertIn("quoted=script_handler_", result.stdout)
