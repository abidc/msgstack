"""Controlled Vocabulary Sweeper — filter generated outputs based on brand rules."""

import re
import logging
from uuid import UUID
from src.store import Store

log = logging.getLogger(__name__)

def apply_controlled_vocabulary(text: str, domain_id: UUID, store: Store) -> str:
    """
    Query the 'word_list' entries in the active brand guide or canon domain
    representing banned terms or owned language. Applies replacements or flags warnings.
    """
    entries = store.get_canon_entries(domain_id, include_unapproved=False)
    
    # Extract banned word rules
    # Expected format: "Banned: term1, term2 -> replacement" or "term1 -> term2"
    replacements = {}
    
    for entry in entries:
        if entry.section_type == "word_list":
            content = entry.content.strip()
            # Parse lines of banned mappings
            for line in content.split("\n"):
                if "->" in line:
                    parts = line.split("->")
                    banned = parts[0].replace("Banned:", "").replace("banned:", "").strip().lower()
                    replacement = parts[1].strip()
                    replacements[banned] = replacement
                elif ":" in line and ("banned" in line.lower() or "avoid" in line.lower()):
                    # Simple list to remove
                    words = line.split(":", 1)[1].split(",")
                    for w in words:
                        replacements[w.strip().lower()] = ""

    # Apply replacements
    modified_text = text
    for banned_term, replacement in replacements.items():
        if banned_term:
            # Case-insensitive word boundary replacement
            pattern = re.compile(rf"\b{re.escape(banned_term)}\b", re.IGNORECASE)
            modified_text = pattern.sub(replacement, modified_text)

    return modified_text
