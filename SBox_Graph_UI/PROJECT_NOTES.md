# Implementation notes relative to the supplied algorithm

The supplied Word algorithm selects one polynomial from the provided candidate list, generates an S-box from the adjacency matrix, affine constant and polynomial, then evaluates nonlinearity, LP, SAC, differential uniformity, fixed/opposite fixed points and cycles before applying the SAC-based acceptance condition.

This implementation preserves that workflow while making the following engineering corrections/clarifications:

1. **Polynomial is a real runtime parameter.** The supplied Python prototype hard-coded `111110011` inside field multiplication even though the Word algorithm shows random polynomial selection. Here the selected/manual polynomial is passed into every GF(2^8) multiplication and inversion operation.
2. **Matrix rank is computed over GF(2).** Floating-point `numpy.linalg.matrix_rank` is not the correct algebraic test for a binary affine matrix. The project uses binary Gaussian elimination.
3. **Irreducibility is validated.** A custom degree-8 polynomial must pass a GF(2) irreducibility test before generation.
4. **LP is reported transparently.** The UI reports maximum |LAT|, LP/max bias = max|LAT|/(2·256), maximum approximation probability = 0.5+LP, and the corresponding equal-count.
5. **Both generation and independent evaluation are supported.** A pasted 256-entry S-box can be analyzed without any graph or polynomial parameters.
6. **Reproducibility is explicit.** A seed controls random graph/polynomial/b generation and all search results can be exported.
7. **Graph visualization is built in.** Edge lists and matrices are interchangeable, and the directed graph can be exported as SVG.
