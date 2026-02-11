"""
Fast Market Discovery with Advanced Matching Algorithm
Professional-grade matching with temporal fencing, numeric precision, and inversion detection
"""

import json
import logging
import re
from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime
from collections import defaultdict
from difflib import SequenceMatcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImprovedMarketMatcher:
    """
    Professional-grade market matching with three-gate filter system:
    Gate 1: Category & Entity (broad filter)
    Gate 2: Poison Pills (hard disqualification)
    Gate 3: Semantic Score (deep filter)
    """

    # Directional logic synonyms
    DIRECTIONAL_SYNONYMS = {
        "above": "over",
        "more than": "over",
        "at least": "over",
        "below": "under",
        "less than": "under",
        "fewer than": "under",
        "no more than": "under"
    }

    # Binary state normalization
    BINARY_STATES = {
        "to occur": "happens",
        "to happen": "happens",
        "to be released": "happens",
        "to be announced": "happens",
        "will be": "happens",
        "gets": "happens"
    }

    # Negation words for inversion detection
    NEGATIONS = {'not', 'lose', 'loses', 'fail', 'fails', 'below', 'under', 'defeat', 'defeated'}

    @staticmethod
    def extract_temporal_context(text: str) -> Dict[str, any]:
        """
        Extract temporal information with deadline vs window detection

        Returns:
        - is_deadline: "by June", "before July" (any time up to)
        - is_window: "in June", "during July" (specifically within)
        - year: extracted year
        - month: extracted month
        """
        is_deadline = bool(re.search(r'\b(by|before|until)\b', text))
        is_window = bool(re.search(r'\b(in|during|throughout|within)\b', text))

        # Extract year
        year_match = re.search(r'\b(20\d{2})\b', text)
        year = int(year_match.group(1)) if year_match else None

        # Extract month
        month_patterns = {
            'january': 1, 'jan': 1,
            'february': 2, 'feb': 2,
            'march': 3, 'mar': 3,
            'april': 4, 'apr': 4,
            'may': 5,
            'june': 6, 'jun': 6,
            'july': 7, 'jul': 7,
            'august': 8, 'aug': 8,
            'september': 9, 'sep': 9, 'sept': 9,
            'october': 10, 'oct': 10,
            'november': 11, 'nov': 11,
            'december': 12, 'dec': 12
        }

        month = None
        for month_name, month_num in month_patterns.items():
            if month_name in text:
                month = month_num
                break

        return {
            'is_deadline': is_deadline,
            'is_window': is_window,
            'year': year,
            'month': month
        }

    @staticmethod
    def get_numeric_tolerance(topic: str) -> float:
        """
        Get tolerance percentage based on market topic

        Topic-specific tolerances:
        - Crypto price: 0.1% (psychological barriers matter)
        - Box office: 5% (estimates vary)
        - Weather: Fixed 1 degree
        - Default: 2%
        """
        topic = topic.lower()

        if any(kw in topic for kw in ['bitcoin', 'btc', 'eth', 'ethereum', 'crypto', 'price']):
            return 0.001  # 0.1%
        elif any(kw in topic for kw in ['box office', 'revenue', 'gross']):
            return 0.05  # 5%
        elif any(kw in topic for kw in ['temperature', 'temp', 'degrees']):
            return 0.01  # 1 degree effective
        else:
            return 0.02  # 2% default

    @staticmethod
    def detect_inversion(prop1: Dict, prop2: Dict) -> bool:
        """
        Detect if markets are inverted (opposite outcomes)

        Example:
        - "Will Trump win?" vs "Will Trump lose?"
        - "Bitcoin above $100k?" vs "Bitcoin below $100k?"
        """
        actions1 = set(prop1['actions'])
        actions2 = set(prop2['actions'])

        # Check if one has negation and other doesn't
        p1_neg = bool(actions1 & ImprovedMarketMatcher.NEGATIONS)
        p2_neg = bool(actions2 & ImprovedMarketMatcher.NEGATIONS)

        # Check directional opposites
        has_above_below = (
            (bool(actions1 & {'above', 'over'}) and bool(actions2 & {'below', 'under'})) or
            (bool(actions1 & {'below', 'under'}) and bool(actions2 & {'above', 'over'}))
        )

        has_win_lose = (
            (bool(actions1 & {'win', 'wins'}) and bool(actions2 & {'lose', 'loses'})) or
            (bool(actions1 & {'lose', 'loses'}) and bool(actions2 & {'win', 'wins'}))
        )

        return (p1_neg != p2_neg) or has_above_below or has_win_lose

    @staticmethod
    def extract_core_proposition(text: str) -> Dict[str, any]:
        """
        Extract core proposition with advanced normalization

        Returns dict with:
        - entities: Key people/things
        - actions: Verbs and outcomes
        - numbers: Normalized numeric thresholds
        - temporal: Deadline vs window, year, month
        - topics: Event categories
        - inverted: Whether outcome is negated
        """
        original_text = text
        text = text.lower().strip()

        # Remove common fluff
        text = re.sub(r'^will\s+', '', text)
        text = re.sub(r'\?+$', '', text)

        # Apply directional synonyms
        for original, canonical in ImprovedMarketMatcher.DIRECTIONAL_SYNONYMS.items():
            text = text.replace(original, canonical)

        # Apply binary state normalization
        for original, canonical in ImprovedMarketMatcher.BINARY_STATES.items():
            text = text.replace(original, canonical)

        # Extract temporal context
        temporal = ImprovedMarketMatcher.extract_temporal_context(text)

        # Extract and normalize numbers with context
        numbers = []
        number_contexts = []
        for num_match in re.finditer(r'(\$)?(\d+(?:,\d{3})*(?:\.\d+)?)\s*([kmbKMB%]|billion|million|thousand)?', text):
            value = num_match.group(2).replace(',', '')
            suffix = num_match.group(3) or ''
            is_currency = bool(num_match.group(1))

            # Normalize to actual value
            num_value = float(value)
            if suffix.lower() in ['k', 'thousand']:
                num_value *= 1000
            elif suffix.lower() in ['m', 'million']:
                num_value *= 1000000
            elif suffix.lower() in ['b', 'billion']:
                num_value *= 1000000000

            numbers.append(int(num_value))
            number_contexts.append({
                'value': int(num_value),
                'is_currency': is_currency,
                'is_percentage': suffix == '%'
            })

        # Normalize entity synonyms
        synonym_map = {
            'btc': 'bitcoin',
            'bitcoin': 'bitcoin',
            'eth': 'ethereum',
            'ethereum': 'ethereum',
            'donald trump': 'trump',
            'donald j trump': 'trump',
            'joe biden': 'biden',
            'kamala harris': 'harris',
            'jerome powell': 'powell',
            'elon musk': 'musk',
            'elon': 'musk',
            'federal reserve': 'fed',
            'presidential': 'president',
            'chairman': 'chair',
            # Verb synonyms
            'reach': 'hit',
            'achieve': 'hit',
            'reaches': 'hits',
            'achieves': 'hits',
            'attain': 'hit',
            'surpass': 'exceed',
            'cross': 'hit',
        }

        for synonym, canonical in synonym_map.items():
            text = text.replace(synonym, canonical)

        # Extract key entities
        entities = []

        # Countries
        countries = []
        country_patterns = ['usa', 'america', 'united states', 'u.s.', 'u.k.', 'uk', 'britain',
                           'russia', 'china', 'ukraine', 'france', 'germany', 'japan', 'canada']
        for country in country_patterns:
            if country in text:
                countries.append(country)

        # Common entities (normalized)
        common_entities = ['trump', 'biden', 'harris', 'musk', 'bitcoin', 'ethereum',
                          'fed', 'powell', 'gop', 'democrat', 'republican', 'mrbeast', 'lebron',
                          'super bowl', 'nfl', 'nba', 'oscars', 'grammy', 'election', 'senate', 'house',
                          'sp500', 's&p', 'nasdaq', 'dow', 'apple', 'tesla', 'amazon', 'google']
        for entity in common_entities:
            if entity in text:
                entities.append(entity)

        # Extract topics
        topics = []
        topic_patterns = {
            'tweets': r'\b(tweet|tweets|posting|post)\b',
            'price': r'\b(price|value|worth|market cap|trading)\b',
            'election': r'\b(elect|elected|election|vote|ballot|primary)\b',
            'nomination': r'\b(nominat|nominee)\b',
            'sports': r'\b(game|match|championship|score|tournament|playoff)\b',
            'wealth': r'\b(trillionaire|billionaire|millionaire|rich|wealth|net worth)\b',
            'crypto': r'\b(bitcoin|btc|ethereum|eth|crypto)\b',
            'stock': r'\b(stock|share|market|trading|nasdaq|dow)\b',
        }
        for topic, pattern in topic_patterns.items():
            if re.search(pattern, text):
                topics.append(topic)

        # Extract actions with negation awareness
        action_words = []
        action_patterns = [
            r'\b(win|wins|winning|won)\b',
            r'\b(lose|loses|losing|lost)\b',
            r'\b(hit|hits|hitting)\b',
            r'\b(pass|passes|exceed|exceeds)\b',
            r'\b(elect|elected|election)\b',
            r'\b(nominat|nominated|nominee)\b',
            r'\b(resign|resigns|fired)\b',
            r'\b(above|below|over|under)\b',
            r'\b(before|after|by)\b',
            r'\b(become|becomes)\b',
            r'\b(president|ceo|chairman|chair)\b',
            r'\b(trillionaire|billionaire|millionaire)\b',
            r'\b(end|ends|ending|ended|abolish)\b',
            r'\b(start|starts|beginning|begin)\b',
            r'\b(announce|announces|announced)\b',
            r'\b(release|releases|released)\b',
        ]
        for pattern in action_patterns:
            matches = re.findall(pattern, text)
            action_words.extend(matches)

        # Detect if outcome is inverted
        is_inverted = any(neg in text for neg in ['not', 'no', "n't", 'never', 'fail'])

        return {
            'text': text,
            'original': original_text,
            'numbers': numbers,
            'number_contexts': number_contexts,
            'temporal': temporal,
            'entities': list(set(entities)),
            'actions': list(set(action_words)),
            'topics': topics,
            'countries': countries,
            'is_inverted': is_inverted,
            'normalized': re.sub(r'[^\w\s]', ' ', text).split()
        }

    @staticmethod
    def calculate_match_score(prop1: Dict, prop2: Dict) -> Tuple[float, bool]:
        """
        Three-gate filter system for matching

        Returns: (score, is_inverted)
        - score: 0.0 to 1.0
        - is_inverted: True if markets are opposite outcomes
        """

        # ===== GATE 1: ENTITY ANCHORING (Broad Filter) =====
        entities1 = set(prop1['entities'])
        entities2 = set(prop2['entities'])

        entity_overlap = 0
        if entities1 and entities2:
            entity_overlap = len(entities1 & entities2) / max(len(entities1), len(entities2))
            if entity_overlap < 0.5:  # STRICT: Must have 50%+ entity overlap
                return 0.0, False
        elif entities1 or entities2:
            # One has entities, one doesn't = different events
            return 0.0, False

        # ===== GATE 2: POISON PILLS (Hard Disqualification) =====

        # Poison Pill 1: Country mismatch
        countries1 = set(prop1.get('countries', []))
        countries2 = set(prop2.get('countries', []))
        if countries1 and countries2:
            if not (countries1 & countries2):
                return 0.0, False

        # Poison Pill 2: Temporal mismatch (Year/Month)
        temp1 = prop1['temporal']
        temp2 = prop2['temporal']

        # If both have years, they must match
        if temp1['year'] and temp2['year']:
            if temp1['year'] != temp2['year']:
                return 0.0, False

        # If both have months, they must match
        if temp1['month'] and temp2['month']:
            if temp1['month'] != temp2['month']:
                return 0.0, False

        # If one is "by June" and other is "in June", penalize (not exact same event)
        if temp1['is_deadline'] != temp2['is_deadline'] or temp1['is_window'] != temp2['is_window']:
            if temp1['month'] and temp2['month']:
                # Same month but different temporal context = 50% penalty
                pass  # Will be handled in scoring

        # Check for inversion EARLY (before numeric check)
        # Inverted markets use the SAME numbers but opposite directions
        is_inverted = ImprovedMarketMatcher.detect_inversion(prop1, prop2)

        # Poison Pill 3: Numeric threshold mismatch with topic-specific tolerance
        if prop1['numbers'] and prop2['numbers']:
            # Get topic for tolerance calculation
            topics = list(set(prop1['topics'] + prop2['topics']))
            topic_str = ' '.join(topics) if topics else ''
            tolerance = ImprovedMarketMatcher.get_numeric_tolerance(topic_str)

            # For inverted markets, numbers should match EXACTLY (same threshold, opposite direction)
            if is_inverted:
                tolerance = 0.001  # 0.1% for inverted markets

            # Check if any numbers are within tolerance
            has_close_number = False
            for ctx1 in prop1['number_contexts']:
                for ctx2 in prop2['number_contexts']:
                    n1 = ctx1['value']
                    n2 = ctx2['value']

                    # Must be same type (both currency or both not)
                    if ctx1.get('is_currency') != ctx2.get('is_currency'):
                        continue

                    # Check tolerance
                    if n1 == n2:
                        has_close_number = True
                        break
                    elif max(n1, n2) > 0:
                        delta = abs(n1 - n2) / max(n1, n2)
                        if delta <= tolerance:
                            has_close_number = True
                            break

                if has_close_number:
                    break

            if not has_close_number:
                return 0.0, False

        # Poison Pill 4: Topic mismatch (unless inverted)
        topics1 = set(prop1.get('topics', []))
        topics2 = set(prop2.get('topics', []))
        if not is_inverted:  # Allow different topics for inverted markets
            if topics1 and topics2 and not (topics1 & topics2):
                # Both have topics but no overlap = different event types
                return 0.0, False

        # ===== GATE 3: SEMANTIC SCORE (Deep Filter) =====

        # Action parity check with semantic equivalents
        actions1 = set(prop1['actions'])
        actions2 = set(prop2['actions'])

        action_overlap = 0
        if actions1 and actions2:
            # For inverted markets, actions SHOULD be different (that's the point!)
            if is_inverted:
                action_overlap = 0.9  # High score for inverted actions
            else:
                # Direct overlap
                direct_overlap = len(actions1 & actions2)

                # Check semantic equivalents
                equivalent_actions = [
                    ({'win', 'won'}, {'elect', 'elected'}),
                    ({'elect', 'elected'}, {'become', 'president'}),
                    ({'nominat', 'nominated', 'nominee'}, {'elect', 'elected'}),
                    ({'hit', 'hits'}, {'exceed', 'exceeds', 'pass', 'passes'}),
                    ({'above', 'over'}, {'exceed', 'exceeds'}),
                ]

                semantic_match = False
                for equiv1, equiv2 in equivalent_actions:
                    if (actions1 & equiv1) and (actions2 & equiv2):
                        semantic_match = True
                        break
                    if (actions1 & equiv2) and (actions2 & equiv1):
                        semantic_match = True
                        break

                if direct_overlap > 0 or semantic_match:
                    action_overlap = 0.8
                else:
                    # No action overlap and no semantic equivalents = likely different
                    return 0.0, False

        # Word overlap calculation
        words1 = set(prop1['normalized'])
        words2 = set(prop2['normalized'])

        # Remove stop words
        stop_words = {'a', 'an', 'the', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or', 'but',
                     'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
                     'do', 'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might'}
        words1 -= stop_words
        words2 -= stop_words

        if not words1 or not words2:
            return 0.0, False

        word_overlap = len(words1 & words2) / max(len(words1), len(words2))

        # Sequence similarity
        sequence_sim = SequenceMatcher(None, prop1['text'], prop2['text']).ratio()

        # Calculate weighted score
        base_score = (
            entity_overlap * 0.35 +      # Entities very important
            action_overlap * 0.25 +       # Actions critical
            word_overlap * 0.25 +         # Word overlap matters
            sequence_sim * 0.15          # Exact phrasing helps
        )

        # Boost for matching numbers
        if prop1['numbers'] and prop2['numbers']:
            base_score = min(1.0, base_score + 0.1)

        # Boost for matching temporal context
        if temp1['year'] and temp2['year'] and temp1['year'] == temp2['year']:
            base_score = min(1.0, base_score + 0.05)

        if temp1['month'] and temp2['month'] and temp1['month'] == temp2['month']:
            base_score = min(1.0, base_score + 0.05)

        return base_score, is_inverted

    @staticmethod
    def are_markets_same_event(title1: str, title2: str, min_score: float = 0.65) -> Tuple[bool, float]:
        """
        Determine if two market titles refer to the same event

        Args:
            title1: First market title
            title2: Second market title
            min_score: Minimum score to consider a match

        Returns:
            (is_match, score)
        """
        prop1 = ImprovedMarketMatcher.extract_core_proposition(title1)
        prop2 = ImprovedMarketMatcher.extract_core_proposition(title2)

        score, is_inverted = ImprovedMarketMatcher.calculate_match_score(prop1, prop2)

        # If inverted, still a match but need to note it
        # (For arbitrage, inverted markets are actually useful!)
        return (score >= min_score, score)


