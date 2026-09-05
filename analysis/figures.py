#!/usr/bin/env python3
"""Generate standalone article figures from audited data and explicit diagrams."""
from pathlib import Path
from html import escape
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'articles/assets'
OUT.mkdir(exist_ok=True)
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12, 'svg.fonttype': 'none',
                     'svg.hashsalt': 'lean-cfg-2026', 'figure.facecolor': '#111827',
                     'axes.facecolor': '#111827', 'text.color': '#f3f4f6',
                     'axes.labelcolor': '#d1d5db', 'xtick.color': '#d1d5db',
                     'ytick.color': '#f3f4f6', 'axes.edgecolor': '#6b7280'})
metadata = {'Date': None, 'Creator': 'lean-tactic-research/analysis/figures.py'}
audit = json.loads((ROOT / 'analysis/audit.json').read_text())
fig, ax = plt.subplots(figsize=(8.2, 4.1), layout='constrained')
colors = ['#34d399', '#60a5fa', '#fb923c']
labels = ['Named alternative', 'Generic fallback', 'Rejected']
for y, cond in enumerate(['unconstrained', 'constrained']):
    c = audit['runs'][cond+'__qwen']['classification_counts']
    left = 0
    for key, color, label in zip(['named', 'fallback', 'parse_fail'], colors, labels):
        n = c.get(key, 0)
        ax.barh(y, n, left=left, color=color, height=.46, label=label if y == 0 else None)
        if n:
            ax.text(left+n/2, y, str(n), ha='center', va='center', color='#111827', fontweight='bold')
        left += n
ax.set(yticks=[0, 1], yticklabels=['Unconstrained', 'Constrained'], xlim=(0, 640),
       xlabel='First cleaned lines (640 samples in each condition)',
       title='Qwen: a change in CFG acceptance')
ax.invert_yaxis()
ax.legend(loc='upper center', bbox_to_anchor=(.5, -.28), ncol=3, frameon=False, fontsize=10)
ax.spines[['top', 'right', 'left']].set_visible(False)
fig.savefig(OUT/'qwen-acceptance.svg', metadata=metadata)
plt.close(fig)

strength = json.loads((ROOT / 'analysis/strength.json').read_text())
classes = [('Truncation','A_truncation'), ('English-word lead','B_english_lead'),
           ('Different tactic','C_wrong_tactic_kw'), ('Argument shuffle','D1_arg_shuffle'),
           ('Full token shuffle','D2_full_shuffle'), ('Identifier soup','F_ident_soup'),
           ('Prose candidates', None)]
fig, ax = plt.subplots(figsize=(8.2, 4.8), layout='constrained')
for y, (label, key) in enumerate(classes):
    rejected, total = strength['classes'][key] if key else strength['prose']
    pct = 100*rejected/total
    ax.barh(y, pct, height=.56, color='#60a5fa')
    ax.text(max(pct+.5, .5), y, f'{rejected}/{total}', va='center', fontsize=11)
ax.set(yticks=list(range(7)), yticklabels=[x[0] for x in classes], xlim=(0, 38),
       xlabel='Rejected by the scoring CFG (%)',
       title='Mutation sensitivity depends on the class')
ax.invert_yaxis()
ax.spines[['top', 'right', 'left']].set_visible(False)
fig.savefig(OUT/'mutation-rejection.svg', metadata=metadata)
plt.close(fig)


def diagram(title, desc, height):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="760" height="{height}" viewBox="0 0 760 {height}" role="img" aria-labelledby="title desc">',
            f'<title id="title">{escape(title)}</title><desc id="desc">{escape(desc)}</desc>',
            f'<rect width="760" height="{height}" rx="16" fill="#111827"/>',
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8"/></marker></defs>']


def text(parts, x, y, value, size=19, color='#f3f4f6', mono=False):
    font = 'monospace' if mono else 'system-ui, sans-serif'
    parts.append(f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-family="{font}">{escape(value)}</text>')


def box(parts, x, y, w, h):
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="#1f2937" stroke="#475569"/>')


def arrow(parts, x1, y1, x2, y2):
    parts.append(f'<path d="M{x1} {y1} L{x2} {y2}" stroke="#94a3b8" stroke-width="2" marker-end="url(#arrow)"/>')


p=diagram('Extraction changes the counting unit', 'A constructor and two focus branches become one flattened entry under the historical extractor.', 490)
text(p, 30, 42, 'Extraction changes the counting unit', 25)
box(p, 30, 65, 700, 145)
text(p, 50, 96, 'SOURCE PROOF BODY', 14, '#93c5fd')
for i,line in enumerate(['constructor', '· exact h.2', '· exact h.1']):text(p, 50, 126+i*29, line, 21, mono=True)
arrow(p, 380, 215, 380, 258)
box(p, 30, 270, 700, 92)
text(p, 50, 299, 'HISTORICAL EXTRACTED ENTRY', 14, '#93c5fd')
text(p, 50, 335, 'constructor · exact h.2 · exact h.1', 21, mono=True)
arrow(p, 380, 368, 380, 398)
text(p, 50, 431, 'One leading keyword is counted; the CFG accepts the entry.', 20)
text(p, 50, 462, 'Acceptance cannot establish that extraction was faithful.', 18, '#cbd5e1')
p.append('</svg>');(OUT/'extraction.svg').write_text('\n'.join(p))

p=diagram('Grammar-aware sampling', 'Model probabilities and a tokenizer-aware matcher are combined to mask tokens; each sampled token updates the prefix and matcher.', 540)
text(p, 30, 42, 'Two inputs to the sampling decision', 25)
for x,title,lines in [(30,'MODEL',['Prompt + generated prefix','→ next-token logits']), (400,'MATCHER',['Grammar + tokenizer + prefix','→ allowed token IDs'])]:
    box(p,x,75,330,118);text(p,x+18,105,title,14,'#93c5fd')
    for i,line in enumerate(lines):text(p,x+18,140+i*28,line,18)
arrow(p,195,197,315,246);arrow(p,565,197,445,246)
box(p,170,258,420,110)
text(p,195,293,'MASK AND SAMPLE',14,'#6ee7b7')
text(p,195,325,'Disallow tokens; renormalize;',20)
text(p,195,353,'sample one surviving choice.',20)
arrow(p,380,373,380,411)
text(p,95,447,'Append the token and advance the matcher.',23)
text(p,95,485,'Repeat until valid completion or a recorded stop condition.',18,'#cbd5e1')
p.append('</svg>');(OUT/'decoding.svg').write_text('\n'.join(p))
print('Generated four standalone SVG figures in',OUT)
