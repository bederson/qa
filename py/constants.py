ENABLE_DEBUG_LOGGING = True
USE_LOCAL_DATABASE_WHEN_RUNNING_LOCALLY = True # Does not work to use Google SQL instance when running locally yet
ALLOW_DUPLICATE_TASKS_WHEN_RUNNING_LOCALLY = False

# Database
CLOUDSQL_INSTANCE = "qa-umd-test:qadb"
DATABASE_NAME = "qa"
LOCAL_DB_USER = "qatest"
LOCAL_DB_PWD = "qatest"

# Phases
PHASE_NOTES = 1
PHASE_CASCADE = 2

# Job Types
ADD_NOTE = 1
SUGGEST_CATEGORY = 2
BEST_CATEGORY = 3
MATCH_CATEGORY = 4
VERIFY_CATEGORY = 5

# Cascade 
SKIP_VERIFY_CATEGORY = True
DEFAULT_VOTING_THRESHOLD = 2
CASCADE_Q = 1                   # min number of items allowed in a category
CASCADE_MAX_ITERATIONS = 1      # max number of iterations allowed
CASCADE_MAX_UNCATEGORIZED = 5   # max number uncategorized items (w/o going over max # iterations)

# Channel
EMPTY_CLIENT_TOKEN = "00000"

STOP_WORDS = [ "all", "also", "and", "any", "been", "did", "for", "not", "had", "now", "she", "that", "the", "this", "was", "were" ]