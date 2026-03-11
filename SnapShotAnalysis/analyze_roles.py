"""
Simple script to analyze role performance from your games.
Run this after your game finishes to see detailed role statistics.
"""
from database_manager import DatabaseManager
from snapshot_manager3 import SnapshotManager
from role_analysis import RoleAnalyzer
import sys


def main():
    db = DatabaseManager(
        host='localhost',
        database='zombie_game',
        user='zombie_user',
        password='violet230201'
    )
    
    try:
        db.connect()
        sm = SnapshotManager(db)
        ra = RoleAnalyzer(sm)
        
        # Get game_id from command line or use most recent
        if len(sys.argv) > 1:
            game_id = int(sys.argv[1])
        else:
            # Get most recent game with snapshots
            with db.get_cursor() as cursor:
                cursor.execute("""
                    SELECT game_id 
                    FROM game_snapshots 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """)
                result = cursor.fetchone()
                if not result:
                    print("❌ No games with snapshots found!")
                    print("Run a game with snapshots first.")
                    return
                game_id = result['game_id']
        
        print(f"\n🔍 Analyzing Game {game_id}...")
        
        # Full role analysis
        ra.print_role_analysis(game_id)
        
        # Hunter-specific analysis
        print("\n" + "=" * 70)
        print("HUNTER DETAILED ANALYSIS")
        print("=" * 70)
        hunter_stats = ra.compare_hunter_vs_tank(game_id)
        h = hunter_stats['hunter_performance']
        print(f"\nHunter Performance:")
        print(f"  Total Zombie Kills: {h['total_zombie_kills']}")
        print(f"    └─ Tank Zombies: {h['tank_zombie_kills']}")
        print(f"    └─ Speed Zombies: {h['speed_zombie_kills']}")
        print(f"    └─ Standard Zombies: {h['standard_zombie_kills']}")
        print(f"  Total Damage Dealt: {h['total_damage']}")
        print(f"  Critical Hits: {h['critical_hits']}")
        
        # Doctor-specific analysis
        print("\n" + "=" * 70)
        print("DOCTOR DETAILED ANALYSIS")
        print("=" * 70)
        doctor_stats = ra.get_doctor_healing_stats(game_id)
        if 'error' not in doctor_stats:
            print(f"\nDoctor Performance:")
            print(f"  Total Doctors: {doctor_stats['total_doctors']}")
            print(f"  Total Heals: {doctor_stats['total_heals']}")
            print(f"  Total HP Restored: {doctor_stats['total_health_restored']}")
            print(f"  Avg Heals per Doctor: {doctor_stats['avg_heals_per_doctor']:.1f}")
            
            print("\n  Individual Doctors:")
            for doc in doctor_stats['doctors']:
                print(f"    {doc['name']}: {doc['heals_performed']} heals, {doc['total_health_restored']} HP restored")
        else:
            print(f"  {doctor_stats['error']}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("ROLE ANALYSIS TOOL")
    print("=" * 70)
    print("\nUsage:")
    print("  python analyze_roles.py           # Analyze most recent game")
    print("  python analyze_roles.py <game_id> # Analyze specific game")
    print()
    
    main()
