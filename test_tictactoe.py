"""Unit tests for tictactoe.py. No Jev server needed: the HTTP call is mocked.

Run from jev-test/: python3 -m unittest test_tictactoe
"""
import contextlib
import io
import json
import os
import tempfile
import unittest
import urllib.error
from unittest import mock

import tictactoe

URL = "http://127.0.0.1:8080/v1/systemone"
LOCAL_HINT = "Start the local server first"


def board(layout):
    """A board from nine characters, row by row: X, O, or . for an empty square."""
    return {square: None if mark == "." else mark for square, mark in zip(tictactoe.SQUARES, layout)}


def empty_squares(b):
    return [square for square in tictactoe.SQUARES if not b[square]]


def move_answer(choice, **fields):
    return {"answers": {"move": {"choice": choice, **fields}}}


def reply(body):
    """A fake urlopen() response. A str body is sent as is, anything else as JSON."""
    response = mock.MagicMock()
    response.__enter__.return_value.read.return_value = (body if isinstance(body, str) else json.dumps(body)).encode()
    return response


class GameTestCase(unittest.TestCase):
    """Keeps the real score file untouched and the screen output out of the test report."""

    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.score_path = os.path.join(folder, "score.json")
        self.enterContext(mock.patch.object(tictactoe, "SCORE_PATH", self.score_path))
        self.output = self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def type_in(self, *texts):
        return self.enterContext(mock.patch("builtins.input", side_effect=texts))


class WinnerTest(unittest.TestCase):
    def test_every_line_wins(self):
        for name, squares in tictactoe.LINES.items():
            with self.subTest(name):
                layout = "".join("X" if square in squares else "." for square in tictactoe.SQUARES)
                self.assertEqual(tictactoe.winner(board(layout)), "X")

    def test_o_wins(self):
        self.assertEqual(tictactoe.winner(board("OOOXX.X..")), "O")

    def test_no_winner_on_empty_board(self):
        self.assertIsNone(tictactoe.winner(board(".........")))

    def test_no_winner_on_full_drawn_board(self):
        self.assertIsNone(tictactoe.winner(board("XOXXOOOXX")))


class RenderTest(unittest.TestCase):
    def test_shows_marks_and_numbers_of_empty_squares(self):
        self.assertEqual(
            tictactoe.render(board("X...O....")),
            " X | 2 | 3\n---+---+---\n 4 | O | 6\n---+---+---\n 7 | 8 | 9",
        )


class DescribeTest(unittest.TestCase):
    def test_lists_confidence_and_top_three_probabilities(self):
        answer = {"confidence": 0.9, "probabilities": {"3": 0.06, "1": 0.9, "9": 0.01, "7": 0.03}}
        self.assertEqual(
            tictactoe.describe(1, answer),
            "Jev plays 1 (top-left corner, confidence 0.90; 1: 0.90, 3: 0.06, 7: 0.03)",
        )

    def test_without_probabilities(self):
        self.assertEqual(tictactoe.describe(1, {"confidence": 0.9}), "Jev plays 1 (top-left corner, confidence 0.90)")

    def test_without_confidence_or_probabilities(self):
        self.assertEqual(tictactoe.describe(5, {}), "Jev plays 5 (center)")


class AskMoveTest(GameTestCase):
    def ask(self, *texts, layout="........."):
        self.type_in(*texts)
        return tictactoe.ask_move(board(layout), dict(tictactoe.NEW_SCORE), "")

    def test_accepts_an_empty_square(self):
        self.assertEqual(self.ask("5"), 5)

    def test_asks_again_until_the_square_is_valid(self):
        # Blank, text, out of range, a superscript digit, then a taken square.
        self.assertEqual(self.ask("", "abc", "0", "10", "²", "5", "3", layout="....X...."), 3)
        self.assertEqual(self.output.getvalue().count("Pick an empty square by its number."), 6)

    def test_q_quits(self):
        for text in ("q", " Quit "):
            with self.subTest(text), self.assertRaises(SystemExit) as exit_:
                self.ask(text)
            self.assertEqual(exit_.exception.code, 0)


class JevMoveTest(unittest.TestCase):
    def jev_move(self, body, layout="....X...."):
        b = board(layout)
        with mock.patch("urllib.request.urlopen", return_value=reply(body)) as urlopen:
            result = tictactoe.jev_move(b, empty_squares(b))
        self.request = json.loads(urlopen.call_args.args[0].data)
        return result

    def test_returns_move_and_answer(self):
        body = move_answer("1", confidence=0.9)
        self.assertEqual(self.jev_move(body), (1, body["answers"]["move"]))

    def test_offers_only_the_empty_squares(self):
        self.jev_move(move_answer("2"), layout="X...O...X")
        self.assertEqual(list(self.request["questions"]["move"]["criteria"]), ["2", "3", "4", "6", "7", "8"])
        self.assertEqual(self.request["state"]["lines"]["diagonal 1-5-9"], "X O X")

    def test_rejects_a_square_that_is_not_empty(self):
        for choice in ("5", "12"):
            with self.subTest(choice), self.assertRaisesRegex(tictactoe.JevError, "not an empty square"):
                self.jev_move(move_answer(choice))

    def test_rejects_a_reply_without_a_move(self):
        for body in ("<html>proxy error</html>", {"usage": {}}, {"answers": {"move": None}}, move_answer("center")):
            with self.subTest(body), self.assertRaisesRegex(tictactoe.JevError, "could not read a move"):
                self.jev_move(body)


