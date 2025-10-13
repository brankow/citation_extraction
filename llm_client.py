import re
import json
import time
import requests 
import openai
import instructor
from typing import Dict, Any, Union, List

# Import necessary configuration, Pydantic schemas, and external helpers
import constants
# Import Pydantic models instead of dictionary schemas
from schemas import NPLReferences, StandardsReferences, AccessionIDs 


# --- LM Studio Configuration (Accessing External Constants) ---
LM_STUDIO_URL = constants.LM_STUDIO_URL
MODEL_NAME = constants.MODEL_NAME
MAX_RETRIES = constants.MAX_RETRIES
INITIAL_DELAY = constants.INITIAL_DELAY

FORMULA_REGEX = re.compile(
    r'\b[a-z0-9\-\(\)\[\]\{\}]{20,}\b',
    re.IGNORECASE  # Ensures matching works regardless of case (A-Z or a-z)
)

# 1. COMPILE THE REGEX FOR SINGLE PERCENTAGES
# This targets any number (integer or decimal) immediately followed by 'wt%'.
# E.g., 2.5wt%, 10wt%, 40wt%
SINGLE_WT_PERCENT_REGEX = re.compile(r'(\d+\.?\d*)\s?wt%', re.IGNORECASE)

# 2. COMPILE THE REGEX FOR RATIOS
# This targets structures like 60wt%/40wt% (two numbers separated by a slash, followed by wt%).
# This is more complex to capture, so we will use a broader target to catch both numbers and the slash/wt%
# E.g., 60wt%/40wt%
RATIO_WT_PERCENT_REGEX = re.compile(r'(\d+\.?\d*)\s?wt%\s?/\s?(\d+\.?\d*)\s?wt%', re.IGNORECASE)

# --- 1. Instructor/OpenAI Client Setup ---
# Initialize the base, UNPATCHED OpenAI client globally. 
# We will patch it *per function call* to avoid the double-endpoint issue.
CLIENT = openai.OpenAI(
    base_url=LM_STUDIO_URL, 
    api_key="lm-studio" # Dummy key for LM Studio/local servers
)

def clean_unknown_values(data: Union[Dict[str, Any], List[Any], str, None]) -> Union[Dict[str, Any], List[Any], str, None]:
    """
    Recursively replaces strings 'Unknown' or 'unknown' (case-insensitive) 
    with an empty string "" in a parsed JSON object (dict or list).
    """
    if isinstance(data, dict):
        return {k: clean_unknown_values(v) for k, v in data.items()}
    
    elif isinstance(data, list):
        return [clean_unknown_values(item) for item in data]
    
    elif isinstance(data, str):
        # Perform case-insensitive check and replacement
        if data.lower() == 'unknown':
            return ""
        return data
    
    # Return everything else (None, numbers, booleans) as is
    return data


# --- API Communication Helpers (Unchanged) ---
def call_lm_studio_api_with_retry(payload: Dict[str, Any]):
    # ... (This function remains UNCHANGED and is only used for the startup check)
    headers = {"Content-Type": "application/json"}
    
    for attempt in range(MAX_RETRIES):
        try:
            # NOTE: This function's URL is constructed manually, so it must use the 
            # correct LM_STUDIO_URL which should now be "http://localhost:1234/v1/chat/completions"
            # if you want to reuse this for generic non-structured calls.
            # However, for the startup check, we rely on the logic in api_service.py's startup event.
            response = requests.post(LM_STUDIO_URL, headers=headers, data=json.dumps(payload), timeout=60)
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(f"HTTP Error {response.status_code} from LM Studio: {e}", response=response)
        
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                delay = INITIAL_DELAY * (2 ** attempt)
                print(f"Connection attempt {attempt + 1}/{MAX_RETRIES} failed. Retrying in {delay:.2f}s...")
                time.sleep(delay)
            else:
                raise Exception(
                    f"FATAL: LM Studio API call failed after {MAX_RETRIES} retries. "
                    f"Details: {e}"
                )
    return None


