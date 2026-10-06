import numpy as np
from LayerGrouping import LayerGrouping

class StairChecker:
    @staticmethod
    def is_stair_shape(layers):
        if len(layers) != 3:
            return False
        sizes = [len(layer) for layer in layers]
        return sizes == [1, 2, 3]

    @staticmethod
    def is_left_stair(layers):
        xs = [np.mean([p[0] for p in layer]) for layer in layers]
        return xs[0] < xs[1] < xs[2]

    @staticmethod
    def is_right_stair(layers):
        xs = [np.mean([p[0] for p in layer]) for layer in layers]
        return xs[0] > xs[1] > xs[2]

    def check(self, layers):
        
        print(len(layers))

        if not self.is_stair_shape(layers):
            return False, "Not stair shape"

        if self.is_left_stair(layers):
            return True, "Left Stair"
        elif self.is_right_stair(layers):
            return True, "Right Stair"
        else:
            return False, "Incorrect X alignment"
