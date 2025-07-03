from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied


class IsStaff(permissions.BasePermission):
    """
       Allows access only to Staff users.
    """

    message = 'Please verify your identity as a staff to complete this action'

    def has_permission(self, request, view):
        if request.user and request.user.is_active and request.user.is_staff:
            return True
        else:
            raise PermissionDenied(detail=self.message)


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Custom permission to only allow owners to edit their own data"""

    def has_object_permission(self, request, view, obj):
        # Read permissions for any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only to owner
        return obj.user == request.user


class IsAuthenticatedAndActive(permissions.BasePermission):
    """Custom permission for authenticated and active users only"""

    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.is_active
        )
    