package forge.ai;

import com.google.common.collect.Lists;
import com.google.common.collect.ListMultimap;
import com.google.common.collect.Maps;
import com.google.common.collect.Multimap;
import forge.LobbyPlayer;
import forge.card.ColorSet;
import forge.card.ICardFace;
import forge.card.mana.ManaCost;
import forge.card.mana.ManaCostShard;
import forge.deck.Deck;
import forge.deck.DeckSection;
import forge.game.*;
import forge.game.ability.effects.RollDiceEffect;
import forge.game.card.*;
import forge.game.combat.Combat;
import forge.game.cost.Cost;
import forge.game.cost.CostPart;
import forge.game.cost.CostPartMana;
import forge.game.keyword.KeywordInterface;
import forge.game.mana.Mana;
import forge.game.mana.ManaConversionMatrix;
import forge.game.mana.ManaCostBeingPaid;
import forge.game.player.*;
import forge.game.replacement.ReplacementEffect;
import forge.game.spellability.*;
import forge.game.staticability.StaticAbility;
import forge.game.trigger.WrappedAbility;
import forge.game.zone.PlayerZone;
import forge.game.zone.ZoneType;
import forge.item.PaperCard;
import forge.util.ITriggerEvent;
import forge.util.collect.FCollectionView;
import org.apache.commons.lang3.tuple.ImmutablePair;
import org.apache.commons.lang3.tuple.Pair;

import java.util.*;
import java.util.function.Predicate;

/**
 * RL-based PlayerController that interfaces with Python for neural network decisions.
 * This controller abstracts MTG decisions into a limited set of decision types that can be
 * handled by reinforcement learning agents.
 */
public class PlayerControllerRl extends PlayerController {
    
    private final RlBridge rlBridge;
    
    // Decision type enumeration for the RL agent
    public enum RlDecisionType {
        CHOOSE_CARDS_FROM_LIST,      // Generic "choose N cards from a list" - covers most card selection
        CHOOSE_TARGETS,              // Choose targets for spells/abilities
        CHOOSE_NUMBER,               // Choose a number in a range
        CHOOSE_BINARY,               // True/false, yes/no decisions
        CHOOSE_OPTION_FROM_LIST,     // Choose one option from a list of strings
        MULLIGAN_DECISION,           // Keep or mulligan hand
        DECLARE_ATTACKERS,           // Choose which creatures attack
        DECLARE_BLOCKERS,            // Choose how to block
        PLAY_SPELL_OR_ABILITY        // Choose which spell/ability to play
    }
    
    // Simplified game state representation for RL
    public static class RlGameState {
        // TODO: Implement game state serialization to numerical vectors
        // This would include information like:
        // - Hand size, library size, graveyard size for each player
        // - Life totals, mana available
        // - Creatures in play (power, toughness, abilities)
        // - Game phase, turn number
        // - Cards in various zones (encoded as feature vectors)
        
        public RlGameState(Game game, Player perspective) {
            // Stub - implement state extraction
        }
        
        public double[] toVector() {
            // Stub - convert game state to numerical vector for NN
            return new double[1000]; // Placeholder size
        }
    }
    
    // RL decision request structure
    public static class RlDecisionRequest {
        public RlDecisionType decisionType;
        public RlGameState gameState;
        public List<String> options;      // String representations of choices
        public Map<String, Object> metadata; // Additional context
        public int minChoices;
        public int maxChoices;
        
        public RlDecisionRequest(RlDecisionType type, RlGameState state) {
            this.decisionType = type;
            this.gameState = state;
            this.options = new ArrayList<>();
            this.metadata = new HashMap<>();
            this.minChoices = 1;
            this.maxChoices = 1;
        }
    }
    
    // RL decision response structure
    public static class RlDecisionResponse {
        public List<Integer> chosenIndices; // Indices of chosen options
        public Map<String, Object> additionalData; // For complex decisions
        
        public RlDecisionResponse() {
            this.chosenIndices = new ArrayList<>();
            this.additionalData = new HashMap<>();
        }
    }

    public PlayerControllerRl(Game game, Player p, LobbyPlayer lp) {
        super(game, p, lp);
        this.rlBridge = new RlBridge();
        
        // Attempt to connect to the RL server
        if (!this.rlBridge.connect()) {
            System.out.println("Warning: Could not connect to RL agent server. Using fallback AI behavior.");
        } else {
            System.out.println("Successfully connected to RL agent server on localhost:12345");
        }
    }

