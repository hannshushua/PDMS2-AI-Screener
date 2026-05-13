from math import hypot
class CheckGap:
    def __init__(self, gap_threshold=50):
        self.gap_threshold = gap_threshold

    def check(self, layers):
        gap_pairs = []

        # 遍歷已經分好的每一層
        for layer in layers:
            # 如果該層只有一塊積木，不可能有縫隙
            if len(layer) < 2:
                continue
                
            # 將該層積木依照 X 座標由左至右排序
            sorted_layer = sorted(layer, key=lambda p: p[0])
            
            # 檢查相鄰兩塊積木的距離
            for i in range(len(sorted_layer) - 1):
                p1 = sorted_layer[i]
                p2 = sorted_layer[i+1]
                
                dist = abs(p2[0] - p1[0])
                if dist > self.gap_threshold:
                    # 為了符合你原本 main.py 畫線雙向的邏輯 (len(gap_pairs) // 2)
                    # 這裡加入雙向 pair
                    gap_pairs.append((p1, p2, dist))
                    gap_pairs.append((p2, p1, dist))

        return gap_pairs