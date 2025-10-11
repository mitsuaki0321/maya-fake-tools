"""
Keyframe functions.
"""

from dataclasses import dataclass, fields
from logging import getLogger

import maya.cmds as cmds

logger = getLogger(__name__)


TANGENT_TYPES = [
    "spline",
    "linear",
    "fast",
    "slow",
    "flat",
    "step",
    "stepnext",
    "fixed",
    "clamped",
    "plateau",
    "auto",
    "autoease",
    "automix",
    "autocustom",
]


class InfinityType:
    """Infinity type class."""

    _infinity_types = ("Constant", "Linear", "Constant", "Cycle", "Cycle Relative", "Oscillate")

    def __init__(self, anim_curve: str):
        """Initialize the infinity type object.

        Args:
            anim_curve (str): The animation curve node.
        """
        if not anim_curve:
            raise ValueError("Invalid animation curve")

        if not cmds.objExists(anim_curve):
            raise ValueError(f"Invalid animation curve. Not exists: {anim_curve}")

        if "animCurve" not in cmds.nodeType(anim_curve, inherited=True):
            raise ValueError(f"Invalid animation curve node: {anim_curve}")

        self.anim_curve = anim_curve

    @classmethod
    def list_infinity_types(cls) -> list[str]:
        """List the infinity types.

        Returns:
            list[str]: The infinity types.
        """
        return cls._infinity_types

    @property
    def infinity_types(self) -> list[str]:
        """Get the infinity types.

        Returns:
            list[str]: The infinity types.
        """
        return self._infinity_types

    def get_pre_infinity(self) -> str:
        """Get the pre infinity type.

        Returns:
            str: The pre infinity type.
        """
        return cmds.getAttr(f"{self.anim_curve}.preInfinity", asString=True)

    def set_pre_infinity(self, infinity_type: str):
        """Set the pre infinity type.

        Args:
            infinity_type (str): The pre infinity type.
        """
        if infinity_type not in self._infinity_types:
            raise ValueError(f"Invalid pre infinity type: {infinity_type}")

        cmds.setAttr(f"{self.anim_curve}.preInfinity", self._infinity_types.index(infinity_type))

    def get_post_infinity(self) -> str:
        """Get the post infinity type.

        Returns:
            str: The post infinity type.
        """
        return cmds.getAttr(f"{self.anim_curve}.postInfinity", asString=True)

    def set_post_infinity(self, infinity_type: str):
        """Set the post infinity type.

        Args:
            infinity_type (str): The post infinity type.
        """
        if infinity_type not in self._infinity_types:
            raise ValueError(f"Invalid post infinity type: {infinity_type}")

        cmds.setAttr(f"{self.anim_curve}.postInfinity", self._infinity_types.index(infinity_type))


@dataclass
class KeyframeData:
    """Keyframe data class.

    Args:
        x_value (float): The time or attribute float.
        y_value (float): The value.
        in_tangent_type (str): The in tangent type.
        out_tangent_type (str): The out tangent type.
        in_weight (float): The in tangent weight.
        out_weight (float): The out tangent weight.
        in_angle (float): The in tangent angle.
        out_angle (float): The out tangent angle.
    """

    x_value: float
    y_value: float
    in_tangent_type: str = "auto"
    out_tangent_type: str = "auto"
    in_weight: float = 1.0
    out_weight: float = 1.0
    in_angle: float = 0.0
    out_angle: float = 0.0
    lock: bool = False

    def __post_init__(self):
        if self.in_tangent_type not in TANGENT_TYPES:
            raise ValueError(f"Invalid in_tangent_type: {self.in_tangent_type}")
        if self.out_tangent_type not in TANGENT_TYPES:
            raise ValueError(f"Invalid out_tangent_type: {self.out_tangent_type}")


