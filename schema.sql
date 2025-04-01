CREATE TABLE accounts (account_number TEXT PRIMARY KEY, balance REAL);
CREATE TABLE transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, account_number TEXT, amount REAL, type TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE users (username TEXT PRIMARY KEY, password TEXT);
INSERT INTO accounts VALUES ('1234', 375.50);
INSERT INTO transactions (account_number, amount, type, timestamp) VALUES ('1234', 50.0, 'deposit', '2025-03-31 15:37:11');
INSERT INTO transactions (account_number, amount, type, timestamp) VALUES ('1234', 50.0, 'deposit', '2025-03-31 15:53:56');
INSERT INTO users VALUES ('testuser', 'password123');
