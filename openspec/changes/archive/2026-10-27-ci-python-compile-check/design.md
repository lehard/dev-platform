## Command

`python3 scripts/check_ci_python.py --workflow .github/workflows/ci.yml --job validate --compile template/scripts --compile scripts --compile tests`

All inputs are explicit arguments in `dev-platform/checks.toml`; the script has no defaults for them.

## Reading the CI version

`yaml.safe_load` (PyYAML is already required by the test suite) of the workflow. `jobs.<job>.steps` must contain exactly one step whose `uses` starts with `actions/setup-python@`; its `with.python-version` must be a string or number matching `^3\.\d+$`. Anything else refuses, naming the workflow, the job and what was found.

## Comparison

Local version is `sys.version_info[:2]` of the interpreter running the check, which is the `python3` that runs the rest of the full set. Equal: print `ci-python: local 3.x matches CI 3.x; the full set runs on the CI version` and exit 0.

Different: `shutil.which("python3.x")`; missing refuses with `local 3.13, CI 3.11: no python3.11 on PATH`. The found interpreter is asked for its `major.minor`; another answer refuses. Then `python3.x -m compileall -q <paths>`; non-zero exit fails with both versions and the compiler output tail. Success prints that only compilation was checked on the CI version.

Exit codes: 0 pass, 1 compile failure, 2 refusal (unreadable or unavailable input).

## Limit

Compilation catches syntax and compile-time limits of the CI version. Runtime behaviour differences (library behaviour, removed APIs used only at runtime) are not caught; required CI stays the merge gate.
