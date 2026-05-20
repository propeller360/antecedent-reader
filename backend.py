import re
import os
import json

# Setup the configuration path in the execution folder
CONFIG_FILE = "app_config.json"

def get_run_count_and_lock():
    """
    Reads the configuration file to determine the launch state.
    Returns True if it is the absolute first launch, False otherwise.
    """
    if not os.path.exists(CONFIG_FILE):
        # File doesn't exist, meaning this is the absolute first launch
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump({"first_run_completed": True}, f)
        except Exception:
            pass # Fallback safety cage for restricted permission folders
        return True
    
    return False

# Execute the run counter check before loading heavy dependencies
is_first_run = get_run_count_and_lock()

# Secure the absolute offline deep-learning parameters based on the run count
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

if is_first_run:
    print("--- FIRST RUN DETECTED: Network gate open for model caching ---")
    os.environ["HF_HUB_OFFLINE"] = "0"
else:
    print("--- PROD RUN: Pure offline environment locked ---")
    os.environ["HF_HUB_OFFLINE"] = "1"


try:
    import spacy
    import en_core_web_sm
    from sentence_transformers import SentenceTransformer, util
except ImportError:
    raise ImportError("Please ensure 'spacy', 'en_core_web_sm', and 'sentence-transformers' are installed.")

print("Loading local NLP grammatical chunker module...")
nlp = en_core_web_sm.load()

print("Loading local semantic transformer vector engine...")
model = SentenceTransformer('all-MiniLM-L6-v2')

# ... (The rest of your backend functions like split_into_individual_claims remain exactly the same)


def extract_reference_numerals_from_desc(description_text):
    """
    Scans the Detailed Description to find structural reference numerals.
    Matches patterns like: 'fluid 102', 'transducer element (104)', 'layer 206a'
    Returns a dictionary of {cleaned_element_name: numeral}
    """
    if not description_text.strip():
        return {}
        
    # Pattern to match nouns/phrases followed by a number (optional parentheses or alphanumeric suffixes like 102a)
    pattern = r'\b([a-zA-Z\s\-]{3,40?})\s*\(?(\d{3,4}[a-z]?)\)?\b'
    matches = re.findall(pattern, description_text)
    
    numeral_map = {}
    for element, num in matches:
        # Strip trailing/leading garbage and common stop words from the discovered phrases
        clean_el = element.lower().strip()
        clean_el = re.sub(r'^(a|an|the|said|such|each|any)\s+', '', clean_el)
        
        # Avoid registering general patent layout terms as component phrases
        if clean_el in ["figure", "fig", "embodiment", "claim", "step", "method", "invention", "aspect"]:
            continue
            
        if len(clean_el) > 2:
            # Standardize pluralization endings for dictionary lookup consistency
            if clean_el.endswith('s') and not clean_el.endswith('ss'):
                clean_el = clean_el[:-1]
            numeral_map[clean_el.strip()] = num
            
    return numeral_map


def split_into_individual_claims(raw_claims_text):
    claim_start_pattern = r'(?:^[Cc]laim\s+)?(\d+)[.\s:]'
    lines = raw_claims_text.split('\n')
    parsed_claims = {}
    current_claim_num = None
    current_claim_text = []

    for line in lines:
        cleaned_line = line.strip()
        if not cleaned_line:
            continue
        match = re.match(claim_start_pattern, cleaned_line)
        if match:
            if current_claim_num is not None:
                parsed_claims[current_claim_num] = " ".join(current_claim_text)
            current_claim_num = int(match.group(1))
            text_body = cleaned_line[match.end():].strip()
            current_claim_text = [text_body]
        else:
            if current_claim_num is not None:
                current_claim_text.append(cleaned_line)
                
    if current_claim_num is not None:
        parsed_claims[current_claim_num] = " ".join(current_claim_text)
        
    return parsed_claims


def extract_parent_claims(claim_text):
    pattern = r'\b[Cc]laims?\s+(\d+)(?:\s+(?:or|and)\s+(\d+))?\b'
    matches = re.findall(pattern, claim_text)
    parents = []
    for match in matches:
        for num_str in match:
            if num_str:
                parents.append(int(num_str))
    return parents


def truncate_at_patent_modifiers(phrase_text):
    t = phrase_text.lower().strip()
    modifiers = [r'\bhaving\b', r'\bcomprising\b', r'\bconfigured\b', r'\bpositioned\b', r'\bwherein\b', r'\bto\b']
    for mod in modifiers:
        t = re.split(mod, t)[0].strip()
    
    t = re.sub(r'\b(plurality of|array of|two-dimensional array of|set of|matrix of)\s+', '', t)
    if t.endswith('s') and not t.endswith('ss'):
        t = t[:-1]
    return t.strip()


