"""Module for interacting with WordNet's lexical database."""

from typing import List, Dict, Optional, Any, Set
from dataclasses import dataclass
from pathlib import Path
import json
import time
from nltk.corpus import wordnet as wn
from nltk.corpus.reader.wordnet import Synset

from utils.utils import Utils


@dataclass
class WordInfo:
    """Represents word information from WordNet."""
    word: str
    part_of_speech: str
    definitions: List[str]
    examples: List[str]
    synonyms: List[str]
    antonyms: List[str]
    hypernyms: List[str]
    hyponyms: List[str]
    meronyms: List[str]
    holonyms: List[str]
    last_accessed: Optional[float] = None


class WordNet:
    """Handles interactions with WordNet's lexical database."""
    
    CACHE_DIR = Path("cache/wordnet")
    CACHE_FILE = CACHE_DIR / "words.json"
    CACHE_DURATION = 86400  # 24 hours in seconds
    
    def __init__(self):
        """Initialize the WordNet client with caching."""
        self.words: Dict[str, WordInfo] = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load cached word data from disk."""
        try:
            if self.CACHE_FILE.exists():
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.words = {
                        word: WordInfo(**word_data)
                        for word, word_data in data.items()
                    }
        except Exception as e:
            Utils.log_red(f"Error loading WordNet cache: {e}")
            self.words = {}
    
    def _save_cache(self):
        """Save word data to cache file."""
        try:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(
                    {word: word_info.__dict__ 
                     for word, word_info in self.words.items()},
                    f,
                    ensure_ascii=False,
                    indent=2
                )
        except Exception as e:
            Utils.log_red(f"Error saving WordNet cache: {e}")
    
    def _is_cache_valid(self, word_info: WordInfo) -> bool:
        """Check if cached word data is still valid."""
        if not word_info.last_accessed:
            return False
        return (time.time() - word_info.last_accessed) < self.CACHE_DURATION
    
    def get_word_info(self, word: str) -> Optional[WordInfo]:
        """Get comprehensive information about a word."""
        # Check cache first
        if word in self.words and self._is_cache_valid(self.words[word]):
            return self.words[word]
        
        try:
            synsets = wn.synsets(word)
            if not synsets:
                return None
            
            # Collect all information
            definitions = []
            examples = []
            synonyms = set()
            antonyms = set()
            hypernyms = set()
            hyponyms = set()
            meronyms = set()
            holonyms = set()
            
            for synset in synsets:
                definitions.extend(synset.definition().split('; '))
                examples.extend(synset.examples())
                synonyms.update(synset.lemma_names())
                
                # Get antonyms
                for lemma in synset.lemmas():
                    antonyms.update(ant.name() for ant in lemma.antonyms())
                
                # Get hypernyms and hyponyms
                hypernyms.update(s.name() for s in synset.hypernyms())
                hyponyms.update(s.name() for s in synset.hyponyms())
                
                # Get meronyms and holonyms
                meronyms.update(s.name() for s in synset.part_meronyms())
                meronyms.update(s.name() for s in synset.substance_meronyms())
                meronyms.update(s.name() for s in synset.member_meronyms())
                
                holonyms.update(s.name() for s in synset.part_holonyms())
                holonyms.update(s.name() for s in synset.substance_holonyms())
                holonyms.update(s.name() for s in synset.member_holonyms())
            
            # Create WordInfo object
            word_info = WordInfo(
                word=word,
                part_of_speech=synsets[0].pos(),
                definitions=definitions,
                examples=examples,
                synonyms=list(synonyms),
                antonyms=list(antonyms),
                hypernyms=list(hypernyms),
                hyponyms=list(hyponyms),
                meronyms=list(meronyms),
                holonyms=list(holonyms),
                last_accessed=time.time()
            )
            
            self.words[word] = word_info
            self._save_cache()
            
            return word_info
            
        except Exception as e:
            Utils.log_red(f"Error getting WordNet info for {word}: {e}")
            return None
    
    def get_synonyms(self, word: str) -> List[str]:
        """Get synonyms for a word."""
        word_info = self.get_word_info(word)
        return word_info.synonyms if word_info else []
    
    def get_antonyms(self, word: str) -> List[str]:
        """Get antonyms for a word."""
        word_info = self.get_word_info(word)
        return word_info.antonyms if word_info else []
    
    def get_hypernyms(self, word: str) -> List[str]:
        """Get hypernyms (more general terms) for a word."""
        word_info = self.get_word_info(word)
        return word_info.hypernyms if word_info else []
    
    def get_hyponyms(self, word: str) -> List[str]:
        """Get hyponyms (more specific terms) for a word."""
        word_info = self.get_word_info(word)
        return word_info.hyponyms if word_info else []
    
    def get_meronyms(self, word: str) -> List[str]:
        """Get meronyms (parts) for a word."""
        word_info = self.get_word_info(word)
        return word_info.meronyms if word_info else []
    
    def get_holonyms(self, word: str) -> List[str]:
        """Get holonyms (wholes) for a word."""
        word_info = self.get_word_info(word)
        return word_info.holonyms if word_info else []
    
    def get_word_similarity(self, word1: str, word2: str) -> float:
        """Get similarity score between two words."""
        try:
            synsets1 = wn.synsets(word1)
            synsets2 = wn.synsets(word2)
            
            if not synsets1 or not synsets2:
                return 0.0
            
            # Get maximum similarity between any pair of synsets
            max_similarity = 0.0
            for syn1 in synsets1:
                for syn2 in synsets2:
                    try:
                        similarity = syn1.path_similarity(syn2)
                        if similarity and similarity > max_similarity:
                            max_similarity = similarity
                    except:
                        continue
            
            return max_similarity
            
        except Exception as e:
            Utils.log_red(f"Error calculating word similarity: {e}")
            return 0.0
    
    def get_related_words(self, word: str, depth: int = 2) -> Set[str]:
        """Get related words up to a certain depth."""
        try:
            related = set()
            synsets = wn.synsets(word)
            
            for synset in synsets:
                # Get immediate relations
                related.update(synset.lemma_names())
                related.update(s.name() for s in synset.hypernyms())
                related.update(s.name() for s in synset.hyponyms())
                
                # Get deeper relations if depth > 1
                if depth > 1:
                    for hypernym in synset.hypernyms():
                        related.update(s.name() for s in hypernym.hyponyms())
                    for hyponym in synset.hyponyms():
                        related.update(s.name() for s in hyponym.hypernyms())
            
            # Remove the original word
            related.discard(word)
            return related
            
        except Exception as e:
            Utils.log_red(f"Error getting related words: {e}")
            return set() 