# S-Box Graph Design Studio

A desktop GUI for generating and evaluating 8×8 S-boxes using the uploaded graph-based algorithm:

**directed graph → adjacency matrix → degree-8 irreducible polynomial + affine vector b → GF(2^8) inversion → affine transformation → cryptographic evaluation**

The interface is in English and uses only Python's standard library (`tkinter` included with normal Windows Python installations).

## Main features

- 16 supplied candidate degree-8 irreducible polynomials.
- Manual or random polynomial selection.
- Manual or random 8-bit affine constant `b`.
- Manual edge entry (`1->2`, `1 2`, `(1,2)`) or manual adjacency matrix entry.
- Random directed graph generation with an exact edge count.
- **Nonsingularity checked over GF(2)**.
- Directed graph visualization directly in the GUI.
- Graph export as SVG.
- S-box generation for an 8×8 full-rank affine matrix.
- Independent evaluator for any pasted 256-entry S-box.
- Reproducible random search with a seed.
- Random search over adjacency matrices, the supplied polynomial set and `b`.
- The supplied paper's SAC acceptance rule, plus a stricter AND-threshold mode.
- CSV/JSON export of parameters, S-box and results.
- Full DDT and LAT export.

## Evaluated properties

- Bijectivity and number of unique outputs
- Vectorial nonlinearity: minimum and maximum over nonzero component masks
- Coordinate nonlinearities
- Maximum absolute Walsh coefficient
- Maximum absolute LAT coefficient
- LP / maximum linear bias (`max |LAT| / 512`)
- Maximum linear approximation probability and equal-count
- Differential uniformity (DU)
- 8×8 SAC matrix
- SAC minimum, maximum, mean and population standard deviation
- Fixed points (FP)
- Opposite fixed points (OFP)
- Cycle count and cycle lengths
- Component algebraic degrees and maximum algebraic degree

## Candidate polynomials

The exact 16 values supplied for the project are included:

```text
111110101
111100111
111001111
111110011
110101001
110001101
110000111
101110001
101101001
101100101
101100011
101011111
101001101
100101101
100101011
100011101
```

The UI validates any custom 9-bit monic degree-8 polynomial for irreducibility over GF(2) before S-box generation.

## Windows quick start

1. Install Python 3.10+ from python.org. During installation, enable **Add Python to PATH**.
2. Extract this ZIP.
3. Double-click `run_windows.bat`.

Or open Command Prompt in the project directory and run:

```bat
py -3 app.py
```

No `pip install` step is required for the GUI.

## Linux

Run:

```bash
python3 app.py
```

If Tkinter is not installed, install your distribution's Tk package (for example `python3-tk` on Debian/Ubuntu).

## How to generate an S-box

1. Open **Generator & Graph**.
2. Keep `Vertices = 8` for an 8×8 S-box.
3. Enter the number of directed edges, e.g. `31`.
4. Click **Random Nonsingular Graph**, or type edges/matrix manually.
5. Select one of the supplied irreducible polynomials or type a custom one.
6. Enter an 8-bit `b` or click **Random b**.
7. Click **Generate S-box + Evaluate**.
8. View the metrics and LUT under **Results & Export**.

## How to evaluate an existing S-box

1. Open **S-box Evaluator**.
2. Paste exactly 256 values.
3. Select `Auto`, `Decimal`, or `Hex`.
4. Click **Evaluate Pasted S-box**.

For a conventional hex LUT such as `63 7C 77 ...`, select **Hex** explicitly for maximum clarity.

## How random search works

Random Search generates a new nonsingular adjacency matrix for every trial. It can choose a polynomial from all 16 supplied candidates (or keep the current polynomial), randomize `b`, generate the S-box, and compute the full metric set.

The `Paper SAC rule (OR)` reproduces the supplied condition:

```text
AVG_SAC == 0.5
OR (MIN_SAC > 0.45 AND MAX_SAC < 0.56)
OR Square_dev < 0.027
```

The `Strict thresholds (AND)` rule lets you require NL, DU, LP, SAC interval/std and optionally FP+OFP=0 simultaneously.

## Reproducibility

Enter a seed in the Generator tab. The same seed and the same settings reproduce the random graph/search sequence. Search CSV export records the polynomial, `b`, matrix, S-box and metrics for every trial.

## Matrix bit convention

For compatibility with the uploaded source algorithm, matrix row 0 controls output bit 7 and matrix row 7 controls output bit 0. Each matrix row is interpreted as an 8-bit mask. The result is XORed with the 8-bit affine constant `b`.

## Important scientific note

A high score or good individual cryptographic metrics do not constitute a proof that an S-box or a cipher using it is secure. The search score is only a transparent ranking aid. Security claims should be based on the individual cryptographic criteria, structural analysis, and the security of the complete cipher construction.

## Files

- `app.py` — Tkinter GUI
- `sbox_core.py` — finite-field operations, S-box construction, metrics, graph/matrix utilities
- `test_core.py` — self-tests
- `candidate_polynomials.csv` — supplied polynomial list with hex and algebraic form
- `run_windows.bat` — Windows launcher
- `build_exe_windows.bat` — optional PyInstaller helper
- `requirements.txt` — documents that the application itself has no third-party runtime dependencies

## Self-test

```bash
python test_core.py
```

You should see `All core tests passed.`
