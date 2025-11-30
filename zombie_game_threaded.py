import random
import math
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import copy
from database_manager import DatabaseManager


class GameDBThreaded:
    """Database-backed zombie game with multithreaded agent processing."""
    
    def __init__(self, db: DatabaseManager, grid_size: int = 20, num_threads: int = 4):
        self.db = db
        self.grid_size = grid_size
        self.game_id = None
        self.round_num = 0
        self.num_threads = num_threads
        
        # Thread synchronization
        self.state_lock = Lock()
        self.combat_buffer = []
        self.item_pickups = []
        
    def spawn_agents(self, num_humans: int = 5, num_zombies: int = 5):
        """Spawn agents and store them in database."""
        print(f"\n--- SPAWNING {num_humans} HUMANS AND {num_zombies} ZOMBIES ---")
        
        agents = []
        
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
        
        for i in range(num_zombies):
            x = random.randint(self.grid_size // 2, self.grid_size - 1)
            y = random.randint(0, self.grid_size - 1)
            
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
        print(f"\n🥊 Spawned {num_medkits} MedKits and ⚔️ {num_swords} Swords")
    
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
    
    def process_human_turn(self, human: Dict, game_state: Dict) -> Dict:
        """Process a single human's turn (thread-safe)."""
        # Work on a copy to avoid race conditions
        human_update = copy.deepcopy(human)
        
        # Check for role abilities (Doctor healing)
        if human_update['role_name'] == 'Doctor':
            role_data = human_update.get('role_data', {})
            heal_charges = role_data.get('heal_charges', 3)
            if heal_charges > 0 and human_update['health'] < human_update['max_health'] * 0.6:
                heal_amount = int(human_update['max_health'] * 0.5)
                human_update['health'] = min(human_update['health'] + heal_amount, human_update['max_health'])
                role_data['heal_charges'] = heal_charges - 1
                human_update['role_data'] = role_data
                print(f"  💚 {human_update['name']} heals for {heal_amount} HP!")
        
        # Look for items if no role
        if not human_update['role_name'] and game_state['items']:
            nearest_item = self.find_nearest(human_update, game_state['items'])
            if nearest_item:
                distance = self.calculate_distance(
                    human_update['x'], human_update['y'], nearest_item['x'], nearest_item['y']
                )
                if distance <= 1.5:
                    self.assign_role_to_human(human_update, nearest_item)
                    with self.state_lock:
                        self.item_pickups.append((nearest_item['item_id'], human_update['agent_id']))
                    return human_update
        
        # Find and attack/move toward nearest zombie
        if game_state['zombies']:
            nearest_zombie = self.find_nearest(human_update, game_state['zombies'])
            distance = self.calculate_distance(
                human_update['x'], human_update['y'], nearest_zombie['x'], nearest_zombie['y']
            )
            
            if distance <= 1.5:
                combat_result = self.calculate_attack(human_update, nearest_zombie)
                with self.state_lock:
                    self.combat_buffer.append(combat_result)
            else:
                # Move toward zombie
                dx = 1 if nearest_zombie['x'] > human_update['x'] else -1 if nearest_zombie['x'] < human_update['x'] else 0
                dy = 1 if nearest_zombie['y'] > human_update['y'] else -1 if nearest_zombie['y'] < human_update['y'] else 0
                human_update['x'] = max(0, min(self.grid_size - 1, human_update['x'] + dx))
                human_update['y'] = max(0, min(self.grid_size - 1, human_update['y'] + dy))
        
        return human_update
    
    def process_zombie_turn(self, zombie: Dict, game_state: Dict) -> Dict:
        """Process a single zombie's turn (thread-safe)."""
        zombie_update = copy.deepcopy(zombie)
        
        if not game_state['humans']:
            return zombie_update
        
        nearest_human = self.find_nearest(zombie_update, game_state['humans'])
        distance = self.calculate_distance(
            zombie_update['x'], zombie_update['y'], nearest_human['x'], nearest_human['y']
        )
        
        if distance <= 1.5:
            combat_result = self.calculate_attack(zombie_update, nearest_human)
            with self.state_lock:
                self.combat_buffer.append(combat_result)
        else:
            # Determine movement based on role
            role_data = zombie_update.get('role_data', {})
            movement_range = role_data.get('movement_range', 1)
            
            dx = 1 if nearest_human['x'] > zombie_update['x'] else -1 if nearest_human['x'] < zombie_update['x'] else 0
            dy = 1 if nearest_human['y'] > zombie_update['y'] else -1 if nearest_human['y'] < zombie_update['y'] else 0
            
            if movement_range >= 1:
                for _ in range(int(movement_range)):
                    zombie_update['x'] = max(0, min(self.grid_size - 1, zombie_update['x'] + dx))
                    zombie_update['y'] = max(0, min(self.grid_size - 1, zombie_update['y'] + dy))
            elif random.random() < movement_range:
                zombie_update['x'] = max(0, min(self.grid_size - 1, zombie_update['x'] + dx))
                zombie_update['y'] = max(0, min(self.grid_size - 1, zombie_update['y'] + dy))
        
        return zombie_update
    
    def calculate_attack(self, attacker: Dict, target: Dict) -> Dict:
        """Calculate attack damage (doesn't modify state directly)."""
        # Check for zombie miss chance
        if attacker['agent_type'] == 'Zombie' and random.random() < 0.2:
            print(f"  🧟 {attacker['name']} lunges at {target['name']} but misses!")
            return None
        
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
        
        emoji = "🔫" if attacker['agent_type'] == 'Human' else "🧟"
        print(f"  {emoji} {attacker['name']} attacks {target['name']} for {damage} damage!")
        
        return {
            'attacker_id': attacker['agent_id'],
            'target_id': target['agent_id'],
            'damage': damage,
            'was_critical': was_critical
        }
    
    def apply_combat_results(self, agents_dict: Dict[int, Dict]):
        """Apply all buffered combat results to agents."""
        for combat in self.combat_buffer:
            if combat is None:
                continue
                
            target_id = combat['target_id']
            if target_id in agents_dict:
                agents_dict[target_id]['health'] -= combat['damage']
                if agents_dict[target_id]['health'] <= 0:
                    agents_dict[target_id]['health'] = 0
                    agents_dict[target_id]['is_alive'] = False
                    print(f"  💀 {agents_dict[target_id]['name']} has been defeated!")
            
            # Log combat
            self.db.log_combat(
                self.game_id, self.round_num,
                combat['attacker_id'], combat['target_id'],
                combat['damage'], combat['was_critical']
            )
    
    def assign_role_to_human(self, human: Dict, item: Dict):
        """Assign role based on picked up item."""
        if item['item_type'] == 'MedKit':
            human['role_name'] = 'Doctor'
            human['role_data'] = {'heal_charges': 3, 'heal_amount': 0.5}
            print(f"  🥊 {human['name']} becomes a Doctor!")
        elif item['item_type'] == 'Sword':
            human['role_name'] = 'Hunter'
            human['attack_power'] = int(human['base_attack_power'] * 1.5)
            human['role_data'] = {'attack_multiplier': 2.0, 'critical_chance': 0.3}
            print(f"  ⚔️ {human['name']} becomes a Hunter!")
    
    def run_round(self):
        """Execute one round of the game with multithreading."""
        self.round_num += 1
        print(f"\n{'='*60}")
        print(f"ROUND {self.round_num}")
        print(f"{'='*60}")
        
        # Clear buffers
        self.combat_buffer = []
        self.item_pickups = []
        
        # Fetch all alive agents and items
        humans = self.db.get_alive_agents(self.game_id, 'Human')
        zombies = self.db.get_alive_agents(self.game_id, 'Zombie')
        items = self.db.get_available_items(self.game_id)
        
        # Create shared game state (read-only for threads)
        game_state = {
            'humans': humans,
            'zombies': zombies,
            'items': items
        }
        
        # Process agents in parallel
        updated_agents = {}
        
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            # Submit all human tasks
            human_futures = {
                executor.submit(self.process_human_turn, human, game_state): human['agent_id']
                for human in humans
            }
            
            # Submit all zombie tasks
            zombie_futures = {
                executor.submit(self.process_zombie_turn, zombie, game_state): zombie['agent_id']
                for zombie in zombies
            }
            
            # Collect human results
            for future in as_completed(human_futures):
                agent_id = human_futures[future]
                try:
                    updated_agent = future.result()
                    updated_agents[agent_id] = updated_agent
                except Exception as e:
                    print(f"Error processing human {agent_id}: {e}")
            
            # Collect zombie results
            for future in as_completed(zombie_futures):
                agent_id = zombie_futures[future]
                try:
                    updated_agent = future.result()
                    updated_agents[agent_id] = updated_agent
                except Exception as e:
                    print(f"Error processing zombie {agent_id}: {e}")
        
        # Apply combat results
        self.apply_combat_results(updated_agents)
        
        # Process item pickups
        for item_id, agent_id in self.item_pickups:
            self.db.pick_up_item(item_id, agent_id)
        
        # Batch update all agents in database
        import json
        updates = [
            (a['health'], a['is_alive'], a['x'], a['y'],
             a['role_name'], json.dumps(a.get('role_data', {})), a['agent_id'])
            for a in updated_agents.values()
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
        print("ZOMBIE APOCALYPSE SIMULATION (MULTITHREADED)")
        print("="*60)
        print(f"Grid Size: {self.grid_size}x{self.grid_size}")
        print(f"Agents: {num_humans} Humans vs {num_zombies} Zombies")
        print(f"Threads: {self.num_threads}")
        
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
