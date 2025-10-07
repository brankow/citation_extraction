def correct_npl_mistakes(reference):
    """
    Applies heuristics to fix common LLM extraction errors.

    Includes:
    1. Title/Publisher swap heuristic.
    2. Corrects improperly formatted DOI URLs (e.g., DOI:10... to https://doi.org/10...).
    3. Completes bare DOI strings (e.g., 10.1016/... to https://doi.org/10.1016/...).
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

    return corrected