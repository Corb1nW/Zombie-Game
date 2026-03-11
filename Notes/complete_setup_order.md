# Complete Setup Order: PostgreSQL + Python + pgAdmin on WSL

Follow these steps in order for a complete development environment.

## PHASE 1: Install Core Components

### Step 1: Install PostgreSQL
```bash
sudo apt update
sudo apt upgrade -y
sudo apt install postgresql postgresql-contrib -y
sudo service postgresql start
```

### Step 2: Install Python Virtual Environment Tools
```bash
sudo apt install python3-full python3-venv -y
```

### Step 3: Install pgAdmin (Choose ONE option)

**Option A: Install pgAdmin on Windows (Recommended for WSL)**
1. Download from: https://www.pgadmin.org/download/pgadmin-4-windows/
2. Run the installer on Windows
3. Skip to Step 4 below

**Option B: Install pgAdmin in WSL (Web Interface)**
```bash
# Add pgAdmin repository
sudo apt install curl -y
curl -fsS https://www.pgadmin.org/static/packages_pgadmin_org.pub | sudo gpg --dearmor -o /usr/share/keyrings/packages-pgadmin-org.gpg

sudo sh -c 'echo "deb [signed-by=/usr/share/keyrings/packages-pgadmin-org.gpg] https://ftp.postgresql.org/pub/pgadmin/pgadmin4/apt/$(lsb_release -cs) pgadmin4 main" > /etc/apt/sources.list.d/pgadmin4.list'

sudo apt update
sudo apt install pgadmin4-web -y

# Setup web server
sudo /usr/pgadmin4/bin/setup-web.sh
# Enter email: your-email@example.com
# Enter password: (choose a secure password)
```

## PHASE 2: Configure PostgreSQL

### Step 4: Configure PostgreSQL for Remote Access (if using Windows pgAdmin)

```bash
# Edit postgresql.conf
sudo nano /etc/postgresql/*/main/postgresql.conf

# Change this line:
listen_addresses = 'localhost'
# To:
listen_addresses = '*'

# Save: Ctrl+X, then Y, then Enter
```

```bash
# Edit pg_hba.conf
sudo nano /etc/postgresql/*/main/pg_hba.conf

# Add this line before the "# IPv4 local connections:" section:
local   all   all   md5

# Add this line at the very end:
host    all             all             172.16.0.0/12           md5

# Save: Ctrl+X, then Y, then Enter
```

```bash
# Restart PostgreSQL
sudo service postgresql restart
```

### Step 5: Get Your WSL IP Address (needed for Windows pgAdmin)

```bash
hostname -I
# Note the first IP address (e.g., 172.x.x.x)
# You'll use this in pgAdmin connection settings
```

### Step 6: Create Database and User

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Run these commands in the PostgreSQL prompt:
```

```sql
CREATE DATABASE zombie_game;
CREATE USER zombie_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE zombie_game TO zombie_user;

-- Connect to the database
\c zombie_game

-- Grant additional permissions
GRANT ALL ON SCHEMA public TO zombie_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO zombie_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO zombie_user;

-- Exit
\q
```

### Step 7: Test Database Connection

```bash
# Test connection from WSL
psql -U zombie_user -d zombie_game -h localhost
# Enter your password
# Type \q to exit
```

## PHASE 3: Setup pgAdmin Connection

### Step 8: Connect pgAdmin to PostgreSQL

**If using Windows pgAdmin:**
1. Open pgAdmin on Windows
2. Right-click "Servers" → "Register" → "Server..."
3. **General tab:**
   - Name: `Zombie Game WSL`
4. **Connection tab:**
   - Host: `172.x.x.x` (your WSL IP from Step 5)
   - Port: `5432`
   - Maintenance database: `postgres`
   - Username: `zombie_user`
   - Password: `your_secure_password`
   - ✓ Save password
5. Click "Save"

**If using WSL pgAdmin (web):**
1. Open browser: http://127.0.0.1/pgadmin4
2. Login with email/password from Step 3
3. Right-click "Servers" → "Register" → "Server..."
4. **General tab:**
   - Name: `Zombie Game`
5. **Connection tab:**
   - Host: `localhost`
   - Port: `5432`
   - Maintenance database: `postgres`
   - Username: `zombie_user`
   - Password: `your_secure_password`
6. Click "Save"

### Step 9: Verify pgAdmin Connection

In pgAdmin:
1. Expand: `Servers → Zombie Game WSL → Databases → zombie_game`
2. Right-click `zombie_game` → "Query Tool"
3. Run this test query:
```sql
SELECT version();
```
4. You should see PostgreSQL version info!

## PHASE 4: Setup Python Environment

### Step 10: Create Virtual Environment

```bash
# Create project directory
mkdir -p ~/zombie_game
cd ~/zombie_game

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Your prompt should now show (venv)
```

### Step 11: Install Python Dependencies

```bash
# Make sure (venv) is showing in your prompt
pip install "psycopg[binary]>=3.3"

# Verify installation
python -c "import psycopg; print(f'✅ psycopg {psycopg.__version__}')"
```

### Step 12: Add Convenience Alias

```bash
# This lets you type 'zombie' to activate your environment
echo "alias zombie='cd ~/zombie_game && source venv/bin/activate'" >> ~/.bashrc
source ~/.bashrc