# --- Standard Detection (Unchanged) ---
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

ExtractionResult = Union[Dict[str, Any], str]

# ----------------------------------------------------------------------
# --- Structured Extraction Functions (With Safe Patch/Unpatch Cycle) ---
# ----------------------------------------------------------------------

# In llm_client.py

def extract_npl_references(paragraph_text: str) -> ExtractionResult:
    """
    Extracts NPL references by injecting the Pydantic JSON Schema 
    directly into the user prompt message, as required by LM Studio.
    """
    if constants.terminal_feedback:
        print(paragraph_text)
    # 1. Get the JSON schema from the Pydantic model (using default, unproblematic call)
    npl_schema = NPLReferences.model_json_schema()
    
    # 2. System prompt focuses on strict adherence
    system_prompt = "You are a highly deterministic data extraction engine. Your ONLY task is to output a single, valid JSON object that strictly adheres to the provided JSON Schema. Do not include any conversational text, explanations, or extraneous characters."

    # 3. User prompt includes the schema as text
    user_prompt = f"""
        From the following text, extract all non-patent publication references.
        Ensure the output is a single JSON object that strictly conforms to the JSON schema provided below.
        
        Mandatory rules:
        - If no references are found, return a json object with an empty 'references' array.
        - Only references with a date should be extracted.
        - Do not extract patent applications and publications.


        CRITICAL FORMATTING RULES:
        - The **root of the output MUST be a dictionary** containing a single key named **"references"**.
        - The value of "references" MUST be a JSON array containing the extracted reference objects.
        - The 'author' field MUST be a **JSON array of strings** (e.g., ["Peters M.", "Sanchez P. et al."]). Split authors when a comma separates them into separate strings within this array.
        - Do NOT include any markdown fences (e.g., ```json) around the output.
        - **Do NOT use null, None, or empty strings ("") for mandatory fields unless explicitly allowed by the schema.**



        --- JSON SCHEMA ---
        {json.dumps(npl_schema, indent=2)} 
        --- END OF JSON SCHEMA ---

        --- TEXT TO ANALYZE ---
        {paragraph_text}
        --- END OF TEXT ---
        
        ONLY output the JSON object. Do not output anything else.
    """
    
    # 4. Payload configuration (NO 'response_format' field needed, as the schema is in the prompt)
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt}, 
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.0,
        # NOTE: Remove 'response_format' entirely.
    }
    
    try:
        llm_response = call_lm_studio_api_with_retry(payload)
        
        if llm_response and 'choices' in llm_response and llm_response['choices']:
            llm_text_raw = llm_response['choices'][0]['message']['content']
            llm_text = llm_text_raw if llm_text_raw is not None else "" 
            
            # Since we are back to text output, we must re-introduce JSON extraction 
            # and validation. Pydantic is still the best validation tool.
            
            # 5. Extract and Validate (You must use your old robust_json_extract if that's 
            # what the rest of your system relies on, but here is a Pydantic-based version):
            try:
                # We need to extract the raw JSON string first, which your old robust_json_extract did
                # Since I don't have robust_json_extract, I will use a simple json.loads, 
                # but you might need to re-import/re-add your original robust_json_extract function here
                json_data = json.loads(llm_text)
                cleaned_json_data = clean_unknown_values(json_data)
                validated_response = NPLReferences.model_validate(cleaned_json_data)
                return validated_response.model_dump()
            except Exception as e:
                 # This catch includes validation, decode errors, and potential LLM conversational output
                return f"[LLM Extraction Failed: Pydantic Validation Failed: {e}. Raw Text: {llm_text[:200]}...]"

        else:
            return "[LLM Extraction Failed: Invalid response structure or no choices returned.]"
            
    except Exception as e:
        return f"[LLM Extraction Failed (NPL/Prompt Injection): {e}]"

