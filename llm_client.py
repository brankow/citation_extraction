import re
import json
import time
import requests 

# Import necessary configuration and schemas
import constants
import schemas

# You will need to move format_schema and simple regex functions to utils.py as recommended.
# Assuming format_schema is moved to utils, we import it here:
from utils import format_schema 

# --- LM Studio Configuration (Accessing External Constants) ---
LM_STUDIO_URL = constants.LM_STUDIO_URL
MODEL_NAME = constants.MODEL_NAME
MAX_RETRIES = constants.MAX_RETRIES
INITIAL_DELAY = constants.INITIAL_DELAY

# --- API Communication Helpers ---

def call_lm_studio_api_with_retry(payload):
    """
    Makes a synchronous request to the LM Studio API with basic exponential backoff.
    """
    headers = {"Content-Type": "application/json"}
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(LM_STUDIO_URL, headers=headers, data=json.dumps(payload), timeout=60)
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.HTTPError as e:
            # Re-raise the HTTP error immediately
            raise requests.exceptions.HTTPError(f"HTTP Error {response.status_code} from LM Studio: {e}", response=response)
        
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                delay = INITIAL_DELAY * (2 ** attempt)
                print(f"Connection attempt {attempt + 1}/{MAX_RETRIES} failed. Retrying in {delay:.2f}s...")
                time.sleep(delay)
            else:
                # Raise a fatal error after max retries
                raise Exception(
                    f"FATAL: LM Studio API call failed after {MAX_RETRIES} retries. "
                    f"Please ensure the LM Studio server is running with a model loaded at {LM_STUDIO_URL}. "
                    f"Details: {e}"
                )
    return None

def robust_json_extract(llm_text):
    """
    Safely extracts and parses the FIRST valid, balanced JSON object from LLM output.
    Uses compiled regex from constants for efficiency.
    """
    # 1. Aggressive cleaning: remove non-standard spaces, markdown fences, and common LLM thinking tags.
    if llm_text is None:
            llm_text = ""
    cleaned_text = llm_text.replace('\xa0', ' ').strip()
    
    # Remove common JSON markdown wrappers and thinking tags
    cleaned_text = constants.JSON_MARKDOWN_START.sub('', cleaned_text)
    cleaned_text = constants.JSON_MARKDOWN_END.sub('', cleaned_text)
    cleaned_text = constants.THINK_TAGS.sub('', cleaned_text)
    
    # 2. Find the index of the first opening brace.
    start_index = cleaned_text.find('{')
    
    if start_index == -1:
        return f"[No valid JSON structure found in response. Raw text: {llm_text[:100]}...]"

    # 3. Use a brace counter to find the index of the corresponding closing brace.
    brace_count = 0
    end_index = -1
    
    # Iterate from the first opening brace to find the end of the first balanced object
    for i in range(start_index, len(cleaned_text)):
        char = cleaned_text[i]
        
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1

            # If the brace count returns to 0, we found the closing brace for the top-level object.
            if brace_count == 0:
                end_index = i + 1  # Include the '}'
                break

    if end_index == -1:
        # If we reached the end of the string but the braces were not balanced.
        return f"########[Structural JSON Error. Unbalanced braces. JSON starts but does not close: {cleaned_text[start_index:]}...]"
    
    # 4. Extract the isolated JSON string. Everything after end_index is discarded.
    json_string = cleaned_text[start_index:end_index]
    
    # 5. Apply last-mile JSON fixes (trailing commas, escaped newlines)
    try:
        # Fix trailing comma and escaped newlines
        json_string = constants.TRAILING_COMMA.sub(r'\1', json_string)
        # Additional safety: replace any escaped newlines that might break json.loads
        json_string = json_string.replace('\\n', '\n')
        
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        return f"########[Structural JSON Error. {e}. Parsed content (attempted fix):\n{json_string}...]"

# --- Standard Detection (Used to feed LLM context) ---
# NOTE: These are kept here as they are direct helpers to the LLM extraction process.

def extract_3gpp_references(text: str):
    if not constants._3GPP_PRESENT.search(text):
        return []
    matches = constants._3GPP_PATTERN.findall(text)
    return [re.sub(r'\s+', ' ', m.strip().upper()) for m in matches]

def extract_ieee_references(text: str):
    """Extract IEEE standard/project numbers if 'IEEE' appears in the text."""
    if not constants._IEEE_PRESENT.search(text):
        return []
    matches = constants._IEEE_PATTERN.findall(text)
    return [m.upper() for m in matches]

def clean_llm_response(llm_text: str) -> str:
    if llm_text is None:
        return ""
    
    return (
        llm_text
        .replace('["unknown"]', '[]')
        .replace('["Unknown"]', '[]')
        .replace('"unknown"', '""')
        .replace('"Unknown"', '""')
    )

# --- Structured Extraction Functions ---

