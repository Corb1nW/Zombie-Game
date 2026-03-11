from abc import ABC, abstractmethod
import random
import math


class Item(ABC):
    """Abstract base class for all items in the game."""
    
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.picked_up = False
    
    @abstractmethod
    def get_description(self):
        """Get item description."""
        pass


class MedKit(Item):
    """MedKit item that transforms human into Doctor role."""
    
    def __init__(self, x, y):
        super().__init__(x, y)
        self.item_type = "MedKit"
    
    def get_description(self):
        return "MedKit (becomes Doctor)"


class Sword(Item):
    """Sword item that transforms human into Hunter role."""
    
    def __init__(self, x, y):
        super().__init__(x, y)
        self.item_type = "Sword"
    
    def get_description(self):
        return "Sword (becomes Hunter)"


class Role(ABC):
    """Abstract base class for agent roles using composition."""
    
    def __init__(self, agent):
        self.agent = agent
        self.role_name = "None"
    
    @abstractmethod
    def use_special_ability(self, game_state):
        """Use role-specific special ability."""
        pass
    
    @abstractmethod
    def get_attack_modifier(self):
        """Get attack damage modifier for this role."""
        pass
    
    def get_role_description(self):
        """Get description of the role."""
        return self.role_name


class Doctor(Role):
    """Doctor role - can heal self and has healing abilities."""
    
    def __init__(self, agent):
        super().__init__(agent)
        self.role_name = "Doctor"
        self.heal_charges = 3  # Can heal 3 times
        self.heal_amount = 0.5  # Heals 50% of max health
    
    def use_special_ability(self, game_state):
        """Doctor can heal themselves when health is low."""
        if self.heal_charges > 0 and self.agent.health < self.agent.max_health * 0.6:
            heal_amount = int(self.agent.max_health * self.heal_amount)
            old_health = self.agent.health
            self.agent.health = min(self.agent.health + heal_amount, self.agent.max_health)
            actual_heal = self.agent.health - old_health
            self.heal_charges -= 1
            print(f"  💚 Doctor {self.agent.name} heals for {actual_heal} HP! (Charges left: {self.heal_charges})")
            return True
        return False
    
    def get_attack_modifier(self):
        """Doctors have normal attack power."""
        return 1.0
    
    def get_role_description(self):
        return f"{self.role_name} (Heals: {self.heal_charges})"


class Hunter(Role):
    """Hunter role - has increased attack power and combat abilities."""
    
    def __init__(self, agent):
        super().__init__(agent)
        self.role_name = "Hunter"
        self.attack_multiplier = 2.0  # Double attack power
        self.critical_chance = 0.3  # 30% chance for critical hit
    
    def use_special_ability(self, game_state):
        """Hunter's special ability is passive (increased damage and crits)."""
        # Hunter abilities are passive, applied during attack
        return False
    
    def get_attack_modifier(self):
        """Hunters deal double damage, with chance for critical hit."""
        modifier = self.attack_multiplier
        if random.random() < self.critical_chance:
            print(f"  ⚡ CRITICAL HIT!")
            modifier *= 1.5  # Critical hits deal 3x damage total
        return modifier
    
    def get_role_description(self):
        return f"{self.role_name} (ATK x{self.attack_multiplier})"


class SpeedZombie(Role):
    """Speed Zombie role - moves faster but has reduced attack power."""
    
    def __init__(self, agent):
        super().__init__(agent)
        self.role_name = "Speed Zombie"
        self.attack_multiplier = 0.6  # 60% attack power
        self.movement_range = 2  # Can move 2 spaces per turn
    
    def use_special_ability(self, game_state):
        """Speed Zombie's special ability is passive (faster movement)."""
        # Speed abilities are passive, applied during movement
        return False
    
    def get_attack_modifier(self):
        """Speed Zombies deal reduced damage."""
        return self.attack_multiplier
    
    def get_movement_range(self):
        """Return how many spaces this zombie can move."""
        return self.movement_range
    
    def get_role_description(self):
        return f"{self.role_name} (Speed: {self.movement_range}, ATK: {int(self.attack_multiplier*100)}%)"


