#!/usr/bin/env python3
"""Generate the workshop's architecture and flow diagrams as PNGs.

The diagrams used to be ASCII art inside fenced code blocks. ASCII reads as
debug output, wraps badly on narrow screens, and cannot be styled. These are
generated from Graphviz sources kept in this file, so a diagram is edited by
changing a few lines here and re-running, not by nudging box-drawing characters.

Usage:
  python3 generate_diagrams.py            # render everything
  python3 generate_diagrams.py --list     # names only
  python3 generate_diagrams.py <name>     # one diagram

Requires Graphviz (`dot` on PATH). Output goes to
workshop/static/images/diagrams/<name>.png, with the .dot source written
alongside it so the exact input is reviewable in git.
"""
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "static" / "images" / "diagrams"

# Shared look. Muted fills with a single accent so the eye lands on the flow,
# not on the colours.
INK = "#232F3E"        # AWS squid ink, text and borders
ACCENT = "#FF9900"     # AWS orange, reserved for the one thing that matters
BOX = "#F7F8FA"        # near-white box fill
BOX2 = "#EAF1F8"       # tinted fill for AWS-managed things
EDGE = "#5A6B7B"

PREAMBLE = f"""
  graph [fontname="Helvetica", fontsize=11, bgcolor="white",
         rankdir=TB, nodesep=0.35, ranksep=0.45, pad=0.25];
  node  [fontname="Helvetica", fontsize=11, shape=box, style="rounded,filled",
         color="{INK}", fillcolor="{BOX}", fontcolor="{INK}", penwidth=1.2,
         margin="0.18,0.11"];
  edge  [fontname="Helvetica", fontsize=9, color="{EDGE}", fontcolor="{EDGE}",
         penwidth=1.1, arrowsize=0.8];
"""

DIAGRAMS = {}

# ---------------------------------------------------------------- introduction
# The running example: one agent, three deterministic tools, two eval lenses.
# Replaces the ASCII diagram that mislabelled the tools as "Agents".
DIAGRAMS["architecture-overview"] = f"""
digraph G {{
{PREAMBLE}
  user [label="You\\n(CLI prompt)", fillcolor="white"];

  subgraph cluster_proc {{
    label="One process: the Coordinator agent";
    fontname="Helvetica"; fontsize=10; fontcolor="{EDGE}";
    style="rounded,dashed"; color="{EDGE}";
    coord [label="Coordinator\\nan LLM that chooses which tool to call", fillcolor="{BOX2}"];
    sites [label="query_sites\\nattraction lookup"];
    route [label="plan_route\\nitinerary planner"];
    dine  [label="suggest_dining\\nrestaurant picks"];
    coord -> sites; coord -> route; coord -> dine;
  }}

  data [label="Luminara mock data\\nattractions, distances, restaurants", fillcolor="white", style="rounded,filled,dashed"];
  sites -> data [style=dotted, arrowhead=none];
  route -> data [style=dotted, arrowhead=none];
  dine  -> data [style=dotted, arrowhead=none];

  cw [label="CloudWatch\\naws/spans + the agent's log group", fillcolor="{BOX2}"];
  obs [label="GenAI Observability\\nthe trajectory you can see", fillcolor="{BOX2}"];

  user -> coord [label="  prompt"];
  coord -> cw [label="  one span per step", color="{ACCENT}", fontcolor="{ACCENT}", penwidth=1.6];
  cw -> obs;
}}
"""

# ------------------------------------------------------------------ path A
DIAGRAMS["path-a-architecture"] = f"""
digraph G {{
{PREAMBLE}
  subgraph cluster_ec2 {{
    label="Code Editor EC2  (you author and deploy here)";
    fontname="Helvetica"; fontsize=10; fontcolor="{EDGE}";
    style="rounded,dashed"; color="{EDGE}";
    cli [label="agentcore deploy", fillcolor="white"];
  }}

  subgraph cluster_rt {{
    label="AgentCore Runtime  (managed: your agent's production home)";
    fontname="Helvetica"; fontsize=10; fontcolor="{EDGE}";
    style="rounded"; color="{INK}"; bgcolor="#FBFCFD";
    container [label="Your container\\nStrands agent + 3 tools", fillcolor="{BOX}"];
    sidecar [label="OTEL sidecar  (injected for you)\\nemits records, exports spans,\\nstamps service.name", fillcolor="{BOX2}"];
    container -> sidecar [label="  lifecycle events"];
  }}

  obs [label="AgentCore Observability\\naws/spans + runtime log group", fillcolor="{BOX2}"];
  eval [label="Online Evaluation\\nscores each session  (Module 2)", fillcolor="{BOX2}"];

  cli -> container [label="  CodeZip + CDK"];
  sidecar -> obs [label="  OTLP", color="{ACCENT}", fontcolor="{ACCENT}", penwidth=1.6];
  obs -> eval;
}}
"""

