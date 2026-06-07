"""ChaoxingAgent 异常基类 — 三级异常模型"""


class ChaoxingError(Exception):
    """所有自定义异常的基类"""
    pass


class RecoverableError(ChaoxingError):
    """可恢复异常 — 自动重试，重试上限后升级为 PauseRequiredError"""
    pass


class PauseRequiredError(ChaoxingError):
    """需暂停异常 — 保存现场，通知用户，等待用户指令"""
    pass


class FatalStopError(ChaoxingError):
    """致命停止异常 — 保存 trace，退出"""
    pass
