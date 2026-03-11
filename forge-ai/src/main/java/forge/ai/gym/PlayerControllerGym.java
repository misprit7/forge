package forge.ai.gym;

import forge.LobbyPlayer;
import forge.ai.PlayerControllerAi;
import forge.game.card.Card;
import forge.game.Game;
import forge.game.GameEntity;
import forge.game.combat.Combat;
import forge.game.combat.CombatUtil;
import forge.game.player.Player;

/**
 * Player controller that routes decisions to a Python Gym agent via TCP.
 * Currently only overrides chooseStartingPlayer; all other decisions
 * delegate to the AI (inherited from PlayerControllerAi).
 */
public class PlayerControllerGym extends PlayerControllerAi {
    private final GymSocket socket;

    public PlayerControllerGym(Game game, Player player, LobbyPlayer lp, GymSocket socket) {
        super(game, player, lp);
        this.socket = socket;
    }

    @Override
    public Player chooseStartingPlayer(boolean isFirstGame) {
        try {
            // Send decision request to Python
            String opponentName = "";
            for (Player p : getGame().getPlayers()) {
                if (p != this.player) {
                    opponentName = p.getName();
                    break;
                }
            }
            socket.send("{\"type\":\"decision\",\"method\":\"chooseStartingPlayer\","
                    + "\"options\":[\"play\",\"draw\"],"
                    + "\"player\":\"" + escapeJson(this.player.getName()) + "\","
                    + "\"opponent\":\"" + escapeJson(opponentName) + "\"}");

            // Block for response
            String response = socket.receive();
            if (response == null) {
                System.err.println("GymSocket: client disconnected, falling back to AI");
                return super.chooseStartingPlayer(isFirstGame);
            }

            // Parse action from {"action": N}
            int action = parseAction(response);
            if (action == 0) {
                // Choose to play (this player goes first)
                return this.player;
            } else {
                // Choose to draw (opponent goes first)
                for (Player p : getGame().getPlayers()) {
                    if (p != this.player) {
                        return p;
                    }
                }
            }
        } catch (Exception e) {
            System.err.println("GymSocket error in chooseStartingPlayer: " + e.getMessage());
        }
        return super.chooseStartingPlayer(isFirstGame);
    }

    @Override
    public void declareAttackers(Player attacker, Combat combat) {
        // Fast policy: attack with everything that can legally attack
        GameEntity defender = combat.getDefenders().getFirst();
        for (Card c : attacker.getCreaturesInPlay()) {
            if (CombatUtil.canAttack(c, defender)) {
                combat.addAttacker(c, defender);
            }
        }
    }

    @Override
    public void declareBlockers(Player defender, Combat combat) {
        // Fast policy: never block
    }

    private static int parseAction(String json) {
        // Parse {"action": N} without a JSON library
        int idx = json.indexOf("\"action\"");
        if (idx < 0) return 0;
        idx = json.indexOf(':', idx);
        if (idx < 0) return 0;
        StringBuilder sb = new StringBuilder();
        for (int i = idx + 1; i < json.length(); i++) {
            char c = json.charAt(i);
            if (Character.isDigit(c) || c == '-') {
                sb.append(c);
            } else if (sb.length() > 0) {
                break;
            }
        }
        return sb.length() > 0 ? Integer.parseInt(sb.toString()) : 0;
    }

    private static String escapeJson(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }
}
