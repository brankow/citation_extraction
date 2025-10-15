import re
import constants
from datetime import datetime
from typing import List, Callable, Tuple, Dict, Any

# ----------------------------------------------------------------------
# --- Global Definitions and Configuration ---
# ----------------------------------------------------------------------

# Mapping for month abbreviations/full names to numbers (to handle various formats)
MONTH_MAP = {
    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
    'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
    'january': '01', 'february': '02', 'march': '03', 'april': '04', 'june': '06',
    'july': '07', 'august': '08', 'september': '09', 'october': '10', 'november': '11', 'december': '12'
}

# --- URL Cleaning Helpers ---

# Unsafe/Unallowed Characters from the list (must be percent-encoded if used as data)
UNALLOWED_URL_CHARS = [' ', '"', '<', '>', '{', '}', '|', '\\', '^', '~', '[', ']']
# Create a regex pattern to split on any of these characters
URL_SPLIT_PATTERN = re.compile(f"[{re.escape(''.join(UNALLOWED_URL_CHARS))}]")

# Pattern to check if a component LOOKS like a standard web address.
URL_START_PATTERN = re.compile(
    r'^(https?://|ftp://|ft://|www\.|([a-zA-Z0-9_-]+\.)+[a-zA-Z0-9_-]+/)',
    re.IGNORECASE
)

# ----------------------------------------------------------------------
# --- Date Standardization Functions ---
# ----------------------------------------------------------------------


def standardize_date(date_str):
    """
    Transforms a date string into 'ddmmyyyy' format, using '00' for missing day/month.
    Returns the transformed date string or None if transformation failed.
    """
    if not date_str:
        return None, False

    original_date = date_str.strip()
    
    # ----------------------------------------------------
    # CRITICAL PHASE 0: Check Exact Numeric/ISO Formats FIRST (without lowercasing)
    # ----------------------------------------------------
    
    # Full ISO format (YYYY-MM-DD) - Handles '2020-01-09'
    try:
        dt_obj = datetime.strptime(original_date, '%Y-%m-%d')
        return f"{dt_obj.day:02d}{dt_obj.month:02d}{dt_obj.year:04d}", True
    except ValueError:
        pass # Continue to the next phase

    # Check for ISO YYYY-MM (e.g., '2017-01')
    match_ym_iso = re.match(r'^(\d{4})-(\d{2})$', original_date)
    if match_ym_iso:
        year, month = match_ym_iso.groups()
        return "00" + month + year, True
        
    # Check for MM-YYYY (e.g., '04-2019')
    match_my_iso = re.match(r'^(\d{2})-(\d{4})$', original_date)
    if match_my_iso:
        month, year = match_my_iso.groups()
        return "00" + month + year, True
        
    # ----------------------------------------------------
    # PHASE 1: Clean and Parse Formats with Text/Ambiguity
    # ----------------------------------------------------

     # 1. Strip outer parenthesis/dots/commas.
    clean_date = original_date.strip('()')
    # 2. Replace internal commas and periods with a space for consistent parsing.
    clean_date = re.sub(r'[\.,]', ' ', clean_date).strip()
    # 3. Normalize multiple spaces and convert to lowercase for case-insensitive month matching
    clean_date = re.sub(r'\s+', ' ', clean_date).lower()

    date_formats = [
        # Day Month Year (full month) - Handles '6 April 2019', '13 May 2019'
        '%d %B %Y',    
        
        # Month Day Year (abbreviated month) - Handles 'dec 17 2002'
        '%b %d %Y',    
        
        # Year Month Day (abbreviated month) - Handles '2009 feb 27', '2014 nov 28'
        '%Y %b %d',  
        
        # Month Day Year (full month)
        '%B %d %Y',
        
        # Year Month Day (full month)
        '%Y %B %d', 
        
        # Month Year only
        '%b %Y',       
        '%B %Y',       
    ]
    
    for fmt in date_formats:
        try:
            dt_obj = datetime.strptime(clean_date, fmt)
            
            # Day logic: assume '00' if day is not in the format.
            if any(code in fmt for code in ['%d', '-%d']):
                day_str = f"{dt_obj.day:02d}"
            else:
                day_str = "00"

            month_str = f"{dt_obj.month:02d}"
            year_str = f"{dt_obj.year:04d}"
            return day_str + month_str + year_str, True

        except ValueError:
            continue
    
    # ----------------------------------------------------
    # PHASE 3: Handle Year-Only specifically (using regex)
    # ----------------------------------------------------
    
    # Check for Year only (e.g., '2018')
    match_y = re.match(r'^\d{4}$', original_date.strip())
    if match_y:
        year = match_y.group(0)
        return "0000" + year, True
        
    # Check for Year and Month only (e.g., '2011 mar' or 'mar 2011')
    # This phase handles cases where there's only year+month text after cleaning
    parts = clean_date.split()
    if len(parts) == 2:
        year_part = next((p for p in parts if p.isdigit() and len(p) == 4), None)
        month_part = next((p for p in parts if p in MONTH_MAP), None)
        
        if year_part and month_part:
            month_str = MONTH_MAP[month_part]
            return "00" + month_str + year_part, True

    # ----------------------------------------------------
    # PHASE 4: Failed to transform
    # ----------------------------------------------------
    return date_str, False

