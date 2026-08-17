from __future__ import annotations

MODEL_VERSION = "brand-dna-1.1.0"
SKLEARN_ARTIFACT_VERSION = "1.8.0"
TEXT_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
IMAGE_MODEL_NAME = "sentence-transformers/clip-ViT-B-32"
TARGET_COLUMN = "Performance_Class"
RANDOM_STATE = 42
N_SPLITS = 5
LOGISTIC_C = 0.01
ONE_HOT_MIN_FREQUENCY = 2

CATEGORICAL_FEATURES = [
    "campaign_goal",
    "campaign_type",
    "product_category",
    "brand_name",
    "day",
    "time_bucket",
    "season",
    "language",
    "dialect",
    "cta_presence",
    "cta_type",
    "contains_human",
    "logo_position_category",
    "visual_style",
    "layout_type",
    "is_product_post",
]

BASE_NUMERIC_FEATURES = [
    "caption_length",
    "word_count",
    "emoji_count",
    "number_of_ctas",
    "number_of_hashtags",
    "number_of_products",
    "image_count",
    "text_in_image_length",
    "text_in_image_word_count",
]

TONE_TOKENS = [
    "playful",
    "promotional",
    "urgent",
    "premium",
    "informative",
    "interactive",
    "emotional",
]

HOOK_STYLE_PATTERNS = {
    "question": ["question", "interrogative"],
    "curiosity": ["curiosity", "surprising"],
    "problem_solution": ["problem", "solution"],
    "benefit_value": ["benefit", "value"],
    "urgency_scarcity": ["urgency", "urgent", "scarcity", "limited"],
    "giveaway_prize": ["giveaway", "prize", "winner", "contest"],
    "announcement_arrival": ["announcement", "arrival", "introduction", "reveal"],
    "premium_aspiration": ["premium", "luxury", "aspiration", "aspirational"],
    "emotional_story": ["emotional", "storytelling", "story"],
    "comparison_claim": ["comparative", "competitive", "claim"],
}

WRITING_STYLE_PATTERNS = {
    "feature_list": ["feature list", "offer list", "bullet list", "giveaway list"],
    "direct_cta": ["direct cta", "store cta"],
    "comment_cta": ["comment cta"],
    "educational": ["educational", "explanation"],
}

CONTENT_PILLAR_PATTERNS = {
    "giveaway": ["giveaway", "contest"],
    "product_features": ["feature"],
    "education": ["education"],
    "offer_discount": ["offer", "discount", "price"],
    "new_arrival": ["new arrival"],
    "lifestyle_community": ["lifestyle", "community", "sports", "events"],
    "ai_technology": ["ai", "technology", "search"],
    "camera": ["camera"],
    "charging": ["charging"],
    "home_appliance": ["appliance", "home", "freshness", "energy efficiency"],
}

COLOR_FAMILIES = [
    "white",
    "black",
    "gray",
    "blue",
    "cyan",
    "teal",
    "red",
    "orange",
    "yellow",
    "green",
    "magenta",
    "purple",
    "pink",
    "brown",
]

FEATURE_GROUP_ORDER_PREDESIGN = [
    "campaign_goal",
    "campaign_type",
    "product_category",
    "brand_name",
    "day",
    "time_bucket",
    "season",
    "language",
    "dialect",
    "cta_presence",
    "cta_type",
    "tone",
    "hook_style",
    "writing_style",
    "content_pillar",
    "caption_length",
    "word_count",
    "emoji_count",
    "number_of_ctas",
    "number_of_hashtags",
    "number_of_products",
    "contains_human",
    "dominant_colors",
    "logo_position",
    "visual_style",
    "layout_type",
    "image_count",
    "is_product_post",
    "text_in_image",
    "text_similarity_to_success",
]

FEATURE_GROUP_ORDER_MULTIMODAL = FEATURE_GROUP_ORDER_PREDESIGN + [
    "image_similarity_to_success"
]

OUTCOME_OR_LEAKAGE_COLUMNS = {
    "Likes",
    "Comments",
    "Shares",
    "Reactions",
    "Reach",
    "Engagement Rate",
    "Reaction_Breakdown_Total",
    "Public_Interactions",
    "Weighted_Engagement",
    "Public_Engagement_Rate",
    "Relative_Performance_Index",
    "Performance_Class",
}