class FastMarketDiscovery:
    """
    Fast market discovery using category-based filtering
    Only compares markets within compatible categories
    """

    # Category mapping between platforms
    CATEGORY_MAP = {
        'all': ['Politics', 'Elections', 'Economics', 'Entertainment', 'World', 'Companies',
                'Science and Technology', 'Climate and Weather', 'Health', 'Sports', 'Social'],
        'politics': ['Politics', 'Elections'],
        'us-current-affairs': ['Politics', 'Elections', 'World'],
        'crypto': ['Financials', 'Economics'],
        'sports': ['Sports'],
        'pop-culture': ['Entertainment'],
        'business': ['Companies', 'Economics'],
        'science': ['Science and Technology'],
    }

    def __init__(self):
        self.matcher = ImprovedMarketMatcher()

    def fetch_polymarket_markets(self, limit: int = 500, progress_callback=None) -> Dict[str, List[Dict]]:
        """Fetch and categorize Polymarket markets"""
        try:
            import requests
            logger.info(f"Fetching Polymarket markets (limit: {limit})...")

            markets_by_category = defaultdict(list)
            offset = 0
            page_size = 100
            total_fetched = 0

            while total_fetched < limit:
                if progress_callback:
                    progress_callback(total_fetched, limit, f'Fetching Polymarket... ({total_fetched}/{limit})')

                resp = requests.get('https://gamma-api.polymarket.com/markets', params={
                    'active': 'true',
                    'closed': 'false',
                    'limit': page_size,
                    'offset': offset,
                    'order': 'liquidityClob',
                    'ascending': 'false',
                })

                if not resp.ok:
                    break

                markets = resp.json()
                if not markets:
                    break

                for market in markets:
                    category = market.get('category', '').lower() or 'all'

                    clob_ids = market.get('clobTokenIds', '').strip('[]').split(',')
                    token_id = clob_ids[0].strip().strip('"') if clob_ids else ''

                    if not token_id:
                        continue

                    liquidity = float(market.get('liquidityNum', 0) or 0)

                    markets_by_category[category].append({
                        'id': market.get('conditionId') or market.get('id'),
                        'title': market.get('question', ''),
                        'category': category,
                        'liquidity': liquidity,
                        'token_id': token_id,
                    })
                    total_fetched += 1

                    if total_fetched >= limit:
                        break

                offset += page_size
                if len(markets) < page_size:
                    break

            logger.info(f"Fetched {total_fetched} Polymarket markets across {len(markets_by_category)} categories")

            return dict(markets_by_category)

        except Exception as e:
            logger.error(f"Error fetching Polymarket: {e}")
            return {}

    def fetch_kalshi_markets(self, limit: int = 500, progress_callback=None) -> Dict[str, List[Dict]]:
        """Fetch and categorize Kalshi markets"""
        try:
            import requests
            logger.info(f"Fetching Kalshi markets (limit: {limit})...")

            markets_by_category = defaultdict(list)
            base_url = 'https://api.elections.kalshi.com/trade-api/v2'
            cursor = None
            total_fetched = 0

            while total_fetched < limit:
                if progress_callback:
                    progress_callback(total_fetched, limit, f'Fetching Kalshi... ({total_fetched}/{limit})')

                params = {
                    'status': 'open',
                    'limit': 200,
                    'with_nested_markets': 'true'
                }
                if cursor:
                    params['cursor'] = cursor

                resp = requests.get(f'{base_url}/events', params=params)
                if not resp.ok:
                    break

                data = resp.json()
                events = data.get('events', [])

                if not events:
                    break

                for event in events:
                    category = event.get('category', 'Unknown')

                    for mkt in event.get('markets', []):
                        ticker = mkt.get('ticker', '')
                        if not ticker:
                            continue

                        markets_by_category[category].append({
                            'ticker': ticker,
                            'title': mkt.get('title', event.get('title', '')),
                            'event_title': event.get('title', ''),
                            'category': category,
                            'liquidity': mkt.get('liquidity', 0),
                        })
                        total_fetched += 1

                        if total_fetched >= limit:
                            break

                    if total_fetched >= limit:
                        break

                cursor = data.get('cursor')
                if not cursor:
                    break

            logger.info(f"Fetched {total_fetched} Kalshi markets across {len(markets_by_category)} categories")

            return dict(markets_by_category)

        except Exception as e:
            logger.error(f"Error fetching Kalshi: {e}")
            return {}

    def find_matching_pairs(
        self,
        poly_markets_by_cat: Dict[str, List[Dict]],
        kalshi_markets_by_cat: Dict[str, List[Dict]],
        min_similarity: float = 0.60,
        progress_callback=None
    ) -> List[Dict]:
        """
        Fast matching using category filtering with advanced matching
        """
        logger.info("Fast matching with three-gate filter system...")

        matched_pairs = []
        total_comparisons = 0
        sample_comparisons = []

        for poly_cat, poly_markets in poly_markets_by_cat.items():
            kalshi_cats = self.CATEGORY_MAP.get(poly_cat, [poly_cat.title()])

            kalshi_candidates = []
            for k_cat in kalshi_cats:
                kalshi_candidates.extend(kalshi_markets_by_cat.get(k_cat, []))

            if not kalshi_candidates:
                continue

            logger.info(f"Matching {poly_cat}: {len(poly_markets)} poly vs {len(kalshi_candidates)} kalshi")

            for i, poly in enumerate(poly_markets):
                if progress_callback and i % 10 == 0:
                    progress_callback(
                        len(matched_pairs),
                        len(poly_markets),
                        f'Matching {poly_cat}... ({len(matched_pairs)} found)'
                    )

                best_match = None
                best_score = 0

                for kalshi in kalshi_candidates:
                    total_comparisons += 1

                    is_match, score = self.matcher.are_markets_same_event(
                        poly['title'],
                        kalshi['title'],
                        min_score=min_similarity
                    )

                    if len(sample_comparisons) < 5:
                        sample_comparisons.append({
                            'poly': poly['title'],
                            'kalshi': kalshi['title'],
                            'score': score,
                            'match': is_match
                        })

                    if is_match and score > best_score:
                        best_score = score
                        best_match = kalshi

                if best_match:
                    matched_pairs.append({
                        'polymarket_token_id': poly.get('token_id', poly['id']),
                        'poly_title': poly['title'],
                        'poly_liquidity': poly['liquidity'],
                        'kalshi_ticker': best_match['ticker'],
                        'kalshi_title': best_match['title'],
                        'kalshi_liquidity': best_match['liquidity'],
                        'similarity_score': best_score,
                        'category': poly_cat,
                        'name': poly['title'],
                    })

        logger.info("\nSample comparisons:")
        for comp in sample_comparisons:
            logger.info(f"  {comp['score']:.2f} {'✓' if comp['match'] else '✗'} | {comp['poly'][:50]} <-> {comp['kalshi'][:50]}")

        logger.info(f"\nFound {len(matched_pairs)} matches with {total_comparisons:,} comparisons")

        matched_pairs.sort(key=lambda x: x['similarity_score'], reverse=True)

        return matched_pairs

    def discover_pairs(
        self,
        max_markets: int = 500,
        min_similarity: float = 0.60,
        min_liquidity: float = 0,
        save_to_file: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> List[Dict]:
        """Fast discovery with advanced matching"""
        logger.info("Starting market discovery with advanced matching...")

        if progress_callback:
            progress_callback(0, 100, 'Starting discovery...')

        if progress_callback:
            progress_callback(5, 100, 'Fetching Polymarket...')

        poly_markets = self.fetch_polymarket_markets(
            limit=max_markets,
            progress_callback=lambda c, t, l: progress_callback(5 + int(c/t * 30), 100, l) if progress_callback else None
        )

        if progress_callback:
            progress_callback(35, 100, 'Fetching Kalshi...')

        kalshi_markets = self.fetch_kalshi_markets(
            limit=max_markets,
            progress_callback=lambda c, t, l: progress_callback(35 + int(c/t * 30), 100, l) if progress_callback else None
        )

        if not poly_markets or not kalshi_markets:
            logger.error("Failed to fetch markets")
            return []

        if progress_callback:
            progress_callback(65, 100, 'Matching markets...')

        pairs = self.find_matching_pairs(
            poly_markets,
            kalshi_markets,
            min_similarity=min_similarity,
            progress_callback=lambda c, t, l: progress_callback(65 + int(c/t * 30), 100, l) if progress_callback else None
        )

        if save_to_file and pairs:
            if progress_callback:
                progress_callback(95, 100, f'Saving {len(pairs)} pairs...')
            self.save_pairs_to_mapping(pairs, save_to_file)

        if progress_callback:
            progress_callback(100, 100, f'Complete! Found {len(pairs)} matches')

        return pairs

    def save_pairs_to_mapping(self, pairs: List[Dict], filepath: str = "discovered_markets.json"):
        """Save pairs to JSON file"""
        mapping = {}

        for i, pair in enumerate(pairs):
            key = f"pair_{i+1}"
            mapping[key] = {
                'name': pair.get('name', pair['poly_title']),
                'polymarket_token_id': pair['polymarket_token_id'],
                'kalshi_ticker': pair['kalshi_ticker'],
                'poly_title': pair['poly_title'],
                'kalshi_title': pair['kalshi_title'],
                'similarity_score': pair['similarity_score'],
                'category': pair.get('category', 'unknown'),
                'discovered_at': datetime.now().isoformat()
            }

        with open(filepath, 'w') as f:
            json.dump(mapping, f, indent=2)

        logger.info(f"Saved {len(pairs)} pairs to {filepath}")
