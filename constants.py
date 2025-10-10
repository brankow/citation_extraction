import re
from datetime import datetime

# --- LM Studio Configuration ---
# NOTE: This configuration targets a local LLM server (like LM Studio).
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
# Set this to the name of the model you have loaded in LM Studio.
# MODEL_NAME = "qwen/qwen3-1.7b" 
# MODEL_NAME = "meta-llama-3-8b-instruct"
MODEL_NAME = "meta-llama-3.1-8b-instruct"
# MODEL_NAME = "granite-4.0-h-tiny-mlx"
# MODEL_NAME = "mistralai/magistral-small-2509"

MAX_RETRIES = 3
INITIAL_DELAY = 1 # seconds
current_year = datetime.now().year
terminal_feedback = False  # Set to True to enable terminal feedback 

# --- COMPILED REGULAR EXPRESSIONS (for performance) ---
STANDARDS_BODIES_REGEX = re.compile(r'\b(?:3GPP|IEEE)\b', re.IGNORECASE) 
# 3GPP patterns
_3GPP_PATTERN = re.compile(
    r'\b(?:'
    r'(?:TS|TR)\s*\d{1,3}(?:\.\d{1,3})?'  # Technical Specs: TS 23.501, TR 38.901
    r'|'
    r'CR\s*\d{1,4}'                        # Change Requests: CR 1234
    r'|'
    r'[RS][PSCN\d]-?\d{6,7}'               # Contributions: RP-200938, R1-2104253, S2-2301234
    r')\b',
    flags=re.IGNORECASE
)
_3GPP_PRESENT = re.compile(r'\b3GPP\b', flags=re.IGNORECASE)
# IEEE patterns
_IEEE_PRESENT = re.compile(r'\bIEEE\b', re.IGNORECASE)
_IEEE_PATTERN = re.compile(
    r'\bP?\d{3,4}(?:\.[A-Za-z0-9]+)+\b', # The '*' has been changed to a '+'
    re.IGNORECASE
)
# Year detection pattern (1900-2025)
years_list = [str(y) for y in range(1900, current_year + 1)]
YEAR_PATTERN = '|'.join(years_list)
YEAR_REGEX = re.compile(rf'\b({YEAR_PATTERN})\b')

# Genbank and biological database patterns
GENBANK_REGEX = re.compile(r'\b(?:CAS|genbank|Genbank|Uniprot|Swissprot|PDB|RefSeq|NCBI)\b')

# DOI pattern
DOI_REGEX = re.compile(
    r'\b(?:'
    r'10\.[1-9]\d{3,8}/[-._;()/:A-Z0-9]+'
    r'|https?://(?:dx\.)?doi\.org/10\.\d{4,9}/[-._;()/:A-Z0-9]+'
    r')\b',
    re.IGNORECASE
)

# JSON cleaning patterns
JSON_MARKDOWN_START = re.compile(r'^\s*```json\s*', flags=re.IGNORECASE | re.MULTILINE)
JSON_MARKDOWN_END = re.compile(r'\s*```\s*$', flags=re.MULTILINE)
THINK_TAGS = re.compile(r'<\/?\s*think\s*>', flags=re.IGNORECASE | re.MULTILINE)
TRAILING_COMMA = re.compile(r',\s*([\}\]])')

# XML tag removal pattern
XML_TAGS = re.compile(r'<[^>]+>')