"""
Integration wrapper for running games with automatic snapshot capturing.
"""
from snapshot_manager import SnapshotManager
from zombie_game_validated import GameDBValidated


class GameWithSnapshots(GameDBValidated):
    """Extended game class that automatically captures snapshots."""
    
    def __init__(self, db, grid_size=20, num_threads=4, snapshot_interval=10):
        """
        Initialize game with snapshot capability.
        
        Args:
            db: DatabaseManager instance
            grid_size: Size of the game grid
            num_threads: Number of threads for event processing
            snapshot_interval: Capture snapshot every N rounds
        """
        super().__init__(db, grid_size, num_threads)
        self.snapshot_manager = SnapshotManager(db)
        self.snapshot_interval = snapshot_interval
        self.snapshot_ids = []
    
    def run_game_with_snapshots(self, num_humans, num_zombies, max_rounds):
        """
        Run game and capture snapshots at regular intervals.
        
        Returns:
            snapshot_ids: List of captured snapshot IDs
        """
        # Initialize game
        self.setup_game(num_humans, num_zombies)
        
        # Capture initial snapshot
        snap_id = self.snapshot_manager.capture_snapshot(
            self.game_id, 0, 'periodic', 'Initial game state'
        )
        self.snapshot_ids.append(snap_id)
        print(f"📸 Captured initial snapshot {snap_id}")
        
        # Run game with periodic snapshots
        for round_num in range(1, max_rounds + 1):
            self.simulate_round()
            
            # Capture snapshot at intervals
            if round_num % self.snapshot_interval == 0:
                snap_id = self.snapshot_manager.capture_snapshot(
                    self.game_id, round_num, 'periodic', 
                    f'Round {round_num} snapshot'
                )
                self.snapshot_ids.append(snap_id)
                print(f"📸 Captured snapshot {snap_id} at round {round_num}")
            
            # Check win condition
            alive_humans = len([a for a in self.humans if a.is_alive])
            alive_zombies = len([z for z in self.zombies if z.is_alive])
            
            if alive_humans == 0 or alive_zombies == 0:
                # Capture final snapshot
                snap_id = self.snapshot_manager.capture_snapshot(
                    self.game_id, round_num, 'event', 
                    f'Game ended - {"Humans" if alive_zombies == 0 else "Zombies"} won'
                )
                self.snapshot_ids.append(snap_id)
                print(f"📸 Captured final snapshot {snap_id}")
                break
        
        return self.snapshot_ids
    
    def capture_event_snapshot(self, round_num, event_description):
        """
        Manually capture a snapshot for a specific event.
        
        Args:
            round_num: Current round number
            event_description: Description of the event
        """
        snap_id = self.snapshot_manager.capture_snapshot(
            self.game_id, round_num, 'event', event_description
        )
        self.snapshot_ids.append(snap_id)
        print(f"📸 Captured event snapshot {snap_id}: {event_description}")
        return snap_id
