import networkx as nx
from pyvis.network import Network
import json

# ── Event & Weather Config ────────────────────────────────────────────────────
EVENT_FACTORS = {
    "normal_day": 1.0,
    "weekend": 1.4,
    "festival_day": 2.5,
    "shahi_snan": 8.0,
}

WEATHER_FACTORS = {
    "clear": 1.0,
    "light_rain": 0.8,
    "heavy_rain": 0.6,
}

# Node capacities (base, normal day)
BASE_CAPACITY = {
    1: 25000,
    2: 18000,
    3: 15000,
    4: 20000,
    5: 30000,
    6: 12000,
    7: 10000,
    8: 8000,
    9: 9000,
    10: 6000,
    11: 5000,
    12: 5000,
    13: 6000,
    14: 5000,
    15: 4000,
    16: 20000,
    17: 15000,
    18: 10000,
    19: 10000,
    20: 8000,
    21: 30000,
    22: 20000,
    23: 25000,
    24: 40000,
    25: 35000,
}

# Simulated current occupancy (normal day baseline)
CURRENT_OCC = {
    1: 18500,
    2: 12000,
    3: 9500,
    4: 14000,
    5: 22000,
    6: 7500,
    7: 6200,
    8: 4800,
    9: 5100,
    10: 3200,
    11: 3100,
    12: 2900,
    13: 3800,
    14: 2700,
    15: 2100,
    16: 11000,
    17: 8500,
    18: 5200,
    19: 4800,
    20: 3900,
    21: 8000,
    22: 3000,
    23: 6000,
    24: 9000,
    25: 7500,
}

# Source fusion weights for Crowd Intelligence Engine
FUSION_SOURCES = {
    "Gate Counters": 0.35,
    "Camera AI": 0.25,
    "QR Scans": 0.20,
    "GPS Samples": 0.10,
    "Volunteers": 0.10,
}


def dynamic_weight(
    dist_km, event="normal_day", weather="clear", base_congestion=0.5
):
    """
    Dynamic edge weight:
    Weight = Distance × Event Factor × (1 + Congestion) / Weather Factor
    """
    ef = EVENT_FACTORS[event]
    wf = WEATHER_FACTORS[weather]
    return round(dist_km * ef * (1 + base_congestion) / wf, 2)


def effective_capacity(node_id, event="normal_day", weather="clear"):
    base = BASE_CAPACITY[node_id]
    wf = WEATHER_FACTORS[weather]
    ef = EVENT_FACTORS[event]
    return int(base * wf), int(
        base * wf * 0.8
    )  # (effective_cap, safe_threshold)


def risk_level(occ, safe_thresh):
    ratio = occ / safe_thresh if safe_thresh > 0 else 1
    if ratio >= 1.0:
        return "CRITICAL 🔴", "#FF2D2D"
    if ratio >= 0.85:
        return "HIGH ⚠️", "#FF8C00"
    if ratio >= 0.65:
        return "MEDIUM 🟡", "#FFD700"
    return "LOW 🟢", "#00E676"


