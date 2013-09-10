ENABLE_DEBUG_LOGGING = True
USE_LOCAL_DATABASE_WHEN_RUNNING_LOCALLY = True # Does not work to use Google SQL instance when running locally yet
ALLOW_DUPLICATE_TASKS_WHEN_RUNNING_LOCALLY = False
FIND_SUBCATEGORIES = True

# Database
CLOUDSQL_INSTANCE = "qa-umd-test:qadb"
DATABASE_NAME = "qa"
LOCAL_DB_USER = "qatest"
LOCAL_DB_PWD = "qatest"

# Cascade Job Types
SUGGEST_CATEGORY = 1
BEST_CATEGORY = 2
FIT_CATEGORY = 3

# Cascade Settings
CASCADE_P = 80                  # % of overlapping items used to detect duplicate categories
CASCADE_Q = 1                   # min number of items allowed in a category
CASCADE_INITIAL_ITEM_SET = 0
CASCADE_SUBSEQUENT_ITEM_SET = 1
DEFAULT_VOTING_THRESHOLD = 2

# Channel
EMPTY_CLIENT_TOKEN = "00000"

STOP_WORDS = [ "all", "also", "and", "any", "been", "did", "for", "not", "had", "now", "she", "that", "the", "this", "was", "were" ]