# --- URL Cleaning Functions  ---

def is_valid_url_component(text: str) -> bool:
    """
    Checks if a piece of text adheres to a minimum standard for a URL or identifier,
    using the stricter regex and filtering unallowed characters.
    """
    text = text.strip()
    
    # 1. Basic checks
    if len(text) < 5 or '.' not in text:
        return False
    
    # 2. Unallowed characters check
    if any(c in text for c in UNALLOWED_URL_CHARS):
        return False
        
    # 3. Must match the start pattern (protocol, www., or domain.tld/)
    if not URL_START_PATTERN.match(text):
        return False

    return True

def clean_url_by_splitting(potential_url_string: str) -> str:
    """
    Splits a potential URL string on unallowed characters and returns the first 
    component that looks like a valid URL/domain.
    """
    if not potential_url_string:
        return ""
        
    # 1. Split on any unallowed character
    parts = URL_SPLIT_PATTERN.split(potential_url_string)
    
    # 2. Find the first component that passes validation
    for p in parts:
        if is_valid_url_component(p):
            return p.strip()
            
    # 3. If no component is valid, return an empty string
    return ""

# ----------------------------------------------------------------------
# --- Main Correction Function ---
# ----------------------------------------------------------------------

def correct_npl_mistakes(reference):
    """
    Applies heuristics to fix common LLM extraction errors.

    Includes:
    1. Title/Publisher swap heuristic.
    2. Corrects improperly formatted DOI URLs (e.g., DOI:10... to https://doi.org/10...).
    3. Completes bare DOI strings (e.g., 10.1016/... to https://doi.org/10.1016/...).
    4. Cleans any remaining URL by splitting on unallowed characters.**
    5. Clears title if it contains the single author's name.**
    6. Standardizes publication date to ddmmyyyy format.
    7. Remove the Publisher if the length is less than 4 characters
    8. Remove the Title if the length is less than 4 characters
    """
    corrected = False


    # --- Heuristic 1: Title/Publisher Swap ---
    title_raw = reference.get("title")
    title = title_raw.strip() if title_raw is not None else ""
    publisher_raw = reference.get("publisher")
    publisher = publisher_raw.strip() if publisher_raw is not None else ""
    url_raw = reference.get("url")
    url = url_raw.strip() if url_raw is not None else ""

    # --- Heuristic 1: Title/Publisher Swap ---
    title_word_count = len(title.split())

    if title_word_count > 0 and title_word_count < 4 and not publisher:
        
        # Check if the title starts with a common journal indicator (optional, but improves confidence)
        if title.lower().startswith(("the", "j.", "journal", "nature", "science", "biochemistry")):
            
            # SWAP: Move the short title to the publisher/serial field
            reference["publisher"] = title
            reference["title"] = "" # Clear the title, as it's now the publisher
            if constants.terminal_feedback:
                print(f"  ~ CORRECTION: Swapped short title ('{title}') to publisher field.")
            corrected = True
            title = ""  # Update local variable 
    # --- Heuristic 2 & 3: DOI URL Correction/Completion ---
    
    if url:
        original_url = url
        doi_corrected = False
        
        # 2. Correction: Fix 'doi:' or 'DOI:' prefix
        if url.lower().startswith("doi:"):
            # Remove 'doi:' (4 characters) and standardize
            doi_path = url[4:].strip()
            url = f"https://doi.org/{doi_path}"
            doi_corrected = True
            
        # 3. Completion: Handle bare DOI strings (e.g., '10.1016/...')
        # Check if it starts with the standard DOI directory pattern ('10.') 
        # AND it hasn't been recognized as a standard URL or fixed in step 2.
        elif url.startswith("10.") and not url.lower().startswith("http"):
            url = f"https://doi.org/{url}"
            doi_corrected = True
            
        # Apply the final corrected URL to the reference if a correction occurred
        if doi_corrected:
            reference["url"] = url
            corrected = True
            if constants.terminal_feedback:
                print(f"  ~ CORRECTION: Fixed DOI URL: '{original_url}' -> '{url}'")

    # --- Heuristic 4: Unallowed Character URL Splitting and Cleaning ---   
    current_url = reference.get("url")
    if current_url:
        original_url_for_split = current_url.strip()
        cleaned_url = clean_url_by_splitting(original_url_for_split)
        
        if original_url_for_split != cleaned_url:
            reference["url"] = cleaned_url
            # If the URL was changed (either cleaned or discarded), mark as corrected
            corrected = True 
            if constants.terminal_feedback and cleaned_url:
                print(f"  ~ CORRECTION: Cleaned URL via splitting: '{original_url_for_split}' -> '{cleaned_url}'")
            elif constants.terminal_feedback and not cleaned_url and original_url_for_split:
                print(f"  ~ CORRECTION: Discarded invalid URL: '{original_url_for_split}'")

    # --- Heuristic 5: Clear Title if it Contains Single Author ---
    authors_list = reference.get("author") 

    # Check 1: Must have exactly ONE author AND a title must exist
    # AND the list must not be empty or None.
    if authors_list and isinstance(authors_list, list) and len(authors_list) == 1 and title:
        
        # Schema confirms the item is a string, so we extract directly.
        first_author_name = str(authors_list[0])

        # Final cleanup and lowercase for comparison
        author_name_clean = first_author_name.strip().lower()
        title_clean = title.strip().lower()

        # Check 2: Author name must be PRESENT ANYWHERE in the title (and must be at least 2 chars long)
        if len(author_name_clean) >= 2 and author_name_clean in title_clean:
            
            reference["title"] = ""
            corrected = True
            
            # Since the title local variable is used for Heuristic 1 checks, update it.
            # This is technically unnecessary here as H5 runs after H1, but safe practice.
            title = "" 
            
            if constants.terminal_feedback:
                print(f"  ~ CORRECTION: Cleared title ('{title_raw}') because it contained the single author ('{author_name_clean}').")
        
    # --- Heuristic 6: Date Standardization (ddmmyyyy) ---
    original_date_raw = reference.get("publication_date")
    original_date = original_date_raw.strip() if original_date_raw is not None else ""
    
    if original_date:
        transformed_date, success = standardize_date(original_date)
        
        if success:
            reference["publication_date"] = transformed_date
            # Check if date was actually changed to "ddmmyyyy" (from original format)
            if original_date != transformed_date: 
                corrected = True
        else:
            # Print a comment if transformation failed
            print(f"  ! WARNING: Date '{original_date}' could not be transformed to ddmmyyyy and was left as is.")

    # --- Heuristic 7: Remove Publisher if too short ---
    publisher_raw = reference.get("publisher")
    publisher = publisher_raw.strip() if publisher_raw is not None else ""
    if publisher and len(publisher) < 4:
        reference["publisher"] = ""
        corrected = True
        if constants.terminal_feedback:
            print(f"  ~ CORRECTION: Removed short publisher ('{publisher}').")

    # --- Heuristic 8: Remove Title if too short ---
    title_raw = reference.get("title")
    title = title_raw.strip() if title_raw is not None else ""
    if title and len(title) < 4:
        reference["title"] = ""
        corrected = True
        if constants.terminal_feedback:
            print(f"  ~ CORRECTION: Removed short title ('{title}').")  

    return corrected