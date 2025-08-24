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
import subprocess
import os
import signal
import atexit
from datetime import datetime
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
        elif request.decision_type == "PLAY_SPELL_OR_ABILITY":
            return self._process_spell_choice(action, request)
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
    
    def _process_spell_choice(self, action: np.ndarray, request: ForgeDecisionRequest) -> ForgeDecisionResponse:
        """Process spell/ability selection - this is where RL agents will learn strategy"""
        if len(request.options) == 0:
            return ForgeDecisionResponse([0])  # Pass if no options
        
        print(f"RL Agent deciding from {len(request.options)} options:")
        for i, option in enumerate(request.options):
            print(f"  {i}: {option}")
        
        # For demonstration: Use action to choose, but add some logic
        if len(action) > 0:
            # Use the action value to make a weighted choice
            # action[0] is between -1 and 1, convert to choice index
            normalized_action = (action[0] + 1) / 2  # Convert to 0-1 range
            choice_index = int(normalized_action * len(request.options))
            choice_index = min(choice_index, len(request.options) - 1)
        else:
            choice_index = 0
        
        print(f"RL Agent selected option {choice_index}: {request.options[choice_index]}")
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
    
    def wait_for_decision_request(self, timeout: float = 10.0) -> Optional[ForgeDecisionRequest]:
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
        print(f"Python: Sending response: {response_msg}")
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
                            print(f"Python: Received message: {line.strip()}")
                            try:
                                message = json.loads(line)
                                if message.get("type") == "decision_request":
                                    print(f"Python: Parsed decision request, putting in queue")
                                    self.request_queue.put(message)
                                else:
                                    print(f"Python: Received non-decision message: {message.get('type')}")
                            except json.JSONDecodeError:
                                print(f"Python: Invalid JSON received: {line}")
                                
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
    
    This environment automatically starts a Forge Java process when reset() is called
    and allows RL agents to play MTG by making high-level decisions.
    """
    
    def __init__(self, 
                 state_size: int = 1000,
                 action_size: int = 10,
                 host: str = "localhost", 
                 port: int = 12345,
                 forge_root: str = None,
                 deck1: str = "wr",
                 deck2: str = "gb",
                 auto_start_forge: bool = True):
        super().__init__()
        
        self.state_size = state_size
        self.action_size = action_size
        self.host = host
        self.port = port
        self.auto_start_forge = auto_start_forge
        self.deck1 = deck1
        self.deck2 = deck2
        
        # Auto-detect forge root if not provided
        if forge_root is None:
            # Assume we're in the python/ subdirectory of forge-ai
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.forge_root = os.path.dirname(current_dir)
        else:
            self.forge_root = forge_root
            
        # Verify forge root exists
        run_script = os.path.join(self.forge_root, "run-forge-headless.sh")
        if not os.path.exists(run_script):
            raise FileNotFoundError(f"Forge run script not found at {run_script}. Please specify correct forge_root.")
        
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
        self.forge_process = None
        self.log_file = None
        self.log_thread = None
        
        # Create logs directory
        self.logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Register cleanup on exit
        atexit.register(self._cleanup)
        
    def reset(self, seed=None, options=None):
        """Reset environment and start new game"""
        super().reset(seed=seed)
        
        # Stop any existing forge process
        self._stop_forge()
        
        # Start new forge process if auto_start_forge is enabled
        if self.auto_start_forge:
            self._start_forge()
            
        # Connect to forge
        max_retries = 10
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            if self.forge_client.connect():
                break
            print(f"Connection attempt {attempt + 1}/{max_retries} failed, retrying in {retry_delay}s...")
            time.sleep(retry_delay)
        else:
            raise ConnectionError(f"Could not connect to Forge after {max_retries} attempts")
        
        print("Successfully connected to Forge!")
        
        # Initialize game state
        initial_state = np.zeros(self.state_size, dtype=np.float32)
        initial_state[0] = 1.0  # Game active flag
        self.current_state = initial_state
        self.game_active = True
        
        # Process any immediate decision requests that might come during game startup
        print("Python: Checking for any startup decision requests...")
        startup_request = self.forge_client.wait_for_decision_request(timeout=2.0)
        if startup_request:
            print(f"Python: Handling startup decision: {startup_request.decision_type}")
            # Handle the startup decision with a default action
            default_action = np.array([0.0] * self.action_size)
            response = self.action_processor.process_action(default_action, startup_request)
            self.forge_client.send_decision_response(response)
        
        return initial_state, {}
    
    def step(self, action):
        """Take one step in the environment"""
        if not self.game_active:
            raise RuntimeError("Game not active. Call reset() first.")
        
        # Wait for decision request from Forge
        print("Python: Waiting for decision request from Forge...")
        request = self.forge_client.wait_for_decision_request()
        if request is None:
            print("Python: Didn't get decision request (timeout)")
            # Timeout or game ended
            return self.current_state, 0.0, True, False, {}
        
        print(f"Python: Received decision request: {request.decision_type} with {len(request.options)} options")
        
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

        print('step')
        
        return new_state, reward, terminated, truncated, {}
    
    def close(self):
        """Clean up environment"""
        self._cleanup()
    
    def _start_forge(self):
        """Start Forge headless process with RL agent"""
        print("Starting Forge headless process...")
        
        # Create timestamped log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"forge_output_{timestamp}.log"
        log_path = os.path.join(self.logs_dir, log_filename)
        
        run_script = os.path.join(self.forge_root, "run-forge-headless.sh")
        cmd = [
            run_script,
            "sim", 
            "-ai", "rl",
            "-d", self.deck1, self.deck2,
            "-n", "1",  # Large number so game doesn't end quickly during training
            # "-q"  # Quiet mode
        ]
        
        try:
            # Open log file
            self.log_file = open(log_path, 'w', buffering=1)  # Line buffered
            print(f"Logging Forge output to: {log_path}")
            
            # Start the process
            self.forge_process = subprocess.Popen(
                cmd,
                cwd=self.forge_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                preexec_fn=os.setsid,  # Create new process group for clean shutdown
                text=True,
                bufsize=1  # Line buffered
            )
            
            print(f"Started Forge process with PID {self.forge_process.pid}")
            
            # Start logging thread
            self._start_logging_thread()
            
            # Give Forge time to initialize
            time.sleep(5)
            
            # Check if process is still running
            if self.forge_process.poll() is not None:
                print("Forge process exited early, checking logs...")
                self._flush_remaining_output()
                raise RuntimeError(f"Forge process exited early. Check log file: {log_path}")
                
        except Exception as e:
            print(f"Failed to start Forge: {e}")
            if self.log_file:
                self.log_file.close()
                self.log_file = None
            raise
    
    def _start_logging_thread(self):
        """Start background thread to capture and log Forge output"""
        def log_output():
            try:
                while self.forge_process and self.forge_process.poll() is None:
                    line = self.forge_process.stdout.readline()
                    if line:
                        # Write to log file with timestamp
                        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        log_line = f"[{timestamp}] {line}"
                        self.log_file.write(log_line)
                        self.log_file.flush()
                        
                        # Also print important messages to console
                        if any(keyword in line for keyword in [
                            "RL Bridge server started", 
                            "Python RL client connected",
                            "RL Agent chose to play",
                            "Successfully connected to Forge",
                            "Using Reinforcement Learning AI agent",
                            "ERROR", "Exception", "Failed"
                        ]):
                            print(f"Forge: {line.strip()}")
                    else:
                        time.sleep(0.1)
                        
                # Flush any remaining output when process ends
                self._flush_remaining_output()
                        
            except Exception as e:
                print(f"Error in logging thread: {e}")
            
        self.log_thread = threading.Thread(target=log_output, daemon=True)
        self.log_thread.start()
    
    def _flush_remaining_output(self):
        """Flush any remaining output from the process"""
        if self.forge_process and self.log_file:
            try:
                # Read any remaining output
                remaining_output = self.forge_process.stdout.read()
                if remaining_output:
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    log_lines = remaining_output.split('\n')
                    for line in log_lines:
                        if line.strip():
                            self.log_file.write(f"[{timestamp}] {line}\n")
                    self.log_file.flush()
            except Exception as e:
                print(f"Error flushing output: {e}")

    def _stop_forge(self):
        """Stop Forge process if running"""
        if self.forge_process and self.forge_process.poll() is None:
            print(f"Stopping Forge process {self.forge_process.pid}...")
            try:
                # First, disconnect the client
                if self.forge_client.connected:
                    self.forge_client.disconnect()
                
                # Flush any remaining output
                self._flush_remaining_output()
                
                # Kill the entire process group to clean up all child processes
                os.killpg(os.getpgid(self.forge_process.pid), signal.SIGTERM)
                
                # Wait for process to terminate
                try:
                    self.forge_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print("Forge process didn't terminate gracefully, forcing kill...")
                    os.killpg(os.getpgid(self.forge_process.pid), signal.SIGKILL)
                    self.forge_process.wait()
                    
                print("Forge process stopped")
            except Exception as e:
                print(f"Error stopping Forge process: {e}")
            finally:
                self.forge_process = None
    
    def _cleanup(self):
        """Clean up all resources"""
        if self.forge_client.connected:
            self.forge_client.disconnect()
        self._stop_forge()
        
        # Close log file
        if self.log_file:
            self.log_file.close()
            self.log_file = None


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