class TimeKeyframe:
    """Time keyframe class."""

    def __init__(self, plug: str):
        """Initialize the keyframe object.

        Args:
            plug (str): The target plug name.
        """
        if not plug:
            raise ValueError("Invalid plug name")

        if not cmds.objExists(plug):
            raise ValueError(f"Invalid plug. Not exists: {plug}")

        self.plug = plug

    def get_times(self) -> list[float]:
        """Get the keyframe times.

        Notes:
            cmds.keyframe(plug, query=True, timeChange=True) returns the time values.

        Returns:
            list[float]: The time values.
        """
        return cmds.keyframe(self.plug, query=True, timeChange=True) or []

    def find_anim_curve(self) -> str | None:
        """Find the animation curve node.

        Returns:
            Optional[str]: The animation curve node. None if not found.
        """
        source_plugs = cmds.listConnections(self.plug, s=True, d=False, p=True, type="animCurve")
        if not source_plugs:
            logger.warning(f"Failed to find input plug: {self.plug}")
            return None

        if cmds.nodeType(source_plugs[0]) in ["animCurveTL", "animCurveTA", "animCurveTU", "animCurveTT"]:
            return source_plugs[0]

        logger.warning(f"Found input plug is not animation curve: {self.plug}")

    def get_keyframe(self, x_value: float) -> KeyframeData:
        """Get the keyframe data at the given time.

        Args:
            x_value (float): The time value.

        Returns:
            KeyframeData: The keyframe data.
        """
        times = self.get_times()
        if not times:
            raise ValueError(f"Failed to get keyframe cause no animation curve found: {self.plug}")

        if x_value not in times:
            raise ValueError(f"Failed to get keyframe cause no keyframe found at time: {x_value}")

        value = cmds.getAttr(self.plug, time=x_value)
        in_tangent_type = cmds.keyTangent(self.plug, time=(x_value, x_value), query=True, inTangentType=True)[0]
        out_tangent_type = cmds.keyTangent(self.plug, time=(x_value, x_value), query=True, outTangentType=True)[0]
        in_weight = cmds.keyTangent(self.plug, time=(x_value, x_value), query=True, inWeight=True)[0]
        out_weight = cmds.keyTangent(self.plug, time=(x_value, x_value), query=True, outWeight=True)[0]
        in_angle = cmds.keyTangent(self.plug, time=(x_value, x_value), query=True, inAngle=True)[0]
        out_angle = cmds.keyTangent(self.plug, time=(x_value, x_value), query=True, outAngle=True)[0]
        lock = cmds.keyTangent(self.plug, time=(x_value, x_value), query=True, lock=True)[0]

        return KeyframeData(
            x_value=x_value,
            y_value=value,
            in_tangent_type=in_tangent_type,
            out_tangent_type=out_tangent_type,
            in_weight=in_weight,
            out_weight=out_weight,
            in_angle=in_angle,
            out_angle=out_angle,
            lock=lock,
        )

    def set_keyframe(self, keyframe: KeyframeData):
        """Set the keyframe data.

        Args:
            keyframe (KeyframeData): The keyframe data.
        """
        cmds.setKeyframe(self.plug, time=keyframe.x_value, value=keyframe.y_value)

        cmds.keyTangent(
            self.plug,
            time=(keyframe.x_value, keyframe.x_value),
            inTangentType=keyframe.in_tangent_type,
            outTangentType=keyframe.out_tangent_type,
            inWeight=keyframe.in_weight,
            outWeight=keyframe.out_weight,
            inAngle=keyframe.in_angle,
            outAngle=keyframe.out_angle,
            weightLock=keyframe.lock,
        )

        logger.debug(f"Set keyframe: {self.plug} >> {keyframe.x_value} {keyframe.y_value}")

    def remove_keyframe(self, x_value: float):
        """Remove the keyframe at the given time.

        Args:
            x_value (float): The time value.
        """
        cmds.cutKey(self.plug, time=(x_value, x_value), clear=True)

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.plug}')"

    def __str__(self):
        return f"{self.plug}"


