"""Entry point.  Run:  python app.py   ->  http://127.0.0.1:5000"""
import os

from lifelink import create_app
from seed import seed_demo_data

app = create_app()
seed_demo_data(app)          # creates admin + demo users only if DB is empty

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
