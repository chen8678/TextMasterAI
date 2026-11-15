import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import login
from django.utils import timezone
from .serializers import UserSerializer, LoginSerializer, RegisterSerializer
from .models import User
from django.conf import settings as dj_settings
from apps.system.throttles import LoginRateThrottle, RegisterRateThrottle

logger = logging.getLogger(__name__)

def _first_error_message(errors):
    """从 DRF serializer.errors 中取第一条可读错误信息"""
    if not errors:
        return '请求参数错误'
    if isinstance(errors, list):
        return errors[0] if errors else '请求参数错误'
    if isinstance(errors, dict):
        for key, value in errors.items():
            if isinstance(value, list) and value:
                return value[0]
            if isinstance(value, str):
                return value
    return '请求参数错误'


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def login_view(request):
    """用户登录。请求体 JSON：{"username": "xxx", "password": "xxx"}"""
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)
        
        # 更新最后登录时间
        user.last_login_at = timezone.now()
        user.save(update_fields=['last_login_at'])
        
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data
        })
    detail = _first_error_message(serializer.errors)
    return Response({'detail': detail, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([RegisterRateThrottle])
def register_view(request):
    """用户注册（受 ALLOW_PUBLIC_REGISTRATION 与注册限流约束）。"""
    if not getattr(dj_settings, "ALLOW_PUBLIC_REGISTRATION", False):
        return Response(
            {
                "detail": "当前未开放自助注册，请联系管理员开通账号。",
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        refresh = RefreshToken.for_user(user)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """用户登出：将 refresh 加入黑名单。"""
    refresh_token = request.data.get("refresh")
    if not refresh_token:
        return Response(
            {"detail": "缺少 refresh 令牌"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({"message": "登出成功"}, status=status.HTTP_200_OK)
    except TokenError as exc:
        return Response(
            {"detail": f"refresh 无效或已过期: {exc}"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception:
        logger.exception("logout_view unexpected error")
        return Response(
            {"detail": "登出失败，请稍后重试"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def admin_login_view(request):
    """管理员登录"""
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        
        # 检查是否为管理员
        if not (user.is_staff or user.is_superuser):
            return Response({
                'error': '权限不足，需要管理员权限'
            }, status=status.HTTP_403_FORBIDDEN)
        
        refresh = RefreshToken.for_user(user)
        
        # 更新最后登录时间
        user.last_login_at = timezone.now()
        user.save(update_fields=['last_login_at'])
        
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data
        })
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    """获取或更新用户信息"""
    if request.method == 'GET':
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
    
    elif request.method == 'PUT':
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