# ── Node definitions ──────────────────────────────────────────────────────────
LOCATION_NODES = {
    # P1 – Critical Zones
    1: ("Ram Ghat", "P1", "#FF2D2D"),
    2: ("Datt Akhada Ghat", "P1", "#FF2D2D"),
    3: ("Narsingh Ghat", "P1", "#FF2D2D"),
    4: ("Triveni Ghat", "P1", "#FF2D2D"),
    5: ("Mahakaleshwar Temple", "P1", "#FF2D2D"),
    # P2 – Religious Corridors
    6: ("Harsiddhi Temple", "P2", "#FF8C00"),
    7: ("Kal Bhairav Temple", "P2", "#FF8C00"),
    8: ("Mangalnath Temple", "P2", "#FF8C00"),
    9: ("Chintaman Ganesh", "P2", "#FF8C00"),
    10: ("Sandipani Ashram", "P2", "#FF8C00"),
    # P3 – Redistribution Nodes
    11: ("Freeganj Junction", "P3", "#FFD700"),
    12: ("Dewas Gate Junction", "P3", "#FFD700"),
    13: ("Tower Chowk", "P3", "#FFD700"),
    14: ("Nanakheda Junction", "P3", "#FFD700"),
    15: ("Kothi Road Junction", "P3", "#FFD700"),
    # P4 – Entry/Exit Gateways
    16: ("Ujjain Railway Station", "P4", "#00C5FF"),
    17: ("Nanakheda Bus Stand", "P4", "#00C5FF"),
    18: ("Indore Road Entry", "P4", "#00C5FF"),
    19: ("Dewas Road Entry", "P4", "#00C5FF"),
    20: ("Agar Road Entry", "P4", "#00C5FF"),
    # P5 – Buffer / Holding Areas
    21: ("Tent City North", "P5", "#00E676"),
    22: ("Emergency Holding Area", "P5", "#00E676"),
    23: ("Tent City South", "P5", "#00E676"),
    24: ("Overflow Parking", "P5", "#00E676"),
    25: ("Accommodation Zone", "P5", "#00E676"),
}

# Intelligence layer nodes (new)
INTEL_NODES = {
    101: ("☁️ Weather Feed", "DATA", "#BB86FC"),
    102: ("📅 Event Calendar", "DATA", "#BB86FC"),
    103: ("📷 Camera AI Counts", "DATA", "#CF6679"),
    104: ("📡 GPS Samples", "DATA", "#CF6679"),
    105: ("🔖 QR Checkpoints", "DATA", "#CF6679"),
    106: ("🚪 Gate Counters", "DATA", "#CF6679"),
    107: ("👷 Volunteer Reports", "DATA", "#CF6679"),
    200: ("🧠 Crowd Intelligence\nEngine", "ENGINE", "#FFFFFF"),
    201: ("⚡ Congestion Alerts", "OUTPUT", "#FF6B35"),
    202: ("🗺️ Route Optimizer", "OUTPUT", "#FF6B35"),
    203: ("📊 Authority Dashboard", "OUTPUT", "#FF6B35"),
    204: ("🔄 Compliance Feedback", "OUTPUT", "#FF6B35"),
}

# ── Base edges (location graph) ───────────────────────────────────────────────
BASE_EDGES = [
    (16, 11, 0.8),
    (16, 14, 1.2),
    (17, 14, 0.3),
    (18, 12, 1.5),
    (19, 12, 0.9),
    (20, 15, 2.1),
    (11, 13, 0.6),
    (12, 13, 0.7),
    (13, 14, 0.9),
    (14, 15, 1.1),
    (15, 11, 1.4),
    (13, 5, 0.5),
    (11, 7, 0.9),
    (12, 8, 1.3),
    (14, 9, 1.7),
    (15, 10, 2.0),
    (5, 1, 0.4),
    (5, 2, 0.6),
    (7, 3, 0.8),
    (6, 1, 0.5),
    (6, 4, 0.7),
    (8, 4, 1.1),
    (9, 3, 1.3),
    (10, 4, 1.6),
    (1, 2, 0.3),
    (2, 3, 0.4),
    (3, 4, 0.5),
    (14, 21, 0.8),
    (15, 23, 1.2),
    (12, 22, 1.0),
    (11, 24, 0.9),
    (13, 25, 1.5),
]

# Intelligence layer edges
INTEL_EDGES = [
    # Data sources → Engine
    (101, 200),
    (102, 200),
    (103, 200),
    (104, 200),
    (105, 200),
    (106, 200),
    (107, 200),
    # Engine → Outputs
    (200, 201),
    (200, 202),
    (200, 203),
    # Feedback loop
    (202, 204),
    (204, 200),
    # Engine influences key redistribution nodes
    (201, 13),
    (202, 11),
    (202, 14),
    (203, 16),
]

# ── Simulate scenario ─────────────────────────────────────────────────────────
SCENARIO = (
    "shahi_snan"  # change to: normal_day / weekend / festival_day / shahi_snan
)
WEATHER = "light_rain"  # change to: clear / light_rain / heavy_rain

