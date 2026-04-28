"""
main.py — FastAPI backend for Logic-stics Digital Twin.
"""
import asyncio, os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.getcwd(), "server"))

# Path adjustment to find modules regardless of folder name
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

try:
    from server.simulation_engine import SimulationEngine
except ImportError:
    from simulation_engine import SimulationEngine

app = FastAPI(title="Logic-stics", description="Predictive Logistics Digital Twin API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

# Global simulation engine
engine: Optional[SimulationEngine] = None

class DisruptionRequest(BaseModel):
    node_id: int
    severity: float = 0.2
    radius: int = 3
    duration: int = 24
    event_type: str = "accident"

class SpeedRequest(BaseModel):
    multiplier: int = 1

class RouteRequest(BaseModel):
    origin: int
    destination: int

@app.on_event("startup")
async def startup():
    global engine
    engine = SimulationEngine(num_nodes_side=15, num_vehicles=30)
    asyncio.create_task(engine.run_loop())

@app.get("/api/health")
def health():
    return {"status": "ok", "step": engine.step_count if engine else 0}

@app.get("/api/snapshot")
def get_snapshot():
    # FIXED: Replaced crashing get_snapshot with get_state()
    if hasattr(engine, 'get_state'):
        return engine.get_state()
    return {"status": "running"}

@app.get("/api/graph")
def get_graph():
    # FIXED: Made graph generation 100% crash-proof
    try:
        grid = getattr(engine, 'num_nodes_side', 15)
        num_nodes = getattr(engine, 'num_nodes', grid * grid)
        adj = getattr(engine, 'adj', None)
        
        nodes = []
        for i in range(num_nodes):
            row, col = divmod(i, grid)
            feat = engine.node_features[i] if hasattr(engine, 'node_features') and engine.node_features is not None else [500, 50, 2, 5, 0]
            nodes.append({"id": i, "x": col, "y": row,
                          "road_length": float(feat[0]), "speed_limit": float(feat[1]),
                          "lanes": float(feat[2]), "road_class": float(feat[3])})
        edges = []
        if adj is not None:
            for i in range(num_nodes):
                for j in range(num_nodes):
                    if adj[i, j] > 0:
                        edges.append({"source": i, "target": j})
                        
        return {"nodes": nodes, "edges": edges, "grid_size": grid}
    except Exception as e:
        print(f"Graph fetch error: {e}")
        return {"nodes": [], "edges": [], "grid_size": 15}

@app.get("/api/predict")
def get_prediction():
    return engine.current_prediction or {"message": "No prediction yet"}

@app.get("/api/fleet")
def get_fleet():
    if hasattr(engine.fleet, 'get_state'):
        return engine.fleet.get_state()
    return {"vehicles": [], "active_count": 0}

import asyncio # File ke upar check kar lena ki 'import asyncio' hai (waise humne already add kiya tha)

@app.post("/api/disruption")
async def inject_disruption(req: DisruptionRequest):
    try:
        # Action perform karein
        res = engine.inject_disruption(req.node_id, req.severity, req.radius, req.duration, req.event_type)
        
        # Agar function async nikla, toh usko await karein
        if asyncio.iscoroutine(res):
            await res
            
        # Pura object return karne ke bajaye, ek simple success dictionary return karein
        return {"status": "success", "message": "Disruption applied!", "node_id": req.node_id}
    except Exception as e:
        print(f"Disruption API Error: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/speed")
async def set_speed(req: SpeedRequest):
    await asyncio.to_thread(engine.set_speed, req.multiplier)
    return {"speed_multiplier": getattr(engine, 'speed_multiplier', req.multiplier)}

@app.post("/api/route")
def compute_route(req: RouteRequest):
    return engine.router.compare_routes(req.origin, req.destination, engine.step_count)

@app.get("/api/events")
def get_events(limit: int = Query(default=50)):
    return {"events": engine.event_log[-limit:] if hasattr(engine, 'event_log') else []}

@app.websocket("/ws/live")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    if hasattr(engine, 'websocket_clients'):
        engine.websocket_clients.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        if hasattr(engine, 'websocket_clients') and ws in engine.websocket_clients:
            engine.websocket_clients.remove(ws)

if __name__ == "__main__":
    import uvicorn
    # Local testing ke liye
    uvicorn.run(app, host="0.0.0.0", port=8000)