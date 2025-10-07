NPL_REFERENCES_SCHEMA = {
    "type": "object",
    "properties": {
        "references": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": { "type": "string" },
                    "author": { 
                        "type": "array",
                        "items": { "type": "string" }
                    },
                    "publisher": { "type": "string" },
                    "publication_date": { "type": "string" },
                    "volume": { "type": "string" },
                    "pages": { "type": "string" },
                    "url": { "type": "string" }
                },
                # 'title' added to required fields to encourage LLM output
                "required": ["title", "author", "publisher", "publication_date", "volume", "pages", "url"], 
                "additionalProperties": False
            }
        }
    },
    "required": ["references"],
    "additionalProperties": False
}

STANDARDS_REFERENCES_SCHEMA = {
    "type": "object",
    "properties": {
        "references": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": { "type": "string" },
                    "standardisation_body": {
                        "type": "string",
                        "description": "The name of the standards organization.",
                        "enum": ["3GPP", "IEEE", "ISO", "W3C"]
                    },
                    "publication_date": { "type": "string" },
                    "accession_number": { "type": "string" },
                    "version": { "type": "string" },
                    "url": { "type": "string" }
                },
                "required": ["title", "standardisation_body", "publication_date", "accession_number", "version", "url"],
                "additionalProperties": False
            }
        }
    },
    "required": ["references"],
    "additionalProperties": False
}

ACCESSION_IDS_SCHEMA = {
    "type": "object",
    "properties": {
        "accessions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": { "type": "string" },
                    "id": { "type": "string" }
                },
                "required": ["type", "id"],
                "additionalProperties": False
            }
        }
    },
    "required": ["accessions"],
    "additionalProperties": False
}