def extract_standard_references(paragraph_text, _3gpp_standards, _ieee_standards) -> ExtractionResult:
    """
    Extracts standard references by injecting the Pydantic JSON Schema 
    directly into the user prompt message, as required by LM Studio.
    """
    if constants.terminal_feedback:
        print(paragraph_text)
    
    # --- 1. Dynamic Prompt Setup (Unchanged) ---
    standards_list_section = []
    if _3gpp_standards:
        standards_list_section.append(f"3GPP candidate standards: {json.dumps(_3gpp_standards, ensure_ascii=False)}")
    if _ieee_standards:
        standards_list_section.append(f"IEEE candidate standards: {json.dumps(_ieee_standards, ensure_ascii=False)}")

    if standards_list_section:
        standards_intro = "The text may contain references to standards from the following lists:"
        standards_list_text = "\n".join(standards_list_section)
        standards_instructions = "Extract any standard mentioned from these lists."
    else:
        standards_intro = "No specific standard lists were provided for extraction."
        standards_list_text = "Therefore, you must return an object with an empty 'references' array."
        standards_instructions = ""
    
    # 2. Get the JSON schema from the Pydantic model (using default, unproblematic call)
    standards_schema = StandardsReferences.model_json_schema()

    # 3. System prompt focuses on strict adherence
    system_prompt = "You are a highly deterministic data extraction engine. Your ONLY task is to output a single valid JSON object that strictly conforms to the provided JSON Schema. Do not include any conversational text, explanations, or extraneous characters."

    # 4. User prompt includes the schema as text
    user_prompt = f"""
    {standards_intro}
    {standards_list_text}
    {standards_instructions}

    Each reference must include:
    - "standardisation_body": the organization name (e.g., "3GPP", "IEEE")
    - "accession_number": the alphanumeric code uniquely identifying the standard (e.g., "TS 23.501", "802.11be")
    - "title": a short descriptive text following or associated with the standard (if present, else "")
    - "version": the version or edition of the standard (if present, else "")

    RULES:
    - If no references are found, return a JSON object with an empty "references" array.

    --- JSON SCHEMA ---
    {json.dumps(standards_schema, indent=2)} 
    --- END OF JSON SCHEMA ---

    --- TEXT TO ANALYZE ---
    {paragraph_text}
    --- END OF TEXT ---
    
    ONLY output the JSON object. Do not output anything else.
    """
    
    # 5. Payload configuration (NO 'response_format' field)
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt}, 
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.0,
    }

    try:
        llm_response = call_lm_studio_api_with_retry(payload)
        
        if llm_response and 'choices' in llm_response and llm_response['choices']:
            llm_text_raw = llm_response['choices'][0]['message']['content']
            llm_text = llm_text_raw if llm_text_raw is not None else "" 
            
            # 6. Extraction and Validation (REPLACE with your robust_json_extract if needed)
            try:
                # Assuming robust_json_extract is used to clean/extract the JSON string
                # If robust_json_extract is unavailable, this will often fail:
                json_data = json.loads(llm_text) 
                validated_response = StandardsReferences.model_validate(json_data)
                return validated_response.model_dump()
            except Exception as e:
                # Catch validation/decoding errors
                return f"[LLM Extraction Failed: Pydantic Validation Failed: {e}. Raw Text: {llm_text[:200]}...]"

        else:
            return "[LLM Extraction Failed: Invalid response structure or no choices returned.]"
            
    except Exception as e:
        return f"[LLM Extraction Failed (Standards/Prompt Injection): {e}]"

def replace_long_formulas(paragraph: str) -> str:
    """
    Scans a paragraph and replaces any string matching the long chemical/molecular 
    formula regex with the word "FORMULA".

    Args:
        paragraph: The input text containing potential formulas.

    Returns:
        The paragraph with long formulas replaced by "FORMULA".
    """
    # 2. Use re.sub() with the precompiled regex to perform the replacement.
    modified_paragraph = FORMULA_REGEX.sub("FORMULA", paragraph)
    return modified_paragraph

