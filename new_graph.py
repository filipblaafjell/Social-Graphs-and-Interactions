import os
import re
import networkx as nx
from collections import Counter
import io
from rapidfuzz import process
import requests

# --- LOAD BASE GRAPH ---
url = "https://raw.githubusercontent.com/filipblaafjell/Social-Graphs-and-Interactions/main/rock_bands_graph.graphml"
response = requests.get(url)
response.raise_for_status()
G = nx.read_graphml(io.BytesIO(response.content))
print("Loaded rock music bands graph from GitHub")

if "AllMusic" in G:
    G.remove_node("AllMusic")
print("Removed 'AllMusic' node if it existed.")

# --- LOCAL WIKITEXT SOURCE ---
WIKI_DIR = r"C:/Users/tempuser/DTU/soical_graphs/assignment2/bands"  # adjust as needed

def find_wiki_file(artist_name, wiki_files):
    """Find best matching saved file for a given artist."""
    norm_files = [f.lower().replace(".txt", "").replace("_", " ") for f in wiki_files]
    artist_norm = artist_name.lower().strip()
    match, score, _ = process.extractOne(artist_norm, norm_files)
    if score > 85:
        return wiki_files[norm_files.index(match)]
    return None

def extract_genres_from_text(text):
    """Extract genres from Wikipedia infobox with improved regex patterns"""
    
    # Multiple patterns to handle different infobox formats
    patterns = [
        # Pattern 1: | genre = {{flatlist| or {{hlist| with content
        r"\|\s*(genre|genres|musical[_ ]style)\s*=\s*\{\{(?:flatlist|hlist)\|[^}]*?\*\s*\[\[([^\]]+)\]\].*?\}\}",
        # Pattern 2: | genre = {{flatlist| or {{hlist| multi-line until }}
        r"\|\s*(genre|genres|musical[_ ]style)\s*=\s*\{\{(?:flatlist|hlist)\|([^}]+)\}\}",
        # Pattern 3: | genre = direct content until next |
        r"\|\s*(genre|genres|musical[_ ]style)\s*=\s*([^|}]+?)(?=\n\||\n\}\}|\n$)",
        # Pattern 4: More permissive - genre field until obvious termination
        r"\|\s*(genre|genres|musical[_ ]style)\s*=\s*(.*?)(?=\n\|\s*[a-zA-Z]|\n\}\})"
    ]
    
    section = ""
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)
        if match:
            section = match.group(2)
            break
    
    if not section:
        return []
    
    # Extract genres from the section
    genres = []
    
    # Method 1: Extract from [[...]] links (most reliable)
    wiki_links = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", section)
    for link in wiki_links:
        clean_link = link.strip().lower()
        if clean_link and len(clean_link) > 2 and not clean_link.startswith('category:'):
            genres.append(clean_link)
    
    # Method 2: If no links found, try to extract from plain text
    if not genres:
        # Remove template syntax and extract text
        cleaned_section = re.sub(r'\{\{[^}]*\}\}', '', section)  # Remove templates
        cleaned_section = re.sub(r'\[\[[^\]]*\]\]', '', cleaned_section)  # Remove remaining links
        cleaned_section = re.sub(r'<[^>]*>', '', cleaned_section)  # Remove HTML tags
        
        # Split by common separators
        potential_genres = re.split(r'[,;•\n]', cleaned_section)
        for genre in potential_genres:
            clean_genre = genre.strip().lower()
            clean_genre = re.sub(r'\([^)]*\)', '', clean_genre)  # Remove parentheses
            clean_genre = re.sub(r'\s+', ' ', clean_genre).strip()  # Normalize spaces
            
            if clean_genre and len(clean_genre) > 2 and clean_genre not in ['class=nowraplinks']:
                genres.append(clean_genre)
    
    # Clean and normalize genres
    cleaned_genres = []
    for genre in genres:
        clean_genre = genre.strip().lower()
        
        # Remove common Wikipedia artifacts
        clean_genre = re.sub(r'music$', '', clean_genre).strip()
        clean_genre = re.sub(r'^the\s+', '', clean_genre)
        
        # Skip obvious non-genres
        skip_terms = ['class=nowraplinks', 'flatlist', 'hlist', 'nowrap', 'refn', 'cite', 'ref']
        if any(term in clean_genre for term in skip_terms):
            continue
            
        if clean_genre and len(clean_genre) > 1:
            cleaned_genres.append(clean_genre)
    
    # Return unique genres, limited to reasonable number
    return sorted(set(cleaned_genres))[:5]

