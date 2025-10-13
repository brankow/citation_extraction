from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

# --- 1. Standards Schema ---

# Enum for strictly defined standard bodies
class StandardBody(str, Enum):
    """Enforce the use of specific standardization bodies."""
    G3PP = "3GPP"
    IEEE = "IEEE"
    ISO = "ISO"
    W3C = "W3C"

class StandardReference(BaseModel):
    """Corresponds to the 'items' object in STANDARDS_REFERENCES_SCHEMA."""
    title: str = Field(..., description="A short descriptive text following or associated with the standard (if present, else empty string).")
    standardisation_body: StandardBody = Field(
        ...,
        description="The organization name (e.g., 3GPP, IEEE). Must be one of the enumerated values."
    )
    accession_number: str = Field(..., description="The alphanumeric code uniquely identifying the standard (e.g., TS 23.501, 802.11be).")
    version: str = Field(..., description="The version or edition of the standard (if present, else empty string).")

class StandardsReferences(BaseModel):
    """Corresponds to the root STANDARDS_REFERENCES_SCHEMA."""
    references: List[StandardReference] = Field(
        ...,
        description="A list of standard references found in the text."
    )

# --- 2. NPL References Schema ---

class NPLReference(BaseModel):
    """Corresponds to the 'items' object in NPL_REFERENCES_SCHEMA."""
    title: str = Field(..., description="The main title of the article or document.")
    author: List[str] = Field(..., description="A list of authors' names.")
    publisher: str = Field(..., description="The journal, conference name, or publisher.")
    publication_date: str = Field(..., description="The date of publication, in any format.")
    volume: str = Field(..., description="The volume number of the publication (if applicable).")
    pages: str = Field(..., description="The page range or single page number (if applicable).")
    url: str = Field(..., description="A URL or DOI associated with the reference.")

class NPLReferences(BaseModel):
    """Corresponds to the root NPL_REFERENCES_SCHEMA."""
    references: List[NPLReference] = Field(
        ...,
        description="A list of non-patent literature references found in the text."
    )

# --- 3. Accession IDs Schema ---

class AccessionItem(BaseModel):
    """Corresponds to the 'items' object in ACCESSION_IDS_SCHEMA."""
    type: str = Field(..., description="The type of accession ID (e.g., CAS, Uniprot, GenBank).")
    id: Optional[str] = Field(default="", description="The unique accession number")

class AccessionIDs(BaseModel):
    """Corresponds to the root ACCESSION_IDS_SCHEMA."""
    accessions: List[AccessionItem] = Field(
        ...,
        description="A list of accession IDs (CAS numbers, GenBank, etc.) found in the text."
    )