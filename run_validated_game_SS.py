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
    
    # Test 1: Small game with snapshots every 5 rounds
    print("\n🎮 Test 1: Small validated game (5v5) with 4 threads + SNAPSHOTS...")
    start_time = time.time()
    game = GameDBValidated(db, grid_size=20, num_threads=4, snapshot_interval=5)
    game.run_game(num_humans=5, num_zombies=5, max_rounds=50)
    elapsed = time.time() - start_time
    print(f"\n⏱️ Game completed in {elapsed:.2f} seconds")
    print(f"📸 Snapshots captured: {len(game.snapshot_ids)}")
    
    # Test 2: Medium game with snapshots every 10 rounds
    print("\n\n🎮 Test 2: Medium validated game (50v50) with 8 threads + SNAPSHOTS...")
    start_time = time.time()
    game = GameDBValidated(db, grid_size=50, num_threads=8, snapshot_interval=10)
    game.run_game(num_humans=50, num_zombies=50, max_rounds=100)
    elapsed = time.time() - start_time
    print(f"\n⏱️ Game completed in {elapsed:.2f} seconds")
    print(f"📸 Snapshots captured: {len(game.snapshot_ids)}")
    
    # Test 3: Large game (uncomment to test) - snapshots every 20 rounds
    # print("\n\n🎮 Test 3: Large validated game (500v500) with 16 threads + SNAPSHOTS...")
    # start_time = time.time()
    # game = GameDBValidated(db, grid_size=100, num_threads=16, snapshot_interval=20)
    # game.run_game(num_humans=500, num_zombies=500, max_rounds=100)
    # elapsed = time.time() - start_time
    # print(f"\n⏱️ Game completed in {elapsed:.2f} seconds")
    # print(f"📸 Snapshots captured: {len(game.snapshot_ids)}")
    
finally:
    db.close()
