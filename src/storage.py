import csv
import os
async def storage(data):
    # 正确调用异步函数

    os.makedirs("../fang_data",exist_ok=True)  # 创建文件存放目录
    fang_data = os.path.join("../fang_data",f"fang_data.csv")
    # 保存到CSV
    if data:
        with open(fang_data,'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['标题','价格','描述'])  # 表头

            count = 0
            for idx, book in enumerate(data):
                if book is None:
                    print(f"[警告] 第 {idx} 条数据为空，跳过")
                    continue
                try:
                    writer.writerow([book.get('title',''), book.get('price',''), book.get('description','')])
                    count += 1
                except Exception as e:
                    print(f"[错误] 第 {idx} 条数据写入失败: {e}")

        print(f"成功保存 {count} 条数据到 fang_data.csv")



