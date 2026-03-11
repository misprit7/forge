# ---
# jupyter:
#   jupytext:
#     formats: ipynb,.notebook.py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.18.1
#   kernelspec:
#     display_name: .venv
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Forge Gym — Training with PPO
#
# Uses Stable-Baselines3 PPO to learn the play/draw decision.
# The agent should learn that going first (action=0) is better.
#
# Stats tracked in TensorBoard:
# - Win rate (rolling)
# - Mean reward
# - % of time agent chooses "play" (go first)
# - Mean game length (turns)

# %%
from collections import deque

import numpy as np
from forge_env import ForgeMTGEnv
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback

# %% [markdown]
# ## Custom callback for game stats


# %%
class ForgeStatsCallback(BaseCallback):
    """Logs game-specific stats to TensorBoard."""

    def __init__(self, window: int = 100, verbose: int = 0):
        super().__init__(verbose)
        self.window = window
        self.wins = deque(maxlen=window)
        self.rewards = deque(maxlen=window)
        self.actions = deque(maxlen=window)
        self.turns = deque(maxlen=window)
        self.total_games = 0

    def _on_step(self) -> bool:
        for i, done in enumerate(self.locals["dones"]):
            if done:
                info = self.locals["infos"][i]
                reward = self.locals["rewards"][i]
                action = info.get("action", -1)

                self.wins.append(1.0 if reward > 0 else 0.0)
                self.rewards.append(reward)
                self.actions.append(action)
                self.turns.append(info.get("turns", 0))
                self.total_games += 1

                if self.total_games % 25 == 0:
                    win_rate = np.mean(self.wins)
                    play_rate = np.mean([1.0 if a == 0 else 0.0 for a in self.actions])
                    mean_reward = np.mean(self.rewards)
                    mean_turns = np.mean(self.turns)

                    self.logger.record("forge/win_rate", win_rate)
                    self.logger.record("forge/mean_reward", mean_reward)
                    self.logger.record("forge/play_rate", play_rate)
                    self.logger.record("forge/mean_turns", mean_turns)
                    self.logger.record("forge/total_games", self.total_games)

                    if self.verbose:
                        print(
                            f"Games: {self.total_games:5d} | "
                            f"Win: {win_rate:.1%} | "
                            f"Play: {play_rate:.1%} | "
                            f"Reward: {mean_reward:+.2f} | "
                            f"Turns: {mean_turns:.0f}"
                        )
        return True


# %% [markdown]
# ## Create environment and train

# %%
env = ForgeMTGEnv(decks=["gb", "gb"])

model = PPO(
    "MlpPolicy",
    env,
    verbose=1,
    tensorboard_log="./tb_logs",
    device="cpu",
    n_steps=64,        # games per policy update
    batch_size=64,
    n_epochs=10,       # more passes over each batch to extract signal
    learning_rate=1e-3,  # high LR — this is a simple bandit problem
    gamma=0.0,         # single-step episodes, no discounting needed
    ent_coef=0.05,     # encourage exploration early on
    clip_range=0.3,    # wider clip for faster policy shifts
)

# %%
callback = ForgeStatsCallback(window=100, verbose=1)
model.learn(total_timesteps=1000, callback=callback)

# %% [markdown]
# ## Results
#
# Check TensorBoard for detailed graphs:
# ```bash
# cd forge-gym/notebooks
# tensorboard --logdir tb_logs
# ```

# %%
# Final stats
print(f"\n{'=' * 50}")
print(f"Training complete: {callback.total_games} games played")
if callback.wins:
    print(f"Final win rate:  {np.mean(callback.wins):.1%}")
    print(
        f"Final play rate: {np.mean([1.0 if a == 0 else 0.0 for a in callback.actions]):.1%}"
    )
    print(f"Mean reward:     {np.mean(callback.rewards):+.2f}")
    print(f"Mean turns:      {np.mean(callback.turns):.0f}")

# %%
env.close()
