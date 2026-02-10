"""
Compare role performance across multiple games.
Useful for testing different configurations.
"""
from database_manager import DatabaseManager
from snapshot_manager3 import SnapshotManager
from role_analysis import RoleAnalyzer
import sys


def compare_multiple_games(game_ids: list):
    """Compare role performance across multiple games."""
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
        
        print("\n" + "=" * 80)
        print("MULTI-GAME ROLE COMPARISON")
        print("=" * 80)
        
        all_results = []
        
        for game_id in game_ids:
            print(f"\n🎮 Analyzing Game {game_id}...")
            
            analysis = ra.analyze_role_performance(game_id)
            
            # Get winner
            with db.get_cursor() as cursor:
                cursor.execute("SELECT status FROM game_sessions WHERE game_id = %s", (game_id,))
                result = cursor.fetchone()
                winner = result['status'] if result else 'Unknown'
            
            # Extract key metrics
            human_roles = {k: v for k, v in analysis['human_roles'].items() if v['total_count'] > 0}
            zombie_roles = {k: v for k, v in analysis['zombie_roles'].items() if v['total_count'] > 0}
            
            game_summary = {
                'game_id': game_id,
                'rounds': analysis['total_rounds'],
                'winner': winner,
                'total_humans': sum(r['total_count'] for r in human_roles.values()),
                'human_survivors': sum(r['survived'] for r in human_roles.values()),
                'total_zombies': sum(r['total_count'] for r in zombie_roles.values()),
                'zombie_survivors': sum(r['survived'] for r in zombie_roles.values()),
                'human_kills': sum(r['total_kills'] for r in human_roles.values()),
                'zombie_kills': sum(r['total_kills'] for r in zombie_roles.values()),
                'roles': {}
            }
            
            # Collect role-specific data
            for role_name, stats in {**human_roles, **zombie_roles}.items():
                game_summary['roles'][role_name] = {
                    'count': stats['total_count'],
                    'survived': stats['survived'],
                    'survival_rate': stats['survival_rate'],
                    'kills': stats['total_kills'],
                    'avg_kills': stats['avg_kills_per_agent']
                }
            
            all_results.append(game_summary)
        
        # Print comparison
        print("\n" + "=" * 80)
        print("COMPARISON SUMMARY")
        print("=" * 80)
        
        # Game outcomes
        print("\n📊 Game Outcomes:")
        print(f"{'Game ID':<10} {'Rounds':<8} {'Winner':<15} {'Humans':<12} {'Zombies':<12}")
        print("-" * 80)
        for result in all_results:
            humans_str = f"{result['human_survivors']}/{result['total_humans']}"
            zombies_str = f"{result['zombie_survivors']}/{result['total_zombies']}"
            print(f"{result['game_id']:<10} {result['rounds']:<8} {result['winner']:<15} "
                  f"{humans_str:<12} {zombies_str:<12}")
        
        # Role performance comparison
        all_roles = set()
        for result in all_results:
            all_roles.update(result['roles'].keys())
        
        if all_roles:
            print("\n📋 Role Performance Across Games:")
            for role_name in sorted(all_roles):
                print(f"\n   {role_name}:")
                print(f"   {'Game':<8} {'Count':<8} {'Survived':<12} {'Survival %':<12} {'Kills':<8} {'Avg/Agent':<10}")
                print("   " + "-" * 70)
                
                for result in all_results:
                    if role_name in result['roles']:
                        r = result['roles'][role_name]
                        surv_str = f"{r['survived']}/{r['count']}"
                        print(f"   {result['game_id']:<8} {r['count']:<8} {surv_str:<12} "
                              f"{r['survival_rate']:>10.1f}% {r['kills']:<8} {r['avg_kills']:>9.2f}")
        
        # Statistical summary
        print("\n📈 Statistics:")
        
        # Average game length
        avg_rounds = sum(r['rounds'] for r in all_results) / len(all_results)
        print(f"   Average game length: {avg_rounds:.1f} rounds")
        
        # Win rates
        human_wins = sum(1 for r in all_results if 'HUMAN' in r['winner'].upper())
        zombie_wins = sum(1 for r in all_results if 'ZOMBIE' in r['winner'].upper())
        draws = sum(1 for r in all_results if 'DRAW' in r['winner'].upper())
        
        print(f"   Human wins: {human_wins}/{len(all_results)} ({human_wins/len(all_results)*100:.1f}%)")
        print(f"   Zombie wins: {zombie_wins}/{len(all_results)} ({zombie_wins/len(all_results)*100:.1f}%)")
        if draws > 0:
            print(f"   Draws: {draws}/{len(all_results)}")
        
        # Average survival rates
        avg_human_survival = sum(r['human_survivors']/r['total_humans'] if r['total_humans'] > 0 else 0 
                                for r in all_results) / len(all_results) * 100
        avg_zombie_survival = sum(r['zombie_survivors']/r['total_zombies'] if r['total_zombies'] > 0 else 0 
                                 for r in all_results) / len(all_results) * 100
        
        print(f"   Average human survival: {avg_human_survival:.1f}%")
        print(f"   Average zombie survival: {avg_zombie_survival:.1f}%")
        
        print("\n" + "=" * 80)
        
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python compare_games.py <game_id1> <game_id2> [game_id3] ...")
        print("\nExample:")
        print("  python compare_games.py 1 2 3 4 5")
        print("\nOr get last N games:")
        print("  python compare_games.py last 5")
        sys.exit(1)
    
    if sys.argv[1] == 'last' and len(sys.argv) == 3:
        # Get last N games
        n = int(sys.argv[2])
        
        db = DatabaseManager(
            host='localhost',
            database='zombie_game',
            user='zombie_user',
            password='violet230201'
        )
        try:
            db.connect()
            with db.get_cursor() as cursor:
                cursor.execute("""
                    SELECT DISTINCT game_id 
                    FROM game_snapshots 
                    ORDER BY game_id DESC 
                    LIMIT %s
                """, (n,))
                results = cursor.fetchall()
                game_ids = [r['game_id'] for r in results]
        finally:
            db.close()
        
        if not game_ids:
            print("❌ No games found!")
            sys.exit(1)
        
        print(f"\nComparing last {n} games: {game_ids}")
    else:
        # Use specified game IDs
        game_ids = [int(gid) for gid in sys.argv[1:]]
    
    compare_multiple_games(game_ids)
