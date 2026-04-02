from playwright.sync_api import sync_playwright
import time

# ======================
# 你的账号密码
# ======================
USERNAME = "5894"
PASSWORD = "Cq123456"

# 持久化配置（记住登录）
USER_DATA_DIR = "./my_browser_profile"

# 你要跳的页面
HOME_URL = "http://111.10.250.16:9803/#/main/home"
TARGET_URL = "http://111.10.250.16:9803/#/produce/craft/product/inventory"


# ======================
# 你可以自己加功能！
# ======================
def func1(page):
    print("👉 执行功能 1：刷新当前页面")
    page.reload()


def func2(page):
    print("👉 执行功能 2：点击页面第一个按钮")
    page.click("button >> visible=true")


def func3(page):
    print("👉 执行功能 3：截图当前页面")
    page.screenshot(path="截图.png")


def func4(page):
    print("👉 执行功能 4：跳转到库存页面")
    page.goto(TARGET_URL)


# ======================
# 主程序
# ======================
with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir=USER_DATA_DIR,
        headless=False,
        slow_mo=300
    )
    page = browser.new_page()
    page.goto(HOME_URL)

    # 自动登录
    try:
        page.wait_for_selector('input[placeholder="请输入用户名"]', timeout=4000)
        page.fill('input[placeholder="请输入用户名"]', USERNAME)
        page.fill('input[placeholder="请输入密码"]', PASSWORD)
        page.click('button.submit-button:has-text("登录")')
        page.wait_for_load_state("networkidle")
        print("✅ 登录成功！")
    except:
        print("✅ 已登录，无需重复登录")

    # 跳转到目标页面
    page.goto(TARGET_URL)
    print("✅ 已进入库存页面")
    time.sleep(1)

    # ======================
    # 交互式菜单（你输入数字执行）
    # ======================
    while True:
        print("\n===== 请选择要执行的操作 =====")
        print("1 → 刷新页面")
        print("2 → 点击页面第一个按钮")
        print("3 → 截图")
        print("4 → 重新跳转到库存页面")
        print("0 → 退出程序")

        try:
            choice = input("\n请输入数字：").strip()

            if choice == "1":
                func1(page)
            elif choice == "2":
                func2(page)
            elif choice == "3":
                func3(page)
            elif choice == "4":
                func4(page)
            elif choice == "0":
                print("👋 退出程序...")
                break
            else:
                print("❌ 输入错误，请重新输入")
        except Exception as e:
            print("发生错误：", e)

    browser.close()