import xml.etree.ElementTree as ET
import os
import sys
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
import constants 
from citation_catalog import CitationCatalog 
from citation_filters import should_skip_npl_reference 
from citation_corrections import correct_npl_mistakes
from utils import extract_paragraph_texts # Only need this one
from llm_client import (
    extract_npl_references,
    extract_standard_references,
    extract_accessions_with_llm,
    extract_3gpp_references,
    extract_ieee_references,
    call_lm_studio_api_with_retry
)

# Initialize the FastAPI application
app = FastAPI(
    title="Citation Extraction Service",
    description="API to extract structured citations from raw XML text using LLMs.",
    version="1.0.0"
)

# --- LLM API Check (Moved to startup event) ---
@app.on_event("startup")
async def startup_event():
    """Checks the LLM API connection when the FastAPI server starts."""
    print("--- LLM Citation Extractor Service Startup ---")
    try:
        call_lm_studio_api_with_retry({
            "model": constants.MODEL_NAME,
            "messages": [{"role": "user", "content": "hello"}],
            "temperature": 0.0,
            "stream": False,
            "max_tokens": 1 
        })
        print(f"✓ Connected to LLM server at {constants.LM_STUDIO_URL}")
        
    except Exception as e: 
        print(f"✗ FATAL ERROR: Could not connect to LLM server at {constants.LM_STUDIO_URL}.")
        print("Service will start, but citation extraction will fail.")
        # We don't exit the process in a service, but log the error prominently.

#  Start the server suing  uvicorn api_service:app --reload 

