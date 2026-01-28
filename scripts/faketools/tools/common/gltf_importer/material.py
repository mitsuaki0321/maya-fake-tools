"""Material conversion for glTF importer.

Converts glTF PBR materials to Maya shaders (Arnold/Stingray/Standard).
"""

from __future__ import annotations

from logging import getLogger

import maya.cmds as cmds

logger = getLogger(__name__)


class MaterialConverter:
    """PBR material to Maya shader converter."""

    def __init__(self, shader_type: str = "arnold"):
        """Initialize converter.

        Args:
            shader_type: Shader type ('arnold', 'stingray', 'standard', 'auto').
        """
        self.shader_type = shader_type
        self.converted_materials: dict[str, str] = {}

    def detect_available_renderer(self) -> str:
        """Detect available renderer.

        Returns:
            str: 'arnold', 'stingray', or 'standard'.
        """
        # Check if Arnold plugin is loaded
        if cmds.pluginInfo("mtoa", query=True, loaded=True):
            return "arnold"

        # Check if StingrayPBS is available (Maya 2017+)
        try:
            if cmds.shadingNode("StingrayPBS", query=True, isPostProcess=True) is not None:
                return "stingray"
        except RuntimeError:
            pass

        # Default to standard shader
        return "standard"

    def convert_materials(self, imported_nodes: list[str]) -> None:
        """Convert materials on imported nodes.

        This method finds all materials assigned to the imported meshes
        and logs information about them. FBX import already brings materials,
        so this is mainly for potential future enhancement.

        Args:
            imported_nodes: List of imported node names.
        """
        if self.shader_type == "auto":
            self.shader_type = self.detect_available_renderer()
            logger.info(f"Auto-detected renderer: {self.shader_type}")

        # Find all shape nodes under imported nodes
        all_shapes = []
        for node in imported_nodes:
            shapes = cmds.listRelatives(node, allDescendents=True, type="mesh") or []
            all_shapes.extend(shapes)

        if not all_shapes:
            logger.info("No mesh shapes found in imported nodes")
            return

        # Get unique shading groups
        shading_groups = set()
        for shape in all_shapes:
            sgs = cmds.listConnections(shape, type="shadingEngine") or []
            shading_groups.update(sgs)

        logger.info(f"Found {len(shading_groups)} shading groups on imported meshes")
        for sg in shading_groups:
            logger.debug(f"  - {sg}")

    def convert_material(self, material_name: str, pbr_params: dict) -> str:
        """Create Maya material from PBR parameters.

        Args:
            material_name: Material name.
            pbr_params: PBR parameter dictionary with keys:
                - baseColor: [r, g, b, a]
                - baseColorTexture: path/to/texture.png
                - metallic: float (0.0-1.0)
                - roughness: float (0.0-1.0)
                - metallicRoughnessTexture: path/to/texture.png
                - normalTexture: path/to/normal.png
                - emissive: [r, g, b]
                - emissiveTexture: path/to/emissive.png
                - aoTexture: path/to/ao.png

        Returns:
            str: Created shading group name.
        """
        if self.shader_type == "auto":
            self.shader_type = self.detect_available_renderer()

        logger.info(f"Converting material: {material_name} (renderer: {self.shader_type})")

        if self.shader_type == "arnold":
            return self._create_arnold_material(material_name, pbr_params)
        elif self.shader_type == "stingray":
            return self._create_stingray_material(material_name, pbr_params)
        else:
            return self._create_standard_material(material_name, pbr_params)

    def _create_arnold_material(self, material_name: str, pbr_params: dict) -> str:
        """Create Arnold aiStandardSurface material.

        Args:
            material_name: Material name.
            pbr_params: PBR parameters.

        Returns:
            str: Shading group name.
        """
        shader = cmds.shadingNode("aiStandardSurface", asShader=True, name=f"{material_name}_aiSS")
        shading_group = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=f"{material_name}_SG")
        cmds.connectAttr(f"{shader}.outColor", f"{shading_group}.surfaceShader", force=True)

        # Base Color
        if "baseColor" in pbr_params:
            color = pbr_params["baseColor"]
            cmds.setAttr(f"{shader}.baseColor", color[0], color[1], color[2], type="double3")

        if "baseColorTexture" in pbr_params:
            file_node = self._create_file_texture(pbr_params["baseColorTexture"], f"{material_name}_baseColor")
            cmds.connectAttr(f"{file_node}.outColor", f"{shader}.baseColor", force=True)

        # Metallic
        if "metallic" in pbr_params:
            cmds.setAttr(f"{shader}.metalness", pbr_params["metallic"])

        # Roughness
        if "roughness" in pbr_params:
            cmds.setAttr(f"{shader}.specularRoughness", pbr_params["roughness"])

        # Metallic/Roughness Texture
        if "metallicRoughnessTexture" in pbr_params:
            file_node = self._create_file_texture(pbr_params["metallicRoughnessTexture"], f"{material_name}_metallicRoughness")
            cmds.connectAttr(f"{file_node}.outColorR", f"{shader}.metalness", force=True)
            cmds.connectAttr(f"{file_node}.outColorG", f"{shader}.specularRoughness", force=True)

        # Normal Map
        if "normalTexture" in pbr_params:
            normal_map = self._create_normal_map(pbr_params["normalTexture"], f"{material_name}_normal")
            cmds.connectAttr(f"{normal_map}.outValue", f"{shader}.normalCamera", force=True)

        # Emissive
        if "emissive" in pbr_params:
            emissive = pbr_params["emissive"]
            cmds.setAttr(f"{shader}.emission", 1.0)
            cmds.setAttr(f"{shader}.emissionColor", emissive[0], emissive[1], emissive[2], type="double3")

        if "emissiveTexture" in pbr_params:
            file_node = self._create_file_texture(pbr_params["emissiveTexture"], f"{material_name}_emissive")
            cmds.setAttr(f"{shader}.emission", 1.0)
            cmds.connectAttr(f"{file_node}.outColor", f"{shader}.emissionColor", force=True)

        self.converted_materials[material_name] = shading_group
        logger.info(f"  Arnold material created: {shader} -> {shading_group}")

        return shading_group

    def _create_stingray_material(self, material_name: str, pbr_params: dict) -> str:
        """Create Stingray PBS material.

        Args:
            material_name: Material name.
            pbr_params: PBR parameters.

        Returns:
            str: Shading group name.
        """
        shader = cmds.shadingNode("StingrayPBS", asShader=True, name=f"{material_name}_stingray")
        shading_group = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=f"{material_name}_SG")
        cmds.connectAttr(f"{shader}.outColor", f"{shading_group}.surfaceShader", force=True)

        # Base Color
        if "baseColor" in pbr_params:
            color = pbr_params["baseColor"]
            cmds.setAttr(f"{shader}.baseColor", color[0], color[1], color[2], type="double3")

        if "baseColorTexture" in pbr_params:
            file_node = self._create_file_texture(pbr_params["baseColorTexture"], f"{material_name}_baseColor")
            cmds.connectAttr(f"{file_node}.outColor", f"{shader}.TEX_color_map", force=True)

        # Metallic
        if "metallic" in pbr_params:
            cmds.setAttr(f"{shader}.metallic", pbr_params["metallic"])

        # Roughness
        if "roughness" in pbr_params:
            cmds.setAttr(f"{shader}.roughness", pbr_params["roughness"])

        # Normal Map
        if "normalTexture" in pbr_params:
            file_node = self._create_file_texture(pbr_params["normalTexture"], f"{material_name}_normal")
            cmds.connectAttr(f"{file_node}.outColor", f"{shader}.TEX_normal_map", force=True)

        # Emissive
        if "emissiveTexture" in pbr_params:
            file_node = self._create_file_texture(pbr_params["emissiveTexture"], f"{material_name}_emissive")
            cmds.connectAttr(f"{file_node}.outColor", f"{shader}.TEX_emissive_map", force=True)

        self.converted_materials[material_name] = shading_group
        logger.info(f"  Stingray material created: {shader} -> {shading_group}")

        return shading_group

    def _create_standard_material(self, material_name: str, pbr_params: dict) -> str:
        """Create standard Blinn material (fallback).

        Args:
            material_name: Material name.
            pbr_params: PBR parameters.

        Returns:
            str: Shading group name.
        """
        shader = cmds.shadingNode("blinn", asShader=True, name=f"{material_name}_blinn")
        shading_group = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=f"{material_name}_SG")
        cmds.connectAttr(f"{shader}.outColor", f"{shading_group}.surfaceShader", force=True)

        # Base Color
        if "baseColor" in pbr_params:
            color = pbr_params["baseColor"]
            cmds.setAttr(f"{shader}.color", color[0], color[1], color[2], type="double3")

        if "baseColorTexture" in pbr_params:
            file_node = self._create_file_texture(pbr_params["baseColorTexture"], f"{material_name}_baseColor")
            cmds.connectAttr(f"{file_node}.outColor", f"{shader}.color", force=True)

        # Roughness -> eccentricity
        if "roughness" in pbr_params:
            cmds.setAttr(f"{shader}.eccentricity", pbr_params["roughness"])

        # Metallic -> reflectivity
        if "metallic" in pbr_params:
            cmds.setAttr(f"{shader}.reflectivity", pbr_params["metallic"])

        # Normal Map
        if "normalTexture" in pbr_params:
            normal_map = self._create_normal_map(pbr_params["normalTexture"], f"{material_name}_normal")
            cmds.connectAttr(f"{normal_map}.outValue", f"{shader}.normalCamera", force=True)

        self.converted_materials[material_name] = shading_group
        logger.info(f"  Standard material created: {shader} -> {shading_group}")

        return shading_group

    def _create_file_texture(self, texture_path: str, node_name: str) -> str:
        """Create file texture node.

        Args:
            texture_path: Texture file path.
            node_name: Node name.

        Returns:
            str: File node name.
        """
        # Create place2dTexture node
        place2d = cmds.shadingNode("place2dTexture", asUtility=True, name=f"{node_name}_place2d")

        # Create file node
        file_node = cmds.shadingNode("file", asTexture=True, name=node_name, isColorManaged=True)

        # Set texture path
        cmds.setAttr(f"{file_node}.fileTextureName", texture_path, type="string")

        # Connect place2dTexture to file node
        cmds.connectAttr(f"{place2d}.coverage", f"{file_node}.coverage", force=True)
        cmds.connectAttr(f"{place2d}.translateFrame", f"{file_node}.translateFrame", force=True)
        cmds.connectAttr(f"{place2d}.rotateFrame", f"{file_node}.rotateFrame", force=True)
        cmds.connectAttr(f"{place2d}.mirrorU", f"{file_node}.mirrorU", force=True)
        cmds.connectAttr(f"{place2d}.mirrorV", f"{file_node}.mirrorV", force=True)
        cmds.connectAttr(f"{place2d}.stagger", f"{file_node}.stagger", force=True)
        cmds.connectAttr(f"{place2d}.wrapU", f"{file_node}.wrapU", force=True)
        cmds.connectAttr(f"{place2d}.wrapV", f"{file_node}.wrapV", force=True)
        cmds.connectAttr(f"{place2d}.repeatUV", f"{file_node}.repeatUV", force=True)
        cmds.connectAttr(f"{place2d}.offset", f"{file_node}.offset", force=True)
        cmds.connectAttr(f"{place2d}.rotateUV", f"{file_node}.rotateUV", force=True)
        cmds.connectAttr(f"{place2d}.noiseUV", f"{file_node}.noiseUV", force=True)
        cmds.connectAttr(f"{place2d}.vertexUvOne", f"{file_node}.vertexUvOne", force=True)
        cmds.connectAttr(f"{place2d}.vertexUvTwo", f"{file_node}.vertexUvTwo", force=True)
        cmds.connectAttr(f"{place2d}.vertexUvThree", f"{file_node}.vertexUvThree", force=True)
        cmds.connectAttr(f"{place2d}.vertexCameraOne", f"{file_node}.vertexCameraOne", force=True)
        cmds.connectAttr(f"{place2d}.outUV", f"{file_node}.uv", force=True)
        cmds.connectAttr(f"{place2d}.outUvFilterSize", f"{file_node}.uvFilterSize", force=True)

        return file_node

    def _create_normal_map(self, texture_path: str, node_name: str) -> str:
        """Create normal map node.

        Args:
            texture_path: Normal map texture path.
            node_name: Node name.

        Returns:
            str: Bump2d node name.
        """
        file_node = self._create_file_texture(texture_path, node_name)

        # Set to Raw color space (normal maps are linear)
        cmds.setAttr(f"{file_node}.colorSpace", "Raw", type="string")

        # Create bump2d node
        bump2d = cmds.shadingNode("bump2d", asUtility=True, name=f"{node_name}_bump2d")
        cmds.setAttr(f"{bump2d}.bumpInterp", 1)  # Tangent Space Normals

        # Connect file to bump2d
        cmds.connectAttr(f"{file_node}.outColor", f"{bump2d}.bumpValue", force=True)

        return bump2d

    def apply_material_to_mesh(self, mesh_name: str, shading_group: str) -> None:
        """Apply material to mesh.

        Args:
            mesh_name: Mesh name.
            shading_group: Shading group name.
        """
        try:
            cmds.sets(mesh_name, edit=True, forceElement=shading_group)
            logger.info(f"  Material applied: {mesh_name} -> {shading_group}")
        except Exception as e:
            logger.warning(f"  Failed to apply material: {mesh_name} - {e}")

    def get_converted_material(self, material_name: str) -> str | None:
        """Get converted material's shading group.

        Args:
            material_name: Material name.

        Returns:
            str | None: Shading group name, or None if not found.
        """
        return self.converted_materials.get(material_name)
