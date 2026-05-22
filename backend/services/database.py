from pymongo import ASCENDING, MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError

from config import MONGO_DB_NAME, MONGO_URI


_client = None
_db = None


def get_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(MONGO_URI)
        _db = _client[MONGO_DB_NAME]
    return _db


def init_db():
    db = get_db()
    db["Users"].create_index("email", unique=True)
    db["Users"].create_index("userId", unique=True)
    db["Movies"].create_index("movieId", unique=True)
    db["Movies"].create_index([("title", ASCENDING), ("genres", ASCENDING)])
    db["Ratings"].create_index([("userId", ASCENDING), ("movieId", ASCENDING)], unique=True)
    db["Ratings"].create_index("movieId")
    db["WatchHistory"].create_index([("userId", ASCENDING), ("timestamp", ASCENDING)])
    db["Counters"].create_index("name", unique=True)
    return db


def get_next_sequence(name, start=1):
    db = get_db()
    if not db["Counters"].find_one({"name": name}):
        try:
            db["Counters"].insert_one({"name": name, "value": int(start)})
            return int(start)
        except DuplicateKeyError:
            pass
    result = db["Counters"].find_one_and_update(
        {"name": name},
        {"$inc": {"value": 1}},
        return_document=ReturnDocument.AFTER,
    )
    return int(result["value"])
