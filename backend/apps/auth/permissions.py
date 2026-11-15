from rest_framework.permissions import BasePermission


class IsProUser(BasePermission):
    """仅允许 PRO 用户访问。"""

    message = "该功能仅对 PRO 用户开放。"

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and getattr(user, "is_pro", False))
