from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('admin-login/', views.admin_login_view, name='admin-login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    # P0-10 / P0-03 偏差修复：挂载 refresh，供黑名单与 smoke 验收
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
