"""Core cryptographic and graph routines for the S-Box Graph Design Studio.

The construction follows the uploaded algorithm:
    directed graph -> adjacency matrix A -> choose degree-8 irreducible
    polynomial m(x) and affine vector b -> field inversion -> affine map
    -> evaluate cryptographic properties.

Only Python's standard library is required.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple, Dict, Any
import random
import re

CANDIDATE_POLYNOMIALS = [
    "111110101", "111100111", "111001111", "111110011",
    "110101001", "110001101", "110000111", "101110001",
    "101101001", "101100101", "101100011", "101011111",
    "101001101", "100101101", "100101011", "100011101",
]


def polynomial_expression(bits: str) -> str:
    bits = normalize_polynomial(bits)
    value = int(bits, 2)
    terms = []
    for p in range(8, -1, -1):
        if (value >> p) & 1:
            if p == 0:
                terms.append("1")
            elif p == 1:
                terms.append("x")
            else:
                terms.append(f"x^{p}")
    return " + ".join(terms)


def normalize_polynomial(value: str | int) -> str:
    if isinstance(value, int):
        n = value
    else:
        text = str(value).strip().lower().replace("_", "")
        if text.startswith("0x"):
            n = int(text, 16)
        elif re.fullmatch(r"[01]{9}", text):
            n = int(text, 2)
        else:
            raise ValueError("Polynomial must be a 9-bit binary string (e.g. 111110011) or hex (e.g. 0x1F3).")
    if n < 0x100 or n > 0x1FF:
        raise ValueError("A degree-8 monic polynomial must be a 9-bit value from 0x100 to 0x1FF.")
    return f"{n:09b}"


def _poly_degree(p: int) -> int:
    return p.bit_length() - 1


def _poly_mod(a: int, modulus: int) -> int:
    md = _poly_degree(modulus)
    while a and _poly_degree(a) >= md:
        a ^= modulus << (_poly_degree(a) - md)
    return a


def _poly_mul_mod(a: int, b: int, modulus: int) -> int:
    result = 0
    aa = a
    bb = b
    while bb:
        if bb & 1:
            result ^= aa
        bb >>= 1
        aa <<= 1
    return _poly_mod(result, modulus)


def _poly_gcd(a: int, b: int) -> int:
    while b:
        a, b = b, _poly_mod(a, b)
    return a


def is_irreducible_degree8(poly: str | int) -> bool:
    """Rabin-style irreducibility check for a monic degree-8 GF(2) polynomial."""
    bits = normalize_polynomial(poly)
    p = int(bits, 2)
    x = 0b10
    power = x
    # An irreducible degree-8 polynomial has no common factor with
    # x^(2^i)-x for i=1..4, and x^(2^8) == x mod p.
    for i in range(1, 9):
        power = _poly_mul_mod(power, power, p)
        if i <= 4 and _poly_gcd(power ^ x, p) != 1:
            return False
    return power == x


def gf_mul(a: int, b: int, modulus: int) -> int:
    """Multiply two bytes in GF(2^8) under the given 9-bit modulus."""
    a &= 0xFF
    b &= 0xFF
    low = modulus & 0xFF
    result = 0
    for _ in range(8):
        if b & 1:
            result ^= a
        b >>= 1
        carry = a & 0x80
        a = (a << 1) & 0xFF
        if carry:
            a ^= low
    return result & 0xFF


def gf_pow(a: int, exponent: int, modulus: int) -> int:
    result = 1
    base = a & 0xFF
    e = exponent
    while e:
        if e & 1:
            result = gf_mul(result, base, modulus)
        base = gf_mul(base, base, modulus)
        e >>= 1
    return result


def gf_inverse(a: int, modulus: int) -> int:
    if a == 0:
        return 0
    # For an irreducible degree-8 polynomial, GF(2^8)^* has order 255.
    return gf_pow(a, 254, modulus)


def parity(x: int) -> int:
    return x.bit_count() & 1


def validate_binary_vector(bits: str, n: int = 8) -> str:
    t = str(bits).strip().replace(" ", "")
    if not re.fullmatch(rf"[01]{{{n}}}", t):
        raise ValueError(f"Affine vector b must contain exactly {n} bits.")
    return t


def affine_transform(matrix: Sequence[Sequence[int]], x: int, b: int) -> int:
    if len(matrix) != 8 or any(len(row) != 8 for row in matrix):
        raise ValueError("S-box affine transformation requires an 8x8 matrix.")
    y = 0
    # Compatibility with the uploaded code: matrix row 0 controls output bit 7,
    # row 7 controls output bit 0; each row is interpreted as an 8-bit mask.
    for r, row in enumerate(matrix):
        row_mask = 0
        for bit in row:
            row_mask = (row_mask << 1) | (int(bit) & 1)
        out_bit = parity(row_mask & x)
        y |= out_bit << (7 - r)
    return (y ^ b) & 0xFF


def generate_sbox(matrix: Sequence[Sequence[int]], b_bits: str, polynomial: str | int) -> List[int]:
    poly_bits = normalize_polynomial(polynomial)
    if not is_irreducible_degree8(poly_bits):
        raise ValueError(f"Polynomial {poly_bits} is not irreducible over GF(2).")
    if gf2_rank(matrix) != 8:
        raise ValueError("Adjacency/affine matrix must have GF(2) rank 8 (nonsingular).")
    b_bits = validate_binary_vector(b_bits, 8)
    b = int(b_bits, 2)
    modulus = int(poly_bits, 2)
    return [affine_transform(matrix, gf_inverse(x, modulus), b) for x in range(256)]


def gf2_rank(matrix: Sequence[Sequence[int]]) -> int:
    if not matrix:
        return 0
    rows = []
    ncols = len(matrix[0])
    for row in matrix:
        if len(row) != ncols:
            raise ValueError("Matrix rows must have equal length.")
        mask = 0
        for v in row:
            mask = (mask << 1) | (int(v) & 1)
        rows.append(mask)
    rank = 0
    for col in range(ncols - 1, -1, -1):
        pivot = next((r for r in range(rank, len(rows)) if (rows[r] >> col) & 1), None)
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        for r in range(len(rows)):
            if r != rank and ((rows[r] >> col) & 1):
                rows[r] ^= rows[rank]
        rank += 1
        if rank == len(rows):
            break
    return rank


def matrix_from_edges(n: int, edges: Iterable[Tuple[int, int]]) -> List[List[int]]:
    if n < 1:
        raise ValueError("Number of vertices must be positive.")
    m = [[0] * n for _ in range(n)]
    for u, v in edges:
        if not (0 <= u < n and 0 <= v < n):
            raise ValueError(f"Edge ({u}, {v}) is outside vertex range 0..{n-1}.")
        m[u][v] = 1
    return m


def edges_from_matrix(matrix: Sequence[Sequence[int]]) -> List[Tuple[int, int]]:
    return [(i, j) for i, row in enumerate(matrix) for j, v in enumerate(row) if int(v) & 1]


def matrix_to_text(matrix: Sequence[Sequence[int]]) -> str:
    return "\n".join(" ".join(str(int(v) & 1) for v in row) for row in matrix)


def parse_matrix(text: str, expected_n: int | None = None) -> List[List[int]]:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    rows: List[List[int]] = []
    for ln in lines:
        compact = re.sub(r"[\s,;|\[\](){}]", "", ln)
        if re.fullmatch(r"[01]+", compact):
            row = [int(c) for c in compact]
        else:
            tokens = re.findall(r"[01]", ln)
            row = [int(t) for t in tokens]
        if row:
            rows.append(row)
    if not rows:
        raise ValueError("No matrix data found.")
    ncols = len(rows[0])
    if any(len(r) != ncols for r in rows):
        raise ValueError("All matrix rows must have the same number of entries.")
    if expected_n is not None and (len(rows) != expected_n or ncols != expected_n):
        raise ValueError(f"Expected a {expected_n}x{expected_n} matrix.")
    if len(rows) != ncols:
        raise ValueError("Adjacency matrix must be square.")
    return rows


def parse_edge_list(text: str, n: int, numbering: str = "1..N") -> List[Tuple[int, int]]:
    """Parse edges like '1->2', '1 2', '(1,2)', one or many per line."""
    pairs = re.findall(r"(-?\d+)\s*(?:->|,|\s+)\s*(-?\d+)", text)
    if not pairs and text.strip():
        raise ValueError("Could not parse edge list. Use formats such as 1->2, 1 2, or (1,2).")
    edges = []
    one_based = numbering == "1..N"
    for a, b in pairs:
        u, v = int(a), int(b)
        if one_based:
            u -= 1
            v -= 1
        if not (0 <= u < n and 0 <= v < n):
            label = "1..N" if one_based else "0..N-1"
            raise ValueError(f"Edge ({a},{b}) is outside selected vertex numbering {label}.")
        edges.append((u, v))
    return list(dict.fromkeys(edges))


def random_nonsingular_matrix(n: int = 8, edge_count: int = 31, allow_loops: bool = True,
                              rng: random.Random | None = None, max_attempts: int = 10000) -> List[List[int]]:
    rng = rng or random.Random()
    possible = [(i, j) for i in range(n) for j in range(n) if allow_loops or i != j]
    if edge_count < 0 or edge_count > len(possible):
        raise ValueError(f"Edge count must be between 0 and {len(possible)} for this graph setting.")
    for _ in range(max_attempts):
        edges = rng.sample(possible, edge_count)
        m = matrix_from_edges(n, edges)
        if gf2_rank(m) == n:
            return m
    raise RuntimeError(f"Could not find a nonsingular {n}x{n} matrix with {edge_count} edges after {max_attempts} attempts.")


def _fwht(values: List[int]) -> List[int]:
    a = values[:]
    h = 1
    n = len(a)
    while h < n:
        for i in range(0, n, h * 2):
            for j in range(i, i + h):
                x = a[j]
                y = a[j + h]
                a[j] = x + y
                a[j + h] = x - y
        h *= 2
    return a


def _component_walsh(sbox: Sequence[int], mask: int) -> List[int]:
    signs = [1 if parity(mask & int(y)) == 0 else -1 for y in sbox]
    return _fwht(signs)


def vectorial_nonlinearity(sbox: Sequence[int]) -> Tuple[int, int, List[int], int]:
    nls = []
    max_abs_walsh = 0
    for mask in range(1, 256):
        w = _component_walsh(sbox, mask)
        ma = max(abs(v) for v in w)
        max_abs_walsh = max(max_abs_walsh, ma)
        nls.append(128 - ma // 2)
    return min(nls), max(nls), nls, max_abs_walsh


def coordinate_nonlinearities(sbox: Sequence[int]) -> List[int]:
    out = []
    for bit in range(8):
        w = _component_walsh(sbox, 1 << bit)
        out.append(128 - max(abs(v) for v in w) // 2)
    return out


def linear_metrics(sbox: Sequence[int]) -> Tuple[int, float, float, int]:
    """Return max |LAT|, LP/bias, max approximation probability, max equal-count.

    The uploaded program computes an imbalance and then divides by two. This is
    equivalent to max|LAT|/(2*256). For AES-like S-boxes with max |LAT|=32,
    LP/bias is 0.0625 and the maximum equal-count is 144.
    """
    max_abs = 0
    for out_mask in range(1, 256):
        w = _component_walsh(sbox, out_mask)
        # Input mask 0 is harmless for a permutation, but keep the standard a!=0 convention.
        local = max(abs(w[a]) for a in range(1, 256))
        if local > max_abs:
            max_abs = local
    lp_bias = max_abs / 512.0
    max_prob = 0.5 + lp_bias
    max_count = int((256 + max_abs) // 2)
    return max_abs, lp_bias, max_prob, max_count


def differential_uniformity(sbox: Sequence[int]) -> Tuple[int, Tuple[int, int] | None]:
    max_du = 0
    arg = None
    for a in range(1, 256):
        counts = [0] * 256
        for x in range(256):
            counts[int(sbox[x]) ^ int(sbox[x ^ a])] += 1
        local = max(counts)
        if local > max_du:
            max_du = local
            arg = (a, counts.index(local))
    return max_du, arg


def ddt_table(sbox: Sequence[int]) -> List[List[int]]:
    table = []
    for a in range(256):
        counts = [0] * 256
        for x in range(256):
            counts[int(sbox[x]) ^ int(sbox[x ^ a])] += 1
        table.append(counts)
    return table


def lat_table(sbox: Sequence[int]) -> List[List[int]]:
    # Rows=input mask a, cols=output mask b.
    table = [[0] * 256 for _ in range(256)]
    table[0][0] = 256
    for b in range(1, 256):
        w = _component_walsh(sbox, b)
        for a in range(256):
            table[a][b] = w[a]
    return table


def sac_matrix(sbox: Sequence[int]) -> List[List[float]]:
    sac = [[0.0] * 8 for _ in range(8)]
    for in_bit in range(8):
        delta = 1 << in_bit
        for x in range(256):
            diff = int(sbox[x]) ^ int(sbox[x ^ delta])
            for out_bit in range(8):
                sac[in_bit][out_bit] += (diff >> out_bit) & 1
        for out_bit in range(8):
            sac[in_bit][out_bit] /= 256.0
    return sac


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _population_std(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    mu = _mean(values)
    return (sum((v - mu) ** 2 for v in values) / len(values)) ** 0.5


def fixed_points(sbox: Sequence[int]) -> List[int]:
    return [x for x, y in enumerate(sbox) if int(y) == x]


def opposite_fixed_points(sbox: Sequence[int]) -> List[int]:
    return [x for x, y in enumerate(sbox) if int(y) == (x ^ 0xFF)]


def cycle_structure(sbox: Sequence[int]) -> List[int]:
    if len(set(map(int, sbox))) != len(sbox):
        return []
    visited = [False] * len(sbox)
    lengths = []
    for start in range(len(sbox)):
        if visited[start]:
            continue
        cur = start
        length = 0
        while not visited[cur]:
            visited[cur] = True
            cur = int(sbox[cur])
            length += 1
        lengths.append(length)
    return sorted(lengths, reverse=True)


def algebraic_degrees(sbox: Sequence[int]) -> List[int]:
    degrees = []
    for bit in range(8):
        coeff = [(int(y) >> bit) & 1 for y in sbox]
        for i in range(8):
            step = 1 << i
            for mask in range(256):
                if mask & step:
                    coeff[mask] ^= coeff[mask ^ step]
        deg = 0
        for mask, c in enumerate(coeff):
            if c:
                deg = max(deg, mask.bit_count())
        degrees.append(deg)
    return degrees


def parse_sbox(text: str, base_mode: str = "auto") -> List[int]:
    cleaned = text.replace("[", " ").replace("]", " ").replace("{", " ").replace("}", " ")
    tokens = re.findall(r"0x[0-9a-fA-F]+|\b[0-9a-fA-F]{1,2}\b|\b\d{1,3}\b", cleaned)
    if len(tokens) != 256:
        raise ValueError(f"Expected exactly 256 S-box values; found {len(tokens)}.")
    mode = base_mode.strip().lower()
    if mode not in {"auto", "decimal", "hex"}:
        raise ValueError("base_mode must be auto, decimal, or hex.")
    if mode == "auto":
        # A conventional hex LUT normally contains A-F (or 0x prefixes). Once such
        # evidence is present, parse the complete table consistently as hexadecimal.
        mode = "hex" if any(t.lower().startswith("0x") or re.search(r"[a-fA-F]", t) for t in tokens) else "decimal"
    values = []
    for tok in tokens:
        if tok.lower().startswith("0x"):
            v = int(tok, 16)
        else:
            v = int(tok, 16 if mode == "hex" else 10)
        if not 0 <= v <= 255:
            raise ValueError(f"S-box value {tok} is outside 0..255.")
        values.append(v)
    return values


def sbox_to_hex_grid(sbox: Sequence[int]) -> str:
    return "\n".join(" ".join(f"{int(sbox[16*r+c]):02X}" for c in range(16)) for r in range(16))


def sbox_to_decimal_grid(sbox: Sequence[int]) -> str:
    return "\n".join(" ".join(f"{int(sbox[16*r+c]):3d}" for c in range(16)) for r in range(16))


def evaluate_sbox(sbox: Sequence[int]) -> Dict[str, Any]:
    if len(sbox) != 256:
        raise ValueError("An 8x8 S-box must contain exactly 256 entries.")
    values = [int(v) for v in sbox]
    if any(v < 0 or v > 255 for v in values):
        raise ValueError("S-box entries must be in 0..255.")

    bijective = len(set(values)) == 256
    nl_min, nl_max, _all_nl, max_abs_walsh = vectorial_nonlinearity(values)
    coord_nl = coordinate_nonlinearities(values)
    lat_max, lp_bias, max_prob, max_count = linear_metrics(values)
    du, du_arg = differential_uniformity(values)
    sac = sac_matrix(values)
    sac_flat = [v for row in sac for v in row]
    fp = fixed_points(values)
    ofp = opposite_fixed_points(values)
    cycles = cycle_structure(values) if bijective else []
    degrees = algebraic_degrees(values)

    return {
        "bijective": bijective,
        "unique_outputs": len(set(values)),
        "nonlinearity_min": nl_min,
        "nonlinearity_max": nl_max,
        "coordinate_nonlinearities": coord_nl,
        "max_abs_walsh": max_abs_walsh,
        "lat_max_abs": lat_max,
        "lp_bias": lp_bias,
        "max_linear_probability": max_prob,
        "max_linear_count": max_count,
        "differential_uniformity": du,
        "du_argmax": du_arg,
        "sac_matrix": sac,
        "sac_min": min(sac_flat),
        "sac_max": max(sac_flat),
        "sac_mean": _mean(sac_flat),
        "sac_std": _population_std(sac_flat),
        "fixed_points": fp,
        "opposite_fixed_points": ofp,
        "fixed_total": len(fp) + len(ofp),
        "cycle_count": len(cycles),
        "cycle_lengths": cycles,
        "component_degrees": degrees,
        "algebraic_degree": max(degrees),
    }


def paper_sac_filter(metrics: Dict[str, Any]) -> bool:
    """Filter reproduced from the uploaded Word algorithm (with numerical tolerance)."""
    avg = float(metrics["sac_mean"])
    mn = float(metrics["sac_min"])
    mx = float(metrics["sac_max"])
    sd = float(metrics["sac_std"])
    return abs(avg - 0.5) < 1e-12 or ((mn > 0.45) and (mx < 0.56)) or (sd < 0.027)


def strict_filter(metrics: Dict[str, Any], thresholds: Dict[str, float | int | bool]) -> bool:
    if metrics["nonlinearity_min"] < int(thresholds.get("nl_min", 112)):
        return False
    if metrics["differential_uniformity"] > int(thresholds.get("du_max", 4)):
        return False
    if metrics["lp_bias"] > float(thresholds.get("lp_max", 0.0625)) + 1e-15:
        return False
    if metrics["sac_min"] < float(thresholds.get("sac_min", 0.45)):
        return False
    if metrics["sac_max"] > float(thresholds.get("sac_max", 0.56)):
        return False
    if metrics["sac_std"] > float(thresholds.get("sac_std_max", 0.027)):
        return False
    if thresholds.get("require_zero_fp", False) and metrics["fixed_total"] != 0:
        return False
    return True


def quality_score(metrics: Dict[str, Any]) -> float:
    """A transparent ranking score for search UI; not a cryptographic theorem."""
    score = 100.0
    score -= max(0, 112 - metrics["nonlinearity_min"]) * 2.5
    score -= max(0, metrics["differential_uniformity"] - 4) * 3.0
    score -= max(0.0, metrics["lp_bias"] - 0.0625) * 120.0
    score -= abs(metrics["sac_mean"] - 0.5) * 80.0
    score -= metrics["sac_std"] * 100.0
    score -= metrics["fixed_total"] * 0.5
    return round(score, 4)


@dataclass
class CandidateResult:
    iteration: int
    polynomial: str
    b_bits: str
    matrix: List[List[int]]
    sbox: List[int]
    metrics: Dict[str, Any]
    score: float

