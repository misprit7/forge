package forge.view;

import java.io.IOException;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

import forge.ai.gym.GymSocket;
import forge.ai.gym.LobbyPlayerGym;
import forge.deck.Deck;
import forge.game.Game;
import forge.game.GameEndReason;
import forge.game.GameRules;
import forge.game.GameType;
import forge.game.Match;
import forge.game.player.RegisteredPlayer;
import forge.model.FModel;
import forge.player.GamePlayerUtil;

/**
 * Entry point for the Gym server CLI mode.
 * Listens for a Python Gym client, then loops:
 *   receive "reset" → run one game → send game result.
 */
public class GymServer {

    public static void start(String[] args) {
        FModel.initialize(null, null);

        // Parse args
        Map<String, List<String>> params = new HashMap<>();
        List<String> options = null;
        for (int i = 1; i < args.length; i++) {
            String a = args[i];
            if (a.charAt(0) == '-') {
                options = new ArrayList<>();
                params.put(a.substring(1), options);
            } else if (options != null) {
                options.add(a);
            }
        }

        int port = 9753;
        if (params.containsKey("p")) {
            port = Integer.parseInt(params.get("p").get(0));
        }

        if (!params.containsKey("d") || params.get("d").size() < 2) {
            System.out.println("Usage: gym -d <deck1> <deck2> [-p port]");
            return;
        }

        List<String> deckNames = params.get("d");
        GameType type = GameType.Constructed;

        // Load decks
        Deck deck1 = SimulateMatch.deckFromCommandLineParameter(deckNames.get(0), type);
        Deck deck2 = SimulateMatch.deckFromCommandLineParameter(deckNames.get(1), type);
        if (deck1 == null || deck2 == null) {
            System.out.println("Could not load decks");
            return;
        }

        try (GymSocket socket = new GymSocket(port)) {
            System.out.println("Waiting for Python client...");
            socket.acceptClient();
            System.out.println("Client connected. Ready for games.");

            // Game loop
            while (true) {
                String msg = socket.receive();
                if (msg == null) {
                    System.out.println("Client disconnected.");
                    break;
                }

                // Expect {"command":"reset"}
                if (!msg.contains("\"reset\"")) {
                    System.err.println("Unexpected message: " + msg);
                    continue;
                }
                runOneGame(socket, deck1, deck2, type);
            }
        } catch (IOException e) {
            System.err.println("GymServer error: " + e.getMessage());
            e.printStackTrace();
        }
    }

    private static void runOneGame(GymSocket socket, Deck deck1, Deck deck2, GameType type) {
        GameRules rules = new GameRules(type);
        rules.setAppliedVariants(EnumSet.of(type));

        List<RegisteredPlayer> players = new ArrayList<>();

        // Player 0: Gym agent
        RegisteredPlayer rp1 = new RegisteredPlayer(deck1);
        rp1.setPlayer(new LobbyPlayerGym("GymAgent", socket));
        players.add(rp1);

        // Player 1: AI opponent
        RegisteredPlayer rp2 = new RegisteredPlayer(deck2);
        rp2.setPlayer(GamePlayerUtil.createAiPlayer("AI-Opponent", 1));
        players.add(rp2);

        Match match = new Match(rules, players, "GymMatch");
        Game game = match.createGame();

        try {
            TimeLimitedCodeBlock.runWithTimeout(() -> {
                match.startGame(game);
            }, 120, TimeUnit.SECONDS);
        } catch (TimeoutException e) {
            System.out.println("Game timed out, ending as draw");
        } catch (Exception | StackOverflowError e) {
            System.err.println("Game error: " + e.getMessage());
            e.printStackTrace();
        } finally {
            if (!game.isGameOver()) {
                game.setGameOver(GameEndReason.Draw);
            }
        }

        // Determine winner
        int winnerIndex = -1; // draw
        if (!game.getOutcome().isDraw()) {
            String winnerName = game.getOutcome().getWinningLobbyPlayer().getName();
            if ("GymAgent".equals(winnerName)) {
                winnerIndex = 0;
            } else {
                winnerIndex = 1;
            }
        }

        int turns = game.getPhaseHandler().getTurn();
        float reward = winnerIndex == 0 ? 1.0f : (winnerIndex == 1 ? -1.0f : 0.0f);

        socket.send("{\"type\":\"game_over\",\"winner\":" + winnerIndex
                + ",\"reward\":" + reward
                + ",\"turns\":" + turns + "}");

        System.out.println("Game finished. Winner: " + (winnerIndex == -1 ? "draw" : winnerIndex)
                + ", Turns: " + turns);
    }
}
