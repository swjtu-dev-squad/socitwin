import os

# 基础路径配置
DB_PATH = r"e:\MyProject\公司的工作\人工智能\Mission\socitwin\topic_polarization\oasis_datasets.db"#一定得是文件本身的位置
OUTPUT_DIR = r"e:\MyProject\公司的工作\人工智能\Mission\socitwin\topic_polarization\Output"
OUTPUT_HTML = os.path.join(OUTPUT_DIR, "topic_polarization_chart.html")

# 确保输出目录存在
os.makedirs(OUTPUT_DIR, exist_ok=True)