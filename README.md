

You can use pandas and sqlite3 in Python to read an Excel file and insert the data into SQLite. Below is a complete script that does this:

Steps:

1. Install dependencies (if not installed):

pip install pandas openpyxl sqlite3


2. Use the script below to read the Excel file and insert data into SQLite.




---

Python Script:

import pandas as pd
import sqlite3

# Define database and Excel file paths
db_path = "mydatabase.db"
excel_path = "mydata.xlsx"  # Change this to your actual file

# Connect to SQLite database (creates it if it doesn't exist)
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create the table if it doesn't exist
cursor.execute('''
CREATE TABLE IF NOT EXISTS my_table (
    my_id INTEGER PRIMARY KEY,  -- Adjust if your primary key is different
    col1 TEXT,
    col2 TEXT,
    col3 TEXT,
    col4 TEXT,
    col5 INTEGER,
    col6 INTEGER,
    col7 REAL,
    col8 BLOB
);
''')

# Read Excel file
df = pd.read_excel(excel_path, engine="openpyxl")

# Convert BLOB column (col8) to binary if necessary
def convert_to_blob(value):
    if pd.isna(value):  # Handle NaN values
        return None
    return value.encode() if isinstance(value, str) else value

df["col8"] = df["col8"].apply(convert_to_blob)

# Insert data into SQLite
for _, row in df.iterrows():
    cursor.execute('''
        INSERT INTO my_table (my_id, col1, col2, col3, col4, col5, col6, col7, col8)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (row["my_id"], row["col1"], row["col2"], row["col3"], row["col4"], row["col5"], row["col6"], row["col7"], row["col8"]))

# Commit changes and close connection
conn.commit()
conn.close()

print("Data successfully inserted into SQLite!")


---

Explanation:

Reads an Excel file using pandas.read_excel().

Creates a SQLite database and table if it doesn't exist.

Converts BLOB data if necessary.

Iterates over rows and inserts data using sqlite3.execute().

Commits changes and closes the database connection.


Would you like a script to verify if data is correctly inserted?



