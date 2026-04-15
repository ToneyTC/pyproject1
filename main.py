from playwright.sync_api import sync_playwright
import re
import time

# 工艺详情页校验（文案按业务约定，若系统升级日期变化可改此处）
_EXP_批记录报表 = ("RC-9000-05-02", "批包装记录", "2025.10.26")
_EXP_指令报表 = ("RC-9001-15-03", "中药饮片", "批包装指令", "2025.10.26")
_EXP_指令参数记录 = ("饮片包装批指令-新",)
_EXP_工序记录报表 = ("RC-9020-01-11", "包装生产记录", "2026.01.26")
_EXP_工步设备编码 = ("SC-276", "SC-477", "SC-492")

# ======================
# 配置信息
# ======================
USERNAME = "5894"
PASSWORD = "Cq123456"
HOME_URL = "http://111.10.250.16:9803/"
USER_DATA_DIR = "./my_profile"


def _产品BOM列表总条数(page):
    """
    列表数据条数以分页「共 N 条」为准（与界面右下角一致）；
    解析不到时再退回数表格行（固定列/多 body 时 tr 可能不准，仅作兜底）。
    """
    pat = re.compile(r"共\s*(\d+)\s*条")
    totals = page.locator(".el-pagination__total")
    for i in range(totals.count()):
        el = totals.nth(i)
        if not el.is_visible():
            continue
        m = pat.search(el.inner_text())
        if m:
            return int(m.group(1))
    m = pat.search(page.locator("body").inner_text())
    if m:
        return int(m.group(1))
    return page.locator("table.el-table__body tr").count()


def _勾选物料表格行(row):
    """勾选 Element UI 表格行左侧选择框。原生 checkbox 常因样式在视口外，需滚动 + force 或 JS click。"""
    row.scroll_into_view_if_needed(timeout=10000)
    time.sleep(0.2)
    first_cell = row.locator("td").first
    label = first_cell.locator("label.el-checkbox").first
    if label.count() > 0:
        label.click(timeout=8000, force=True)
        return
    inp = first_cell.locator("input.el-checkbox__original").first
    if inp.count() == 0:
        inp = row.locator("input.el-checkbox__original").first
    if inp.count() == 0:
        inp = row.locator("input[type='checkbox']").first
    inp.evaluate("el => { if (!el.checked) el.click(); }")


def _投料工位已选择(row, cell_count):
    """仅当投料工位对应 input 的 value 非空时视为已选。界面仍显示「选择投料工位」占位时 value 为空，不算已选。"""
    cells = row.locator("td")
    feed_cell = cells.nth(cell_count - 1)

    ph = row.locator("input[placeholder='选择投料工位']").first
    if ph.count() > 0 and ph.input_value().strip():
        return True

    inner = feed_cell.locator("input.el-input__inner").first
    if inner.count() > 0 and inner.input_value().strip():
        return True

    return False


def _勾选匹配物料行跳过半成品首行(page, code, action_label="操作"):
    """
    在表格中勾选「查询结果里匹配 code」的一行：
    若首行整行文案含「半成品」（物料代码/名称/产品类型等任一列）且存在第二条匹配行，则勾选第二条。
    """
    rows = page.locator("table.el-table__body tr").filter(has_text=code)
    n = rows.count()
    if n == 0:
        raise RuntimeError(f"未找到与物料代码 {code!r} 匹配的行")

    half_in_row = "半成品" in rows.nth(0).inner_text()

    idx = 0
    if half_in_row:
        if n >= 2:
            idx = 1
            print(f"⚠️ 首行与半成品相关（代码/名称或类型列），{action_label}改选第二条")
        else:
            print("⚠️ 首行与半成品相关但仅一条匹配，仍勾选该条")

    target = rows.nth(idx)
    target.wait_for(timeout=10000)
    _勾选物料表格行(target)


def _点击返回上一页(page):
    for sel in (
        "button:has-text('返回上一页')",
        "span:has-text('返回上一页')",
        "a:has-text('返回上一页')",
    ):
        loc = page.locator(sel).first
        if loc.count() > 0 and loc.is_visible():
            loc.click(timeout=5000)
            time.sleep(0.8)
            return
    page.locator("text=返回上一页").first.click(timeout=5000, force=True)
    time.sleep(0.8)


