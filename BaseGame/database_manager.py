
import psycopg
from psycopg.rows import dict_row
from contextlib import contextmanager
import json
from typing import List, Dict, Optional, Tuple


class DatabaseManager:
    """Manages PostgreSQL connection and operations for the zombie game using psycopg 3.3."""

    def __init__(self, host='localhost', database='zombie_game', user='postgres', password='password', port=543>
        self.conninfo = f"host={host} port={port} dbname={database} user={user} password={password}"
        self.conn = None

    def connect(self):
        """Establish database connection."""
        try:
            self.conn = psycopg.connect(self.conninfo)
            print("✅ Connected to PostgreSQL database")
        except Exception as e:
            print(f"❌ Error connecting to database: {e}")
            raise

    def close(self):
    """Close database connection."""
        if self.conn:
            self.conn.close()
            print("📴 Database connection closed")

    @contextmanager
    def get_cursor(self, dict_cursor=True):
        """Context manager for database cursor."""
        cursor = self.conn.cursor(row_factory=dict_row if dict_cursor else None)
        try:
            yield cursor
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Database error: {e}")
            raise
        finally:
            cursor.close()

    def initialize_schema(self):
        """Create all necessary tables for the game."""
        schema_sql = """
        -- Game sessions table
        CREATE TABLE IF NOT EXISTS game_sessions (
            game_id SERIAL PRIMARY KEY,
            grid_size INTEGER NOT NULL,
            round_num INTEGER DEFAULT 0,
            status VARCHAR(20) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP
        );

        -- Agents table (both humans and zombies)
        CREATE TABLE IF NOT EXISTS agents (
            agent_id SERIAL PRIMARY KEY,
            game_id INTEGER REFERENCES game_sessions(game_id) ON DELETE CASCADE,
            name VARCHAR(50) NOT NULL,
            agent_type VARCHAR(20) NOT NULL,
            health INTEGER NOT NULL,
            max_health INTEGER NOT NULL,
            attack_power INTEGER NOT NULL,
            base_attack_power INTEGER NOT NULL,
            is_alive BOOLEAN DEFAULT TRUE,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            role_name VARCHAR(50),
            role_data JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Items table
        CREATE TABLE IF NOT EXISTS items (
            item_id SERIAL PRIMARY KEY,
            game_id INTEGER REFERENCES game_sessions(game_id) ON DELETE CASCADE,
            item_type VARCHAR(50) NOT NULL,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            picked_up BOOLEAN DEFAULT FALSE,
            picked_by_agent_id INTEGER REFERENCES agents(agent_id)
        );

        -- Combat log table
        CREATE TABLE IF NOT EXISTS combat_log (
            log_id SERIAL PRIMARY KEY,
            game_id INTEGER REFERENCES game_sessions(game_id) ON DELETE CASCADE,
            round_num INTEGER NOT NULL,
            attacker_id INTEGER REFERENCES agents(agent_id),
            target_id INTEGER REFERENCES agents(agent_id),
            damage INTEGER NOT NULL,
            was_critical BOOLEAN DEFAULT FALSE,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Create indexes for performance
        CREATE INDEX IF NOT EXISTS idx_agents_game_alive ON agents(game_id, is_alive);
        CREATE INDEX IF NOT EXISTS idx_agents_position ON agents(x, y) WHERE is_alive = TRUE;
        CREATE INDEX IF NOT EXISTS idx_items_game_available ON items(game_id, picked_up);
        CREATE INDEX IF NOT EXISTS idx_combat_log_game ON combat_log(game_id, round_num);
        """

        with self.get_cursor(dict_cursor=False) as cursor:
            cursor.execute(schema_sql)
        print("✅ Database schema initialized")

    def create_game_session(self, grid_size: int) -> int:
        """Create a new game session and return game_id."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO game_sessions (grid_size, status) VALUES (%s, %s) RETURNING game_id",
                (grid_size, 'active')
            )
            result = cursor.fetchone()
            game_id = result['game_id']
            print(f"🎮 Created game session: {game_id}")
            return game_id

    def batch_insert_agents(self, game_id: int, agents: List[Dict]):
        """Batch insert multiple agents efficiently using psycopg 3 executemany."""
        insert_sql = """
            INSERT INTO agents (game_id, name, agent_type, health, max_health,
                              attack_power, base_attack_power, x, y, role_name, role_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING agent_id
        """

        values = [
            (game_id, a['name'], a['agent_type'], a['health'], a['max_health'],
             a['attack_power'], a['base_attack_power'], a['x'], a['y'],
             a.get('role_name'), json.dumps(a.get('role_data', {})))
            for a in agents
        ]

        with self.get_cursor(dict_cursor=False) as cursor:
            cursor.executemany(insert_sql, values)
            print(f"✅ Inserted {len(agents)} agents")

    def batch_update_agents(self, updates: List[Tuple]):
        """Batch update agent positions and health using psycopg 3 executemany."""
        update_sql = """
            UPDATE agents
            SET health = %s, is_alive = %s, x = %s, y = %s,
                role_name = %s, role_data = %s, updated_at = CURRENT_TIMESTAMP
            WHERE agent_id = %s
        """

        with self.get_cursor(dict_cursor=False) as cursor:
            cursor.executemany(update_sql, updates)

    def get_alive_agents(self, game_id: int, agent_type: Optional[str] = None) -> List[Dict]:
        """Get all alive agents, optionally filtered by type."""
        query = "SELECT * FROM agents WHERE game_id = %s AND is_alive = TRUE"
        params = [game_id]

        if agent_type:
            query += " AND agent_type = %s"
            params.append(agent_type)

        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    def get_available_items(self, game_id: int) -> List[Dict]:
        """Get all unpicked items."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM items WHERE game_id = %s AND picked_up = FALSE",
                (game_id,)
            )
            return cursor.fetchall()

    def insert_items(self, game_id: int, items: List[Dict]):
        """Insert items into the database using psycopg 3 executemany."""
        insert_sql = """
            INSERT INTO items (game_id, item_type, x, y)
            VALUES (%s, %s, %s, %s)
        """

        values = [(game_id, item['item_type'], item['x'], item['y']) for item in items]

        with self.get_cursor(dict_cursor=False) as cursor:
            cursor.executemany(insert_sql, values)
            print(f"✅ Inserted {len(items)} items")

    def pick_up_item(self, item_id: int, agent_id: int):
        """Mark an item as picked up."""
        with self.get_cursor(dict_cursor=False) as cursor:
            cursor.execute(
                "UPDATE items SET picked_up = TRUE, picked_by_agent_id = %s WHERE item_id = %s",
                (agent_id, item_id)
            )
    
    def log_combat(self, game_id: int, round_num: int, attacker_id: int,
                   target_id: int, damage: int, was_critical: bool = False):
        """Log combat action for analytics."""
        with self.get_cursor(dict_cursor=False) as cursor:
            cursor.execute(
                """INSERT INTO combat_log (game_id, round_num, attacker_id, target_id, damage, was_critical)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (game_id, round_num, attacker_id, target_id, damage, was_critical)
            )

    def update_game_round(self, game_id: int, round_num: int):
        """Update the current round number."""
        with self.get_cursor(dict_cursor=False) as cursor:
            cursor.execute(
                "UPDATE game_sessions SET round_num = %s WHERE game_id = %s",
                (round_num, game_id)
            )
    
    def end_game(self, game_id: int, winner: str):
        """Mark game as ended."""
        with self.get_cursor(dict_cursor=False) as cursor:
            cursor.execute(
                "UPDATE game_sessions SET status = %s, ended_at = CURRENT_TIMESTAMP WHERE game_id = %s",
                (winner, game_id)
            )

    def get_game_statistics(self, game_id: int) -> Dict:
        """Get comprehensive game statistics."""
        with self.get_cursor() as cursor:
            # Agent counts
            cursor.execute("""
                SELECT agent_type,
                       COUNT(*) as total,
                       SUM(CASE WHEN is_alive THEN 1 ELSE 0 END) as alive
                FROM agents
                WHERE game_id = %s
                GROUP BY agent_type
            """, (game_id,))
            agent_stats = cursor.fetchall()
            
            # Combat stats
            cursor.execute("""
                SELECT COUNT(*) as total_attacks,
                       SUM(damage) as total_damage,
                       SUM(CASE WHEN was_critical THEN 1 ELSE 0 END) as critical_hits
                FROM combat_log
                WHERE game_id = %s
            """, (game_id,))
            combat_stats = cursor.fetchone()

            return {
                'agents': agent_stats,
                'combat': combat_stats
            }
    
    def clean_old_games(self, days: int = 7):
        """Remove games older than specified days."""
        with self.get_cursor(dict_cursor=False) as cursor:
            cursor.execute("""
                DELETE FROM game_sessions
                WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '%s days'
            """, (days,))
            print(f"🧹 Cleaned up old game sessions")