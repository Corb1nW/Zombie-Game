# Zombie Game Database Project - Complete File Structure

## 📁 Project Structure

```
~/zombie_game/
├── venv/                          # Virtual environment (auto-generated)
├── database_manager.py            # Database operations layer
├── zombie_game_db.py              # Main game logic
├── run_game.py                    # Game runner script
├── test_db_connection.py          # Database connection test
├── README.md                      # Project documentation
└── .env                           # Environment variables (optional)
```

---

## 📄 File 1: `database_manager.py`

```python
import psycopg
from psycopg.rows import dict_row
from contextlib import contextmanager
import json
from typing import List, Dict, Optional, Tuple


class DatabaseManager:
    """Manages PostgreSQL connection and operations for the zombie game using psycopg 3.3."""
    
    def __init__(self, host='localhost', database='zombie_game', user='postgres', password='password', port=5432):
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
```

---

## 📄 File 2: `zombie_game_db.py`

```python
import random
import math
from typing import List, Dict
import json


class GameDB:
    """Database-backed zombie game that can scale to thousands of agents."""
    
    def __init__(self, db, grid_size: int = 20):
        self.db = db
        self.grid_size = grid_size
        self.game_id = None
        self.round_num = 0
    
    def spawn_agents(self, num_humans: int = 5, num_zombies: int = 5):
        """Spawn agents and store them in database."""
        print(f"\n--- SPAWNING {num_humans} HUMANS AND {num_zombies} ZOMBIES ---")
        
        agents = []
        
        # Create humans
        for i in range(num_humans):
            x = random.randint(0, self.grid_size // 2 - 1)
            y = random.randint(0, self.grid_size - 1)
            agents.append({
                'name': f'Human_{i+1}',
                'agent_type': 'Human',
                'health': 100,
                'max_health': 100,
                'attack_power': 20,
                'base_attack_power': 20,
                'x': x,
                'y': y,
                'role_name': None,
                'role_data': {}
            })
        
        # Create zombies with random roles
        for i in range(num_zombies):
            x = random.randint(self.grid_size // 2, self.grid_size - 1)
            y = random.randint(0, self.grid_size - 1)
            
            # Randomly assign role
            roll = random.random()
            if roll < 0.25:
                role_name = 'Speed Zombie'
                role_data = {'movement_range': 2, 'attack_multiplier': 0.6}
            elif roll < 0.50:
                role_name = 'Tank Zombie'
                role_data = {'movement_range': 0.5, 'attack_multiplier': 2.5}
            else:
                role_name = None
                role_data = {}
            
            agents.append({
                'name': f'Zombie_{i+1}',
                'agent_type': 'Zombie',
                'health': 80,
                'max_health': 80,
                'attack_power': 15,
                'base_attack_power': 15,
                'x': x,
                'y': y,
                'role_name': role_name,
                'role_data': role_data
            })
        
        self.db.batch_insert_agents(self.game_id, agents)
    
    def spawn_items(self, num_medkits: int = 1, num_swords: int = 1):
        """Spawn items at random locations."""
        items = []
        
        for _ in range(num_medkits):
            items.append({
                'item_type': 'MedKit',
                'x': random.randint(0, self.grid_size - 1),
                'y': random.randint(0, self.grid_size - 1)
            })
        
        for _ in range(num_swords):
            items.append({
                'item_type': 'Sword',
                'x': random.randint(0, self.grid_size - 1),
                'y': random.randint(0, self.grid_size - 1)
            })
        
        self.db.insert_items(self.game_id, items)
        print(f"\n🏥 Spawned {num_medkits} MedKits and ⚔️ {num_swords} Swords")
    
    def calculate_distance(self, x1: int, y1: int, x2: int, y2: int) -> float:
        """Calculate Euclidean distance between two points."""
        return math.sqrt((x1 - x2)**2 + (y1 - y2)**2)
    
    def find_nearest(self, agent: Dict, targets: List[Dict]) -> Dict:
        """Find nearest target to an agent."""
        if not targets:
            return None
        return min(targets, key=lambda t: self.calculate_distance(
            agent['x'], agent['y'], t['x'], t['y']
        ))
    
    def process_human_turn(self, human: Dict, game_state: Dict):
        """Process a single human's turn."""
        # Check for role abilities (Doctor healing)
        if human['role_name'] == 'Doctor':
            role_data = human.get('role_data', {})
            heal_charges = role_data.get('heal_charges', 3)
            if heal_charges > 0 and human['health'] < human['max_health'] * 0.6:
                heal_amount = int(human['max_health'] * 0.5)
                human['health'] = min(human['health'] + heal_amount, human['max_health'])
                role_data['heal_charges'] = heal_charges - 1
                human['role_data'] = role_data
                print(f"  💚 {human['name']} heals for {heal_amount} HP!")
        
        # Look for items if no role
        if not human['role_name'] and game_state['items']:
            nearest_item = self.find_nearest(human, game_state['items'])
            distance = self.calculate_distance(
                human['x'], human['y'], nearest_item['x'], nearest_item['y']
            )
            if distance <= 1.5:
                self.assign_role_to_human(human, nearest_item)
                self.db.pick_up_item(nearest_item['item_id'], human['agent_id'])
                return
        
        # Find and attack/move toward nearest zombie
        if game_state['zombies']:
            nearest_zombie = self.find_nearest(human, game_state['zombies'])
            distance = self.calculate_distance(
                human['x'], human['y'], nearest_zombie['x'], nearest_zombie['y']
            )
            
            if distance <= 1.5:
                self.attack(human, nearest_zombie)
            else:
                # Move toward zombie
                dx = 1 if nearest_zombie['x'] > human['x'] else -1 if nearest_zombie['x'] < human['x'] else 0
                dy = 1 if nearest_zombie['y'] > human['y'] else -1 if nearest_zombie['y'] < human['y'] else 0
                human['x'] = max(0, min(self.grid_size - 1, human['x'] + dx))
                human['y'] = max(0, min(self.grid_size - 1, human['y'] + dy))
    
    def process_zombie_turn(self, zombie: Dict, game_state: Dict):
        """Process a single zombie's turn."""
        if not game_state['humans']:
            return
        
        nearest_human = self.find_nearest(zombie, game_state['humans'])
        distance = self.calculate_distance(
            zombie['x'], zombie['y'], nearest_human['x'], nearest_human['y']
        )
        
        if distance <= 1.5:
            self.attack(zombie, nearest_human)
        else:
            # Determine movement based on role
            role_data = zombie.get('role_data', {})
            movement_range = role_data.get('movement_range', 1)
            
            dx = 1 if nearest_human['x'] > zombie['x'] else -1 if nearest_human['x'] < zombie['x'] else 0
            dy = 1 if nearest_human['y'] > zombie['y'] else -1 if nearest_human['y'] < zombie['y'] else 0
            
            # Handle different movement ranges
            if movement_range >= 1:
                for _ in range(int(movement_range)):
                    zombie['x'] = max(0, min(self.grid_size - 1, zombie['x'] + dx))
                    zombie['y'] = max(0, min(self.grid_size - 1, zombie['y'] + dy))
            elif random.random() < movement_range:
                zombie['x'] = max(0, min(self.grid_size - 1, zombie['x'] + dx))
                zombie['y'] = max(0, min(self.grid_size - 1, zombie['y'] + dy))
    
    def attack(self, attacker: Dict, target: Dict):
        """Execute attack from attacker to target."""
        # Check for zombie miss chance
        if attacker['agent_type'] == 'Zombie' and random.random() < 0.2:
            print(f"  🧟 {attacker['name']} lunges at {target['name']} but misses!")
            return
        
        # Calculate base damage
        damage = random.randint(
            int(attacker['attack_power'] * 0.5),
            attacker['attack_power']
        )
        
        # Apply role modifiers
        was_critical = False
        role_data = attacker.get('role_data', {})
        attack_multiplier = role_data.get('attack_multiplier', 1.0)
        
        # Hunter critical hit chance
        if attacker['role_name'] == 'Hunter' and random.random() < 0.3:
            attack_multiplier *= 1.5
            was_critical = True
            print(f"  ⚡ CRITICAL HIT!")
        
        damage = int(damage * attack_multiplier)
        
        # Apply damage
        target['health'] -= damage
        if target['health'] <= 0:
            target['health'] = 0
            target['is_alive'] = False
            print(f"  💀 {target['name']} has been defeated!")
        
        emoji = "🔫" if attacker['agent_type'] == 'Human' else "🧟"
        print(f"  {emoji} {attacker['name']} attacks {target['name']} for {damage} damage!")
        
        # Log combat
        self.db.log_combat(
            self.game_id, self.round_num,
            attacker['agent_id'], target['agent_id'],
            damage, was_critical
        )
    
    def assign_role_to_human(self, human: Dict, item: Dict):
        """Assign role based on picked up item."""
        if item['item_type'] == 'MedKit':
            human['role_name'] = 'Doctor'
            human['role_data'] = {'heal_charges': 3, 'heal_amount': 0.5}
            print(f"  🏥 {human['name']} becomes a Doctor!")
        elif item['item_type'] == 'Sword':
            human['role_name'] = 'Hunter'
            human['attack_power'] = int(human['base_attack_power'] * 1.5)
            human['role_data'] = {'attack_multiplier': 2.0, 'critical_chance': 0.3}
            print(f"  ⚔️ {human['name']} becomes a Hunter!")
    
    def run_round(self):
        """Execute one round of the game."""
        self.round_num += 1
        print(f"\n{'='*60}")
        print(f"ROUND {self.round_num}")
        print(f"{'='*60}")
        
        # Fetch all alive agents and items
        humans = self.db.get_alive_agents(self.game_id, 'Human')
        zombies = self.db.get_alive_agents(self.game_id, 'Zombie')
        items = self.db.get_available_items(self.game_id)
        
        game_state = {
            'humans': humans,
            'zombies': zombies,
            'items': items
        }
        
        # Process all human turns
        for human in humans:
            self.process_human_turn(human, game_state)
        
        # Process all zombie turns
        for zombie in zombies:
            self.process_zombie_turn(zombie, game_state)
        
        # Batch update all agents in database
        all_agents = humans + zombies
        updates = [
            (a['health'], a['is_alive'], a['x'], a['y'],
             a['role_name'], json.dumps(a.get('role_data', {})), a['agent_id'])
            for a in all_agents
        ]
        self.db.batch_update_agents(updates)
        self.db.update_game_round(self.game_id, self.round_num)
    
    def is_game_over(self) -> bool:
        """Check if game is over."""
        humans = self.db.get_alive_agents(self.game_id, 'Human')
        zombies = self.db.get_alive_agents(self.game_id, 'Zombie')
        return len(humans) == 0 or len(zombies) == 0
    
    def display_status(self):
        """Display current game status."""
        humans = self.db.get_alive_agents(self.game_id, 'Human')
        zombies = self.db.get_alive_agents(self.game_id, 'Zombie')
        
        print("\n--- HUMANS ---")
        for h in humans:
            role = f", Role: {h['role_name']}" if h['role_name'] else ""
            print(f"{h['name']} - HP: {h['health']}/{h['max_health']}, Pos: ({h['x']},{h['y']}){role}")
        
        print("\n--- ZOMBIES ---")
        for z in zombies:
            role = f", Role: {z['role_name']}" if z['role_name'] else ""
            print(f"{z['name']} - HP: {z['health']}/{z['max_health']}, Pos: ({z['x']},{z['y']}){role}")
        
        print(f"\nAlive: {len(humans)} Humans, {len(zombies)} Zombies")
    
    def run_game(self, num_humans: int = 5, num_zombies: int = 5, max_rounds: int = 50):
        """Run the full game simulation."""
        print("="*60)
        print("ZOMBIE APOCALYPSE SIMULATION (DATABASE-BACKED)")
        print("="*60)
        print(f"Grid Size: {self.grid_size}x{self.grid_size}")
        print(f"Agents: {num_humans} Humans vs {num_zombies} Zombies")
        
        # Create game session
        self.game_id = self.db.create_game_session(self.grid_size)
        
        # Spawn entities
        self.spawn_agents(num_humans, num_zombies)
        self.spawn_items()
        self.display_status()
        
        # Run game loop
        while not self.is_game_over() and self.round_num < max_rounds:
            self.run_round()
        
        # End game
        humans = self.db.get_alive_agents(self.game_id, 'Human')
        zombies = self.db.get_alive_agents(self.game_id, 'Zombie')
        
        print("\n" + "="*60)
        print("GAME OVER!")
        print("="*60)
        self.display_status()
        
        if len(humans) > len(zombies):
            winner = "HUMANS WIN"
            print("\n🎉 HUMANS WIN!")
        elif len(zombies) > len(humans):
            winner = "ZOMBIES WIN"
            print("\n🧟 ZOMBIES WIN!")
        else:
            winner = "DRAW"
            print("\n⚔️ DRAW!")
        
        self.db.end_game(self.game_id, winner)
        
        # Display statistics
        stats = self.db.get_game_statistics(self.game_id)
        print(f"\n📊 Final Statistics:")
        print(f"   Total attacks: {stats['combat']['total_attacks']}")
        print(f"   Total damage: {stats['combat']['total_damage']}")
        print(f"   Critical hits: {stats['combat']['critical_hits']}")
```