class TankZombie(Role):
    """Tank Zombie role - slower movement but much higher attack power."""
    
    def __init__(self, agent):
        super().__init__(agent)
        self.role_name = "Tank Zombie"
        self.attack_multiplier = 2.5  # 2.5x attack power
        self.movement_range = 0.5  # Moves slower (half speed)
    
    def use_special_ability(self, game_state):
        """Tank Zombie's special ability is passive (higher damage)."""
        # Tank abilities are passive, applied during attack
        return False
    
    def get_attack_modifier(self):
        """Tank Zombies deal massive damage."""
        return self.attack_multiplier
    
    def get_movement_range(self):
        """Return how many spaces this zombie can move."""
        return self.movement_range
    
    def get_role_description(self):
        return f"{self.role_name} (Speed: {self.movement_range}, ATK: {int(self.attack_multiplier*100)}%)"


class Agent(ABC):
    """Abstract base class for all agents in the game."""
    
    def __init__(self, name, health, attack_power, x, y):
        self.name = name
        self.health = health
        self.max_health = health
        self.attack_power = attack_power
        self.is_alive = True
        self.x = x
        self.y = y
        self.role = None  # Composition: agent HAS-A role
    
    @abstractmethod
    def attack(self, target):
        """Attack another agent. Must be implemented by child classes."""
        pass
    
    @abstractmethod
    def decide_action(self, game_state):
        """Decide what action to take this turn. Must be implemented by child classes."""
        pass
    
    def take_damage(self, damage):
        """Reduce health when taking damage."""
        self.health -= damage
        if self.health <= 0:
            self.health = 0
            self.is_alive = False
            print(f"  💀 {self.name} has been defeated!")
    
    def move(self, dx, dy, grid_size):
        """Move the agent on the grid."""
        new_x = max(0, min(grid_size - 1, self.x + dx))
        new_y = max(0, min(grid_size - 1, self.y + dy))
        self.x = new_x
        self.y = new_y
    
    def distance_to(self, other):
        """Calculate distance to another agent or item."""
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)
    
    def display_status(self):
        """Display the current status of the agent."""
        status = "ALIVE" if self.is_alive else "DEAD"
        role_info = f", Role: {self.role.get_role_description()}" if self.role else ""
        print(f"{self.name} - HP: {self.health}/{self.max_health}, ATK: {self.attack_power}, Pos: ({self.x},{self.y}){role_info} - {status}")


class Human(Agent):
    """Human agent that can attack zombies and pick up items to gain roles."""
    
    def __init__(self, name, health=100, attack_power=20, x=0, y=0):
        super().__init__(name, health, attack_power, x, y)
        self.agent_type = "Human"
        self.base_attack_power = attack_power
    
    def attack(self, target):
        """Human attacks with weapon, dealing damage modified by role."""
        if not self.is_alive:
            return False
        
        # Base damage calculation
        damage = random.randint(int(self.attack_power * 0.7), self.attack_power)
        
        # Apply role modifier if human has a role
        if self.role:
            damage = int(damage * self.role.get_attack_modifier())
        
        print(f"  🔫 {self.name} attacks {target.name} for {damage} damage!")
        target.take_damage(damage)
        return True
    
    def assign_role(self, item):
        """Assign a role to the human based on the item picked up."""
        if isinstance(item, MedKit):
            self.role = Doctor(self)
            print(f"  🏥 {self.name} becomes a Doctor!")
        elif isinstance(item, Sword):
            self.role = Hunter(self)
            self.attack_power = int(self.base_attack_power * 1.5)  # Base boost
            print(f"  ⚔️  {self.name} becomes a Hunter!")
        item.picked_up = True
    
    def pick_up_item(self, item):
        """Pick up an item and change role."""
        if self.role is None:  # Only pick up if no role yet
            self.assign_role(item)
            return True
        return False
    
    def decide_action(self, game_state):
        """Decide whether to move, attack, pick up item, or use special ability."""
        # Use role special ability if available
        if self.role:
            self.role.use_special_ability(game_state)
        
        # Look for items if no role yet
        if self.role is None and game_state['items']:
            nearest_item = min(game_state['items'], key=lambda item: self.distance_to(item))
            if self.distance_to(nearest_item) <= 1.5 and not nearest_item.picked_up:
                self.pick_up_item(nearest_item)
                return
        
        # Find nearest zombie
        alive_zombies = [z for z in game_state['zombies'] if z.is_alive]
        if alive_zombies:
            nearest_zombie = min(alive_zombies, key=lambda z: self.distance_to(z))
            distance = self.distance_to(nearest_zombie)
            
            # Attack if in range
            if distance <= 1.5:
                self.attack(nearest_zombie)
            else:
                # Move toward zombie
                dx = 1 if nearest_zombie.x > self.x else -1 if nearest_zombie.x < self.x else 0
                dy = 1 if nearest_zombie.y > self.y else -1 if nearest_zombie.y < self.y else 0
                self.move(dx, dy, game_state['grid_size'])


