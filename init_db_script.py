from api.database import init_db
import os

print(f"Current working directory: {os.getcwd()}")
print("Initializing database...")
init_db()
print("Database initialized successfully.")
