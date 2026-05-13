from math import hypot

class CheckGap:
    def __init__(self, gap_threshold=50, y_layer_threshold=30):
        self.gap_threshold = gap_threshold
        self.y_layer_threshold = y_layer_threshold

    def check(self, centroids):
        gap_pairs = []

        for i, (cx, cy) in enumerate(centroids):
            left_neighbor = None
            right_neighbor = None
            min_left_dx = float('inf')
            min_right_dx = float('inf')

            for j, (nx, ny) in enumerate(centroids):
                if i == j:
                    continue
                if abs(ny - cy) > self.y_layer_threshold:
                    continue  # 過濾非同層

                dx = nx - cx
                if dx < 0 and abs(dx) < min_left_dx:
                    min_left_dx = abs(dx)
                    left_neighbor = (nx, ny)
                elif dx > 0 and abs(dx) < min_right_dx:
                    min_right_dx = abs(dx)
                    right_neighbor = (nx, ny)

            if left_neighbor:
                dist = abs(cx - left_neighbor[0])
                if dist > self.gap_threshold:
                    gap_pairs.append(((cx, cy), left_neighbor, dist))

            if right_neighbor:
                dist = abs(cx - right_neighbor[0])
                if dist > self.gap_threshold:
                    gap_pairs.append(((cx, cy), right_neighbor, dist))
        
        return gap_pairs
