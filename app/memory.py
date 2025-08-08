import sqlite3, os, json

SCHEMA = [
'''CREATE TABLE IF NOT EXISTS matches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT,
  source TEXT,
  handle TEXT,
  folder TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);''',
'''CREATE TABLE IF NOT EXISTS profiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER,
  bio TEXT,
  traits_json TEXT,
  last_screenshot_path TEXT,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(match_id) REFERENCES matches(id)
);''',
'''CREATE TABLE IF NOT EXISTS chats (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER,
  history_text TEXT,
  summary TEXT,
  last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(match_id) REFERENCES matches(id)
);''',
'''CREATE TABLE IF NOT EXISTS suggestions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER,
  prompt TEXT,
  suggestions_json TEXT,
  chosen_text TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(match_id) REFERENCES matches(id)
);'''
]

class DB:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        for s in SCHEMA:
            self.conn.execute(s)
        self.conn.commit()

    def upsert_match(self, name, source="phone_link", handle=None, folder=None):
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM matches WHERE name=? AND source=?", (name, source))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute("INSERT INTO matches (name, source, handle, folder) VALUES (?,?,?,?)",
                    (name, source, handle, folder))
        self.conn.commit()
        return cur.lastrowid

    def save_profile(self, match_id, bio, traits_json=None, screenshot_path=None):
        self.conn.execute("INSERT INTO profiles (match_id, bio, traits_json, last_screenshot_path) VALUES (?,?,?,?)",
                          (match_id, bio, traits_json, screenshot_path))
        self.conn.commit()

    def save_chat(self, match_id, history_text, summary=None):
        self.conn.execute("INSERT INTO chats (match_id, history_text, summary) VALUES (?,?,?)",
                          (match_id, history_text, summary))
        self.conn.commit()

    def save_suggestions(self, match_id, prompt, suggestions, chosen_text=None):
        self.conn.execute("INSERT INTO suggestions (match_id, prompt, suggestions_json, chosen_text) VALUES (?,?,?,?)",
                          (match_id, prompt, json.dumps(suggestions, ensure_ascii=False), chosen_text))
        self.conn.commit()