    @Override
    public boolean isAI() {
        return true;
    }

    // Main decision routing method - this is where we abstract all decisions
    private RlDecisionResponse makeRlDecision(RlDecisionRequest request) {
        // Use the RL bridge to request decision from Python
        if (rlBridge != null) {
            return rlBridge.requestDecision(request);
        } else {
            // Fallback if no RL bridge available
            System.err.println("No RL bridge available, using fallback");
            return createFallbackResponse(request);
        }
    }
    
    private RlDecisionResponse createFallbackResponse(RlDecisionRequest request) {
        RlDecisionResponse response = new RlDecisionResponse();
        
        // Fallback: just choose the first option for most decisions
        if (!request.options.isEmpty()) {
            response.chosenIndices.add(0);
            // For multi-choice decisions, choose up to maxChoices
            for (int i = 1; i < Math.min(request.maxChoices, request.options.size()); i++) {
                if (Math.random() < 0.3) { // Random selection for now
                    response.chosenIndices.add(i);
                }
            }
        }
        
        return response;
    }

    // Utility method to convert cards to string options
    private List<String> cardsToOptions(CardCollectionView cards) {
        List<String> options = new ArrayList<>();
        for (Card card : cards) {
            // Create a string representation that includes key info
            String option = card.getName() + " (" + card.getManaCost() + ")";
            if (card.isCreature()) {
                option += " [" + card.getCurrentPower() + "/" + card.getCurrentToughness() + "]";
            }
            options.add(option);
        }
        return options;
    }

    // ============================================================================
    // CORE DECISION METHOD IMPLEMENTATIONS
    // ============================================================================

    @Override
    public CardCollectionView chooseCardsForEffect(CardCollectionView sourceList, SpellAbility sa, 
            String title, int min, int max, boolean isOptional, Map<String, Object> params) {
        
        RlGameState gameState = new RlGameState(getGame(), player);
        RlDecisionRequest request = new RlDecisionRequest(RlDecisionType.CHOOSE_CARDS_FROM_LIST, gameState);
        
        request.options = cardsToOptions(sourceList);
        request.minChoices = isOptional ? 0 : min;
        request.maxChoices = max;
        request.metadata.put("title", title);
        request.metadata.put("spellAbility", sa != null ? sa.getDescription() : "None");
        
        RlDecisionResponse response = makeRlDecision(request);
        
        CardCollection chosen = new CardCollection();
        for (Integer index : response.chosenIndices) {
            if (index >= 0 && index < sourceList.size()) {
                chosen.add(sourceList.get(index));
            }
        }
        
        return chosen;
    }

    @Override
    public boolean chooseBinary(SpellAbility sa, String question, BinaryChoiceType kindOfChoice, Boolean defaultChoice) {
        RlGameState gameState = new RlGameState(getGame(), player);
        RlDecisionRequest request = new RlDecisionRequest(RlDecisionType.CHOOSE_BINARY, gameState);
        
        request.options.add("Yes");
        request.options.add("No");
        request.metadata.put("question", question);
        request.metadata.put("choiceType", kindOfChoice.toString());
        
        RlDecisionResponse response = makeRlDecision(request);
        
        return response.chosenIndices.isEmpty() ? 
               (defaultChoice != null ? defaultChoice : false) : 
               response.chosenIndices.get(0) == 0;
    }

    @Override
    public int chooseNumber(SpellAbility sa, String title, int min, int max) {
        RlGameState gameState = new RlGameState(getGame(), player);
        RlDecisionRequest request = new RlDecisionRequest(RlDecisionType.CHOOSE_NUMBER, gameState);
        
        for (int i = min; i <= max; i++) {
            request.options.add(String.valueOf(i));
        }
        request.metadata.put("title", title);
        
        RlDecisionResponse response = makeRlDecision(request);
        
        if (response.chosenIndices.isEmpty()) {
            return min;
        }
        
        int chosenIndex = response.chosenIndices.get(0);
        return min + chosenIndex;
    }

    @Override
    public boolean mulliganKeepHand(Player firstPlayer, int cardsToReturn) {
        RlGameState gameState = new RlGameState(getGame(), player);
        RlDecisionRequest request = new RlDecisionRequest(RlDecisionType.MULLIGAN_DECISION, gameState);
        
        request.options.add("Keep");
        request.options.add("Mulligan");
        request.metadata.put("cardsToReturn", cardsToReturn);
        request.metadata.put("handSize", player.getCardsIn(ZoneType.Hand).size());
        
        RlDecisionResponse response = makeRlDecision(request);
        
        return response.chosenIndices.isEmpty() || response.chosenIndices.get(0) == 0;
    }

