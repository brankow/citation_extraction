
import re
import constants

# Helper function to check if a value is truly present
def has_content(value):
    """Check if a value has meaningful content."""
    if isinstance(value, list):
        # Check if any item in the list has non-whitespace content
        return any(item and item.strip() for item in value)
    elif isinstance(value, str):
        return bool(value.strip())
    return bool(value)

def should_skip_npl_reference(ref: dict) -> bool:
    """
    Applies a series of filters to a single extracted NPL reference.

    Args:
        ref (dict): A single NPL reference dictionary (LLM output format).

    Returns:
        bool: True if the reference should be skipped (filtered out), False otherwise.
    """

    # Get the key fields
    author = ref.get("author", [])
    title = ref.get("title", "").strip()
    date = ref.get("publication_date", "").strip()
    publisher = ref.get("publisher", "").strip()
    volume = ref.get("volume", "").strip()
    pages = ref.get("pages", "").strip()
    url = ref.get("url", "").strip()

    # Check presence of key fields
    author_has_content = has_content(author)
    title_has_content = has_content(title)
    date_has_content = has_content(date)
    publisher_has_content = has_content(publisher)
    volume_has_content = has_content(volume)
    pages_has_content = has_content(pages)
    url_has_content = has_content(url)  
                                
    # --- FIX: Define author_string unconditionally here ---
    # Simple string of authors (e.g., 'Mohamed et al.')
    author_string = ", ".join(author).strip()
    # ---------------------------------------------------
    
    # Check for completeness (all other fields are empty)
    is_bare_citation = (
        author_has_content and 
        date_has_content and
        not publisher_has_content and
        not volume_has_content and
        not pages_has_content and
        not url_has_content
    )

    # --- FILTERING LOGIC ---
    # Condition 8: Filter out citations with 3GPP as date.  
    is_standards_date = (
        date_has_content and 
        constants.STANDARDS_BODIES_REGEX.search(date)
    )

    if is_standards_date:
        if constants.terminal_feedback:
            print(f"  - Skipping NPL reference (Condition 7: 3GPP/IEE in Date): {date}")
        return True # Skip this reference

    # Condition 7: Filter out citations with 3GPP as publisher.  
    is_standards_publisher = (
        publisher_has_content and 
        constants.STANDARDS_BODIES_REGEX.search(publisher)
    )

    if is_standards_publisher:
        if constants.terminal_feedback:
            print(f"  - Skipping NPL reference (Condition 7: 3GPP/IEE in Publisher): {publisher}")
        return True # Skip this reference

    # Condition 6: Filter out citations with ONLY Title.
    is_title_only = (
        not author_has_content and            # Missing Author
        title_has_content and                # Has Title
        not publisher_has_content and        # Missing Publisher
        not date_has_content and             
        not volume_has_content and
        not pages_has_content and
        not url_has_content
    )
    
    if is_title_only:
        if constants.terminal_feedback:
            print(f"  - Skipping NPL reference (Condition 6:Title Only filter): {title}")
        return True # Skip this reference

    # Condition 5: Filter out citations with ONLY Publisher and Date.
    
    if (publisher_has_content and date_has_content and not author_has_content and not title_has_content and not volume_has_content and not pages_has_content and not url_has_content):
        if constants.terminal_feedback:
            print(f"  - Skipping NPL reference (Condition 5: Publisher & Date Only filter): {publisher}, {date}")
        return True # Skip this reference

    # Condition 4: Completely Empty Reference (excluding the empty container)
    # Check if ALL major fields are absent (empty list/string)
    if (not author_has_content and not title_has_content and not date_has_content and 
        not publisher_has_content and not volume_has_content and not pages_has_content and not url_has_content):
        if constants.terminal_feedback:
            print(f"  - Skipping NPL reference (Condition 4: Completely Empty)")
        return True # Skip this reference

    # Condition 3: Only Publication Date is Present (and all others are absent)
    if (not author_has_content and not title_has_content and date_has_content and 
        not publisher_has_content and not volume_has_content and not pages_has_content and not url_has_content):
        if constants.terminal_feedback:
            print(f"  - Skipping NPL reference (Condition 3: Only Date is Present): {date}")
        return True # Skip this reference
    
    # Condition 2: Author, Title, and Date are present, and Author is in Title.
    if is_bare_citation and title_has_content:
        
        # If the author string is contained in the title string (case-insensitive)
        if author_string.lower() in title.lower():
            if constants.terminal_feedback:
                print(f"  - Skipping NPL reference (Condition 2: Bare Author/Date/Title, Author in Title): {author_string}, {date}")
            return True # Skip this reference

    # --- FILTERING LOGIC (Condition 1: Author and Date Only) ---
    
    # Condition 1: Only 'author' and 'publication_date' are filled. Title is also absent.
    is_author_and_date_only = (
        is_bare_citation and                        # Bare citation check from above
        not title_has_content                            # Title must also be absent
    )
    
    if is_author_and_date_only:
        # Now author_string is guaranteed to be defined
        if constants.terminal_feedback:
            print(f"  - Skipping NPL reference (Condition 1: Author & Date Only filter): {author_string}, {date}")
        return True # Skip this reference
                                
    # --- FILTERING LOGIC END ---
    
    # If none of the skip conditions were met
    return False
                            