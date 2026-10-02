from backend.seed import ADVISORS, seed
from backend.server import Database


def test_seed_creates_advisors_without_agents(tmp_path):
    database_path = str(tmp_path / "seed.db")
    seed(database_path)

    database = Database(database_path)
    try:
        advisors = database.connection.execute(
            "SELECT id, name, email FROM advisors ORDER BY id"
        ).fetchall()
        agents = database.connection.execute("SELECT id FROM agents").fetchall()
    finally:
        database.close()

    assert len(advisors) == len(ADVISORS)
    assert agents == []
