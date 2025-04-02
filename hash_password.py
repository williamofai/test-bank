import sqlite3
import bcrypt

conn = sqlite3.connect('bank.db')
cursor = conn.cursor()

# Hash the password for testuser
password = "password123"
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

# Store the hash as bytes
cursor.execute("UPDATE users SET password = ? WHERE username = ?", (hashed, 'testuser'))

conn.commit()
conn.close()
print("Password hashed successfully!")