def _读工艺表单项文本(page, label_fragment):
    item = page.locator("div.el-form-item").filter(has_text=label_fragment).first
    if item.count() == 0:
        return ""
    inp = item.locator("input.el-input__inner").first
    if inp.count() > 0:
        v = inp.input_value().strip()
        if v:
            return v
        # disabled/readonly 的 el-select 有时 input_value 为空，回退读取 value 属性
        attr_v = (inp.get_attribute("value") or "").strip()
        if attr_v:
            return attr_v
    ta = item.locator("textarea").first
    if ta.count() > 0:
        v = ta.input_value().strip()
        if v:
            return v
    # 再兜底：返回整个表单项文本（包含下拉已选展示文案）
    return item.inner_text()


def _工艺字段符合(page, label_fragment, expected_parts):
    text = _读工艺表单项文本(page, label_fragment)
    if not text:
        return False
    return all(part in text for part in expected_parts)


def _读取当前工序记录报表文本(page):
    """
    读取当前工序区域里的「工序记录报表」字段文本。
    优先取你提供的只读 input（placeholder=请选择工序记录报表）的 value。
    """
    item = page.locator("div.el-form-item").filter(has_text="工序记录报表").first
    if item.count() > 0:
        inp = item.locator(
            "input[placeholder='请选择工序记录报表'], input.el-input__inner[placeholder*='工序记录报表']"
        ).first
        if inp.count() > 0:
            v = inp.input_value().strip()
            if v:
                return v
            attr_v = (inp.get_attribute("value") or "").strip()
            if attr_v:
                return attr_v
        return item.inner_text()

    # 兜底：直接取页面该占位输入
    inp = page.locator("input[placeholder='请选择工序记录报表']").first
    if inp.count() > 0:
        v = inp.input_value().strip()
        if v:
            return v
        attr_v = (inp.get_attribute("value") or "").strip()
        if attr_v:
            return attr_v
    return ""


def _加工顺序仅一条且为包装(page):
    # 优先按工序列表 DOM 判断，避免正文正则受空格/标点/隐藏文本影响
    items = page.locator("li.working-procedure-item")
    n = items.count()
    if n == 0:
        # 兜底：部分页面可能未带 class
        items = page.locator("li").filter(has_text=re.compile(r"包装"))
        n = items.count()
    if n != 1:
        return False
    txt = items.nth(0).inner_text().strip()
    txt_norm = re.sub(r"\s+", "", txt)
    return "包装" in txt_norm


def _工艺列表行属成品工艺(text):
    """与半成品/BCP 工艺区分：含「半成品」或编码含 _bcp 的视为非目标行。"""
    low = text.lower()
    if "半成品" in text:
        return False
    if "_bcp" in low:
        return False
    return True


def _工艺管理列表工艺编号列索引(page):
    """根据表头「工艺编号」定位列下标，避免点到其它列链接。"""
    ths = page.locator(".el-table__header-wrapper th, table.el-table__header th")
    for i in range(ths.count()):
        if "工艺编号" in ths.nth(i).inner_text():
            return i
    return 1


def _工艺单元格点击编号入口(cell):
    """工艺编号可能是 `<a>` 或 `el-button--text` 文字按钮。"""
    btn = cell.locator("button.el-button--text").first
    if btn.count() > 0:
        btn.click(timeout=8000)
        return True
    btn = cell.locator("button").first
    if btn.count() > 0:
        btn.click(timeout=8000)
        return True
    link = cell.locator("a").first
    if link.count() > 0:
        link.click(timeout=8000)
        return True
    return False


def _工艺表格行点击工艺编号进入详情(page, row):
    """点击该行「工艺编号」列内的链接或文字按钮进入工艺基本信息页。"""
    idx = _工艺管理列表工艺编号列索引(page)
    cell = row.locator("td").nth(idx)
    if _工艺单元格点击编号入口(cell):
        return
    for j in range(row.locator("td").count()):
        c = row.locator("td").nth(j)
        if _工艺单元格点击编号入口(c):
            return
    raise RuntimeError("该行未找到可点击的工艺编号（链接或按钮）")