    @Override
    public void declareAttackers(Player attacker, Combat combat) {
        // For now, delegate to fallback AI to prevent stalling
        // TODO: Implement attacker selection using RL
        fallbackAi.declareAttackers(attacker, combat);
    }

    @Override
    public void declareBlockers(Player defender, Combat combat) {
        // For now, delegate to fallback AI to prevent stalling  
        // TODO: Implement blocker selection using RL
        fallbackAi.declareBlockers(defender, combat);
    }

    @Override
    public List<SpellAbility> chooseSpellAbilityToPlay() {
        // Use RL agent to choose which spell/ability to play
        CardCollection cards = ComputerUtilAbility.getAvailableCards(getGame(), player);
        List<SpellAbility> playableSpells = ComputerUtilAbility.getSpellAbilities(cards, player);
        
        if (playableSpells.isEmpty()) {
            return new ArrayList<>();
        }
        
        RlGameState gameState = new RlGameState(getGame(), player);
        RlDecisionRequest request = new RlDecisionRequest(RlDecisionType.PLAY_SPELL_OR_ABILITY, gameState);
        
        // Convert spells to string options for RL agent
        List<String> options = new ArrayList<>();
        options.add("Pass (play nothing)"); // Always include pass option
        
        for (SpellAbility sa : playableSpells) {
            String description = sa.getHostCard().getName();
            if (sa.isSpell()) {
                description += " (Spell)";
            } else {
                description += " (" + sa.getDescription() + ")";
            }
            // Add mana cost info
            if (sa.getPayCosts() != null && sa.getPayCosts().hasManaCost()) {
                description += " [" + sa.getPayCosts().getCostMana().toString() + "]";
            }
            options.add(description);
        }
        
        request.options = options;
        request.minChoices = 0; // Can choose to pass
        request.maxChoices = 1; // Choose one spell or pass
        request.metadata.put("title", "Choose spell/ability to play");
        request.metadata.put("availableSpells", playableSpells.size());
        request.metadata.put("gamePhase", getGame().getPhaseHandler().getPhase().toString());
        
        RlDecisionResponse response = makeRlDecision(request);
        
        List<SpellAbility> result = new ArrayList<>();
        
        if (!response.chosenIndices.isEmpty()) {
            int chosenIndex = response.chosenIndices.get(0);
            
            // Index 0 is "Pass", indices 1+ are actual spells
            if (chosenIndex > 0 && chosenIndex <= playableSpells.size()) {
                SpellAbility chosenSpell = playableSpells.get(chosenIndex - 1);
                result.add(chosenSpell);
                System.out.println("RL Agent chose to play: " + chosenSpell.getHostCard().getName());
            } else {
                System.out.println("RL Agent chose to pass");
            }
        } else {
            System.out.println("RL Agent made no choice, defaulting to pass");
        }
        
        return result;
    }

    // ============================================================================
    // DELEGATION TO EXISTING AI FOR COMPLEX DECISIONS (TEMPORARY)
    // ============================================================================
    
    // For now, delegate complex decisions to the existing AI while we build out the RL interface
    private final PlayerControllerAi fallbackAi = new PlayerControllerAi(getGame(), player, lobbyPlayer);

    @Override
    public SpellAbility getAbilityToPlay(Card hostCard, List<SpellAbility> abilities, ITriggerEvent triggerEvent) {
        return fallbackAi.getAbilityToPlay(hostCard, abilities, triggerEvent);
    }

    @Override
    public void playSpellAbilityNoStack(SpellAbility effectSA, boolean mayChoseNewTargets) {
        fallbackAi.playSpellAbilityNoStack(effectSA, mayChoseNewTargets);
    }

    @Override
    public void orderAndPlaySimultaneousSa(List<SpellAbility> activePlayerSAs) {
        fallbackAi.orderAndPlaySimultaneousSa(activePlayerSAs);
    }

    @Override
    public boolean playTrigger(Card host, WrappedAbility wrapperAbility, boolean isMandatory) {
        return fallbackAi.playTrigger(host, wrapperAbility, isMandatory);
    }

    @Override
    public boolean playSaFromPlayEffect(SpellAbility tgtSA) {
        return fallbackAi.playSaFromPlayEffect(tgtSA);
    }

