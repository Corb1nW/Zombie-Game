import psycopg
from psycopg.rows import dict_row
from datetime import datetime
import json
from typing import List, Dict, Optional
import pandas as pd
import numpy as np


class SnapshotManager:
    """Manages game state snapshots for analysis and testing."""
    
    def __init__(self, db_manager):
        """
        Initialize snapshot manager.
        
        Args:
            db_manager: DatabaseManager instance with active connection
        """
        self.db = db_manager
        self._initialize_snapshot_schema()
    
    def _initialize_snapshot_schema(self):
        """Create snapshot-related tables."""
        schema_sql = """
        -- Snapshots table to track snapshot metadata
        CREATE TABLE IF NOT EXISTS game_snapshots (
            snapshot_id SERIAL PRIMARY KEY,
            game_id INTEGER REFERENCES game_sessions(game_id) ON DELETE CASCADE,
            round_num INTEGER NOT NULL,
            snapshot_type VARCHAR(50) DEFAULT 'manual',
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- Aggregated metrics for quick access
            total_humans INTEGER,
            alive_humans INTEGER,
            total_zombies INTEGER,
            alive_zombies INTEGER,
            total_items INTEGER,
            available_items INTEGER,
            
            -- Game dynamics metrics
            avg_human_health FLOAT,
            avg_zombie_health FLOAT,
            human_zombie_distance_avg FLOAT,
            combat_events_this_round INTEGER
        );
        
        -- Snapshot agent data
        CREATE TABLE IF NOT EXISTS snapshot_agents (
            snapshot_agent_id SERIAL PRIMARY KEY,
            snapshot_id INTEGER REFERENCES game_snapshots(snapshot_id) ON DELETE CASCADE,
            agent_id INTEGER,
            name VARCHAR(50),
            agent_type VARCHAR(20),
            health INTEGER,
            max_health INTEGER,
            attack_power INTEGER,
            base_attack_power INTEGER,
            is_alive BOOLEAN,
            x INTEGER,
            y INTEGER,
            role_name VARCHAR(50),
            role_data JSONB
        );
        
        -- Snapshot items data
        CREATE TABLE IF NOT EXISTS snapshot_items (
            snapshot_item_id SERIAL PRIMARY KEY,
            snapshot_id INTEGER REFERENCES game_snapshots(snapshot_id) ON DELETE CASCADE,
            item_id INTEGER,
            item_type VARCHAR(50),
            x INTEGER,
            y INTEGER,
            picked_up BOOLEAN,
            picked_by_agent_id INTEGER
        );
        
        -- Comparative metrics between snapshots
        CREATE TABLE IF NOT EXISTS snapshot_deltas (
            delta_id SERIAL PRIMARY KEY,
            game_id INTEGER REFERENCES game_sessions(game_id) ON DELETE CASCADE,
            from_snapshot_id INTEGER REFERENCES game_snapshots(snapshot_id),
            to_snapshot_id INTEGER REFERENCES game_snapshots(snapshot_id),
            
            -- Population changes
            humans_killed INTEGER,
            zombies_killed INTEGER,
            
            -- Health dynamics
            avg_human_health_change FLOAT,
            avg_zombie_health_change FLOAT,
            
            -- Spatial dynamics
            avg_movement_distance FLOAT,
            human_zombie_distance_change FLOAT,
            
            -- Combat metrics
            total_damage_dealt INTEGER,
            combat_events INTEGER,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Create indexes for performance
        CREATE INDEX IF NOT EXISTS idx_snapshots_game ON game_snapshots(game_id, round_num);
        CREATE INDEX IF NOT EXISTS idx_snapshot_agents ON snapshot_agents(snapshot_id, agent_type);
        CREATE INDEX IF NOT EXISTS idx_snapshot_items ON snapshot_items(snapshot_id);
        CREATE INDEX IF NOT EXISTS idx_deltas_game ON snapshot_deltas(game_id);
        """
        
        with self.db.get_cursor(dict_cursor=False) as cursor:
            cursor.execute(schema_sql)
        print("✅ Snapshot schema initialized")
    
    def capture_snapshot(self, game_id: int, round_num: int, 
                        snapshot_type: str = 'manual',
                        description: str = None) -> int:
        """
        Capture a complete snapshot of the current game state.
        
        Args:
            game_id: Game session ID
            round_num: Current round number
            snapshot_type: Type of snapshot ('manual', 'periodic', 'event')
            description: Optional description
            
        Returns:
            snapshot_id: ID of the created snapshot
        """
        with self.db.get_cursor() as cursor:
            # Get current agent data
            cursor.execute("SELECT * FROM agents WHERE game_id = %s", (game_id,))
            agents = cursor.fetchall()
            
            # Get current item data
            cursor.execute("SELECT * FROM items WHERE game_id = %s", (game_id,))
            items = cursor.fetchall()
            
            # Calculate metrics
            humans = [a for a in agents if a['agent_type'] == 'Human']
            zombies = [a for a in agents if a['agent_type'] == 'Zombie']
            
            alive_humans = [h for h in humans if h['is_alive']]
            alive_zombies = [z for z in zombies if z['is_alive']]
            
            avg_human_health = np.mean([h['health'] for h in alive_humans]) if alive_humans else 0
            avg_zombie_health = np.mean([z['health'] for z in alive_zombies]) if alive_zombies else 0
            
            # Calculate average distance between humans and zombies
            avg_distance = self._calculate_avg_hz_distance(alive_humans, alive_zombies)
            
            # Get combat events for this round
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM combat_log
                WHERE game_id = %s AND round_num = %s
            """, (game_id, round_num))
            combat_result = cursor.fetchone()
            combat_count = combat_result['count'] if combat_result else 0
            
            # Insert snapshot metadata
            cursor.execute("""
                INSERT INTO game_snapshots 
                (game_id, round_num, snapshot_type, description, 
                 total_humans, alive_humans, total_zombies, alive_zombies,
                 total_items, available_items, avg_human_health, avg_zombie_health,
                 human_zombie_distance_avg, combat_events_this_round)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING snapshot_id
            """, (
                game_id, round_num, snapshot_type, description,
                len(humans), len(alive_humans), len(zombies), len(alive_zombies),
                len(items), len([i for i in items if not i['picked_up']]),
                float(avg_human_health), float(avg_zombie_health),
                float(avg_distance), combat_count
            ))
            
            snapshot_id = cursor.fetchone()['snapshot_id']
            
            # Insert agent snapshot data (using executemany for psycopg 3)
            if agents:
                agent_values = [
                    (snapshot_id, a['agent_id'], a['name'], a['agent_type'],
                     a['health'], a['max_health'], a['attack_power'], a['base_attack_power'],
                     a['is_alive'], a['x'], a['y'], a['role_name'], 
                     json.dumps(a['role_data']) if a['role_data'] else '{}')
                    for a in agents
                ]
                cursor.executemany("""
                    INSERT INTO snapshot_agents 
                    (snapshot_id, agent_id, name, agent_type, health, max_health,
                     attack_power, base_attack_power, is_alive, x, y, role_name, role_data)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, agent_values)
            
            # Insert item snapshot data (using executemany for psycopg 3)
            if items:
                item_values = [
                    (snapshot_id, i['item_id'], i['item_type'], i['x'], i['y'],
                     i['picked_up'], i['picked_by_agent_id'])
                    for i in items
                ]
                cursor.executemany("""
                    INSERT INTO snapshot_items 
                    (snapshot_id, item_id, item_type, x, y, picked_up, picked_by_agent_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, item_values)
        
        print(f"📸 Captured snapshot {snapshot_id} for game {game_id} at round {round_num}")
        return snapshot_id
    
    def _calculate_avg_hz_distance(self, humans: List[Dict], zombies: List[Dict]) -> float:
        """Calculate average distance between all human-zombie pairs."""
        if not humans or not zombies:
            return 0.0
        
        distances = []
        for h in humans:
            for z in zombies:
                dist = np.sqrt((h['x'] - z['x'])**2 + (h['y'] - z['y'])**2)
                distances.append(dist)
        
        return np.mean(distances) if distances else 0.0
    
    def compute_delta(self, from_snapshot_id: int, to_snapshot_id: int) -> int:
        """Compute and store differences between two snapshots."""
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM game_snapshots WHERE snapshot_id IN (%s, %s)
            """, (from_snapshot_id, to_snapshot_id))
            snapshots = cursor.fetchall()
            
            if len(snapshots) != 2:
                raise ValueError("Could not find both snapshots")
            
            snap1 = next(s for s in snapshots if s['snapshot_id'] == from_snapshot_id)
            snap2 = next(s for s in snapshots if s['snapshot_id'] == to_snapshot_id)
            
            if snap1['game_id'] != snap2['game_id']:
                raise ValueError("Snapshots are from different games")
            
            # Calculate deltas
            humans_killed = snap1['alive_humans'] - snap2['alive_humans']
            zombies_killed = snap1['alive_zombies'] - snap2['alive_zombies']
            
            avg_human_health_change = snap2['avg_human_health'] - snap1['avg_human_health']
            avg_zombie_health_change = snap2['avg_zombie_health'] - snap1['avg_zombie_health']
            
            distance_change = snap2['human_zombie_distance_avg'] - snap1['human_zombie_distance_avg']
            
            # Calculate movement distance
            cursor.execute("""
                SELECT 
                    AVG(SQRT(POWER(s2.x - s1.x, 2) + POWER(s2.y - s1.y, 2))) as avg_movement
                FROM snapshot_agents s1
                JOIN snapshot_agents s2 ON s1.agent_id = s2.agent_id
                WHERE s1.snapshot_id = %s 
                  AND s2.snapshot_id = %s
                  AND s1.is_alive = TRUE
                  AND s2.is_alive = TRUE
            """, (from_snapshot_id, to_snapshot_id))
            result = cursor.fetchone()
            avg_movement = result['avg_movement'] if result and result['avg_movement'] else 0.0
            
            # Get combat events between snapshots
            cursor.execute("""
                SELECT 
                    COUNT(*) as combat_events,
                    COALESCE(SUM(damage), 0) as total_damage
                FROM combat_log
                WHERE game_id = %s 
                  AND round_num > %s 
                  AND round_num <= %s
            """, (snap1['game_id'], snap1['round_num'], snap2['round_num']))
            combat_data = cursor.fetchone()
            
            # Insert delta record
            cursor.execute("""
                INSERT INTO snapshot_deltas
                (game_id, from_snapshot_id, to_snapshot_id,
                 humans_killed, zombies_killed,
                 avg_human_health_change, avg_zombie_health_change,
                 avg_movement_distance, human_zombie_distance_change,
                 total_damage_dealt, combat_events)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING delta_id
            """, (
                snap1['game_id'], from_snapshot_id, to_snapshot_id,
                humans_killed, zombies_killed,
                float(avg_human_health_change), float(avg_zombie_health_change),
                float(avg_movement), float(distance_change),
                int(combat_data['total_damage']), int(combat_data['combat_events'])
            ))
            
            delta_id = cursor.fetchone()['delta_id']
        
        print(f"📊 Computed delta {delta_id} between snapshots {from_snapshot_id} and {to_snapshot_id}")
        return delta_id
    
    def get_snapshot_summary(self, snapshot_id: int) -> Dict:
        """Get a summary of a specific snapshot."""
        with self.db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM game_snapshots WHERE snapshot_id = %s", (snapshot_id,))
            return cursor.fetchone()
    
    def get_game_snapshots(self, game_id: int) -> List[Dict]:
        """Get all snapshots for a game, ordered by round."""
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM game_snapshots 
                WHERE game_id = %s 
                ORDER BY round_num
            """, (game_id,))
            return cursor.fetchall()
    
    def get_snapshot_agents(self, snapshot_id: int, agent_type: Optional[str] = None) -> pd.DataFrame:
        """Get agent data from a snapshot as a DataFrame."""
        query = "SELECT * FROM snapshot_agents WHERE snapshot_id = %s"
        params = [snapshot_id]
        
        if agent_type:
            query += " AND agent_type = %s"
            params.append(agent_type)
        
        with self.db.get_cursor() as cursor:
            cursor.execute(query, params)
            data = cursor.fetchall()
        
        return pd.DataFrame(data)
    
    def analyze_game_dynamics(self, game_id: int) -> Dict:
        """Analyze overall game dynamics across all snapshots."""
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM game_snapshots 
                WHERE game_id = %s 
                ORDER BY round_num
            """, (game_id,))
            snapshots = cursor.fetchall()
            
            if not snapshots:
                return {"error": "No snapshots found for this game"}
            
            df = pd.DataFrame(snapshots)
            
            analysis = {
                'game_id': game_id,
                'total_rounds': int(df['round_num'].max()),
                'total_snapshots': len(snapshots),
                'human_survival_rate': (df['alive_humans'].iloc[-1] / df['total_humans'].iloc[0]) * 100,
                'zombie_survival_rate': (df['alive_zombies'].iloc[-1] / df['total_zombies'].iloc[0]) * 100,
                'humans_killed_total': int(df['total_humans'].iloc[0] - df['alive_humans'].iloc[-1]),
                'zombies_killed_total': int(df['total_zombies'].iloc[0] - df['alive_zombies'].iloc[-1]),
                'human_health_trend': {
                    'start': float(df['avg_human_health'].iloc[0]),
                    'end': float(df['avg_human_health'].iloc[-1]),
                    'min': float(df['avg_human_health'].min()),
                    'max': float(df['avg_human_health'].max())
                },
                'zombie_health_trend': {
                    'start': float(df['avg_zombie_health'].iloc[0]),
                    'end': float(df['avg_zombie_health'].iloc[-1]),
                    'min': float(df['avg_zombie_health'].min()),
                    'max': float(df['avg_zombie_health'].max())
                },
                'distance_trend': {
                    'start': float(df['human_zombie_distance_avg'].iloc[0]),
                    'end': float(df['human_zombie_distance_avg'].iloc[-1]),
                    'min': float(df['human_zombie_distance_avg'].min()),
                    'max': float(df['human_zombie_distance_avg'].max())
                },
                'total_combat_events': int(df['combat_events_this_round'].sum()),
                'avg_combat_per_round': float(df['combat_events_this_round'].mean()),
                'max_combat_round': int(df.loc[df['combat_events_this_round'].idxmax(), 'round_num']),
                'items_picked_up': int(df['total_items'].iloc[0] - df['available_items'].iloc[-1])
            }
            
            cursor.execute("SELECT * FROM snapshot_deltas WHERE game_id = %s", (game_id,))
            deltas = cursor.fetchall()
            
            if deltas:
                delta_df = pd.DataFrame(deltas)
                analysis['delta_analysis'] = {
                    'avg_humans_killed_per_interval': float(delta_df['humans_killed'].mean()),
                    'avg_zombies_killed_per_interval': float(delta_df['zombies_killed'].mean()),
                    'avg_damage_per_interval': float(delta_df['total_damage_dealt'].mean()),
                    'total_distance_moved': float(delta_df['avg_movement_distance'].sum())
                }
        
        return analysis
    
    def compare_snapshots(self, snapshot_id1: int, snapshot_id2: int) -> Dict:
        """Compare two snapshots in detail."""
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    s1.agent_id, s1.name, s1.agent_type,
                    s1.x as x1, s1.y as y1, s2.x as x2, s2.y as y2,
                    s1.health as health1, s2.health as health2,
                    s1.is_alive as alive1, s2.is_alive as alive2
                FROM snapshot_agents s1
                JOIN snapshot_agents s2 ON s1.agent_id = s2.agent_id
                WHERE s1.snapshot_id = %s AND s2.snapshot_id = %s
            """, (snapshot_id1, snapshot_id2))
            
            agents = cursor.fetchall()
        
        casualties = [a for a in agents if a['alive1'] and not a['alive2']]
        survivors = [a for a in agents if a['alive1'] and a['alive2']]
        
        movements = []
        health_changes = []
        
        for agent in survivors:
            dx = agent['x2'] - agent['x1']
            dy = agent['y2'] - agent['y1']
            distance = np.sqrt(dx**2 + dy**2)
            movements.append({
                'agent_id': agent['agent_id'],
                'name': agent['name'],
                'type': agent['agent_type'],
                'distance': float(distance),
                'dx': dx, 'dy': dy
            })
            
            health_change = agent['health2'] - agent['health1']
            health_changes.append({
                'agent_id': agent['agent_id'],
                'name': agent['name'],
                'type': agent['agent_type'],
                'health_change': health_change,
                'health1': agent['health1'],
                'health2': agent['health2']
            })
        
        return {
            'casualties': {
                'count': len(casualties),
                'by_type': {
                    'Human': len([c for c in casualties if c['agent_type'] == 'Human']),
                    'Zombie': len([c for c in casualties if c['agent_type'] == 'Zombie'])
                },
                'details': casualties
            },
            'movements': {
                'avg_distance': float(np.mean([m['distance'] for m in movements])) if movements else 0,
                'max_distance': float(max([m['distance'] for m in movements])) if movements else 0,
                'by_agent': movements
            },
            'health_changes': {
                'avg_change': float(np.mean([h['health_change'] for h in health_changes])) if health_changes else 0,
                'total_damage_taken': int(sum([abs(h['health_change']) for h in health_changes if h['health_change'] < 0])),
                'total_healing': int(sum([h['health_change'] for h in health_changes if h['health_change'] > 0])),
                'by_agent': health_changes
            }
        }
    
    def export_snapshot_to_json(self, snapshot_id: int, filepath: str):
        """Export a snapshot to a JSON file for external analysis."""
        with self.db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM game_snapshots WHERE snapshot_id = %s", (snapshot_id,))
            snapshot = cursor.fetchone()
            
            cursor.execute("SELECT * FROM snapshot_agents WHERE snapshot_id = %s", (snapshot_id,))
            agents = cursor.fetchall()
            
            cursor.execute("SELECT * FROM snapshot_items WHERE snapshot_id = %s", (snapshot_id,))
            items = cursor.fetchall()
        
        export_data = {
            'snapshot': dict(snapshot),
            'agents': [dict(a) for a in agents],
            'items': [dict(i) for i in items]
        }
        
        # Handle datetime serialization
        for key, value in export_data['snapshot'].items():
            if isinstance(value, datetime):
                export_data['snapshot'][key] = value.isoformat()
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"💾 Exported snapshot {snapshot_id} to {filepath}")
