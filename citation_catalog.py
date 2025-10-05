import xml.etree.ElementTree as ET

# --- Unified Document Structure ---
class CitationCatalog:
    """
    Unified structure to aggregate all extracted citations from the document.
    This will be converted to XML at the end of processing.
    """
    def __init__(self):
        self.npl_citations = []  # List of NPL citations
        self.accession_citations = []  # List of accession IDs
        self.standard_citations = []  # List of standards
        self._npl_counter = 1
        self._accession_counter = 1 # <-- Accession and Standard counters not used but kept for clarity
        self._standard_counter = 1 # <-- They rely on the shared _npl_counter for XML ID generation
        self._npl_unique_keys = set()
    
    def add_npl_reference(self, reference_data, paragraph_num, crossref_id=None):
        """
        Add a non-patent literature reference to the catalog.
        Maps from LLM schema to unified format.
        """
        # 0. Create the unique key for this reference
        author_string = ", ".join(reference_data.get("author", [])).strip()
        title = reference_data.get("title", "")
        publisher = reference_data.get("publisher", "")
        publication_date = reference_data.get("publication_date", "")

        # Use a combination of author, title, publisher, and date as the unique identifier
        citation_key = (
            author_string.lower().strip(),
            title.lower().strip(),
            publisher.lower().strip(),
            publication_date.lower().strip()
        )
        
        # 0a. Check for GLOBAL DUPLICATE
        if citation_key in self._npl_unique_keys:
            # Found a duplicate already in the catalog, do not add.
            return None 

        # 0b. Add the key to the global set before adding the citation
        self._npl_unique_keys.add(citation_key)
        
        # 1. Capture the current sequential number
        current_seq_num = self._npl_counter
        
        # 2. Construct IDs based on the current number
        citation_id = f"ref-ncit{current_seq_num:04d}"
        default_crossref_id = f"ncit{current_seq_num:04d}"
        
        # 3. Increment the counter for the *next* citation
        self._npl_counter += 1
        
        unified_citation = {
            "id": citation_id,
            "npl_type": "s",  # 's' for serial/article
            "crossrefid": crossref_id or default_crossref_id, 
            "paragraph_num": paragraph_num,
            "citation_type": "article",
            "authors": reference_data.get("author", []),
            "title": reference_data.get("title", ""),
            "serial_title": reference_data.get("publisher", ""),
            "publication_date": reference_data.get("publication_date", ""),
            "volume": reference_data.get("volume", ""),
            "pages": reference_data.get("pages", ""),
            "url": reference_data.get("url", "")
        }
        
        self.npl_citations.append(unified_citation)
        return citation_id
    
    def add_accession(self, accession_data, paragraph_num, crossref_id=None):
        """
        Add a biological accession ID to the catalog.
        Maps from LLM schema to unified format.
        """
        
        # 1. Capture the current sequential number
        current_seq_num = self._npl_counter
        
        # 2. Construct IDs based on the current number
        citation_id = f"ref-ncit{current_seq_num:04d}"
        default_crossref_id = f"ncit{current_seq_num:04d}"
        
        # 3. Increment the counter for the *next* citation
        self._npl_counter += 1
        
        unified_citation = {
            "id": citation_id,
            "npl_type": "e",  # 'e' for electronic/online
            "crossrefid": crossref_id or default_crossref_id, 
            "paragraph_num": paragraph_num,
            "citation_type": "online",
            "online_title": accession_data.get("type", ""),
            "accession_number": accession_data.get("id", "")
        }
        
        self.accession_citations.append(unified_citation)
        return citation_id
    
    def add_standard(self, standard_data, paragraph_num, crossref_id=None):
        """
        Add a standard reference to the catalog.
        Maps from LLM schema to unified format.
        """
        # 1. Capture the current sequential number
        current_seq_num = self._npl_counter
        
        # 2. Construct IDs based on the current number
        citation_id = f"ref-ncit{current_seq_num:04d}"
        default_crossref_id = f"ncit{current_seq_num:04d}"
        
        # 3. Increment the counter for the *next* citation
        self._npl_counter += 1
        
        unified_citation = {
            "id": citation_id,
            "npl_type": "t",  # 't' for technical standard
            # FIX: Use the calculated default_crossref_id
            "crossrefid": crossref_id or default_crossref_id, 
            "paragraph_num": paragraph_num,
            "citation_type": "standard",
            "title": standard_data.get("title", ""),
            "standardisation_body": standard_data.get("standardisation_body", ""),
            "publication_date": standard_data.get("publication_date", ""),
            "accession_number": standard_data.get("accession_number", ""),
            "version": standard_data.get("version", ""),
            "url": standard_data.get("url", "")
        }
        
        self.standard_citations.append(unified_citation)
        return citation_id
    
    def get_all_citations(self):
        """Returns all citations in a single list."""
        all_citations = self.npl_citations + self.accession_citations + self.standard_citations
        # Sort by the numeric part of the ID to ensure consistent order
        all_citations.sort(key=lambda citation: int(citation["id"].replace("ref-ncit", "")))
        return all_citations    
    
    def to_xml(self):
        """
        Converts the entire catalog to XML format matching the target schema.
        Returns an ElementTree root element.
        """
        root = ET.Element("ep-citation-catalog")
        
        # Add all citations (order: NPL, then accessions, then standards)
        for citation in self.get_all_citations():
            nplcit = ET.SubElement(root, "nplcit")
            nplcit.set("id", citation["id"])
            nplcit.set("npl-type", citation["npl_type"])
            nplcit.set("crossrefid", citation["crossrefid"])
            
            if citation["citation_type"] == "article":
                self._build_article_xml(nplcit, citation)
            elif citation["citation_type"] == "online":
                self._build_online_xml(nplcit, citation)
            elif citation["citation_type"] == "standard":
                self._build_standard_xml(nplcit, citation)
        
        return root
    
    def _build_article_xml(self, parent, citation):
        """Build XML structure for article citations."""
        article = ET.SubElement(parent, "article")
        
        # Authors
        for author_name in citation.get("authors", []):
            author = ET.SubElement(article, "author")
            name = ET.SubElement(author, "name")
            name.text = author_name
        
        # Article title (FIX: Map the 'title' field here)
        atl = ET.SubElement(article, "atl")
        atl.text = citation.get("title", "") # <-- FIX: Now maps the title
        
        # Serial info
        serial = ET.SubElement(article, "serial")
        sertitle = ET.SubElement(serial, "sertitle")
        sertitle.text = citation.get("serial_title", "")
        
        pubdate = ET.SubElement(serial, "pubdate")
        sdate = ET.SubElement(pubdate, "sdate")
        sdate.text = citation.get("publication_date", "")
        ET.SubElement(pubdate, "edate")
        
        if citation.get("volume"):
            vid = ET.SubElement(serial, "vid")
            vid.text = citation["volume"]
        
        # Pages
        if citation.get("pages"):
            location = ET.SubElement(article, "location")
            pp = ET.SubElement(location, "pp")
            ppf = ET.SubElement(pp, "ppf")
            ppl = ET.SubElement(pp, "ppl")
            
            # Try to split pages like "3790-3799"
            pages = citation["pages"]
            if "-" in pages:
                page_parts = pages.split("-")
                ppf.text = page_parts[0].strip()
                ppl.text = page_parts[1].strip() if len(page_parts) > 1 else ""
            else:
                ppf.text = pages

        # Url
        if citation.get("url"):
            url_elem = ET.SubElement(article, "url")
            url_elem.text = citation["url"]
    
    def _build_online_xml(self, parent, citation):
        """Build XML structure for online/accession citations."""
        online = ET.SubElement(parent, "online")
        
        online_title = ET.SubElement(online, "online-title")
        online_title.text = citation.get("online_title", "")
        
        absno = ET.SubElement(online, "absno")
        absno.text = citation.get("accession_number", "")
        
        ET.SubElement(online, "avail")
    
    def _build_standard_xml(self, parent, citation):
        """Build XML structure for standard citations."""
        standard = ET.SubElement(parent, "standard")
        
        std_title = ET.SubElement(standard, "std-title")
        std_title.text = citation.get("title", "")
        
        std_body = ET.SubElement(standard, "std-body")
        std_body.text = citation.get("standardisation_body", "")
        
        std_num = ET.SubElement(standard, "std-number")
        std_num.text = citation.get("accession_number", "")
        
        if citation.get("version"):
            std_ver = ET.SubElement(standard, "std-version")
            std_ver.text = citation["version"]
    
    def save_to_file(self, filepath):
        """Save the catalog as XML to a file."""
        root = self.to_xml()
        tree = ET.ElementTree(root)
        ET.indent(tree, space="    ")  # Pretty print
        tree.write(filepath, encoding="UTF-8", xml_declaration=True)
        print(f"\n✓ Citation catalog saved to: {filepath}")
    
    def print_summary(self):
        """Print a summary of collected citations."""
        print(f"\n{'='*70}")
        print("CITATION CATALOG SUMMARY")
        print(f"{'='*70}")
        print(f"NPL References: {len(self.npl_citations)}")
        print(f"Accession IDs: {len(self.accession_citations)}")
        print(f"Standards: {len(self.standard_citations)}")
        print(f"Total Citations: {len(self.get_all_citations())}")
        print(f"{'='*70}\n")
