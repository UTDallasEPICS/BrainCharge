import sqlite3
import os


DATABASE_PATH = os.path.join(
    #This is where database data will be stored
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "braincharge.db"
)

SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__),
    "schema.sql"
)


def get_connection():
    #Creates and returns a connection to the SQLite database.
    #Create data folder if it does not exist
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    return connection


def initialize_database():

    #Creates database tables if they do not exist.
    connection = get_connection()
    cursor = connection.cursor()

    with open(SCHEMA_PATH, "r") as schema:
        schema_sql = schema.read()
        cursor.executescript(schema_sql)

    connection.commit()
    connection.close()


if __name__ == "__main__":
    initialize_database()
    print("Database initialized!")