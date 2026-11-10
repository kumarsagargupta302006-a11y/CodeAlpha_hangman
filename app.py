"""Hangman backend (Flask).

The word is chosen and checked on the server, so players can't peek at the
answer in the browser. Run locally:  python3 app.py
Run in production:                   gunicorn app:app
"""
import os
import random
import uuid
from collections import OrderedDict

from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static")

WORDS = ["python", "program", "keyboard", "network", "variable"]
MAX_WRONG = 6
MAX_GAMES = 1000  # keep memory bounded: oldest games are dropped first

# game_id -> game dict (in memory; use a database/Redis for multi-server setups)
games = OrderedDict()


def new_game():
    game_id = uuid.uuid4().hex
    games[game_id] = {
        "word": random.choice(WORDS),
        "guessed": [],
        "wrong": [],
        "status": "playing",  # playing | won | lost
    }
    while len(games) > MAX_GAMES:
        games.popitem(last=False)
    return game_id, games[game_id]


def public_state(game_id, game):
    """What the browser is allowed to see (the word is hidden until the game is lost)."""
    word = game["word"]
    return {
        "game_id": game_id,
        "masked": [ch if ch in game["guessed"] else None for ch in word],
        "guessed": game["guessed"],
        "wrong_letters": game["wrong"],
        "wrong_left": MAX_WRONG - len(game["wrong"]),
        "max_wrong": MAX_WRONG,
        "status": game["status"],
        "word": word if game["status"] == "lost" else None,
    }


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.post("/api/new")
def api_new():
    game_id, game = new_game()
    return jsonify(public_state(game_id, game)), 201


@app.get("/api/state/<game_id>")
def api_state(game_id):
    game = games.get(game_id)
    if game is None:
        return jsonify(error="Game not found. Start a new game."), 404
    return jsonify(public_state(game_id, game))


@app.post("/api/guess")
def api_guess():
    data = request.get_json(silent=True) or {}
    game_id = data.get("game_id")
    letter = str(data.get("letter", "")).strip().lower()

    game = games.get(game_id)
    if game is None:
        return jsonify(error="Game not found. Start a new game."), 404
    if game["status"] != "playing":
        return jsonify(error="This game is already over."), 400
    if len(letter) != 1 or not ("a" <= letter <= "z"):
        return jsonify(error="Please send a single letter (a-z)."), 400
    if letter in game["guessed"]:
        return jsonify(error="You already guessed that letter."), 400

    game["guessed"].append(letter)
    if letter not in game["word"]:
        game["wrong"].append(letter)

    if all(ch in game["guessed"] for ch in game["word"]):
        game["status"] = "won"
    elif len(game["wrong"]) >= MAX_WRONG:
        game["status"] = "lost"

    return jsonify(public_state(game_id, game))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