    @Override
    public List<PaperCard> sideboard(Deck deck, GameType gameType, String message) {
        return fallbackAi.sideboard(deck, gameType, message);
    }

    @Override
    public List<PaperCard> chooseCardsYouWonToAddToDeck(List<PaperCard> losses) {
        return fallbackAi.chooseCardsYouWonToAddToDeck(losses);
    }

    // ============================================================================
    // REMAINING ABSTRACT METHOD IMPLEMENTATIONS (SIMPLIFIED OR DELEGATED)
    // ============================================================================

    @Override
    public Map<Card, Integer> assignCombatDamage(Card attacker, CardCollectionView blockers, 
            CardCollectionView remaining, int damageDealt, GameEntity defender, boolean overrideOrder) {
        return fallbackAi.assignCombatDamage(attacker, blockers, remaining, damageDealt, defender, overrideOrder);
    }

    @Override
    public Map<GameEntity, Integer> divideShield(Card effectSource, Map<GameEntity, Integer> affected, int shieldAmount) {
        return fallbackAi.divideShield(effectSource, affected, shieldAmount);
    }

    @Override
    public Map<Byte, Integer> specifyManaCombo(SpellAbility sa, ColorSet colorSet, int manaAmount, boolean different) {
        return fallbackAi.specifyManaCombo(sa, colorSet, manaAmount, different);
    }

    @Override
    public CardCollectionView choosePermanentsToSacrifice(SpellAbility sa, int min, int max, CardCollectionView validTargets, String message) {
        return chooseCardsForEffect(validTargets, sa, message, min, max, min == 0, Maps.newHashMap());
    }

    @Override
    public CardCollectionView choosePermanentsToDestroy(SpellAbility sa, int min, int max, CardCollectionView validTargets, String message) {
        return chooseCardsForEffect(validTargets, sa, message, min, max, min == 0, Maps.newHashMap());
    }

    @Override
    public Integer announceRequirements(SpellAbility ability, String announce) {
        return fallbackAi.announceRequirements(ability, announce);
    }

    @Override
    public TargetChoices chooseNewTargetsFor(SpellAbility ability, Predicate<GameObject> filter, boolean optional) {
        return fallbackAi.chooseNewTargetsFor(ability, filter, optional);
    }

    @Override
    public boolean chooseTargetsFor(SpellAbility currentAbility) {
        return fallbackAi.chooseTargetsFor(currentAbility);
    }

    @Override
    public Pair<SpellAbilityStackInstance, GameObject> chooseTarget(SpellAbility sa, List<Pair<SpellAbilityStackInstance, GameObject>> allTargets) {
        return fallbackAi.chooseTarget(sa, allTargets);
    }

    @Override
    public boolean helpPayForAssistSpell(ManaCostBeingPaid cost, SpellAbility sa, int max, int requested) {
        return fallbackAi.helpPayForAssistSpell(cost, sa, max, requested);
    }

    @Override
    public Player choosePlayerToAssistPayment(FCollectionView<Player> optionList, SpellAbility sa, String title, int max) {
        return fallbackAi.choosePlayerToAssistPayment(optionList, sa, title, max);
    }

    @Override
    public CardCollection chooseCardsForEffectMultiple(Map<String, CardCollection> validMap, SpellAbility sa, String title, boolean isOptional) {
        return fallbackAi.chooseCardsForEffectMultiple(validMap, sa, title, isOptional);
    }

    @Override
    public <T extends GameEntity> T chooseSingleEntityForEffect(FCollectionView<T> optionList, DelayedReveal delayedReveal, SpellAbility sa, String title, boolean isOptional, Player relatedPlayer, Map<String, Object> params) {
        return fallbackAi.chooseSingleEntityForEffect(optionList, delayedReveal, sa, title, isOptional, relatedPlayer, params);
    }

    @Override
    public <T extends GameEntity> List<T> chooseEntitiesForEffect(FCollectionView<T> optionList, int min, int max, DelayedReveal delayedReveal, SpellAbility sa, String title, Player relatedPlayer, Map<String, Object> params) {
        return fallbackAi.chooseEntitiesForEffect(optionList, min, max, delayedReveal, sa, title, relatedPlayer, params);
    }

    @Override
    public List<SpellAbility> chooseSpellAbilitiesForEffect(List<SpellAbility> spells, SpellAbility sa, String title, int num, Map<String, Object> params) {
        return fallbackAi.chooseSpellAbilitiesForEffect(spells, sa, title, num, params);
    }

