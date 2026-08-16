from helpers import most_frequent_links, normalize_title

# Hard ceiling on deck size. Keeps the "flood" side of the game in check
# so that discarding is a real decision (making room) rather than a purely
# optional bonus, and gives _fill_replacements a natural stopping point.
MAX_DECK_SIZE = 24


class WikiDeckGame:
    def __init__(self, start_title, target_title):
        self.start_title = normalize_title(start_title)
        self.target_title = normalize_title(target_title)
        self.deck = [self.start_title]
        self.played = []

    def _dedupe(self, values):
        seen = set()
        unique = []
        for value in values:
            key = normalize_title(value).lower()
            if key not in seen:
                unique.append(normalize_title(value))
                seen.add(key)
        return unique

    def _seen_cards(self):
        return {normalize_title(card).lower() for card in self.deck + self.played}

    def _candidate_cards(self):
        """Titles to draw replacement cards from.

        This is a living pool rather than a fixed one: it's rebuilt from
        every article the player has actually played, so it grows as the
        game progresses and can't be drained the way a fixed pair of
        sources could. Before anything has been played yet, it falls back
        to the start article to bootstrap the very first discard. The
        target article's links are always included too, so there's a
        constant thread of "useful territory" pointing toward the goal.
        """
        sources = list(self.played) if self.played else [self.start_title]
        sources.append(self.target_title)

        candidates = []
        for title in sources:
            candidates.extend(most_frequent_links(title, limit=6))
        return self._dedupe(candidates)

    def _fill_replacements(self, count):
        """Return up to `count` fresh candidate titles not already in the
        deck or already played, capped so the deck never exceeds
        MAX_DECK_SIZE."""
        room = MAX_DECK_SIZE - len(self.deck)
        count = min(count, room)
        if count <= 0:
            return []

        seen = self._seen_cards()
        replacements = []
        for candidate in self._candidate_cards():
            key = normalize_title(candidate).lower()
            if key in seen:
                continue
            replacements.append(normalize_title(candidate))
            seen.add(key)
            if len(replacements) == count:
                break
        return replacements

    def discard_cards(self, card_titles):
        """Discard a specific set of cards the player selected from the deck.

        Every 2 cards discarded earns 1 replacement card, rounded down:
        discarding 1 card earns nothing, discarding 2 earns 1, discarding 3
        still only earns 1, discarding 4 earns 2, and so on. This rewards
        discarding in pairs (or more) over discarding one at a time.
        """
        if not card_titles:
            raise ValueError("Select at least one card to discard.")

        clean_titles = [normalize_title(title) for title in card_titles]

        if len(clean_titles) != len({title.lower() for title in clean_titles}):
            raise ValueError("Each card can only be selected once.")

        deck_lower = {card.lower() for card in self.deck}
        for title in clean_titles:
            if title.lower() not in deck_lower:
                raise ValueError(f"{title!r} is not in the current deck.")

        # Remove exactly the selected cards, wherever they sit in the deck.
        discarded = []
        remaining = list(self.deck)
        for title in clean_titles:
            key = title.lower()
            for card in remaining:
                if card.lower() == key:
                    discarded.append(card)
                    remaining.remove(card)
                    break
        self.deck = remaining

        replacements = self._fill_replacements(len(discarded) // 2)
        self.deck.extend(replacements)

        return discarded, replacements

    def choose_card(self, card_title):
        clean_title = normalize_title(card_title)

        if clean_title not in self.deck:
            raise ValueError(f"{clean_title!r} is not in the current deck.")

        self.deck.remove(clean_title)
        self.played.append(clean_title)

        if clean_title.lower() == self.target_title.lower():
            return {"won": True, "played": clean_title}

        # All qualifying links found on the played article's page. Not all
        # of these will actually be added -- some may already be in the
        # deck or already played.
        linked_cards = self._dedupe(most_frequent_links(clean_title, limit=6))

        seen_cards = self._seen_cards()
        added_cards = []
        for card in linked_cards:
            if len(self.deck) >= MAX_DECK_SIZE:
                break
            clean_card = normalize_title(card)
            if clean_card.lower() not in seen_cards:
                self.deck.append(clean_card)
                seen_cards.add(clean_card.lower())
                added_cards.append(clean_card)

        return {
            "won": False,
            "played": clean_title,
            "linked_cards": linked_cards,
            "added_cards": added_cards,
        }

    @property
    def current_cards(self):
        return list(self.deck)