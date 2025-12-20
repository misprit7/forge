#!/usr/bin/env python3
"""
Interactive MTG player using the Forge gym environment.

Instead of training an AI, this script allows a human to make decisions
by stepping through the game manually. Useful for testing the environment
and understanding the decision flow.
"""

import argparse
import signal
import sys
import json
from typing import Optional
import numpy as np

from forge_rl_gym import ForgeEnv, Colors

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print(f"\n{Colors.RED}Received interrupt signal. Cleaning up...{Colors.RESET}")
    sys.exit(0)

def print_game_state(obs, info):
    """Print the current game state in a readable format"""
    print(f"\n{Colors.BLUE}=== GAME STATE ==={Colors.RESET}")
    print(f"Observation vector shape: {obs.shape}")
    print(f"Observation sample (first 10 values): {obs[:10]}")
    
    # Check if there's any meaningful state info
    non_zero_indices = np.nonzero(obs)[0]
    if len(non_zero_indices) > 0:
        print(f"Non-zero values at indices: {non_zero_indices[:10]}")  # Show first 10
        print(f"Non-zero values: {obs[non_zero_indices[:10]]}")
    else:
        print("All observation values are zero (placeholder state)")
    
    if info:
        print(f"Info: {info}")
    print(f"{Colors.BLUE}=================={Colors.RESET}")

def get_user_action(action_space):
    """Get action from user input"""
    print(f"\n{Colors.GREEN}Your turn! Please choose an action:{Colors.RESET}")
    print(f"Action space: {action_space}")
    print(f"Action space shape: {action_space.shape}")
    print(f"Action range: [{action_space.low[0]:.2f}, {action_space.high[0]:.2f}]")
    
    print(f"\nOptions:")
    print(f"1. Enter {action_space.shape[0]} numbers between {action_space.low[0]:.2f} and {action_space.high[0]:.2f}")
    print(f"2. Type 'random' for random action")
    print(f"3. Type 'zero' for zero action")
    print(f"4. Type 'quit' to exit")
    
    while True:
        try:
            user_input = input(f"\n{Colors.GREEN}> {Colors.RESET}").strip().lower()
            
            if user_input == 'quit':
                return None
            elif user_input == 'random':
                action = action_space.sample()
                print(f"Random action: {action}")
                return action
            elif user_input == 'zero':
                action = np.zeros(action_space.shape, dtype=np.float32)
                print(f"Zero action: {action}")
                return action
            else:
                # Try to parse as numbers
                parts = user_input.replace(',', ' ').split()
                if len(parts) != action_space.shape[0]:
                    print(f"{Colors.RED}Error: Need exactly {action_space.shape[0]} numbers{Colors.RESET}")
                    continue
                
                values = [float(x) for x in parts]
                action = np.array(values, dtype=np.float32)
                
                # Clip to valid range
                action = np.clip(action, action_space.low, action_space.high)
                print(f"Your action (clipped to valid range): {action}")
                return action
                
        except ValueError as e:
            print(f"{Colors.RED}Error parsing input: {e}{Colors.RESET}")
            print("Please try again or type 'help' for options.")
        except KeyboardInterrupt:
            return None

