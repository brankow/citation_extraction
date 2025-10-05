def correct_npl_mistakes(reference):
    """
    Applies heuristics to fix common LLM extraction errors.

    The primary heuristic: If the 'title' is very short (e.g., < 4 words)
    AND the 'publisher' (serial title) is missing, we assume the short title
    is actually the publisher/journal name and swap them.
    """
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
            
            # Optional: Log the correction
            print(f"  ~ CORRECTION: Swapped short title ('{title}') to publisher field.")
            return True # Indicates a correction was made

    return False # No correction needed