G = nx.DiGraph()

# Add location nodes
for nid, (label, priority, color) in LOCATION_NODES.items():
    eff_cap, safe_thresh = effective_capacity(nid, SCENARIO, WEATHER)
    occ = CURRENT_OCC[nid]
    # Scale occupancy for scenario
    scaled_occ = min(int(occ * EVENT_FACTORS[SCENARIO]), eff_cap)
    risk_text, risk_color = risk_level(scaled_occ, safe_thresh)

    pct = round(scaled_occ / eff_cap * 100, 1) if eff_cap > 0 else 0
    size = {"P1": 38, "P2": 30, "P3": 24, "P4": 24, "P5": 20}[priority]

    # Make P1 nodes blink red on shahi_snan if critical
    node_color = (
        risk_color if priority == "P1" and SCENARIO == "shahi_snan" else color
    )

    tooltip = (
        f"<b>{label}</b><br>"
        f"Priority: {priority}<br>"
        f"<hr style='margin:4px 0;border-color:#444'>"
        f"Scenario: <b>{SCENARIO.replace('_', ' ').title()}</b><br>"
        f"Weather: <b>{WEATHER.replace('_', ' ').title()}</b><br>"
        f"<hr style='margin:4px 0;border-color:#444'>"
        f"Occupancy: <b>{scaled_occ:,}</b><br>"
        f"Effective Capacity: <b>{eff_cap:,}</b><br>"
        f"Safe Threshold (80%): <b>{safe_thresh:,}</b><br>"
        f"Load: <b>{pct}%</b><br>"
        f"Risk: <b>{risk_text}</b><br>"
        f"<hr style='margin:4px 0;border-color:#444'>"
        f"Event Factor: ×{EVENT_FACTORS[SCENARIO]}<br>"
        f"Weather Factor: ×{WEATHER_FACTORS[WEATHER]}"
    )

    node_shape = "dot"
    label_lower = label.lower()
    if (
        "temple" in label_lower
        or "ashram" in label_lower
        or "ganesh" in label_lower
    ):
        node_shape = "star"
        label = "🕉️ " + label
    elif "ghat" in label_lower:
        node_shape = "hexagon"
        label = "🌊 " + label
    elif "junction" in label_lower or "chowk" in label_lower:
        node_shape = "triangle"
        label = "🚦 " + label
    elif (
        "entry" in label_lower
        or "station" in label_lower
        or "stand" in label_lower
    ):
        node_shape = "square"
        label = "🚉 " + label

    G.add_node(
        nid,
        label=label,
        title=tooltip,
        color=node_color,
        size=size,
        shape=node_shape,
        font={"size": 10, "color": "white"},
    )

# Add intelligence layer nodes
for nid, (label, layer, color) in INTEL_NODES.items():
    shape = (
        "diamond"
        if layer == "ENGINE"
        else ("square" if layer == "OUTPUT" else "triangle")
    )
    size = 45 if layer == "ENGINE" else (28 if layer == "OUTPUT" else 22)
    sources_info = ""
    if nid == 200:
        sources_info = (
            "<hr style='margin:4px 0;border-color:#444'>Fusion Weights:<br>"
            + "".join(
                [
                    f"• {k}: {int(v * 100)}%<br>"
                    for k, v in FUSION_SOURCES.items()
                ]
            )
        )
    G.add_node(
        nid,
        label=label,
        title=f"<b>{label}</b><br>Layer: {layer}{sources_info}",
        color=color,
        size=size,
        shape=shape,
        font={
            "size": 10,
            "color": "#0D0D1A" if layer == "ENGINE" else "white",
        },
    )

