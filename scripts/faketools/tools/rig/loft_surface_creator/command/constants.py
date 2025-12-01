"""Constants for loft surface creation."""

# Curve parameters
MIN_POSITIONS_FOR_CURVE = 2
MIN_POSITIONS_FOR_CUBIC_CURVE = 3
CURVE_DEGREE = 3  # Always use cubic curves

# Minimum chains for closed loft
MIN_CHAINS_FOR_CLOSE = 3

# Output types
OUTPUT_NURBS_SURFACE = "nurbsSurface"
OUTPUT_MESH = "mesh"
VALID_OUTPUT_TYPES = [OUTPUT_NURBS_SURFACE, OUTPUT_MESH]

# Weight calculation methods
WEIGHT_METHOD_LINEAR = "linear"
WEIGHT_METHOD_EASE = "ease"
WEIGHT_METHOD_STEP = "step"
VALID_WEIGHT_METHODS = [WEIGHT_METHOD_LINEAR, WEIGHT_METHOD_EASE, WEIGHT_METHOD_STEP]
