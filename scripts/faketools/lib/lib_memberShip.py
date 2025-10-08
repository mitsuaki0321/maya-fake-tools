"""Component membership functions."""

from logging import getLogger

import maya.cmds as cmds

logger = getLogger(__name__)


class ComponentTags:
    """Maya Component Tags class."""

    def __init__(self, shape: str, tag_name: str):
        """Initialize the class.

        Args:
            tag_name (str): The tag name.
            shape (str): The shape node.
        """
        if not tag_name:
            raise ValueError("No tag name specified")

        if not shape:
            raise ValueError("No shape specified")

        if not cmds.objExists(shape):
            raise ValueError(f"Node does not exist: {shape}")

        self.shape = shape
        self._name = tag_name

    @property
    def name(self) -> str:
        """Get the tag name.

        Returns:
            str: The tag name.
        """
        return self._name

    @property
    def num_components(self) -> int:
        """Get the number of components in the tag.

        Returns:
            int: The number of components.
        """
        shape_output = f"{self.shape}.{cmds.deformableShape(self.shape, localShapeOutAttr=True)[0]}"
        return cmds.geometryAttrInfo(shape_output, elementCount=True, componentTagExpression=self._name)

    @property
    def component_type(self) -> str:
        """Get the component type of the tag.

        Returns:
            str: The component type.
        """
        shape_output = f"{self.shape}.{cmds.deformableShape(self.shape, localShapeOutAttr=True)[0]}"
        return cmds.geometryAttrInfo(shape_output, componentTagCategory=True, componentTagExpression=self._name)

    @classmethod
    def exists(cls, shape: str, tag_name: str) -> bool:
        """Check if the tag exists.

        Args:
            tag_name(str): The tag name.
            shape(str): The shape node.

        Returns:
            bool: Whether the tag exists.
        """
        if not tag_name:
            raise ValueError("No tag name specified")

        if not shape:
            raise ValueError("No shape specified")

        if not cmds.objExists(shape):
            raise ValueError(f"Node does not exist: {shape}")

        shape_output = f"{shape}.{cmds.deformableShape(shape, localShapeOutAttr=True)[0]}"
        tags = cmds.geometryAttrInfo(shape_output, componentTagNames=True)
        return tag_name in tags

    @classmethod
    def create(cls, shape: str, tag_name: str) -> "ComponentTags":
        """Create a new tag.

        Args:
            tag_name(str): The tag name.
            shape(str): The shape node.

        Returns:
            ComponentTags: The new tag.
        """
        if not tag_name:
            raise ValueError("No tag name specified")

        if not shape:
            raise ValueError("No shape specified")

        if not cmds.objExists(shape):
            raise ValueError(f"Node does not exist: {shape}")

        edit_data = cmds.componentTag(shape, tagName=tag_name, queryEdit=True)
        if not edit_data["create"]:
            raise ValueError(f"Tag already exists: {tag_name}")

        tag_name = cmds.componentTag([f"{shape}.cp[*]"], newTagName=tag_name, create=True)

        logger.debug(f"Created tag: {tag_name}")

        return cls(shape, tag_name)

    def query(self) -> list[str]:
        """Query the tag components.

        Returns:
            list[str]: The tag components.
        """
        shape_output = f"{self.shape}.{cmds.deformableShape(self.shape, localShapeOutAttr=True)[0]}"
        components = cmds.geometryAttrInfo(shape_output, components=True, componentTagExpression=self._name)
        components = [f"{self.shape}.{comp}" for comp in components]

        return components

    def add(self, components: list[str]) -> bool:
        """Add components to the tag.

        Args:
            components(list[str]): The components to add.

        Returns:
            bool: Whether the components were added.
        """
        if not components:
            raise ValueError("No components specified")

        status = cmds.componentTag(components, tagName=self._name, modify="add")
        if not status:
            cmds.warning(f"Failed to add components to tag: {self._name}")
            return False

        logger.debug(f"Added components to tag: {self._name}")

        return True

    def replace(self, components: list[str]) -> bool:
        """Replace components in the tag.

        Args:
            components(list[str]): The components to replace.

        Returns:
            bool: Whether the components were replaced.
        """
        if not components:
            raise ValueError("No components specified")

        status = cmds.componentTag(components, tagName=self._name, modify="replace")
        if not status:
            cmds.warning(f"Failed to replace components in tag: {self._name}")
            return False

        logger.debug(f"Replaced components in tag: {self._name}")

        return True

    def remove(self, components: list[str]) -> bool:
        """Remove components from the tag.

        Args:
            components(list[str]): The components to remove.

        Returns:
            bool: Whether the components were removed.
        """
        if not components:
            raise ValueError("No components specified")

        status = cmds.componentTag(components, tagName=self._name, modify="remove")
        if not status:
            cmds.warning(f"Failed to remove components from tag: {self._name}")
            return False

        logger.debug(f"Removed components from tag: {self._name}")

        return True

    def clear(self) -> bool:
        """Clear the tag components.

        Returns:
            bool: Whether the tag was cleared.
        """
        status = cmds.componentTag(self.shape, tagName=self._name, modify="clear")
        if not status:
            cmds.warning(f"Failed to clear tag: {self._name}")
            return False

        logger.debug(f"Cleared tag: {self._name}")

        return True

    def rename(self, new_name: str) -> bool:
        """Rename the tag.

        Args:
            new_name(str): The new tag name.

        Returns:
            bool: Whether the tag was renamed.
        """
        if not new_name:
            raise ValueError("No new name specified")

        status = cmds.componentTag(self.shape, tagName=self._name, newTagName=new_name, rename=True)
        if not status:
            cmds.warning(f"Failed to rename tag: {self._name} -> {new_name}")
            return False

        self._name = new_name

        logger.debug(f"Renamed tag: {self._name}")

        return True

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self.shape}', '{self._name}')"

    def __str__(self) -> str:
        return f"{self._name}"