# Add location edges with dynamic weights
for src, dst, dist in BASE_EDGES:
    w = dynamic_weight(dist, SCENARIO, WEATHER)
    src_name = LOCATION_NODES[src][0]
    dst_name = LOCATION_NODES[dst][0]
    # Color edge by weight severity
    if w > 10:
        ecol = "#FF2D2D"
    elif w > 5:
        ecol = "#FF8C00"
    elif w > 2:
        ecol = "#FFD700"
    else:
        ecol = "#444466"

    # Define dynamic gate status based on severe congestion
    if w > 10:
        gate_status = "🚧 CLOSED"
        dashes = True
    else:
        gate_status = "🟢 OPEN"
        dashes = False

    G.add_edge(
        src,
        dst,
        label=f"{dist}km | {gate_status}",
        title=f"{src_name} → {dst_name}<br>Base dist: {dist}km<br>Dynamic weight: <b>{w}</b><br>Gate Status: {gate_status}<br>Event: {SCENARIO}<br>Weather: {WEATHER}",
        color=ecol,
        width=1.5,
        dashes=dashes,
    )

# Add intelligence edges
for src, dst in INTEL_EDGES:
    is_feedback = src == 204
    G.add_edge(
        src,
        dst,
        label="",
        title="Data flow" if not is_feedback else "Compliance feedback loop",
        color="#BB86FC" if src in INTEL_NODES else "#FF6B35",
        width=2 if src == 200 or dst == 200 else 1,
        dashes=is_feedback,
    )

# ── Compute Fixed Layout ──────────────────────────────────────────────────────
pos = nx.spring_layout(G, k=0.9, iterations=500, seed=42)
for n, p in pos.items():
    G.nodes[n]["x"] = float(p[0] * 1200)
    G.nodes[n]["y"] = float(p[1] * 1200)
    G.nodes[n]["fixed"] = True

# ── PyVis ─────────────────────────────────────────────────────────────────────
net = Network(
    height="860px",
    width="100%",
    bgcolor="#0A0A18",
    font_color="white",
    directed=True,
    notebook=False,
)
net.from_nx(G)

net.set_options("""
{
  "physics": {
    "enabled": false
  },
  "edges": {
    "font": { "size": 8, "color": "#888899", "align": "middle" },
    "smooth": { "type": "curvedCW", "roundness": 0.15 },
    "arrows": { "to": { "enabled": true, "scaleFactor": 0.6 } }
  },
  "nodes": {
    "shadow": { "enabled": true, "color": "rgba(0,0,0,0.6)", "size": 10 }
  },
  "interaction": {
    "hover": true,
    "tooltipDelay": 80,
    "navigationButtons": true,
    "keyboard": true,
    "dragNodes": false
  }
}
""")

# ── Legend + info panel ───────────────────────────────────────────────────────
scenario_colors = {
    "normal_day": "#00E676",
    "weekend": "#FFD700",
    "festival_day": "#FF8C00",
    "shahi_snan": "#FF2D2D",
}
sc = scenario_colors.get(SCENARIO, "#FFFFFF")
wc = {
    "clear": "#00C5FF",
    "light_rain": "#BB86FC",
    "heavy_rain": "#CF6679",
}.get(WEATHER, "#FFFFFF")

