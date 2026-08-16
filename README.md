# Wordplay

A Python game where you navigate between Wikipedia articles by playing cards representing linked pages.

## How to Play

Start with a Wikipedia article and try to reach the target article.

Playing a card explores that Wikipedia page and adds relevant linked articles to your deck.

Discard unwanted cards to receive replacements.

You win by playing the target article.

You lose if you run out of cards before reaching the target.

The deck has a maximum size of 24 cards.

## Project Structure

game.py — graphical user interface and game interaction.

cards.py — core game state, deck, playing, and discard logic.

helpers.py — Wikipedia API access, article parsing, and link ranking.

## Requirements

Python 3 and:

requests
beautifulsoup4

Install dependencies:

pip install requests beautifulsoup4

## Running

python game.py

The game retrieves Wikipedia article information through the Wikipedia API.