def process_xml_content(xml_text: str) -> str:
    """
    Parses XML content from a string and extracts citations.
    This replaces the logic previously in extract_paragraphs.
    Returns the final citation XML string.
    """
    if not xml_text:
        raise ValueError("Input XML content cannot be empty.")

    # Initialize the citation catalog
    catalog = CitationCatalog()

    try:
        # 1. Parse the XML content from the input string
        root = ET.fromstring(xml_text)
        
        # 2. Iterate through all <p> elements in the document
        paragraphs_found = 0
        
        for p_element in root.iter('p'):
            
            # 3. Extract the 'num' attribute
            paragraph_num = p_element.get('num')            
            
            # --- Extracting full XML content, including nested tags ---
            # NOTE: We assume extract_paragraph_texts is correctly imported from utils
            raw_content_with_tags, stripped_text = extract_paragraph_texts(
                p_element, 
                constants.XML_TAGS 
            )
            
            # 4. Check if the required 'num' attribute exists AND apply filtering
            if paragraph_num:
                
                # Filtering Condition 1: Contains a year between 1900 and 2025
                year_detected = constants.YEAR_REGEX.search(stripped_text)
                contains_year = bool(year_detected)
                
                # Filtering Condition 2: Contains the literal tag <nplcit
                citation_count = raw_content_with_tags.count('<nplcit') 
                contains_nplcit = citation_count > 0
                
                # Filtering Condition 3: Contains "genbank" (case insensitive)
                contains_genbank = bool(constants.GENBANK_REGEX.search(stripped_text))

                # Filtering Condition 4: Contains doi link
                contains_doi = bool(constants.DOI_REGEX.search(stripped_text))

                # Filtering Condition 5: Contains standard names like 3GPP, IEEE
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
                                # Apply heuristic corrections
                                correct_npl_mistakes(ref)
                                
                                # Filter references
                                if should_skip_npl_reference(ref):
                                    continue
                                
                                references_to_add.append(ref)
                            
                            for ref in references_to_add:
                                catalog.add_npl_reference(ref, paragraph_num)

                            if len(references_to_add) > 0:
                                if constants.terminal_feedback:
                                    print(f"  ✓ Added {len(references_to_add)} NPL reference(s)")
                            else:
                                if constants.terminal_feedback:
                                    print("  • No NPL references found or added.")
                        else:
                            print(f"  ✗ NPL extraction failed for P:{paragraph_num}")

                    
                    # --- Step 5b: Gene Accession ID Extraction  ---
                    if contains_genbank:
                        if constants.terminal_feedback:
                            print(f"[{paragraph_num}] Extracting accession IDs...")
                        accession_data = extract_accessions_with_llm(stripped_text)

                        if isinstance(accession_data, dict) and "accessions" in accession_data:
                            accessions_to_add = []
                            for acc in accession_data["accessions"]:

                                if not isinstance(acc, dict):
                                    if constants.terminal_feedback:
                                        print(f"  ⚠ Skipping invalid accession entry: {acc}")
                                    continue 

                                acc_type = acc.get("type", "").strip()
                                acc_id = acc.get("id", "").strip()

                                # Filter out invalid accessions
                                if not acc_type or acc_type.lower() == "none" or not acc_id:
                                    continue
                                
                                accessions_to_add.append(acc)

                            for acc in accessions_to_add:
                                catalog.add_accession(acc, paragraph_num)

                            if constants.terminal_feedback:
                                print(f"  ✓ Added {len(accessions_to_add)} accession(s)")
                        else:
                            print(f"  ✗ Accession extraction failed for P:{paragraph_num}")
                    
                    # --- Step 5c: Standards Data Extraction ---
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
                            print(f"  ✗ Standards extraction failed for P:{paragraph_num}")
                    # -------------------------------------------

        # 6. Generate the XML output
        if catalog.get_all_citations():
            catalog.print_summary()
            
            # Use ET.tostring to get the XML as a bytes object
            root_element = catalog.to_xml()
            
            # Generate the final XML string with UTF-8 declaration and pretty printing
            # The XML declaration is necessary for a complete document
            xml_bytes = ET.tostring(root_element, encoding="UTF-8", xml_declaration=True)
            
            # Pretty print (indent) the XML
            # NOTE: ET.indent requires Python 3.9+, otherwise you'll need a different pretty-printing library.
            # We'll use a simple approach for compatibility, or rely on ET.tostring with encoding.
            
            # For best output (assuming Python 3.9+ for ET.indent):
            # ET.indent(root_element, space="    ") 
            # xml_bytes = ET.tostring(root_element, encoding="UTF-8", xml_declaration=True)
            
            # Return the decoded string
            return xml_bytes.decode("UTF-8")
            
        else:
            # If no citations found, return an empty but valid catalog XML structure
            empty_root = ET.Element("ep-citation-catalog")
            return ET.tostring(empty_root, encoding="UTF-8", xml_declaration=True).decode("UTF-8")


    except ET.ParseError as e:
        # Catch XML parsing errors from the input text
        raise HTTPException(
            status_code=400, 
            detail=f"Input XML Parse Error: {e}. Please ensure the input text is valid XML."
        )
    except Exception as e:
        # Catch any unexpected errors during LLM calls or processing
        print(f"An unexpected error occurred during processing: {e}", file=sys.stderr)
        raise HTTPException(
            status_code=500, 
            detail=f"Internal processing error: {e}"
        )


# --- API Endpoint Definition ---

@app.post("/process_xml", 
          response_class=Response, 
          responses={200: {"content": {"application/xml": {}}}},
          summary="Extracts citations from an XML document string.")
async def process_xml_input(request: Request):
    """
    Accepts raw XML text in the request body, processes it to extract citations, 
    and returns the structured citation catalog XML.
    """
    try:
        # Get the raw body as text
        xml_input_text = await request.body()
        
        # Decode the bytes to a string
        xml_input_text = xml_input_text.decode('utf-8')
        
        # Process the content
        xml_output = process_xml_content(xml_input_text)
        
        # Return the resulting XML string with the correct Content-Type header
        return Response(content=xml_output, media_type="application/xml")
        
    except HTTPException as e:
        # Re-raise explicit HTTP exceptions (e.g., 400 XML Parse Error)
        raise e
    except Exception as e:
        # Catch all other exceptions and return a generic 500 error
        raise HTTPException(
            status_code=500,
            detail="Failed to process request due to an unexpected server error."
        )