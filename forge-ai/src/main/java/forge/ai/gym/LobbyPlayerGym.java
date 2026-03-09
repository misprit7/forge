package forge.ai.gym;

import forge.LobbyPlayer;
import forge.game.Game;
import forge.game.player.IGameEntitiesFactory;
import forge.game.player.Player;
import forge.game.player.PlayerController;

/**
 * Lobby player that creates PlayerControllerGym instances.
 * Follows the LobbyPlayerAi pattern.
 */
public class LobbyPlayerGym extends LobbyPlayer implements IGameEntitiesFactory {
    private final GymSocket socket;

    public LobbyPlayerGym(String name, GymSocket socket) {
        super(name);
        this.socket = socket;
    }

    private PlayerControllerGym createControllerFor(Player player) {
        return new PlayerControllerGym(player.getGame(), player, this, socket);
    }

    @Override
    public PlayerController createMindSlaveController(Player master, Player slave) {
        return createControllerFor(slave);
    }

    @Override
    public Player createIngamePlayer(Game game, final int id) {
        Player player = new Player(getName(), game, id);
        player.setFirstController(createControllerFor(player));
        return player;
    }

    @Override
    public void hear(LobbyPlayer player, String message) {
        // Gym player doesn't process chat messages
    }
}
