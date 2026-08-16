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

    def _rank_by_closeness(self, candidates):
        """Sort candidates so titles that appear directly on the target
        article's own page come first.

        There's no real graph-distance signal available -- only page links
        -- so this is a proxy: a title that shows up among the target's own
        most-frequent links is one hop away from the goal, which is about
        as "close" as a replacement card can get. Everything else keeps its
        existing relative order (Python's sort is stable), so the pool
        doesn't get shuffled, just biased toward the goal.
        """
        target_links = {t.lower() for t in most_frequent_links(self.target_title, limit=12)}
        return sorted(candidates, key=lambda title: title.lower() not in target_links)

    def _fill_replacements(self, count, exclude=None):
        """Return up to `count` fresh candidate titles not already in the
        deck, already played, or in ``exclude``. Capped so the deck never
        exceeds MAX_DECK_SIZE. Candidates closer to the target are
        preferred.

        The ``exclude`` parameter lets callers (like `discard_cards`) mark
        recently-removed cards as ineligible for immediate replacement.
        """
        room = MAX_DECK_SIZE - len(self.deck)
        count = min(count, room)
        if count <= 0:
            return []

        seen = self._seen_cards()
        if exclude:
            for ex in exclude:
                seen.add(normalize_title(ex).lower())

        replacements = []
        ranked_candidates = self._rank_by_closeness(self._candidate_cards())
        for candidate in ranked_candidates:
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

        Every 5 cards discarded earns 1 replacement card, rounded down:
        discarding 1-4 cards earns nothing, discarding 5-9 earns 1,
        discarding 10-14 earns 2, and so on. This makes discarding a much
        steeper trade -- replacements (which are biased toward the target)
        are earned slowly, so churning the deck is a real cost, not a
        near-free way to fish for better cards.
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

        replacements = self._fill_replacements(len(discarded) // 5, exclude=discarded)
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
