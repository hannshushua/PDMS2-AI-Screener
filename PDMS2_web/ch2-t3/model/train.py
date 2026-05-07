import tensorflow as tf
from tensorflow.keras import layers, models
from tensorflow.keras.preprocessing.image import ImageDataGenerator
import matplotlib.pyplot as plt

# 1. 設定參數
IMG_SIZE = (224, 224)
BATCH_SIZE = 32
EPOCHS = 20
DATASET_PATH = 'dataset' # 請指向包含 test, train 等資料夾的目錄

# 2. 資料預處理 (Data Augmentation)
# 針對手繪圖，我們可以加入一點旋轉和縮放，增加模型魯棒性
train_datagen = ImageDataGenerator(
    rescale=1./255,
    rotation_range=20,
    width_shift_range=0.1,
    height_shift_range=0.1,
    zoom_range=0.1,
    horizontal_flip=True,
    validation_split=0.2 # 預留 20% 作為驗證集
)
TRAIN_DIR = 'dataset/train'
train_generator = train_datagen.flow_from_directory(
    TRAIN_DIR,
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode='categorical',
    subset='training'
)

VALID_DIR = 'dataset/valid'
val_generator = train_datagen.flow_from_directory(
    VALID_DIR,
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode='categorical',
    subset='validation'
)
print(train_generator.num_classes)

# 3. 建立純 CNN 模型架構
model = models.Sequential([
    # 第一層卷積：擷取基本線條特徵
    layers.Conv2D(32, (3, 3), activation='relu', input_shape=(224, 224, 3)),
    layers.MaxPooling2D((2, 2)),
    
    # 第二層卷積：組合線條成局部形狀
    layers.Conv2D(64, (3, 3), activation='relu'),
    layers.MaxPooling2D((2, 2)),
    
    # 第三層卷積：識別更複雜的幾何特徵
    layers.Conv2D(128, (3, 3), activation='relu'),
    layers.MaxPooling2D((2, 2)),
    
    # 平坦化與全連接層
    layers.Flatten(),
    layers.Dense(128, activation='relu'),
    layers.Dropout(0.5), # 防止過擬合
    layers.Dense(train_generator.num_classes, activation='softmax') 
])

# 4. 編譯模型
model.compile(
    optimizer='adam',
    loss='categorical_crossentropy',
    metrics=['accuracy']
)

model.summary()

print("Keras 識別出的類別標籤:", train_generator.class_indices)
# 5. 開始訓練
history = model.fit(
    train_generator,
    epochs=EPOCHS,
    validation_data=val_generator
)



# 6. 儲存模型
model.save('old_model.h5')
print("模型訓練完成並已儲存！")