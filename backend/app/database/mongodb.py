import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "studyai")

try:
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    db = client[DATABASE_NAME]
    users_collection = db["users"]
    students_collection = db["students"]
    predictions_collection = db["predictions"]
    study_plans_collection = db["study_plans"]
    sessions_collection = db["sessions"]
    quizzes_collection = db["quizzes"]
    notes_collection = db["notes"]
except Exception as e:
    print(f"Warning: MongoDB connection error: {e}")
    client = None
    db = None
    users_collection = None
    students_collection = None
    predictions_collection = None
    study_plans_collection = None
    sessions_collection = None
    quizzes_collection = None
    notes_collection = None