class AttributeKeyframe:
    """Attribute keyframe class."""

    def __init__(self, plug: str):
        """Initialize the keyframe object.

        Args:
            plug (str): The target plug name.
        """
        if not plug:
            raise ValueError("Invalid plug name")

        if not cmds.objExists(plug):
            raise ValueError(f"Invalid plug. Not exists: {plug}")

        self.plug = plug

    def get_driver_values(self, driver_plug: str) -> list[float]:
        """Get the driver values.

        Notes:
            cmds.keyframe(anim_curve, query=True, floatChange=True) returns the driver values.

        Args:
            driver_plug (str): The driver plug.

        Returns:
            list[float]: The driver values.
        """
        anim_curve = self.find_anim_curve(driver_plug)
        if not anim_curve:
            raise ValueError(f"Failed to get attribute driver values: {self.plug}")

        return cmds.keyframe(anim_curve, query=True, floatChange=True) or []

    def find_anim_curve(self, driver_plug: str) -> str | None:
        """Find the animation curve node.

        Args:
            driver_plug (str): The driver plug.

        Returns:
            Optional[str]: The animation curve node. None if not found target animCurve node.
        """
        source_plugs = cmds.listConnections(self.plug, s=True, d=False, p=True)
        if not source_plugs:
            logger.warning(f"Failed to find input plug: {self.plug}")
            return None

        source_node = cmds.ls(source_plugs[0], objectsOnly=True)[0]
        anim_curves = []

        def _find_anim_curve(node):
            """Find the animation curve node."""
            if cmds.nodeType(node) in ["animCurveUU", "animCurveUL", "animCurveUA", "animCurveUT"]:
                anim_curves.append(node)

            elif cmds.nodeType(node) == "blendWeighted":
                bw_source_nodes = cmds.listConnections(node, s=True, d=False)
                for bw_source_node in bw_source_nodes:
                    _find_anim_curve(bw_source_node)

        _find_anim_curve(source_node)
        if not anim_curves:
            logger.warning(f"Failed to find animation curve: {self.plug}")
            return None

        driver_plug = cmds.ls(driver_plug)[0]  # Name rearrange
        for anim_curve in anim_curves:
            source_plug = cmds.listConnections(anim_curve, s=True, d=False, p=True, scn=True)
            if source_plug and source_plug[0] == driver_plug:
                return anim_curve

        return None

    def get_keyframe(self, x_value: float, driver_plug: str) -> KeyframeData:
        """Get the keyframe data at the given time.

        Args:
            x_value (float): The attribute value.
            driver_plug (str): The driver plug.

        Returns:
            KeyframeData: The keyframe data.
        """
        anim_curve = self.find_anim_curve(driver_plug)
        if not anim_curve:
            raise ValueError(f"Failed to get keyframe cause no target animation curve found: {self.plug}")

        x_values = self.get_driver_values(driver_plug)
        if x_value not in x_values:
            raise ValueError(f"Failed to get keyframe cause no keyframe found at time: {x_value}")

        value = cmds.keyframe(anim_curve, query=True, valueChange=True, float=(x_value, x_value))[0]
        in_tangent_type = cmds.keyTangent(anim_curve, float=(x_value, x_value), query=True, inTangentType=True)[0]
        out_tangent_type = cmds.keyTangent(anim_curve, float=(x_value, x_value), query=True, outTangentType=True)[0]
        in_weight = cmds.keyTangent(anim_curve, float=(x_value, x_value), query=True, inWeight=True)[0]
        out_weight = cmds.keyTangent(anim_curve, float=(x_value, x_value), query=True, outWeight=True)[0]
        in_angle = cmds.keyTangent(anim_curve, float=(x_value, x_value), query=True, inAngle=True)[0]
        out_angle = cmds.keyTangent(anim_curve, float=(x_value, x_value), query=True, outAngle=True)[0]
        lock = cmds.keyTangent(anim_curve, float=(x_value, x_value), query=True, lock=True)[0]

        return KeyframeData(
            x_value=x_value,
            y_value=value,
            in_tangent_type=in_tangent_type,
            out_tangent_type=out_tangent_type,
            in_weight=in_weight,
            out_weight=out_weight,
            in_angle=in_angle,
            out_angle=out_angle,
            lock=lock,
        )

    def set_keyframe(self, keyframe: KeyframeData, driver_plug: str):
        """Set the keyframe data.

        Args:
            keyframe (KeyframeData): The keyframe data.
        """
        if not isinstance(keyframe, KeyframeData):
            raise ValueError("Invalid keyframe data")

        cmds.setDrivenKeyframe(self.plug, currentDriver=driver_plug, driverValue=keyframe.x_value, value=keyframe.y_value)

        anim_curve = self.find_anim_curve(driver_plug)

        cmds.keyTangent(
            anim_curve,
            float=(keyframe.x_value, keyframe.x_value),
            inTangentType=keyframe.in_tangent_type,
            outTangentType=keyframe.out_tangent_type,
            inWeight=keyframe.in_weight,
            outWeight=keyframe.out_weight,
            inAngle=keyframe.in_angle,
            outAngle=keyframe.out_angle,
            lock=keyframe.lock,
        )

        logger.debug(f"Set driven keyframe: {self.plug} >> {keyframe.x_value} {keyframe.y_value}")

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.plug}')"

    def __str__(self):
        return self.plug