    @Override
    public SpellAbility chooseSingleSpellForEffect(List<SpellAbility> spells, SpellAbility sa, String title, Map<String, Object> params) {
        return fallbackAi.chooseSingleSpellForEffect(spells, sa, title, params);
    }

    @Override
    public boolean confirmAction(SpellAbility sa, PlayerActionConfirmMode mode, String message, List<String> options, Card cardToShow, Map<String, Object> params) {
        return chooseBinary(sa, message, BinaryChoiceType.TapOrUntap, true);
    }

    @Override
    public boolean confirmBidAction(SpellAbility sa, PlayerActionConfirmMode bidlife, String string, int bid, Player winner) {
        return fallbackAi.confirmBidAction(sa, bidlife, string, bid, winner);
    }

    @Override
    public boolean confirmReplacementEffect(ReplacementEffect replacementEffect, SpellAbility effectSA, GameEntity affected, String question) {
        return fallbackAi.confirmReplacementEffect(replacementEffect, effectSA, affected, question);
    }

    @Override
    public boolean confirmStaticApplication(Card hostCard, PlayerActionConfirmMode mode, String message, String logic) {
        return fallbackAi.confirmStaticApplication(hostCard, mode, message, logic);
    }

    @Override
    public boolean confirmTrigger(WrappedAbility sa) {
        return fallbackAi.confirmTrigger(sa);
    }

    @Override
    public List<Card> exertAttackers(List<Card> attackers) {
        return fallbackAi.exertAttackers(attackers);
    }

    @Override
    public List<Card> enlistAttackers(List<Card> attackers) {
        return fallbackAi.enlistAttackers(attackers);
    }

    @Override
    public CardCollection orderBlockers(Card attacker, CardCollection blockers) {
        return fallbackAi.orderBlockers(attacker, blockers);
    }

    @Override
    public CardCollection orderBlocker(Card attacker, Card blocker, CardCollection oldBlockers) {
        return fallbackAi.orderBlocker(attacker, blocker, oldBlockers);
    }

    @Override
    public CardCollection orderAttackers(Card blocker, CardCollection attackers) {
        return fallbackAi.orderAttackers(blocker, attackers);
    }

    @Override
    public void reveal(CardCollectionView cards, ZoneType zone, Player owner, String messagePrefix, boolean addMsgSuffix) {
        fallbackAi.reveal(cards, zone, owner, messagePrefix, addMsgSuffix);
    }

    @Override
    public void reveal(List<CardView> cards, ZoneType zone, PlayerView owner, String messagePrefix, boolean addMsgSuffix) {
        fallbackAi.reveal(cards, zone, owner, messagePrefix, addMsgSuffix);
    }

    @Override
    public void notifyOfValue(SpellAbility saSource, GameObject realtedTarget, String value) {
        fallbackAi.notifyOfValue(saSource, realtedTarget, value);
    }

    @Override
    public ImmutablePair<CardCollection, CardCollection> arrangeForScry(CardCollection topN) {
        return fallbackAi.arrangeForScry(topN);
    }

    @Override
    public ImmutablePair<CardCollection, CardCollection> arrangeForSurveil(CardCollection topN) {
        return fallbackAi.arrangeForSurveil(topN);
    }

    @Override
    public boolean willPutCardOnTop(Card c) {
        return fallbackAi.willPutCardOnTop(c);
    }

    @Override
    public CardCollectionView orderMoveToZoneList(CardCollectionView cards, ZoneType destinationZone, SpellAbility source) {
        return fallbackAi.orderMoveToZoneList(cards, destinationZone, source);
    }

    @Override
    public CardCollectionView chooseCardsToDiscardFrom(Player playerDiscard, SpellAbility sa, CardCollection validCards, int min, int max) {
        return chooseCardsForEffect(validCards, sa, "Choose cards to discard", min, max, min == 0, Maps.newHashMap());
    }

    @Override
    public CardCollectionView chooseCardsToDiscardUnlessType(int min, CardCollectionView hand, String param, SpellAbility sa) {
        return fallbackAi.chooseCardsToDiscardUnlessType(min, hand, param, sa);
    }

    @Override
    public CardCollection chooseCardsToDiscardToMaximumHandSize(int numDiscard) {
        CardCollectionView hand = player.getCardsIn(ZoneType.Hand);
        CardCollectionView chosen = chooseCardsForEffect(hand, null, "Choose cards to discard to hand size", 
                                                         numDiscard, numDiscard, false, Maps.newHashMap());
        return new CardCollection(chosen);
    }

