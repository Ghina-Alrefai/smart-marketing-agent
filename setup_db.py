# setup_db.py

import sqlite3

conn = sqlite3.connect("marketing.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    description TEXT,
    benefits TEXT
)
""")

cursor.execute("DELETE FROM products")  

products = [
   ("iPhone 17 Pro Max", "Flagship Apple phone with powerful A19 Pro chip and advanced camera system", "fast performance, premium design, excellent camera"),
("Samsung Galaxy S26", "High-end Samsung phone with AMOLED display and AI features", "vivid display, strong performance, smart features"),
("Google Pixel 10 Pro XL", "Google phone with pure Android experience and AI-powered photography", "best camera processing, clean system, fast updates"),
("OnePlus 13 5G", "Powerful smartphone with fast charging and smooth performance", "super fast charging, affordable flagship, smooth usage"),
("Samsung Galaxy A57 5G", "Mid-range phone with large battery and 120Hz display", "long battery life, good price, reliable daily use")
]

cursor.executemany("""
INSERT INTO products (name, description, benefits)
VALUES (?, ?, ?)
""", products)

conn.commit()
conn.close()

print("Database ready!")