from sbox_core import *

# AES affine matrix represented with the same row/output-bit convention used by this project.
# These tests focus on invariants rather than forcing an AES LUT orientation.

def run():
    for p in CANDIDATE_POLYNOMIALS:
        assert is_irreducible_degree8(p), p

    rng = random.Random(12345)
    m = random_nonsingular_matrix(8, 31, True, rng)
    assert gf2_rank(m) == 8
    assert len(edges_from_matrix(m)) == 31

    p = "111110011"
    b = "10010101"
    s = generate_sbox(m, b, p)
    assert len(s) == 256
    assert len(set(s)) == 256
    metrics = evaluate_sbox(s)
    assert metrics["bijective"]
    assert metrics["differential_uniformity"] >= 2
    assert 0.0 <= metrics["sac_mean"] <= 1.0
    assert sum(metrics["cycle_lengths"]) == 256

    # Round-trip matrix text.
    m2 = parse_matrix(matrix_to_text(m), 8)
    assert m2 == m

    # Edge parser, 1-based mode.
    e = parse_edge_list("1->2\n2,3\n3 4", 8, "1..N")
    assert e == [(0,1),(1,2),(2,3)]
    print("All core tests passed.")
    print("Polynomial:", p, polynomial_expression(p))
    print("Sample metrics:", {k: metrics[k] for k in ["nonlinearity_min","differential_uniformity","lp_bias","sac_mean"]})

if __name__ == "__main__":
    run()
