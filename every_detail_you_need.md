# Logic-stics — Complete Hackathon Presentation Guide

> **Purpose**: This document contains *everything* you need to present Logic-stics to hackathon judges. Every claim is backed by the actual codebase. Existing documents are *referenced by name* so you can upload them directly to NotebookLM.

---

## 1. The Elevator Pitch (30 seconds)

> "Modern supply chains lose **$4 billion annually** to reactive logistics — trucks get rerouted *after* they're already stuck in traffic. We built **Logic-stics**, a Predictive Digital Twin that uses a **Graph Neural Network** to predict traffic bottlenecks **60 minutes into the future** and dynamically reroutes delivery fleets *before* congestion even forms. It's deployed live — backend on Render, frontend on Vercel — and anchored to **real-time traffic data** from the TomTom API near Delhi University."

---

## 2. Problem Statement — Why This Matters

**The Hackathon Challenge**: *"Design a scalable system capable of continuously analyzing multifaceted transit data to preemptively detect and flag potential supply chain disruptions."*

**What's wrong with current systems?**

- Standard GPS routing (Google Maps, Waze) is **reactive** — it reroutes you *after* the jam has formed
- Supply chains manage millions of shipments but have **zero predictive visibility**
- A single highway accident can cascade into $50M+ in delayed freight across a region

**Our answer**: Don't wait for congestion. **Predict it 60 minutes ahead** using the topology of the road network itself, then reroute fleets preemptively.

---

## 3. Why Every Technology Was Chosen

### 3.1 Why ASTGCN (and not LSTM, CNN, or Transformer)?

| Alternative                    | Why we rejected it                                                                                                                                                                                                 | Why ASTGCN wins                                                                                                                                   |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| **LSTM / GRU**           | Only captures*temporal* patterns. Roads are not a flat sequence — they're a graph. An LSTM has zero idea that Node 45 is physically connected to Node 46.                                                       | ASTGCN natively operates on graphs.                                                                                                               |
| **CNN**                  | Treats data as a 2D image grid (Euclidean). Roads are**non-Euclidean** — intersections have irregular connectivity. A CNN can't model that a 6-lane highway affects traffic differently than a side street. | ASTGCN uses Chebyshev spectral convolutions on the actual adjacency matrix.                                                                       |
| **Standard Transformer** | Quadratic O(N²) complexity. Scales poorly beyond a few hundred nodes. Also doesn't natively understand graph topology.                                                                                            | ASTGCN has linear complexity in edge count O(\|E\|).                                                                                              |
| **Simpler GCN (STGCN)**  | No attention mechanism — treats all neighbors and all timesteps with equal importance.                                                                                                                            | ASTGCN adds**Spatial Attention** (which neighbors matter most?) and **Temporal Attention** (which historical timesteps matter most?). |

> 📄 **For deep research backing**: See `resource.md` in the repo — it's a 40,000-word research document covering the full state-of-the-art (2023–2026) of spatio-temporal graph models, including BigST, ST-LLM, PDG2Seq, SupplyGraph, and why ASTGCN was selected as the optimal hackathon architecture.

### 3.2 Why Chebyshev Spectral Convolutions?

Standard graph convolutions require full eigendecomposition of the Laplacian — O(N³). Chebyshev polynomials **approximate** spectral filters using only K-hop neighborhoods (we use K=3), making it tractable for 225 nodes in real-time.

**Actual code**: `model/astgcn.py` lines 18–44 — `scaled_laplacian()` computes `~L = 2L/λ_max - I`, then `cheb_polynomials()` builds T₀…T_{K-1} using the recurrence relation `T_k = 2L·T_{k-1} - T_{k-2}`.

### 3.3 Why a 15×15 Grid (225 nodes)?

- **Realistic enough** to demonstrate cascading disruptions and multi-hop rerouting
- **Fast enough** to run real-time inference every 3 simulation steps without lag
- **Scalable architecture** — the code supports any size via `build_synthetic_grid(rows, cols)` and also has a full OSMnx pipeline (`extract_city_graph()`) to load real city data

### 3.4 Why Time-Dependent A* (not Dijkstra)?

Dijkstra finds shortest paths with **static** weights. Our A* implementation in `routing/dynamic_router.py` is **time-dependent**:

