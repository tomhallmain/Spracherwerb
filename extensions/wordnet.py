"""Module for interacting with WordNet's lexical database."""

from typing import List, Dict, Optional, Any, Set
from dataclasses import dataclass
from pathlib import Path
import json
import time
from nltk.corpus import wordnet as wn
from nltk.corpus.reader.wordnet import Synset

from utils.logging_setup import get_logger

logger = get_logger(__name__)


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

    def get_cleaned_synonyms(self) -> List[str]:
        """Return synonyms with synset format stripped."""
        return [s.split('.')[0] for s in self.synonyms]

    def get_cleaned_antonyms(self) -> List[str]:
        """Return antonyms with synset format stripped."""
        return [a.split('.')[0] for a in self.antonyms]

    def get_cleaned_hypernyms(self) -> List[str]:
        """Return hypernyms with synset format stripped."""
        return [h.split('.')[0] for h in self.hypernyms]

    def get_cleaned_hyponyms(self) -> List[str]:
        """Return hyponyms with synset format stripped."""
        return [h.split('.')[0] for h in self.hyponyms]

    def get_cleaned_meronyms(self) -> List[str]:
        """Return meronyms with synset format stripped."""
        return [m.split('.')[0] for m in self.meronyms]

    def get_cleaned_holonyms(self) -> List[str]:
        """Return holonyms with synset format stripped."""
        return [h.split('.')[0] for h in self.holonyms]

    def get_cleaned_relations(self) -> Dict[str, List[str]]:
        """Return all relations with synset format stripped."""
        return {
            'synonyms': self.get_cleaned_synonyms(),
            'antonyms': self.get_cleaned_antonyms(),
            'hypernyms': self.get_cleaned_hypernyms(),
            'hyponyms': self.get_cleaned_hyponyms(),
            'meronyms': self.get_cleaned_meronyms(),
            'holonyms': self.get_cleaned_holonyms()
        }


class WordNet:
    """Handles interactions with WordNet's lexical database."""
    
    CACHE_DIR = Path("cache/wordnet")
    CACHE_FILE = CACHE_DIR / "words.json"
    CACHE_DURATION = 86400  # 24 hours in seconds
    
    def __init__(self):
        """Initialize the WordNet client with caching."""
        self.words: Dict[str, WordInfo] = {}
        self._load_cache()
    
    def _load_cache(self) -> Dict[str, Any]:
        """Load cached word data from disk."""
        try:
            if self.CACHE_FILE.exists():
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.words = {
                        word: WordInfo(**word_data)
                        for word, word_data in data.items()
                    }
                    return data
            return {}
        except Exception as e:
            logger.error(f"Error loading WordNet cache: {e}")
            self.words = {}
            return {}
    
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
            logger.error(f"Error saving WordNet cache: {e}")
    
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
            logger.error(f"Error getting WordNet info for {word}: {e}")
            return None
    
    def get_synonyms(self, word: str, cleaned: bool = True) -> List[str]:
        """Get synonyms for a word.
        
        Args:
            word: The word to get synonyms for
            cleaned: If True, returns cleaned versions (without synset format)
                   If False, returns raw versions (with synset format)
        """
        word_info = self.get_word_info(word)
        if not word_info:
            return []
        return word_info.get_cleaned_synonyms() if cleaned else word_info.synonyms
    
    def get_antonyms(self, word: str, cleaned: bool = True) -> List[str]:
        """Get antonyms for a word.
        
        Args:
            word: The word to get antonyms for
            cleaned: If True, returns cleaned versions (without synset format)
                   If False, returns raw versions (with synset format)
        """
        word_info = self.get_word_info(word)
        if not word_info:
            return []
        return word_info.get_cleaned_antonyms() if cleaned else word_info.antonyms
    
    def get_hypernyms(self, word: str, cleaned: bool = True) -> List[str]:
        """Get hypernyms (more general terms) for a word.
        
        Args:
            word: The word to get hypernyms for
            cleaned: If True, returns cleaned versions (without synset format)
                   If False, returns raw versions (with synset format)
        """
        word_info = self.get_word_info(word)
        if not word_info:
            return []
        return word_info.get_cleaned_hypernyms() if cleaned else word_info.hypernyms
    
    def get_hyponyms(self, word: str, cleaned: bool = True) -> List[str]:
        """Get hyponyms (more specific terms) for a word.
        
        Args:
            word: The word to get hyponyms for
            cleaned: If True, returns cleaned versions (without synset format)
                   If False, returns raw versions (with synset format)
        """
        word_info = self.get_word_info(word)
        if not word_info:
            return []
        return word_info.get_cleaned_hyponyms() if cleaned else word_info.hyponyms
    
    def get_meronyms(self, word: str, cleaned: bool = True) -> List[str]:
        """Get meronyms (parts) for a word.
        
        Args:
            word: The word to get meronyms for
            cleaned: If True, returns cleaned versions (without synset format)
                   If False, returns raw versions (with synset format)
        """
        word_info = self.get_word_info(word)
        if not word_info:
            return []
        return word_info.get_cleaned_meronyms() if cleaned else word_info.meronyms
    
    def get_holonyms(self, word: str, cleaned: bool = True) -> List[str]:
        """Get holonyms (wholes) for a word.
        
        Args:
            word: The word to get holonyms for
            cleaned: If True, returns cleaned versions (without synset format)
                   If False, returns raw versions (with synset format)
        """
        word_info = self.get_word_info(word)
        if not word_info:
            return []
        return word_info.get_cleaned_holonyms() if cleaned else word_info.holonyms
    
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
            logger.error(f"Error calculating word similarity: {e}")
            return 0.0
    
    def get_related_words(self, word: str, depth: int = 2, cleaned: bool = True) -> Set[str]:
        """Get related words up to a certain depth.
        
        Args:
            word: The word to get related words for
            depth: How many levels of relations to explore (default: 2)
            cleaned: If True, returns cleaned versions (without synset format)
                   If False, returns raw versions (with synset format)
        """
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
            
            # Clean the results if requested
            if cleaned:
                related = {word.split('.')[0] for word in related}
            
            return related
            
        except Exception as e:
            logger.error(f"Error getting related words: {e}")
            return set() 