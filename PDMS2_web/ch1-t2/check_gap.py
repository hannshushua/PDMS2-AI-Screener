import numpy as np


def mask_gap(left_mask, right_mask):
    """兩個遮罩的實際水平縫隙 (px)：在兩塊都有的列上，量左塊最右邊到右塊最左邊的距離，取中位數。
    沒有重疊的列就用整體左右邊界。比中心距 - 積木寬準，不會因為兩塊積木寬度不同而高估 / 低估。"""
    rows_l = left_mask.any(axis=1)
    rows_r = right_mask.any(axis=1)
    rows = np.nonzero(rows_l & rows_r)[0]
    if len(rows) == 0:
        xl = np.nonzero(left_mask.any(axis=0))[0]
        xr = np.nonzero(right_mask.any(axis=0))[0]
        return float(xr.min() - xl.max() - 1)
    gaps = []
    for y in rows:
        gaps.append(np.nonzero(right_mask[y])[0].min() - np.nonzero(left_mask[y])[0].max() - 1)
    return float(np.median(gaps))


class CheckGap:
    def __init__(self, gap_ratio=0.25):
        """
        gap_ratio: 允許的縫隙寬度，相對於積木寬度的比例。
        例如 0.25 表示相鄰兩塊積木的空隙要超過積木寬度的 25% 才算「有縫隙」。
        數值越大越不敏感。
        """
        self.gap_ratio = gap_ratio

    def check(self, layers, block_width, masks=None):
        """masks: {中心點: 遮罩}，有給就用遮罩邊緣量真正的縫隙，沒給就用中心距 - 積木寬"""
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
                if masks is not None and p1 in masks and p2 in masks:
                    gap = mask_gap(masks[p1], masks[p2])
                else:
                    gap = abs(p2[0] - p1[0]) - block_width
                if gap > gap_threshold:
                    # 為了符合你原本 main.py 畫線雙向的邏輯 (len(gap_pairs) // 2)
                    # 這裡加入雙向 pair
                    gap_pairs.append((p1, p2, gap))
                    gap_pairs.append((p2, p1, gap))

        return gap_pairs