def _工艺管理查询后打开并校验详情(page, code):
    """查询后打开不含「半成品」的工艺行，逐项校验；任一步失败立即返回上一页。"""
    time.sleep(1.2)
    rows = page.locator("table.el-table__body tr").filter(has_text=code)
    n = rows.count()
    if n == 0:
        print("❌ 工艺管理无匹配行，跳过详情校验")
        return

    pick_i = None
    for i in range(n):
        if _工艺列表行属成品工艺(rows.nth(i).inner_text()):
            pick_i = i
            break
    if pick_i is None:
        pick_i = 0
        print("⚠️ 匹配行均为半成品/BCP 等，仍打开首条")

    row = rows.nth(pick_i)
    row.scroll_into_view_if_needed(timeout=8000)
    _工艺表格行点击工艺编号进入详情(page, row)
    print("✅ 已点击工艺编号进入工艺基本信息（优先成品/非 BCP 行）")
    time.sleep(2)

    def fail(msg):
        print(f"❌ {msg}，返回上一页")
        _点击返回上一页(page)

    if not _工艺字段符合(page, "批记录报表", _EXP_批记录报表):
        return fail("批记录报表与约定不符")
    if not _工艺字段符合(page, "指令报表", _EXP_指令报表):
        return fail("指令报表与约定不符")
    if not _工艺字段符合(page, "指令参数记录", _EXP_指令参数记录):
        return fail("指令参数记录与约定不符")
    if not _加工顺序仅一条且为包装(page):
        return fail("加工顺序须仅一条且为「包装」")

    step_item = page.locator("li.working-procedure-item").filter(has_text="包装").first
    if step_item.count() > 0:
        step_item.click(timeout=5000)
    else:
        try:
            page.locator("text=1、包装").first.click(timeout=5000)
        except Exception:
            page.get_by_text(re.compile(r"1\s*[、.]\s*包装")).first.click(timeout=5000)
    time.sleep(1)

    step_report_text = _读取当前工序记录报表文本(page)
    if not step_report_text or not all(part in step_report_text for part in _EXP_工序记录报表):
        return fail("工序记录报表与约定不符")

    tab = page.locator("div.el-tabs__item").filter(has_text="工位").filter(has_text="工步").first
    if tab.count() == 0:
        tab = page.locator("div.el-tabs__item:text('工位&工步')").first
    tab.click(timeout=5000)
    time.sleep(1)

    step_area = page.locator("table.el-table__body").first
    if step_area.count() == 0:
        return fail("未找到工位工步表格")
    step_text = step_area.inner_text()
    for dev in _EXP_工步设备编码:
        if dev not in step_text:
            return fail(f"工步/设备区域未包含 {dev}")

    print("✅ 工艺详情校验全部通过")
    _点击返回上一页(page)


def _填充工艺管理查询工艺字段(page, code):
    craft_input = page.locator("input[placeholder='请输入工艺名称/编码']").first
    if craft_input.count() == 0:
        craft_input = page.locator("input[placeholder*='工艺名称']").first
    craft_input.clear()
    craft_input.fill(code)


def _关闭可能出现的确认弹窗(page, max_rounds=6):
    """发布等操作后的 Element 确定/确认弹窗。"""
    for _ in range(max_rounds):
        clicked = False
        for sel in (
            "div.el-message-box__wrapper button:has-text('确定')",
            ".el-dialog:visible button.el-button--primary:has-text('确定')",
            ".el-dialog:visible button:has-text('确认')",
        ):
            btn = page.locator(sel).first
            if btn.count() > 0 and btn.is_visible():
                btn.click(timeout=4000)
                clicked = True
                time.sleep(0.6)
                break
        if not clicked:
            break


