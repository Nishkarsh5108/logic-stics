"""
simulation_engine.py — Orchestrates the full digital twin simulation loop.
HYBRID VERSION: 1x = Live Sync, >1x = Predictive Fast-Forward.
FIXED: Added safety check for websocket client removal to prevent crash.
"""
import time, threading, json, numpy as np, asyncio, httpx, datetime
import sys, os

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.graph_builder import build_synthetic_grid
from data.traffic_simulator import TrafficSimulator
from data.dataset_loader import generate_synthetic_traffic
from model.predictor import Predictor
from routing.dynamic_router import DynamicRouter
from routing.fleet_manager import FleetManager

TOMTOM_KEY = os.environ.get("TOMTOM_KEY", "po8RAcqnVRmWqMl9l4RRVp8IYZdv2P4X")

class SimulationEngine:
    """Full digital-twin simulation orchestrator."""

    def __init__(self, num_nodes_side: int = 15, num_vehicles: int = 30):
        n = num_nodes_side
        self.num_nodes = n * n

        # 1) Build graph
        print("[SimEngine] Building graph ...")
        self.adj, self.node_features = build_synthetic_grid(n, n, out_dir="data/raw")

        # 2) Generate synthetic training data & train if needed
        if not os.path.exists("data/processed/train.npz"):
            print("[SimEngine] Generating synthetic traffic data ...")
            generate_synthetic_traffic(self.num_nodes, num_steps=12 * 288,
                                       out_dir="data/processed")

        # 3) Load predictor
        print("[SimEngine] Loading predictor ...")
        self.predictor = Predictor(
            checkpoint_path="model/checkpoints/best_model.pt",
            adj_path="data/raw/graph_data.pkl",
            scaler_path="data/processed/scaler.pkl")

        # 4) Traffic simulator
        self.traffic_sim = TrafficSimulator(self.num_nodes, self.adj)

        # 5) Router
        self.router = DynamicRouter(self.adj, self.node_features)

        # 6) Fleet
        self.fleet = FleetManager(num_vehicles, self.num_nodes, self.router)

        # State
        self.running = False
        
        # HYBRID TIME ENGINE VARIABLES
        self.speed_multiplier = 1   
        self.tick_interval = 2.0    
        self.current_sim_time = datetime.datetime.now()
        self.is_live_synced = True  
        
        self.current_prediction = None
        self.event_log: list[dict] = []
        self.websocket_clients: list = []
        self.step_count = 0
        
        # Real-time data state
        self.last_real_speed = 25.0 

        # Warm up
        for _ in range(15):
            self.traffic_sim.tick()

    async def _fetch_tomtom_speed(self):
        """Fetch real-time speed from TomTom for North Campus."""
        url = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
        params = {
            "point": "28.6892,77.2106",
            "unit": "KMPH",
            "key": TOMTOM_KEY
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    speed = data['flowSegmentData']['currentSpeed']
                    jitter = np.random.uniform(-0.4, 0.4)
                    return float(speed) + jitter
        except Exception as e:
            print(f"[TomTom] Error: {e}")
        return self.last_real_speed

    def set_speed(self, multiplier: int):
        self.speed_multiplier = max(1, min(multiplier, 100))
        if self.speed_multiplier == 1:
            self.is_live_synced = True
            self.current_sim_time = datetime.datetime.now() 
        else:
            self.is_live_synced = False

    def inject_disruption(self, node_id: int, severity: float = 0.2,
                          radius: int = 3, duration: int = 24,
                          event_type: str = "accident") -> dict:
        node_id = node_id % self.num_nodes
        d = self.traffic_sim.inject_disruption(node_id, severity, radius, duration, event_type)
        event = {"type": "disruption_injected", "node_id": node_id,
                 "severity": severity, "event_type": event_type,
                 "step": self.step_count}
        self.event_log.append(event)
        return event

    async def _run_tick(self) -> dict:
        """Execute one simulation tick with Hybrid Time."""
        if self.is_live_synced:
            self.current_sim_time = datetime.datetime.now()
        else:
            delta = datetime.timedelta(seconds=self.tick_interval * self.speed_multiplier)
            self.current_sim_time += delta

        time_decimal = self.current_sim_time.hour + (self.current_sim_time.minute / 60.0)
        day_of_week = self.current_sim_time.weekday()

        if self.step_count % 5 == 0:
            self.last_real_speed = await self._fetch_tomtom_speed()

        speeds = self.traffic_sim.tick()
        speeds[0] = self.last_real_speed 
        self.step_count += 1

        bottleneck_nodes = []
        if self.step_count % 3 == 0:
            history = self.traffic_sim.get_history_tensor(lookback=12)
            if history is not None:
                self.current_prediction = self.predictor.predict(history)
                bottleneck_nodes = self.current_prediction["bottleneck_nodes"]

        self.router.update_speeds(speeds)
        fleet_events = self.fleet.tick(speeds, bottleneck_nodes)
        self.event_log.extend(fleet_events)

        state = {
            "step": self.step_count,
            "traffic": {
                "speeds": speeds.tolist(),
                "time_of_day": time_decimal,
                "day_of_week": day_of_week,
                "current_speed": self.last_real_speed
            },
            "prediction": self.current_prediction,
            "fleet": self.fleet.get_state(),
            "events": fleet_events,
            "bottleneck_nodes": bottleneck_nodes,
            "live_anchor_speed": self.last_real_speed,
            "is_live_synced": self.is_live_synced,
            "speed_multiplier": self.speed_multiplier
        }
        return state

    async def run_loop(self):
        """Main simulation loop with safe WebSocket handling."""
        self.running = True
        while self.running:
            try:
                state = await self._run_tick()
                msg = json.dumps(state, default=str)
                
                dead = []
                # Attempt to send message to all connected clients
                for ws in self.websocket_clients:
                    try:
                        await ws.send_text(msg)
                    except Exception:
                        dead.append(ws)
                
                # SAFE REMOVAL: Fixed the 'list.remove(x): x not in list' error
                for ws in dead:
                    if ws in self.websocket_clients:
                        self.websocket_clients.remove(ws)

            except Exception as e:
                print(f"[SimLoop Error] {e}")
            
            await asyncio.sleep(self.tick_interval)

    def stop(self):
        self.running = False

    def get_snapshot(self) -> dict:
        now = datetime.datetime.now()
        return {
            "step": self.step_count,
            "traffic": {
                "time_of_day": now.hour + (now.minute / 60.0),
                "day_of_week": now.weekday()
            },
            "live_anchor_speed": self.last_real_speed,
            "num_nodes": self.num_nodes,
            "grid_size": 15
        }