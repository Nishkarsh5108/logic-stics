"""
train_and_run.py — Final Optimized Version for Render.
Fixes: Uvicorn execution logic and path fallbacks.
"""
import os, sys

# Path setup
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.getcwd())

def get_app():
    print("=" * 60)
    print("  Logic-stics — Official Cloud Deployment")
    print("=" * 60)
    print("\n[✓] Bypassing training. Using pre-trained model.")
    print("\n[4/4] Attempting to import backend server ...")
    
    try:
        from server.main import app
        print("  ✓ Imported 'app' from 'server.main'")
        return app
    except ImportError:
        try:
            sys.path.append(os.path.join(os.getcwd(), "server"))
            from main import app
            print("  ✓ Imported 'app' from 'main' (fallback)")
            return app
        except ImportError as e:
            print(f"  ❌ ERROR: Could not find app instance. {e}")
            sys.exit(1)

if __name__ == "__main__":
    # 1. Get the app instance
    app_instance = get_app()
    
    # 2. Launch Uvicorn (Outside the function logic)
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"  🚀 Server launching on port {port}...")
    uvicorn.run(app_instance, host="0.0.0.0", port=port)