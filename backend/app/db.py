"""SQLite access and seed data."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from .paths import DATA_DIR

DB_PATH = DATA_DIR / "app.db"

# The categories the built-in topics are shown under, in this order.
CATEGORIES = ["Everyday", "Work", "School", "Shopping", "Food", "Travel", "Services", "Home", "Opinions"]

# Built-in topics: (title, the situation the tutor plays out, the tutor's opening line in German,
# category). New topics go at the end: a topic's place here decides its id in a new database.
SEED_TOPICS = [
    (
        "Small talk",
        "A relaxed chat between two acquaintances about everyday life.",
        "Hallo! Schön, dich zu sehen. Wie war deine Woche bisher?",
        "Everyday",
    ),
    (
        "Introducing yourself",
        "Two people meet for the first time at a social event and get to know each other.",
        "Hallo, ich glaube, wir kennen uns noch nicht. Ich bin Alex. Wie heißt du, und was machst du so?",
        "Everyday",
    ),
    (
        "At a café",
        "The tutor is a barista taking the learner's order at a café.",
        "Guten Morgen! Herzlich willkommen. Was darf es für Sie sein?",
        "Food",
    ),
    (
        "Travel plans",
        "Two friends talk about a trip the learner is planning or has taken.",
        "Ich habe gehört, du planst eine Reise. Wohin möchtest du denn fahren?",
        "Travel",
    ),
    (
        "Weekend and hobbies",
        "A friendly chat about what the learner does in their free time.",
        "Und, was machst du am Wochenende normalerweise gern?",
        "Everyday",
    ),
    (
        "A meeting at work",
        "The tutor is a colleague catching up with the learner on a project before a meeting.",
        "Danke, dass du dabei bist. Bevor wir anfangen: Woran hast du diese Woche gearbeitet?",
        "Work",
    ),
    # Everyday
    (
        "Talking about the weather",
        "Two neighbours run into each other outside and chat about the weather and their day.",
        "Morgen! Was für ein Wetter heute, oder? Wie geht es Ihnen?",
        "Everyday",
    ),
    (
        "Making plans with a friend",
        "The tutor is a friend of the learner, and the two decide what to do together this weekend.",
        "Hey! Hast du am Wochenende Zeit? Ich dachte, wir könnten zusammen etwas unternehmen.",
        "Everyday",
    ),
    # Work
    (
        "Daily stand-up",
        "The tutor leads a team's short daily meeting, where each person says what they did, "
        "what they will do next, and what is in their way.",
        "Guten Morgen zusammen. Fangen wir mit dir an. Was hast du gestern geschafft?",
        "Work",
    ),
    (
        "Asking a colleague for help",
        "The tutor is a colleague at the next desk; the learner is stuck on a task and needs their help.",
        "Hey, du siehst ein bisschen ratlos aus. Ist alles in Ordnung?",
        "Work",
    ),
    (
        "A status update for your manager",
        "The tutor is the learner's manager in a one-on-one meeting about how a project is going.",
        "Danke, dass du dir Zeit nimmst. Wie läuft das Projekt? Liegen wir noch im Zeitplan?",
        "Work",
    ),
    (
        "A call with a client",
        "The tutor is a client on a phone call with the learner about what they need and by when.",
        "Hallo, danke für Ihren Anruf. Ich wollte mit Ihnen besprechen, was wir von Ihrem Team brauchen. Passt es gerade?",
        "Work",
    ),
    # School
    (
        "Asking a professor a question",
        "The tutor is a professor in their office hours; the learner is a student with a question "
        "about the course.",
        "Kommen Sie herein, nehmen Sie Platz. Wobei kann ich Ihnen helfen?",
        "School",
    ),
    (
        "A group project",
        "The tutor is a classmate; the two plan a group project and decide who does what.",
        "Also, das Projekt ist in zwei Wochen fällig. Wie sollen wir die Arbeit aufteilen?",
        "School",
    ),
    (
        "Introducing yourself in class",
        "The tutor is a teacher on the first day of a class, getting to know a new student.",
        "Willkommen im Kurs! Kannst du uns ein bisschen von dir erzählen?",
        "School",
    ),
    (
        "Chatting with a classmate",
        "The tutor is a classmate chatting with the learner after class about the lecture and "
        "their plans.",
        "Die Vorlesung war ganz schön viel auf einmal! Wie fandest du sie?",
        "School",
    ),
    # Shopping
    (
        "At a market",
        "The tutor sells fruit and vegetables at an outdoor market; the learner wants to buy "
        "some and asks about prices.",
        "Hallo! Alles ganz frisch heute Morgen. Was darf es sein?",
        "Shopping",
    ),
    (
        "Buying clothes",
        "The tutor is a shop assistant in a clothing store, helping the learner find the right "
        "item and size.",
        "Hallo, herzlich willkommen! Suchen Sie etwas Bestimmtes?",
        "Shopping",
    ),
    (
        "Returning an item",
        "The tutor works at a store's customer service desk; the learner wants to return or "
        "exchange something they bought.",
        "Hallo, wie kann ich Ihnen helfen?",
        "Shopping",
    ),
    (
        "At the supermarket checkout",
        "The tutor is a cashier at a supermarket, ringing up the learner's groceries.",
        "Hallo! Haben Sie alles gefunden, was Sie gesucht haben?",
        "Shopping",
    ),
    # Food
    (
        "Ordering at a restaurant",
        "The tutor is a server at a restaurant, taking the learner's order for a meal.",
        "Guten Abend und herzlich willkommen. Darf ich Ihnen schon etwas zu trinken bringen, während Sie in die Karte schauen?",
        "Food",
    ),
    (
        "Booking a table by phone",
        "The tutor answers the phone at a restaurant; the learner calls to book a table.",
        "Vielen Dank für Ihren Anruf. Was kann ich für Sie tun?",
        "Food",
    ),
    (
        "A problem with your order",
        "The tutor is a server at a restaurant; something is wrong with what the learner was "
        "served, and the learner says so politely.",
        "Hallo, schmeckt es Ihnen bisher?",
        "Food",
    ),
    # Travel
    (
        "Airport check-in",
        "The tutor works at an airline's check-in desk; the learner is checking in for a flight "
        "with a bag.",
        "Guten Morgen! Wohin fliegen Sie heute? Darf ich bitte Ihren Reisepass sehen?",
        "Travel",
    ),
    (
        "Hotel check-in",
        "The tutor is a hotel receptionist; the learner arrives with a reservation and has a few "
        "questions about the stay.",
        "Guten Tag und herzlich willkommen! Haben Sie bei uns reserviert?",
        "Travel",
    ),
    (
        "Asking for directions",
        "The learner is a visitor who is lost in a city; the tutor is a local on the street who "
        "knows the way.",
        "Hallo! Sie sehen ein bisschen verloren aus. Kann ich Ihnen helfen?",
        "Travel",
    ),
    (
        "At immigration",
        "The tutor is an immigration officer at an airport, asking the learner about their visit.",
        "Der Nächste, bitte. Guten Tag. Was ist der Zweck Ihrer Reise?",
        "Travel",
    ),
    # Services
    (
        "At the doctor's",
        "The tutor is a doctor; the learner is a patient who is not feeling well and describes "
        "their symptoms.",
        "Guten Tag, setzen Sie sich bitte. Was führt Sie zu mir?",
        "Services",
    ),
    (
        "At a pharmacy",
        "The tutor is a pharmacist; the learner needs something for a minor health problem and "
        "asks how to take it.",
        "Guten Tag. Was kann ich für Sie tun?",
        "Services",
    ),
    (
        "At the bank",
        "The tutor works at a bank; the learner wants to open an account or has a question about "
        "theirs.",
        "Guten Morgen! Was kann ich heute für Sie tun?",
        "Services",
    ),
    (
        "Calling customer service",
        "The tutor is a customer service agent on the phone; the learner calls about a problem "
        "with a product or a bill.",
        "Vielen Dank, dass Sie den Kundenservice anrufen. Wie kann ich Ihnen helfen?",
        "Services",
    ),
    # Home
    (
        "Talking to your landlord",
        "The tutor is the learner's landlord; the learner tells them about something in the "
        "apartment that needs fixing.",
        "Hallo, schön, von Ihnen zu hören. Ist mit der Wohnung alles in Ordnung?",
        "Home",
    ),
    (
        "Meeting a new neighbour",
        "The learner has just moved in; the tutor is a neighbour who lives next door and says hello.",
        "Hallo! Sie sind bestimmt gerade hier eingezogen. Ich wohne nebenan. Wie läuft der Umzug?",
        "Home",
    ),
    (
        "Calling a repair service",
        "The tutor answers the phone at a repair company; the learner calls because something at "
        "home is broken and books a visit.",
        "Guten Tag, danke für Ihren Anruf. Was ist denn das Problem?",
        "Home",
    ),
    (
        "Viewing an apartment",
        "The tutor is an agent showing the learner an apartment for rent; the learner asks about "
        "the place, the rent, and the area.",
        "Hallo, schön, dass Sie da sind! Kommen Sie rein. Das ist das Wohnzimmer. Wie gefällt es Ihnen bisher?",
        "Home",
    ),
    # Opinions: no role to play; the learner talks at more length about what they think.
    (
        "A movie or show you watched",
        "A friendly chat in which the learner describes a movie or show they watched and says "
        "what they thought of it. The tutor asks for details and reasons.",
        "Ich suche gerade etwas Gutes zum Anschauen. Welchen Film oder welche Serie hast du zuletzt gesehen?",
        "Opinions",
    ),
    (
        "Your hometown",
        "A friendly chat in which the learner describes the place they come from and what they "
        "like and dislike about it. The tutor asks for details and reasons.",
        "Erzähl mal, wo kommst du eigentlich her? Wie ist es in deiner Heimatstadt?",
        "Opinions",
    ),
    (
        "Working from home or at the office",
        "A friendly discussion of whether it is better to work from home or at the office. The "
        "tutor asks for the learner's opinion and reasons, and sometimes gently takes the other side.",
        "Manche lieben das Homeoffice, andere halten es gar nicht aus. Wie ist das bei dir?",
        "Opinions",
    ),
    (
        "Something you read recently",
        "A friendly chat in which the learner sums up a book or an article they read and says "
        "what they thought of it. The tutor asks for details and reasons.",
        "Hast du in letzter Zeit etwas Interessantes gelesen? Worum ging es?",
        "Opinions",
    ),
    (
        "Your plans for next year",
        "A friendly chat about what the learner wants to do or change next year and why. The "
        "tutor asks for details and reasons.",
        "Das Jahr vergeht so schnell! Gibt es etwas, das du nächstes Jahr machen oder ändern möchtest?",
        "Opinions",
    ),
]


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """A connection for one block of work: what the block changed is saved when it ends and
    dropped when it fails, and the connection is closed either way. Leaving it open would
    keep the database file locked on Windows."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _add_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    """Add a column to a table made by an earlier version of the app, unless it is there."""
    if column not in [found["name"] for found in conn.execute(f"PRAGMA table_info({table})")]:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL UNIQUE,
                situation TEXT NOT NULL,
                opener TEXT NOT NULL
            )
            """
        )
        # 1 for a topic the learner added; the built-in ones cannot be removed.
        _add_column(conn, "topics", "custom", "INTEGER NOT NULL DEFAULT 0")
        # The category a built-in topic is shown under; empty for the learner's own topics.
        _add_column(conn, "topics", "category", "TEXT")
        # Adds the built-in topics a database of an earlier version does not have yet. A title the
        # learner already used for a topic of their own is left to them.
        # What the tutor knows besides the situation: the summary of the text a topic was made from.
        _add_column(conn, "topics", "background", "TEXT")
        # Only the missing ones are inserted: an insert that is ignored still uses up an id.
        known = {row["title"] for row in conn.execute("SELECT title FROM topics")}
        conn.executemany(
            "INSERT INTO topics (title, situation, opener, category) VALUES (?, ?, ?, ?)",
            [topic for topic in SEED_TOPICS if topic[0] not in known],
        )
        conn.executemany(
            "UPDATE topics SET category = ? WHERE title = ? AND custom = 0",
            [(category, title) for title, _, _, category in SEED_TOPICS],
        )
        conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        # A conversation keeps its topic's title and situation, so it stays readable (and the
        # tutor can still reply in it) after the topic is changed or removed.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_id INTEGER REFERENCES topics(id) ON DELETE SET NULL,
                title TEXT NOT NULL,
                situation TEXT NOT NULL,
                started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                review TEXT,
                background TEXT
            )
            """
        )
        # `review` (JSON, written when a conversation is wrapped up) was added after the first
        # conversations were saved.
        _add_column(conn, "conversations", "review", "TEXT")
        # A copy of the topic's background, kept like its title and situation.
        _add_column(conn, "conversations", "background", "TEXT")
        # One line of a conversation, in the order they were said. The delivery columns and the
        # correction columns are filled for the learner's lines only.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK (role IN ('tutor', 'learner')),
                text TEXT NOT NULL,
                clarity INTEGER,
                unclear_words TEXT,
                words_per_minute INTEGER,
                correction_original TEXT,
                correction_improved TEXT,
                correction_explanation TEXT,
                practiced INTEGER NOT NULL DEFAULT 0,
                practiced_at TEXT,
                corrected_at TEXT,
                dismissed INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        # How often a correction's better sentence was said correctly afterwards, and when last;
        # added after the first conversations were saved.
        _add_column(conn, "messages", "practiced", "INTEGER NOT NULL DEFAULT 0")
        _add_column(conn, "messages", "practiced_at", "TEXT")
        # The learner's progress on a sentence pattern; the patterns themselves are in the code.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pattern_progress (
                pattern_id TEXT PRIMARY KEY,
                sessions INTEGER NOT NULL DEFAULT 0,
                last_correct INTEGER,
                last_total INTEGER,
                practiced_at TEXT
            )
            """
        )
        # A YouTube video saved to study with. Only its subtitles are kept, as sentences with
        # the seconds between which each is said; the video is played by YouTube's own player.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT '',
                language TEXT NOT NULL,
                generated INTEGER NOT NULL DEFAULT 0,
                added_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            )
            """
        )
        # The CEFR level (A1-C2) of a video's German: estimated when it is added, or set by
        # the learner; empty while neither has happened.
        _add_column(conn, "videos", "level", "TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS video_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
                position INTEGER NOT NULL,
                start REAL NOT NULL,
                end REAL NOT NULL,
                text TEXT NOT NULL,
                shadowed INTEGER NOT NULL DEFAULT 0,
                best INTEGER
            )
            """
        )
        # How often a sentence was shadowed and the best score (0-100) so far; added after the
        # first videos were saved.
        _add_column(conn, "video_lines", "shadowed", "INTEGER NOT NULL DEFAULT 0")
        _add_column(conn, "video_lines", "best", "INTEGER")
        conn.execute("CREATE INDEX IF NOT EXISTS video_lines_by_video ON video_lines (video, position)")
        # A sentence of a video in the learner's language, written when the learner asks for the
        # translation; one for each language it was asked in.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS line_translations (
                line INTEGER NOT NULL REFERENCES video_lines(id) ON DELETE CASCADE,
                language TEXT NOT NULL,
                text TEXT NOT NULL,
                PRIMARY KEY (line, language)
            )
            """
        )
        # A sentence pattern the learner made from a sentence of a video. The sentence is kept
        # as its example, so the pattern outlives the video.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS own_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern TEXT NOT NULL UNIQUE,
                use TEXT NOT NULL,
                example TEXT NOT NULL,
                line INTEGER REFERENCES video_lines(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            )
            """
        )
        # A sentence got wrong in pattern practice, kept to be practised again next to the
        # corrections of conversations. One row for each sentence asked for; a new wrong try
        # at it replaces what was said.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pattern_mistakes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_id TEXT NOT NULL,
                pattern TEXT NOT NULL,
                prompt TEXT NOT NULL,
                said TEXT NOT NULL,
                improved TEXT NOT NULL,
                explanation TEXT NOT NULL DEFAULT '',
                practiced INTEGER NOT NULL DEFAULT 0,
                practiced_at TEXT,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                UNIQUE (pattern_id, prompt)
            )
            """
        )
        # When a line's correction was made, to order it among the pattern mistakes, and whether
        # the learner took it off the list of corrections (it stays in its conversation).
        _add_column(conn, "messages", "corrected_at", "TEXT")
        _add_column(conn, "messages", "dismissed", "INTEGER NOT NULL DEFAULT 0")
        conn.execute("CREATE INDEX IF NOT EXISTS messages_by_conversation ON messages (conversation_id, id)")
