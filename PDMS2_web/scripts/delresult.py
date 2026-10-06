import os

# 設定父目錄與子目錄名稱
parent_dir = 'kid'
sub_folders = ['test1', 'test2', 'test3', 'test4', 'test5']

# 圖片副檔名清單
img_exts = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')

def clean_kid_results():
    deleted_count = 0
    
    for folder in sub_folders:
        # 組合出路徑，例如：kid/test1
        target_path = os.path.join(parent_dir, folder)
        
        if os.path.isdir(target_path):
            print(f"檢查目錄：{target_path}")
            
            for filename in os.listdir(target_path):
                # 檢查檔名包含 "result" 且為圖片格式
                if "result" in filename.lower() and filename.lower().endswith(img_exts):
                    file_to_delete = os.path.join(target_path, filename)
                    
                    try:
                        os.remove(file_to_delete)
                        print(f"已刪除：{filename}")
                        deleted_count += 1
                    except Exception as e:
                        print(f"無法刪除 {filename}: {e}")
        else:
            print(f"找不到資料夾：{target_path}")

    print(f"\n清理完畢！共刪除了 {deleted_count} 張圖片。")

if __name__ == "__main__":
    clean_kid_results()