---

## 📄 File 3: `run_game.py`

```python
from database_manager import DatabaseManager
from zombie_game_db import GameDB

# Database configuration
db = DatabaseManager(
    host='localhost',
    database='zombie_game',
    user='zombie_user',
    password='your_secure_password'  # UPDATE THIS!
)

try:
    # Connect to database
    db.connect()
    
    # Initialize schema (only needed first time, safe to run multiple times)
    db.initialize_schema()
    
    # Run a small game (5v5)
    print("\n🎮 Starting game (5v5)...")
    game = GameDB(db, grid_size=20)
    game.run_game(num_humans=5, num_zombies=5, max_rounds=50)
    
    # Uncomment for large scale test (500v500)
    # print("\n🎮 Starting large game (500v500)...")
    # game = GameDB(db, grid_size=100)
    # game.run_game(num_humans=500, num_zombies=500, max_rounds=100)
    
finally:
    db.close()
```

---

## 📄 File 4: `test_db_connection.py`

```python
from database_manager import DatabaseManager

db = DatabaseManager(
    host='localhost',
    database='zombie_game',
    user='zombie_user',
    password='your_secure_password'  # UPDATE THIS!
)

try:
    db.connect()
    print("✅ Connected successfully!")
    
    db.initialize_schema()
    print("✅ Schema initialized!")
    
    game_id = db.create_game_session(grid_size=20)
    print(f"✅ Created game session: {game_id}")
    
    print("\n🎉 Database setup complete!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
```

