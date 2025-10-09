
import xml.etree.ElementTree as ET
import sys
import os 
import constants # Contains Regexes and API settings
from citation_catalog import CitationCatalog 
from citation_filters import should_skip_npl_reference 
from citation_corrections import correct_npl_mistakes
from utils import select_xml_file, extract_paragraph_texts

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
            if paragraph_num:
                
                # Filtering Condition 1: Contains a year between 1900 and 2025
                
                matched_year = None 
                contains_year = False
                
                # Use stripped_text for boundary-based year matching
                year_detected = constants.YEAR_REGEX.search(stripped_text)
                
                if year_detected:
                    contains_year = True
                    matched_year = year_detected.group(1)

                # Filtering Condition 2: Contains the literal tag <nplcit
                citation_count = raw_content_with_tags.count('<nplcit') 
                contains_nplcit = citation_count > 0
                
                # Filtering Condition 3: Contains "genbank" (case insensitive)
                contains_genbank = bool(constants.GENBANK_REGEX.search(stripped_text))

                # Filtering Condition 4: Contains doi link

                contains_doi = bool(constants.DOI_REGEX.search(stripped_text))

                # Filtering Condition 5: Contains standard names like 3GPP, IEEE, ISO, W3C
                _3gpp_standards = extract_3gpp_references(stripped_text)
                _ieee_standards = extract_ieee_references(stripped_text)
                
                contains_standards = bool(_3gpp_standards) or bool(_ieee_standards)


                # Process if AT LEAST ONE condition is met
                if contains_year or contains_nplcit or contains_genbank or contains_doi or contains_standards:
                    paragraphs_found += 1
                    
                    # --- Step 5a: NPL Reference Extraction ---
                    if contains_year or contains_doi:
                        if constants.terminal_feedback:
                            print(f"[{paragraph_num}] Extracting NPL references...")
                        npl_data = extract_npl_references(stripped_text)

                        if isinstance(npl_data, dict) and "references" in npl_data:
                                            
                            references_to_add = []
                            
                            for ref in npl_data["references"]:

                                # --- CORRECTION SECTION START ---
                                # Apply heuristic corrections to the reference data dictionary in-place
                                correct_npl_mistakes(ref)
                                
                                # Re-read variables after potential correction
                                title = ref.get("title", "")
                                publisher = ref.get("publisher", "")
                                # --- CORRECTION SECTION END ---


                                # --- FILTERING LOGIC (Externalized) ---
                                if should_skip_npl_reference(ref):
                                    continue # Skip this reference
                                
                                references_to_add.append(ref)
                            
                            # Now add only the references that passed the filter
                            total_extracted = len(npl_data['references'])
                            total_added = len(references_to_add)
                                    
                            # Now add only the references that passed the filter
                            for ref in references_to_add:
                                catalog.add_npl_reference(ref, paragraph_num)

                            if total_added > 0:
                                if constants.terminal_feedback:
                                    print(f"  ✓ Added {total_added} NPL reference(s)")
                            elif total_extracted > 0 and total_added == 0:
                                # Success in filtering, but nothing left to add. Not a failure.
                                if constants.terminal_feedback:
                                    print(f"  • Extracted {total_extracted} references, added {total_added}")
                            else:
                                # npl_data was valid, but references array was empty, which is fine.
                                if constants.terminal_feedback:
                                    print("  • No NPL references found.")

                        else:
                            print(f"  ✗ NPL extraction failed: {npl_data}")

                    
                    # --- Step 5b: Gene Accession ID Extraction  ---
                    if contains_genbank:
                        if constants.terminal_feedback:
                            print(f"[{paragraph_num}] Extracting accession IDs...")
                        accession_data = extract_accessions_with_llm(stripped_text)

                        if isinstance(accession_data, dict) and "accessions" in accession_data:
                            accessions_to_add = []
                            for acc in accession_data["accessions"]:
                                acc_type = acc.get("type", "").strip()
                                acc_id = acc.get("id", "").strip()


                                # Filter out invalid accessions
                                if not acc_type or acc_type.lower() == "none":
                                    if constants.terminal_feedback:
                                        print(f"  - Skipping accession (missing or invalid type): type={repr(acc_type)}, id={repr(acc_id)}")
                                    continue
                                
                                if not acc_id:
                                    if constants.terminal_feedback:
                                        print(f"  - Skipping accession (missing ID): type={repr(acc_type)}, id={repr(acc_id)}")
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
                            print(f"[{paragraph_num}] Extracting standards...")
                        standards_data = extract_standard_references(stripped_text, _3gpp_standards, _ieee_standards)
                        
                        if isinstance(standards_data, dict) and "references" in standards_data:
                            for std in standards_data["references"]:
                                catalog.add_standard(std, paragraph_num)
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