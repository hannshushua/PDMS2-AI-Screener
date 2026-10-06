class CheckGap:
    def __init__(self, gap_ratio=0.25):
        """
        gap_ratio: 允許的縫隙寬度，相對於積木寬度的比例。
        例如 0.25 表示相鄰兩塊積木的空隙要超過積木寬度的 25% 才算「有縫隙」。
        數值越大越不敏感。
        """
        self.gap_ratio = gap_ratio

    def check(self, layers, block_width):
        gap_pairs = []

        if not block_width or block_width <= 0:
            return gap_pairs

        gap_threshold = self.gap_ratio * block_width

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

                # 中心點距離要扣掉一個積木寬度，才是真正的縫隙寬度
                # (兩塊緊貼時中心距 ≈ 積木寬，縫隙 ≈ 0)
                gap = abs(p2[0] - p1[0]) - block_width
                if gap > gap_threshold:
                    # 為了符合你原本 main.py 畫線雙向的邏輯 (len(gap_pairs) // 2)
                    # 這裡加入雙向 pair
                    gap_pairs.append((p1, p2, gap))
                    gap_pairs.append((p2, p1, gap))

        return gap_pairs
