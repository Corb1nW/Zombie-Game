"""
Enhanced role analysis with better handling of actual game data.
Provides cleaner, more actionable insights.
"""
from database_manager import DatabaseManager
from snapshot_manager3 import SnapshotManager
from role_analysis import RoleAnalyzer
import sys


def print_enhanced_report(game_id: int):
    """Print enhanced role analysis report."""
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
        
        analysis = ra.analyze_role_performance(game_id)
        
        print("\n" + "=" * 80)
        print("ENHANCED ROLE PERFORMANCE REPORT")
        print("=" * 80)
        print(f"Game ID: {analysis['game_id']} | Total Rounds: {analysis['total_rounds']}")
        
        # Get game outcome
        with db.get_cursor() as cursor:
            cursor.execute("SELECT status FROM game_sessions WHERE game_id = %s", (game_id,))
            result = cursor.fetchone()
            winner = result['status'] if result else 'Unknown'
        
        print(f"Winner: {winner}")
        
        # Filter out roles with 0 population
        human_roles = {k: v for k, v in analysis['human_roles'].items() 
                      if v['total_count'] > 0}
        zombie_roles = {k: v for k, v in analysis['zombie_roles'].items() 
                       if v['total_count'] > 0}
        
        # HUMAN ROLES ANALYSIS
        print("\n" + "─" * 80)
        print("👥 HUMAN TEAM ANALYSIS")
        print("─" * 80)
        
        if human_roles:
            # Summary stats
            total_humans = sum(r['total_count'] for r in human_roles.values())
            total_survived = sum(r['survived'] for r in human_roles.values())
            total_kills = sum(r['total_kills'] for r in human_roles.values())
            total_damage = sum(r['total_damage_dealt'] for r in human_roles.values())
            
            print(f"\n📊 Overall Human Performance:")
            print(f"   Starting Population: {total_humans}")
            print(f"   Survived: {total_survived} ({total_survived/total_humans*100:.1f}%)")
            print(f"   Total Zombie Kills: {total_kills}")
            print(f"   Total Damage Dealt: {total_damage:,}")
            
            # Breakdown by role
            print(f"\n📋 By Role:")
            for role_name in sorted(human_roles.keys()):
                stats = human_roles[role_name]
                print(f"\n   🧑 {role_name}:")
                print(f"      Count: {stats['total_count']} | Survived: {stats['survived']} ({stats['survival_rate']:.1f}%)")
                print(f"      Kills: {stats['total_kills']} ({stats['avg_kills_per_agent']:.2f} per agent)")
                print(f"      Damage: {stats['total_damage_dealt']:,} total")
                
                if stats['critical_hits'] > 0:
                    crit_rate = (stats['critical_hits'] / analysis['combat_by_role'].get(f"Human_{role_name}", {}).get('total_attacks', 1)) * 100
                    print(f"      Critical Hits: {stats['critical_hits']} ({crit_rate:.1f}%)")
                
                if stats['total_healing'] > 0:
                    print(f"      💊 Healing: {stats['total_healing']} HP restored")
                
                # Show what they killed
                if stats['zombie_kills_by_type']:
                    kills_str = ", ".join([f"{ztype}: {count}" for ztype, count in stats['zombie_kills_by_type'].items()])
                    print(f"      Targets: {kills_str}")
        else:
            print("\n   ❌ No human data (all standard/no special roles)")
        
        # ZOMBIE ROLES ANALYSIS
        print("\n" + "─" * 80)
        print("🧟 ZOMBIE TEAM ANALYSIS")
        print("─" * 80)
        
        if zombie_roles:
            # Summary stats
            total_zombies = sum(r['total_count'] for r in zombie_roles.values())
            total_survived = sum(r['survived'] for r in zombie_roles.values())
            total_kills = sum(r['total_kills'] for r in zombie_roles.values())
            total_damage = sum(r['total_damage_dealt'] for r in zombie_roles.values())
            
            print(f"\n📊 Overall Zombie Performance:")
            print(f"   Starting Population: {total_zombies}")
            print(f"   Survived: {total_survived} ({total_survived/total_zombies*100:.1f}%)")
            print(f"   Total Human Kills: {total_kills}")
            print(f"   Total Damage Dealt: {total_damage:,}")
            
            # Breakdown by role
            print(f"\n📋 By Role:")
            for role_name in sorted(zombie_roles.keys()):
                stats = zombie_roles[role_name]
                print(f"\n   🧟 {role_name}:")
                print(f"      Count: {stats['total_count']} | Survived: {stats['survived']} ({stats['survival_rate']:.1f}%)")
                print(f"      Human Kills: {stats['human_kills']} ({stats['avg_kills_per_agent']:.2f} per agent)")
                print(f"      Damage: {stats['total_damage_dealt']:,} total")
                
                if stats['critical_hits'] > 0:
                    crit_rate = (stats['critical_hits'] / analysis['combat_by_role'].get(f"Zombie_{role_name}", {}).get('total_attacks', 1)) * 100
                    print(f"      Critical Hits: {stats['critical_hits']} ({crit_rate:.1f}%)")
        else:
            print("\n   ❌ No zombie role data")
        
        # COMBAT EFFECTIVENESS COMPARISON
        print("\n" + "─" * 80)
        print("⚔️  COMBAT EFFECTIVENESS RANKINGS")
        print("─" * 80)
        
        combat_stats = analysis['combat_by_role']
        
        # Rank by damage
        print("\n🎯 Most Damaging Roles:")
        ranked = sorted(combat_stats.items(), key=lambda x: x[1]['total_damage'], reverse=True)[:5]
        for i, (role, stats) in enumerate(ranked, 1):
            if stats['total_damage'] > 0:
                print(f"   {i}. {stats['agent_type']} - {stats['role_name']}: "
                      f"{stats['total_damage']:,} damage in {stats['total_attacks']} attacks "
                      f"(avg: {stats['avg_damage_per_attack']:.1f})")
        
        # Rank by efficiency (damage per attack)
        print("\n💥 Most Efficient Attackers (damage per attack):")
        ranked = sorted(combat_stats.items(), key=lambda x: x[1]['avg_damage_per_attack'], reverse=True)[:5]
        for i, (role, stats) in enumerate(ranked, 1):
            if stats['total_attacks'] > 0:
                print(f"   {i}. {stats['agent_type']} - {stats['role_name']}: "
                      f"{stats['avg_damage_per_attack']:.1f} avg damage "
                      f"({stats['critical_hit_rate']:.1f}% crit rate)")
        
        # Rank by kills
        print("\n💀 Most Lethal Roles:")
        role_kills = []
        for role_name, stats in {**human_roles, **zombie_roles}.items():
            role_kills.append((
                stats.get('agent_type', 'Unknown'),
                role_name,
                stats['total_kills'],
                stats['total_count']
            ))
        
        ranked_kills = sorted(role_kills, key=lambda x: x[2], reverse=True)[:5]
        for i, (agent_type, role_name, kills, count) in enumerate(ranked_kills, 1):
            if kills > 0:
                print(f"   {i}. {agent_type} - {role_name}: "
                      f"{kills} kills ({kills/count:.2f} per agent)")
        
        # KEY INSIGHTS
        print("\n" + "─" * 80)
        print("🔍 KEY INSIGHTS")
        print("─" * 80)
        
        insights = []
        
        # Speed vs Tank comparison
        if 'Speed Zombie' in zombie_roles and 'Tank Zombie' in zombie_roles:
            speed = zombie_roles['Speed Zombie']
            tank = zombie_roles['Tank Zombie']
            
            if speed['avg_kills_per_agent'] > tank['avg_kills_per_agent']:
                insights.append(f"• Speed Zombies were more effective: {speed['avg_kills_per_agent']:.2f} vs "
                              f"{tank['avg_kills_per_agent']:.2f} kills per agent")
            else:
                insights.append(f"• Tank Zombies were more effective: {tank['avg_kills_per_agent']:.2f} vs "
                              f"{speed['avg_kills_per_agent']:.2f} kills per agent")
            
            if speed['survival_rate'] > tank['survival_rate']:
                insights.append(f"• Speed Zombies survived better: {speed['survival_rate']:.1f}% vs "
                              f"{tank['survival_rate']:.1f}%")
            elif tank['survival_rate'] > speed['survival_rate']:
                insights.append(f"• Tank Zombies survived better: {tank['survival_rate']:.1f}% vs "
                              f"{speed['survival_rate']:.1f}%")
        
        # Hunter effectiveness
        if 'Hunter' in human_roles:
            hunter = human_roles['Hunter']
            if hunter['total_kills'] > 0:
                insights.append(f"• Hunters eliminated {hunter['total_kills']} zombies "
                              f"({hunter['avg_kills_per_agent']:.2f} per hunter)")
            
            hunter_combat = combat_stats.get('Human_Hunter', {})
            if hunter_combat.get('critical_hit_rate', 0) > 15:
                insights.append(f"• Hunters had exceptional accuracy: {hunter_combat['critical_hit_rate']:.1f}% crit rate")
        
        # Doctor value
        if 'Doctor' in human_roles:
            doctor = human_roles['Doctor']
            if doctor['total_healing'] > 0:
                insights.append(f"• Doctors restored {doctor['total_healing']} HP across the game")
                if doctor['survival_rate'] > 50:
                    insights.append(f"• Doctors had high survival: {doctor['survival_rate']:.1f}% (support role protected)")
        
        # Combat intensity
        total_combat_events = analysis.get('total_combat_events', 0)
        if total_combat_events > 0:
            combat_per_round = total_combat_events / analysis['total_rounds']
            if combat_per_round > 50:
                insights.append(f"• Very intense combat: {combat_per_round:.1f} attacks per round")
            elif combat_per_round < 10:
                insights.append(f"• Low combat intensity: {combat_per_round:.1f} attacks per round")
        
        if insights:
            for insight in insights:
                print(insight)
        else:
            print("• Standard game with no notable patterns")
        
        print("\n" + "=" * 80)
        
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        game_id = int(sys.argv[1])
    else:
        # Get most recent game
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
                    SELECT game_id 
                    FROM game_snapshots 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """)
                result = cursor.fetchone()
                if not result:
                    print("❌ No games with snapshots found!")
                    sys.exit(1)
                game_id = result['game_id']
        finally:
            db.close()
    
    print_enhanced_report(game_id)
