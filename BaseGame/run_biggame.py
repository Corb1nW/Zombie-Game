from database_manager import DatabaseManager
from zombie_game_validated_SS import GameDBValidated
import time

# Database configuration
db = DatabaseManager(
    host='localhost',
    database='zombie_game',
    user='zombie_user',
    password='violet230201'
)

try:
    # Connect to database
    db.connect()
    
    # Initialize schema
    db.initialize_schema()
    

    print("\n🎮 1000 vs 1000")
    start_time = time.time()
    game = GameDBValidated(db, grid_size=1000, num_threads=16, snapshot_interval=5)
    game.run_game(num_humans=1000, num_zombies=1000, max_rounds=500)
    elapsed = time.time() - start_time
    print(f"\n⏱️ Game completed in {elapsed:.2f} seconds")
    print(f"📸 Snapshots captured: {len(game.snapshot_ids)}")
    
    
finally:
    db.close()