@dataclass
class AnimCurveData:
    """Animation curve data class.

    Args:
        pre_infinity (str): The pre infinity type.
        post_infinity (str): The post infinity type.
        keyframes (list[KeyframeData]): The list of keyframe data.
    """

    keyframes: list[KeyframeData]
    weighted_tangents: bool = False
    pre_infinity: str = "Constant"
    post_infinity: str = "Constant"

    def __post_init__(self):
        if self.pre_infinity not in InfinityType.list_infinity_types():
            raise ValueError(f"Invalid pre_infinity: {self.pre_infinity}")

        if self.post_infinity not in InfinityType.list_infinity_types():
            raise ValueError(f"Invalid post_infinity: {self.post_infinity}")

    @classmethod
    def from_dict(cls, data: dict):
        """Set the data from dictionary.

        Args:
            data (dict): The dictionary data.

        Returns:
            AnimCurveData: The animation curve data.
        """
        field_names = [field.name for field in fields(cls)]
        init_data = {}

        for key, value in data.items():
            if key in field_names:
                if key in ["keyframes"]:
                    keyframes = []
                    for keyframe in value:
                        keyframes.append(KeyframeData(**keyframe))
                    init_data[key] = keyframes
                else:
                    init_data[key] = value

        return cls(**init_data)


@dataclass
class SetDrivenKeyData:
    """Set driven key data class.

    Args:
        driven_plug (str): The driven plug.
        driver_plug (str): The driver plug.
        keyframes (list[KeyframeData]): The keyframe data.
    """

    anim_curve_data: AnimCurveData
    driven_plug: str
    driver_plug: str


class TimeAnimCurve:
    """Time animation curve class."""

    def __init__(self, plug: str):
        """Initialize the animation curve object.

        Args:
            plug (str): The target plug name.
        """
        if not plug:
            raise ValueError("Invalid plug name")

        if not cmds.objExists(plug):
            raise ValueError(f"Invalid plug. Not exists: {plug}")

        self.plug = plug

    def get_anim_curves(self) -> list[str]:
        """Get the animation curve node.

        Returns:
            list[str]: The animation curve node.
        """
        # TODO: Consider connections with pairBlend node when necessary.
        return cmds.listConnections(self.plug, s=True, d=False, type="animCurve") or []

    def get_keyframes(self) -> AnimCurveData:
        """Get the keyframe data.

        Returns:
            AnimCurve: The animation curve data.
        """
        keyframe = TimeKeyframe(self.plug)
        anim_curve = keyframe.find_anim_curve()
        if not anim_curve:
            raise ValueError(f"Failed to get keyframes cause no animation curve found: {self.plug}")

        times = keyframe.get_times()
        keyframe_datas = []
        for time in times:
            keyframe_data = keyframe.get_keyframe(time)
            keyframe_datas.append(keyframe_data)

        anim_curve = keyframe.find_anim_curve()
        weighted_tangents = cmds.keyTangent(anim_curve, query=True, weightedTangents=True)[0]
        infinity = InfinityType(anim_curve)

        return AnimCurveData(
            keyframes=keyframe_datas,
            weighted_tangents=weighted_tangents,
            pre_infinity=infinity.get_pre_infinity(),
            post_infinity=infinity.get_post_infinity(),
        )

    def set_keyframes(self, anim_curve_data: AnimCurveData):
        """Set the keyframe data.

        Args:
            anim_curve (AnimCurve): The animation curve data.
        """
        keyframe = TimeKeyframe(self.plug)
        for keyframe_data in anim_curve_data.keyframes:
            keyframe.set_keyframe(keyframe_data)

        anim_curve = keyframe.find_anim_curve()
        cmds.keyTangent(anim_curve, e=True, weightedTangents=anim_curve_data.weighted_tangents)
        infinity = InfinityType(anim_curve)
        infinity.set_pre_infinity(anim_curve_data.pre_infinity)
        infinity.set_post_infinity(anim_curve_data.post_infinity)

        logger.debug(f"Set keyframes: {self.plug}")

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.plug}')"

    def __str__(self):
        return f"{self.plug}"