# ------------------------------------------------------------------ path B
DIAGRAMS["path-b-architecture"] = f"""
digraph G {{
{PREAMBLE}
  subgraph cluster_ec2 {{
    label="Code Editor EC2  (your agent keeps running where it already runs)";
    fontname="Helvetica"; fontsize=10; fontcolor="{EDGE}";
    style="rounded"; color="{INK}"; bgcolor="#FBFCFD";
    agent [label="pi-mono travel agent\\nCoordinator + 3 tools", fillcolor="{BOX}"];
    adapter [label="OpenInference adapter  (you write this)\\nAGENT / LLM / TOOL spans\\nmodel name, token counts", fillcolor="{BOX2}"];
    agent -> adapter [label="  lifecycle events"];
  }}

  xray [label="AWS X-Ray OTLP endpoint\\nxray.{{region}}.amazonaws.com", fillcolor="{BOX2}"];
  spans [label="aws/spans\\nevery span, queryable", fillcolor="{BOX2}"];
  dash [label="GenAI Observability\\ndashboard", fillcolor="{BOX2}"];
  eval [label="AgentCore\\nEvaluation", fillcolor="{BOX2}"];

  adapter -> xray [label="  OTLP, SigV4 signed", color="{ACCENT}", fontcolor="{ACCENT}", penwidth=1.6];
  xray -> spans;
  spans -> dash;
  spans -> eval;
}}
"""

# ------------------------------------------------------------------ module 2
DIAGRAMS["module2-eval-pipeline"] = f"""
digraph G {{
{PREAMBLE}
  agent [label="Your agent  (from Module 1)\\nemits spans and one record per session", fillcolor="{BOX}"];
  cw [label="CloudWatch\\naws/spans  +  the agent's log group", fillcolor="{BOX2}"];
  cfg [label="Online Evaluation Config\\nwatches the log group,\\npicks up finished sessions", fillcolor="{BOX2}"];
  judge [label="LLM judge\\nscores against a rubric", fillcolor="{BOX2}"];
  results [label="Evaluation results log group\\nscore + explanation per session", fillcolor="{BOX}"];

  agent -> cw [label="  OTLP, SigV4 signed"];
  cw -> cfg [label="  session goes idle\\l  (5 min default)\\l"];
  cfg -> judge;
  judge -> results [label="  ~5 to 10 min", color="{ACCENT}", fontcolor="{ACCENT}", penwidth=1.6];
}}
"""

# ------------------------------------------------------------------ module 3
DIAGRAMS["module3-two-gates"] = f"""
digraph G {{
{PREAMBLE}
  change [label="You change something\\nmodel swap, prompt edit, new tool", fillcolor="white"];
  pre [label="Pre-deploy gate:  npm run eval\\n6 curated cases, both lenses\\nfast, repeatable, blocks the PR", fillcolor="{BOX}"];
  ship [label="Ship it", fillcolor="{BOX2}"];
  post [label="Post-deploy safety net:  Online Evaluation\\ncontent + trajectory on every real session\\ncontinuous, no one has to remember", fillcolor="{BOX}"];
  loop [label="Module 4:  failures become new cases", fillcolor="{BOX2}"];

  change -> pre;
  pre -> ship [label="  both lenses green", color="{ACCENT}", fontcolor="{ACCENT}", penwidth=1.6];
  pre -> change [label="  a lens went red", style=dashed, constraint=false];
  ship -> post;
  post -> loop [label="  regression on traffic\\l  you never anticipated\\l"];
  loop -> pre [label="  now guarded forever", style=dashed];
}}
"""

# ------------------------------------------------------------------ module 4
DIAGRAMS["module4-ground-truth-loop"] = f"""
digraph G {{
{PREAMBLE}
  rankdir=TB;
  prod [label="Production\\nreal users, real queries,\\nOnline Eval scoring every session", fillcolor="{BOX2}"];
  extract [label="Extract  (this module)\\nquery the results log group,\\ntake the lowest scores and the errors", fillcolor="{BOX}"];
  transform [label="Transform\\nquery + trajectory + judge reasoning\\nbecome Case objects", fillcolor="{BOX}"];
  dev [label="Dev\\nadd the cases, watch them fail,\\nfix the agent, watch them pass", fillcolor="{BOX}"];

  prod -> extract [label="  low scores\\l  and errors\\l"];
  extract -> transform;
  transform -> dev;
  dev -> prod [label="  deploy, now permanently guarded", color="{ACCENT}", fontcolor="{ACCENT}", penwidth=1.6];
}}
"""


def render(name: str) -> bool:
    src = DIAGRAMS[name]
    OUT.mkdir(parents=True, exist_ok=True)
    dot_path = OUT / f"{name}.dot"
    png_path = OUT / f"{name}.png"
    dot_path.write_text(src)
    try:
        # -Gdpi=144 keeps text crisp on high-density screens without a huge file.
        subprocess.run(
            ["dot", "-Tpng", "-Gdpi=144", "-o", str(png_path), str(dot_path)],
            check=True, capture_output=True, text=True,
        )
    except FileNotFoundError:
        print("  ERROR: Graphviz `dot` not found on PATH.")
        return False
    except subprocess.CalledProcessError as e:
        print(f"  ERROR rendering {name}: {e.stderr.strip()}")
        return False
    kb = png_path.stat().st_size / 1024
    print(f"  {name}.png ({kb:.0f} KB)")
    return True


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--list" in sys.argv:
        for k in DIAGRAMS:
            print(k)
        return 0
    names = args or list(DIAGRAMS)
    failed = 0
    for n in names:
        if n not in DIAGRAMS:
            print(f"  SKIP {n}: no such diagram")
            failed += 1
            continue
        if not render(n):
            failed += 1
    print(f"\n{len(names) - failed}/{len(names)} rendered into {OUT}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
