# Blender Pivot Align

Blender Pivot Align is a compact Blender add-on for quickly positioning and rotating an object's pivot from the 3D Viewport.

It provides simple one-click controls for common pivot operations, a dedicated pivot editing mode, and two-way matching between the object pivot and Blender's 3D Cursor.

<img height="400" alt="Screenshot" src="https://github.com/user-attachments/assets/4a9117c7-9fe6-4262-aba9-479a1a5af774" />

## Features

- Move the pivot to the object's bounding-box center.
- Move the pivot to world `0, 0, 0`.
- Move the pivot independently to the minimum or maximum X, Y, or Z bounds.
- Rotate the pivot axes by `+90°` or `-90°` on local X, Y, or Z.
- Keep the visible mesh in place while repositioning or rotating the pivot.
- Pivot Edit Mode automatically enables Local transform orientation and Blender's Affect Only Origins option.
- Snap the 3D Cursor to the pivot.
- Snap the pivot to the 3D Cursor.
- Optionally copy rotation when matching the pivot and 3D Cursor.
- Uses evaluated object bounds so visible modifier results are included when calculating Min, Max, and Center positions.
- Preserves child world transforms when the parent object's pivot is changed.
- Supports shape keys when compensating mesh geometry.

## Installation

1. Download `pivot_align.py`.
2. Open Blender.
3. Go to `Edit > Preferences > Add-ons`.
4. Choose `Install from Disk...`.
5. Select `pivot_align.py`.
6. Enable **Pivot Align** if Blender does not enable it automatically.

## Location

Open the 3D Viewport and press `N` to display the Sidebar.

The add-on appears under:

`3D Viewport > Sidebar > Pivot`

A **Pivot Align** submenu is also added to Blender's **Object** menu.

## Usage

### Pivot Edit Mode

Enable **Pivot Edit Mode** at the top of the panel when you want to manipulate the pivot directly.

While enabled, the add-on sets:

- Transform Orientation to **Local**
- **Affect Only Origins** to On

This makes Blender's transform gizmo display the pivot's current local orientation and allows normal Move and Rotate tools to manipulate the pivot without transforming the mesh.

Disabling Pivot Edit Mode returns the transform orientation to **Global** and turns Affect Only Origins off.

### Pivot Position

- **To Center** moves the pivot to the center of the object's world-space bounding box.
- **To World 0** moves the pivot to world origin.
- **X/Y/Z Max** moves only that pivot coordinate to the object's maximum bound on that axis.
- **X/Y/Z Min** moves only that pivot coordinate to the object's minimum bound on that axis.

The visible mesh remains stationary.

### Pivot Rotation

Use the X, Y, and Z rotation buttons to rotate only the pivot axes by `+90°` or `-90°`.

The mesh remains visually unchanged while its local pivot orientation changes.

### 3D Cursor

- **Cursor ← Pivot** moves the 3D Cursor to the active object's pivot.
- **Pivot ← Cursor** moves the active object's pivot to the 3D Cursor.
- Enable **Match Rotation** to transfer orientation as well as position.

This makes the 3D Cursor useful as a temporary placement and orientation target for pivots.

## Notes

Pivot editing operations currently require an active **Mesh** object in **Object Mode**.

Moving or rotating a Blender object origin while keeping its geometry stationary requires compensating the mesh data. If a mesh is shared by multiple objects, Pivot Align makes the edited mesh data single-user before changing it so other linked objects are not modified unexpectedly.

Blender internally calls this point the **Object Origin**. The add-on uses the term **Pivot** in its interface because it describes the intended workflow more directly.

## Compatibility

The add-on metadata targets Blender 4.3 or newer.

## Files

- `pivot_align.py` - Blender add-on
- `README.md` - Documentation
