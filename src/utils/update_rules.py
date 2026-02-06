import sqlite3
db_path = '/Users/randylust/.openclaw/workspace/lust-rentals-v2/data/overrides/rules.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("UPDATE categorization_rules SET criteria_field = 'memo' WHERE name LIKE 'Coventry%'")
    conn.commit()
    print("Successfully updated rules")
except sqlite3.Error as e:
    print(f"Error updating rules: {e}")
finally:
    conn.close()

print("done")