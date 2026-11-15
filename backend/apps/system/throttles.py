"""项目级限流策略（P3-T21 / P0-04）。"""
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"


class RegisterRateThrottle(AnonRateThrottle):
    """公网自助注册限流（默认 5/hour，见 THROTTLE_REGISTER）。"""

    scope = "register"


class AskQuestionRateThrottle(UserRateThrottle):
    scope = "ask_question"


class SandboxTriggerRateThrottle(UserRateThrottle):
    scope = "sandbox_trigger"