class AttributeAnimCurve:
    """Attribute animation curve class."""

    def __init__(self, driven_plug: str):
        """Initialize the animation curve object.

        Args:
            driven_plug (str): The driven plug name.
        """
        if not driven_plug:
            raise ValueError("Invalid driven plug name")

        if not cmds.objExists(driven_plug):
            raise ValueError(f"Invalid driven plug. Not exists: {driven_plug}")

        self.driven_plug = driven_plug

    def get_anim_curves(self) -> list[str]:
        """Get driven animation curve nodes.

        Returns:
            list[str]: The driven animation curve nodes.
        """
        driver_plugs = cmds.setDrivenKeyframe(self.driven_plug, q=True, driver=True)
        if not driver_plugs:
            logger.debug(f"No driven keys found: {self.driven_plug}")
            return []

        attribute_keyframe = AttributeKeyframe(plug=self.driven_plug)

        anim_curves = []
        for driver_plug in driver_plugs:
            anim_curve = attribute_keyframe.find_anim_curve(driver_plug)
            if anim_curve:
                anim_curves.append(anim_curve)

        if not anim_curves:
            logger.debug(f"No driven animation curves found: {self.driven_plug}")

        return anim_curves

    def get_keyframes(self, driver_plug: str) -> AnimCurveData:
        """Get the keyframe data.

        Args:
            driver_plug (str): The driver plug.

        Returns:
            AnimCurve: The animation curve data.
        """
        keyframe = AttributeKeyframe(self.driven_plug)
        anim_curve = keyframe.find_anim_curve(driver_plug)
        if not anim_curve:
            raise ValueError(f"Failed to get keyframes cause no animation curve found: {self.driven_plug}")

        driver_values = keyframe.get_driver_values(driver_plug)
        keyframe_datas = []
        for driver_value in driver_values:
            keyframe_data = keyframe.get_keyframe(driver_value, driver_plug)
            keyframe_datas.append(keyframe_data)

        anim_curve = keyframe.find_anim_curve(driver_plug)
        weighted_tangents = cmds.keyTangent(anim_curve, query=True, weightedTangents=True)[0]
        infinity = InfinityType(anim_curve)

        return AnimCurveData(
            keyframes=keyframe_datas,
            weighted_tangents=weighted_tangents,
            pre_infinity=infinity.get_pre_infinity(),
            post_infinity=infinity.get_post_infinity(),
        )

    def set_keyframes(self, anim_curve_data: AnimCurveData, driver_plug: str):
        """Set the keyframe data.

        Args:
            anim_curve (AnimCurve): The animation curve data.
            driver_plug (str): The driver plug.
        """
        if not isinstance(anim_curve_data, AnimCurveData):
            raise ValueError("Invalid anim_curve_data")

        keyframe = AttributeKeyframe(self.driven_plug)
        for keyframe_data in anim_curve_data.keyframes:
            keyframe.set_keyframe(keyframe=keyframe_data, driver_plug=driver_plug)

        anim_curve = keyframe.find_anim_curve(driver_plug)
        cmds.keyTangent(anim_curve, e=True, weightedTangents=anim_curve_data.weighted_tangents)
        infinity = InfinityType(anim_curve)
        infinity.set_pre_infinity(anim_curve_data.pre_infinity)
        infinity.set_post_infinity(anim_curve_data.post_infinity)

        logger.debug(f"Set keyframes: {self.driven_plug}")


def mirror_anim_curve(anim_curve: str, mirror_time: bool = False, mirror_value: bool = False) -> None:
    """Mirror the animation curve.

    Args:
        anim_curve (str): The animation curve node.
        mirror_time (bool): If True, mirror the time axis.
        mirror_value (bool): If True, mirror the value axis.
    """
    if not anim_curve:
        raise ValueError("Invalid animation curve")

    if not cmds.objExists(anim_curve):
        raise ValueError(f"Animation curve does not exists: {anim_curve}")

    if "animCurve" not in cmds.nodeType(anim_curve, inherited=True):
        raise ValueError(f"Invalid animation curve type: {anim_curve}")

    if not mirror_time and not mirror_value:
        cmds.warning("No options to mirror. Please set mirror axis options.")
        return

    if mirror_time:
        cmds.scaleKey(anim_curve, timeScale=-1, timePivot=0, floatScale=-1, floatPivot=0, valueScale=1, valuePivot=0)
        infinity = InfinityType(anim_curve)
        infinity.set_pre_infinity(infinity.get_post_infinity())
        infinity.set_post_infinity(infinity.get_pre_infinity())

    if mirror_value:
        cmds.scaleKey(anim_curve, timeScale=1, timePivot=0, floatScale=1, floatPivot=0, valueScale=-1, valuePivot=0)

    logger.debug(f"Mirrored animation curve: {anim_curve}")
