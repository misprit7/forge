# Forge Gym: Building & Running

## Prerequisites

- Java 21+
- Maven

## Build

```bash
mvn package -DskipTests
```

## Run (Desktop GUI)

Run from the `forge-gui/` directory so the app can find `res/` at the expected relative path:

```bash
cd forge-gui
java -jar ../forge-gui-desktop/target/forge-gui-desktop-2.0.12-SNAPSHOT-jar-with-dependencies.jar
```

### Why `forge-gui/`?

The desktop app resolves its assets directory relative to the working directory. When running from a JAR with a SNAPSHOT version, `GuiDesktop.getAssetsDir()` returns `""`, so it looks for `res/` in the current directory. `forge-gui/` already contains `res/`, so no symlinks or copies are needed.

## Run (Headless Simulation)

Run AI-vs-AI games from the command line without the GUI:

```bash
cd forge-gui
java -jar ../forge-gui-desktop/target/forge-gui-desktop-2.0.12-SNAPSHOT-jar-with-dependencies.jar sim -d grizzly grizzly -n 3
```

- `sim` — simulation mode (no GUI)
- `-d <deck1> <deck2>` — deck names (looked up from `~/.forge/decks/constructed/`)
- `-n <count>` — number of games to play

### Debug logging

Pass tinylog level as a system property:

```bash
java -Dtinylog.writerdefault.level=debug -jar ../forge-gui-desktop/target/forge-gui-desktop-2.0.12-SNAPSHOT-jar-with-dependencies.jar
```

Use `trace` for maximum detail.

## Data directories

On Linux, user data and cache go to:

- **User data:** `~/.forge/` (preferences, quest saves)
- **Decks:** `~/.forge/decks/constructed/` (constructed deck files)
- **Cache:** `~/.cache/forge/` (skins, card pics, fonts, db)

These can be overridden via `forge.profile.properties` in the assets directory.

## Run (Gym Server)

Start a TCP server that exposes game decisions to a Python Gymnasium agent:

```bash
cd forge-gui
java -jar ../forge-gui-desktop/target/forge-gui-desktop-2.0.12-SNAPSHOT-jar-with-dependencies.jar gym -d grizzly grizzly -p 9753
```

- `gym` — gymnasium server mode
- `-d <deck1> <deck2>` — deck names (player 0 = gym agent, player 1 = AI opponent)
- `-p <port>` — TCP port (default: 9753)

Then connect from Python:

```python
from forge_env import ForgeMTGEnv

env = ForgeMTGEnv(port=9753)
obs, info = env.reset()
print(info)  # {'method': 'chooseStartingPlayer', 'options': ['play', 'draw'], ...}

obs, reward, terminated, truncated, info = env.step(0)  # 0=play, 1=draw
print(reward, info)  # 1.0 {'winner': 0, 'turns': 42}
```

The gym env is in `forge-gym/forge_env.py`. Currently exposes only the play/draw decision; all other decisions are handled by the AI.
