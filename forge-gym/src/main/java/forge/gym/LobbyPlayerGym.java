package forge.gym;

import java.util.Set;

import forge.LobbyPlayer;
import forge.game.Game;
import forge.game.player.IGameEntitiesFactory;
import forge.game.player.Player;
import forge.game.player.PlayerController;

public class LobbyPlayerGym extends LobbyPlayer implements IGameEntitiesFactory {

    private String aiProfile = "";
    private boolean allowCheatShuffle;
    private boolean useSimulation;

    public LobbyPlayerGym(String name, Set<GymOption> options) {
        super(name);
        if (options != null && options.contains(GymOption.USE_SIMULATION)) {
            this.useSimulation = true;
        }
    }

    public boolean isAllowCheatShuffle() {
        return allowCheatShuffle;
    }
    public void setAllowCheatShuffle(boolean allowCheatShuffle) {
        this.allowCheatShuffle = allowCheatShuffle;
    }

    private PlayerControllerGym createControllerFor(Player player) {
        PlayerControllerGym result = new PlayerControllerGym(player.getGame(), player, this);
        result.setUseSimulation(useSimulation);
        result.allowCheatShuffle(allowCheatShuffle);
        return result;
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
    public void hear(LobbyPlayer player, String message) { /* Local AI is deaf. */ }
}
