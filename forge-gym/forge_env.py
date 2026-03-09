"""Gymnasium environment for Forge MTG."""

import json
import socket
import subprocess
import time
from typing import Any, Optional

import gymnasium as gym
import numpy as np
from gymnasium import spaces


class ForgeMTGEnv(gym.Env):
    """Gymnasium environment that connects to a Forge gym server.

    Currently exposes only the play/draw decision after winning the coin toss.
    All other game decisions are handled by the Forge AI.

    Action space: Discrete(2) — 0 = play (go first), 1 = draw (go second)
    Observation space: Dict with decision method and options

    When the gym agent doesn't win the coin toss, no decision is presented.
    In that case, reset() returns with info["skipped"]=True and the episode
    is immediately terminal (step() should not be called).
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9753,
        forge_jar: Optional[str] = None,
        forge_args: Optional[list[str]] = None,
    ):
        super().__init__()

        self.host = host
        self.port = port
        self.forge_process = None
        self.sock = None
        self._recv_buf = b""

        # Action space: play or draw
        self.action_space = spaces.Discrete(2)

        # Observation: just the decision method for now
        self.observation_space = spaces.Dict({
            "method": spaces.Discrete(1),  # 0 = chooseStartingPlayer
        })

        # Track whether the current episode needs a step() call
        self._needs_step = False
        self._last_game_over = None

        # Start Forge subprocess if jar path provided
        if forge_jar is not None:
            args = ["java", "-jar", forge_jar, "gym"] + (forge_args or [])
            self.forge_process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            # Wait for server to start
            time.sleep(3)

        self._connect()

    def _connect(self):
        """Connect to the Forge gym server."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        for attempt in range(10):
            try:
                self.sock.connect((self.host, self.port))
                return
            except ConnectionRefusedError:
                if attempt < 9:
                    time.sleep(1)
                else:
                    raise

    def _send(self, obj: dict):
        """Send a JSON message."""
        self.sock.sendall((json.dumps(obj) + "\n").encode())

    def _receive(self) -> dict:
        """Receive a newline-delimited JSON message."""
        while b"\n" not in self._recv_buf:
            data = self.sock.recv(4096)
            if not data:
                raise ConnectionError("Server disconnected")
            self._recv_buf += data
        line, _, self._recv_buf = self._recv_buf.partition(b"\n")
        return json.loads(line)

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[dict[str, Any]] = None,
    ) -> tuple[dict, dict]:
        super().reset(seed=seed)

        # Tell Forge to start a new game
        self._send({"command": "reset"})

        # Receive either a decision request or game_over
        # (game_over happens when AI won the coin toss — no decision for us)
        msg = self._receive()

        obs = {"method": 0}

        if msg.get("type") == "game_over":
            # No decision was needed this game
            self._needs_step = False
            self._last_game_over = msg
            info = {
                "skipped": True,
                "winner": msg.get("winner", -1),
                "turns": msg.get("turns", 0),
                "reward": msg.get("reward", 0.0),
            }
        else:
            # Decision request
            self._needs_step = True
            self._last_game_over = None
            info = {
                "skipped": False,
                "method": msg.get("method", ""),
                "options": msg.get("options", []),
                "player": msg.get("player", ""),
                "opponent": msg.get("opponent", ""),
            }

        return obs, info

    def step(self, action: int) -> tuple[dict, float, bool, bool, dict]:
        if not self._needs_step:
            # Episode was already terminal from reset (no decision needed)
            msg = self._last_game_over or {}
            return (
                {"method": 0},
                msg.get("reward", 0.0),
                True,
                False,
                {"winner": msg.get("winner", -1), "turns": msg.get("turns", 0)},
            )

        # Send the action
        self._send({"action": int(action)})

        # Receive game result
        msg = self._receive()
        self._needs_step = False

        reward = msg.get("reward", 0.0)
        terminated = msg.get("type") == "game_over"
        truncated = False
        info = {
            "winner": msg.get("winner", -1),
            "turns": msg.get("turns", 0),
        }

        obs = {"method": 0}
        return obs, reward, terminated, truncated, info

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        if self.forge_process:
            self.forge_process.terminate()
            self.forge_process.wait(timeout=10)
            self.forge_process = None
