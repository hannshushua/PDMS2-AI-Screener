import numpy as np

class LayerGrouping:
    def __init__(self, layer_ratio):
        """
        layer_ratio: 用於判斷是否為同一層的比例，相對於積木高度
        例如：0.8 表示如果兩個積木的Y座標差距小於積木高度的80%，就認為是同一層
        """
        self.layer_ratio = layer_ratio

    def group_by_y(self, centroids, boxes=None, block_height=None):
        """
        根據Y座標將積木分層
        
        參數:
        - centroids: 積木中心點列表 [(x1,y1), (x2,y2), ...]
        - boxes: YOLO檢測框列表 [(x1,y1,x2,y2), ...] (可選)
        - block_height: 手動指定積木高度 (可選)
        
        返回:
        - layers: 分層結果 [[(x1,y1), (x2,y2)], [...], ...]
        """
        if not centroids:
            return []
        
        # 計算layer_threshold
        if block_height is not None:
            # 使用手動指定的積木高度
            layer_threshold = block_height * self.layer_ratio
        elif boxes is not None and len(boxes) > 0:
            # 使用檢測框計算平均積木高度
            heights = [box[3] - box[1] for box in boxes]  # y2 - y1
            avg_height = np.mean(heights)
            layer_threshold = avg_height * self.layer_ratio
        else:
            # 預設值（向後兼容）
            layer_threshold = 30
            print("警告: 未提供積木尺寸資訊，使用預設threshold=30")
        
        # 按Y座標排序（由上到下）
        sorted_points = sorted(centroids, key=lambda p: p[1])
        
        layers = []
        for cx, cy in sorted_points:
            placed = False
            
            # 檢查是否可以加入現有層
            for layer in layers:
                # 計算與該層中心Y座標的平均值
                layer_avg_y = np.mean([point[1] for point in layer])
                
                if abs(layer_avg_y - cy) < layer_threshold:
                    layer.append((cx, cy))
                    placed = True
                    break
            
            # 如果無法加入現有層，創建新層
            if not placed:
                layers.append([(cx, cy)])
        
        # 按Y座標排序層級（從上到下）
        layers.sort(key=lambda layer: np.mean([point[1] for point in layer]))
        print(f'分成 {len(layers)} 層')
        return layers
