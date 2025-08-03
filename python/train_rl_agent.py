"""
Example script for training an RL agent to play Magic: The Gathering using Forge.

This demonstrates how to use the ForgeEnv gym environment with popular RL libraries
like stable-baselines3 to train agents.

Usage:
1. Start Forge Java process with RL PlayerController
2. Run this script to train an agent
3. The agent will learn to play MTG through self-play or against existing AI
"""

import numpy as np
import argparse
import time
from typing import Optional
import os

# Uncomment these when dependencies are available:
# from stable_baselines3 import PPO, A2C, DQN
# from stable_baselines3.common.env_util import make_vec_env
# from stable_baselines3.common.callbacks import EvalCallback, StopTrainingOnRewardThreshold

from forge_rl_gym import ForgeEnv


class MockRLAgent:
    """Mock RL agent for demonstration when stable-baselines3 isn't available"""
    
    def __init__(self, env):
        self.env = env
        self.total_steps = 0
        
    def learn(self, total_timesteps: int):
        """Simulate learning by taking random actions"""
        print(f"Training mock agent for {total_timesteps} timesteps...")
        
        obs, info = self.env.reset()
        
        for step in range(total_timesteps):
            action = self.env.action_space.sample()
            obs, reward, terminated, truncated, info = self.env.step(action)
            
            self.total_steps += 1
            
            if terminated or truncated:
                print(f"Episode ended at step {step}, total steps: {self.total_steps}")
                obs, info = self.env.reset()
                
            if step % 1000 == 0:
                print(f"Training step {step}/{total_timesteps}")
        
        print("Training completed!")
    
    def save(self, path: str):
        print(f"Mock agent 'saved' to {path}")
    
    def load(self, path: str):
        print(f"Mock agent 'loaded' from {path}")


def create_training_environment(host: str = "localhost", port: int = 12345) -> ForgeEnv:
    """Create and configure the training environment"""
    env = ForgeEnv(
        state_size=1000,  # Size of game state vector
        action_size=10,   # Size of action vector
        host=host,
        port=port
    )
    return env


def train_ppo_agent(env: ForgeEnv, total_timesteps: int = 100000, model_name: str = "forge_ppo"):
    """Train a PPO agent (requires stable-baselines3)"""
    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.callbacks import EvalCallback
        
        print("Training PPO agent...")
        
        # Create PPO model
        model = PPO(
            "MlpPolicy",
            env,
            verbose=1,
            tensorboard_log="./tensorboard_logs/",
            learning_rate=3e-4,
            n_steps=2048,
            batch_size=64,
            n_epochs=10,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.2,
            clip_range_vf=None,
            ent_coef=0.01,
            vf_coef=0.5,
            max_grad_norm=0.5,
        )
        
        # Create evaluation callback
        eval_callback = EvalCallback(
            env,
            best_model_save_path="./models/",
            log_path="./logs/",
            eval_freq=10000,
            deterministic=True,
            render=False
        )
        
        # Train the model
        model.learn(total_timesteps=total_timesteps, callback=eval_callback)
        
        # Save the model
        model.save(f"./models/{model_name}")
        print(f"Model saved as {model_name}")
        
        return model
        
    except ImportError:
        print("stable-baselines3 not available, using mock agent")
        mock_agent = MockRLAgent(env)
        mock_agent.learn(total_timesteps)
        mock_agent.save(f"./models/{model_name}")
        return mock_agent


def train_dqn_agent(env: ForgeEnv, total_timesteps: int = 100000, model_name: str = "forge_dqn"):
    """Train a DQN agent (requires stable-baselines3 and discrete action space)"""
    try:
        from stable_baselines3 import DQN
        
        print("Training DQN agent...")
        print("Note: DQN requires discrete action space. Consider using PPO for continuous actions.")
        
        # For DQN, we'd need to modify the environment to have discrete actions
        # This is just a placeholder showing how it would be done
        
        model = DQN(
            "MlpPolicy",
            env,
            verbose=1,
            learning_rate=1e-4,
            buffer_size=1000000,
            learning_starts=50000,
            batch_size=32,
            tau=1.0,
            gamma=0.99,
            train_freq=4,
            gradient_steps=1,
            target_update_interval=10000,
            exploration_fraction=0.1,
            exploration_initial_eps=1.0,
            exploration_final_eps=0.05,
        )
        
        model.learn(total_timesteps=total_timesteps)
        model.save(f"./models/{model_name}")
        print(f"Model saved as {model_name}")
        
        return model
        
    except ImportError:
        print("stable-baselines3 not available, using mock agent")
        mock_agent = MockRLAgent(env)
        mock_agent.learn(total_timesteps)
        mock_agent.save(f"./models/{model_name}")
        return mock_agent


