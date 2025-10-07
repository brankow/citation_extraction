import re
from datetime import datetime

# Mapping for month abbreviations/full names to numbers (to handle various formats)
MONTH_MAP = {
    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
    'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
    'january': '01', 'february': '02', 'march': '03', 'april': '04', 'june': '06',
    'july': '07', 'august': '08', 'september': '09', 'october': '10', 'november': '11', 'december': '12'
}

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


def correct_npl_mistakes(reference):
    """
    Applies heuristics to fix common LLM extraction errors.

    Includes:
    1. Title/Publisher swap heuristic.
    2. Corrects improperly formatted DOI URLs (e.g., DOI:10... to https://doi.org/10...).
    3. Completes bare DOI strings (e.g., 10.1016/... to https://doi.org/10.1016/...).
    4. Standardizes publication date to ddmmyyyy format.
    """
    corrected = False


    # --- Heuristic 1: Title/Publisher Swap ---
    title = reference.get("title", "").strip()
    publisher = reference.get("publisher", "").strip()
    title_word_count = len(title.split())
    
    if title_word_count > 0 and title_word_count < 4 and not publisher:
        
        # Check if the title starts with a common journal indicator (optional, but improves confidence)
        if title.lower().startswith(("the", "j.", "journal", "nature", "science", "biochemistry")):
            
            # SWAP: Move the short title to the publisher/serial field
            reference["publisher"] = title
            reference["title"] = "" # Clear the title, as it's now the publisher
            
            print(f"  ~ CORRECTION: Swapped short title ('{title}') to publisher field.")
            corrected = True
    # --- Heuristic 2 & 3: DOI URL Correction/Completion ---
    url = reference.get("url", "").strip()
    
    if url:
        original_url = url
        
        # 2. Correction: Fix 'doi:' or 'DOI:' prefix
        if url.lower().startswith("doi:"):
            # Remove 'doi:' (4 characters) and standardize
            doi_path = url[4:].strip()
            url = f"https://doi.org/{doi_path}"
            corrected = True
            
        # 3. Completion: Handle bare DOI strings (e.g., '10.1016/...')
        # Check if it starts with the standard DOI directory pattern ('10.') 
        # AND it hasn't been recognized as a standard URL or fixed in step 2.
        elif url.startswith("10.") and not url.lower().startswith("http"):
            url = f"https://doi.org/{url}"
            corrected = True
            
        # Apply the final corrected URL to the reference if a correction occurred
        if corrected:
            reference["url"] = url
            if original_url != url:
                print(f"  ~ CORRECTION: Fixed DOI URL: '{original_url}' -> '{url}'")
    # --- Heuristic 3: Date Standardization (ddmmyyyy) ---
    original_date = reference.get("publication_date", "").strip()
    
    if original_date:
        transformed_date, success = standardize_date(original_date)
        
        if success:
            reference["publication_date"] = transformed_date
        else:
            # Print a comment if transformation failed
            print(f"  ! WARNING: Date '{original_date}' could not be transformed to ddmmyyyy and was left as is.")
    return corrected