    @Override
    public CardCollectionView chooseCardsToDelve(int genericAmount, CardCollection grave) {
        return fallbackAi.chooseCardsToDelve(genericAmount, grave);
    }

    @Override
    public Map<Card, ManaCostShard> chooseCardsForConvokeOrImprovise(SpellAbility sa, ManaCost manaCost, CardCollectionView untappedCards, boolean improvise) {
        return fallbackAi.chooseCardsForConvokeOrImprovise(sa, manaCost, untappedCards, improvise);
    }

    @Override
    public List<Card> chooseCardsForSplice(SpellAbility sa, List<Card> cards) {
        return fallbackAi.chooseCardsForSplice(sa, cards);
    }

    @Override
    public CardCollectionView chooseCardsToRevealFromHand(int min, int max, CardCollectionView valid) {
        return chooseCardsForEffect(valid, null, "Choose cards to reveal", min, max, min == 0, Maps.newHashMap());
    }

    @Override
    public List<SpellAbility> chooseSaToActivateFromOpeningHand(List<SpellAbility> usableFromOpeningHand) {
        return fallbackAi.chooseSaToActivateFromOpeningHand(usableFromOpeningHand);
    }

    @Override
    public Player chooseStartingPlayer(boolean isFirstGame) {
        return chooseBinary(null, "Choose to play first?", BinaryChoiceType.PlayOrDraw, true) ? player : player.getStrongestOpponent();
    }

    @Override
    public PlayerZone chooseStartingHand(List<PlayerZone> zones) {
        return fallbackAi.chooseStartingHand(zones);
    }

    @Override
    public Mana chooseManaFromPool(List<Mana> manaChoices) {
        return fallbackAi.chooseManaFromPool(manaChoices);
    }

    @Override
    public String chooseSomeType(String kindOfType, SpellAbility sa, Collection<String> validTypes, boolean isOptional) {
        RlGameState gameState = new RlGameState(getGame(), player);
        RlDecisionRequest request = new RlDecisionRequest(RlDecisionType.CHOOSE_OPTION_FROM_LIST, gameState);
        
        request.options.addAll(validTypes);
        request.metadata.put("kindOfType", kindOfType);
        request.minChoices = isOptional ? 0 : 1;
        
        RlDecisionResponse response = makeRlDecision(request);
        
        if (response.chosenIndices.isEmpty() || response.chosenIndices.get(0) >= validTypes.size()) {
            return validTypes.iterator().next();
        }
        
        return request.options.get(response.chosenIndices.get(0));
    }

    @Override
    public String chooseSector(Card assignee, String ai, List<String> sectors) {
        return fallbackAi.chooseSector(assignee, ai, sectors);
    }

    @Override
    public List<Card> chooseContraptionsToCrank(List<Card> contraptions) {
        return fallbackAi.chooseContraptionsToCrank(contraptions);
    }

    @Override
    public int chooseSprocket(Card assignee, boolean forceDifferent) {
        return fallbackAi.chooseSprocket(assignee, forceDifferent);
    }

    @Override
    public PlanarDice choosePDRollToIgnore(List<PlanarDice> rolls) {
        return fallbackAi.choosePDRollToIgnore(rolls);
    }

    @Override
    public Integer chooseRollToIgnore(List<Integer> rolls) {
        return fallbackAi.chooseRollToIgnore(rolls);
    }

    @Override
    public List<Integer> chooseDiceToReroll(List<Integer> rolls) {
        return fallbackAi.chooseDiceToReroll(rolls);
    }

    @Override
    public Integer chooseRollToModify(List<Integer> rolls) {
        return fallbackAi.chooseRollToModify(rolls);
    }

    @Override
    public RollDiceEffect.DieRollResult chooseRollToSwap(List<RollDiceEffect.DieRollResult> rolls) {
        return fallbackAi.chooseRollToSwap(rolls);
    }

    @Override
    public String chooseRollSwapValue(List<String> swapChoices, Integer currentResult, int power, int toughness) {
        return fallbackAi.chooseRollSwapValue(swapChoices, currentResult, power, toughness);
    }

    @Override
    public Object vote(SpellAbility sa, String prompt, List<Object> options, ListMultimap<Object, Player> votes, Player forPlayer, boolean optional) {
        return fallbackAi.vote(sa, prompt, options, votes, forPlayer, optional);
    }

