import sys
sys.path.insert(0, '.')

from database_manager import DatabaseManager
from snapshot_manager3 import SnapshotManager


db = DatabaseManager(
    host='localhost',
    database='zombie_game',
    user='zombie_user',
    password='violet230201'
)

try:
    print("=" * 70)
    print("SNAPSHOT SYSTEM TEST (psycopg 3)")
    print("=" * 70)
    
    # Connect
    print("\n1️⃣ Connecting to database...")
    db.connect()
    
    # Initialize schema
    print("\n2️⃣ Initializing schemas...")
    db.initialize_schema()
    
    # Create snapshot manager
    print("\n3️⃣ Creating snapshot manager...")
    sm = SnapshotManager(db)
    
    # Create a test game
    print("\n4️⃣ Creating test game session...")
    game_id = db.create_game_session(grid_size=20)
    
    # Insert test agents
    print("\n5️⃣ Inserting test agents...")
    test_agents = [
        {
            'name': 'Human_1',
            'agent_type': 'Human',
            'health': 100,
            'max_health': 100,
            'attack_power': 20,
            'base_attack_power': 20,
            'x': 5,
            'y': 5,
            'role_name': None,
            'role_data': {}
        },
        {
            'name': 'Human_2',
            'agent_type': 'Human',
            'health': 100,
            'max_health': 100,
            'attack_power': 20,
            'base_attack_power': 20,
            'x': 6,
            'y': 6,
            'role_name': None,
            'role_data': {}
        },
        {
            'name': 'Zombie_1',
            'agent_type': 'Zombie',
            'health': 80,
            'max_health': 80,
            'attack_power': 15,
            'base_attack_power': 15,
            'x': 15,
            'y': 15,
            'role_name': None,
            'role_data': {}
        },
        {
            'name': 'Zombie_2',
            'agent_type': 'Zombie',
            'health': 80,
            'max_health': 80,
            'attack_power': 15,
            'base_attack_power': 15,
            'x': 16,
            'y': 16,
            'role_name': None,
            'role_data': {}
        }
    ]
    
    db.batch_insert_agents(game_id, test_agents)
    
    # Capture initial snapshot
    print("\n6️⃣ Capturing initial snapshot...")
    snap_id_1 = sm.capture_snapshot(
        game_id=game_id,
        round_num=0,
        snapshot_type='test',
        description='Initial test state'
    )
    
    # Simulate changes
    print("\n7️⃣ Simulating game changes...")
    with db.get_cursor(dict_cursor=False) as cursor:
        # Damage a human
        cursor.execute("UPDATE agents SET health = 75 WHERE name = 'Human_1'")
        # Kill a zombie
        cursor.execute("UPDATE agents SET health = 0, is_alive = FALSE WHERE name = 'Zombie_2'")
        # Move an agent
        cursor.execute("UPDATE agents SET x = 10, y = 10 WHERE name = 'Human_2'")
    
    # Capture second snapshot
    print("\n8️⃣ Capturing second snapshot...")
    snap_id_2 = sm.capture_snapshot(
        game_id=game_id,
        round_num=5,
        snapshot_type='test',
        description='After changes'
    )
    
    # Analyze the game
    print("\n9️⃣ Analyzing game dynamics...")
    dynamics = sm.analyze_game_dynamics(game_id)
    
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    
    print(f"\n📊 Game Analysis:")
    print(f"  Game ID: {dynamics['game_id']}")
    print(f"  Total rounds: {dynamics['total_rounds']}")
    print(f"  Total snapshots: {dynamics['total_snapshots']}")
    print(f"  Human survival rate: {dynamics['human_survival_rate']:.1f}%")
    print(f"  Zombie survival rate: {dynamics['zombie_survival_rate']:.1f}%")
    print(f"  Humans killed: {dynamics['humans_killed_total']}")
    print(f"  Zombies killed: {dynamics['zombies_killed_total']}")
    
    # Compare snapshots
    print("\n🔍 Comparing snapshots...")
    comparison = sm.compare_snapshots(snap_id_1, snap_id_2)
    
    print(f"\n💀 Casualties: {comparison['casualties']['count']}")
    print(f"   Humans: {comparison['casualties']['by_type']['Human']}")
    print(f"   Zombies: {comparison['casualties']['by_type']['Zombie']}")
    
    print(f"\n🚶 Movement:")
    print(f"   Avg distance: {comparison['movements']['avg_distance']:.2f}")
    print(f"   Max distance: {comparison['movements']['max_distance']:.2f}")
    
    print(f"\n❤️ Health Changes:")
    print(f"   Avg change: {comparison['health_changes']['avg_change']:.2f}")
    print(f"   Total damage: {comparison['health_changes']['total_damage_taken']}")
    
    # Compute delta
    print("\n📈 Computing delta...")
    delta_id = sm.compute_delta(snap_id_1, snap_id_2)
    
    # Export snapshot
    print("\n💾 Exporting snapshot...")
    sm.export_snapshot_to_json(snap_id_1, 'test_snapshot.json')
    
    # Get snapshot agents as DataFrame
    print("\n📋 Getting agent data...")
    agents_df = sm.get_snapshot_agents(snap_id_1)
    print(f"\nAgent DataFrame shape: {agents_df.shape}")
    print("\nAgents:")
    print(agents_df[['name', 'agent_type', 'health', 'x', 'y', 'is_alive']])
    
    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED!")
    print("=" * 70)
    
    print("\nSnapshot system is working correctly with psycopg 3!")
    print("You can now integrate it with your zombie game.")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    
finally:
    db.close()
