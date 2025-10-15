
import xml.etree.ElementTree as ET
import sys
import os 
import constants # Contains Regexes and API settings
from citation_catalog import CitationCatalog 
from citation_filters import should_skip_npl_reference 
from citation_corrections import correct_npl_mistakes
from utils import select_xml_file, extract_paragraph_texts, simplify_long_words, simplify_bio_numbers
from paragraph_splitter import split_and_clean_paragraph

from llm_client import (
    extract_npl_references,
    extract_standard_references,
    extract_accessions_with_llm,
    extract_3gpp_references,
    extract_ieee_references,
    call_lm_studio_api_with_retry # Needed for the main connection check
)


def extract_paragraphs(file_path):
    """
    Parses the given XML file and extracts the 'num' attribute, the complete
    XML content, and a plain-text version from all <p> elements.
    
    Only paragraphs that meet the specified filter criteria (containing a year
    1900-2025, the <nplcit tag, or the word 'genbank') are printed and then 
    sent for LLM analysis.
    """
    if not file_path:
        print("File selection cancelled. Exiting.")
        return

    # Initialize the citation catalog
    catalog = CitationCatalog()

    try:
        if constants.terminal_feedback:
            print(f"\n--- Parsing file: {file_path} ---")

        # 1. Parse the XML file
        tree = ET.parse(file_path)
        root = tree.getroot()

        # 2. Iterate through all <p> elements in the document
        paragraphs_found = 0
        
        for p_element in root.iter('p'):
            
            # 3. Extract the 'num' attribute
            paragraph_num = p_element.get('num')            
            
            # --- Extracting full XML content, including nested tags ---
            raw_content_with_tags, stripped_text = extract_paragraph_texts(
                p_element, 
                constants.XML_TAGS # Pass the compiled regex needed for stripping
            )
            
            # 4. Check if the required 'num' attribute exists AND apply filtering
            if not paragraph_num:
                continue
                
            # 5. SPLIT THE PARAGRAPH IF IT'S TOO LONG
            split_parts = split_and_clean_paragraph(stripped_text)
            
            if constants.terminal_feedback and len(split_parts) > 1:
                lengths = [len(p) for p in split_parts]
                print(f"[{paragraph_num}] SPLIT: lengths -> {', '.join(map(str, lengths))}")

            # 6. ITERATE OVER THE SPLIT PARTS
            for i, part_text in enumerate(split_parts):
                
                # Assign a unique ID for the sub-paragraph, e.g., "p123.1", "p123.2"
                part_num = f"{paragraph_num}.{i+1}" if len(split_parts) > 1 else paragraph_num

                # The part text is what goes into the LLM logic
                current_text_to_process = part_text 

                # 7. Apply Filtering (Use the current part_text)                
                matched_year = None 
                contains_year = False
                
                # Use stripped_text for boundary-based year matching
                year_detected = constants.YEAR_REGEX.search(current_text_to_process)
                
                if year_detected:
                    contains_year = True
                    matched_year = year_detected.group(1)

                # Filtering Condition 2: Contains the literal tag <nplcit
                # Since we stripped the text before splitting, we can't reliably check for the tag in the *part*.
                # For safety, we'll keep the original simple count on the *whole* paragraph's raw_content_with_tags
                # or rely on LLM extraction if the paragraph contains other citation indicators.
                citation_count = raw_content_with_tags.count('<nplcit') 
                contains_nplcit = citation_count > 0 
                
                # Filtering Condition 3: Contains "genbank" (case insensitive)
                contains_genbank = bool(constants.GENBANK_REGEX.search(current_text_to_process))

                # Filtering Condition 4: Contains doi link

                contains_doi = bool(constants.DOI_REGEX.search(current_text_to_process))
                contains_volume = bool(constants.VOLUME_REGEX.search(current_text_to_process))

                # Filtering Condition 5: Contains standard names like 3GPP, IEEE, ISO, W3C
                _3gpp_standards = extract_3gpp_references(current_text_to_process)
                _ieee_standards = extract_ieee_references(current_text_to_process)
                
                contains_standards = bool(_3gpp_standards) or bool(_ieee_standards)


                # Process if AT LEAST ONE condition is met
                if contains_year or contains_nplcit or contains_genbank or contains_doi or contains_volume or contains_standards:
                    paragraphs_found += 1
                    

                    # --- Step 5a: NPL Reference Extraction  ---
                    if contains_year or contains_doi or contains_volume:
                        if len(current_text_to_process) < 20:
                            if constants.terminal_feedback:
                                 print(f"[{part_num}] SKIPPED LLM CALL: Length {len(current_text_to_process)} < 20 chars.")
                            continue # Skip the rest of the loop iteration
                        
                        if constants.terminal_feedback:
                            print(f"[{part_num}] Extracting NPL references...")

                        # Now that 'current_text_to_process' is pre-split, we call the LLM directly.
                        
                        npl_data = extract_npl_references(current_text_to_process)
                        
                        total_extracted_npl = 0
                        all_references_to_add = [] # List to collect all valid references
                        
                        # 1. Process the LLM Output
                        if isinstance(npl_data, dict) and "references" in npl_data:
                            total_extracted_npl = len(npl_data["references"])
                            
                            # Process and filter references
                            for ref in npl_data["references"]:
                                correct_npl_mistakes(ref)
                                if should_skip_npl_reference(ref):
                                    continue 
                                
                                # Collect valid references
                                all_references_to_add.append(ref) 
                        else: 
                            if constants.terminal_feedback:
                                # Print failure for the specific part
                                print(f"  ✗ NPL extraction failed: {npl_data}")

                        # 2. Add all valid references to the catalog.
                        total_added_npl = len(all_references_to_add)
                        for ref in all_references_to_add:
                            catalog.add_npl_reference(ref, part_num) 

                        # 3. Consolidate and print final feedback.
                        if total_added_npl > 0:
                            if constants.terminal_feedback:
                                # Report the final count, no need to mention "chunks" anymore
                                print(f"  ✓ Added {total_added_npl} NPL reference(s)")
                        elif total_extracted_npl > 0 and total_added_npl == 0:
                            # Success in extraction, but all were filtered out.
                            if constants.terminal_feedback:
                                print(f"  • Extracted {total_extracted_npl} references, added 0 (All filtered out)")
                        else:
                            # Total extracted was 0.
                            if constants.terminal_feedback:
                                print("  • No NPL references found.")
                  
                    # --- Step 5b: Gene Accession ID Extraction ---
                    if contains_genbank:
                        if constants.terminal_feedback:
                            print(f"[{part_num}] Extracting accession IDs...")
                        
                        # 1. Start with the pre-split paragraph part
                        text_for_accession = current_text_to_process 

                        # 2. VITAL: Step A - Remove common biological number clutter (NEW STEP)
                        simplified_bio_text = simplify_bio_numbers(text_for_accession)

                        # 3. VITAL: Step B - Simplify long chemical names
                        simplified_text = simplify_long_words(simplified_bio_text, max_length=20)

                        # 5. Pass the finally cleaned text to the extraction function
                        accession_data = extract_accessions_with_llm(simplified_text)

                        if isinstance(accession_data, dict) and "accessions" in accession_data:
                            accessions_to_add = []
                            for acc in accession_data["accessions"]:
                                if not isinstance(acc, dict):
                                    if constants.terminal_feedback:
                                        print(f"  - Skipping invalid accession entry (not a dict): {acc}")
                                    continue
                                
                                acc_type_raw = acc.get("type")
                                acc_type = acc_type_raw.strip() if acc_type_raw is not None else ""
                                
                                acc_id_raw = acc.get("id")
                                acc_id = acc_id_raw.strip() if acc_id_raw is not None else ""

                                # Filter out invalid accessions
                                if not acc_type or acc_type.lower() == "none" or not acc_id:
                                    if constants.terminal_feedback:
                                        print(f"  - Skipping invalid accession: type={repr(acc_type)}, id={repr(acc_id)}")
                                    continue

                                if acc_type == "CAS" and not constants.CAS_ACCESSION_REGEX.match(acc_id):
                                    if constants.terminal_feedback:
                                        print(f"  - Skipping invalid CAS format: {acc_id}")
                                    continue
                                
                                accessions_to_add.append(acc)

                            # Add valid accessions to catalog
                            for acc in accessions_to_add:
                                catalog.add_accession(acc, paragraph_num)
                            if constants.terminal_feedback:
                                print(f"  ✓ Added {len(accession_data['accessions'])} accession(s)")
                        else:
                            print(f"  ✗ Accession extraction failed: {accession_data}")
                    
                    # --- Step 5c: LLM Structured Standards Data Extraction (if needed) ---
                    if contains_standards:
                        if constants.terminal_feedback:
                            print(f"[{part_num}] Extracting standards...")
                        standards_data = extract_standard_references(current_text_to_process, _3gpp_standards, _ieee_standards)
                        if isinstance(standards_data, dict) and "references" in standards_data:
                            for std in standards_data["references"]:
                                catalog.add_standard(std, part_num)
                            if constants.terminal_feedback:
                                print(f"  ✓ Added {len(standards_data['references'])} standard(s)")
                        else:
                            print(f"  ✗ Standards extraction failed: {standards_data}")
                    # -------------------------------------------


        # 6. Save the catalog to a new file
        if catalog.get_all_citations():
            catalog.print_summary()
            # 1. Determine the path to the original file's directory
            input_dir = os.path.dirname(file_path)
            output_dir = os.path.join(input_dir, "Output") 

            # 1. Ensure the output directory exists
            # os.makedirs creates the directory, or does nothing if it already exists (exist_ok=True)
            try:
                os.makedirs(output_dir, exist_ok=True)
            except OSError as e:
                print(f"Error creating output directory '{output_dir}': {e}")
                return # Stop processing if we can't create the directory
            
            # 2. Generate the filename based on the original file
            
            # Get just the filename (e.g., 'document.xml')
            filename = os.path.basename(file_path)
            
            # Get the base and extension *of the filename*, not the full path
            base, ext = os.path.splitext(filename) 
            
            # Construct the new filename (e.g., 'document_citations.xml')
            new_filename_only = f"{base}_citations{ext}"
            
            # Construct the final path: 'Output/document_citations.xml'
            new_file_path = os.path.join(output_dir, new_filename_only)
            
            catalog.save_to_file(new_file_path)
        else:
            if constants.terminal_feedback:
                print("\nNo citations were found or extracted. No output file generated.")

    except ET.ParseError as e:
        print(f"\nFATAL XML Parse Error: {e}")
        print("Please ensure the selected file is a valid XML document.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        # Optionally re-raise if you need to debug
        # raise 

def main():
    """Main function to run the application flow."""
    print("--- LLM Citation Extractor ---")
    
    # 1. API CONNECTION CHECK
    try:
        # Use the imported, robust client function to check connectivity and model readiness.
        # A minimal payload is sent, relying on the function's internal retries and error handling.
        call_lm_studio_api_with_retry({
            "model": constants.MODEL_NAME,
            "messages": [{"role": "user", "content": "hello"}], # Minimal prompt
            "temperature": 0.0,
            "stream": False,
            "max_tokens": 1 
        })
        print(f"✓ Connected to LLM server at {constants.LM_STUDIO_URL}")
        
    except Exception as e: 
        # Catch any failure (connection, HTTP, timeout, etc.) raised by the retry function.
        print(f"✗ ERROR: Could not connect to LLM server at {constants.LM_STUDIO_URL}.")
        print("Please ensure the server is running with a model loaded.")
        # Optional: print(f"Details: {e}") 
        sys.exit(1)

    # 2. File Processing
    xml_file_path = select_xml_file()
    
    if xml_file_path:
        extract_paragraphs(xml_file_path)

if __name__ == "__main__":
    main()