legend = f"""
<div style="
  position:fixed; top:16px; left:16px; z-index:999;
  background:rgba(10,10,24,0.95); border:1px solid #333366;
  border-radius:12px; padding:16px 20px; color:white;
  font-family:'Segoe UI',sans-serif; font-size:12px; min-width:230px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.7);
">
  <div style="font-size:17px;font-weight:700;color:#FFD700;letter-spacing:1px;margin-bottom:4px;">
    🕉 Simhastha Ujjain 2028
  </div>
  <div style="font-size:10px;color:#AAAACC;margin-bottom:12px;">Crowd Intelligence Knowledge Graph v2</div>

  <div style="background:rgba(255,255,255,0.05);border-radius:8px;padding:8px;margin-bottom:12px;">
    <div>Scenario: <span style="color:{sc};font-weight:700">{SCENARIO.replace("_", " ").upper()}</span></div>
    <div>Weather: <span style="color:{wc};font-weight:700">{WEATHER.replace("_", " ").upper()}</span></div>
    <div style="font-size:10px;color:#888;margin-top:4px;">
      Event ×{EVENT_FACTORS[SCENARIO]} | Weather ×{WEATHER_FACTORS[WEATHER]}
    </div>
  </div>

  <div style="font-weight:600;margin-bottom:6px;color:#AAAACC;font-size:10px;text-transform:uppercase;letter-spacing:1px">Location Nodes</div>
  {"".join([f'<div style="display:flex;align-items:center;gap:8px;margin:4px 0"><span style="width:12px;height:12px;border-radius:50%;background:{c};display:inline-block;flex-shrink:0"></span><span>{l}</span></div>' for l, c in [("P1 – Critical Zones", "#FF2D2D"), ("P2 – Religious Corridors", "#FF8C00"), ("P3 – Redistribution", "#FFD700"), ("P4 – Entry/Exit", "#00C5FF"), ("P5 – Buffer Zones", "#00E676")]])}

  <div style="font-weight:600;margin:10px 0 6px;color:#AAAACC;font-size:10px;text-transform:uppercase;letter-spacing:1px">Intelligence Layer</div>
  <div style="display:flex;align-items:center;gap:8px;margin:4px 0"><span style="width:12px;height:12px;background:#BB86FC;transform:rotate(45deg);display:inline-block;flex-shrink:0"></span><span>🧠 AI Engine (diamond)</span></div>
  <div style="display:flex;align-items:center;gap:8px;margin:4px 0"><span style="width:12px;height:12px;background:#BB86FC;clip-path:polygon(50% 0,100% 100%,0 100%);display:inline-block;flex-shrink:0"></span><span>Data Sources (triangle)</span></div>
  <div style="display:flex;align-items:center;gap:8px;margin:4px 0"><span style="width:12px;height:12px;background:#FF6B35;display:inline-block;flex-shrink:0"></span><span>Outputs (square)</span></div>

  <div style="font-weight:600;margin:10px 0 6px;color:#AAAACC;font-size:10px;text-transform:uppercase;letter-spacing:1px">Edge Weight (Dynamic)</div>
  <div style="display:flex;align-items:center;gap:8px;margin:3px 0"><span style="width:20px;height:3px;background:#FF2D2D;display:inline-block"></span><span>Critical (W&gt;10)</span></div>
  <div style="display:flex;align-items:center;gap:8px;margin:3px 0"><span style="width:20px;height:3px;background:#FF8C00;display:inline-block"></span><span>High (W 5–10)</span></div>
  <div style="display:flex;align-items:center;gap:8px;margin:3px 0"><span style="width:20px;height:3px;background:#FFD700;display:inline-block"></span><span>Medium (W 2–5)</span></div>
  <div style="display:flex;align-items:center;gap:8px;margin:3px 0"><span style="width:20px;height:3px;background:#444466;display:inline-block"></span><span>Low (W&lt;2)</span></div>

  <div style="margin-top:12px;padding-top:8px;border-top:1px solid #222244;font-size:10px;color:#666;">
    Nodes: {G.number_of_nodes()} | Edges: {G.number_of_edges()} | Hover any node/edge
  </div>
</div>
"""

out_path = "api/static/simhastha_kg_v2.html"
net.save_graph(out_path)

with open(out_path, "r") as f:
    html = f.read()
html = html.replace("<body>", "<body>\n" + legend, 1)
html = html.replace(
    "</body>",
    """
<script type="text/javascript">
  if (typeof network !== 'undefined') {
      network.once("stabilizationIterationsDone", function() {
          network.setOptions({ physics: false });
      });
  }
</script>
</body>
""",
)
with open(out_path, "w") as f:
    f.write(html)

print(f"Saved → {out_path}")
print(f"Nodes: {G.number_of_nodes()} | Edges: {G.number_of_edges()}")
print(f"Scenario: {SCENARIO} | Weather: {WEATHER}")
print(
    f"Sample dynamic weight (Ram Ghat edge, dist=0.4km): {dynamic_weight(0.4, SCENARIO, WEATHER)}"
)