class Zombie(Agent):
    """Zombie agent that can attack humans."""
    
    def __init__(self, name, health=80, attack_power=15, x=0, y=0):
        super().__init__(name, health, attack_power, x, y)
        self.agent_type = "Zombie"
        self.base_attack_power = attack_power
    
    def assign_random_role(self):
        """Randomly assign a role to the zombie at spawn (25% Speed, 25% Tank, 50% None)."""
        roll = random.random()
        if roll < 0.25:
            self.role = SpeedZombie(self)
            print(f"  ⚡ {self.name} spawned as a Speed Zombie!")
        elif roll < 0.50:
            self.role = TankZombie(self)
            print(f"  🛡️  {self.name} spawned as a Tank Zombie!")
        # else: 50% chance of no role (stays None)
    
    def attack(self, target):
        """Zombie attacks with bite, dealing damage with chance to miss."""
        if not self.is_alive:
            return False
        
        if random.random() < 0.2:
            print(f"  🧟 {self.name} lunges at {target.name} but misses!")
            return False
        
        # Base damage calculation
        damage = random.randint(int(self.attack_power * 0.5), self.attack_power)
        
        # Apply role modifier if zombie has a role
        if self.role:
            damage = int(damage * self.role.get_attack_modifier())
        
        print(f"  🧟 {self.name} bites {target.name} for {damage} damage!")
        target.take_damage(damage)
        return True
    
    def decide_action(self, game_state):
        """Zombies move toward and attack nearest human."""
        # Find nearest human
        alive_humans = [h for h in game_state['humans'] if h.is_alive]
        if alive_humans:
            nearest_human = min(alive_humans, key=lambda h: self.distance_to(h))
            distance = self.distance_to(nearest_human)
            
            # Attack if in range
            if distance <= 1.5:
                self.attack(nearest_human)
            else:
                # Determine movement range based on role
                movement_range = 1  # Default movement
                if self.role and hasattr(self.role, 'get_movement_range'):
                    movement_range = self.role.get_movement_range()
                
                # Move toward human (potentially multiple steps for speed zombies)
                dx = 1 if nearest_human.x > self.x else -1 if nearest_human.x < self.x else 0
                dy = 1 if nearest_human.y > self.y else -1 if nearest_human.y < self.y else 0
                
                # For speed zombies, move multiple times
                if movement_range >= 1:
                    for _ in range(int(movement_range)):
                        self.move(dx, dy, game_state['grid_size'])
                else:
                    # For tank zombies with fractional movement, only move sometimes
                    if random.random() < movement_range:
                        self.move(dx, dy, game_state['grid_size'])


