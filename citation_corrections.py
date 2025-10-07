def correct_npl_mistakes(reference):
    """
    Applies heuristics to fix common LLM extraction errors.

    The primary heuristic: If the 'title' is very short (e.g., < 4 words)
    AND the 'publisher' (serial title) is missing, we assume the short title
    is actually the publisher/journal name and swap them.
    Corrects improperly formatted DOI URLs (e.g., DOI:10... to https://doi.org/10...).    """
    corrected = False
    title = reference.get("title", "").strip()
    publisher = reference.get("publisher", "").strip()

    # Heuristic 1: Short 'title' that looks like a journal/publisher, but 'publisher' is empty.
    title_word_count = len(title.split())
    
    if title_word_count > 0 and title_word_count < 4 and not publisher:
        
        # Check if the title starts with a common journal indicator (optional, but improves confidence)
        if title.lower().startswith(("the", "j.", "journal", "nature", "science", "biochemistry")):
            
            # SWAP: Move the short title to the publisher/serial field
            reference["publisher"] = title
            reference["title"] = "" # Clear the title, as it's now the publisher
            
            print(f"  ~ CORRECTION: Swapped short title ('{title}') to publisher field.")
            corrected = True
    # --- Heuristic 2: DOI URL Correction ---
    url = reference.get("url", "").strip()
    
    # Check for 'doi:' or 'DOI:' prefixes in the URL field (case-insensitive)
    if url.lower().startswith("doi:"):
        
        # 1. Remove the 'doi:' prefix (case-insensitive, 4 characters)
        # We ensure to strip any leading/trailing whitespace after removing the prefix
        doi_path = url[4:].strip()
        
        # 2. Construct the correct full DOI URL
        corrected_url = f"https://doi.org/{doi_path}"
        
        # 3. Update the reference data
        reference["url"] = corrected_url
        
        print(f"  ~ CORRECTION: Fixed DOI URL: '{url}' -> '{corrected_url}'")
        corrected = True

    return corrected # Returns True if any correction was made  