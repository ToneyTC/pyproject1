from playwright.sync_api import sync_playwright
import time

# ======================
# 你的账号密码
# ======================
USERNAME = "5894"
PASSWORD = "Cq123456"

# ======================
# 核心：持久化用户数据目录
# 登录信息会永久保存在这里
# ======================
USER_DATA_DIR = "./my_browser_profile"

with sync_playwright() as p:
    # 启动浏览器，开启持久化（记住密码、记住登录、记住账号）
    browser = p.chromium.launch_persistent_context(
        user_data_dir=USER_DATA_DIR,  # 关键：保存所有数据
        headless=False,
        slow_mo=300,
        viewport={"width": 1300, "height": 800}
    )

    page = browser.new_page()
    page.goto("http://111.10.250.16:9803/#/main/home")

    # ============= 自动登录 =============
    try:
        # 等待用户名输入框出现
        page.wait_for_selector('input[placeholder="请输入用户名"]', timeout=5000)

        print("正在输入账号密码...")
        page.fill('input[placeholder="请输入用户名"]', USERNAME)
        page.fill('input[placeholder="请输入密码"]', PASSWORD)

        # 点击登录
        page.click('button.submit-button:has-text("登录")')
        time.sleep(2)
        print("登录成功！信息已永久保存！")

    except:
        print("已经登录过啦！无需再次输入密码～")

    # ============= 永久不关闭 =============
    print("页面已保持打开，关闭窗口即可退出")
    while True:
        time.sleep(1)