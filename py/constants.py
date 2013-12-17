ENABLE_DEBUG_LOGGING = True
ENABLE_TASK_QUEUE_DEBUG_LOGGING = True

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

ALLOW_DUPLICATE_TASKS_WHEN_RUNNING_LOCALLY = True
FIND_EQUAL_CATEGORIES = True        # check categories with similar stem words (EQUAL_CATEGORY)
SIMILAR_STEM_PERCENTAGE = 30        # categories with at least this percentage of the same stem words should be compared for equality (EQUAL_CATEGORY)
VERIFY_CATEGORIES = True            # verify categories that fit (VERIFY_CATEGORY)

# Whether or not to do fit tasks for subsequent item set at same time as initial set or afterwards
# NOT WORKING if True
# if categories deleted after initial set (because they are duplicates, etc.), need to update 
# fit tasks to use remaining categories so second category creation is correct
# if skip=1 values are lost when categories are regenerated (need to keep somehow; or at least make sure skipped categories not used in future)
# also need to update % complete in admin
CATEGORIZE_SUBSEQUENT_AFTER_INITIAL = False 

# Cascade Settings
CASCADE_INITIAL_ITEM_SET = 0        # set of items to suggest categories for
CASCADE_SUBSEQUENT_ITEM_SET = 1     # set of items that categories are not suggested for (but are included in fit tasks)
ITEM_SET_RATIOS = {}                # number of items to add to initial set followed by subsequent set; initial must by >= 1; keyed by percentage
ITEM_SET_RATIOS[50] = { "initial": 1, "subsequent": 1 } # 50% of items in initial item set
ITEM_SET_RATIOS[67] = { "initial": 2, "subsequent": 1 } # 67% of items in initial item set
ITEM_SET_RATIOS[75] = { "initial": 3, "subsequent": 1 } # 75% of items in initial item set

CASCADE_K = 2                       # redundancy factor used by suggest category and best category tasks
CASCADE_K2 = 1                      # redundancy factor used by fit tasks
CASCADE_M = 50                      # percentage of items placed in initial item set
CASCADE_P = 80                      # % of overlapping items used to detect duplicates and subcategories
CASCADE_Q = 1                       # min number of items allowed in a category
CASCADE_S = 5                       # number of categories grouped together in jobs (e.g., # categories to fit to an idea)
CASCADE_T = 3                       # number of items grouped together in jobs (e.g., # items to suggest categories for)

DEFAULT_VOTING_THRESHOLD = 2        # min number of votes required to pass cascade step (if k>3 or k2>3); 1 otherwise
FIND_SUBCATEGORIES = True           # whether or not to find subcategories in results
MIN_DUPLICATE_SIZE_PERCENTAGE = 50  # categories >= this % in size than others are duplicates if >= p % items overlap
                                    # categories < this % in size than others are subcategories if >= p % items overlap
DELETE_LOOSE_CATEGORIES = False     # whether or not to include categories that contain p % of all items in results
MERGE_NEST_CATEGORIES_AGAIN = False # check for duplicate and nested categories a second time

# Channel
EMPTY_CLIENT_TOKEN = "00000"

STOP_WORDS = [ "a", "about", "all", "am", "an", "and", "any", "are", "as", "at", "be", "been", "being", "but", "by", "can", "did", "do", "for", "from", "get", "had", "has", "he", "her", "here", "him", "his", "how", "I", "if", "in", "into", "is", "it", "its", "just", "my", "of", "on", "only", "or", "our", "put", "said", "she", "so", "some", "than", "that", "the", "them", "they", "their", "there", "this", "to", "was", "we", "went", "were", "what", "when", "where", "which", "who", "will", "with", "without", "you", "your" ];