    @Override
    public CardCollectionView londonMulliganReturnCards(Player mulliganingPlayer, int cardsToReturn) {
        return fallbackAi.londonMulliganReturnCards(mulliganingPlayer, cardsToReturn);
    }

    @Override
    public boolean confirmMulliganScry(Player p) {
        return fallbackAi.confirmMulliganScry(p);
    }

    @Override
    public boolean playChosenSpellAbility(SpellAbility sa) {
        return fallbackAi.playChosenSpellAbility(sa);
    }

    @Override
    public List<AbilitySub> chooseModeForAbility(SpellAbility sa, List<AbilitySub> possible, int min, int num, boolean allowRepeat) {
        return fallbackAi.chooseModeForAbility(sa, possible, min, num, allowRepeat);
    }

    @Override
    public int chooseNumberForCostReduction(SpellAbility sa, int min, int max) {
        return chooseNumber(sa, "Choose cost reduction", min, max);
    }

    @Override
    public int chooseNumberForKeywordCost(SpellAbility sa, Cost cost, KeywordInterface keyword, String prompt, int max) {
        return chooseNumber(sa, prompt, 0, max);
    }

    @Override
    public int chooseNumber(SpellAbility sa, String title, List<Integer> values, Player relatedPlayer) {
        RlGameState gameState = new RlGameState(getGame(), player);
        RlDecisionRequest request = new RlDecisionRequest(RlDecisionType.CHOOSE_NUMBER, gameState);
        
        for (Integer value : values) {
            request.options.add(value.toString());
        }
        request.metadata.put("title", title);
        
        RlDecisionResponse response = makeRlDecision(request);
        
        if (response.chosenIndices.isEmpty() || response.chosenIndices.get(0) >= values.size()) {
            return values.get(0);
        }
        
        return values.get(response.chosenIndices.get(0));
    }

    @Override
    public boolean chooseBinary(SpellAbility sa, String question, BinaryChoiceType kindOfChoice, Map<String, Object> params) {
        return chooseBinary(sa, question, kindOfChoice, (Boolean) null);
    }

    @Override
    public boolean chooseFlipResult(SpellAbility sa, Player flipper, boolean[] results, boolean call) {
        return fallbackAi.chooseFlipResult(sa, flipper, results, call);
    }

    @Override
    public byte chooseColor(String message, SpellAbility sa, ColorSet colors) {
        return fallbackAi.chooseColor(message, sa, colors);
    }

    @Override
    public byte chooseColorAllowColorless(String message, Card c, ColorSet colors) {
        return fallbackAi.chooseColorAllowColorless(message, c, colors);
    }

    @Override
    public List<String> chooseColors(String message, SpellAbility sa, int min, int max, List<String> options) {
        return fallbackAi.chooseColors(message, sa, min, max, options);
    }

    @Override
    public ICardFace chooseSingleCardFace(SpellAbility sa, String message, Predicate<ICardFace> cpp, String name) {
        return fallbackAi.chooseSingleCardFace(sa, message, cpp, name);
    }

    @Override
    public ICardFace chooseSingleCardFace(SpellAbility sa, List<ICardFace> faces, String message) {
        return fallbackAi.chooseSingleCardFace(sa, faces, message);
    }

    @Override
    public CardState chooseSingleCardState(SpellAbility sa, List<CardState> states, String message, Map<String, Object> params) {
        return fallbackAi.chooseSingleCardState(sa, states, message, params);
    }

    @Override
    public boolean chooseCardsPile(SpellAbility sa, CardCollectionView pile1, CardCollectionView pile2, String faceUp) {
        return fallbackAi.chooseCardsPile(sa, pile1, pile2, faceUp);
    }

    @Override
    public CounterType chooseCounterType(List<CounterType> options, SpellAbility sa, String prompt, Map<String, Object> params) {
        return fallbackAi.chooseCounterType(options, sa, prompt, params);
    }

    @Override
    public String chooseKeywordForPump(List<String> options, SpellAbility sa, String prompt, Card tgtCard) {
        return fallbackAi.chooseKeywordForPump(options, sa, prompt, tgtCard);
    }

    @Override
    public boolean confirmPayment(CostPart costPart, String string, SpellAbility sa) {
        return fallbackAi.confirmPayment(costPart, string, sa);
    }

    @Override
    public ReplacementEffect chooseSingleReplacementEffect(List<ReplacementEffect> possibleReplacers) {
        return fallbackAi.chooseSingleReplacementEffect(possibleReplacers);
    }

