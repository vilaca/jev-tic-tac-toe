#!/usr/bin/env python3
"""Tic-tac-toe in the terminal: you are X (player 1), Jev is O (player 2).

On each of its turns Jev gets the board and one choice question whose options are the
empty squares, so it can only pick a legal move. Jev is a decision model, not a game
engine, so expect it to miss a win or a block now and then.

The endpoint comes from JEV_URL, then TYPESAFE_API_KEY, then OPENROUTER_API_KEY.
With none of them set, it uses the local OpenJev server on 127.0.0.1:8080.
"""
import json
import os
import sys
import urllib.error
import urllib.request

SQUARES = {
    1: "top-left corner", 2: "top edge", 3: "top-right corner",
    4: "left edge", 5: "center", 6: "right edge",
    7: "bottom-left corner", 8: "bottom edge", 9: "bottom-right corner",
}
LINES = {
    "top row": (1, 2, 3),
    "middle row": (4, 5, 6),
    "bottom row": (7, 8, 9),
    "left column": (1, 4, 7),
    "middle column": (2, 5, 8),
    "right column": (3, 6, 9),
    "diagonal 1-5-9": (1, 5, 9),
    "diagonal 3-5-7": (3, 5, 7),
}
INSTRUCTIONS = (
    "You play O in tic-tac-toe against X. Empty squares are shown by their number. "
    "Pick the square for your next move. If a line has two O and one empty square, take it to win. "
    "Otherwise, if a line has two X and one empty square, take it to block X. "
    "Otherwise prefer the center, then a corner, then an edge."
)
TIMEOUT_S = float(os.environ.get("JEV_TIMEOUT", "30"))
SCORE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tictactoe-score.json")
NEW_SCORE = {"you": 0, "jev": 0, "draws": 0}


class JevError(Exception):
    """Jev replied, but not with a legal move."""


def endpoint():
    if os.environ.get("JEV_URL"):
        return os.environ["JEV_URL"], "local", os.environ.get("JEV_MODEL", "jev-latest")
    if os.environ.get("TYPESAFE_API_KEY"):
        return "https://api.typesafe.ai/v1/systemone", os.environ["TYPESAFE_API_KEY"], "jev-latest"
    if os.environ.get("OPENROUTER_API_KEY"):
        return "https://openrouter.ai/api/v1/systemone", os.environ["OPENROUTER_API_KEY"], "typesafe/jev-1.13"
    return "http://127.0.0.1:8080/v1/systemone", "local", "jev-latest"


def cell(board, square):
    return board[square] or str(square)


def render(board):
    rows = (" | ".join(cell(board, square) for square in range(first, first + 3)) for first in (1, 4, 7))
    return "\n---+---+---\n".join(f" {row}" for row in rows)


def winner(board):
    for a, b, c in LINES.values():
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    return None


def jev_move(board, empty):
    state = {
        "you": "O",
        "opponent": "X",
        "board": render(board),
        "lines": {name: " ".join(cell(board, square) for square in squares) for name, squares in LINES.items()},
    }
    questions = {
        "move": {
            "type": "choice",
            "instructions": INSTRUCTIONS,
            "criteria": {str(square): SQUARES[square] for square in empty},
        },
    }
    url, key, model = endpoint()
    body = json.dumps({"model": model, "state": state, "questions": questions}).encode()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    with urllib.request.urlopen(urllib.request.Request(url, body, headers), timeout=TIMEOUT_S) as response:
        reply = response.read().decode(errors="replace")
    try:
        answer = json.loads(reply)["answers"]["move"]
        move = int(answer["choice"])
    except (ValueError, KeyError, TypeError):
        raise JevError(f"could not read a move from the reply: {reply}") from None
    if move not in empty:
        raise JevError(f"it picked {move}, which is not an empty square")
    return move, answer


def describe(move, answer):
    top = sorted(answer.get("probabilities", {}).items(), key=lambda item: item[1], reverse=True)[:3]
    odds = ", ".join(f"{square}: {p:.2f}" for square, p in top)
    confidence = answer.get("confidence")
    confidence_text = f", confidence {confidence:.2f}" if confidence is not None else ""
    odds_text = f"; {odds}" if odds else ""
    return f"Jev plays {move} ({SQUARES[move]}{confidence_text}{odds_text})"


def draw(board, score, *messages):
    # Redraw in place on a terminal; piped output just scrolls.
    if sys.stdout.isatty():
        print("\033[H\033[2J", end="")
    print("Tic-tac-toe: you are X, Jev is O.")
    print(f"Score: you {score['you']}, Jev {score['jev']}, draws {score['draws']}\n\n{render(board)}\n")
    for message in filter(None, messages):
        print(message)


def ask_move(board, score, status):
    while True:
        text = input("Your move (1-9, q to quit): ").strip().lower()
        if text in ("q", "quit"):
            sys.exit(0)
        if text.isdecimal() and int(text) in SQUARES and not board[int(text)]:
            return int(text)
        draw(board, score, status, "Pick an empty square by its number.")


def play(first, score):
    board = dict.fromkeys(SQUARES)
    turn = first
    status = "You go first." if first == "X" else "Jev goes first."
    while True:
        draw(board, score, status)
        if turn == "X":
            move = ask_move(board, score, status)
            board[move] = "X"
            status = f"You played {move}."
        else:
            empty = [square for square in SQUARES if not board[square]]
            if len(empty) == 1:
                move = empty[0]
                status = f"Jev plays {move} (last empty square)"
            else:
                print("Jev is thinking...")
                move, answer = jev_move(board, empty)
                status = describe(move, answer)
            board[move] = "O"

        won = winner(board)
        if won or all(board.values()):
            key, result = {"X": ("you", "You win!"), "O": ("jev", "Jev wins!"), None: ("draws", "Draw.")}[won]
            score[key] += 1
            draw(board, score, status, result)
            return
        turn = "O" if turn == "X" else "X"


def load_score():
    try:
        with open(SCORE_PATH) as f:
            return {**NEW_SCORE, **json.load(f)}
    except (OSError, ValueError, TypeError):  # missing or unreadable file starts from zero
        return dict(NEW_SCORE)


def save_score(score):
    try:
        with open(SCORE_PATH, "w") as f:
            json.dump(score, f)
    except OSError:
        pass


def main():
    first = "X"
    score = load_score()
    try:
        while True:
            play(first, score)
            save_score(score)
            if input("\nPlay again? [y/N] ").strip().lower() != "y":
                return
            first = "O" if first == "X" else "X"
    except (EOFError, KeyboardInterrupt):
        print()
    except urllib.error.HTTPError as e:  # before OSError, which it subclasses
        sys.exit(f"\nJev at {endpoint()[0]} returned HTTP {e.code}: {e.read().decode(errors='replace')}")
    except JevError as e:
        sys.exit(f"\nBad answer from Jev at {endpoint()[0]}: {e}")
    except OSError as e:
        url, key, _ = endpoint()
        hint = ("\nStart the local server first: cd openjev && OPENJEV_BACKEND=mlx ../.venv/bin/python -m openjev\n"
                "No openjev/ folder? Get it from https://github.com/razorback16/openjev (setup steps in README.md).")
        sys.exit(f"\nCould not reach Jev at {url}: {e}{hint if key == 'local' else ''}")


if __name__ == "__main__":
    main()
