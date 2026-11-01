"""The documented CLI must open with the same preset cards as first web launch."""
import sqlite3

import pytest

from data.card_binding_seed import BOUND_CARD_IDS
from data.seed import USER_ID, generate, main


def bound_ids(path):
    with sqlite3.connect(path) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='agent_card_binding'").fetchone():
            return set()
        return {row[0] for row in conn.execute(
            'SELECT card_id FROM agent_card_binding WHERE user_id=?', (USER_ID,))}


@pytest.mark.parametrize('flags', [[], ['--reset'], ['--bind-cards']])
def test_default_judge_cli_prebinds_all_six_cards(tmp_path, flags):
    db = tmp_path / 'judge.db'
    assert main(['--db', str(db), *flags]) == 0
    assert bound_ids(db) == set(BOUND_CARD_IDS)
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT DISTINCT status FROM card').fetchall() == [('normal',)]


def test_cli_opt_out_keeps_the_empty_binding_fixture(tmp_path):
    db = tmp_path / 'empty.db'
    assert main(['--db', str(db), '--no-bind-cards']) == 0
    assert bound_ids(db) == set()


def test_programmatic_test_seed_keeps_existing_defaults(tmp_path):
    db = tmp_path / 'fixture.db'
    generate(db, months=13)
    assert bound_ids(db) == set()
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT COUNT(*) FROM card').fetchone()[0] == 3


def test_conflicting_card_flags_are_rejected(tmp_path):
    with pytest.raises(SystemExit) as error:
        main(['--db', str(tmp_path / 'invalid.db'), '--bind-cards', '--no-bind-cards'])
    assert error.value.code == 2
