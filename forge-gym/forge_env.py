"""Gymnasium environment for Forge MTG."""

import json
import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

import gymnasium as gym
import numpy as np
from gymnasium import spaces

# Default path: forge-gym/../forge-gui-desktop/target/
_DEFAULT_FORGE_ROOT = Path(__file__).resolve().parent.parent


def _find_jar(forge_root: Path) -> Path:
    """Find the forge-gui-desktop jar in the build output."""
    target_dir = forge_root / "forge-gui-desktop" / "target"
    for f in sorted(target_dir.glob("forge-gui-desktop-*-jar-with-dependencies.jar")):
        return f
    raise FileNotFoundError(
        f"No forge-gui-desktop jar found in {target_dir}. Run 'mvn package -DskipTests' first."
    )


class ForgeMTGEnv(gym.Env):
    """Gymnasium environment that connects to a Forge gym server.

    Currently exposes only the play/draw decision after winning the coin toss.
    All other game decisions are handled by the Forge AI.

    Action space: Discrete(2) — 0 = play (go first), 1 = draw (go second)
    Observation space: Dict with decision method and options

    When the gym agent doesn't win the coin toss, no decision is presented.
    In that case, reset() returns with info["skipped"]=True and the episode
    is immediately terminal (step() should not be called).

    Usage:
        # Auto-start Forge (headless training):
        env = ForgeMTGEnv(decks=["gb", "gb"])

        # Connect to an already-running Forge server:
        env = ForgeMTGEnv(port=9753)
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9753,
        decks: Optional[list[str]] = None,
        forge_root: Optional[str] = None,
        java: str = "java",
        java_args: Optional[list[str]] = None,
    ):
        """
        Args:
            host: Hostname to connect to.
            port: TCP port for the gym server.
            decks: Two deck names, e.g. ["gb", "gb"]. If provided,
                Forge is started as a subprocess automatically.
            forge_root: Path to the Forge project root. Defaults to the parent
                of the forge-gym directory.
            java: Java executable name or path.
            java_args: Extra JVM arguments (e.g. ["-Xmx4g"]).
        """
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

        # Auto-start Forge if decks are provided
        if decks is not None:
            if len(decks) < 2:
                raise ValueError("Need at least 2 deck names")
            root = Path(forge_root) if forge_root else _DEFAULT_FORGE_ROOT
            jar = _find_jar(root)
            cwd = root / "forge-gui"  # Must run from here for asset resolution

            cmd = [java]
            if java_args:
                cmd.extend(java_args)
            cmd.extend(["-jar", str(jar), "gym", "-d"] + list(decks) + ["-p", str(port)])

            self.forge_process = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

        self._connect()

    def _connect(self):
        """Connect to the Forge gym server, retrying until it's ready."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        for attempt in range(30):
            try:
                self.sock.connect((self.host, self.port))
                return
            except ConnectionRefusedError:
                if self.forge_process and self.forge_process.poll() is not None:
                    stdout = self.forge_process.stdout.read().decode() if self.forge_process.stdout else ""
                    raise RuntimeError(
                        f"Forge process exited with code {self.forge_process.returncode}:\n{stdout}"
                    )
                if attempt < 29:
                    time.sleep(1)
                else:
                    raise ConnectionError(
                        f"Could not connect to Forge gym server at {self.host}:{self.port} "
                        f"after 30 attempts"
                    )

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
            try:
                self.forge_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.forge_process.kill()
            self.forge_process = None
