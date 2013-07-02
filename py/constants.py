ENABLE_DEBUG_LOGGING = True
USE_LOCAL_DATABASE_WHEN_RUNNING_LOCALLY = True # Does not work to use Google SQL instance when running locally yet

# Database
CLOUDSQL_INSTANCE = "qa-umd-test:qadb"
DATABASE_NAME = "qa"
LOCAL_DB_USER = "qatest"
LOCAL_DB_PWD = "qatest"

# Phases
PHASE_NOTES = 1
PHASE_CASCADE = 2

# Cascade 
DEFAULT_VOTING_THRESHOLD = 2
NONE_OF_THE_ABOVE = "None of the above"

# Channel
EMPTY_CLIENT_TOKEN = "00000"

STOP_WORDS = [ "all", "also", "and", "any", "been", "did", "for", "not", "had", "now", "she", "that", "the", "this", "was", "were" ]