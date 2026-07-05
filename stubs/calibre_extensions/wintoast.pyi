def initialize_toast(appname: str, app_user_model_id: str, shortcut_policy: int = 0) -> None:
    'Initialize the WinToast library with the specified app name and app user model id'
    pass

def notify(title: str, message: str, icon_path: str) -> int:
    'Show a toast notification with the specified title, message and icon path, returning its id'
    pass

SHORTCUT_POLICY_IGNORE: int
SHORTCUT_POLICY_REQUIRE_CREATE: int
SHORTCUT_POLICY_REQUIRE_NO_CREATE: int
