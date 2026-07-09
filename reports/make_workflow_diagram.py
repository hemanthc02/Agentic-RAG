"""Generate the Multi-Agent RAG workflow / architecture diagram.

Renders a layered, Lucid-style diagram (300 DPI PNG + PDF) showing:
  - the offline indexing pipeline (fully local),
  - the runtime 4-agent LangGraph flow with the verifier retry loop,
  - the swappable LLM backend lane (Groq / Ollama),
  - the local CPU services lane (MiniLM, FAISS, DeBERTa-NLI).

Run:  python reports/make_workflow_diagram.py
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

# ----------------------------------------------------------------------------- #
# Palette (professional, per skill visual standards)
# ----------------------------------------------------------------------------- #
C_BG = "#FFFFFF"
C_INK = "#0F172A"        # near-black text
C_MUTE = "#64748B"       # muted text
C_BLUE = "#1E3A8A"       # primary deep blue
C_BLUE_L = "#DBEAFE"     # light blue fill
C_SLATE = "#475569"
C_SLATE_L = "#E2E8F0"
C_GREEN = "#059669"
C_GREEN_L = "#D1FAE5"
C_ORANGE = "#EA580C"
C_ORANGE_L = "#FFEDD5"
C_RED = "#DC2626"
C_PURPLE = "#7C3AED"
C_PURPLE_L = "#EDE9FE"
C_CYAN = "#0891B2"
C_CYAN_L = "#CFFAFE"
C_AMBER_L = "#FEF3C7"

plt.rcParams["font.family"] = "DejaVu Sans"

fig, ax = plt.subplots(figsize=(20, 14))
fig.patch.set_facecolor(C_BG)
ax.set_xlim(0, 200)
ax.set_ylim(0, 140)
ax.axis("off")


# ----------------------------------------------------------------------------- #
# Helpers
# ----------------------------------------------------------------------------- #
def _lh(sz: float) -> float:
    """Line height in data units for a given point size.

    Figure is 20x14 in over ylim 140 → 1 data unit ≈ 7.2 pt. 1.5x line spacing.
    """
    return sz / 7.2 * 1.5


def box(x, y, w, h, fc, ec, title, subtitle="", tech="", title_color=None,
        title_size=12, sub_size=9, tech_size=8, rounded=0.025, lw=1.6, z=2):
    """Draw a rounded box with a top-down title / subtitle / tech-label stack."""
    p = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0.02,rounding_size={rounded * 100}",
        linewidth=lw, edgecolor=ec, facecolor=fc, zorder=z,
    )
    ax.add_patch(p)
    cx = x + w / 2
    tcol = title_color or C_INK

    # Build the line list, then vertically center the whole stack in the box.
    lines: list[tuple[str, float, str, str]] = []
    if title:
        lines.append((title, title_size, "bold", tcol))
    if subtitle:
        lines.append((subtitle, sub_size, "normal", C_INK))
    if tech:
        for t in tech.split("\n"):
            lines.append((t, tech_size, "normal", C_MUTE))

    total_h = sum(_lh(sz) for _, sz, _, _ in lines)
    cur = y + h / 2 + total_h / 2  # top of first line
    for txt, sz, wt, col in lines:
        ax.text(cx, cur, txt, ha="center", va="top", fontsize=sz,
                fontweight=wt, color=col, zorder=z + 1)
        cur -= _lh(sz)


def arrow(x1, y1, x2, y2, color=C_SLATE, lw=2.2, style="-|>", ls="-",
          rad=0.0, z=3, mut=18):
    a = FancyArrowPatch(
        (x1, y1), (x2, y2), connectionstyle=f"arc3,rad={rad}",
        arrowstyle=style, mutation_scale=mut, linewidth=lw,
        color=color, linestyle=ls, zorder=z,
    )
    ax.add_patch(a)


def label(x, y, txt, color=C_SLATE, size=8.5, weight="bold", ha="center",
          style="normal", bg=None):
    bbox = dict(boxstyle="round,pad=0.25", fc=bg, ec="none") if bg else None
    ax.text(x, y, txt, ha=ha, va="center", fontsize=size, color=color,
            fontweight=weight, fontstyle=style, zorder=6, bbox=bbox)


def zone(x, y, w, h, label_txt, color):
    p = FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=1.2",
        linewidth=1.4, edgecolor=color, facecolor="none",
        linestyle=(0, (6, 4)), zorder=1,
    )
    ax.add_patch(p)
    ax.text(x + 1.5, y + h - 2.4, label_txt, ha="left", va="center",
            fontsize=11, fontweight="bold", color=color, zorder=1)


# ----------------------------------------------------------------------------- #
# Title block
# ----------------------------------------------------------------------------- #
ax.text(100, 136, "Multi-Agent RAG with Verified Citations — System Workflow",
        ha="center", va="center", fontsize=20, fontweight="bold", color=C_INK)
ax.text(100, 131.5,
        "CPU-only academic-paper Q&A · LangGraph orchestration · NLI-based "
        "citation verifier (the novelty) · dual LLM backend",
        ha="center", va="center", fontsize=11, color=C_MUTE)


# ============================================================================= #
# ZONE A — Offline indexing pipeline (fully local, one-time)
# ============================================================================= #
zone(6, 105, 188, 22, "  ZONE A · Offline indexing  (one-time · fully local · no network)", C_SLATE)

ay = 109
aw, ah = 38, 13
gap = 6
ax0 = 12
box(ax0, ay, aw, ah, C_SLATE_L, C_SLATE, "data/pdfs/", "PDF corpus (gitignored)",
    "30–50 arXiv PDFs\n{source, page} kept", title_color=C_SLATE)
box(ax0 + (aw + gap), ay, aw, ah, C_BLUE_L, C_BLUE, "ingestion.py", "parse + chunk",
    "PyMuPDF (fitz)\n512-char / 64 overlap\nchunk_id metadata")
box(ax0 + 2 * (aw + gap), ay, aw, ah, C_BLUE_L, C_BLUE, "retrieval.py", "embed chunks",
    "all-MiniLM-L6-v2\n384-dim · CPU")
box(ax0 + 3 * (aw + gap), ay, aw, ah, C_PURPLE_L, C_PURPLE, "FAISS index",
    "persisted vector store", "flat ≤5k chunks\nIVF if larger", title_color=C_PURPLE)

for i in range(3):
    arrow(ax0 + aw + i * (aw + gap), ay + ah / 2,
          ax0 + (aw + gap) + i * (aw + gap), ay + ah / 2)
label(ax0 + aw + gap / 2, ay + ah + 2.2, "pages", size=8)
label(ax0 + 2 * (aw + gap) - gap / 2, ay + ah + 2.2, "chunks", size=8)
label(ax0 + 3 * (aw + gap) - gap / 2, ay + ah + 2.2, "vectors", size=8)


# ============================================================================= #
# ZONE B — Runtime Q&A pipeline (LangGraph StateGraph)
# ============================================================================= #
zone(6, 62, 188, 39, "  ZONE B · Runtime Q&A pipeline  (LangGraph StateGraph)", C_BLUE)

by = 74
bw, bh = 27, 17
bgap = 6.5
bx0 = 9

# User question (oval-ish)
qx = bx0
box(qx, by, 20, bh, "#F1F5F9", C_INK, "User", "Question", "research query",
    title_size=12)

# Planner
px = qx + 20 + bgap
box(px, by, bw, bh, C_GREEN_L, C_GREEN, "Planner", "agents/planner.py",
    "decompose →\n1–4 sub-questions\nPydantic schema", title_color=C_GREEN)

# Retriever
rx = px + bw + bgap
box(rx, by, bw, bh, C_GREEN_L, C_GREEN, "Retriever", "agents/retriever.py",
    "FAISS search/sub-q\nLLM relevance grade\nCRAG re-query ×1", title_color=C_GREEN)

# Synthesizer
sx = rx + bw + bgap
box(sx, by, bw, bh, C_GREEN_L, C_GREEN, "Synthesizer", "agents/synthesizer.py",
    "grounded answer\ninline [1][2] cites\n→ (claim, chunk_ids)", title_color=C_GREEN)

# Verifier (novelty - highlighted)
vx = sx + bw + bgap
box(vx, by, bw + 2, bh, C_ORANGE_L, C_ORANGE, "Verifier ★", "agents/verifier.py",
    "per-claim NLI\nentailment score\nverdict vs thr 0.6", title_color=C_ORANGE,
    lw=2.6)

# Final answer
fx = vx + bw + 2 + bgap
box(fx, by, 22, bh, C_AMBER_L, C_ORANGE, "Final", "Answer",
    "+ per-claim\nfaithfulness", title_color=C_ORANGE)

# forward arrows
arrow(qx + 20, by + bh / 2, px, by + bh / 2, color=C_BLUE)
arrow(px + bw, by + bh / 2, rx, by + bh / 2, color=C_BLUE)
arrow(rx + bw, by + bh / 2, sx, by + bh / 2, color=C_BLUE)
arrow(sx + bw, by + bh / 2, vx, by + bh / 2, color=C_BLUE)
arrow(vx + bw + 2, by + bh / 2, fx, by + bh / 2, color=C_GREEN, lw=2.6)
label((vx + bw + 2 + fx) / 2, by + bh / 2 + 2.4, "all pass", color=C_GREEN, size=8)

# retry loop: Verifier -> Synthesizer (curved above)
arrow(vx + (bw + 2) / 2, by + bh, sx + bw / 2, by + bh, color=C_RED,
      rad=-0.55, lw=2.4, style="-|>", mut=16)
label((sx + bw / 2 + vx + (bw + 2) / 2) / 2, by + bh + 6.0,
      "fail & retry_count < 2  →  feedback (which claim + cited evidence)",
      color=C_RED, size=8.5, bg="#FFFFFF")


# ============================================================================= #
# ZONE C — LLM backend abstraction (swappable, dual-mode)
# ============================================================================= #
zone(6, 34, 120, 25, "  ZONE C · llm_backend.py  (mandatory abstraction — agents NEVER call providers directly)", C_CYAN)

# generate() interface bar
box(11, 49, 110, 7, C_CYAN_L, C_CYAN,
    "generate(prompt, temperature, max_tokens) · name · retry backoff (1,2,4)s ×3",
    title_color=C_CYAN, title_size=11, rounded=0.04)

box(13, 37, 52, 10, "#EFF6FF", C_BLUE,
    "GroqBackend  (default)", "Llama 3.3 70B · cloud HTTPS",
    "≤30 s/q · free tier 14,400/day", title_color=C_BLUE, title_size=11)
box(69, 37, 50, 10, C_GREEN_L, C_GREEN,
    "OllamaBackend  (local)", "Phi-3-mini Q4 · localhost:11434",
    "≤90 s/q · fully on-device", title_color=C_GREEN, title_size=11)

# dashed arrows from LLM-using agents down to interface
for cx in (px + bw / 2, rx + bw / 2, sx + bw / 2):
    arrow(cx, by, cx, 56, color=C_CYAN, ls=(0, (4, 3)), lw=1.7, style="-|>", mut=13)
label(px + bw / 2, 60.8, "generate()", color=C_CYAN, size=7.5)
label(rx + bw / 2, 60.8, "grade()", color=C_CYAN, size=7.5)
label(sx + bw / 2, 60.8, "synth()", color=C_CYAN, size=7.5)
# interface -> two backends
arrow(45, 49, 39, 47, color=C_CYAN, lw=1.7)
arrow(86, 49, 92, 47, color=C_CYAN, lw=1.7)


# ============================================================================= #
# ZONE D — Local CPU services (both modes)
# ============================================================================= #
zone(130, 34, 64, 25, "  ZONE D · Local CPU services  (both modes)", C_PURPLE)

box(134, 47, 56, 8, C_BLUE_L, C_BLUE, "MiniLM embedder + FAISS.search(query, k=5)",
    "", "used by Retriever — always local", title_size=10)
box(134, 37, 56, 8, C_PURPLE_L, C_PURPLE,
    "DeBERTa-v3 NLI  (cross-encoder/nli-deberta-v3-base)", "",
    "used by Verifier ★ — always local", title_color=C_PURPLE, title_size=9.5)

# Retriever -> local search ; Verifier -> NLI
arrow(rx + bw / 2, by, 150, 55, color=C_BLUE, ls=(0, (4, 3)), lw=1.7, rad=0.15, mut=13)
arrow(vx + (bw + 2) / 2, by, 175, 45, color=C_PURPLE, ls=(0, (4, 3)), lw=1.9,
      rad=0.18, mut=13)
# index feeds search
arrow(ax0 + 3 * (aw + gap) + aw / 2, ay, 162, 55, color=C_PURPLE,
      ls=(0, (2, 2)), lw=1.4, rad=-0.2, mut=11)
label(168, 60, "load index", color=C_PURPLE, size=7.5)


# ============================================================================= #
# Privacy / legend footer
# ============================================================================= #
zone(6, 6, 188, 24, "  Legend & privacy (mode-specific — never say 'fully local' without naming the mode)", C_INK)

# legend swatches
leg = [
    (C_GREEN_L, C_GREEN, "Agent (LLM-driven)"),
    (C_ORANGE_L, C_ORANGE, "Verifier ★ = novelty"),
    (C_BLUE_L, C_BLUE, "Embedding / index"),
    (C_PURPLE_L, C_PURPLE, "NLI / vector store"),
    (C_CYAN_L, C_CYAN, "Backend abstraction"),
]
lx = 11
for fc, ec, txt in leg:
    r = FancyBboxPatch((lx, 23), 3.2, 3.2, boxstyle="round,pad=0.05,rounding_size=0.4",
                       fc=fc, ec=ec, lw=1.4, zorder=4)
    ax.add_patch(r)
    ax.text(lx + 4.2, 24.6, txt, ha="left", va="center", fontsize=9, color=C_INK)
    lx += 36

# arrow legend
ax.text(11, 18.5, "→ solid = data flow", fontsize=9, color=C_SLATE, fontweight="bold")
ax.text(11, 15.4, "⇢ dashed = LLM / service call", fontsize=9, color=C_CYAN, fontweight="bold")
ax.text(11, 12.3, "↩ red = verifier retry (max 2)", fontsize=9, color=C_RED, fontweight="bold")

priv = (
    "PRIVACY:  PDFs never leave the device in either mode.  "
    "Groq mode sends the question + retrieved chunks (PDF excerpts) over HTTPS — "
    "not for air-gapped use.\n"
    "Ollama mode keeps everything on-device.  "
    "Retriever (MiniLM+FAISS) and Verifier (DeBERTa-NLI) are LOCAL in BOTH modes — "
    "only the LLM call differs."
)
ax.text(78, 15.6, priv, ha="left", va="center", fontsize=9.2, color=C_INK,
        bbox=dict(boxstyle="round,pad=0.5", fc="#F8FAFC", ec=C_SLATE, lw=1.2))

fig.savefig("reports/workflow_diagram.png", dpi=300, bbox_inches="tight", facecolor=C_BG)
fig.savefig("reports/workflow_diagram.pdf", bbox_inches="tight", facecolor=C_BG)
print("saved reports/workflow_diagram.png + reports/workflow_diagram.pdf")
