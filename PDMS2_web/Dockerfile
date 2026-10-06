# 1. 使用官方的 Python 3.9 作為基礎環境
FROM python:3.9-slim

# 2. 設定容器內的工作目錄
WORKDIR /app

# 3. 先把套件清單複製進去
COPY requirements.txt .

# 4. 安裝所需的 Python 套件
# (加入 --no-cache-dir 可以讓打包出來的檔案小一點)
RUN pip install --no-cache-dir -r requirements.txt

# 5. 把專案所有的程式碼複製進容器
COPY . .