def evaluate_agent(agent, env: ForgeEnv, num_episodes: int = 10):
    """Evaluate a trained agent"""
    print(f"Evaluating agent for {num_episodes} episodes...")
    
    episode_rewards = []
    episode_lengths = []
    
    for episode in range(num_episodes):
        obs, info = env.reset()
        episode_reward = 0
        episode_length = 0
        
        while True:
            if hasattr(agent, 'predict'):
                action, _ = agent.predict(obs, deterministic=True)
            else:
                action = env.action_space.sample()  # Mock agent
                
            obs, reward, terminated, truncated, info = env.step(action)
            episode_reward += reward
            episode_length += 1
            
            if terminated or truncated:
                break
        
        episode_rewards.append(episode_reward)
        episode_lengths.append(episode_length)
        print(f"Episode {episode + 1}: Reward = {episode_reward:.2f}, Length = {episode_length}")
    
    avg_reward = np.mean(episode_rewards)
    avg_length = np.mean(episode_lengths)
    
    print(f"\nEvaluation Results:")
    print(f"Average Reward: {avg_reward:.2f} ± {np.std(episode_rewards):.2f}")
    print(f"Average Episode Length: {avg_length:.2f} ± {np.std(episode_lengths):.2f}")
    
    return avg_reward, avg_length


def main():
    parser = argparse.ArgumentParser(description="Train RL agent for Magic: The Gathering")
    parser.add_argument("--algorithm", choices=["ppo", "dqn"], default="ppo",
                        help="RL algorithm to use")
    parser.add_argument("--timesteps", type=int, default=100000,
                        help="Number of training timesteps")
    parser.add_argument("--host", default="localhost",
                        help="Forge server host")
    parser.add_argument("--port", type=int, default=12345,
                        help="Forge server port")
    parser.add_argument("--eval-episodes", type=int, default=10,
                        help="Number of episodes for evaluation")
    parser.add_argument("--model-name", default="forge_agent",
                        help="Name for saving the model")
    
    args = parser.parse_args()
    
    print("=== Forge RL Agent Training ===")
    print(f"Algorithm: {args.algorithm}")
    print(f"Timesteps: {args.timesteps}")
    print(f"Forge server: {args.host}:{args.port}")
    print()
    
    # Create directories
    os.makedirs("models", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("tensorboard_logs", exist_ok=True)
    
    # Create environment
    print("Creating environment...")
    env = create_training_environment(args.host, args.port)
    
    try:
        # Train agent
        if args.algorithm == "ppo":
            agent = train_ppo_agent(env, args.timesteps, args.model_name)
        elif args.algorithm == "dqn":
            agent = train_dqn_agent(env, args.timesteps, args.model_name)
        
        # Evaluate agent
        print("\nEvaluating trained agent...")
        evaluate_agent(agent, env, args.eval_episodes)
        
    except KeyboardInterrupt:
        print("\nTraining interrupted by user")
    except Exception as e:
        print(f"\nTraining failed: {e}")
    finally:
        print("Closing environment...")
        env.close()
    
    print("\nTraining session completed!")


def demo_training_setup():
    """Demonstrate the training setup without actually training"""
    print("=== Training Setup Demo ===")
    print()
    
    print("This script demonstrates how to train RL agents for MTG using Forge.")
    print()
    
    print("Prerequisites:")
    print("1. Java Forge process running with PlayerControllerRl")
    print("2. Python environment with gymnasium installed")
    print("3. Optionally: stable-baselines3 for real RL algorithms")
    print()
    
    print("Training process:")
    print("1. Create ForgeEnv that connects to Java process")
    print("2. Initialize RL algorithm (PPO, DQN, etc.)")
    print("3. Train agent through game episodes")
    print("4. Agent learns from rewards and game outcomes")
    print("5. Evaluate and save trained model")
    print()
    
    print("Example commands:")
    print("python train_rl_agent.py --algorithm ppo --timesteps 50000")
    print("python train_rl_agent.py --algorithm dqn --timesteps 100000")
    print()
    
    print("The agent will learn to:")
    print("- Make strategic card choices")
    print("- Decide when to attack and block")
    print("- Manage resources effectively")
    print("- Adapt to different opponents and game states")


if __name__ == "__main__":
    if len(os.sys.argv) == 1:
        # No arguments provided, show demo
        demo_training_setup()
    else:
        main()