from django.http import JsonResponse
from django.core.cache import cache
from django.conf import settings
import time


class RateLimitMiddleware:
    """Rate limiting middleware"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check rate limit for specific endpoints
        if self.should_rate_limit(request):
            if not self.check_rate_limit(request):
                return JsonResponse(
                    {'error': 'Rate limit exceeded'}, 
                    status=429
                )

        response = self.get_response(request)
        return response

    def should_rate_limit(self, request):
        """Check if request should be rate limited"""
        rate_limited_paths = [
            '/user/login-token/',
            '/user/sessions/',
            '/user/users/',
            '/user/leaderboard/'
        ]
        return any(request.path.startswith(path) for path in rate_limited_paths)

    def check_rate_limit(self, request):
        """Check rate limit for request"""
        client_ip = self.get_client_ip(request)
        
        # Determine rate limit settings based on path
        if '/user/login-token/' in request.path:
            settings_key = 'auth'
        elif '/user/sessions/' in request.path:
            settings_key = 'game'
        else:
            settings_key = 'user'

        rate_settings = getattr(settings, 'RATE_LIMIT_SETTINGS', {}).get(
            settings_key, {'window': 60, 'max_requests': 100}
        )

        cache_key = f"rate_limit:{client_ip}:{settings_key}"
        current_time = int(time.time())
        window_start = current_time - rate_settings['window']

        # Get current requests in window
        requests = cache.get(cache_key, [])
        
        # Filter requests within current window
        requests = [req_time for req_time in requests if req_time > window_start]
        
        # Check if limit exceeded
        if len(requests) >= rate_settings['max_requests']:
            return False

        # Add current request
        requests.append(current_time)
        cache.set(cache_key, requests, rate_settings['window'])
        
        return True

    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
