# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

### Core Build Commands
```bash
# Full build with all dependencies
mvn -U -B clean -P windows-linux install

# Quick compile (skip tests and checkstyle)
mvn compile -DskipTests -Dcheckstyle.skip=true

# Build all modules for development
mvn clean install -DskipTests -Dcheckstyle.skip=true

# Run tests
mvn test

# Run single test class
mvn test -Dtest=CardCopyServiceTest

# Run checkstyle validation
mvn checkstyle:check
```

### Running Forge GUI and Headless Mode
```bash
# Run GUI using proper classpath and JVM args (recommended for development)
./run-forge-headless.sh

# Run headless simulation (useful for RL/testing)
./run-forge-headless.sh sim -d wr gb -n 3

# Run with RL PlayerController (after implementing integration)
./run-forge-headless.sh sim -ai rl -d wr gb -n 1
```

### Platform-Specific Builds
```bash
# Windows/Linux build
mvn -U -B clean -P windows-linux install

# Android build (requires Android SDK)
mvn clean install -P android

# Desktop GUI build
mvn clean package -pl forge-gui-desktop
```

## Architecture Overview

### Multi-Module Maven Project Structure

Forge is organized as a multi-module Maven project with clear separation of concerns:

**Core Modules:**
- `forge-core` - Foundational utilities and data structures
- `forge-game` - MTG rules engine and game logic (600+ classes)
- `forge-ai` - AI implementations including rule-based AI and new RL interface

**GUI Modules:**
- `forge-gui` - Shared GUI components and game resources
- `forge-gui-desktop` - Desktop Swing/AWT interface
- `forge-gui-mobile` - LibGDX-based mobile interface
- `forge-gui-android` - Android-specific implementation
- `forge-gui-ios` - iOS-specific implementation

**Specialized Modules:**
- `forge-lda` - Latent Dirichlet Allocation for deck analysis
- `adventure-editor` - Tool for creating adventure mode content
- `forge-installer` - Installation and distribution utilities

### Key Architectural Patterns

**PlayerController Pattern:** The central abstraction for game decision-making. All AI implementations (rule-based AI, human players, RL agents) extend the abstract `PlayerController` class in `forge-game/src/main/java/forge/game/player/PlayerController.java`. This enables pluggable AI without modifying core game logic.

**Game Engine:** The rules engine in `forge-game` implements complete MTG rules including:
- Zone management (hand, library, battlefield, graveyard, stack, exile)
- Priority and timing rules
- Triggered abilities and state-based effects
- Combat system with complex damage assignment
- Comprehensive keyword ability support

**Card Implementation:** Individual MTG cards are implemented as script files in `forge-gui/res/cardsfolder/` with abilities defined declaratively. The game engine interprets these scripts to create `Card` objects with appropriate `SpellAbility` instances.

**AI Architecture:** The existing AI in `forge-ai` uses a rule-based approach with:
- `PlayerControllerAi` as the main decision controller
- `AiController` managing strategy and game analysis
- Specialized AI classes for different decision types (`ComputerUtil*` classes)
- Card evaluation functions and play decision trees

### RL Interface Architecture (New)

A reinforcement learning interface has been added that abstracts MTG decisions into learnable decision types:

**Java Side:**
- `PlayerControllerRl` - Extends `PlayerController` to interface with RL agents
- `RlBridge` - Socket communication with Python RL training environment
- Decision abstraction reduces 100+ decision methods to 8 key decision types

**Python Side (in `/python`):**
- `ForgeEnv` - OpenAI Gym environment for RL training
- Socket-based communication with Java Forge process
- Support for popular RL frameworks (stable-baselines3, etc.)

### Game State Management

The game state is managed through several key classes:
- `Game` - Central game coordinator
- `Player` - Player state and zones
- `Card` - Individual card instances with state tracking
- `Combat` - Combat phase management
- `MagicStack` - Stack for spells and abilities

### Resource Loading

Game resources are loaded from `forge-gui/res/`:
- Card definitions from `/cardsfolder/`
- Edition information from `/editions/`
- AI profiles from `/ai/`
- Adventure mode content from `/adventure/`

## Development Environment Requirements

- **Java JDK 17+** (required)
- **Maven 3.8.1+** (for dependency management)
- **IntelliJ IDEA** (recommended IDE - has specific setup guide)
- **Git** (version control)

## Code Style and Quality

The project enforces strict checkstyle rules (based on `checkstyle.xml`). During development, you can skip checkstyle with `-Dcheckstyle.skip=true`, but production code must pass all style checks.

## Testing

Tests are located in `src/test/java` directories within each module. The test suite includes:
- Unit tests for game logic components
- Integration tests for complete game scenarios  
- AI simulation tests for validating AI decision-making

Use `mvn test -Dtest=ClassName` to run specific test classes during development.