"""
train_and_run.py — Final Optimized Version for Render.
Fixes: Folder structure mapping and module name mismatches.
"""
import os, sys

# Path setup to ensure 'server' folder is visible
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.getcwd())

def main():
    print("=" * 60)
    print("  Logic-stics — Official Cloud Deployment")
    print("=" * 60)

    print("\n[✓] Bypassing training. Using pre-trained model.")

    # Step 4: Launch backend server
    print("\n[4/4] Launching backend server ...")
    import uvicorn
    
    # FINAL IMPORT LOGIC
    # Aapki file ka naam 'main.py' hai, isliye hum 'main' se import karenge
    try:
        from server.main import app
        print("  ✓ Imported 'app' from 'server.main'")
    except ImportError:
        try:
            # Fallback: Agar Python seedha server folder ke andar dekh raha ho
            sys.path.append(os.path.join(os.getcwd(), "server"))
            from main import app
            print("  ✓ Imported 'app' from 'main' (fallback)")
        except ImportError as e:
            print(f" ERROR: Could not find app instance. {e}")
            sys.exit(1)

    if __name__ == "__main__":
        port = int(os.environ.get("PORT", 8000))
        print(f" Server starting on port {port}...")
        uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()