- When evaluating edge (u,v), it asks: *"When will the truck actually arrive at v?"* (computed as `steps_from_now = int(cumulative_time / 300)`)
- It then queries the ASTGCN's **predicted speed at that future timestep** — not the current speed
- This means the algorithm routes around a bottleneck **that doesn't exist yet** but is predicted to form

The heuristic uses Euclidean distance divided by max speed (120 km/h) — admissible and consistent, guaranteeing optimality.

### 3.5 Why FastAPI + WebSockets (not REST polling)?

- REST polling would create 2-second latency spikes between state updates
- WebSockets give us **push-based streaming** — the server broadcasts state to all connected clients instantly
- FastAPI's native `async/await` support means the simulation loop, TomTom API calls, and WebSocket broadcasts all run concurrently without blocking

### 3.6 Why React + HTML Canvas (not D3.js, Mapbox, or Leaflet)?

- **D3.js**: Too heavy for real-time 60fps animation of 225 nodes + 30 vehicles
- **Mapbox/Leaflet**: Designed for real geographic maps. Our grid is synthetic — we'd be fighting the library
- **HTML Canvas with React**: Direct pixel control, 2x DPI scaling for retina displays, zero DOM overhead. The entire map redraws every frame via `useEffect` — exactly what a real-time dashboard needs

### 3.7 Why Framer Motion?

Used in `KPIDashboard.tsx` and `AlertFeed.tsx` for:

- **KPI cards**: Staggered entry animations (`delay: index * 0.05`) — makes the dashboard feel premium
- **Alert feed**: `AnimatePresence` for smooth enter/exit of event cards — critical for a live feed that constantly updates

### 3.8 Why TomTom API (not Google Maps Traffic)?

- TomTom provides **free-tier flow segment data** with current speed + free-flow speed
- We anchor Node 0 of our simulation grid to real-time speed data from **Mall Road near Delhi University** (28.6892°N, 77.2106°E)
- This makes the demo grounded in reality — "that speed number comes from a real sensor right now"

### 3.9 Why Dual Deployment (Render + Vercel)?

| Component                                               | Platform         | Why                                                                           |
| ------------------------------------------------------- | ---------------- | ----------------------------------------------------------------------------- |
| **Python Backend** (FastAPI, PyTorch, sim engine) | **Render** | Supports long-running processes, WebSockets, and Python. Free tier available. |
| **React Frontend** (Vite build)                   | **Vercel** | Optimized for static frontends, global CDN, instant deploys from Git.         |

The frontend connects to `https://logic-stics.onrender.com` for API calls and `wss://logic-stics.onrender.com/ws/live` for WebSocket streaming. Vercel serves the static bundle from `frontend/dist`.

### 3.10 Why Docker Multi-Stage Build?

The `Dockerfile` uses a 2-stage build:

1. **Stage 1** (`node:20-slim`): Builds the React frontend → produces `dist/`
2. **Stage 2** (`python:3.11-slim`): Installs Python deps, copies backend code + built frontend

This keeps the final image small (no Node.js runtime in production) and makes the entire stack deployable as a single container.

---

## 4. Full Architecture — How Data Flows

```
[TomTom API] ──live speed──▶ [SimulationEngine] ──anchors Node 0──▶ [TrafficSimulator]
                                     │                                      │
                                     │                               tick() every 2s
                                     │                                      │
                                     ▼                                      ▼
                              [Predictor]◀──history tensor──── [history_buffer (60 steps)]
                                     │
                              ASTGCN inference (GPU/CPU)
                                     │
                                     ▼
                         predicted_speeds (12 steps ahead)
                         bottleneck_nodes (speed < μ-σ or < 35 km/h)
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                                  ▼
            [DynamicRouter]                    [FleetManager]
         updates edge weights              checks if any vehicle's
         with future speeds                route passes through a
                    │                       predicted bottleneck
                    │                              │
                    ▼                              ▼
            Time-dep A* finds              compare_routes() → if
            fastest future path            dynamic < static → REROUTE
                    │                              │
                    └──────────┬───────────────────┘
                               ▼
                     [WebSocket Broadcast]
                               │
                               ▼
                    [React Dashboard @ 60fps]
                    ├── MapView (Canvas)
                    ├── AlertFeed (live events)
                    ├── KPIDashboard (metrics)
                    └── ControlPanel (disruption inject)
```

