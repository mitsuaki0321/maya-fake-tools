"""Debug script for Animation IO. Run in Maya Script Editor."""

import os
import tempfile

import maya.cmds as cmds


def setup_test_scene():
    """Create test scene with animated objects."""
    cmds.file(new=True, force=True)

    cube1 = cmds.polyCube(name="testCube1")[0]
    cube2 = cmds.polyCube(name="testCube2")[0]

    cmds.setKeyframe(cube1, attribute="translateX", time=1, value=0)
    cmds.setKeyframe(cube1, attribute="translateX", time=24, value=10)
    cmds.setKeyframe(cube1, attribute="rotateY", time=1, value=0)
    cmds.setKeyframe(cube1, attribute="rotateY", time=24, value=90)

    cmds.setKeyframe(cube2, attribute="translateZ", time=1, value=0)
    cmds.setKeyframe(cube2, attribute="translateZ", time=12, value=5)
    cmds.setKeyframe(cube2, attribute="translateZ", time=24, value=-5)

    print(f"[setup] Created: {cube1}, {cube2}")
    return [cube1, cube2]


def test_export(nodes, output_file):
    """Test export."""
    from faketools.tools.anim.anim_import_export import command

    builder = command.AnimationDataBuilder()
    data_list = builder.build(nodes)

    print(f"[export] Built {len(data_list)} AnimationData(s)")
    for data in data_list:
        print(f"  namespace='{data.namespace}': {list(data.nodes.keys())}")

    file_io = command.AnimationFileIO()
    written = file_io.write(output_file, data_list)
    print(f"[export] Written: {written}")
    return data_list


def test_import_replace(input_file):
    """Test import with replace mode."""
    from faketools.tools.anim.anim_import_export import command

    cmds.cutKey("testCube1", clear=True)
    cmds.cutKey("testCube2", clear=True)
    print("[import-replace] Cleared all keyframes")

    keys1 = cmds.keyframe("testCube1", query=True, timeChange=True) or []
    keys2 = cmds.keyframe("testCube2", query=True, timeChange=True) or []
    print(f"  testCube1 keys: {len(keys1)}, testCube2 keys: {len(keys2)}")

    modified = command.import_animation_from_file(input_file, mode=command.MODE_REPLACE)
    print(f"[import-replace] Modified nodes: {modified}")

    keys1 = cmds.keyframe("testCube1", query=True, timeChange=True) or []
    keys2 = cmds.keyframe("testCube2", query=True, timeChange=True) or []
    print(f"  testCube1 keys: {len(keys1)}, testCube2 keys: {len(keys2)}")


def test_import_merge(input_file):
    """Test import with merge mode."""
    from faketools.tools.anim.anim_import_export import command

    cmds.setKeyframe("testCube1", attribute="translateX", time=50, value=99)
    keys_before = cmds.keyframe("testCube1.translateX", query=True, timeChange=True) or []
    print(f"[import-merge] testCube1.tx keys before merge: {keys_before}")

    modified = command.import_animation_from_file(input_file, mode=command.MODE_MERGE)
    print(f"[import-merge] Modified nodes: {modified}")

    keys_after = cmds.keyframe("testCube1.translateX", query=True, timeChange=True) or []
    print(f"  testCube1.tx keys after merge: {keys_after}")
    print(f"  frame 50 survived: {50.0 in keys_after}")


def test_export_split(nodes, output_dir):
    """Test auto namespace split export."""
    from faketools.tools.anim.anim_import_export import command

    if not cmds.namespace(exists="testNS"):
        cmds.namespace(add="testNS")
    cmds.rename("testCube2", "testNS:testCube2")

    all_nodes = ["testCube1", "testNS:testCube2"]
    builder = command.AnimationDataBuilder()
    data_list = builder.build(all_nodes)

    print(f"[split-export] Built {len(data_list)} AnimationData(s)")
    for data in data_list:
        print(f"  namespace='{data.namespace}': {list(data.nodes.keys())}")

    output_file = os.path.join(output_dir, "split_test.json")
    file_io = command.AnimationFileIO()
    written = file_io.write(output_file, data_list)
    print(f"[split-export] Written files: {written}")


def test_validate_bad_file():
    """Test that invalid files are rejected."""
    from faketools.tools.anim.anim_import_export import command

    bad_file = os.path.join(tempfile.gettempdir(), "bad_anim.json")
    with open(bad_file, "w") as f:
        f.write('{"foo": "bar"}')

    file_io = command.AnimationFileIO()
    try:
        file_io.load(bad_file)
        print("[validate] ERROR: Should have raised ValueError")
    except ValueError as e:
        print(f"[validate] Correctly rejected bad file: {e}")
    finally:
        os.remove(bad_file)


def run_all():
    """Run all tests."""
    output_dir = tempfile.mkdtemp(prefix="anim_io_test_")
    output_file = os.path.join(output_dir, "test_anim.json")
    print(f"=== Output dir: {output_dir} ===\n")

    nodes = setup_test_scene()

    print("\n--- Test: Export ---")
    test_export(nodes, output_file)

    print("\n--- Test: Import Replace ---")
    test_import_replace(output_file)

    print("\n--- Test: Import Merge ---")
    test_import_merge(output_file)

    print("\n--- Test: Split Export ---")
    test_export_split(nodes, output_dir)

    print("\n--- Test: Validate Bad File ---")
    test_validate_bad_file()

    print(f"\n=== All tests done. Files at: {output_dir} ===")


run_all()
