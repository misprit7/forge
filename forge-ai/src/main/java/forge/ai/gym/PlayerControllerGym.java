package forge.ai.gym;

import forge.ai.*;

import forge.LobbyPlayer;
import forge.game.*;
import forge.game.card.*;
import forge.game.combat.Combat;
import forge.game.player.*;
import forge.util.collect.FCollectionView;


/**
 * Controller for Gym environment wrapper
 */
public class PlayerControllerGym extends PlayerControllerAi {

    public PlayerControllerGym(Game game, Player p, LobbyPlayer lp) {
        super(game, p, lp);
    }


    @Override
    public void declareAttackers(Player attacker, Combat combat) {
        System.out.println("Declaring gym attackers");
        final FCollectionView<GameEntity> defs = combat.getDefenders();
        for (Card c : attacker.getCreaturesInPlay()) {
            combat.addAttacker(c, defs.getFirst());
        }
    }

    @Override
    public void declareBlockers(Player defender, Combat combat) {
        // List<Card> possibleBlockers = this.player.getCreaturesInPlay();
    }

}


