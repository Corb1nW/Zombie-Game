from abc import ABC, abstractmethod
import random


class Agent(ABC):
    """Abstract base class for all agents in the game."""
    
    def __init__(self, name, health, attack_power):
        self.name = name
        self.health = health
        self.max_health = health
        self.attack_power = attack_power
        self.is_alive = True
    
    @abstractmethod
    def attack(self, target):
        """Attack another agent. Must be implemented by child classes."""
        pass
    
    def take_damage(self, damage):
        """Reduce health when taking damage."""
        self.health -= damage
        if self.health <= 0:
            self.health = 0
            self.is_alive = False
            print(f"{self.name} has been defeated!")
    
    def display_status(self):
        """Display the current status of the agent."""
        status = "ALIVE" if self.is_alive else "DEAD"
        print(f"{self.name} - Health: {self.health}/{self.max_health} - Status: {status}")


class Human(Agent):
    """Human agent that can attack zombies."""
    
    def __init__(self, name, health=100, attack_power=20):
        super().__init__(name, health, attack_power)
        self.agent_type = "Human"
    
    def attack(self, target):
        """Human attacks with weapon, dealing consistent damage."""
        if not self.is_alive:
            print(f"{self.name} is defeated and cannot attack!")
            return
        
        # Add some randomness to attack (70-100% of attack power)
        damage = random.randint(int(self.attack_power * 0.7), self.attack_power)
        print(f"{self.name} attacks {target.name} with a weapon for {damage} damage!")
        target.take_damage(damage)


class Zombie(Agent):
    """Zombie agent that can attack humans."""
    
    def __init__(self, name, health=80, attack_power=15):
        super().__init__(name, health, attack_power)
        self.agent_type = "Zombie"
    
    def attack(self, target):
        """Zombie attacks with bite, dealing damage with chance to miss."""
        if not self.is_alive:
            print(f"{self.name} is defeated and cannot attack!")
            return
        
        # Zombies have a 20% chance to miss
        if random.random() < 0.2:
            print(f"{self.name} lunges at {target.name} but misses!")
            return
        
        # Variable damage (50-100% of attack power)
        damage = random.randint(int(self.attack_power * 0.5), self.attack_power)
        print(f"{self.name} bites {target.name} for {damage} damage!")
        target.take_damage(damage)


class Game:
    """Main game class to manage combat between agents."""
    
    def __init__(self):
        self.agents = []
    
    def add_agent(self, agent):
        """Add an agent to the game."""
        self.agents.append(agent)
    
    def combat_round(self, attacker, defender):
        """Execute one round of combat."""
        print("\n" + "="*50)
        attacker.attack(defender)
        
        if defender.is_alive:
            defender.attack(attacker)
    
    def run_game(self, agent1, agent2):
        """Run the game until one agent is defeated."""
        print("="*50)
        print("GAME START: HUMAN VS ZOMBIE")
        print("="*50)
        
        agent1.display_status()
        agent2.display_status()
        
        round_num = 1
        while agent1.is_alive and agent2.is_alive:
            print(f"\n--- Round {round_num} ---")
            self.combat_round(agent1, agent2)
            round_num += 1
        
        print("\n" + "="*50)
        print("GAME OVER!")
        print("="*50)
        agent1.display_status()
        agent2.display_status()
        
        winner = agent1 if agent1.is_alive else agent2
        print(f"\n🎉 {winner.name} wins the battle!")


# Example usage
if __name__ == "__main__":
    # Create agents
    human = Human("Sarah the Survivor", health=100, attack_power=20)
    zombie = Zombie("Rotting Bob", health=80, attack_power=15)
    
    # Create and run game
    game = Game()
    game.add_agent(human)
    game.add_agent(zombie)
    game.run_game(human, zombie)