def extract_npl_references(paragraph_text):
    """
    Sends the cleaned paragraph text to the LM Studio model to extract
    non-patent publication references ONLY. The model is set to deterministic mode.
    The required JSON schema is included in the prompt.
    """
    system_prompt = "You are a highly deterministic data extraction engine. Your ONLY task is to output a single, valid JSON object that strictly adheres to the provided JSON Schema. Do not include any conversational text, explanations, or extraneous characters."
    
    user_prompt = f"""
        From the following text, extract all non-patent publication references.
        Ensure the output is a single JSON object that strictly conforms to the JSON schema provided below.
        
        Mandatory rules:
        - If no references are found, return a json object with an empty 'references' array.
        - If there are multiple authors, provide them in a comma (,) separated array of strings.
        - Ensure every key is followed by a colon (:), even if the value is an empty string ("").
        - **CRITICAL RULE: The key and its value MUST be separated by a colon (:), NOT a comma (,) in the JSON object. For example, it must be "volume": "42", not "volume", "42".**
        - Only references with a date should be extracted.
        - Please do not extract patent applications and publications.

        --- JSON SCHEMA ---
        {format_schema(schemas.NPL_REFERENCES_SCHEMA)}
        --- END OF JSON SCHEMA ---

        --- TEXT TO ANALYZE ---
        {paragraph_text}
        --- END OF TEXT ---
        
        ONLY output the JSON object. Do not output anything else.
    """
    # 3. Payload configuration: set temperature to 0.0 for deterministic output
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        "temperature": 0.0,  # Maximize determinism (model doesn't 'think' creatively)
        "stream": False
    }

    try:
        llm_response = call_lm_studio_api_with_retry(payload)
        if llm_response and 'choices' in llm_response and llm_response['choices']:
            llm_text_raw = llm_response['choices'][0]['message']['content']
            llm_text = llm_text_raw if llm_text_raw is not None else "" 
            # print (llm_text)
            cleaned_text = clean_llm_response(llm_text)
            # print(cleaned_text)
            return robust_json_extract(cleaned_text)
        else:
            return "[LLM Extraction Failed: Invalid response structure or no choices returned.]"
    except Exception as e:
        return f"[LLM Extraction Failed: {e}]"
    
def extract_standard_references(paragraph_text, _3gpp_standards, _ieee_standards):
    """
    Sends paragraph text to the LLM to extract standard references.
    """
    system_prompt = """
    You are a highly deterministic data extraction engine.
    Your ONLY task is to output a single valid JSON object that conforms EXACTLY to the provided JSON Schema.

    CRITICAL RULES:
    - Use ONLY the information explicitly present within the 'TEXT TO ANALYZE' block.
    - DO NOT infer or hallucinate standards not explicitly written in the text.
    - DO NOT include any explanations, commentary, or text outside the JSON object.
    """

    user_prompt = f"""
    The text may contain references to standards from the following lists:

    3GPP candidate standards: {json.dumps(_3gpp_standards, ensure_ascii=False)}
    IEEE candidate standards: {json.dumps(_ieee_standards, ensure_ascii=False)}

    If any of these standards are indeed mentioned in the text, extract them as structured references.

    Each reference must include:
    - "standardisation_body": the organization name (e.g., "3GPP", "IEEE")
    - "accession_number": the alphanumeric code uniquely identifying the standard (e.g., "TS 23.501", "802.11be")
    - "title": a short descriptive text following or associated with the standard (if present, else "")
    - "version": the version or edition of the standard (if present, else "")

    RULES:
    - If no references are found, return a JSON object with an empty "references" array.
    - Every key must appear in the JSON output, even if its value is an empty string "".
    - Only include references explicitly appearing in the current text.
    - Do not merge, infer, or deduplicate across previous requests.

        --- JSON SCHEMA ---
        {format_schema(schemas.STANDARDS_REFERENCES_SCHEMA)}
        --- END OF JSON SCHEMA ---

        --- TEXT TO ANALYZE ---
        {paragraph_text}
        --- END OF TEXT ---
        
        ONLY output the JSON object. Do not output anything else.
    """
    
    # 3. Payload configuration: set temperature to 0.0 for deterministic output
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        "temperature": 0.0,
        "stream": False
    }

    try:
        llm_response = call_lm_studio_api_with_retry(payload)
        if llm_response and 'choices' in llm_response and llm_response['choices']:
            llm_text_raw = llm_response['choices'][0]['message']['content']
            llm_text = llm_text_raw if llm_text_raw is not None else "" 
            return robust_json_extract(llm_text)
        else:
            return "[LLM Extraction Failed: Invalid response structure or no choices returned.]"
    except Exception as e:
        return f"[LLM Extraction Failed: {e}]"

def extract_accessions_with_llm(paragraph_text):
    """
    Sends the cleaned paragraph text to the LM Studio model to extract
    biological and chemical accession IDs (e.g., Genbank, Uniprot, CAS, etc.) and their types ONLY.
    """
    
    # 1. System prompt emphasizes strict adherence to the schema
    system_prompt = """
        You are a highly deterministic data extraction engine. Your ONLY task is to output a single, valid JSON object that strictly adheres to the provided JSON Schema. Do not include any conversational text, explanations, or extraneous characters.
    """
    
    # 2. User prompt defines the required structured output and includes the schema
    user_prompt = f"""
        From the following text, extract all biological and chemical database accession IDs 
        (e.g., Genbank, Uniprot, Swissprot, PDB, RefSeq, NCBI, CAS, EMBL) and their corresponding database type. 
        Ensure the output is a single JSON object that strictly conforms to the JSON schema provided below.
        
        --- JSON SCHEMA ---
        {format_schema(schemas.ACCESSION_IDS_SCHEMA)}
        --- END OF JSON SCHEMA ---
        
        --- TEXT TO ANALYZE ---
        {paragraph_text}
        --- END OF TEXT ---
        
        ONLY output the JSON object. Do not output anything else.
    """
    
    # 3. Payload configuration: set temperature to 0.0 for deterministic output
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        "temperature": 0.0, # Maximize determinism (model doesn't 'think' creatively)
        "stream": False
    }
    try:
        llm_response = call_lm_studio_api_with_retry(payload)
        if llm_response and 'choices' in llm_response and llm_response['choices']:
            llm_text_raw = llm_response['choices'][0]['message']['content']
            llm_text = llm_text_raw if llm_text_raw is not None else "" 
            return robust_json_extract(llm_text)
        else:
            return "[LLM Extraction Failed: Invalid response structure or no choices returned.]"
    except Exception as e:
        return f"[LLM Extraction Failed: {e}]"