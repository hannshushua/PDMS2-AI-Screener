import tensorflow as tf
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from sklearn.metrics import classification_report, confusion_matrix
import numpy as np

# 1. 設定參數
img_height, img_width = 224, 224 # 請根據你模型當初訓練的尺寸修改
batch_size = 32
test_data_dir = 'dataset/test' # 指向包含類別資料夾的母目錄

# 2. 載入模型
model = load_model('old_model.h5')
print("模型載入成功！")

# 3. 準備測試資料集 (Data Generator)
# 注意：如果你的模型訓練時有做 rescale (例如 /255)，這裡也要加上
test_datagen = ImageDataGenerator(rescale=1./255)

test_generator = test_datagen.flow_from_directory(
    test_data_dir,
    target_size=(img_height, img_width),
    batch_size=batch_size,
    class_mode='categorical', # 如果是二分類也可以用 'binary'
    shuffle=False             # 評估時絕對不能打亂順序，否則 Label 會對不上
)

# 4. 進行預測
print("正在進行預測...")
predictions = model.predict(test_generator)
y_pred = np.argmax(predictions, axis=1) # 取得預測類別索引
y_true = test_generator.classes          # 取得真實類別索引
class_labels = list(test_generator.class_indices.keys()) # 取得類別名稱

# 5. 輸出評估資訊 (包含 F1-score)
print("\n--- 模型評估報告 (Classification Report) ---")
print(classification_report(y_true, y_pred, target_names=class_labels))

# 6. (選配) 混淆矩陣
print("\n--- 混淆矩陣 (Confusion Matrix) ---")
print(confusion_matrix(y_true, y_pred))