def interactive_session(env: ForgeEnv, max_steps: int = 100):
    """Run an interactive session with the environment"""
    print(f"\n{Colors.YELLOW}=== Starting Interactive MTG Session ==={Colors.RESET}")
    print(f"You'll be prompted to make decisions as they come up in the game.")
    print(f"The session will run for up to {max_steps} steps or until the game ends.")
    print(f"Press Ctrl+C at any time to quit.")
    
    try:
        # Reset environment to start new game
        print(f"\n{Colors.BLUE}Resetting environment and starting new game...{Colors.RESET}")
        obs, info = env.reset()
        
        step_count = 0
        total_reward = 0.0
        
        print_game_state(obs, info)
        
        for step in range(max_steps):
            print(f"\n{Colors.YELLOW}=== STEP {step + 1}/{max_steps} ==={Colors.RESET}")
            
            # Get action from user
            action = get_user_action(env.action_space)
            if action is None:
                print(f"{Colors.RED}User quit{Colors.RESET}")
                break
            
            # Take step in environment
            print(f"\n{Colors.BLUE}Taking action in environment...{Colors.RESET}")
            obs, reward, terminated, truncated, info = env.step(action)
            
            step_count += 1
            total_reward += reward
            
            # Show results
            print(f"\n{Colors.GREEN}Step Results:{Colors.RESET}")
            print(f"  Reward: {reward}")
            print(f"  Total reward: {total_reward:.2f}")
            print(f"  Terminated: {terminated}")
            print(f"  Truncated: {truncated}")
            
            print_game_state(obs, info)
            
            if terminated or truncated:
                print(f"\n{Colors.YELLOW}Game ended!{Colors.RESET}")
                if terminated:
                    print("  Reason: Game completed normally")
                if truncated:
                    print("  Reason: Game truncated (timeout or other limit)")
                break
        
        print(f"\n{Colors.GREEN}=== Session Complete ==={Colors.RESET}")
        print(f"Total steps: {step_count}")
        print(f"Final reward: {total_reward:.2f}")
        
        # Ask if user wants another game
        if step_count < max_steps:
            play_again = input(f"\n{Colors.GREEN}Play another game? (y/n): {Colors.RESET}").strip().lower()
            if play_again.startswith('y'):
                return interactive_session(env, max_steps)
        
    except KeyboardInterrupt:
        print(f"\n{Colors.RED}Session interrupted by user{Colors.RESET}")
    except Exception as e:
        print(f"\n{Colors.RED}Error during session: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()

def main():
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    parser = argparse.ArgumentParser(description="Interactive MTG player using Forge")
    parser.add_argument("--host", default="localhost",
                        help="Forge server host")
    parser.add_argument("--port", type=int, default=12345,
                        help="Forge server port")
    parser.add_argument("--deck1", default="ai-test-1",
                        help="First deck to use")
    parser.add_argument("--deck2", default="ai-test-1", 
                        help="Second deck to use")
    parser.add_argument("--max-steps", type=int, default=100,
                        help="Maximum steps per game session")
    parser.add_argument("--connection-timeout", type=int, default=30,
                        help="Timeout for connecting to Forge (seconds)")
    
    args = parser.parse_args()
    
    print(f"{Colors.YELLOW}=== Interactive Forge MTG Player ==={Colors.RESET}")
    print(f"Host: {args.host}:{args.port}")
    print(f"Decks: {args.deck1} vs {args.deck2}")
    print(f"Max steps per game: {args.max_steps}")
    print(f"Connection timeout: {args.connection_timeout}s")
    print(f"Press Ctrl+C at any time to quit")
    
    env = None
    try:
        # Create environment
        print(f"\n{Colors.BLUE}Creating environment (this will auto-start Forge)...{Colors.RESET}")
        env = ForgeEnv(
            state_size=1000,
            action_size=10,
            host=args.host,
            port=args.port,
            deck1=args.deck1,
            deck2=args.deck2,
            auto_start_forge=True
        )
        
        # Show log file location
        if hasattr(env, 'logs_dir'):
            print(f"Forge output logged to: {env.logs_dir}")
        
        print(f"Waiting up to {args.connection_timeout} seconds for Forge to start...")
        
        # Run interactive session
        interactive_session(env, args.max_steps)
        
    except KeyboardInterrupt:
        print(f"\n{Colors.RED}Interrupted by user{Colors.RESET}")
    except ConnectionError as e:
        print(f"\n{Colors.RED}Connection failed: {e}{Colors.RESET}")
        print("Troubleshooting tips:")
        print("1. Check if Java is installed and in PATH")
        print("2. Verify run-forge.sh script exists and is executable")
        print("3. Check the forge log files for errors")
        if env and hasattr(env, 'logs_dir'):
            print(f"   Log directory: {env.logs_dir}")
        print("4. Try running Forge manually first to test the setup")
    except Exception as e:
        print(f"\n{Colors.RED}Session failed: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
    finally:
        if env:
            print(f"\n{Colors.BLUE}Closing environment...{Colors.RESET}")
            try:
                env.close()
            except Exception as e:
                print(f"{Colors.RED}Error closing environment: {e}{Colors.RESET}")
    
    print(f"\n{Colors.GREEN}Interactive session completed!{Colors.RESET}")

if __name__ == "__main__":
    main()