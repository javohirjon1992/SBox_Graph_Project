# Graph-Based Static S-Box Construction: Software and 100,000-Candidate Dataset

This repository contains the software implementation and experimental dataset associated with the study:

**“A Vertex-Edge Affine Mapping Approach for Constructing Cryptographically Strong Static S-boxes in Symmetric-Key Cryptography”**

The repository is intended to support reproducibility, independent verification, and further research on graph-based affine representations for 8×8 substitution-box construction.

---

## Repository Structure

```text
Graph-Based-SBox-Construction/
│
├── SBox_Graph_UI_Project/
│   ├── app.py
│   ├── sbox_core.py
│   ├── test_core.py
│   ├── candidate_polynomials.csv
│   ├── requirements.txt
│   ├── run_windows.bat
│   ├── build_exe_windows.bat
│   ├── SBoxGraphDesignStudio.spec
│   ├── PROJECT_NOTES.md
│   └── README.md
│
├── 100000_SBoxes_Data/
│   ├── 100000_SBoxes_GraphFirst.csv
│   └── 100000_SBoxes_Summary.csv
│
└── README.md
```

The repository has two main components:

1. **`SBox_Graph_UI_Project/`** — source code and graphical interface for S-box generation and evaluation.
2. **`100000_SBoxes_Data/`** — experimental CSV data from the large-scale evaluation of 100,000 candidate parameter combinations.

---

## Method Overview

The implemented construction generates an 8×8 S-box using

\[
S_{A,b,m}(x)=A\,\rho_m(x)\oplus b,
\]

where:

- \(A\in GF(2)^{8\times8}\) is a nonsingular binary matrix represented as the adjacency matrix of an eight-vertex directed graph;
- \(b\in GF(2)^8\) is an 8-bit affine constant;
- \(m(x)\) is an irreducible polynomial of degree 8 defining the representation of \(GF(2^8)\);
- \(\rho_m(x)\) denotes multiplicative inversion in \(GF(2^8)\), with \(\rho_m(0)=0\).

A graph-derived matrix is admitted to the S-box construction stage only when

\[
\operatorname{rank}_{GF(2)}(A)=8.
\]

For every admissible parameter tuple

\[
\Theta=(A,b,m(x)),
\]

a complete 256-entry S-box is generated and evaluated.

---

## Search and Screening Procedure

The graph representation is used as a structured representation of candidate binary matrices. It does **not** by itself reduce or exhaustively traverse the full space of invertible 8×8 binary matrices.

The implemented workflow follows the sequence

```text
Generate candidate graph/matrix
        ↓
Check rank over GF(2)
        ↓
Reject singular matrices
        ↓
Select affine constant b
        ↓
Select irreducible polynomial m(x)
        ↓
Generate the 256-entry S-box
        ↓
Evaluate cryptographic properties
        ↓
Retain or reject the candidate
```

The candidate-generation stage may be stochastic, whereas candidate acceptance is based on explicit structural and cryptographic criteria.

The reported large-scale experiment evaluates **100,000 candidate parameter combinations**. This should be interpreted as a constrained computational search and screening experiment rather than as an exhaustive search over all invertible 8×8 matrices. No claim of global optimality is made.

---

## Cryptographic Properties Evaluated

The software evaluates the following properties:

- bijectivity;
- number of unique outputs;
- vectorial nonlinearity;
- coordinate nonlinearities;
- Walsh–Hadamard spectrum;
- linear approximation characteristics;
- maximum absolute LAT coefficient;
- linear bias / LP;
- differential distribution table;
- differential uniformity (DU);
- strict avalanche criterion (SAC);
- SAC minimum, maximum, mean, and deviation;
- algebraic degree;
- fixed points (FP);
- opposite fixed points (OFP);
- permutation cycle structure.

The software can also export complete DDT and LAT tables for additional analysis.

---

## 1. Software: `SBox_Graph_UI_Project`

`SBox_Graph_UI_Project` contains the graphical and computational implementation of the proposed S-box construction framework.

### Main Files

- `app.py` — graphical user interface;
- `sbox_core.py` — finite-field arithmetic, S-box generation, graph/matrix utilities, and cryptographic evaluation routines;
- `test_core.py` — core verification tests;
- `candidate_polynomials.csv` — candidate degree-8 irreducible polynomials;
- `PROJECT_NOTES.md` — implementation notes and methodological clarifications;
- `requirements.txt` — runtime dependency information;
- `run_windows.bat` — Windows launcher;
- `build_exe_windows.bat` — optional Windows executable build script;
- `SBoxGraphDesignStudio.spec` — PyInstaller configuration.