def _单条半成品_工艺发布确认流程(page, code):
    """
    产品 BOM 仅一条且为半成品时：进入工艺管理「待发布」→ 查询 → 有数据则勾选发布并确认弹窗；
    若「待发布」无数据，则直接切「启用中」查询并校验工艺基本信息（与成品链路校验一致）。
    有待发布且发布成功后同样切「启用中」再校验。
    """
    print("\n👉 跳转工艺管理「待发布」，执行工艺发布确认流程")
    page.click("span.title:text('工艺')", timeout=8000)
    time.sleep(0.5)
    page.click("div.child-menu-name:text('工艺管理')", timeout=8000)
    time.sleep(1.5)
    page.click("div.el-tabs__item:text('待发布')", timeout=8000)
    time.sleep(1)
    _填充工艺管理查询工艺字段(page, code)
    page.click("button:has-text('查询')", timeout=5000)
    time.sleep(1.5)
    if page.locator("text=暂无数据").is_visible(timeout=3000):
        print("ℹ️ 「待发布」无数据 → 在「启用中」确认工艺基本信息是否符合条件")
        page.click("div.el-tabs__item:text('启用中')", timeout=8000)
        time.sleep(1)
        _填充工艺管理查询工艺字段(page, code)
        page.click("button:has-text('查询')", timeout=5000)
        time.sleep(1.2)
        _工艺管理查询后打开并校验详情(page, code)
        return
    row = page.locator("table.el-table__body tr").filter(has_text=code).first
    if row.count() == 0:
        row = page.locator("table.el-table__body tr").first
    row.wait_for(timeout=10000)
    _勾选物料表格行(row)
    time.sleep(0.3)
    page.click("button:has-text('发布')", timeout=5000)
    time.sleep(0.5)
    _关闭可能出现的确认弹窗(page)
    print("✅ 工艺待发布已提交发布（已处理确认弹窗）")
    time.sleep(1.5)
    page.click("div.el-tabs__item:text('启用中')", timeout=8000)
    time.sleep(1)
    _填充工艺管理查询工艺字段(page, code)
    page.click("button:has-text('查询')", timeout=5000)
    time.sleep(1.2)
    _工艺管理查询后打开并校验详情(page, code)


# ======================
# 发布计划（完整逻辑）
# ======================
def 发布计划(page):
    print("\n==================================")
    print(" 👉 开始执行：生产管理 → 工艺 → 产品BOM")
    print("==================================")

    try:
        # 1. 生产管理
        page.click("b.quick-name:text('生产管理')", timeout=8000)
        print("✅ 生产管理")
        time.sleep(1)

        # 2. 工艺
        page.click("span.title:text('工艺')", timeout=8000)
        print("✅ 工艺")
        time.sleep(1)

        # 3. 产品BOM
        page.click("div.child-menu-name:text('产品BOM')", timeout=8000)
        print("✅ 产品BOM")
        time.sleep(2)

        # 切换待发布标签
        page.click("div.el-tabs__item:text('待发布')", timeout=8000)
        print("✅ 已切换到：待发布")
        time.sleep(1)

        # 循环输入物料代码
        while True:
            # 输入物料代码
            input_box = page.locator("input.el-input__inner[placeholder='请输入物料代码']")
            code = input("\n请输入物料代码：").strip()
            if not code.isdigit():
                print("❌ 物料代码仅允许输入数字，请重新输入")
                continue
            input_box.clear()
            input_box.fill(code)
            print(f"✅ 已输入：{code}")
            time.sleep(0.5)

            # 查询
            page.click("button:has-text('查询')", timeout=5000)
            print("✅ 已点击查询")
            time.sleep(2)
