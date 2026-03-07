# Forge Gym Project

Goal: Implement a Gymnasium (RL) interface for Forge to train reinforcement learning agents for Magic: The Gathering.

## Project Structure

Forge is a multi-module Maven project:

- **forge-core** — Card database, deck structures, fundamental types (`PaperCard`, `CardDb`, `Deck`)
- **forge-game** — Complete MTG game engine and rules
- **forge-ai** — AI decision-making, simulation, game state evaluation
- **forge-gui** — GUI abstractions and shared resources (also contains `res/` assets)
- **forge-gui-desktop** — Desktop (Swing) frontend
- **forge-gui-mobile-dev** — Mobile dev frontend
- **forge-lda** — Advanced game features

## Build & Run

See [GYM.md](GYM.md) for build/run instructions.

```bash
mvn package -DskipTests
cd forge-gui && java -jar ../forge-gui-desktop/target/forge-gui-desktop-2.0.12-SNAPSHOT-jar-with-dependencies.jar
```

## Key Architecture for Gym Integration

### Decision Interface

All player decisions flow through `PlayerController` (forge-game). This is the main integration point:

- `PlayerController.java` — Abstract base with 100+ decision methods
- `PlayerControllerAi.java` (forge-ai) — AI implementation
- Key method: `chooseSpellAbilityToPlay()` — called during priority to select an action

### Game Lifecycle

```
Match.createGame() → Game → Match.startGame(game)
  → game.getAction().startGame()
```

Games can be created and run programmatically without a GUI.

### Game State

- `Game.java` — Top-level game state (players, phases, stack, zones)
- `Player.java` — Player state (life, mana pool, cards per zone)
- `Card.java` — Individual card state (power/toughness, counters, keywords, abilities)
- `Zone.java` / `ZoneType` — Card containers (Hand, Library, Battlefield, Graveyard, Exile, Stack, etc.)
- `Combat.java` — Active combat state (attackers, blockers, damage)

### Turn/Phase System

`PhaseHandler.java` manages the turn structure:

UNTAP → UPKEEP → DRAW → MAIN1 → COMBAT (BEGIN → ATTACKERS → BLOCKERS → FIRST_STRIKE_DAMAGE → DAMAGE → END) → MAIN2 → END_OF_TURN → CLEANUP

### Actions

Action types in `forge-game/.../player/actions/`:
- `CastSpellAction`, `ActivateAbilityAction`, `PassPriorityAction`, `SelectCardAction`, `PayManaFromPoolAction`

### Existing Simulation Infrastructure

- `GameSimulator.java` — Runs game simulations for AI lookahead
- `GameCopier.java` — Deep copies game state
- `GameStateEvaluator.java` — Heuristic game state scoring
- `SpellAbilityPicker.java` — Simulation-based action selection
- `GameWrapper.java` (test) — Programmatic game execution for tests

### Key File Paths

| File | Path |
|------|------|
| PlayerController | `forge-game/src/main/java/forge/game/player/PlayerController.java` |
| Game | `forge-game/src/main/java/forge/game/Game.java` |
| Match | `forge-game/src/main/java/forge/game/Match.java` |
| GameAction | `forge-game/src/main/java/forge/game/GameAction.java` |
| Player | `forge-game/src/main/java/forge/game/player/Player.java` |
| Card | `forge-game/src/main/java/forge/game/Card.java` |
| PhaseHandler | `forge-game/src/main/java/forge/game/phase/PhaseHandler.java` |
| AiController | `forge-ai/src/main/java/forge/ai/AiController.java` |
| PlayerControllerAi | `forge-ai/src/main/java/forge/ai/PlayerControllerAi.java` |
| GameSimulator | `forge-ai/src/main/java/forge/ai/simulation/GameSimulator.java` |
| GameCopier | `forge-ai/src/main/java/forge/ai/simulation/GameCopier.java` |
| GameStateEvaluator | `forge-ai/src/main/java/forge/ai/simulation/GameStateEvaluator.java` |
| GameWrapper (test) | `forge-gui-desktop/src/test/java/forge/gamesimulationtests/util/GameWrapper.java` |