### Main Software Capabilities

The interface supports:

- random or manual graph definition;
- manual adjacency-matrix entry;
- nonsingularity testing over \(GF(2)\);
- random graph generation;
- directed-graph visualization;
- SVG graph export;
- manual or random affine constant selection;
- selection of supplied irreducible polynomials;
- validation of custom degree-8 irreducible polynomials;
- complete 8×8 S-box generation;
- evaluation of independently supplied 256-entry S-boxes;
- random parameter search with a reproducible seed;
- CSV and JSON export;
- complete DDT and LAT export.

---

## Running the Software

### Windows

Python 3.10 or newer is recommended.

After cloning or downloading the repository:

```bash
cd SBox_Graph_UI_Project
```

Run:

```bash
python app.py
```

Windows users may also run:

```text
run_windows.bat
```

The application itself does not require third-party Python packages for normal execution. `tkinter` is included in standard Windows Python installations.

### Linux

Run:

```bash
cd SBox_Graph_UI_Project
python3 app.py
```

If Tkinter is not installed, install the appropriate Tk package for your Linux distribution.

---

## Self-Test

To verify the main computational routines, run:

```bash
cd SBox_Graph_UI_Project
python test_core.py
```

A successful execution should report:

```text
All core tests passed.
```

---

## 2. Experimental Data: `100000_SBoxes_Data`

This folder contains the data produced during the large-scale candidate evaluation.

### Files

#### `100000_SBoxes_GraphData.csv`

Contains detailed results associated with the generated and evaluated candidate S-box parameter combinations.

#### `100000_SBoxes_Summary.csv`

Contains the corresponding summary information derived from the 100,000-candidate experiment.

These files are provided to make the computational study auditable and to allow independent analysis of the reported search results.

---

## Reproducibility

The search software supports seed-controlled random generation. When the same software version, seed, search settings, candidate polynomial set, and parameter ranges are used, the candidate-generation sequence can be reproduced.

For each evaluated candidate, the software can record information including:

- graph/adjacency matrix;
- affine constant \(b\);
- irreducible polynomial \(m(x)\);
- generated 256-entry S-box;
- cryptographic evaluation results.

The CSV dataset is included so that the large-scale experiment can be inspected without rerunning the complete search.

---

## Important Scientific Scope

The nonlinear core of the construction is multiplicative inversion over \(GF(2^8)\), followed by an invertible affine output transformation.

Accordingly, the graph representation should be interpreted as a parameterization of the linear affine layer, not as a claim that graph encoding alone creates a new affine-equivalence class or automatically improves every cryptographic property.

Likewise:

- nonsingularity of \(A\) guarantees invertibility of the linear affine layer;
- it does not by itself imply the MDS property;
- the reported graph is a retained candidate, not a proven global optimum;
- strong individual S-box metrics do not by themselves prove the security of a complete block cipher.

These distinctions are important for the correct interpretation of the software and dataset.

---

## Data and Software Use

The repository may be used for:

- reproduction of the reported experiments;
- independent verification of S-box metrics;
- comparison of graph-derived affine matrices;
- analysis of SAC, DU, nonlinearity, LAT, DDT, FP, and OFP behavior;
- development of alternative candidate-screening rules;
- further research on static or parameterized S-box construction.

If the software or dataset is modified, the modified methodology and parameter settings should be reported clearly when publishing derived results.

---

## Associated Manuscript

**Title:**  
*A Vertex-Edge Affine Mapping Approach for Constructing Cryptographically Strong Static S-boxes in Symmetric-Key Cryptography*

Full bibliographic information and DOI can be added here after publication.

---

## Citation

If you use this repository in academic work, please cite the associated article once its final bibliographic information becomes available.

A citation entry will be added after publication.

---

## License

A software/data license has not yet been specified in this repository.

Before public release, it is recommended to add an appropriate `LICENSE` file indicating the permitted terms of software and dataset reuse.

---

## Contact

For questions related to the implementation, experimental dataset, or reproducibility of the reported results, please contact the corresponding author of the associated manuscript.