# Test it
deactivate  # Turn off venv
zombie      # Should activate it again!
```

## PHASE 5: Create and Test Your Application

### Step 13: Create Database Schema

```bash
# Make sure venv is active (zombie command)
cd ~/zombie_game

# Create Python files
nano database_manager.py
# Paste the DatabaseManager code below, then save (Ctrl+X, Y, Enter)
```

**Copy this code into database_manager.py:**

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

Now create the test file:

```bash
nano test_db_connection.py
# Paste this test code:
```

```python
from database_manager import DatabaseManager

db = DatabaseManager(
    host='localhost',
    database='zombie_game',
    user='zombie_user',
    password='your_secure_password'
)

try:
    db.connect()
    print("✅ Connected successfully!")
    
    db.initialize_schema()
    print("✅ Schema initialized!")
    
    game_id = db.create_game_session(grid_size=20)
    print(f"✅ Created game session: {game_id}")
    
    print("\n🎉 Setup complete!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
```

```bash
# Run the test
python test_db_connection.py
```

### Step 14: Verify Tables in pgAdmin

1. In pgAdmin, refresh the database: Right-click `zombie_game` → "Refresh"
2. Expand: `Databases → zombie_game → Schemas → public → Tables`
3. You should see:
   - `agents`
   - `combat_log`
   - `game_sessions`
   - `items`

### Step 15: Create Game Files

```bash
# Still in ~/zombie_game with venv active
nano zombie_game_db.py
# Paste the GameDB code from the artifact, save

# Create main game runner
nano run_game.py
# Paste this:
```

```python
from database_manager import DatabaseManager
from zombie_game_db import GameDB

# Database configuration
db = DatabaseManager(
    host='localhost',
    database='zombie_game',
    user='zombie_user',
    password='your_secure_password'
)

try:
    # Connect to database
    db.connect()
    
    # Run a small game (5v5)
    print("\n🎮 Starting small game (5v5)...")
    game = GameDB(db, grid_size=20)
    game.run_game(num_humans=5, num_zombies=5, max_rounds=50)
    
    # Uncomment for large scale test
    # print("\n🎮 Starting large game (500v500)...")
    # game = GameDB(db, grid_size=100)
    # game.run_game(num_humans=500, num_zombies=500, max_rounds=100)
    
finally:
    db.close()
```

### Step 16: Run Your First Game!

```bash
# Make sure venv is active
python run_game.py
```

### Step 17: View Results in pgAdmin

While or after the game runs, use pgAdmin to:

1. **View live game data:**
```sql
-- Right-click 'zombie_game' → Query Tool, then run:
SELECT * FROM game_sessions ORDER BY created_at DESC LIMIT 5;
SELECT * FROM agents WHERE game_id = 1;
SELECT * FROM combat_log WHERE game_id = 1 ORDER BY timestamp DESC LIMIT 20;
```

2. **Monitor agent status:**
```sql
SELECT 
    agent_type,
    COUNT(*) as total,
    SUM(CASE WHEN is_alive THEN 1 ELSE 0 END) as alive,
    AVG(health) as avg_health
FROM agents 
WHERE game_id = 1 
GROUP BY agent_type;
```

3. **View combat statistics:**
```sql
SELECT 
    COUNT(*) as total_attacks,
    SUM(damage) as total_damage,
    AVG(damage) as avg_damage,
    SUM(CASE WHEN was_critical THEN 1 ELSE 0 END) as critical_hits
FROM combat_log 
WHERE game_id = 1;
```

## PHASE 6: Daily Workflow

### Starting a New Session

```bash
# Open WSL terminal
zombie          # Activates venv and goes to project
python run_game.py
```

### Checking PostgreSQL Status

```bash
sudo service postgresql status
# If not running:
sudo service postgresql start
```

### Using pgAdmin

- **Windows pgAdmin**: Just open the application
- **WSL pgAdmin**: Open browser to http://127.0.0.1/pgadmin4

## Quick Troubleshooting Checklist

```bash
# 1. Check PostgreSQL is running
sudo service postgresql status

# 2. Check you can connect
psql -U zombie_user -d zombie_game -h localhost -c "SELECT 1;"

# 3. Check venv is activated
which python
# Should show: /home/yourname/zombie_game/venv/bin/python

# 4. Check psycopg installed
python -c "import psycopg; print(psycopg.__version__)"

# 5. Get WSL IP (for Windows pgAdmin)
hostname -I

# 6. Test pgAdmin connection
# In pgAdmin Query Tool:
SELECT version();
```

## Success Indicators

You'll know everything is working when:
- ✅ PostgreSQL service is running
- ✅ pgAdmin can connect and shows your database
- ✅ Virtual environment activates with `zombie` command
- ✅ `python run_game.py` executes without errors
- ✅ pgAdmin shows new rows in tables after game runs
- ✅ You can query game data in pgAdmin

## What's Next?

Now you can:
- Scale to 1000+ agents by changing `num_humans` and `num_zombies`
- Use pgAdmin to analyze game statistics
- Create custom SQL queries to study agent behavior
- Monitor performance with pgAdmin's Dashboard
- Export game data for analysis

🎉 **You're all set! Happy coding!**
