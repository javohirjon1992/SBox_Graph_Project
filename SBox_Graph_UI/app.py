"""S-Box Graph Design Studio - English desktop UI.

Run:
    python app.py

No third-party packages are required. Tkinter is included with normal Windows
Python installations from python.org.
"""
from __future__ import annotations

import csv
import json
import math
import os
import queue
import random
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Any, Dict, List, Tuple

from sbox_core import (
    CANDIDATE_POLYNOMIALS,
    CandidateResult,
    algebraic_degrees,
    ddt_table,
    edges_from_matrix,
    evaluate_sbox,
    generate_sbox,
    gf2_rank,
    is_irreducible_degree8,
    lat_table,
    matrix_from_edges,
    matrix_to_text,
    normalize_polynomial,
    paper_sac_filter,
    parse_edge_list,
    parse_matrix,
    parse_sbox,
    polynomial_expression,
    quality_score,
    random_nonsingular_matrix,
    sbox_to_decimal_grid,
    sbox_to_hex_grid,
    strict_filter,
)

APP_TITLE = "S-Box Graph Design Studio"
APP_VERSION = "1.0"


class SBoxStudio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_TITLE} v{APP_VERSION}")
        self.geometry("1450x900")
        self.minsize(1180, 720)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        self.style.configure("Section.TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        self.style.configure("Metric.Treeview", rowheight=25)

        self.current_matrix: List[List[int]] = []
        self.current_sbox: List[int] | None = None
        self.current_metrics: Dict[str, Any] | None = None
        self.current_context: Dict[str, Any] = {}
        self.search_results: List[CandidateResult] = []
        self.search_stop = threading.Event()
        self.search_queue: queue.Queue = queue.Queue()
        self.search_thread: threading.Thread | None = None

        self._build_ui()
        self._load_initial_example()
        self.after(100, self._poll_search_queue)

    # -------------------- UI construction --------------------
    def _build_ui(self):
        top = ttk.Frame(self, padding=(12, 8))
        top.pack(fill="x")
        ttk.Label(top, text=APP_TITLE, style="Title.TLabel").pack(side="left")
        ttk.Label(top, text="Graph-derived GF(2^8) S-box generation, evaluation, and reproducible random search",
                  foreground="#555").pack(side="left", padx=18)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.tab_generator = ttk.Frame(self.notebook)
        self.tab_evaluator = ttk.Frame(self.notebook)
        self.tab_search = ttk.Frame(self.notebook)
        self.tab_results = ttk.Frame(self.notebook)
        self.tab_about = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_generator, text="Generator & Graph")
        self.notebook.add(self.tab_evaluator, text="S-box Evaluator")
        self.notebook.add(self.tab_search, text="Random Search")
        self.notebook.add(self.tab_results, text="Results & Export")
        self.notebook.add(self.tab_about, text="Method & Help")

        self._build_generator_tab()
        self._build_evaluator_tab()
        self._build_search_tab()
        self._build_results_tab()
        self._build_about_tab()

        status = ttk.Frame(self, padding=(10, 3))
        status.pack(fill="x", side="bottom")
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(status, textvariable=self.status_var).pack(side="left")

    def _build_generator_tab(self):
        pane = ttk.Panedwindow(self.tab_generator, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=8)
        left = ttk.Frame(pane, padding=4)
        right = ttk.Frame(pane, padding=4)
        pane.add(left, weight=3)
        pane.add(right, weight=2)

        # Graph settings
        graph_box = ttk.LabelFrame(left, text="1. Directed graph / adjacency matrix", style="Section.TLabelframe", padding=8)
        graph_box.pack(fill="x")

        row = ttk.Frame(graph_box)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Vertices:").pack(side="left")
        self.vertices_var = tk.IntVar(value=8)
        ttk.Spinbox(row, from_=2, to=20, textvariable=self.vertices_var, width=5).pack(side="left", padx=(4, 14))
        ttk.Label(row, text="Edges:").pack(side="left")
        self.edges_count_var = tk.IntVar(value=31)
        ttk.Spinbox(row, from_=0, to=400, textvariable=self.edges_count_var, width=6).pack(side="left", padx=(4, 14))
        self.allow_loops_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row, text="Allow self-loops", variable=self.allow_loops_var).pack(side="left", padx=(0, 14))
        ttk.Label(row, text="Vertex numbering:").pack(side="left")
        self.numbering_var = tk.StringVar(value="1..N")
        ttk.Combobox(row, textvariable=self.numbering_var, values=["1..N", "0..N-1"], state="readonly", width=8).pack(side="left", padx=4)

        row2 = ttk.Frame(graph_box)
        row2.pack(fill="x", pady=3)
        ttk.Label(row2, text="Random seed (optional):").pack(side="left")
        self.seed_var = tk.StringVar(value="20260914")
        ttk.Entry(row2, textvariable=self.seed_var, width=16).pack(side="left", padx=5)
        ttk.Button(row2, text="Random Nonsingular Graph", command=self.random_graph).pack(side="left", padx=5)
        ttk.Button(row2, text="Matrix ← Edges", command=self.matrix_from_edges_ui).pack(side="left", padx=5)
        ttk.Button(row2, text="Edges ← Matrix", command=self.edges_from_matrix_ui).pack(side="left", padx=5)
        ttk.Button(row2, text="Draw Graph", command=self.draw_graph_from_ui).pack(side="left", padx=5)

        data_pane = ttk.Panedwindow(graph_box, orient="horizontal")
        data_pane.pack(fill="both", expand=True, pady=(6, 3))
        ef = ttk.Frame(data_pane)
        mf = ttk.Frame(data_pane)
        data_pane.add(ef, weight=1)
        data_pane.add(mf, weight=1)
        ttk.Label(ef, text="Edge list (e.g. 1->2, 2->3):").pack(anchor="w")
        self.edge_text = tk.Text(ef, height=13, width=28, font=("Consolas", 9), wrap="none")
        self.edge_text.pack(fill="both", expand=True, padx=(0, 5))
        ttk.Label(mf, text="Adjacency matrix (binary):").pack(anchor="w")
        self.matrix_text = tk.Text(mf, height=13, width=38, font=("Consolas", 9), wrap="none")
        self.matrix_text.pack(fill="both", expand=True)
        self.matrix_info_var = tk.StringVar(value="Matrix: not loaded")
        ttk.Label(graph_box, textvariable=self.matrix_info_var).pack(anchor="w", pady=(4, 0))

        # Field + affine settings
        field_box = ttk.LabelFrame(left, text="2. GF(2^8) polynomial and affine vector", style="Section.TLabelframe", padding=8)
        field_box.pack(fill="x", pady=(8, 0))
        prow = ttk.Frame(field_box)
        prow.pack(fill="x", pady=2)
        ttk.Label(prow, text="Irreducible polynomial:").pack(side="left")
        self.poly_var = tk.StringVar(value="111110011")
        self.poly_combo = ttk.Combobox(prow, textvariable=self.poly_var, values=CANDIDATE_POLYNOMIALS, width=16)
        self.poly_combo.pack(side="left", padx=5)
        ttk.Button(prow, text="Random Polynomial", command=self.random_polynomial).pack(side="left", padx=5)
        ttk.Button(prow, text="Validate", command=self.validate_polynomial_ui).pack(side="left", padx=5)
        self.poly_info_var = tk.StringVar(value="")
        ttk.Label(field_box, textvariable=self.poly_info_var, foreground="#444").pack(anchor="w", pady=(2, 4))

        brow = ttk.Frame(field_box)
        brow.pack(fill="x", pady=2)
        ttk.Label(brow, text="Affine constant b (8 bits):").pack(side="left")
        self.b_var = tk.StringVar(value="10010101")
        ttk.Entry(brow, textvariable=self.b_var, width=14).pack(side="left", padx=5)
        ttk.Button(brow, text="Random b", command=self.random_b).pack(side="left", padx=5)

        action_box = ttk.Frame(left, padding=(0, 10, 0, 0))
        action_box.pack(fill="x")
        ttk.Button(action_box, text="Randomize All", command=self.randomize_all).pack(side="left", padx=(0, 8))
        ttk.Button(action_box, text="Generate S-box + Evaluate", command=self.generate_and_evaluate).pack(side="left", padx=8)
        ttk.Button(action_box, text="Go to Results", command=lambda: self.notebook.select(self.tab_results)).pack(side="left", padx=8)

        # Graph canvas
        graph_right = ttk.LabelFrame(right, text="Graph visualization", style="Section.TLabelframe", padding=6)
        graph_right.pack(fill="both", expand=True)
        self.graph_canvas = tk.Canvas(graph_right, background="white", highlightthickness=1, highlightbackground="#bbb")
        self.graph_canvas.pack(fill="both", expand=True)
        self.graph_canvas.bind("<Configure>", lambda _e: self._draw_graph(self.current_matrix) if self.current_matrix else None)
        gr_btns = ttk.Frame(graph_right)
        gr_btns.pack(fill="x", pady=(5, 0))
        ttk.Button(gr_btns, text="Export Graph SVG", command=self.export_graph_svg).pack(side="left")
        ttk.Label(gr_btns, text="Arrows show directed edges; loops are shown as small circles.", foreground="#555").pack(side="left", padx=12)

    def _build_evaluator_tab(self):
        outer = ttk.Frame(self.tab_evaluator, padding=12)
        outer.pack(fill="both", expand=True)
        top = ttk.Frame(outer)
        top.pack(fill="x")
        ttk.Label(top, text="Paste a 256-entry 8×8 S-box in decimal or hexadecimal form.").pack(side="left")
        ttk.Label(top, text="Input format:").pack(side="left", padx=(24, 4))
        self.eval_base_var = tk.StringVar(value="Auto")
        ttk.Combobox(top, textvariable=self.eval_base_var, values=["Auto", "Decimal", "Hex"], state="readonly", width=10).pack(side="left")
        ttk.Button(top, text="Load Current Generated S-box", command=self.load_current_into_evaluator).pack(side="left", padx=6)
        ttk.Button(top, text="Evaluate Pasted S-box", command=self.evaluate_pasted_sbox).pack(side="left", padx=6)
        ttk.Button(top, text="Clear", command=lambda: self.eval_text.delete("1.0", "end")).pack(side="left", padx=6)
        self.eval_text = tk.Text(outer, font=("Consolas", 10), wrap="none")
        self.eval_text.pack(fill="both", expand=True, pady=(10, 0))

    def _build_search_tab(self):
        outer = ttk.Frame(self.tab_search, padding=10)
        outer.pack(fill="both", expand=True)

        settings = ttk.LabelFrame(outer, text="Random generation / search settings", style="Section.TLabelframe", padding=8)
        settings.pack(fill="x")
        r1 = ttk.Frame(settings)
        r1.pack(fill="x", pady=2)
        ttk.Label(r1, text="Trials:").pack(side="left")
        self.trials_var = tk.IntVar(value=100)
        ttk.Spinbox(r1, from_=1, to=100000, textvariable=self.trials_var, width=8).pack(side="left", padx=(4, 12))
        ttk.Label(r1, text="Polynomial source:").pack(side="left")
        self.search_poly_mode_var = tk.StringVar(value="All 16 candidates")
        ttk.Combobox(r1, textvariable=self.search_poly_mode_var,
                     values=["All 16 candidates", "Current polynomial only"], state="readonly", width=23).pack(side="left", padx=(4, 12))
        ttk.Label(r1, text="Selection rule:").pack(side="left")
        self.search_rule_var = tk.StringVar(value="Strict thresholds (AND)")
        ttk.Combobox(r1, textvariable=self.search_rule_var,
                     values=["Strict thresholds (AND)", "Paper SAC rule (OR)", "No filter"], state="readonly", width=23).pack(side="left", padx=(4, 12))
        self.search_random_b_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(r1, text="Random b each trial", variable=self.search_random_b_var).pack(side="left")

        r2 = ttk.Frame(settings)
        r2.pack(fill="x", pady=3)
        ttk.Label(r2, text="NL min ≥").pack(side="left")
        self.t_nl_var = tk.IntVar(value=112)
        ttk.Entry(r2, textvariable=self.t_nl_var, width=6).pack(side="left", padx=(3, 10))
        ttk.Label(r2, text="DU ≤").pack(side="left")
        self.t_du_var = tk.IntVar(value=4)
        ttk.Entry(r2, textvariable=self.t_du_var, width=5).pack(side="left", padx=(3, 10))
        ttk.Label(r2, text="LP ≤").pack(side="left")
        self.t_lp_var = tk.DoubleVar(value=0.0625)
        ttk.Entry(r2, textvariable=self.t_lp_var, width=8).pack(side="left", padx=(3, 10))
        ttk.Label(r2, text="SAC min ≥").pack(side="left")
        self.t_sac_min_var = tk.DoubleVar(value=0.45)
        ttk.Entry(r2, textvariable=self.t_sac_min_var, width=8).pack(side="left", padx=(3, 10))
        ttk.Label(r2, text="SAC max ≤").pack(side="left")
        self.t_sac_max_var = tk.DoubleVar(value=0.56)
        ttk.Entry(r2, textvariable=self.t_sac_max_var, width=8).pack(side="left", padx=(3, 10))
        ttk.Label(r2, text="SAC std ≤").pack(side="left")
        self.t_sac_std_var = tk.DoubleVar(value=0.027)
        ttk.Entry(r2, textvariable=self.t_sac_std_var, width=8).pack(side="left", padx=(3, 10))
        self.t_zero_fp_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(r2, text="Require FP+OFP = 0", variable=self.t_zero_fp_var).pack(side="left")

        r3 = ttk.Frame(settings)
        r3.pack(fill="x", pady=3)
        ttk.Label(r3, text="The search uses the Generator tab's vertex/edge/loop settings and randomizes a nonsingular adjacency matrix each trial.", foreground="#555").pack(side="left")
        ttk.Button(r3, text="Start Search", command=self.start_search).pack(side="right", padx=4)
        ttk.Button(r3, text="Stop", command=self.stop_search).pack(side="right", padx=4)
        ttk.Button(r3, text="Clear Results", command=self.clear_search_results).pack(side="right", padx=4)
        ttk.Button(r3, text="Export Search CSV", command=self.export_search_csv).pack(side="right", padx=4)

        prog = ttk.Frame(outer)
        prog.pack(fill="x", pady=(6, 4))
        self.search_progress = ttk.Progressbar(prog, mode="determinate")
        self.search_progress.pack(side="left", fill="x", expand=True)
        self.search_progress_var = tk.StringVar(value="Not running")
        ttk.Label(prog, textvariable=self.search_progress_var, width=35).pack(side="left", padx=8)

        columns = ("iter", "accepted", "poly", "b", "nl", "du", "lp", "sacmin", "sacmax", "sacmean", "std", "fp", "score")
        self.search_tree = ttk.Treeview(outer, columns=columns, show="headings", height=22)
        headings = {
            "iter": "#", "accepted": "Accepted", "poly": "Polynomial", "b": "b", "nl": "NLmin", "du": "DU",
            "lp": "LP", "sacmin": "SAC min", "sacmax": "SAC max", "sacmean": "SAC mean",
            "std": "SAC std", "fp": "FP+OFP", "score": "Score"
        }
        widths = {"iter":50,"accepted":75,"poly":95,"b":80,"nl":60,"du":50,"lp":70,"sacmin":75,"sacmax":75,"sacmean":80,"std":75,"fp":70,"score":65}
        for c in columns:
            self.search_tree.heading(c, text=headings[c])
            self.search_tree.column(c, width=widths[c], anchor="center", stretch=(c in {"poly", "b"}))
        ysb = ttk.Scrollbar(outer, orient="vertical", command=self.search_tree.yview)
        xsb = ttk.Scrollbar(outer, orient="horizontal", command=self.search_tree.xview)
        self.search_tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        self.search_tree.pack(fill="both", expand=True, side="left", pady=(4, 0))
        ysb.pack(fill="y", side="left", pady=(4, 0))
        xsb.pack(fill="x", side="bottom")
        self.search_tree.bind("<Double-1>", self.load_selected_search_result)

    def _build_results_tab(self):
        outer = ttk.Frame(self.tab_results, padding=10)
        outer.pack(fill="both", expand=True)
        btns = ttk.Frame(outer)
        btns.pack(fill="x", pady=(0, 6))
        ttk.Button(btns, text="Export Current JSON", command=self.export_current_json).pack(side="left", padx=3)
        ttk.Button(btns, text="Export Current CSV", command=self.export_current_csv).pack(side="left", padx=3)
        ttk.Button(btns, text="Export DDT CSV", command=self.export_ddt_csv).pack(side="left", padx=3)
        ttk.Button(btns, text="Export LAT CSV", command=self.export_lat_csv).pack(side="left", padx=3)
        ttk.Button(btns, text="Copy S-box Hex", command=self.copy_sbox_hex).pack(side="left", padx=3)

        inner_nb = ttk.Notebook(outer)
        inner_nb.pack(fill="both", expand=True)
        mtab = ttk.Frame(inner_nb, padding=6)
        stab = ttk.Frame(inner_nb, padding=6)
        sactab = ttk.Frame(inner_nb, padding=6)
        ptab = ttk.Frame(inner_nb, padding=6)
        inner_nb.add(mtab, text="Metrics")
        inner_nb.add(stab, text="S-box LUT")
        inner_nb.add(sactab, text="SAC Matrix")
        inner_nb.add(ptab, text="Parameters")

        self.metrics_tree = ttk.Treeview(mtab, columns=("metric", "value"), show="headings", style="Metric.Treeview")
        self.metrics_tree.heading("metric", text="Metric")
        self.metrics_tree.heading("value", text="Value")
        self.metrics_tree.column("metric", width=290, anchor="w")
        self.metrics_tree.column("value", width=850, anchor="w")
        self.metrics_tree.pack(fill="both", expand=True)

        fmt_row = ttk.Frame(stab)
        fmt_row.pack(fill="x")
        ttk.Label(fmt_row, text="View:").pack(side="left")
        self.sbox_view_mode = tk.StringVar(value="Hex")
        cb = ttk.Combobox(fmt_row, textvariable=self.sbox_view_mode, values=["Hex", "Decimal"], state="readonly", width=10)
        cb.pack(side="left", padx=5)
        cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_sbox_view())
        self.sbox_text = tk.Text(stab, font=("Consolas", 11), wrap="none")
        self.sbox_text.pack(fill="both", expand=True, pady=(5, 0))

        self.sac_tree = ttk.Treeview(sactab, columns=[f"o{i}" for i in range(8)], show="tree headings")
        self.sac_tree.heading("#0", text="Input bit")
        self.sac_tree.column("#0", width=90, anchor="center")
        for i in range(8):
            self.sac_tree.heading(f"o{i}", text=f"Out {i}")
            self.sac_tree.column(f"o{i}", width=95, anchor="center")
        self.sac_tree.pack(fill="both", expand=True)

        self.params_text = tk.Text(ptab, font=("Consolas", 10), wrap="none")
        self.params_text.pack(fill="both", expand=True)

    def _build_about_tab(self):
        text = tk.Text(self.tab_about, wrap="word", padx=18, pady=18, font=("Segoe UI", 10))
        text.pack(fill="both", expand=True)
        content = f"""{APP_TITLE} v{APP_VERSION}\n\n"
        "PURPOSE\n"
        "This tool implements the uploaded graph-based S-box workflow: select graph vertices and directed edges, "
        "construct the adjacency matrix, choose an irreducible degree-8 polynomial m(x) and affine vector b, "
        "apply inversion in GF(2^8) followed by the affine transformation, then evaluate cryptographic properties.\n\n"
        "SUPPORTED WORKFLOWS\n"
        "• Generate a random nonsingular adjacency matrix with an exact edge count.\n"
        "• Enter edges manually and convert them to an adjacency matrix.\n"
        "• Enter an adjacency matrix manually and visualize the directed graph.\n"
        "• Choose any of the 16 supplied candidate degree-8 irreducible polynomials, or type a custom candidate.\n"
        "• Randomize the affine vector b or enter it manually.\n"
        "• Generate and evaluate a new 8×8 S-box.\n"
        "• Paste any existing 256-entry S-box and evaluate it independently.\n"
        "• Run reproducible random searches across graph matrices, polynomials and b values.\n"
        "• Export S-boxes, metrics, DDT, LAT and the graph as SVG.\n\n"
        "CRYPTOGRAPHIC METRICS\n"
        "Bijectivity, vectorial nonlinearity, coordinate nonlinearities, maximum absolute Walsh/LAT coefficient, "
        "LP (maximum linear bias), maximum linear approximation probability/count, differential uniformity, "
        "8×8 SAC matrix and its min/max/mean/population standard deviation, fixed points, opposite fixed points, "
        "cycle structure, and algebraic degree.\n\n"
        "IMPORTANT IMPLEMENTATION NOTES\n"
        "• Matrix nonsingularity is tested over GF(2), not by floating-point real-valued rank.\n"
        "• For S-box generation the affine matrix must be exactly 8×8 and have GF(2) rank 8.\n"
        "• All custom polynomials are checked for degree-8 irreducibility over GF(2).\n"
        "• The 'Paper SAC rule (OR)' reproduces the supplied acceptance condition: mean SAC = 0.5 OR "
        "(SAC_min > 0.45 and SAC_max < 0.56) OR SAC standard deviation < 0.027.\n"
        "• The quality score in Random Search is only a convenient ranking heuristic; it is not a security proof.\n\n"
        "REPRODUCIBILITY\n"
        "Set a random seed before generating a graph or launching a random search. Exported JSON/CSV files preserve "
        "the selected polynomial, b vector, matrix, S-box and computed metrics.\n"
        """
        text.insert("1.0", content)
        text.configure(state="disabled")

    # -------------------- generator actions --------------------
    def _rng_from_seed(self, offset: int = 0) -> random.Random:
        s = self.seed_var.get().strip()
        if not s:
            return random.Random()
        try:
            seed = int(s, 0)
        except ValueError:
            seed = s
        return random.Random(f"{seed}:{offset}")

    def _load_initial_example(self):
        try:
            rng = self._rng_from_seed()
            m = random_nonsingular_matrix(8, 31, True, rng)
            self._set_matrix(m)
            self.validate_polynomial_ui(silent=True)
            self.status_var.set("Ready. A reproducible sample 8-vertex, 31-edge nonsingular graph is loaded.")
        except Exception as exc:
            self.status_var.set(f"Initialization warning: {exc}")

    def random_graph(self):
        try:
            n = int(self.vertices_var.get())
            e = int(self.edges_count_var.get())
            rng = self._rng_from_seed(int(time.time() * 1000) if not self.seed_var.get().strip() else 0)
            m = random_nonsingular_matrix(n, e, self.allow_loops_var.get(), rng)
            self._set_matrix(m)
            self.status_var.set(f"Generated nonsingular {n}×{n} adjacency matrix with {e} directed edges (GF(2) rank {gf2_rank(m)}).")
        except Exception as exc:
            messagebox.showerror("Random graph", str(exc))

    def _set_matrix(self, matrix: List[List[int]]):
        self.current_matrix = [list(map(int, r)) for r in matrix]
        self.matrix_text.delete("1.0", "end")
        self.matrix_text.insert("1.0", matrix_to_text(matrix))
        self._update_matrix_info(matrix)
        self._populate_edge_text(matrix)
        self._draw_graph(matrix)

    def _update_matrix_info(self, matrix: List[List[int]]):
        n = len(matrix)
        rank = gf2_rank(matrix)
        e = len(edges_from_matrix(matrix))
        self.matrix_info_var.set(f"Matrix: {n}×{n} | directed edges: {e} | GF(2) rank: {rank} | {'nonsingular' if rank == n else 'singular'}")

    def _populate_edge_text(self, matrix: List[List[int]]):
        one_based = self.numbering_var.get() == "1..N"
        lines = []
        for u, v in edges_from_matrix(matrix):
            if one_based:
                u += 1; v += 1
            lines.append(f"{u}->{v}")
        self.edge_text.delete("1.0", "end")
        self.edge_text.insert("1.0", "\n".join(lines))

    def matrix_from_edges_ui(self):
        try:
            n = int(self.vertices_var.get())
            edges = parse_edge_list(self.edge_text.get("1.0", "end"), n, self.numbering_var.get())
            m = matrix_from_edges(n, edges)
            self._set_matrix(m)
            self.status_var.set("Adjacency matrix constructed from edge list.")
        except Exception as exc:
            messagebox.showerror("Matrix from edges", str(exc))

    def edges_from_matrix_ui(self):
        try:
            m = parse_matrix(self.matrix_text.get("1.0", "end"))
            self.vertices_var.set(len(m))
            self._set_matrix(m)
            self.status_var.set("Edge list reconstructed from adjacency matrix.")
        except Exception as exc:
            messagebox.showerror("Edges from matrix", str(exc))

    def draw_graph_from_ui(self):
        try:
            m = parse_matrix(self.matrix_text.get("1.0", "end"))
            self.current_matrix = m
            self.vertices_var.set(len(m))
            self._update_matrix_info(m)
            self._draw_graph(m)
            self.status_var.set("Graph redrawn from current matrix.")
        except Exception as exc:
            messagebox.showerror("Draw graph", str(exc))

    def random_polynomial(self):
        rng = self._rng_from_seed(int(time.time() * 1000) if not self.seed_var.get().strip() else 17)
        self.poly_var.set(rng.choice(CANDIDATE_POLYNOMIALS))
        self.validate_polynomial_ui(silent=True)

    def validate_polynomial_ui(self, silent: bool = False):
        try:
            bits = normalize_polynomial(self.poly_var.get())
            irr = is_irreducible_degree8(bits)
            self.poly_var.set(bits)
            self.poly_info_var.set(f"{bits} = 0x{int(bits,2):03X} = {polynomial_expression(bits)} | irreducible: {'YES' if irr else 'NO'}")
            if not irr and not silent:
                messagebox.showwarning("Polynomial", "The entered polynomial is degree 8 but reducible over GF(2). It cannot define GF(2^8).")
            return irr
        except Exception as exc:
            self.poly_info_var.set(str(exc))
            if not silent:
                messagebox.showerror("Polynomial", str(exc))
            return False

    def random_b(self):
        rng = self._rng_from_seed(int(time.time() * 1000) if not self.seed_var.get().strip() else 29)
        self.b_var.set(f"{rng.randrange(256):08b}")

    def randomize_all(self):
        self.random_graph()
        self.random_polynomial()
        self.random_b()

    def _read_generator_inputs(self) -> Tuple[List[List[int]], str, str]:
        matrix = parse_matrix(self.matrix_text.get("1.0", "end"), 8)
        if gf2_rank(matrix) != 8:
            raise ValueError("The 8×8 adjacency/affine matrix is singular over GF(2). Generate or enter a rank-8 matrix.")
        poly = normalize_polynomial(self.poly_var.get())
        if not is_irreducible_degree8(poly):
            raise ValueError(f"Polynomial {poly} is not irreducible over GF(2).")
        b = self.b_var.get().strip().replace(" ", "")
        if len(b) != 8 or any(c not in "01" for c in b):
            raise ValueError("Affine constant b must contain exactly 8 binary digits.")
        return matrix, poly, b

    def generate_and_evaluate(self):
        try:
            self.status_var.set("Generating and evaluating S-box...")
            self.update_idletasks()
            matrix, poly, b = self._read_generator_inputs()
            sbox = generate_sbox(matrix, b, poly)
            metrics = evaluate_sbox(sbox)
            self.current_matrix = matrix
            self.current_sbox = sbox
            self.current_metrics = metrics
            self.current_context = {
                "source": "Generated",
                "polynomial": poly,
                "polynomial_hex": f"0x{int(poly,2):03X}",
                "polynomial_expression": polynomial_expression(poly),
                "b_bits": b,
                "matrix": matrix,
                "matrix_rank_gf2": gf2_rank(matrix),
                "edge_count": len(edges_from_matrix(matrix)),
            }
            self._refresh_results()
            self.notebook.select(self.tab_results)
            self.status_var.set("S-box generated and evaluated successfully.")
        except Exception as exc:
            self.status_var.set("Generation failed.")
            messagebox.showerror("Generate S-box", str(exc))

    # -------------------- graph drawing/export --------------------
    def _graph_positions(self, n: int, width: float, height: float):
        cx, cy = width / 2, height / 2
        radius = max(40.0, min(width, height) * 0.36)
        out = []
        for i in range(n):
            angle = -math.pi / 2 + 2 * math.pi * i / n
            out.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
        return out

    def _draw_graph(self, matrix: List[List[int]]):
        c = self.graph_canvas
        c.delete("all")
        if not matrix:
            return
        w = max(c.winfo_width(), 500)
        h = max(c.winfo_height(), 500)
        n = len(matrix)
        pos = self._graph_positions(n, w, h)
        node_r = max(13, min(24, 180 / max(n, 8)))
        edges = edges_from_matrix(matrix)
        edge_set = set(edges)

        # Edges first
        for u, v in edges:
            x1, y1 = pos[u]
            x2, y2 = pos[v]
            if u == v:
                r = node_r * 1.45
                c.create_oval(x1-r, y1-r*2.15, x1+r, y1-0.1*r, outline="#777", width=1.2)
                c.create_polygon(x1+r*0.55, y1-r*0.30, x1+r*0.15, y1-r*0.45, x1+r*0.35, y1-r*0.05,
                                 fill="#777", outline="#777")
                continue
            dx, dy = x2-x1, y2-y1
            dist = math.hypot(dx, dy) or 1.0
            ux, uy = dx/dist, dy/dist
            sx, sy = x1 + ux*node_r, y1 + uy*node_r
            ex, ey = x2 - ux*node_r, y2 - uy*node_r
            # Separate two opposite directed edges slightly.
            offset = 0
            if (v, u) in edge_set:
                offset = 5 if u < v else -5
            px, py = -uy*offset, ux*offset
            c.create_line(sx+px, sy+py, ex+px, ey+py, arrow=tk.LAST, arrowshape=(8,10,4), fill="#6a6a6a", width=1.1)

        one_based = self.numbering_var.get() == "1..N"
        for i, (x, y) in enumerate(pos):
            c.create_oval(x-node_r, y-node_r, x+node_r, y+node_r, fill="#e9f2ff", outline="#2b5d8a", width=2)
            label = str(i+1 if one_based else i)
            c.create_text(x, y, text=label, font=("Segoe UI", 10, "bold"), fill="#173b5e")
        c.create_text(10, 10, anchor="nw", text=f"Vertices={n}  Edges={len(edges)}  GF(2) rank={gf2_rank(matrix)}",
                      font=("Segoe UI", 9), fill="#333")

    def export_graph_svg(self):
        if not self.current_matrix:
            messagebox.showinfo("Export graph", "No graph is loaded.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".svg", filetypes=[("SVG image", "*.svg")], initialfile="adjacency_graph.svg")
        if not path:
            return
        try:
            self._write_graph_svg(path, self.current_matrix)
            self.status_var.set(f"Graph exported: {path}")
        except Exception as exc:
            messagebox.showerror("Export graph", str(exc))

    def _write_graph_svg(self, path: str, matrix: List[List[int]]):
        width, height = 900, 700
        n = len(matrix)
        pos = self._graph_positions(n, width, height)
        r = 24
        edges = edges_from_matrix(matrix)
        edge_set = set(edges)
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<defs><marker id="arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#666"/></marker></defs>',
            '<rect width="100%" height="100%" fill="white"/>',
        ]
        for u, v in edges:
            x1,y1=pos[u]; x2,y2=pos[v]
            if u == v:
                lines.append(f'<circle cx="{x1}" cy="{y1-r*1.45}" r="{r*0.9}" fill="none" stroke="#666" stroke-width="1.5" marker-end="url(#arrow)"/>')
            else:
                dx,dy=x2-x1,y2-y1; d=math.hypot(dx,dy) or 1
                ux,uy=dx/d,dy/d
                sx,sy=x1+ux*r,y1+uy*r; ex,ey=x2-ux*r,y2-uy*r
                off = (6 if u < v else -6) if (v,u) in edge_set else 0
                px,py=-uy*off,ux*off
                lines.append(f'<line x1="{sx+px:.2f}" y1="{sy+py:.2f}" x2="{ex+px:.2f}" y2="{ey+py:.2f}" stroke="#666" stroke-width="1.5" marker-end="url(#arrow)"/>')
        one_based = self.numbering_var.get() == "1..N"
        for i,(x,y) in enumerate(pos):
            lines.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r}" fill="#e9f2ff" stroke="#2b5d8a" stroke-width="2"/>')
            lines.append(f'<text x="{x:.2f}" y="{y+5:.2f}" text-anchor="middle" font-family="Arial" font-size="15" font-weight="bold" fill="#173b5e">{i+1 if one_based else i}</text>')
        lines.append(f'<text x="20" y="28" font-family="Arial" font-size="14">Vertices={n}, Edges={len(edges)}, GF(2) rank={gf2_rank(matrix)}</text>')
        lines.append('</svg>')
        Path(path).write_text("\n".join(lines), encoding="utf-8")

    # -------------------- evaluator --------------------
    def load_current_into_evaluator(self):
        if not self.current_sbox:
            messagebox.showinfo("Evaluator", "Generate or evaluate an S-box first.")
            return
        self.eval_text.delete("1.0", "end")
        self.eval_text.insert("1.0", sbox_to_hex_grid(self.current_sbox))
        self.eval_base_var.set("Hex")

    def evaluate_pasted_sbox(self):
        try:
            mode = self.eval_base_var.get().lower()
            sbox = parse_sbox(self.eval_text.get("1.0", "end"), mode)
            self.status_var.set("Evaluating pasted S-box...")
            self.update_idletasks()
            metrics = evaluate_sbox(sbox)
            self.current_sbox = sbox
            self.current_metrics = metrics
            self.current_context = {"source": "Pasted S-box evaluator"}
            self._refresh_results()
            self.notebook.select(self.tab_results)
            self.status_var.set("Pasted S-box evaluated successfully.")
        except Exception as exc:
            messagebox.showerror("Evaluate S-box", str(exc))

    # -------------------- random search --------------------
    def start_search(self):
        if self.search_thread and self.search_thread.is_alive():
            messagebox.showinfo("Random search", "A search is already running.")
            return
        try:
            n = int(self.vertices_var.get())
            if n != 8:
                raise ValueError("Random S-box search requires exactly 8 graph vertices.")
            edge_count = int(self.edges_count_var.get())
            trials = int(self.trials_var.get())
            if trials < 1:
                raise ValueError("Trials must be at least 1.")
            current_poly = normalize_polynomial(self.poly_var.get())
            if not is_irreducible_degree8(current_poly):
                raise ValueError("Current polynomial is not irreducible.")
            fixed_b = self.b_var.get().strip()
            if len(fixed_b) != 8 or any(c not in "01" for c in fixed_b):
                raise ValueError("Current b must contain 8 binary digits.")
            thresholds = {
                "nl_min": int(self.t_nl_var.get()),
                "du_max": int(self.t_du_var.get()),
                "lp_max": float(self.t_lp_var.get()),
                "sac_min": float(self.t_sac_min_var.get()),
                "sac_max": float(self.t_sac_max_var.get()),
                "sac_std_max": float(self.t_sac_std_var.get()),
                "require_zero_fp": bool(self.t_zero_fp_var.get()),
            }
        except Exception as exc:
            messagebox.showerror("Random search", str(exc))
            return

        self.search_stop.clear()
        self.search_progress["maximum"] = trials
        self.search_progress["value"] = 0
        self.search_progress_var.set(f"0 / {trials}")
        seed_text = self.seed_var.get().strip()
        settings = {
            "n": 8, "edge_count": edge_count, "allow_loops": self.allow_loops_var.get(), "trials": trials,
            "poly_mode": self.search_poly_mode_var.get(), "current_poly": current_poly,
            "rule": self.search_rule_var.get(), "random_b": self.search_random_b_var.get(), "fixed_b": fixed_b,
            "thresholds": thresholds, "seed": seed_text,
        }
        self.search_thread = threading.Thread(target=self._search_worker, args=(settings,), daemon=True)
        self.search_thread.start()
        self.status_var.set("Random search started.")

    def _search_worker(self, settings: Dict[str, Any]):
        seed = settings["seed"] if settings["seed"] else time.time_ns()
        rng = random.Random(str(seed) + ":search")
        polys = CANDIDATE_POLYNOMIALS if settings["poly_mode"] == "All 16 candidates" else [settings["current_poly"]]
        accepted_count = 0
        started = time.time()
        try:
            for i in range(1, settings["trials"] + 1):
                if self.search_stop.is_set():
                    break
                matrix = random_nonsingular_matrix(8, settings["edge_count"], settings["allow_loops"], rng)
                poly = rng.choice(polys)
                b = f"{rng.randrange(256):08b}" if settings["random_b"] else settings["fixed_b"]
                sbox = generate_sbox(matrix, b, poly)
                metrics = evaluate_sbox(sbox)
                if settings["rule"] == "Paper SAC rule (OR)":
                    accepted = paper_sac_filter(metrics)
                elif settings["rule"] == "Strict thresholds (AND)":
                    accepted = strict_filter(metrics, settings["thresholds"])
                else:
                    accepted = True
                if accepted:
                    accepted_count += 1
                result = CandidateResult(i, poly, b, matrix, sbox, metrics, quality_score(metrics))
                self.search_queue.put(("result", result, accepted, accepted_count, settings["trials"]))
            elapsed = time.time() - started
            self.search_queue.put(("done", accepted_count, elapsed, self.search_stop.is_set()))
        except Exception as exc:
            self.search_queue.put(("error", str(exc)))

    def _poll_search_queue(self):
        try:
            while True:
                item = self.search_queue.get_nowait()
                kind = item[0]
                if kind == "result":
                    _, result, accepted, acount, total = item
                    self.search_results.append(result)
                    m = result.metrics
                    iid = str(len(self.search_results)-1)
                    self.search_tree.insert("", "end", iid=iid, values=(
                        result.iteration, "YES" if accepted else "no", result.polynomial, result.b_bits,
                        m["nonlinearity_min"], m["differential_uniformity"], f"{m['lp_bias']:.6f}",
                        f"{m['sac_min']:.6f}", f"{m['sac_max']:.6f}", f"{m['sac_mean']:.6f}",
                        f"{m['sac_std']:.6f}", m["fixed_total"], f"{result.score:.3f}"
                    ))
                    self.search_progress["value"] = result.iteration
                    self.search_progress_var.set(f"{result.iteration} / {total} | accepted {acount}")
                elif kind == "done":
                    _, acount, elapsed, stopped = item
                    self.search_progress_var.set(f"{'Stopped' if stopped else 'Completed'} | accepted {acount} | {elapsed:.1f} s")
                    self.status_var.set("Random search stopped." if stopped else "Random search completed.")
                elif kind == "error":
                    messagebox.showerror("Random search", item[1])
                    self.status_var.set("Random search failed.")
        except queue.Empty:
            pass
        self.after(100, self._poll_search_queue)

    def stop_search(self):
        self.search_stop.set()
        self.status_var.set("Stop requested; waiting for the current trial to finish...")

    def clear_search_results(self):
        if self.search_thread and self.search_thread.is_alive():
            messagebox.showinfo("Random search", "Stop the running search before clearing results.")
            return
        self.search_results.clear()
        for item in self.search_tree.get_children():
            self.search_tree.delete(item)
        self.search_progress["value"] = 0
        self.search_progress_var.set("Not running")

    def load_selected_search_result(self, _event=None):
        sel = self.search_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if not 0 <= idx < len(self.search_results):
            return
        r = self.search_results[idx]
        self.poly_var.set(r.polynomial)
        self.b_var.set(r.b_bits)
        self._set_matrix(r.matrix)
        self.current_sbox = r.sbox
        self.current_metrics = r.metrics
        self.current_context = {
            "source": f"Random Search trial {r.iteration}",
            "polynomial": r.polynomial,
            "polynomial_hex": f"0x{int(r.polynomial,2):03X}",
            "polynomial_expression": polynomial_expression(r.polynomial),
            "b_bits": r.b_bits,
            "matrix": r.matrix,
            "matrix_rank_gf2": gf2_rank(r.matrix),
            "edge_count": len(edges_from_matrix(r.matrix)),
            "quality_score": r.score,
        }
        self.validate_polynomial_ui(silent=True)
        self._refresh_results()
        self.notebook.select(self.tab_results)

    # -------------------- result display/export --------------------
    def _refresh_results(self):
        for item in self.metrics_tree.get_children():
            self.metrics_tree.delete(item)
        if not self.current_metrics or not self.current_sbox:
            return
        m = self.current_metrics
        metric_rows = [
            ("Source", self.current_context.get("source", "")),
            ("Bijective", m["bijective"]),
            ("Unique outputs", m["unique_outputs"]),
            ("Vectorial nonlinearity (min)", m["nonlinearity_min"]),
            ("Vectorial nonlinearity (max)", m["nonlinearity_max"]),
            ("Coordinate nonlinearities (bits 0..7)", m["coordinate_nonlinearities"]),
            ("Maximum |Walsh|", m["max_abs_walsh"]),
            ("Maximum |LAT|", m["lat_max_abs"]),
            ("LP / maximum linear bias", f"{m['lp_bias']:.8f}"),
            ("Maximum linear approximation probability", f"{m['max_linear_probability']:.8f}"),
            ("Maximum linear equal-count", m["max_linear_count"]),
            ("Differential uniformity (DU)", m["differential_uniformity"]),
            ("DU argmax (input diff, output diff)", m["du_argmax"]),
            ("SAC minimum", f"{m['sac_min']:.8f}"),
            ("SAC maximum", f"{m['sac_max']:.8f}"),
            ("SAC mean", f"{m['sac_mean']:.8f}"),
            ("SAC population std", f"{m['sac_std']:.8f}"),
            ("Fixed points", [f"0x{x:02X}" for x in m["fixed_points"]]),
            ("Opposite fixed points", [f"0x{x:02X}" for x in m["opposite_fixed_points"]]),
            ("FP + OFP", m["fixed_total"]),
            ("Cycle count", m["cycle_count"]),
            ("Cycle lengths", m["cycle_lengths"]),
            ("Component algebraic degrees", m["component_degrees"]),
            ("Algebraic degree", m["algebraic_degree"]),
            ("Paper SAC rule passes", paper_sac_filter(m)),
            ("Quality ranking score", quality_score(m)),
        ]
        for i, (k, v) in enumerate(metric_rows):
            self.metrics_tree.insert("", "end", iid=f"m{i}", values=(k, str(v)))

        self._refresh_sbox_view()
        for item in self.sac_tree.get_children():
            self.sac_tree.delete(item)
        for i, row in enumerate(m["sac_matrix"]):
            self.sac_tree.insert("", "end", text=f"In {i}", values=[f"{v:.6f}" for v in row])

        self.params_text.delete("1.0", "end")
        ctx = dict(self.current_context)
        if "matrix" in ctx:
            matrix = ctx.pop("matrix")
            for k, v in ctx.items():
                self.params_text.insert("end", f"{k}: {v}\n")
            self.params_text.insert("end", "\nAdjacency / affine matrix:\n")
            self.params_text.insert("end", matrix_to_text(matrix))
            self.params_text.insert("end", "\n\nEdges (0-based internal):\n")
            self.params_text.insert("end", ", ".join(f"({u},{v})" for u,v in edges_from_matrix(matrix)))
        else:
            for k, v in ctx.items():
                self.params_text.insert("end", f"{k}: {v}\n")

    def _refresh_sbox_view(self):
        self.sbox_text.delete("1.0", "end")
        if not self.current_sbox:
            return
        if self.sbox_view_mode.get() == "Decimal":
            self.sbox_text.insert("1.0", sbox_to_decimal_grid(self.current_sbox))
        else:
            self.sbox_text.insert("1.0", sbox_to_hex_grid(self.current_sbox))

    def _json_safe_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        out = {}
        for k, v in metrics.items():
            if isinstance(v, tuple):
                out[k] = list(v)
            else:
                out[k] = v
        return out

    def export_current_json(self):
        if not self.current_sbox or not self.current_metrics:
            messagebox.showinfo("Export", "No current S-box result.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")], initialfile="sbox_analysis.json")
        if not path:
            return
        data = {
            "app": f"{APP_TITLE} v{APP_VERSION}",
            "context": self.current_context,
            "sbox_decimal": self.current_sbox,
            "sbox_hex": [f"{v:02X}" for v in self.current_sbox],
            "metrics": self._json_safe_metrics(self.current_metrics),
        }
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
        self.status_var.set(f"Exported JSON: {path}")

    def export_current_csv(self):
        if not self.current_sbox or not self.current_metrics:
            messagebox.showinfo("Export", "No current S-box result.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="sbox_analysis.csv")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Section", "Name", "Value"])
            for k, v in self.current_context.items():
                if k == "matrix":
                    v = " | ".join("".join(map(str, row)) for row in v)
                w.writerow(["parameter", k, v])
            for k, v in self.current_metrics.items():
                if k == "sac_matrix":
                    continue
                w.writerow(["metric", k, v])
            w.writerow(["sbox", "decimal", " ".join(map(str, self.current_sbox))])
            w.writerow(["sbox", "hex", " ".join(f"{v:02X}" for v in self.current_sbox)])
            for i, row in enumerate(self.current_metrics["sac_matrix"]):
                w.writerow(["sac", f"input_bit_{i}", *row])
        self.status_var.set(f"Exported CSV: {path}")

    def export_search_csv(self):
        if not self.search_results:
            messagebox.showinfo("Export search", "No search results.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="random_search_results.csv")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["iteration","polynomial","polynomial_hex","b","matrix_rows","edge_count","NL_min","NL_max","DU","LP","LAT_max_abs","SAC_min","SAC_max","SAC_mean","SAC_std","FP","OFP","FP_plus_OFP","cycle_count","cycle_lengths","algebraic_degree","score","sbox_decimal"])
            for r in self.search_results:
                m = r.metrics
                w.writerow([
                    r.iteration, r.polynomial, f"0x{int(r.polynomial,2):03X}", r.b_bits,
                    "|".join("".join(map(str,row)) for row in r.matrix), len(edges_from_matrix(r.matrix)),
                    m["nonlinearity_min"], m["nonlinearity_max"], m["differential_uniformity"], m["lp_bias"], m["lat_max_abs"],
                    m["sac_min"], m["sac_max"], m["sac_mean"], m["sac_std"],
                    len(m["fixed_points"]), len(m["opposite_fixed_points"]), m["fixed_total"],
                    m["cycle_count"], m["cycle_lengths"], m["algebraic_degree"], r.score,
                    " ".join(map(str, r.sbox))
                ])
        self.status_var.set(f"Exported search CSV: {path}")

    def export_ddt_csv(self):
        if not self.current_sbox:
            messagebox.showinfo("Export DDT", "No current S-box.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="DDT.csv")
        if not path:
            return
        self.status_var.set("Computing full DDT...")
        self.update_idletasks()
        table = ddt_table(self.current_sbox)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["dx\\dy"] + [f"{i:02X}" for i in range(256)])
            for i,row in enumerate(table):
                w.writerow([f"{i:02X}"] + row)
        self.status_var.set(f"Exported DDT: {path}")

    def export_lat_csv(self):
        if not self.current_sbox:
            messagebox.showinfo("Export LAT", "No current S-box.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="LAT.csv")
        if not path:
            return
        self.status_var.set("Computing full LAT...")
        self.update_idletasks()
        table = lat_table(self.current_sbox)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["a\\b"] + [f"{i:02X}" for i in range(256)])
            for i,row in enumerate(table):
                w.writerow([f"{i:02X}"] + row)
        self.status_var.set(f"Exported LAT: {path}")

    def copy_sbox_hex(self):
        if not self.current_sbox:
            messagebox.showinfo("Copy", "No current S-box.")
            return
        self.clipboard_clear()
        self.clipboard_append(sbox_to_hex_grid(self.current_sbox))
        self.status_var.set("S-box hex table copied to clipboard.")

    def on_close(self):
        self.search_stop.set()
        self.destroy()


def main():
    app = SBoxStudio()
    app.mainloop()


if __name__ == "__main__":
    main()