class DeformerMembership:
    """Deformer membership class."""

    def __init__(self, deformer: str):
        """Initialize the class.

        Args:
            deformer (str): The deformer node.
        """
        if not deformer:
            raise ValueError("No deformer specified")

        if not cmds.objExists(deformer):
            raise ValueError(f"Deformer node does not exist: {deformer}")

        if "geometryFilter" not in cmds.nodeType(deformer, inherited=True):
            raise ValueError(f"Node is not a geometryFilter node: {deformer}")

        if not is_use_component_tag():
            raise ValueError("Component tags are not enabled for maya preferences")

        self._deformer_name = deformer

    @property
    def deformer_name(self) -> str:
        """Get the deformer name.

        Returns:
            str: The deformer name.
        """
        return self._deformer_name

    @property
    def num_shapes(self) -> int:
        """Get the number of shapes bound to the deformer.

        Returns:
            int: The number of bound shapes.
        """
        return len(self.get_shapes())

    def get_shapes(self) -> list[str]:
        """Get the shapes bound to the deformer.

        Returns:
            list[str]: The bound shapes.
        """
        return cmds.deformer(self._deformer_name, q=True, geometry=True)

    def get_shape_indices(self) -> list[int]:
        """Get the shape indices bound to the deformer.

        Returns:
            list[int]: The deformer input indices.
        """
        return cmds.deformer(self._deformer_name, q=True, geometryIndices=True)

    def get_all_indices(self) -> list[int]:
        """Get the shape all indices bound to the deformer.

        Returns:
            list[int]: The deformer input indices.
        """
        return cmds.getAttr(f"{self._deformer_name}.input", multiIndices=True)

    def get_components(self) -> list[str]:
        """Get the all components bound to the deformer.

        Args:
            index(int): The shape physical index.

        Returns:
            list[str]: The bound components.
        """
        return cmds.deformer(self._deformer_name, q=True, components=True)

    def get_shape_components(self, index: int = 0) -> list[str]:
        """Get the shape components bound to the deformer.

        Args:
            index(int): The shape physical index.

        Returns:
            list[str]: The bound components.
        """
        if not index:
            ValueError("No index specified")

        if index >= self.num_shapes:
            raise ValueError("Physical Index exceeds the number of shapes")

        shape = self.get_shapes()[index]
        shape_transform = cmds.listRelatives(shape, parent=True, path=True)[0]
        components = cmds.deformer(self._deformer_name, q=True, components=True)

        return [c for c in components if c.startswith(shape_transform)]

    def update_components(self, components: list[str]) -> bool:
        """Update the components bound to the deformer.

        Args:
            components(list[str]): The components to add.

        Returns:
            bool: Whether the components were added.
        """
        if not components:
            raise ValueError("No components specified")

        # Get the update components.
        components = cmds.filterExpand(components, sm=(28, 31, 46), expand=True)  # vertex, cv, lattice point
        if not components:
            cmds.warning("No valid components specified")
            return False

        logger.debug(f"Filter expanded components: {components}")

        # Group the components by shape.
        component_data = {}
        for component in components:
            shape = cmds.ls(component, objectsOnly=True)[0]
            component_data.setdefault(shape, []).append(component)

        logger.debug(f"Component data: {component_data}")

        # Add the new shapes.
        current_shapes = self.get_shapes()
        for shape in component_data:
            if shape not in current_shapes:
                self.add_shape(shape)

        # Update the components.
        current_shapes = self.get_shapes()
        shape_indices = self.get_shape_indices()
        for shape, components in component_data.items():
            num_shape_components = len(cmds.ls(f"{shape}.cp[*]", flatten=True))
            if num_shape_components == len(components):
                expression = "*"
            else:
                expression = self._deformer_name
                if not ComponentTags.exists(shape, expression):
                    component_tag = ComponentTags.create(shape, expression)
                else:
                    component_tag = ComponentTags(shape, expression)

                component_tag.replace(components)

            self.set_tag_expression(shape_indices[current_shapes.index(shape)], expression)

            logger.debug(f"Updated components: {shape} -> {expression} {components}")

        # Remove the old shapes.
        for shape in current_shapes:
            if shape not in component_data:
                cmds.deformer(self._deformer_name, e=True, g=shape, rm=True)

                logger.debug(f"Removed shape: {shape}")

    def add_shape(self, shape: str) -> None:
        """Add the shape to the deformer.

        Args:
            shape(str): The shape to add.
        """
        if not shape:
            raise ValueError("No shape specified")

        if not cmds.objExists(shape):
            raise ValueError(f"Shape node does not exist: {shape}")

        if len(cmds.ls(shape)) > 1:
            raise ValueError(f"Shape node is not unique: {shape}")

        if shape in self.get_shapes():
            cmds.warning(f"Shape is already bound to deformer: {shape}")
            return

        cmds.deformer(self._deformer_name, e=True, g=shape)

        logger.debug(f"Added shape to deformer: {shape}")

    def remove_shape(self, shape: str) -> None:
        """Remove the shape from the deformer.

        Args:
            components(list[str]): The components to remove.
            index(int): The shape physical index.
        """
        if not shape:
            raise ValueError("No shape specified")

        if cmds.objExists(shape):
            cmds.error(f"Shape node does not exist: {shape}")

        if len(cmds.ls(shape)) > 1:
            cmds.error(f"Shape node is not unique: {shape}")

        if shape not in self.get_shapes():
            cmds.warning(f"Shape is not bound to deformer: {shape}")
            return

        cmds.deformer(self._deformer_name, e=True, g=shape, rm=True)

        logger.debug(f"Removed shape from deformer: {shape}")

    def get_tag_expression(self, index: int = 0) -> str:
        """Get the component tag.

        Args:
            index(int): The tag index.

        Returns:
            str: The component tag expression.
        """
        all_indices = self.get_all_indices()
        if index not in all_indices:
            raise ValueError("Index does not exist")

        return cmds.getAttr(f"{self._deformer_name}.input[{index}].componentTagExpression")

    def set_tag_expression(self, index: int = 0, tag_exp: str = "*", is_check: bool = True) -> None:
        """Set the component tag.

        Args:
            tag_exp(str): The component tag expression.
            index(int): The tag index.
            is_check(bool): If True, check if the index is a shape index and if the shape exists, verify if the component tag is valid.

        Notes:
            - If is_check is enabled and the index and tag_exp are incorrect, a warning log will be output and the process will terminate.
        """
        all_indices = self.get_all_indices()
        if index not in all_indices:
            raise ValueError("Index does not exist")

        if is_check:
            shape_indices = self.get_shape_indices()
            if index not in shape_indices:
                logger.warning(f"Index is not a shape index: {index}")
                return
            else:
                shape = self.get_shapes()[shape_indices.index(index)]
                shape_output = f"{shape}.{cmds.deformableShape(shape, localShapeOutAttr=True)[0]}"

                test_components = cmds.geometryAttrInfo(shape_output, components=True, componentTagExpression=tag_exp)
                if not test_components:
                    logger.warning(f"The result is empty or the component tag expression is invalid: {tag_exp}")
                    return

        cmds.setAttr(f"{self._deformer_name}.input[{index}].componentTagExpression", tag_exp, type="string")

        logger.debug(f"Set component tag expression: {tag_exp} -> {self._deformer_name}.input[{index}]")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self._deformer_name}')"

    def __str__(self) -> str:
        return self.__repr__()


