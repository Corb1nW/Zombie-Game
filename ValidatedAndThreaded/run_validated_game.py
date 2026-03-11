from database_manager import DatabaseManager
from zombie_game_validated import GameDBValidated
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
    
    # Test 1: Small game with validation
    print("\n🎮 Test 1: Small validated game (5v5) with 4 threads...")
    start_time = time.time()
    game = GameDBValidated(db, grid_size=20, num_threads=4)
    game.run_game(num_humans=5, num_zombies=5, max_rounds=50)
    elapsed = time.time() - start_time
    print(f"\n⏱️ Game completed in {elapsed:.2f} seconds")
    
    # Test 2: Medium game with validation
    print("\n\n🎮 Test 2: Medium validated game (50v50) with 8 threads...")
    start_time = time.time()
    game = GameDBValidated(db, grid_size=50, num_threads=8)
    game.run_game(num_humans=50, num_zombies=50, max_rounds=100)
    elapsed = time.time() - start_time
    print(f"\n⏱️ Game completed in {elapsed:.2f} seconds")
    
    # Test 3: Large game (uncomment to test)
    # print("\n\n🎮 Test 3: Large validated game (500v500) with 16 threads...")
    # start_time = time.time()
    # game = GameDBValidated(db, grid_size=100, num_threads=16)
    # game.run_game(num_humans=500, num_zombies=500, max_rounds=100)
    # elapsed = time.time() - start_time
    # print(f"\n⏱️ Game completed in {elapsed:.2f} seconds")
    
finally:
    db.close()
