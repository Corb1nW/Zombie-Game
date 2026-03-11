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
    def use(self, agent):
        """Use the item. Must be implemented by child classes."""
        pass
    
    @abstractmethod
    def get_description(self):
        """Get item description."""
        pass


class MedKit(Item):
    """MedKit item that restores 50% of max health."""
    
    def __init__(self, x, y):
        super().__init__(x, y)
        self.item_type = "MedKit"
    
    def use(self, agent):
        """Heal the agent by 50% of max health."""
        heal_amount = int(agent.max_health * 0.5)
        old_health = agent.health
        agent.health = min(agent.health + heal_amount, agent.max_health)
        actual_heal = agent.health - old_health
        print(f"  💚 {agent.name} used MedKit and restored {actual_heal} health!")
        return True
    
    def get_description(self):
        return "MedKit (+50% health)"


class Sword(Item):
    """Sword item that permanently increases attack power by 100%."""
    
    def __init__(self, x, y):
        super().__init__(x, y)
        self.item_type = "Sword"
    
    def use(self, agent):
        """Double the agent's attack power permanently."""
        old_attack = agent.attack_power
        agent.attack_power *= 2
        print(f"  ⚔️  {agent.name} picked up a Sword! Attack power increased from {old_attack} to {agent.attack_power}!")
        return True
    
    def get_description(self):
        return "Sword (+100% attack power)"


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
        self.inventory = []
    
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
        items = f", Items: {len(self.inventory)}" if self.inventory else ""
        print(f"{self.name} - HP: {self.health}/{self.max_health}, ATK: {self.attack_power}, Pos: ({self.x},{self.y}){items} - {status}")


class Human(Agent):
    """Human agent that can attack zombies and pick up items."""
    
    def __init__(self, name, health=100, attack_power=20, x=0, y=0):
        super().__init__(name, health, attack_power, x, y)
        self.agent_type = "Human"
    
    def attack(self, target):
        """Human attacks with weapon, dealing consistent damage."""
        if not self.is_alive:
            return False
        
        damage = random.randint(int(self.attack_power * 0.7), self.attack_power)
        print(f"  🔫 {self.name} attacks {target.name} for {damage} damage!")
        target.take_damage(damage)
        return True
    
    def pick_up_item(self, item):
        """Pick up an item from the ground."""
        if isinstance(item, Sword):
            # Sword is used immediately (permanent boost)
            item.use(self)
            item.picked_up = True
        elif isinstance(item, MedKit):
            # MedKit goes into inventory
            self.inventory.append(item)
            item.picked_up = True
            print(f"  📦 {self.name} picked up a {item.get_description()}")
    
    def use_medkit(self):
        """Use a medkit from inventory if available and needed."""
        if self.inventory and self.health < self.max_health * 0.6:
            medkit = self.inventory.pop(0)
            medkit.use(self)
            return True
        return False
    
    def decide_action(self, game_state):
        """Decide whether to move, attack, pick up item, or use medkit."""
        # Use medkit if health is low
        if self.health < self.max_health * 0.5 and self.inventory:
            self.use_medkit()
        
        # Look for nearby items if not at full power
        if game_state['items']:
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
    
    def attack(self, target):
        """Zombie attacks with bite, dealing damage with chance to miss."""
        if not self.is_alive:
            return False
        
        if random.random() < 0.2:
            print(f"  🧟 {self.name} lunges at {target.name} but misses!")
            return False
        
        damage = random.randint(int(self.attack_power * 0.5), self.attack_power)
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
                # Move toward human
                dx = 1 if nearest_human.x > self.x else -1 if nearest_human.x < self.x else 0
                dy = 1 if nearest_human.y > self.y else -1 if nearest_human.y < self.y else 0
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
        # Spawn humans
        for i in range(5):
            x = random.randint(0, self.grid_size // 2 - 1)
            y = random.randint(0, self.grid_size - 1)
            human = Human(f"Human_{i+1}", x=x, y=y)
            self.humans.append(human)
        
        # Spawn zombies on opposite side
        for i in range(5):
            x = random.randint(self.grid_size // 2, self.grid_size - 1)
            y = random.randint(0, self.grid_size - 1)
            zombie = Zombie(f"Zombie_{i+1}", x=x, y=y)
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