---

## 5. Module-by-Module Breakdown

### 5.1 Data Pipeline (`data/`)

| File                     | What it does                                                                                                                                                                                                                                                                                | Key design decision                                                                                                                                                                                                                   |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `graph_builder.py`     | Builds the road network graph. Has**two modes**: (1) `extract_city_graph()` downloads real city data from OpenStreetMap via OSMnx, converts to a dual graph, and exports to PyTorch Geometric tensors. (2) `build_synthetic_grid()` creates a 15×15 directed grid for demos.     | **Dual-graph formulation**: roads become nodes, intersections become edges. This lets road-level features (length, speed limit, lanes, road class, one-way) live directly on nodes — exactly what GNN message-passing expects. |
| `traffic_simulator.py` | Maintains live traffic state. Simulates daily rush hours via Gaussian peaks at 8 AM and 6 PM, weekend speed boosts, and random noise. Supports disruption injection with**BFS-based spatial decay** — a disruption at Node X radiates outward with `severity^(1/(depth+1))` decay. | The BFS radius system makes disruptions realistic — they don't just affect one node, they cascade to neighbors.                                                                                                                      |
| `dataset_loader.py`    | Handles METR-LA benchmark loading + synthetic data generation. Implements `StandardScaler` (channel-0 normalization, the industry standard). Creates sliding windows `(samples, lookback, N, features)`. Splits 70/10/20 chronologically.                                               | Channel-0 normalization matches the METR-LA/PeMS benchmark protocol exactly — ensuring our model is trained the same way research papers train theirs.                                                                               |

### 5.2 Model (`model/`)

| File             | What it does                                                                                                                                                                                                                                                                                                            | Key design decision                                                                                                                                                             |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `astgcn.py`    | Full ASTGCN implementation:`SpatialAttention` (learns which nodes matter), `TemporalAttention` (learns which timesteps matter), `ChebConv` (K=3 Chebyshev graph convolution), `STBlock` (spatial→temporal with residual + LayerNorm), and the full `ASTGCN` model (2 stacked ST-Blocks + output projection). | **Residual connections** prevent vanishing gradients. **LayerNorm** (not BatchNorm) because batch sizes vary. **2 blocks** balances depth vs. over-smoothing. |
| `trainer.py`   | Training loop with `masked_mae` loss (ignores zero/NaN sensor readings), `OneCycleLR` scheduler, gradient clipping at 5.0, and early stopping (patience=10).                                                                                                                                                        | **Masked loss** is critical — real traffic datasets have sensor failures. Training on zeros would teach the model to predict failures, not traffic.                      |
| `predictor.py` | Inference engine. Loads checkpoint, normalizes input, runs forward pass, denormalizes output.**Bottleneck detection**: a node is flagged if `min_predicted_speed < max(mean - 1σ, 35 km/h)`. Has a **heuristic fallback** (exponential decay) when no trained model exists.                              | The dual-threshold (statistical + absolute 35 km/h floor) catches both relative slowdowns AND absolute near-stoppages.                                                          |

### 5.3 Routing (`routing/`)

