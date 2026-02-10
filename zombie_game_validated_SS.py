import random
import math
from typing import List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, RLock
import copy
from dataclasses import dataclass
from enum import Enum
from database_manager import DatabaseManager
from snapshot_manager3 import SnapshotManager


class EventType(Enum):
    """Types of events that can occur in the game."""
    MOVE = "move"
    ATTACK = "attack"
    HEAL = "heal"
    PICKUP_ITEM = "pickup_item"


@dataclass
class GameEvent:
    """Represents a single game event with validation requirements."""
    event_type: EventType
    actor_id: int
    actor_name: str
    target_id: Optional[int] = None
    target_name: Optional[str] = None
    data: Dict = None
    priority: int = 0  # Higher priority events are validated/processed first
    
    def __post_init__(self):
        if self.data is None:
            self.data = {}


class AgentState:
    """Thread-safe agent state tracker."""
    
    def __init__(self, agent_data: Dict):
        self.agent_id = agent_data['agent_id']
        self.name = agent_data['name']
        self.agent_type = agent_data['agent_type']
        self.health = agent_data['health']
        self.max_health = agent_data['max_health']
        self.attack_power = agent_data['attack_power']
        self.base_attack_power = agent_data['base_attack_power']
        self.x = agent_data['x']
        self.y = agent_data['y']
        self.is_alive = agent_data['is_alive']
        self.role_name = agent_data.get('role_name')
        self.role_data = agent_data.get('role_data', {})
        
        # Validation tracking
        self.lock = RLock()  # Reentrant lock for nested locking
        self.has_acted_this_round = False
        self.has_been_attacked_this_round = False
        self.damage_taken_this_round = 0
    
    def to_dict(self) -> Dict:
        """Convert back to dictionary format."""
        with self.lock:
            return {
                'agent_id': self.agent_id,
                'name': self.name,
                'agent_type': self.agent_type,
                'health': self.health,
                'max_health': self.max_health,
                'attack_power': self.attack_power,
                'base_attack_power': self.base_attack_power,
                'x': self.x,
                'y': self.y,
                'is_alive': self.is_alive,
                'role_name': self.role_name,
                'role_data': self.role_data
            }


