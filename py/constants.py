ENABLE_DEBUG_LOGGING = True
USE_LOCAL_DATABASE_WHEN_RUNNING_LOCALLY = True # Does not work to use Google SQL instance when running locally yet
ALLOW_DUPLICATE_TASKS_WHEN_RUNNING_LOCALLY = False
FIND_SUBCATEGORIES = True
FIND_EQUAL_CATEGORIES = True
VERIFY_CATEGORIES = False

# Database
CLOUDSQL_INSTANCE = "qa-umd-test:qadb"
DATABASE_NAME = "qa"
LOCAL_DB_USER = "qatest"
LOCAL_DB_PWD = "qatest"

# Cascade Job Types
SUGGEST_CATEGORY = 1
BEST_CATEGORY = 2
EQUAL_CATEGORY = 3
FIT_CATEGORY = 4
VERIFY_CATEGORY = 5

# Cascade Settings
CASCADE_P = 80                  # % of overlapping items used to detect duplicate and nested categories
CASCADE_Q = 1                   # min number of items allowed in a category
CASCADE_S = 4
CASCADE_T = 3
CASCADE_INITIAL_ITEM_SET = 0
CASCADE_SUBSEQUENT_ITEM_SET = 1
DEFAULT_VOTING_THRESHOLD = 2
MIN_DUPLICATE_SIZE_PERCENTAGE = 50  # a duplicate category must be this % or greater in size than the category being kept

# Channel
EMPTY_CLIENT_TOKEN = "00000"

STOP_WORDS = [ "a", "about", "all", "am", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by", "can", "did", "do", "for", "from", "get", "had", "has", "he", "here", "his", "how", "I", "if", "in", "into", "is", "it", "its", "of", "on", "only", "or", "put", "said", "she", "so", "some", "than", "that", "the", "them", "they", "their", "there", "this", "to", "was", "we", "went", "were", "what", "when", "where", "which", "who", "will", "with", "without", "you", "your" ];