"""
Nextdoor Integration Module
Fetches local community posts from Nextdoor based on ZIP codes
Uses smart adaptive strategy similar to Twitter implementation
"""

import requests
from datetime import datetime, timedelta


class NextdoorFetcher:
    """
    Fetch local posts from Nextdoor for emergency/community awareness
    
    NOTE: Requires Nextdoor Public Agency API access
    - Apply at: https://nextdoor.com/agency/
    - Must be verified government agency or public safety organization
    - Alternative: Nextdoor for Business API (limited scope)
    """
    
    def __init__(self, api_key=None, zip_codes=None):
        """
        Initialize Nextdoor fetcher
        
        Args:
            api_key: Nextdoor API key (Public Agency API)
            zip_codes: List of ZIP codes to monitor (e.g., ['30301', '30302'])
        """
        self.api_key = api_key
        self.zip_codes = zip_codes or []
        self.base_url = "https://api.nextdoor.com/v2"  # Hypothetical endpoint
        
    def get_local_posts(self):
        """
        Fetch recent local posts using smart adaptive strategy
        
        Returns:
            List of posts sorted by urgency and recency
        """
        if not self.api_key:
            return {
                'error': 'Nextdoor API key not configured',
                'message': 'To enable Nextdoor integration, you need API access',
                'requirements': [
                    '1. Must be a verified government agency or public safety org',
                    '2. Apply for Public Agency API at https://nextdoor.com/agency/',
                    '3. Verification process takes 1-2 weeks',
                    '4. Free for qualified agencies'
                ],
                'alternatives': [
                    'Manual monitoring: Check Nextdoor app/website directly',
                    'Nextdoor Urgent Alerts: Enable email notifications',
                    'RSS alternatives: Some neighborhoods have community sites'
                ],
                'note': 'Nextdoor does not offer general public API access'
            }
        
        if not self.zip_codes:
            return {
                'error': 'No ZIP codes configured',
                'message': 'Add ZIP codes to monitor in the app settings'
            }
        
        posts = []
        errors = []
        
        # Smart adaptive strategies for different post types
        post_strategies = self._get_post_strategies()
        
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            # Fetch posts for each ZIP code
            for zip_code in self.zip_codes:
                try:
                    # Search posts by ZIP code with time filtering
                    for category, strategy in post_strategies.items():
                        posts_data = self._fetch_posts_by_category(
                            zip_code, 
                            category, 
                            strategy,
                            headers
                        )
                        if posts_data:
                            posts.extend(posts_data)
                    
                    # Small delay to avoid rate limits
                    import time
                    time.sleep(0.5)
                    
                except Exception as e:
                    errors.append(f"ZIP {zip_code}: {str(e)}")
                    continue
            
            # Sort posts by urgency and recency
            if posts:
                posts = self._sort_posts_by_urgency(posts)
                print(f"DEBUG: Fetched {len(posts)} posts from {len(self.zip_codes)} ZIP codes")
                return posts
            elif errors:
                return {
                    'error': 'Failed to retrieve posts',
                    'details': errors
                }
            else:
                return {
                    'message': 'No recent posts in monitored areas',
                    'zip_codes': self.zip_codes
                }
                
        except Exception as e:
            return {
                'error': f'Nextdoor API error: {str(e)}',
                'message': 'Check API key and connection'
            }
    
    def _fetch_posts_by_category(self, zip_code, category, strategy, headers):
        """Fetch posts for a specific category with adaptive window"""
        try:
            # Calculate time window
            start_time = (datetime.utcnow() - timedelta(hours=strategy['window_hours'])).isoformat() + 'Z'
            
            # Hypothetical API endpoint structure
            # (Actual Nextdoor API will differ - adapt based on documentation)
            params = {
                'zip_code': zip_code,
                'category': category,
                'start_time': start_time,
                'max_results': strategy['max_results'],
                'sort': 'recent'
            }
            
            # NOTE: This is a hypothetical endpoint structure
            # Real implementation depends on actual Nextdoor API documentation
            url = f"{self.base_url}/posts/search"
            
            response = requests.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                posts = []
                
                for post in data.get('posts', []):
                    # Extract and clean post data
                    post_text = post.get('text', '')
                    created_at = post.get('created_at', '')
                    age_hours = self._calculate_post_age(created_at)
                    
                    # Skip empty posts
                    if not post_text:
                        continue
                    
                    posts.append({
                        'zip_code': zip_code,
                        'category': category,
                        'text': post_text,
                        'author': post.get('author', {}).get('name', 'Unknown'),
                        'created_at': created_at,
                        'age_hours': age_hours,
                        'urgency': strategy['urgency'],
                        'post_type': self._classify_post(post_text, category),
                    })
                
                print(f"DEBUG: ZIP {zip_code}, {category} - {len(posts)} posts (last {strategy['window_hours']}h)")
                return posts
            else:
                print(f"WARNING: ZIP {zip_code}, {category} - HTTP {response.status_code}")
                return []
                
        except Exception as e:
            print(f"ERROR: ZIP {zip_code}, {category} - {str(e)}")
            return []
    
    def _get_post_strategies(self):
        """
        Define smart adaptive strategies for different Nextdoor post categories
        Similar to Twitter account strategies
        """
        return {
            # URGENT - Safety/emergency posts
            'urgent_alert': {
                'window_hours': 6,    # Only last 6 hours (time-sensitive)
                'max_results': 20,
                'urgency': 'critical'
            },
            'crime_safety': {
                'window_hours': 12,   # Recent crime/safety concerns
                'max_results': 15,
                'urgency': 'high'
            },
            
            # IMPORTANT - Community issues
            'lost_found': {
                'window_hours': 24,   # Lost pets, found items
                'max_results': 10,
                'urgency': 'high'
            },
            'general_crime': {
                'window_hours': 24,   # General safety discussions
                'max_results': 10,
                'urgency': 'medium'
            },
            
            # INFORMATIONAL - Community updates
            'emergency_planning': {
                'window_hours': 48,   # Preparedness info
                'max_results': 8,
                'urgency': 'medium'
            },
            'local_news': {
                'window_hours': 24,   # Community news
                'max_results': 5,
                'urgency': 'low'
            },
            'recommendations': {
                'window_hours': 48,   # General recommendations
                'max_results': 5,
                'urgency': 'low'
            }
        }
    
    def _classify_post(self, text, category):
        """
        Classify post type based on content for better prioritization
        Uses keyword matching to identify urgent posts
        """
        text_lower = text.lower()
        
        # CRITICAL keywords - immediate threats
        critical_keywords = [
            'fire', 'shooting', 'robbery', 'break-in', 'assault',
            'suspicious person', 'active shooter', 'police activity',
            'evacuate', 'shelter in place', 'emergency', 'danger'
        ]
        
        # HIGH priority keywords - safety concerns
        high_keywords = [
            'burglary', 'theft', 'stolen', 'vandalism', 'missing person',
            'lost pet', 'found pet', 'suspicious vehicle', 'scam',
            'power outage', 'gas leak', 'flood', 'accident'
        ]
        
        # Check for critical posts
        for keyword in critical_keywords:
            if keyword in text_lower:
                return 'critical'
        
        # Check for high priority posts
        for keyword in high_keywords:
            if keyword in text_lower:
                return 'high'
        
        # Default to category-based urgency
        return category
    
    def _calculate_post_age(self, created_at_str):
        """Calculate how many hours ago a post was created"""
        if not created_at_str:
            return 999
        
        try:
            post_time = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            now = datetime.now(post_time.tzinfo)
            age = now - post_time
            return age.total_seconds() / 3600
        except:
            return 999
    
    def _sort_posts_by_urgency(self, posts):
        """
        Sort posts by urgency and recency
        Similar to Twitter priority sorting
        """
        urgency_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        
        # Sort by urgency first, then by age (newest first within urgency)
        sorted_posts = sorted(
            posts,
            key=lambda p: (
                urgency_order.get(p.get('urgency', 'medium'), 2),
                p.get('age_hours', 999)
            )
        )
        
        return sorted_posts
    
    def get_statistics(self, posts):
        """Get statistics about fetched posts"""
        if not isinstance(posts, list):
            return None
        
        stats = {
            'total_posts': len(posts),
            'by_urgency': {},
            'by_zip': {},
            'by_category': {},
            'newest_post_hours': min((p.get('age_hours', 999) for p in posts), default=0),
            'oldest_post_hours': max((p.get('age_hours', 0) for p in posts), default=0),
        }
        
        for post in posts:
            # Count by urgency
            urgency = post.get('urgency', 'unknown')
            stats['by_urgency'][urgency] = stats['by_urgency'].get(urgency, 0) + 1
            
            # Count by ZIP
            zip_code = post.get('zip_code', 'unknown')
            stats['by_zip'][zip_code] = stats['by_zip'].get(zip_code, 0) + 1
            
            # Count by category
            category = post.get('category', 'unknown')
            stats['by_category'][category] = stats['by_category'].get(category, 0) + 1
        
        return stats


