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
    Observation space: Box([0], [0], float32) — placeholder (single zero);
        will become meaningful as more decision types are added.

    When the gym agent doesn't win the coin toss, reset() automatically
    re-rolls until a decision is needed, so callers always get a valid episode.

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

        # Observation: flat array, placeholder for now
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(1,), dtype=np.float32
        )

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

    def _obs(self) -> np.ndarray:
        return np.zeros(1, dtype=np.float32)

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[dict[str, Any]] = None,
    ) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)

        # Keep resetting until we get a game where the agent has a decision.
        # (When the AI wins the coin toss, the game plays out without us.)
        while True:
            self._send({"command": "reset"})
            msg = self._receive()

            if msg.get("type") == "game_over":
                # No decision this game — try again
                continue

            # Got a decision request
            info = {
                "method": msg.get("method", ""),
                "options": msg.get("options", []),
                "player": msg.get("player", ""),
                "opponent": msg.get("opponent", ""),
            }
            return self._obs(), info

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict]:
        self._send({"action": int(action)})
        msg = self._receive()

        reward = msg.get("reward", 0.0)
        terminated = msg.get("type") == "game_over"
        truncated = False
        info = {
            "winner": msg.get("winner", -1),
            "turns": msg.get("turns", 0),
            "action": int(action),
        }

        return self._obs(), reward, terminated, truncated, info

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