    @Override
    public StaticAbility chooseSingleStaticAbility(String prompt, List<StaticAbility> possibleReplacers) {
        return fallbackAi.chooseSingleStaticAbility(prompt, possibleReplacers);
    }

    @Override
    public String chooseProtectionType(String string, SpellAbility sa, List<String> choices) {
        return fallbackAi.chooseProtectionType(string, sa, choices);
    }

    @Override
    public void revealAnte(String message, Multimap<Player, PaperCard> removedAnteCards) {
        fallbackAi.revealAnte(message, removedAnteCards);
    }

    @Override
    public void revealAISkipCards(String message, Map<Player, Map<DeckSection, List<? extends PaperCard>>> deckCards) {
        fallbackAi.revealAISkipCards(message, deckCards);
    }

    @Override
    public Map<DeckSection, List<? extends PaperCard>> complainCardsCantPlayWell(Deck myDeck) {
        return fallbackAi.complainCardsCantPlayWell(myDeck);
    }

    @Override
    public CardCollectionView cheatShuffle(CardCollectionView list) {
        return fallbackAi.cheatShuffle(list);
    }

    @Override
    public void resetAtEndOfTurn() {
        fallbackAi.resetAtEndOfTurn();
    }
    
    @Override
    protected void finalize() throws Throwable {
        if (rlBridge != null) {
            rlBridge.disconnect();
        }
        super.finalize();
    }

    @Override
    public List<OptionalCostValue> chooseOptionalCosts(SpellAbility choosen, List<OptionalCostValue> optionalCostValues) {
        return fallbackAi.chooseOptionalCosts(choosen, optionalCostValues);
    }

    @Override
    public List<CostPart> orderCosts(List<CostPart> costs) {
        return fallbackAi.orderCosts(costs);
    }

    @Override
    public boolean payCostToPreventEffect(Cost cost, SpellAbility sa, boolean alreadyPaid, FCollectionView<Player> allPayers) {
        return fallbackAi.payCostToPreventEffect(cost, sa, alreadyPaid, allPayers);
    }

    @Override
    public boolean payCostDuringRoll(Cost cost, SpellAbility sa, FCollectionView<Player> allPayers) {
        return fallbackAi.payCostDuringRoll(cost, sa, allPayers);
    }

    @Override
    public boolean payCombatCost(Card card, Cost cost, SpellAbility sa, String prompt) {
        return fallbackAi.payCombatCost(card, cost, sa, prompt);
    }

    @Override
    public boolean payManaCost(ManaCost toPay, CostPartMana costPartMana, SpellAbility sa, String prompt, ManaConversionMatrix matrix, boolean effect) {
        return fallbackAi.payManaCost(toPay, costPartMana, sa, prompt, matrix, effect);
    }

    @Override
    public String chooseCardName(SpellAbility sa, Predicate<ICardFace> cpp, String valid, String message) {
        return fallbackAi.chooseCardName(sa, cpp, valid, message);
    }

    @Override
    public String chooseCardName(SpellAbility sa, List<ICardFace> faces, String message) {
        return fallbackAi.chooseCardName(sa, faces, message);
    }

    @Override
    public Card chooseDungeon(Player player, List<PaperCard> dungeonCards, String message) {
        return fallbackAi.chooseDungeon(player, dungeonCards, message);
    }

    @Override
    public Card chooseSingleCardForZoneChange(ZoneType destination, List<ZoneType> origin, SpellAbility sa, CardCollection fetchList, DelayedReveal delayedReveal, String selectPrompt, boolean isOptional, Player decider) {
        return fallbackAi.chooseSingleCardForZoneChange(destination, origin, sa, fetchList, delayedReveal, selectPrompt, isOptional, decider);
    }

    @Override
    public List<Card> chooseCardsForZoneChange(ZoneType destination, List<ZoneType> origin, SpellAbility sa, CardCollection fetchList, int min, int max, DelayedReveal delayedReveal, String selectPrompt, Player decider) {
        return fallbackAi.chooseCardsForZoneChange(destination, origin, sa, fetchList, min, max, delayedReveal, selectPrompt, decider);
    }

    @Override
    public void autoPassCancel() {
        fallbackAi.autoPassCancel();
    }

    @Override
    public void awaitNextInput() {
        fallbackAi.awaitNextInput();
    }

    @Override
    public void cancelAwaitNextInput() {
        fallbackAi.cancelAwaitNextInput();
    }
}