# --- PROCESS ALL ARTISTS ---
wiki_files = [f for f in os.listdir(WIKI_DIR) if f.endswith(".txt")]
all_artist_genres = {}

for i, artist in enumerate(G.nodes(), 1):
    match = find_wiki_file(artist, wiki_files)
    if not match:
        continue
    with open(os.path.join(WIKI_DIR, match), encoding="utf-8") as f:
        text = f.read()
    genres = extract_genres_from_text(text)
    if genres:
        all_artist_genres[artist] = genres
    if i % 50 == 0:
        print(f"Processed {i}/{G.number_of_nodes()} artists...")

print(f"\nGenres found for {len(all_artist_genres)}/{G.number_of_nodes()} artists.")

# --- CLEANING STEP ---
def clean_genre(g):
    g = g.strip().lower()
    
    # Skip obvious non-genres (publications, websites, etc.)
    non_genres = {
        'about.com', 'all media network', 'daily aztec', 'edinburgh university press', 
        'edmonton sun', 'fireside books', 'forbes', 'gale (publisher)', 'global news',
        'google books', 'jet (magazine)', 'mtv', 'new york times company', 'quietus',
        'rip it up (magazine)', 'rolling stone', 'routledge', 'smooth radio (2014)',
        'washington post', 'all'
    }
    
    if g in non_genres or 'publisher' in g or 'magazine' in g or 'press' in g or 'news' in g:
        return None
    
    # Skip citation artifacts
    if re.match(r"^\[\d+\]$", g) or "citation needed" in g:
        return None
    
    # Clean up formatting artifacts
    g = re.sub(r'\|.*$', '', g)  # Remove pipe and everything after
    g = re.sub(r'&nbsp;', ' ', g)  # Replace HTML entities
    g = re.sub(r'\([^)]*\)', '', g)  # Remove parentheses content
    g = g.strip()
    
    # Replace common variants with standard terms
    replace_map = {
        "hip-hop": "hip hop",
        "r&b": "rhythm and blues",
        "rhythm & blues": "rhythm and blues",
        "new orleans r&b": "rhythm and blues",
        "folk-rock": "folk rock",
        "pop-punk": "pop punk",
        "dance-rock": "dance rock",
        "nu metal": "nu-metal",
        "rock 'n' roll": "rock and roll",
        "rock n roll": "rock and roll",
        "psychedelia": "psychedelic rock",
        "psychedelic": "psychedelic rock",
        "electronica": "electronic",
        "fusion": "jazz fusion",
        "heavy metal music": "heavy metal",
        "nu metal early": "nu-metal",
        "contemporary folk music": "folk",
        "pop music": "pop",
        "rock music": "rock",
        "new wave music": "new wave",
        "hip hop music": "hip hop",
        "beat music": "beat"
    }
    
    g = replace_map.get(g, g)
    g = g.replace("–", "-").replace("—", "-")
    g = re.sub(r"\s+", " ", g).strip()
    
    # Final validation - must be reasonable length and not empty
    return g if len(g) > 2 and not g.isdigit() else None

cleaned_artist_genres = {}
for artist, genres in all_artist_genres.items():
    cleaned = [clean_genre(g) for g in genres if g]
    cleaned = sorted(set(filter(None, cleaned)))
    if cleaned:
        cleaned_artist_genres[artist] = cleaned

# --- VALIDATION ---
print(f"\nValidated: {len(cleaned_artist_genres)} artists have cleaned genres.")
print("Sample:")
for k, v in list(cleaned_artist_genres.items())[:5]:
    print(f"{k}: {v}")

all_cleaned_genres = sorted({g for lst in cleaned_artist_genres.values() for g in lst})
print("\n=== ALL UNIQUE CLEANED GENRES ===")
for g in all_cleaned_genres:
    print(g)

print(f"\nTotal unique cleaned genres: {len(all_cleaned_genres)}")

# --- SAVE GRAPH ---
nx.set_node_attributes(G, {n: ", ".join(genres) for n, genres in cleaned_artist_genres.items()}, "genres")
nx.write_graphml(G, "rock_bands_with_cleaned_genres.graphml")
print("\nGraph saved successfully.")
