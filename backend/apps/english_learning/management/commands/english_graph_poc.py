"""Phase-C G1：本地验证 LangGraph POC（可选依赖 langgraph）。"""

from django.core.management.base import BaseCommand

from apps.english_learning.graph.checkpoint_store import default_thread_id
from apps.english_learning.graph.langgraph_poc import LANGGRAPH_AVAILABLE, invoke_english_graph_poc
from apps.english_learning.services import get_or_create_profile


class Command(BaseCommand):
    help = "运行英语学习向导 LangGraph POC（全向导节点线性占位链 + SQLite/InMemory checkpoint）；需安装 langgraph。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--thread-id",
            type=str,
            default="",
            help="LangGraph thread_id；默认 el:{profile_id}",
        )
        parser.add_argument(
            "--user-id",
            type=int,
            default=None,
            help="若指定，则从该用户的 Profile.session_state 取 phase 作为初始状态",
        )

    def handle(self, *args, **options):
        if not LANGGRAPH_AVAILABLE:
            self.stderr.write(
                self.style.ERROR("未安装 langgraph。完整依赖环境请执行：pip install 'langgraph>=0.2,<0.3'")
            )
            return

        user_id = options.get("user_id")
        initial = None
        thread_id = (options.get("thread_id") or "").strip()
        if user_id is not None:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            user = User.objects.filter(pk=int(user_id)).first()
            if user is None:
                self.stderr.write(self.style.ERROR(f"用户不存在: id={user_id}"))
                return
            profile = get_or_create_profile(user)
            st = profile.session_state or {}
            initial = {"phase": str(st.get("phase") or "intake"), "poc_trace": []}
            if not thread_id:
                thread_id = default_thread_id(profile.pk)
        if not thread_id:
            thread_id = "poc:anonymous"

        out, tip = invoke_english_graph_poc(thread_id=thread_id, initial=initial)
        self.stdout.write(self.style.SUCCESS(f"thread_id={thread_id}"))
        self.stdout.write(str(out))
        if tip:
            self.stdout.write(self.style.WARNING(f"checkpoint_tip={tip}"))