class GameDBValidated:
    """Database-backed zombie game with validated multithreaded event processing."""
    
    def __init__(self, db: DatabaseManager, grid_size: int = 20, num_threads: int = 4, snapshot_interval: int = 10):
        self.db = db
        self.grid_size = grid_size
        self.game_id = None
        self.round_num = 0
        self.num_threads = num_threads
        
        # Thread synchronization
        self.state_lock = Lock()
        self.agent_states: Dict[int, AgentState] = {}
        self.pending_events: List[GameEvent] = []
        self.valid_events: List[GameEvent] = []
        self.invalid_events: List[GameEvent] = []

        self.sm = SnapshotManager(db)
        self.snapshot_interval = snapshot_interval
        self.snapshot_ids = []
        
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

    def find_nearest(self, agent: AgentState, targets: List[AgentState]) -> Optional[AgentState]:
        """Find nearest target to an agent."""
        if not targets:
            return None
        return min(targets, key=lambda t: self.calculate_distance(
            agent.x, agent.y, t.x, t.y
        ))
    
    def generate_human_events(self, human: AgentState, game_state: Dict) -> List[GameEvent]:
        """Generate all possible events for a human (runs in parallel)."""
        events = []
        
        # Check for role abilities (Doctor healing)
        if human.role_name == 'Doctor':
            role_data = human.role_data or {}
            heal_charges = role_data.get('heal_charges', 3)
            if heal_charges > 0 and human.health < human.max_health * 0.6:
                heal_amount = int(human.max_health * 0.5)
                events.append(GameEvent(
                    event_type=EventType.HEAL,
                    actor_id=human.agent_id,
                    actor_name=human.name,
                    priority=10,  # High priority
                    data={
                        'heal_amount': heal_amount,
                        'heal_charges': heal_charges
                    }
                ))
                return events  # Healing takes priority, skip other actions
        
        # Look for items if no role
        if not human.role_name and game_state['items']:
            nearest_item = self.find_nearest_item(human, game_state['items'])
            if nearest_item:
                distance = self.calculate_distance(
                    human.x, human.y, nearest_item['x'], nearest_item['y']
                )
                if distance <= 1.5:
                    events.append(GameEvent(
                        event_type=EventType.PICKUP_ITEM,
                        actor_id=human.agent_id,
                        actor_name=human.name,
                        target_id=nearest_item['item_id'],
                        priority=8,
                        data={'item': nearest_item}
                    ))
                    return events
        
        # Find and attack/move toward nearest zombie
        if game_state['zombies']:
            nearest_zombie = self.find_nearest(human, game_state['zombies'])
            if nearest_zombie:
                distance = self.calculate_distance(
                    human.x, human.y, nearest_zombie.x, nearest_zombie.y
                )
                
                if distance <= 1.5:
                    # Generate attack event
                    events.append(self.create_attack_event(human, nearest_zombie))
                else:
                    # Generate move event
                    dx = 1 if nearest_zombie.x > human.x else -1 if nearest_zombie.x < human.x else 0
                    dy = 1 if nearest_zombie.y > human.y else -1 if nearest_zombie.y < human.y else 0
                    new_x = max(0, min(self.grid_size - 1, human.x + dx))
                    new_y = max(0, min(self.grid_size - 1, human.y + dy))
                    
                    events.append(GameEvent(
                        event_type=EventType.MOVE,
                        actor_id=human.agent_id,
                        actor_name=human.name,
                        priority=1,
                        data={'new_x': new_x, 'new_y': new_y}
                    ))
        
        return events
    
    def generate_zombie_events(self, zombie: AgentState, game_state: Dict) -> List[GameEvent]:
        """Generate all possible events for a zombie (runs in parallel)."""
        events = []
        
        if not game_state['humans']:
            return events
        
        nearest_human = self.find_nearest(zombie, game_state['humans'])
        if not nearest_human:
            return events
            
        distance = self.calculate_distance(
            zombie.x, zombie.y, nearest_human.x, nearest_human.y
        )
        
        if distance <= 1.5:
            # Generate attack event
            events.append(self.create_attack_event(zombie, nearest_human))
        else:
            # Generate move event
            role_data = zombie.role_data or {}
            movement_range = role_data.get('movement_range', 1)
            
            dx = 1 if nearest_human.x > zombie.x else -1 if nearest_human.x < zombie.x else 0
            dy = 1 if nearest_human.y > zombie.y else -1 if nearest_human.y < zombie.y else 0
            
            new_x = zombie.x
            new_y = zombie.y
            
            if movement_range >= 1:
                for _ in range(int(movement_range)):
                    new_x = max(0, min(self.grid_size - 1, new_x + dx))
                    new_y = max(0, min(self.grid_size - 1, new_y + dy))
            elif random.random() < movement_range:
                new_x = max(0, min(self.grid_size - 1, new_x + dx))
                new_y = max(0, min(self.grid_size - 1, new_y + dy))
            
            events.append(GameEvent(
                event_type=EventType.MOVE,
                actor_id=zombie.agent_id,
                actor_name=zombie.name,
                priority=1,
                data={'new_x': new_x, 'new_y': new_y}
            ))
        
        return events
    
    def create_attack_event(self, attacker: AgentState, target: AgentState) -> GameEvent:
        """Create an attack event with calculated damage."""
        # Check for zombie miss chance
        if attacker.agent_type == 'Zombie' and random.random() < 0.2:
            return GameEvent(
                event_type=EventType.ATTACK,
                actor_id=attacker.agent_id,
                actor_name=attacker.name,
                target_id=target.agent_id,
                target_name=target.name,
                priority=5,
                data={'damage': 0, 'missed': True, 'was_critical': False}
            )
        
        # Calculate damage
        damage = random.randint(
            int(attacker.attack_power * 0.5),
            attacker.attack_power
        )
        
        # Apply role modifiers
        was_critical = False
        role_data = attacker.role_data or {}
        attack_multiplier = role_data.get('attack_multiplier', 1.0)
        
        # Hunter critical hit chance
        if attacker.role_name == 'Hunter' and random.random() < 0.3:
            attack_multiplier *= 1.5
            was_critical = True
        
        damage = int(damage * attack_multiplier)
        
        return GameEvent(
            event_type=EventType.ATTACK,
            actor_id=attacker.agent_id,
            actor_name=attacker.name,
            target_id=target.agent_id,
            target_name=target.name,
            priority=5,
            data={
                'damage': damage,
                'was_critical': was_critical,
                'missed': False
            }
        )
    
    def find_nearest_item(self, agent: AgentState, items: List[Dict]) -> Optional[Dict]:
        """Find nearest item to an agent."""
        if not items:
            return None
        return min(items, key=lambda item: self.calculate_distance(
            agent.x, agent.y, item['x'], item['y']
        ))
    
    def validate_event(self, event: GameEvent) -> Tuple[bool, str]:
        """
        Validate if an event can be executed given current game state.
        Returns (is_valid, reason).
        This is the KEY to correctness - runs in parallel with locks.
        """
        actor = self.agent_states.get(event.actor_id)
        
        # Acquire actor lock to check state atomically
        with actor.lock:
            # Rule 1: Actor must be alive
            if not actor.is_alive:
                return False, f"{actor.name} is dead"
            
            # Rule 2: Actor can only act once per round
            if actor.has_acted_this_round:
                return False, f"{actor.name} already acted this round"
            
            # Event-specific validation
            if event.event_type == EventType.ATTACK:
                target = self.agent_states.get(event.target_id)
                
                # Acquire target lock to check state atomically
                with target.lock:
                    # Rule 3: Target must be alive
                    if not target.is_alive:
                        return False, f"Target {target.name} is already dead"
                    
                    # Rule 4: Attacker must be in range
                    distance = self.calculate_distance(
                        actor.x, actor.y, target.x, target.y
                    )
                    if distance > 1.5:
                        return False, f"{actor.name} out of range of {target.name}"
                
                return True, "Valid attack"
            
            elif event.event_type == EventType.MOVE:
                # Rule 5: Movement is always valid if actor is alive and hasn't acted
                return True, "Valid move"
            
            elif event.event_type == EventType.HEAL:
                # Rule 6: Must have heal charges
                role_data = actor.role_data or {}
                if role_data.get('heal_charges', 0) <= 0:
                    return False, "No heal charges remaining"
                return True, "Valid heal"
            
            elif event.event_type == EventType.PICKUP_ITEM:
                # Rule 7: Item must still exist (not picked up by another thread)
                # This would require checking items state - simplified for now
                return True, "Valid pickup"
        
        return False, "Unknown event type"
    
    def execute_event(self, event: GameEvent) -> bool:
        """
        Execute a validated event and update game state.
        Returns True if execution was successful.
        Runs in parallel with locks to ensure correctness.
        """
        actor = self.agent_states.get(event.actor_id)
        
        if event.event_type == EventType.ATTACK:
            target = self.agent_states.get(event.target_id)
            
            # Acquire both locks in consistent order to prevent deadlock
            # Always lock lower ID first
            first_lock = actor if actor.agent_id < target.agent_id else target
            second_lock = target if actor.agent_id < target.agent_id else actor
            
            with first_lock.lock:
                with second_lock.lock:
                    # Re-validate (state might have changed)
                    if not actor.is_alive or actor.has_acted_this_round:
                        return False
                    if not target.is_alive:
                        return False
                    
                    damage = event.data['damage']
                    missed = event.data.get('missed', False)
                    was_critical = event.data.get('was_critical', False)
                    
                    if missed:
                        print(f"  🧟 {actor.name} lunges at {target.name} but misses!")
                    else:
                        # Apply damage
                        target.health -= damage
                        target.damage_taken_this_round += damage
                        target.has_been_attacked_this_round = True
                        
                        if was_critical:
                            print(f"  ⚡ CRITICAL HIT!")
                        
                        emoji = "🔫" if actor.agent_type == 'Human' else "🧟"
                        print(f"  {emoji} {actor.name} attacks {target.name} for {damage} damage!")
                        
                        if target.health <= 0:
                            target.health = 0
                            target.is_alive = False
                            print(f"  💀 {target.name} has been defeated!")
                        
                        # Log combat
                        self.db.log_combat(
                            self.game_id, self.round_num,
                            actor.agent_id, target.agent_id,
                            damage, was_critical
                        )
                    
                    actor.has_acted_this_round = True
                    return True
        
        elif event.event_type == EventType.MOVE:
            with actor.lock:
                if not actor.is_alive or actor.has_acted_this_round:
                    return False
                
                actor.x = event.data['new_x']
                actor.y = event.data['new_y']
                actor.has_acted_this_round = True
                return True
        
        elif event.event_type == EventType.HEAL:
            with actor.lock:
                if not actor.is_alive or actor.has_acted_this_round:
                    return False
                
                heal_amount = event.data['heal_amount']
                actor.health = min(actor.health + heal_amount, actor.max_health)
                
                role_data = actor.role_data or {}
                role_data['heal_charges'] = role_data.get('heal_charges', 3) - 1
                actor.role_data = role_data
                
                print(f"  💚 {actor.name} heals for {heal_amount} HP!")
                actor.has_acted_this_round = True
                return True
        
        elif event.event_type == EventType.PICKUP_ITEM:
            with actor.lock:
                if not actor.is_alive or actor.has_acted_this_round:
                    return False
                
                item = event.data['item']
                self.assign_role_to_human(actor, item)
                self.db.pick_up_item(item['item_id'], actor.agent_id)
                
                actor.has_acted_this_round = True
                return True
        
        return False
    
    def assign_role_to_human(self, human: AgentState, item: Dict):
        """Assign role based on picked up item."""
        if item['item_type'] == 'MedKit':
            human.role_name = 'Doctor'
            human.role_data = {'heal_charges': 3, 'heal_amount': 0.5}
            print(f"  🥊 {human.name} becomes a Doctor!")
        elif item['item_type'] == 'Sword':
            human.role_name = 'Hunter'
            human.attack_power = int(human.base_attack_power * 1.5)
            human.role_data = {'attack_multiplier': 2.0, 'critical_chance': 0.3}
            print(f"  ⚔️ {human.name} becomes a Hunter!")
    
    def run_round(self):
        """Execute one round with validated parallel event generation and processing."""
        self.round_num += 1
        print(f"\n{'='*60}")
        print(f"ROUND {self.round_num}")
        print(f"{'='*60}")
        
        # Fetch all alive agents and items from database
        humans_data = self.db.get_alive_agents(self.game_id, 'Human')
        zombies_data = self.db.get_alive_agents(self.game_id, 'Zombie')
        items = self.db.get_available_items(self.game_id)
        
        # Initialize AgentState objects with locks
        self.agent_states = {}
        for h in humans_data:
            self.agent_states[h['agent_id']] = AgentState(h)
        for z in zombies_data:
            self.agent_states[z['agent_id']] = AgentState(z)
        
        # Create separate lists for thread safety
        humans = [self.agent_states[h['agent_id']] for h in humans_data]
        zombies = [self.agent_states[z['agent_id']] for z in zombies_data]
        
        game_state = {
            'humans': humans,
            'zombies': zombies,
            'items': items
        }
        
        # PHASE 1: Generate events in parallel
        print("\n[Phase 1: Event Generation]")
        self.pending_events = []
        
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            # Submit human event generation tasks
            human_futures = {
                executor.submit(self.generate_human_events, human, game_state): human.agent_id
                for human in humans
            }
            
            # Submit zombie event generation tasks
            zombie_futures = {
                executor.submit(self.generate_zombie_events, zombie, game_state): zombie.agent_id
                for zombie in zombies
            }
            
            # Collect human events
            for future in as_completed(human_futures):
                agent_id = human_futures[future]
                try:
                    events = future.result()
                    with self.state_lock:
                        self.pending_events.extend(events)
                except Exception as e:
                    print(f"Error generating events for human {agent_id}: {e}")
            
            # Collect zombie events
            for future in as_completed(zombie_futures):
                agent_id = zombie_futures[future]
                try:
                    events = future.result()
                    with self.state_lock:
                        self.pending_events.extend(events)
                except Exception as e:
                    print(f"Error generating events for zombie {agent_id}: {e}")
        
        print(f"Generated {len(self.pending_events)} events")
        
        # PHASE 2: Validate events in parallel
        print("\n[Phase 2: Event Validation]")
        self.valid_events = []
        self.invalid_events = []
        
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            validation_futures = {
                executor.submit(self.validate_event, event): event
                for event in self.pending_events
            }
            
            for future in as_completed(validation_futures):
                event = validation_futures[future]
                try:
                    is_valid, reason = future.result()
                    with self.state_lock:
                        if is_valid:
                            self.valid_events.append(event)
                        else:
                            self.invalid_events.append((event, reason))
                except Exception as e:
                    print(f"Error validating event: {e}")
        
        print(f"Valid: {len(self.valid_events)}, Invalid: {len(self.invalid_events)}")
        
        # Sort valid events by priority (higher priority first)
        self.valid_events.sort(key=lambda e: e.priority, reverse=True)
        
        # PHASE 3: Execute valid events in parallel (with re-validation)
        print("\n[Phase 3: Event Execution]")
        
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            execution_futures = {
                executor.submit(self.execute_event, event): event
                for event in self.valid_events
            }
            
            executed_count = 0
            for future in as_completed(execution_futures):
                event = execution_futures[future]
                try:
                    success = future.result()
                    if success:
                        executed_count += 1
                except Exception as e:
                    print(f"Error executing event: {e}")
        
        print(f"Executed {executed_count}/{len(self.valid_events)} events")
        
        # PHASE 4: Batch update database
        print("\n[Phase 4: Database Update]")
        import json
        updates = [
            (agent.health, agent.is_alive, agent.x, agent.y,
             agent.role_name, json.dumps(agent.role_data or {}), agent.agent_id)
            for agent in self.agent_states.values()
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
        print("ZOMBIE APOCALYPSE SIMULATION (VALIDATED MULTITHREADING)")
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

        snap_id = self.sm.capture_snapshot(
        self.game_id, 0, 'periodic', 'Initial game state'
        )
        self.snapshot_ids.append(snap_id)
        print(f"📸 Captured initial snapshot {snap_id}")
        
        # Run game loop
        while not self.is_game_over() and self.round_num < max_rounds:
            self.run_round()

            if self.round_num % self.snapshot_interval == 0:
                snap_id = self.sm.capture_snapshot(
                    self.game_id, self.round_num, 'periodic',
                    f'Round {self.round_num} checkpoint'
                )
                self.snapshot_ids.append(snap_id)
                print(f"📸 Captured snapshot {snap_id} at round {self.round_num}")

        snap_id = self.sm.capture_snapshot(
            self.game_id, self.round_num, 'event', 'Game ended'
        )
        self.snapshot_ids.append(snap_id)
        print(f"📸 Captured final snapshot {snap_id}")
        
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
        print(f"\n📸 Snapshot Analysis:")
        print(f"   Total snapshots captured: {len(self.snapshot_ids)}")
        dynamics = self.sm.analyze_game_dynamics(self.game_id)
        print(f"   Human survival rate: {dynamics['human_survival_rate']:.1f}%")
        print(f"   Zombie survival rate: {dynamics['zombie_survival_rate']:.1f}%")
        print(f"   Total combat events: {dynamics['total_combat_events']}")
        print(f"   Avg combat per round: {dynamics['avg_combat_per_round']:.2f}")