---

## 📄 File 5: `README.md`

```markdown
# Zombie Game - Database-Backed Dynamic Systems Simulation

A scalable zombie apocalypse simulation using PostgreSQL to handle 1000+ agents.

## Features

- **Database-backed state**: All agent states stored in PostgreSQL
- **Scalable**: Handle 1000+ agents with batch operations
- **Role system**: Humans can become Doctors or Hunters, Zombies can be Speed or Tank variants
- **Combat logging**: Track every attack for analytics
- **pgAdmin support**: Visual database management

## Requirements

- Python 3.12+
- PostgreSQL 16+
- psycopg 3.3+
- WSL2 (Windows) or Linux

## Installation

```bash
# Create virtual environment
cd ~/zombie_game
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install "psycopg[binary]>=3.3"
```

## Database Setup

```bash
# Start PostgreSQL
sudo service postgresql start

# Create database and user
sudo -u postgres psql
CREATE DATABASE zombie_game;
CREATE USER zombie_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE zombie_game TO zombie_user;
\c zombie_game
GRANT ALL ON SCHEMA public TO zombie_user;
\q
```

## Usage

```bash
# Activate environment
source venv/bin/activate

# Test database connection
python test_db_connection.py

# Run game (5v5)
python run_game.py
```

## Scaling to 1000+ Agents