def is_use_component_tag() -> bool:
    """Check if the component tag is available from the Maya preferences.

    Returns:
        bool: Whether the component tag is available.
    """
    use_component_tags = cmds.optionVar(q="deformationUseComponentTags")
    selection_component_tags = cmds.optionVar(q="deformationSelectionComponentTags")
    tweak_creation = cmds.optionVar(q="deformationCreateTweak")

    return bool(use_component_tags == 1 and selection_component_tags == 1 and tweak_creation == 0)


def remove_deformer_blank_indices(deformer: str):
    """Remove indices with no geometry set for the specified deformer.

    Notes:
        - The actual attributes are not deleted.
        - This function is intended to clean up the appearance in the Deformer Attributes tab of the Attribute Editor.
        - When this function is executed, the tag of indices with no geometry set will be set to '*'.
        - According to Maya's specifications, indices with no geometry set will not be displayed if the tag is set to '*'.

    Args:
        deformer (str): The name of the deformer node.
    """
    if not deformer:
        raise ValueError("No deformer specified")

    if not cmds.objExists(deformer):
        raise ValueError(f"Deformer node does not exist: {deformer}")

    deformer_membership = DeformerMembership(deformer)
    all_indices = deformer_membership.get_all_indices()
    shape_indices = deformer_membership.get_shape_indices()

    for index in all_indices:
        if index in shape_indices:
            continue

        current_tag = deformer_membership.get_tag_expression(index)
        if current_tag == "*":
            continue

        deformer_membership.set_tag_expression(index, tag_exp="*", is_check=False)

        logger.debug(f"Removed index with no geometry set: {deformer} {index}")