# Mock data generator for testing (when API not available)
class MockNextdoorData:
    """Generate mock Nextdoor posts for testing"""
    
    @staticmethod
    def generate_sample_posts(zip_codes):
        """Generate sample posts for testing the interface"""
        from datetime import datetime, timedelta
        import random
        
        sample_posts = []
        
        categories = {
            'urgent_alert': [
                "Power outage reported on Main St. Multiple blocks affected. Electric company notified.",
                "Suspicious vehicle circling the neighborhood. Dark sedan, no plates visible. Police called.",
                "Gas smell reported near the corner of Oak and Elm. Fire department on scene."
            ],
            'crime_safety': [
                "Package theft reported on Cedar Lane this morning around 10 AM. Check your cameras.",
                "Car break-ins on Maple Street last night. 3 vehicles had windows smashed.",
                "Scam alert: Person claiming to be from water company asking for payment. City confirmed it's fake."
            ],
            'lost_found': [
                "LOST: Orange tabby cat, answers to Whiskers. Last seen on Pine St. Please call if found.",
                "FOUND: Set of car keys near the park entrance. Contact to claim.",
                "Missing: Small white dog, wearing blue collar. Ran out gate this evening."
            ],
            'emergency_planning': [
                "Reminder: Community emergency preparedness meeting next Thursday at 7 PM.",
                "Tornado season prep: Check your emergency kits and know your shelter locations.",
                "Neighborhood watch meeting scheduled for next week. All welcome."
            ]
        }
        
        for zip_code in zip_codes:
            for category, messages in categories.items():
                for i, msg in enumerate(messages):
                    age_hours = random.randint(1, 48)
                    created_at = (datetime.utcnow() - timedelta(hours=age_hours)).isoformat() + 'Z'
                    
                    urgency_map = {
                        'urgent_alert': 'critical',
                        'crime_safety': 'high',
                        'lost_found': 'high',
                        'emergency_planning': 'medium'
                    }
                    
                    sample_posts.append({
                        'zip_code': zip_code,
                        'category': category,
                        'text': msg,
                        'author': f'Neighbor{random.randint(1, 100)}',
                        'created_at': created_at,
                        'age_hours': age_hours,
                        'urgency': urgency_map.get(category, 'medium'),
                        'post_type': category,
                    })
        
        # Sort by urgency and recency
        urgency_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        sample_posts.sort(key=lambda p: (urgency_order[p['urgency']], p['age_hours']))
        
        return sample_posts
