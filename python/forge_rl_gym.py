"""
Forge RL Gym Environment

This module provides a gym-compatible interface for training RL agents to play Magic: The Gathering
using the Forge simulator. It communicates with the Java Forge process via socket communication.

Key Components:
- ForgeEnv: The main gym environment
- GameStateProcessor: Converts JSON game states to numerical vectors
- ActionProcessor: Handles converting RL actions to Forge decisions
- ForgeClient: Manages communication with Java Forge process
"""

import gymnasium as gym
import numpy as np
import socket
import json
import threading
import queue
import time
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass


@dataclass
class ForgeDecisionRequest:
    """Represents a decision request from Forge"""
    decision_type: str
    game_state: Dict[str, Any]
    options: List[str]
    metadata: Dict[str, Any]
    min_choices: int
    max_choices: int


@dataclass 
class ForgeDecisionResponse:
    """Represents a decision response to Forge"""
    chosen_indices: List[int]
    additional_data: Dict[str, Any] = None
    
    def to_dict(self):
        return {
            "chosenIndices": self.chosen_indices,
            "additionalData": self.additional_data or {}
        }


class GameStateProcessor:
    """Processes game state from JSON to numerical vectors for NN input"""
    
    def __init__(self, state_size: int = 1000):
        self.state_size = state_size
        
    def process_game_state(self, game_state_json: Dict[str, Any]) -> np.ndarray:
        """
        Convert game state JSON to numerical vector.
        
        TODO: Implement full game state processing. This would include:
        - Player life totals, hand sizes, library sizes
        - Creatures in play (power/toughness/abilities encoded)
        - Mana available, cards in graveyard
        - Game phase, turn number
        - Spell abilities on the stack
        - etc.
        """
        # For now, return a zero vector as placeholder
        state_vector = np.zeros(self.state_size, dtype=np.float32)
        
        # Example: encode some basic info if available
        if game_state_json:
            # This would be expanded with real game state encoding
            state_vector[0] = 1.0  # Game active flag
            
        return state_vector


class ActionProcessor:
    """Processes RL agent actions into Forge-compatible decisions"""
    
    def __init__(self):
        pass
        
    def process_action(self, action: np.ndarray, request: ForgeDecisionRequest) -> ForgeDecisionResponse:
        """
        Convert RL agent action to Forge decision response.
        
        Args:
            action: Action from RL agent (could be discrete or continuous)
            request: The decision request from Forge
            
        Returns:
            ForgeDecisionResponse with chosen indices
        """
        if request.decision_type == "CHOOSE_CARDS_FROM_LIST":
            return self._process_card_selection(action, request)
        elif request.decision_type == "CHOOSE_BINARY":
            return self._process_binary_choice(action, request)
        elif request.decision_type == "CHOOSE_NUMBER":
            return self._process_number_choice(action, request)
        elif request.decision_type == "CHOOSE_OPTION_FROM_LIST":
            return self._process_option_choice(action, request)
        else:
            # Default: choose first option
            return ForgeDecisionResponse([0] if request.options else [])
    
    def _process_card_selection(self, action: np.ndarray, request: ForgeDecisionRequest) -> ForgeDecisionResponse:
        """Process card selection actions"""
        if len(request.options) == 0:
            return ForgeDecisionResponse([])
            
        # Convert action to card selection
        # This could be done various ways depending on action space design:
        # 1. Action is indices directly
        # 2. Action is probabilities over cards
        # 3. Action is learned card embeddings
        
        # For now, simple approach: action[0] selects which card
        if len(action) > 0:
            card_index = int(action[0]) % len(request.options)
            return ForgeDecisionResponse([card_index])
        else:
            return ForgeDecisionResponse([0])
    
    def _process_binary_choice(self, action: np.ndarray, request: ForgeDecisionRequest) -> ForgeDecisionResponse:
        """Process yes/no decisions"""
        if len(action) > 0:
            choice = 0 if action[0] < 0.5 else 1
        else:
            choice = 0
        return ForgeDecisionResponse([choice])
    
    def _process_number_choice(self, action: np.ndarray, request: ForgeDecisionRequest) -> ForgeDecisionResponse:
        """Process numeric choices"""
        if len(request.options) == 0:
            return ForgeDecisionResponse([0])
            
        if len(action) > 0:
            choice_index = int(action[0]) % len(request.options)
        else:
            choice_index = 0
        return ForgeDecisionResponse([choice_index])
    
    def _process_option_choice(self, action: np.ndarray, request: ForgeDecisionRequest) -> ForgeDecisionResponse:
        """Process categorical choices"""
        if len(request.options) == 0:
            return ForgeDecisionResponse([])
            
        if len(action) > 0:
            choice_index = int(action[0]) % len(request.options)
        else:
            choice_index = 0
        return ForgeDecisionResponse([choice_index])


