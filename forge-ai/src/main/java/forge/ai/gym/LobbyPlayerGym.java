package forge.ai.gym;

import java.util.Set;

import forge.LobbyPlayer;
import forge.game.Game;
import forge.game.player.IGameEntitiesFactory;
import forge.game.player.Player;
import forge.game.player.PlayerController;
import forge.ai.LobbyPlayerAi;
import forge.ai.PlayerControllerAi;

public class LobbyPlayerGym extends LobbyPlayerAi {

    public LobbyPlayerGym(String name, Set<GymOption> options) {
        super(name, null);
    }
    @Override
    protected PlayerControllerAi createControllerFor(Player player) {
        PlayerControllerGym result = new PlayerControllerGym(player.getGame(), player, this);
        result.setUseSimulation(false);
        result.allowCheatShuffle(false);
        return result;
    }
}