class Game:
    """Main game class to manage the simulation."""
    
    def __init__(self, grid_size=20):
        self.grid_size = grid_size
        self.humans = []
        self.zombies = []
        self.items = []
        self.round_num = 0
    
    def spawn_agents(self):
        """Spawn 5 humans and 5 zombies at random locations."""
        print("\n--- SPAWNING AGENTS ---")
        # Spawn humans
        for i in range(5):
            x = random.randint(0, self.grid_size // 2 - 1)
            y = random.randint(0, self.grid_size - 1)
            human = Human(f"Human_{i+1}", x=x, y=y)
            self.humans.append(human)
        
        # Spawn zombies on opposite side with random roles
        for i in range(5):
            x = random.randint(self.grid_size // 2, self.grid_size - 1)
            y = random.randint(0, self.grid_size - 1)
            zombie = Zombie(f"Zombie_{i+1}", x=x, y=y)
            zombie.assign_random_role()  # Randomly assign role at spawn
            self.zombies.append(zombie)
    
    def spawn_items(self):
        """Spawn 1 medkit and 1 sword at random locations."""
        medkit_x = random.randint(0, self.grid_size - 1)
        medkit_y = random.randint(0, self.grid_size - 1)
        self.items.append(MedKit(medkit_x, medkit_y))
        
        sword_x = random.randint(0, self.grid_size - 1)
        sword_y = random.randint(0, self.grid_size - 1)
        self.items.append(Sword(sword_x, sword_y))
        
        print(f"\n📍 MedKit spawned at ({medkit_x}, {medkit_y})")
        print(f"📍 Sword spawned at ({sword_x}, {sword_y})")
    
    def get_game_state(self):
        """Get current game state for agents to make decisions."""
        return {
            'humans': self.humans,
            'zombies': self.zombies,
            'items': [item for item in self.items if not item.picked_up],
            'grid_size': self.grid_size
        }
    
    def run_round(self):
        """Execute one round of the simulation."""
        self.round_num += 1
        print(f"\n{'='*60}")
        print(f"ROUND {self.round_num}")
        print(f"{'='*60}")
        
        game_state = self.get_game_state()
        
        # Humans take their turns
        for human in self.humans:
            if human.is_alive:
                human.decide_action(game_state)
        
        # Zombies take their turns
        for zombie in self.zombies:
            if zombie.is_alive:
                zombie.decide_action(game_state)
    
    def is_game_over(self):
        """Check if game is over."""
        humans_alive = sum(1 for h in self.humans if h.is_alive)
        zombies_alive = sum(1 for z in self.zombies if z.is_alive)
        return humans_alive == 0 or zombies_alive == 0
    
    def display_status(self):
        """Display status of all agents."""
        print("\n--- HUMANS ---")
        for human in self.humans:
            human.display_status()
        
        print("\n--- ZOMBIES ---")
        for zombie in self.zombies:
            zombie.display_status()
        
        humans_alive = sum(1 for h in self.humans if h.is_alive)
        zombies_alive = sum(1 for z in self.zombies if z.is_alive)
        print(f"\nAlive: {humans_alive} Humans, {zombies_alive} Zombies")
    
    def run_game(self, max_rounds=50):
        """Run the full game simulation."""
        print("="*60)
        print("ZOMBIE APOCALYPSE SIMULATION")
        print("="*60)
        print(f"Grid Size: {self.grid_size}x{self.grid_size}")
        
        self.spawn_agents()
        self.spawn_items()
        self.display_status()
        
        while not self.is_game_over() and self.round_num < max_rounds:
            self.run_round()
        
        print("\n" + "="*60)
        print("GAME OVER!")
        print("="*60)
        self.display_status()
        
        humans_alive = sum(1 for h in self.humans if h.is_alive)
        zombies_alive = sum(1 for z in self.zombies if z.is_alive)
        
        if humans_alive > zombies_alive:
            print("\n🎉 HUMANS WIN!")
        elif zombies_alive > humans_alive:
            print("\n🧟 ZOMBIES WIN!")
        else:
            print("\n⚔️ DRAW!")


# Example usage
if __name__ == "__main__":
    game = Game(grid_size=20)
    game.run_game(max_rounds=50)