class ForgeClient:
    """Manages socket communication with Java Forge process"""
    
    def __init__(self, host: str = "localhost", port: int = 12345):
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        self.request_queue = queue.Queue()
        self.response_queue = queue.Queue()
        
    def connect(self) -> bool:
        """Connect to Forge Java process"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            
            # Start background thread to handle messages
            self._start_message_handler()
            
            # Send hello message
            hello_msg = {"type": "hello", "message": "Python RL client connected"}
            self._send_message(hello_msg)
            
            return True
        except Exception as e:
            print(f"Failed to connect to Forge: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from Forge"""
        if self.connected and self.socket:
            goodbye_msg = {"type": "goodbye", "message": "Python RL client disconnecting"}
            self._send_message(goodbye_msg)
            self.socket.close()
            self.connected = False
    
    def wait_for_decision_request(self, timeout: float = 30.0) -> Optional[ForgeDecisionRequest]:
        """Wait for a decision request from Forge"""
        try:
            message = self.request_queue.get(timeout=timeout)
            return self._parse_decision_request(message)
        except queue.Empty:
            return None
    
    def send_decision_response(self, response: ForgeDecisionResponse):
        """Send decision response back to Forge"""
        response_msg = {
            "type": "decision_response",
            "success": True,
            "decision": response.to_dict()
        }
        self._send_message(response_msg)
    
    def _send_message(self, message: dict):
        """Send JSON message to Forge"""
        if self.socket:
            json_str = json.dumps(message)
            self.socket.sendall((json_str + "\n").encode())
    
    def _start_message_handler(self):
        """Start background thread to handle incoming messages"""
        def message_handler():
            buffer = ""
            while self.connected:
                try:
                    data = self.socket.recv(1024).decode()
                    if not data:
                        break
                        
                    buffer += data
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        if line.strip():
                            try:
                                message = json.loads(line)
                                if message.get("type") == "decision_request":
                                    self.request_queue.put(message)
                            except json.JSONDecodeError:
                                print(f"Invalid JSON received: {line}")
                                
                except Exception as e:
                    if self.connected:
                        print(f"Message handler error: {e}")
                    break
        
        thread = threading.Thread(target=message_handler, daemon=True)
        thread.start()
    
    def _parse_decision_request(self, message: dict) -> ForgeDecisionRequest:
        """Parse decision request message from Forge"""
        request_data = message.get("request", {})
        return ForgeDecisionRequest(
            decision_type=request_data.get("decisionType", ""),
            game_state=request_data.get("gameState", {}),
            options=request_data.get("options", []),
            metadata=request_data.get("metadata", {}),
            min_choices=request_data.get("minChoices", 1),
            max_choices=request_data.get("maxChoices", 1)
        )


class ForgeEnv(gym.Env):
    """
    Gymnasium environment for Magic: The Gathering using Forge simulator.
    
    This environment connects to a running Forge Java process and allows
    RL agents to play MTG by making high-level decisions.
    """
    
    def __init__(self, 
                 state_size: int = 1000,
                 action_size: int = 10,
                 host: str = "localhost", 
                 port: int = 12345):
        super().__init__()
        
        self.state_size = state_size
        self.action_size = action_size
        
        # Define observation and action spaces
        self.observation_space = gym.spaces.Box(
            low=-np.inf, high=np.inf, shape=(state_size,), dtype=np.float32
        )
        self.action_space = gym.spaces.Box(
            low=-1.0, high=1.0, shape=(action_size,), dtype=np.float32
        )
        
        # Components
        self.forge_client = ForgeClient(host, port)
        self.state_processor = GameStateProcessor(state_size)
        self.action_processor = ActionProcessor()
        
        self.current_state = None
        self.game_active = False
        
    def reset(self, seed=None, options=None):
        """Reset environment and start new game"""
        super().reset(seed=seed)
        
        if not self.forge_client.connected:
            if not self.forge_client.connect():
                raise ConnectionError("Could not connect to Forge")
        
        # TODO: Send game reset message to Forge
        # For now, just return initial state
        initial_state = np.zeros(self.state_size, dtype=np.float32)
        self.current_state = initial_state
        self.game_active = True
        
        return initial_state, {}
    
    def step(self, action):
        """Take one step in the environment"""
        if not self.game_active:
            raise RuntimeError("Game not active. Call reset() first.")
        
        # Wait for decision request from Forge
        request = self.forge_client.wait_for_decision_request()
        if request is None:
            # Timeout or game ended
            return self.current_state, 0.0, True, False, {}
        
        # Process action through RL agent
        response = self.action_processor.process_action(action, request)
        
        # Send response back to Forge
        self.forge_client.send_decision_response(response)
        
        # Update state
        new_state = self.state_processor.process_game_state(request.game_state)
        self.current_state = new_state
        
        # TODO: Calculate reward based on game state changes
        reward = 0.0
        
        # TODO: Detect game termination
        terminated = False
        truncated = False
        
        return new_state, reward, terminated, truncated, {}
    
    def close(self):
        """Clean up environment"""
        if self.forge_client.connected:
            self.forge_client.disconnect()


def demo_environment():
    """Demonstrate the Forge RL environment"""
    print("=== Forge RL Gym Environment Demo ===")
    print()
    
    # This would be used like any other gym environment:
    print("Example usage:")
    print("""
import forge_rl_gym

# Create environment
env = forge_rl_gym.ForgeEnv()

# Reset to start new game
obs, info = env.reset()

# Take actions
for step in range(1000):
    action = env.action_space.sample()  # Random action
    obs, reward, terminated, truncated, info = env.step(action)
    
    if terminated or truncated:
        obs, info = env.reset()

env.close()
    """)
    
    print("Key features:")
    print("- Standard gym interface for RL training")
    print("- Communicates with Forge Java process via sockets")
    print("- Abstracts MTG decisions into learnable actions")
    print("- Handles game state conversion to numerical vectors")
    print("- Can be used with any RL framework (stable-baselines3, Ray RLlib, etc.)")


if __name__ == "__main__":
    demo_environment()