111
            # 空数据 → 重置 → 重新输入
            if page.locator("text=暂无数据").is_visible(timeout=2000):
                print(f"\n❌ BOM 不存在：{code}")
                page.click("button:has-text('重置')", timeout=3000)
                print("🔄 已重置，重新输入")
                time.sleep(1)
                continue

            # 统计数据条数（以分页「共 N 条」为准）
            data_count = _产品BOM列表总条数(page)
            tr_ref = page.locator("table.el-table__body tr").count()
            print(f"🔍 查询结果总条数：{data_count}（分页）；表格 tr 计数参考：{tr_ref}")

            # ==========================================
            # 1条：半成品 → 专用流程；非半成品 → 勾选第一条（与多条「首条非半成品」一致）
            # ==========================================
            checkbox1_xpath = "/html/body/div/div/div[2]/div/div[2]/div[2]/div/div/div/div[1]/div[1]/div[1]/div[2]/div/div/div/div[4]/div[2]/table/tbody/tr[1]/td[1]/div/label/span/span"

            if data_count == 1:
                first_row = page.locator("table.el-table__body tr").first
                first_row.wait_for(timeout=8000)
                if "半成品" in first_row.inner_text():
                    _单条半成品_工艺发布确认流程(page, code)
                    print("✅ 单条半成品：工艺发布确认流程已完成")
                    break
                print("ℹ️ 只有1条且非半成品 → 勾选第一条并编辑")
                page.locator(f"xpath={checkbox1_xpath}").click(timeout=5000)
                time.sleep(0.5)

            # ==========================================
            # ≥2条数据 → 开始判断
            # ==========================================
            elif data_count >= 2:
                print("📌 数据 ≥2条，开始判断")

                # 读取第一条第5列内容（你给的绝对XPath）
                first_xpath = "/html/body/div[1]/div/div[2]/div/div[2]/div[2]/div/div/div/div[1]/div[1]/div[1]/div[2]/div/div/div/div[3]/table/tbody/tr[1]/td[5]/div/div/div"
                first_text = page.locator(f"xpath={first_xpath}").inner_text().strip()
                print(f"📄 第一条内容：{first_text}")

                # ==========================================
                # 核心逻辑：半成品判断 + 勾选
                # ==========================================
                if "半成品" in first_text:
                    print("✅ 第一条包含【半成品】→ 勾选第二条")
                    checkbox2_xpath = "/html/body/div/div/div[2]/div/div[2]/div[2]/div/div/div/div[1]/div[1]/div[1]/div[2]/div/div/div/div[4]/div[2]/table/tbody/tr[2]/td[1]/div/label/span/span"
                    page.locator(f"xpath={checkbox2_xpath}").click(timeout=5000)
                    print("✅ 第二条已勾选")

                else:
                    print("ℹ️ 第一条【不包含半成品】→ 勾选第一条并编辑")
                    page.locator(f"xpath={checkbox1_xpath}").click(timeout=5000)
                    time.sleep(0.5)

            else:
                continue

            # 点击编辑进入页面（1条非半成品 与 ≥2条 共用）
            page.click("button.el-button--primary:has-text('编辑')", timeout=5000)
            time.sleep(3)
            print("✅ 进入编辑页面")

            # ==========================================
            # 🔥 最终修复：按你的HTML精准识别 自制+成品
            # ==========================================
            print("🔧 开始自动设置：成品 → 主料=是")
            rows = page.locator("table.el-table__body tr")
            row_count = rows.count()
            # 是否主料允许多行同时为「是」（每行是独立单选组）

            for i in range(row_count):
                row = rows.nth(i)
                cells = row.locator("td")
                cell_count = cells.count()
                if cell_count < 5:
                    continue

                # 按列读取，避免使用页面动态 data-v 属性导致定位失败
                manufacture_way = cells.nth(2).inner_text().strip()   # 制造方式
                material_kind = cells.nth(3).inner_text().strip()     # 物料种类（成品/包材等）

                print(f"第{i + 1}行 | 制造方式：{manufacture_way} | 物料种类：{material_kind}")

                # 条件：自制 +（成品/半成品）-> 点击“是否主料”列里的“是”
                if manufacture_way == "自制" and (("成品" in material_kind) or ("半成品" in material_kind)):
                    print("✅ 找到自制成品/半成品行，自动勾选【主料=是】")
                    major_col = cells.nth(4)
                    row.scroll_into_view_if_needed(timeout=8000)
                    time.sleep(0.2)

                    yes_radio = major_col.locator("label.el-radio").filter(has_text="是").first
                    yes_checked = yes_radio.locator("span.el-radio__input.is-checked").count() > 0 if yes_radio.count() > 0 else False
                    if not yes_checked:
                        if yes_radio.count() > 0:
                            yes_radio.click(timeout=5000, force=True)
                        else:
                            # 兜底：点击当前列内第一个单选框
                            major_col.locator("label.el-radio span.el-radio__inner").first.click(timeout=5000, force=True)
                        time.sleep(0.5)

                    yes_checked = yes_radio.locator("span.el-radio__input.is-checked").count() > 0 if yes_radio.count() > 0 else False
                    if not yes_checked:
                        raise RuntimeError(f"第{i + 1}行【是否主料=是】设置失败")

                # 每一行都设置【投料工位 = 机包】（已有选择则跳过）
                if _投料工位已选择(row, cell_count):
                    print(f"⏭️ 第{i + 1}行投料工位已有选择，跳过")
                    continue

                print(f"🔧 第{i + 1}行开始设置投料工位：机包")
                feed_station_input = row.locator("input[placeholder='选择投料工位']").first
                if feed_station_input.count() > 0:
                    feed_station_input.click(timeout=5000)
                else:
                    # 兜底：点击该行最后一列可编辑区域
                    cells.nth(cell_count - 1).locator("input.el-input__inner").first.click(timeout=5000)

                dialog = page.locator("div.el-dialog:visible").last
                dialog.wait_for(timeout=8000)

                machine_pack_node = dialog.get_by_text("机包", exact=False).first
                if machine_pack_node.count() > 0:
                    machine_pack_node.click(timeout=5000)
                    time.sleep(0.5)

                # 保存弹窗选择
                dialog.locator("button:has-text('保存')").last.click(timeout=5000)
                print(f"✅ 第{i + 1}行投料工位已设置为机包")
                time.sleep(0.5)

            # 全部行处理完后，点击页面确认按钮
            confirm_btn = page.locator("button:has-text('确认并提交')").first
            if confirm_btn.count() == 0:
                confirm_btn = page.locator("button:has-text('确认')").first
            confirm_btn.click(timeout=5000)
            print("✅ 已点击确认提交")
            time.sleep(1.5)

            # 回到列表后：勾选不含半成品的首条成品行（首行含半成品则选第二条）并发布
            _勾选匹配物料行跳过半成品首行(page, code, action_label="发布")
            page.click("button:has-text('发布')", timeout=5000)
            print("✅ 已勾选目标行并发布")
            time.sleep(1.5)

            # 发布后切换到待审核
            page.click("div.el-tabs__item:text('待审核')", timeout=8000)
            print("✅ 已切换到待审核")
            time.sleep(1.0)

            # 待审核中同样规则勾选目标行
            _勾选匹配物料行跳过半成品首行(page, code, action_label="审核")

            # 点击审核
            page.click("button:has-text('审核')", timeout=5000)
            print("✅ 已打开审核弹窗")

            # 处理意见选择“通过”
            audit_dialog = page.locator("div.el-dialog:visible").last
            audit_dialog.wait_for(timeout=8000)
            opinion_input = audit_dialog.locator("input[placeholder*='处理意见']").first
            if opinion_input.count() == 0:
                opinion_input = audit_dialog.locator("input[placeholder*='请选择']").first
            opinion_input.click(timeout=5000)
            page.locator("li:has-text('通过')").first.click(timeout=5000)

            # 备注填写 1
            remark_box = audit_dialog.locator("textarea[placeholder*='备注']").first
            if remark_box.count() == 0:
                remark_box = audit_dialog.locator("textarea").first
            remark_box.fill("1")

            # 提交审核
            audit_dialog.locator("button:has-text('提交')").first.click(timeout=5000)
            print("✅ 审核已提交（处理意见=通过，备注=1）")
            time.sleep(1.5)

            # 审核完成后进入工艺管理，用相同物料代码查询
            page.click("span.title:text('工艺')", timeout=8000)
            time.sleep(0.5)
            page.click("div.child-menu-name:text('工艺管理')", timeout=8000)
            print("✅ 已进入工艺管理")
            time.sleep(1.5)

            _填充工艺管理查询工艺字段(page, code)
            page.click("button:has-text('查询')", timeout=5000)
            print(f"✅ 工艺管理已按工艺字段查询：{code}")

            _工艺管理查询后打开并校验详情(page, code)

            print("✅ 成品主料设置完成！")
            break

        print("\n🎉 流程全部执行完成！")

    except Exception as e:
        print(f"\n❌ 执行失败：{str(e)}")


# ======================
# 更新工艺
# ======================
def 更新工艺(page):
    print("\n👉 执行：更新工艺（待补充）")


# ======================
# 主程序（顶级主菜单）
# ======================
with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir=USER_DATA_DIR,
        headless=False,
        slow_mo=250
    )

    page = browser.new_page()
    page.goto(HOME_URL)

    # 自动登录
    try:
        page.wait_for_selector('input[placeholder="请输入用户名"]', timeout=3000)
        page.fill('input[placeholder="用户名"]', USERNAME)
        page.fill('input[placeholder="请输入密码"]', PASSWORD)
        page.click("button:has-text('登录')", timeout=5000)
        page.wait_for_load_state("networkidle")
        print("✅ 登录成功")
    except:
        print("✅ 已自动登录")

    # 顶级主菜单
    while True:
        print("\n===== 【顶级主菜单】=====")
        print("1 → 发布计划")
        print("2 → 更新工艺")
        print("0 → 退出")

        choice = input("请输入数字：").strip()

        if choice == "1":
            发布计划(page)
        elif choice == "2":
            更新工艺(page)
        elif choice == "0":
            print("👋 退出程序")
            break
        else:
            print("❌ 输入错误！")
