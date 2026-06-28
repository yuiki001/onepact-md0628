import requests
import time
import pandas as pd
from datetime import datetime
import os
import subprocess

# ================== 配置 ==================
CSV_FILE = "D:/fansign/ing/82major--md0630/82major线下签售.csv"  # CSV 文件名
GITHUB_REPO = "yuiki001/82major--md0630"        # 请替换为您的仓库名
GITHUB_BRANCH = "main"                          # 分支名（main 或 master）
PRODUCT_NAME = "musicndrama"                 # 商品名称（固定值）
# GitHub Personal Access Token 优先从环境变量 GITHUB_TOKEN 读取

# 定义API URL
url = "https://www.cn.musicndrama.com/ajax/oms/OMS_get_product.cm?prod_idx=13211"

# 定义请求头部
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0',
    'Referer': 'https://cn.musicndrama.com/shop_view/?idx=13211',
    'Cookie': 'al=KR'
}

# 初始化上一次的库存
prev_stock = None


# ================== Git 推送函数 ==================
def git_push_update():
    """
    将最新的 CSV 文件提交并推送到 GitHub
    """
    try:
        # 获取 GitHub Token（优先从环境变量读取）
        token = os.environ.get('GITHUB_TOKEN')
        if not token:
            print("⚠️ 环境变量 GITHUB_TOKEN 未设置，跳过 Git 推送")
            return

        # 构建带认证的远程仓库 URL
        remote_url = f"https://{token}@github.com/{GITHUB_REPO}.git"

        # 添加 CSV 文件到暂存区
        subprocess.run(['git', 'add', CSV_FILE], check=True, capture_output=True)

        # 检查是否有文件变化（避免空提交）
        result = subprocess.run(['git', 'diff', '--cached', '--quiet'], capture_output=True)
        if result.returncode != 0:
            # 有变化，提交
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            commit_msg = f"自动更新数据 {timestamp}"
            subprocess.run(['git', 'commit', '-m', commit_msg], check=True, capture_output=True)

            # 推送到 GitHub（指定分支）
            subprocess.run(
                ['git', 'push', remote_url, f'HEAD:{GITHUB_BRANCH}'],
                check=True,
                capture_output=True,
                text=True
            )
            print(f"✅ 已推送到 GitHub: {commit_msg}")
        else:
            print("⏭️ CSV 文件无变化，跳过推送")

    except subprocess.CalledProcessError as e:
        print(f"❌ Git 操作失败: {e.stderr if e.stderr else e}")
    except Exception as e:
        print(f"❌ 推送过程中发生错误: {e}")


def save_to_csv(data_rows):
    """
    将库存变化写入CSV文件（使用pandas concat方式），并触发Git推送
    data_rows: list of lists, 每行格式 [时间, 商品名称, 库存变化, 单笔销量]
    """
    try:
        # 定义完整的列名顺序
        columns = ['时间', '商品名称', '库存变化', '单笔销量']

        # 1. 如果文件存在，读取现有数据；否则创建空DataFrame
        if os.path.exists(CSV_FILE):
            df_existing = pd.read_csv(CSV_FILE, encoding='utf-8-sig')
            # 兼容旧数据：如果缺少'商品名称'列，则添加并用默认商品名称填充
            if '商品名称' not in df_existing.columns:
                df_existing.insert(1, '商品名称', PRODUCT_NAME)
        else:
            df_existing = pd.DataFrame(columns=columns)

        # 2. 将新数据行转换为DataFrame并拼接
        new_rows_df = pd.DataFrame(data_rows, columns=columns)
        df_updated = pd.concat([df_existing, new_rows_df], ignore_index=True)

        # 3. 保存回CSV（覆盖原文件），使用utf-8-sig编码
        df_updated.to_csv(CSV_FILE, index=False, encoding='utf-8-sig')

        # 4. 打印存储的内容（每条记录，包含商品名称）
        for item in data_rows:
            time_str, product_name, stock_change, single_sale = item
            print(f"{time_str} - 商品名称: {product_name}, 库存变化: {stock_change}, 单笔销量: {single_sale}")

        # 5. 触发Git推送
        git_push_update()

        return True
    except Exception as e:
        print(f"写入CSV文件失败: {e}")
        return False


while True:
    try:
        # 发送GET请求
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # 检查请求是否成功

        # 解析JSON响应
        data = response.json()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 提取当前库存，确保数据结构存在
        if 'data' in data and 'options_detail' in data['data'] and len(data['data']['options_detail']) > 0:
            current_stock = data['data']['options_detail'][0]['stock']

            # 首次运行记录初始库存
            if prev_stock is None:
                # 构建数据行，包含商品名称
                data_row = [[
                    current_time,
                    PRODUCT_NAME,
                    f"初始库存: {current_stock}",
                    0
                ]]
                save_to_csv(data_row)
                prev_stock = current_stock  # 更新prev_stock
            # 检测库存变化并记录
            elif current_stock != prev_stock:
                diff = prev_stock - current_stock
                # 构建数据行，包含商品名称
                data_row = [[
                    current_time,
                    PRODUCT_NAME,
                    f"{prev_stock} -> {current_stock}",
                    diff  # 非初始销量直接填差值（不加绝对值）
                ]]
                save_to_csv(data_row)
                prev_stock = current_stock  # 更新prev_stock
            # 如果库存未变化，不记录任何内容
        else:
            print("意外的JSON结构：options_detail 未找到或为空")

    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")

    except ValueError as e:
        print(f"JSON解析失败: {e}")

    except KeyError as e:
        print(f"键错误: {e}")

    # 每10秒检查一次
    time.sleep(10)