def neutralize_quantitative_noise(paragraph: str) -> str:
    """
    Replaces numerical weight percentages (wt%) and ratios in a paragraph
    with non-numerical placeholders to prevent LLM distraction.
    
    The wt% unit is now removed entirely for single percentage values.
    """
    # First, handle the complex ratio structure: Xwt%/Ywt%
    # This step replaces the entire ratio with a single placeholder.
    paragraph = RATIO_WT_PERCENT_REGEX.sub(r'[A_DEFINED_RATIO]', paragraph)
    
    # Second, handle all remaining single wt% values (like 2.5wt%)
    # The entire match (number + wt%) is replaced by the placeholder.
    paragraph = SINGLE_WT_PERCENT_REGEX.sub(r'[A_CERTAIN_AMOUNT]', paragraph)
    
    return paragraph


def extract_accessions_with_llm(paragraph_text: str) -> ExtractionResult:
    """
    Extracts accession IDs by injecting the Pydantic JSON Schema 
    directly into the user prompt message, as required by LM Studio.
    """
    cleaned_paragraph = neutralize_quantitative_noise(replace_long_formulas(paragraph_text))
    if constants.terminal_feedback:
        print(cleaned_paragraph)
    # 1. Get the JSON schema from the Pydantic model (using default, unproblematic call)
    accession_schema = AccessionIDs.model_json_schema()

    # 2. System prompt focuses on strict adherence
    system_prompt = "You are a highly deterministic data extraction engine. Your ONLY task is to output a single, valid JSON object that strictly conforms to the provided JSON Schema. Do not include any conversational text, explanations, or extraneous characters."
    
    # 3. User prompt includes the schema as text
    user_prompt = f"""
        From the following text, extract all biological and chemical database accession IDs 
        
        DATABASE GUIDANCE:
        - GenBank, Uniprot, Swissprot, PDB, RefSeq, NCBI, EMBL, etc.
        - CAS (Chemical Abstracts Service): Look for the exact pattern [1-7 digits]-[2 digits]-[1 digit] (e.g., 50-78-2 or 1416354-32-9).

        CRITICAL RULE: 
        - Every 'id' field MUST contain a string value (the accession number). DO NOT use 'null', 'None', or empty strings ("") for the 'id' field.
        - If a valid ID cannot be determined, the entire accession object should be omitted from the 'accessions' array.
        
        --- JSON SCHEMA ---
        {json.dumps(accession_schema, indent=2)} 
        --- END OF JSON SCHEMA ---
        
        --- TEXT TO ANALYZE ---
        {cleaned_paragraph}
        --- END OF TEXT ---
        
        ONLY output the JSON object. Do not output anything else.
    """
    
    # 4. Payload configuration (NO 'response_format' field)
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt}, 
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.0,
    }

    try:
        llm_response = call_lm_studio_api_with_retry(payload)
        
        if llm_response and 'choices' in llm_response and llm_response['choices']:
            llm_text_raw = llm_response['choices'][0]['message']['content']
            llm_text = llm_text_raw if llm_text_raw is not None else "" 
            
            # 5. Extraction and Validation (REPLACE with your robust_json_extract if needed)
            try:
                # Assuming robust_json_extract is used to clean/extract the JSON string
                json_data = json.loads(llm_text)
                validated_response = AccessionIDs.model_validate(json_data)
                return validated_response.model_dump()
            except Exception as e:
                # Catch validation/decoding errors
                return f"[LLM Extraction Failed: Pydantic Validation Failed: {e}. Raw Text: {llm_text[:200]}...]"

        else:
            return "[LLM Extraction Failed: Invalid response structure or no choices returned.]"
            
    except Exception as e:
        return f"[LLM Extraction Failed (Accessions/Prompt Injection): {e}]"