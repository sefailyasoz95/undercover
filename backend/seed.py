"""Rebuild the UnderCover database from data/: uv run -m backend.seed"""

from backend import db

if __name__ == "__main__":
    db.seed()
    print(f"Seeded {db.path()}")
