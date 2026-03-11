from database_manager import DatabaseManager
from zombie_game_db import GameDB

# Database configuration - UPDATE PASSWORD!
db = DatabaseManager(
    host='localhost',
    database='zombie_game',
    user='zombie_user',
    password='violet230201'  # UPDATE THIS!
)

try:
    # Connect to database
    db.connect()
    
    # Initialize schema (only needed first time, safe to run multiple times)
    db.initialize_schema()
    
    # Run a small game (5v5)
    print("\n🎮 Starting game (5v5)...")
    game = GameDB(db, grid_size=20)
    game.run_game(num_humans=5, num_zombies=5, max_rounds=50)
    
    # Uncomment for large scale test (500v500)
    # print("\n🎮 Starting large game (500v500)...")
    # game = GameDB(db, grid_size=100)
    # game.run_game(num_humans=500, num_zombies=500, max_rounds=100)
    
finally:
    db.close()