class EndpointTest(unittest.TestCase):
    def endpoint(self, **env):
        with mock.patch.dict(os.environ, env, clear=True):
            return tictactoe.endpoint()

    def test_jev_url_comes_first(self):
        self.assertEqual(
            self.endpoint(JEV_URL="http://jev", JEV_MODEL="m", TYPESAFE_API_KEY="t"),
            ("http://jev", "local", "m"),
        )

    def test_typesafe_before_openrouter(self):
        self.assertEqual(
            self.endpoint(TYPESAFE_API_KEY="t", OPENROUTER_API_KEY="o"),
            ("https://api.typesafe.ai/v1/systemone", "t", "jev-latest"),
        )

    def test_openrouter(self):
        self.assertEqual(
            self.endpoint(OPENROUTER_API_KEY="o"),
            ("https://openrouter.ai/api/v1/systemone", "o", "typesafe/jev-1.13"),
        )

    def test_local_server_when_nothing_is_set(self):
        self.assertEqual(self.endpoint(), (URL, "local", "jev-latest"))


class ScoreFileTest(GameTestCase):
    def write(self, text):
        with open(self.score_path, "w") as f:
            f.write(text)

    def test_round_trip(self):
        tictactoe.save_score({"you": 2, "jev": 1, "draws": 3})
        self.assertEqual(tictactoe.load_score(), {"you": 2, "jev": 1, "draws": 3})

    def test_missing_file_starts_from_zero(self):
        self.assertEqual(tictactoe.load_score(), tictactoe.NEW_SCORE)

    def test_unreadable_file_starts_from_zero(self):
        for text in ("not json", "[1, 2]", "null"):
            with self.subTest(text):
                self.write(text)
                self.assertEqual(tictactoe.load_score(), tictactoe.NEW_SCORE)

    def test_fills_in_missing_counts(self):
        self.write('{"you": 4}')
        self.assertEqual(tictactoe.load_score(), {"you": 4, "jev": 0, "draws": 0})


class PlayTest(GameTestCase):
    def play(self, first, your_moves, jev_moves):
        self.type_in(*map(str, your_moves))
        self.jev = self.enterContext(
            mock.patch.object(tictactoe, "jev_move", side_effect=[(move, {}) for move in jev_moves])
        )
        score = dict(tictactoe.NEW_SCORE)
        tictactoe.play(first, score)
        return score

    def test_you_win(self):
        self.assertEqual(self.play("X", [1, 2, 3], [4, 5]), {"you": 1, "jev": 0, "draws": 0})
        self.assertIn("You win!", self.output.getvalue())

    def test_jev_wins(self):
        self.assertEqual(self.play("O", [4, 5], [1, 2, 3]), {"you": 0, "jev": 1, "draws": 0})
        self.assertIn("Jev wins!", self.output.getvalue())

    def test_draw_and_jev_takes_the_last_square_without_asking(self):
        self.assertEqual(self.play("O", [5, 2, 7, 6], [1, 9, 8, 3]), {"you": 0, "jev": 0, "draws": 1})
        self.assertEqual(self.jev.call_count, 4)
        self.assertIn("Jev plays 4 (last empty square)", self.output.getvalue())

    def test_jev_is_asked_only_about_empty_squares(self):
        self.play("X", [1, 2, 3], [4, 5])
        (_, first_empty), _ = self.jev.call_args_list[0]
        self.assertEqual(first_empty, [2, 3, 4, 5, 6, 7, 8, 9])


class MainErrorTest(GameTestCase):
    """You play 5, then Jev's turn fails."""

    def run_main(self, key="local", **urlopen):
        self.type_in("5")
        self.enterContext(mock.patch.object(tictactoe, "endpoint", return_value=(URL, key, "jev-latest")))
        self.enterContext(mock.patch("urllib.request.urlopen", **urlopen))
        with self.assertRaises(SystemExit) as exit_:
            tictactoe.main()
        return exit_.exception.code

    def test_http_error_shows_status_and_body(self):
        error = urllib.error.HTTPError(URL, 401, "Unauthorized", {}, io.BytesIO(b'{"error": "invalid key"}'))
        message = self.run_main(key="sk-test", side_effect=error)
        self.assertIn('returned HTTP 401: {"error": "invalid key"}', message)
        self.assertNotIn(LOCAL_HINT, message)

    def test_bad_answer(self):
        message = self.run_main(return_value=reply(move_answer("5")))
        self.assertIn("Bad answer from Jev", message)
        self.assertIn("it picked 5, which is not an empty square", message)

    def test_unreachable_local_server_shows_how_to_start_it(self):
        message = self.run_main(side_effect=urllib.error.URLError(ConnectionRefusedError(61, "Connection refused")))
        self.assertIn(f"Could not reach Jev at {URL}", message)
        self.assertIn(LOCAL_HINT, message)

    def test_unreachable_hosted_server_has_no_local_hint(self):
        message = self.run_main(key="sk-test", side_effect=TimeoutError("timed out"))
        self.assertIn(f"Could not reach Jev at {URL}: timed out", message)
        self.assertNotIn(LOCAL_HINT, message)

    def test_score_file_is_not_written_when_a_game_fails(self):
        self.run_main(side_effect=TimeoutError("timed out"))
        self.assertFalse(os.path.exists(self.score_path))


if __name__ == "__main__":
    unittest.main()
