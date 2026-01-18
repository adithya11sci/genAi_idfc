import time
import logging
from typing import List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RoundRobinKeyManager:
    """Smart API key rotation with cooldown tracking"""
    
    def __init__(self, keys: List[str]):
        self.keys = keys
        self.current_index = 0
        self.key_cooldowns = {}  # key -> timestamp when it can be used again
        self.cooldown_duration = 60  # seconds to wait after rate limit
    
    def get_key(self) -> str:
        """Get next available API key using round-robin"""
        current_time = time.time()
        
        # Try all keys in round-robin fashion
        for _ in range(len(self.keys)):
            key = self.keys[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.keys)
            
            # Check if key is on cooldown
            if key in self.key_cooldowns:
                if current_time < self.key_cooldowns[key]:
                    continue  # Skip this key, it's on cooldown
                else:
                    del self.key_cooldowns[key]  # Cooldown expired
            
            return key
        
        # All keys on cooldown - wait for shortest cooldown
        min_wait = min(self.key_cooldowns.values()) - current_time
        if min_wait > 0:
            logger.warning(f"All API keys on cooldown. Waiting {min_wait:.1f}s...")
            time.sleep(min_wait + 1)
        
        # Reset and return first key
        self.key_cooldowns.clear()
        return self.keys[0]
    
    def mark_rate_limited(self, key: str):
        """Mark a key as rate limited"""
        self.key_cooldowns[key] = time.time() + self.cooldown_duration
        logger.warning(f"Key rate limited. {len(self.key_cooldowns)}/{len(self.keys)} keys on cooldown")
