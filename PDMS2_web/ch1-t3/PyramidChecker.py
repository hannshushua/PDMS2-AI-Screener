import numpy as np
from LayerGrouping import LayerGrouping

class PyramidCheck:

    @staticmethod
    def is_pyramid_shape(layers, x_threshold):
        if len(layers) != 3:
            return False

        avg_xs = []
        for layer in layers:
            x_coords = [p[0] for p in layer if isinstance(p, (list, tuple)) and len(p) == 2]
            if not x_coords:
                return False  # 如果任何一層無法計算平均，視為不成立
            avg_x = int(np.mean(x_coords))
            avg_xs.append(avg_x)

        if len(layers[0]) != 1 or len(layers[1]) != 2 or len(layers[2]) != 3:
            return False
        
        #比較最下面那一層的平均x 和 中層 頂層的差距 在一定範圍內就是金字塔
        return (abs(avg_xs[0] - avg_xs[1]) <= x_threshold and abs(avg_xs[0] - avg_xs[2]) <= x_threshold)

    def check_pyramid(self, layers, block_width, gap):
        
        
        if len(layers) != 3:
            return False, "Not 3 layers"


        if self.is_pyramid_shape(layers, x_threshold=block_width) and gap:
            return True, "Pyramid shape!"
        else:
            return False, "Not pyramid"
