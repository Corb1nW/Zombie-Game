"""
Role-Based Analysis Module for Zombie Game Snapshots
Provides detailed analysis of different human and zombie roles.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from snapshot_manager3 import SnapshotManager


class RoleAnalyzer:
    """Analyzes role-specific performance and comparisons."""
    
    def __init__(self, snapshot_manager: SnapshotManager):
        """
        Initialize role analyzer.
        
        Args:
            snapshot_manager: SnapshotManager instance
        """
        self.sm = snapshot_manager
        self.db = snapshot_manager.db
    
    def analyze_role_performance(self, game_id: int) -> Dict:
        """
        Comprehensive role-based analysis across entire game.
        
        Args:
            game_id: Game session ID
            
        Returns:
            Dictionary with role performance metrics
        """
        snapshots = self.sm.get_game_snapshots(game_id)
        
        if not snapshots:
            return {"error": "No snapshots found"}
        
        # Get initial and final snapshots
        initial_snap = snapshots[0]['snapshot_id']
        final_snap = snapshots[-1]['snapshot_id']
        
        # Get agent data from snapshots
        initial_agents = self.sm.get_snapshot_agents(initial_snap)
        final_agents = self.sm.get_snapshot_agents(final_snap)
        
        analysis = {
            'game_id': game_id,
            'total_rounds': snapshots[-1]['round_num'],
            'human_roles': self._analyze_human_roles(game_id, initial_agents, final_agents),
            'zombie_roles': self._analyze_zombie_roles(game_id, initial_agents, final_agents),
            'role_comparisons': self._compare_roles(game_id, snapshots),
            'combat_by_role': self._analyze_combat_by_role(game_id),
            'survival_by_role': self._analyze_survival_by_role(initial_agents, final_agents)
        }
        
        return analysis
    
    def _analyze_human_roles(self, game_id: int, initial_df: pd.DataFrame, 
                            final_df: pd.DataFrame) -> Dict:
        """Analyze human role performance."""
        human_initial = initial_df[initial_df['agent_type'] == 'Human'].copy()
        human_final = final_df[final_df['agent_type'] == 'Human'].copy()
        
        # Group by role
        roles = {}
        for role_name in human_initial['role_name'].unique():
            if pd.isna(role_name):
                role_name = 'Standard'
            
            role_initial = human_initial[human_initial['role_name'] == role_name]
            role_final = human_final[human_final['role_name'] == role_name]
            
            # Get kills for this role (from combat log)
            kills = self._get_role_kills(game_id, role_initial['agent_id'].tolist())
            
            # Get healing done (for Doctor role)
            healing = self._get_role_healing(game_id, role_initial['agent_id'].tolist())
            
            roles[role_name] = {
                'total_count': len(role_initial),
                'survived': len(role_final[role_final['is_alive']]),
                'survival_rate': (len(role_final[role_final['is_alive']]) / len(role_initial) * 100) if len(role_initial) > 0 else 0,
                'avg_health_start': float(role_initial['health'].mean()),
                'avg_health_end': float(role_final['health'].mean()) if len(role_final) > 0 else 0,
                'total_kills': kills['total'],
                'zombie_kills_by_type': kills['by_type'],
                'total_damage_dealt': kills['total_damage'],
                'critical_hits': kills['critical_hits'],
                'total_healing': healing,
                'avg_kills_per_agent': kills['total'] / len(role_initial) if len(role_initial) > 0 else 0
            }
        
        return roles
    
    def _analyze_zombie_roles(self, game_id: int, initial_df: pd.DataFrame, 
                             final_df: pd.DataFrame) -> Dict:
        """Analyze zombie role performance."""
        zombie_initial = initial_df[initial_df['agent_type'] == 'Zombie'].copy()
        zombie_final = final_df[final_df['agent_type'] == 'Zombie'].copy()
        
        # Group by role
        roles = {}
        for role_name in zombie_initial['role_name'].unique():
            if pd.isna(role_name):
                role_name = 'Standard'
            
            role_initial = zombie_initial[zombie_initial['role_name'] == role_name]
            role_final = zombie_final[zombie_final['role_name'] == role_name]
            
            # Get kills for this role
            kills = self._get_role_kills(game_id, role_initial['agent_id'].tolist())
            
            # Get infection count (humans converted)
            infections = self._get_role_infections(game_id, role_initial['agent_id'].tolist())
            
            roles[role_name] = {
                'total_count': len(role_initial),
                'survived': len(role_final[role_final['is_alive']]),
                'survival_rate': (len(role_final[role_final['is_alive']]) / len(role_initial) * 100) if len(role_initial) > 0 else 0,
                'avg_health_start': float(role_initial['health'].mean()),
                'avg_health_end': float(role_final['health'].mean()) if len(role_final) > 0 else 0,
                'total_kills': kills['total'],
                'human_kills': kills['by_type'].get('Human', 0),
                'total_damage_dealt': kills['total_damage'],
                'critical_hits': kills['critical_hits'],
                'infections': infections,
                'avg_kills_per_agent': kills['total'] / len(role_initial) if len(role_initial) > 0 else 0
            }
        
        return roles
    
    def _get_role_kills(self, game_id: int, agent_ids: List[int]) -> Dict:
        """Get kill statistics for specific agents."""
        if not agent_ids:
            return {'total': 0, 'by_type': {}, 'total_damage': 0, 'critical_hits': 0}
        
        with self.db.get_cursor() as cursor:
            # Get all attacks by these agents that resulted in kills
            cursor.execute("""
                SELECT 
                    t.agent_type as target_type,
                    COUNT(*) as kills,
                    SUM(cl.damage) as total_damage,
                    SUM(CASE WHEN cl.was_critical THEN 1 ELSE 0 END) as critical_hits
                FROM combat_log cl
                JOIN agents t ON cl.target_id = t.agent_id
                WHERE cl.game_id = %s 
                  AND cl.attacker_id = ANY(%s)
                  AND t.is_alive = FALSE
                GROUP BY t.agent_type
            """, (game_id, agent_ids))
            
            results = cursor.fetchall()
            
            by_type = {}
            total = 0
            total_damage = 0
            critical_hits = 0
            
            for row in results:
                by_type[row['target_type']] = row['kills']
                total += row['kills']
                total_damage += row['total_damage'] or 0
                critical_hits += row['critical_hits'] or 0
            
            return {
                'total': total,
                'by_type': by_type,
                'total_damage': total_damage,
                'critical_hits': critical_hits
            }
    
    def _get_role_healing(self, game_id: int, agent_ids: List[int]) -> int:
        """Get total healing done by specific agents (for Doctor role)."""
        if not agent_ids:
            return 0
        
        # Note: You'd need to track healing in combat_log or a separate table
        # For now, we'll estimate from role_data if Doctor role exists
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COALESCE(SUM((role_data->>'heals_performed')::int), 0) as total_healing
                FROM agents
                WHERE game_id = %s 
                  AND agent_id = ANY(%s)
                  AND role_data ? 'heals_performed'
            """, (game_id, agent_ids))
            
            result = cursor.fetchone()
            return result['total_healing'] if result else 0
    
    def _get_role_infections(self, game_id: int, agent_ids: List[int]) -> int:
        """Get infection count for zombie agents."""
        if not agent_ids:
            return 0
        
        # Track conversions in role_data if available
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COALESCE(SUM((role_data->>'infections')::int), 0) as total_infections
                FROM agents
                WHERE game_id = %s 
                  AND agent_id = ANY(%s)
                  AND role_data ? 'infections'
            """, (game_id, agent_ids))
            
            result = cursor.fetchone()
            return result['total_infections'] if result else 0
    
    def _compare_roles(self, game_id: int, snapshots: List[Dict]) -> Dict:
        """Compare role performance over time."""
        comparisons = {}
        
        # Track role populations over time
        for snapshot in snapshots:
            snap_id = snapshot['snapshot_id']
            agents_df = self.sm.get_snapshot_agents(snap_id)
            
            for agent_type in ['Human', 'Zombie']:
                type_agents = agents_df[agents_df['agent_type'] == agent_type]
                
                for role_name in type_agents['role_name'].unique():
                    if pd.isna(role_name):
                        role_name = 'Standard'
                    
                    key = f"{agent_type}_{role_name}"
                    
                    if key not in comparisons:
                        comparisons[key] = {
                            'agent_type': agent_type,
                            'role_name': role_name,
                            'population_over_time': [],
                            'avg_health_over_time': [],
                            'rounds': []
                        }
                    
                    role_agents = type_agents[type_agents['role_name'] == role_name]
                    alive_count = len(role_agents[role_agents['is_alive']])
                    avg_health = role_agents[role_agents['is_alive']]['health'].mean()
                    
                    comparisons[key]['population_over_time'].append(alive_count)
                    comparisons[key]['avg_health_over_time'].append(float(avg_health) if not pd.isna(avg_health) else 0)
                    comparisons[key]['rounds'].append(snapshot['round_num'])
        
        return comparisons
    
    def _analyze_combat_by_role(self, game_id: int) -> Dict:
        """Analyze combat effectiveness by role."""
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    a.agent_type,
                    a.role_name,
                    COUNT(*) as attacks,
                    AVG(cl.damage) as avg_damage,
                    SUM(cl.damage) as total_damage,
                    SUM(CASE WHEN cl.was_critical THEN 1 ELSE 0 END) as critical_hits,
                    COUNT(DISTINCT cl.target_id) as unique_targets
                FROM combat_log cl
                JOIN agents a ON cl.attacker_id = a.agent_id
                WHERE cl.game_id = %s
                GROUP BY a.agent_type, a.role_name
                ORDER BY total_damage DESC
            """, (game_id,))
            
            results = cursor.fetchall()
            
            combat_stats = {}
            for row in results:
                role_name = row['role_name'] if row['role_name'] else 'Standard'
                key = f"{row['agent_type']}_{role_name}"
                
                combat_stats[key] = {
                    'agent_type': row['agent_type'],
                    'role_name': role_name,
                    'total_attacks': row['attacks'],
                    'avg_damage_per_attack': float(row['avg_damage']),
                    'total_damage': row['total_damage'],
                    'critical_hits': row['critical_hits'],
                    'critical_hit_rate': (row['critical_hits'] / row['attacks'] * 100) if row['attacks'] > 0 else 0,
                    'unique_targets': row['unique_targets']
                }
            
            return combat_stats
    
    def _analyze_survival_by_role(self, initial_df: pd.DataFrame, 
                                  final_df: pd.DataFrame) -> Dict:
        """Analyze survival rates by role."""
        survival = {}
        
        for agent_type in ['Human', 'Zombie']:
            type_initial = initial_df[initial_df['agent_type'] == agent_type]
            type_final = final_df[final_df['agent_type'] == agent_type]
            
            for role_name in type_initial['role_name'].unique():
                if pd.isna(role_name):
                    role_name = 'Standard'
                
                role_initial = type_initial[type_initial['role_name'] == role_name]
                role_final = type_final[type_final['role_name'] == role_name]
                
                initial_count = len(role_initial)
                survived_count = len(role_final[role_final['is_alive']])
                
                key = f"{agent_type}_{role_name}"
                survival[key] = {
                    'agent_type': agent_type,
                    'role_name': role_name,
                    'initial_count': initial_count,
                    'survived_count': survived_count,
                    'killed_count': initial_count - survived_count,
                    'survival_rate': (survived_count / initial_count * 100) if initial_count > 0 else 0
                }
        
        return survival
    
    def compare_hunter_vs_tank(self, game_id: int) -> Dict:
        """Specific comparison: Hunter vs Tank zombie kills."""
        snapshots = self.sm.get_game_snapshots(game_id)
        initial_snap = snapshots[0]['snapshot_id']
        
        initial_agents = self.sm.get_snapshot_agents(initial_snap)
        hunters = initial_agents[initial_agents['role_name'] == 'Hunter']['agent_id'].tolist()
        
        hunter_kills = self._get_role_kills(game_id, hunters)
        
        comparison = {
            'hunter_performance': {
                'total_zombie_kills': hunter_kills['by_type'].get('Zombie', 0),
                'tank_zombie_kills': self._count_specific_zombie_kills(game_id, hunters, 'Tank Zombie'),
                'speed_zombie_kills': self._count_specific_zombie_kills(game_id, hunters, 'Speed Zombie'),
                'standard_zombie_kills': hunter_kills['by_type'].get('Zombie', 0) - 
                    self._count_specific_zombie_kills(game_id, hunters, 'Tank Zombie') -
                    self._count_specific_zombie_kills(game_id, hunters, 'Speed Zombie'),
                'total_damage': hunter_kills['total_damage'],
                'critical_hits': hunter_kills['critical_hits']
            }
        }
        
        return comparison
    
    def _count_specific_zombie_kills(self, game_id: int, hunter_ids: List[int], 
                                     zombie_role: str) -> int:
        """Count kills of specific zombie type."""
        if not hunter_ids:
            return 0
        
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) as kills
                FROM combat_log cl
                JOIN agents t ON cl.target_id = t.agent_id
                WHERE cl.game_id = %s
                  AND cl.attacker_id = ANY(%s)
                  AND t.agent_type = 'Zombie'
                  AND t.role_name = %s
                  AND t.is_alive = FALSE
            """, (game_id, hunter_ids, zombie_role))
            
            result = cursor.fetchone()
            return result['kills'] if result else 0
    
    def get_doctor_healing_stats(self, game_id: int) -> Dict:
        """Detailed analysis of Doctor role healing."""
        snapshots = self.sm.get_game_snapshots(game_id)
        initial_snap = snapshots[0]['snapshot_id']
        
        initial_agents = self.sm.get_snapshot_agents(initial_snap)
        doctors = initial_agents[initial_agents['role_name'] == 'Doctor']['agent_id'].tolist()
        
        if not doctors:
            return {'error': 'No doctors found in game'}
        
        with self.db.get_cursor() as cursor:
            # Get healing statistics
            cursor.execute("""
                SELECT 
                    agent_id,
                    name,
                    role_data
                FROM agents
                WHERE game_id = %s
                  AND agent_id = ANY(%s)
            """, (game_id, doctors))
            
            doctor_data = cursor.fetchall()
            
            healing_stats = {
                'total_doctors': len(doctors),
                'doctors': []
            }
            
            for doc in doctor_data:
                role_data = doc['role_data'] or {}
                healing_stats['doctors'].append({
                    'agent_id': doc['agent_id'],
                    'name': doc['name'],
                    'heals_performed': role_data.get('heals_performed', 0),
                    'total_health_restored': role_data.get('total_health_restored', 0)
                })
            
            healing_stats['total_heals'] = sum(d['heals_performed'] for d in healing_stats['doctors'])
            healing_stats['total_health_restored'] = sum(d['total_health_restored'] for d in healing_stats['doctors'])
            healing_stats['avg_heals_per_doctor'] = healing_stats['total_heals'] / len(doctors) if doctors else 0
            
            return healing_stats
    
    def print_role_analysis(self, game_id: int):
        """Print formatted role analysis report."""
        analysis = self.analyze_role_performance(game_id)
        
        print("\n" + "=" * 70)
        print("ROLE-BASED PERFORMANCE ANALYSIS")
        print("=" * 70)
        print(f"Game ID: {analysis['game_id']}")
        print(f"Total Rounds: {analysis['total_rounds']}")
        
        # Human roles
        print("\n" + "-" * 70)
        print("HUMAN ROLES")
        print("-" * 70)
        for role_name, stats in analysis['human_roles'].items():
            print(f"\n🧑 {role_name}:")
            print(f"  Population: {stats['total_count']} → {stats['survived']} survived ({stats['survival_rate']:.1f}%)")
            print(f"  Health: {stats['avg_health_start']:.1f} → {stats['avg_health_end']:.1f}")
            print(f"  Combat: {stats['total_kills']} kills ({stats['avg_kills_per_agent']:.2f} per agent)")
            print(f"  Damage: {stats['total_damage_dealt']} total ({stats['critical_hits']} critical hits)")
            if stats['total_healing'] > 0:
                print(f"  Healing: {stats['total_healing']} HP restored")
            if stats['zombie_kills_by_type']:
                print(f"  Zombie Kills by Type: {stats['zombie_kills_by_type']}")
        
        # Zombie roles
        print("\n" + "-" * 70)
        print("ZOMBIE ROLES")
        print("-" * 70)
        for role_name, stats in analysis['zombie_roles'].items():
            print(f"\n🧟 {role_name}:")
            print(f"  Population: {stats['total_count']} → {stats['survived']} survived ({stats['survival_rate']:.1f}%)")
            print(f"  Health: {stats['avg_health_start']:.1f} → {stats['avg_health_end']:.1f}")
            print(f"  Combat: {stats['total_kills']} kills ({stats['avg_kills_per_agent']:.2f} per agent)")
            print(f"  Damage: {stats['total_damage_dealt']} total ({stats['critical_hits']} critical hits)")
            print(f"  Human Kills: {stats['human_kills']}")
            if stats['infections'] > 0:
                print(f"  Infections: {stats['infections']}")
        
        # Combat comparison
        print("\n" + "-" * 70)
        print("COMBAT EFFECTIVENESS BY ROLE")
        print("-" * 70)
        for key, stats in sorted(analysis['combat_by_role'].items(), 
                                key=lambda x: x[1]['total_damage'], reverse=True):
            print(f"\n{stats['agent_type']} - {stats['role_name']}:")
            print(f"  Attacks: {stats['total_attacks']}")
            print(f"  Avg Damage: {stats['avg_damage_per_attack']:.1f}")
            print(f"  Total Damage: {stats['total_damage']}")
            print(f"  Critical Hit Rate: {stats['critical_hit_rate']:.1f}%")
            print(f"  Unique Targets: {stats['unique_targets']}")
        
        print("\n" + "=" * 70)


# Example usage
if __name__ == "__main__":
    from database_manager import DatabaseManager
    from snapshot_manager import SnapshotManager
    
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
        
        # Analyze most recent game
        game_id = 1  # Replace with your game_id
        
        ra.print_role_analysis(game_id)
        
        # Specific comparisons
        print("\n\n📊 Hunter vs Zombie Types:")
        hunter_stats = ra.compare_hunter_vs_tank(game_id)
        print(hunter_stats)
        
        print("\n\n💊 Doctor Healing Stats:")
        doctor_stats = ra.get_doctor_healing_stats(game_id)
        print(doctor_stats)
        
    finally:
        db.close()
