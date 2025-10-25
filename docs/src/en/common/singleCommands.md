---
title: Single Commands
category: common
description: Frequently used single commands
lang: en
lang-ref: Single Commands
order: 0
---

### Usage

Select a command from the menu to execute it.

Commands differ in how they handle selection. There are three types of commands below.

**Scene Command**  
A command that runs on the entire scene. It executes regardless of selection.

**All Command**  
A command that runs on all selected nodes.

**Pair Command**  
A command that uses the first selected node as the source and applies to the subsequent selected nodes.

## Command List

### Scene Command

- **OptimizeScene**
  - Optimizes the scene.
    - Removes unknown plugins.
    - Deletes unknown nodes.
    - Deletes unused nodes.
    - Removes DataStructure.

### All Command

- **Lock And Hide**
  - Locks and hides the attributes shown in the Channel Box for the selected nodes.
  - If a Channel Box attribute is directly selected, it applies only to that attribute.
  - Visibility is hidden but not locked.
  
- **Unlock And Show**
  - Restores the Channel Box display to the state when the node was created.
  - Dynamic attributes (user-defined attributes) are not considered.
  
- **ZeroOut**
  - Resets the attributes shown in the Channel Box for the selected nodes to their default values.
  
- **Break Connections**
  - Breaks connections for the attributes shown in the Channel Box for the selected nodes.
  - If a Channel Box attribute is directly selected, it applies only to that attribute.

- **Freeze Transform**
  - Freezes transforms and resets the pivot for the selected nodes.

- **Freeze Mesh Vertices**
  - Freezes the vertices of the selected mesh(es).

- **DeleteConstraint**
  - Deletes constraints from the selected nodes.

- **Joint to Chain**
  - Sets up parent-child relationships for the selected nodes in a chain.

- **Mirror Joints**
  - Mirrors the selected nodes across the YZ plane.

- **Delete Extra Attributes**
  - Deletes all dynamic attributes (user-defined attributes) from the selected nodes.
  - Locked attributes are also deleted.

- **Duplicate Original Shape**
  - Duplicates the original shape of the selected shape(s).


### Pair Command

- **Snap Positions**
  - Snaps the positions of the second and subsequent selected nodes to the first selected node's position.

- **Snap Rotations**
  - Snaps the rotations of the second and subsequent selected nodes to the first selected node's rotation.

- **Snap Scales**
  - Snaps the scales of the second and subsequent selected nodes to the first selected node's scale.

- **Snap Translate and Rotate**
  - Snaps the translation and rotation of the second and subsequent selected nodes to the first selected node's translation and rotation.

- **Copy Transform**
  - Copies Translate, Rotate, and Scale from the first selected node to the second and subsequent selected nodes.

- **Connect Transform**
  - Connects Translate, Rotate, and Scale from the first selected node to the second and subsequent selected nodes.

- **Copy Weights**
  - Copies SkinCluster weights from the first selected node to the second and subsequent selected nodes.
  - If a SkinCluster does not exist on the second and subsequent selected nodes, one is created automatically.

- **Connect Shape**
  - Connects the topology of the first selected node to the second and subsequent selected nodes.
  
- **Copy Shape**
  - Copies the topology of the first selected node to the second and subsequent selected nodes.

- **Parent Transform**
  - Parents the first selected node under the second and subsequent selected nodes.
