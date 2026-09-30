# Flow 자동화용 전용 Chrome 프로필에 사람이 1회 로그인하기 위한 창을 여는 스크립트
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        ".flow_profile", channel="chrome", headless=False,
        ignore_default_args=["--enable-automation"],
        args=["--disable-blink-features=AutomationControlled"],
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://accounts.google.com/v3/signin/identifier?continue=https://flow.google.com/&flowName=GlifWebSignIn&flowEntry=ServiceLogin")
    print("로그인 후 창을 닫으면 세션이 저장된다.")
    ctx.wait_for_event("close", timeout=0)
