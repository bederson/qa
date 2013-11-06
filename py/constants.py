ENABLE_DEBUG_LOGGING = True

# Database
USE_LOCAL_DATABASE_WHEN_RUNNING_LOCALLY = True # does not work to use Google SQL instance when running locally yet
CLOUDSQL_INSTANCE = "qa-umd-test:qadb"
DATABASE_NAME = "qa"
LOCAL_DB_USER = "qatest"
LOCAL_DB_PWD = "qatest"

# Authentication Types (for students)
NO_AUTHENTICATION = 0
GOOGLE_AUTHENTICATION = 1
NICKNAME_AUTHENTICATION = 2

# Cascade Job Types
SUGGEST_CATEGORY = 1
BEST_CATEGORY = 2
EQUAL_CATEGORY = 3
FIT_CATEGORY = 4
VERIFY_CATEGORY = 5

ALLOW_DUPLICATE_TASKS_WHEN_RUNNING_LOCALLY = False
FIND_EQUAL_CATEGORIES = True        # check categories with similar stem words (EQUAL_CATEGORY)
VERIFY_CATEGORIES = True            # verify categories that fit (VERIFY_CATEGORY)

# Cascade Settings
CASCADE_M = 50                      # % of items placed in initial item set (TODO/FIX: code always assumes 50% currently)
CASCADE_P = 80                      # % of overlapping items used to detect duplicates and subcategories
CASCADE_Q = 1                       # min number of items allowed in a category
CASCADE_S = { "min": 4, "max": 6 }  # number of categories grouped together in jobs (e.g., # categories to fit to an idea)
CASCADE_T = 3                       # number of items grouped together in jobs (e.g., # items to suggest categories for)
CASCADE_INITIAL_ITEM_SET = 0        # set of items to suggest categories for
CASCADE_SUBSEQUENT_ITEM_SET = 1

DEFAULT_VOTING_THRESHOLD = 2        # min number of votes required to pass cascade step (if k>3 or k2>3); 1 otherwise
FIND_SUBCATEGORIES = True           # whether or not to find subcategories in results
MIN_DUPLICATE_SIZE_PERCENTAGE = 50  # categories >= this % in size than others are duplicates if >= p % items overlap
                                    # categories < this % in size than others are subcategories if >= p % items overlap
DELETE_LOOSE_CATEGORIES = False     # whether or not to include categories that contain p % of all items in results

# Channel
EMPTY_CLIENT_TOKEN = "00000"

STOP_WORDS = [ "a", "about", "all", "am", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by", "can", "did", "do", "for", "from", "get", "had", "has", "he", "her", "here", "him", "his", "how", "I", "if", "in", "into", "is", "it", "its", "just", "my", "of", "on", "only", "or", "put", "said", "she", "so", "some", "than", "that", "the", "them", "they", "their", "there", "this", "to", "was", "we", "went", "were", "what", "when", "where", "which", "who", "will", "with", "without", "you", "your" ];