| File                  | What it does                                                                                                                                                                                                                                                                                                                      | Key design decision                                                                                                                                                              |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dynamic_router.py` | Builds a NetworkX DiGraph from the adjacency matrix. Implements time-dependent A*.`_get_travel_time(u, v, steps_from_now)` queries predicted future speeds. `compare_routes()` computes static vs. dynamic routes for the "time saved" metric.                                                                                | The `node_steps` tracker estimates how many 5-min intervals into the future the vehicle will be at each node — this is what makes the routing truly **time-dependent**. |
| `fleet_manager.py`  | Simulates 30 delivery trucks with cargo types (electronics, food, medicine, etc.). Each tick: checks if remaining route passes through any bottleneck → if yes, calls `compare_routes()` → if dynamic route saves time, reroutes the vehicle. Delivered vehicles **respawn** with new destinations for continuous demo. | The respawn mechanic is smart — it means the demo never "runs out" of vehicles. The KPI counters keep accumulating, making longer demos more impressive.                        |

### 5.4 Server (`server/`)

| File                     | What it does                                                                                                                                                                                                                        | Key design decision                                                                                                                                                                                     |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `simulation_engine.py` | The orchestrator. Initializes all components, runs the async tick loop (every 2s), broadcasts state via WebSocket. Fetches TomTom live speed every 5 ticks. Supports**time travel** (offset hours for historical simulation). | TomTom data anchors Node 0 to real-world speed — this is what lets you say "our system ingests live traffic data."                                                                                     |
| `main.py`              | FastAPI app with 8 endpoints (see API table in README). CORS wide-open for hackathon (`allow_origins=["*"]`). WebSocket endpoint at `/ws/live` with auto-cleanup of dead connections.                                           | The `try/except ImportError` pattern for `simulation_engine` makes the import work regardless of whether you run from project root or `server/` directory — critical for deployment flexibility. |

### 5.5 Frontend (`frontend/src/`)

| File                 | What it does                                                                                                                                                                                                                                                                                       | Key design decision                                                                                                                                                  |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `useSimulation.ts` | Custom React hook. Connects to Render backend via WebSocket with**auto-reconnect** (3s delay). Fetches graph topology once on mount. Exposes `injectDisruption()` and `setSpeed()` API wrappers.                                                                                         | Auto-reconnect is essential — Render's free tier cold-starts, so the first connection might fail.                                                                   |
| `App.tsx`          | CSS Grid layout: `320px sidebar                                                                                                                                                                                                                                                                    | flex map                                                                                                                                                             |
| `MapView.tsx`      | HTML Canvas renderer at 2x DPI. Draws: grid background → edges (color-coded by speed) → bottleneck halos (radial gradient, severity-scaled) → disruption pulsing rings → intersection nodes → vehicle dots (purple=normal, cyan=rerouted). Supports mouse hover tooltips and click-to-inject. | 2x DPI canvas (`canvas.width = dimensions.width * 2` + `ctx.scale(2,2)`) makes the map crisp on retina displays — a subtle but important visual quality signal. |
| `ControlPanel.tsx` | Simulation clock display, speed selector (1x/5x/10x/30x/60x), disruption injection button, system info readout (model, lookback, horizon, grid size, vehicles).                                                                                                                                    | Shows judges the technical parameters at a glance without needing to explain.                                                                                        |
| `KPIDashboard.tsx` | 6 KPI cards with Framer Motion stagger animation: Active Shipments, Deliveries, Reroutes, Time Saved, Avg Delivery Time, Efficiency %.                                                                                                                                                             | These are the**quantitative proof** that the system works — judges love numbers.                                                                              |
| `AlertFeed.tsx`    | Live event feed with animated entry/exit. Color-coded cards: blue=reroute, red=disruption, green=delivery. Shows last 30 events.                                                                                                                                                                   | This is the "wow factor" — events stream in real-time, making the system feel alive.                                                                                |
| `index.css`        | 637-line design system. Dark theme (`#0a0e1a`), glassmorphism (`backdrop-filter: blur(12px)`), Inter + JetBrains Mono fonts, CSS custom properties for colors/spacing/transitions, responsive breakpoints, custom scrollbar, gradient logo.                                                    | The glassmorphism + dark theme + JetBrains Mono for numbers = enterprise-grade dashboard aesthetic.                                                                  |

---

## 6. Deployment Architecture

```
┌─────────────────────────────────┐     ┌──────────────────────────┐
│         VERCEL (Frontend)       │     │     RENDER (Backend)     │
│  Static React build (dist/)    │────▶│  FastAPI + PyTorch       │
│  Global CDN                    │ API │  WebSocket server        │
│  Auto-deploy from Git          │◀────│  TomTom API integration  │
│                                │ WS  │  Simulation engine       │
└─────────────────────────────────┘     └──────────────────────────┘
```

**Live URLs**:

- Frontend: Deployed on Vercel (your friend's deployment)
- Backend API: `https://logic-stics.onrender.com`
- WebSocket: `wss://logic-stics.onrender.com/ws/live`

**Why split deployment?** Vercel can't run Python/PyTorch. Render can't serve static files as efficiently. Split = best of both worlds.

---
