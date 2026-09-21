from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.users.models import User


def is_root_user(user) -> bool:
    """
    Root / superuser — barcha API endpointlarga to'liq ruxsat.
    username == 'root' yoki is_superuser=True.
    """
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'is_superuser', False):
        return True
    if getattr(user, 'username', None) == 'root':
        return True
    return False


class IsBusinessOwner(BasePermission):
    def has_permission(self, request, view):
        if is_root_user(request.user):
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.OWNER
        )


class IsEmployee(BasePermission):
    def has_permission(self, request, view):
        if is_root_user(request.user):
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.EMPLOYEE
        )


class IsCustomer(BasePermission):
    def has_permission(self, request, view):
        if is_root_user(request.user):
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.CUSTOMER
        )


class IsOwnerOrCustomer(BasePermission):
    """Katalog: OWNER, CUSTOMER yoki root."""

    def has_permission(self, request, view):
        if is_root_user(request.user):
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (User.Role.OWNER, User.Role.CUSTOMER)
        )


class IsCatalogViewer(BasePermission):
    """Authenticated users may browse the catalog; writes stay role-restricted."""

    def has_permission(self, request, view):
        if is_root_user(request.user):
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role == User.Role.EMPLOYEE:
            return request.method in SAFE_METHODS
        return bool(
            request.user.role in (
                User.Role.OWNER,
                User.Role.CUSTOMER,
            )
        )


class IsBusinessOwnerOrRoot(BasePermission):
    def has_permission(self, request, view):
        return is_root_user(request.user) or bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.OWNER
        )


class IsEmployeeOrOwner(BasePermission):
    def has_permission(self, request, view):
        if is_root_user(request.user):
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (User.Role.OWNER, User.Role.EMPLOYEE)
        )


IsEmployeeOrOwnerShared = IsEmployeeOrOwner
