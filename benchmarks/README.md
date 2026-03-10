## Benchmark Harness

Run the local benchmark suite from the repository root:

```powershell
py -3.13 benchmarks/run_benchmarks.py
```

What it does:

- generates deterministic local `.wav` fixtures in `benchmarks/workspace/fixtures`
- evaluates note, chord, drum, silence, long-form, and smoke-test cases
- saves machine-readable JSON and a concise Markdown report in `benchmarks/results`

The suite is local-only. It does not upload audio.