def analyze_patent_draft(raw_claims_text, raw_description_text):
    """
    Unified analysis gate. Ingests claims AND description text.
    Returns: (antecedent_html_report, numeral_suggestions_html_report)
    """
    claims_dict = split_into_individual_claims(raw_claims_text)
    
    # 1. Harvest reference numerals out of the description
    discovered_numerals = extract_reference_numerals_from_desc(raw_description_text)
    
    # Seed the primary semantic tracking engine using terms validated by the Description
    # Maps {claim_num: [{"text": clean_text, "vector": vec}]}
    semantic_registry = {} 
    
    antecedent_report = []
    numeral_report = []

    for claim_num in sorted(claims_dict.keys()):
        text = claims_dict[claim_num]
        doc = nlp(text)
        parents = extract_parent_claims(text)
        
        inherited_elements = []
        invalid_dependency = False
        for p in parents:
            if p not in claims_dict:
                invalid_dependency = True
            elif p in semantic_registry:
                inherited_elements.extend(semantic_registry[p])
                
        claim_ant_html = f"<h4>Claim {claim_num}:</h4>"
        claim_num_html = f"<h4>Claim {claim_num} Numeral Suggestions:</h4><ul>"
        has_numeral_suggestions = False
        
        if invalid_dependency:
            claim_ant_html += f"<p style='color: #d9534f;'><b>[Dependency Error]:</b> References a non-existent claim number.</p>"
            antecedent_report.append(claim_ant_html)
            numeral_report.append(f"<h4>Claim {claim_num} Numeral Suggestions:</h4><p style='color: gray;'>Skipped due to dependency failure.</p>")
            semantic_registry[claim_num] = []
            continue

        local_elements = []
        annotated_words = []
        
        chunk_map = {chunk.start: chunk for chunk in doc.noun_chunks}
        
        skip_until = -1
        for token in doc:
            if token.i < skip_until:
                continue
                
            if token.i in chunk_map:
                chunk = chunk_map[token.i]
                skip_until = chunk.end
                
                chunk_words = [t.text for t in chunk]
                det = chunk_words[0].lower() if chunk_words else ""
                base_phrase = " ".join(chunk_words[1:]).strip().lower() if det in ['a', 'an', 'the', 'said'] else " ".join(chunk_words).strip().lower()
                
                clean_phrase = truncate_at_patent_modifiers(base_phrase)
                
                if not clean_phrase or "claim" in clean_phrase or clean_phrase in ["method", "apparatus", "system", "taper"]:
                    annotated_words.append(chunk.text)
                    continue
                
                if "of claim" in text[chunk.start_char:chunk.end_char + 25].lower():
                    annotated_words.append(chunk.text)
                    continue

                phrase_vector = model.encode(clean_phrase, convert_to_tensor=True)
                
                # --- DESCRIPTION CROSS-REFERENCE ENRICHMENT ---
                # If the description explicitly maps this exact element, increase matching confidence baseline
                description_boost = clean_phrase in discovered_numerals
                
                all_accessible = inherited_elements + local_elements
                matched_basis = False
                for item in all_accessible:
                    if clean_phrase == item["text"] or clean_phrase in item["text"] or item["text"] in clean_phrase:
                        matched_basis = True
                        break
                    similarity = util.cos_sim(phrase_vector, item["vector"]).item()
                    threshold = 0.78 if description_boost else 0.82  # Dynamic safety envelope
                    if similarity > threshold:
                        matched_basis = True
                        break

                # --- ANTECEDENT RULE CHECKING ---
                if det in ['a', 'an']:
                    if matched_basis:
                        annotated_words.append(f"<b style='color: red; text-decoration: underline;'>{chunk.text}</b>")
                        claim_ant_html += f"<p style='color: #d9534f;'>→ <i>Error: Redefining element '{clean_phrase}' using '{det}'. Use 'the' or 'said'.</i></p>"
                    else:
                        local_elements.append({"text": clean_phrase, "vector": phrase_vector})
                        annotated_words.append(chunk.text)
                        
                elif det in ['the', 'said']:
                    if not matched_basis:
                        annotated_words.append(f"<b style='color: red; text-decoration: underline;'>{chunk.text}</b>")
                        claim_ant_html += f"<p style='color: #d9534f;'>→ <i>Error: Missing antecedent basis for '{chunk.text}'.</i></p>"
                    else:
                        local_elements.append({"text": clean_phrase, "vector": phrase_vector})
                        annotated_words.append(chunk.text)
                else:
                    local_elements.append({"text": clean_phrase, "vector": phrase_vector})
                    annotated_words.append(chunk.text)
                
                # --- REFERENCE NUMERAL TRACKING MATCHING (Option B) ---
                # Check if the clean component matches an item extracted from the description
                if clean_phrase in discovered_numerals:
                    assigned_num = discovered_numerals[clean_phrase]
                    # Only suggest if the numeral isn't written directly behind the noun chunk
                    if assigned_num not in text[chunk.end_char:chunk.end_char+15]:
                        claim_num_html += f"<li>Found: '<b>{chunk.text}</b>' → Suggest adding numeral <b>({assigned_num})</b></li>"
                        has_numeral_suggestions = True
            else:
                annotated_words.append(token.text_with_ws)

        semantic_registry[claim_num] = inherited_elements + local_elements
        
        reconstructed_text = "".join(annotated_words).replace(" .", ".").replace(" ,", ",")
        claim_ant_html = f"<h4>Claim {claim_num}:</h4><p>{reconstructed_text}</p>" + claim_ant_html.replace(f"<h4>Claim {claim_num}:</h4>", "")
        antecedent_report.append(claim_ant_html)
        
        # Wrap up numeral output window presentation text
        if not has_numeral_suggestions:
            claim_num_html += "<li style='color: gray; list-style-type: none;'>No missing reference numerals found.</li>"
        claim_num_html += "</ul>"
        numeral_report.append(claim_num_html)

    return "<hr>".join(antecedent_report), "<hr>".join(numeral_report)
