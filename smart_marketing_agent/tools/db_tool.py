import sqlite3
import os

def get_products():
    try:
        db_path = os.path.join(os.path.dirname(__file__), "marketing.db")
        print("DB PATH:", db_path) 

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products")

        rows = cursor.fetchall()
        conn.close()

        data = [dict(row) for row in rows]

        print("DATA:", data)  

        return {
            "success": True,
            "data": data
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }