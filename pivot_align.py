bl_info = {
    "name": "Pivot Align",
    "version": (1, 2, 0),
    "blender": (4, 3, 0),
    "location": "3D Viewport > Sidebar > Pivot",
    "description": "Pivot alignment, rotation, and 3D Cursor matching tools",
    "category": "3D View",
}

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty
from math import radians
from mathutils import Matrix, Vector


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def get_active_mesh(context):
    obj = context.active_object
    if obj is None or obj.type != 'MESH':
        return None
    return obj


def get_descendants(obj):
    """Return descendants in parent-to-child order."""
    result = []
    stack = list(obj.children)

    while stack:
        child = stack.pop(0)
        result.append(child)
        stack.extend(list(child.children))

    return result


def ensure_single_user_mesh(obj):
    """
    Moving an origin while leaving geometry in place requires changing the
    mesh's local coordinates. If the mesh data is linked, make this object
    single-user so other linked objects are not modified.
    """
    if obj.data.users > 1:
        obj.data = obj.data.copy()
        return True
    return False


def set_origin_matrix_keep_geometry(obj, new_world_matrix):
    """
    Change the object's origin transform while keeping the visible mesh
    fixed in world space.

    World geometry before:
        old_world @ vertex

    World geometry after:
        new_world @ new_vertex

    Therefore:
        new_vertex = inverse(new_world) @ old_world @ vertex
    """
    made_single_user = ensure_single_user_mesh(obj)

    old_world = obj.matrix_world.copy()
    child_world_matrices = [
        (child, child.matrix_world.copy())
        for child in get_descendants(obj)
    ]

    compensation = new_world_matrix.inverted_safe() @ old_world

    # Transform the base mesh and all shape keys together.
    obj.data.transform(compensation, shape_keys=True)
    obj.matrix_world = new_world_matrix
    obj.data.update()

    # Changing an object's origin transform can otherwise move its children.
    # Restore each descendant's original world transform.
    for child, world_matrix in child_world_matrices:
        child.matrix_world = world_matrix

    return made_single_user


def set_origin_location_keep_geometry(obj, world_location):
    new_world = obj.matrix_world.copy()
    new_world.translation = Vector(world_location)
    return set_origin_matrix_keep_geometry(obj, new_world)


def get_world_bounds(context, obj):
    """
    Return world-space min/max bounds.
    Uses the evaluated object so visible modifier results are included.
    """
    depsgraph = context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)

    corners = [
        eval_obj.matrix_world @ Vector(corner)
        for corner in eval_obj.bound_box
    ]

    min_bound = Vector((
        min(v.x for v in corners),
        min(v.y for v in corners),
        min(v.z for v in corners),
    ))

    max_bound = Vector((
        max(v.x for v in corners),
        max(v.y for v in corners),
        max(v.z for v in corners),
    ))

    return min_bound, max_bound


def cursor_rotation_quaternion(cursor):
    return cursor.matrix.to_quaternion()


def set_cursor_rotation_from_matrix(cursor, matrix):
    quat = matrix.to_quaternion()

    if cursor.rotation_mode == 'QUATERNION':
        cursor.rotation_quaternion = quat

    elif cursor.rotation_mode == 'AXIS_ANGLE':
        axis, angle = quat.to_axis_angle()
        cursor.rotation_axis_angle = (angle, axis.x, axis.y, axis.z)

    else:
        cursor.rotation_euler = quat.to_euler(cursor.rotation_mode)


def matrix_with_rotation_and_scale(location, rotation_quat, scale):
    return (
        Matrix.Translation(location)
        @ rotation_quat.to_matrix().to_4x4()
        @ Matrix.Diagonal((scale.x, scale.y, scale.z, 1.0))
    )


def apply_pivot_edit_mode(scene, enabled):
    """
    Pivot Edit Mode provides a focused Blender pivot-editing workflow:

    Enabled:
      - Transform Orientation = Local
      - Affect Only Origins = On

    Disabled:
      - Transform Orientation = Global
      - Affect Only Origins = Off

    Local orientation makes the transform gizmo display the object's current
    origin axes, including rotations made by this add-on.
    """
    scene.transform_orientation_slots[0].type = (
        'LOCAL' if enabled else 'GLOBAL'
    )
    scene.tool_settings.use_transform_data_origin = enabled


def update_pivot_edit_mode(self, context):
    apply_pivot_edit_mode(self, self.pivot_align_edit_mode)


# ------------------------------------------------------------
# Operators
# ------------------------------------------------------------

class PIVOTALIGN_OT_set_origin(bpy.types.Operator):
    bl_idname = "pivotalign.set_origin"
    bl_label = "Set Pivot"
    bl_description = "Move the object pivot without moving the visible mesh"
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(
        name="Mode",
        items=(
            ('CENTER', "Center", "Move pivot to the center of the world-space bounding box"),
            ('WORLD', "World Origin", "Move pivot to world 0, 0, 0"),
            ('MAX_X', "Max X", "Move only the pivot X coordinate to the object's maximum world X"),
            ('MIN_X', "Min X", "Move only the pivot X coordinate to the object's minimum world X"),
            ('MAX_Y', "Max Y", "Move only the pivot Y coordinate to the object's maximum world Y"),
            ('MIN_Y', "Min Y", "Move only the pivot Y coordinate to the object's minimum world Y"),
            ('MAX_Z', "Max Z", "Move only the pivot Z coordinate to the object's maximum world Z"),
            ('MIN_Z', "Min Z", "Move only the pivot Z coordinate to the object's minimum world Z"),
        ),
    )

    @classmethod
    def poll(cls, context):
        obj = get_active_mesh(context)
        return obj is not None and obj.mode == 'OBJECT'

    def execute(self, context):
        obj = get_active_mesh(context)
        min_bound, max_bound = get_world_bounds(context, obj)

        current = obj.matrix_world.translation.copy()

        if self.mode == 'CENTER':
            target = (min_bound + max_bound) * 0.5

        elif self.mode == 'WORLD':
            target = Vector((0.0, 0.0, 0.0))

        else:
            target = current.copy()

            axis_index = {
                'X': 0,
                'Y': 1,
                'Z': 2,
            }[self.mode[-1]]

            if self.mode.startswith('MAX'):
                target[axis_index] = max_bound[axis_index]
            else:
                target[axis_index] = min_bound[axis_index]

        made_single_user = set_origin_location_keep_geometry(obj, target)

        if made_single_user:
            self.report(
                {'INFO'},
                "Linked mesh data was made single-user so other objects were not changed."
            )

        return {'FINISHED'}


class PIVOTALIGN_OT_rotate_origin(bpy.types.Operator):
    bl_idname = "pivotalign.rotate_origin"
    bl_label = "Rotate Pivot"
    bl_description = "Rotate the object's local pivot axes without rotating the visible mesh"
    bl_options = {'REGISTER', 'UNDO'}

    axis: EnumProperty(
        name="Axis",
        items=(
            ('X', "X", "Rotate around local X"),
            ('Y', "Y", "Rotate around local Y"),
            ('Z', "Z", "Rotate around local Z"),
        ),
    )

    angle: FloatProperty(
        name="Angle",
        default=90.0,
    )

    @classmethod
    def poll(cls, context):
        obj = get_active_mesh(context)
        return obj is not None and obj.mode == 'OBJECT'

    def execute(self, context):
        obj = get_active_mesh(context)

        location, rotation, scale = obj.matrix_world.decompose()
        delta_rotation = Matrix.Rotation(
            radians(self.angle),
            4,
            self.axis,
        ).to_quaternion()

        # Rotate the pivot axes in local space while preserving world scale.
        new_rotation = rotation @ delta_rotation
        new_world = matrix_with_rotation_and_scale(
            location,
            new_rotation,
            scale,
        )

        made_single_user = set_origin_matrix_keep_geometry(obj, new_world)

        if made_single_user:
            self.report(
                {'INFO'},
                "Linked mesh data was made single-user so other objects were not changed."
            )

        return {'FINISHED'}


class PIVOTALIGN_OT_cursor_from_origin(bpy.types.Operator):
    bl_idname = "pivotalign.cursor_from_origin"
    bl_label = "Cursor from Pivot"
    bl_description = "Move the 3D Cursor to the active object's pivot"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        obj = context.active_object
        cursor = context.scene.cursor

        cursor.location = obj.matrix_world.translation

        if context.scene.pivot_align_match_rotation:
            set_cursor_rotation_from_matrix(cursor, obj.matrix_world)

        return {'FINISHED'}


class PIVOTALIGN_OT_origin_from_cursor(bpy.types.Operator):
    bl_idname = "pivotalign.origin_from_cursor"
    bl_label = "Pivot from Cursor"
    bl_description = "Move the active object's pivot to the 3D Cursor without moving the visible mesh"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = get_active_mesh(context)
        return obj is not None and obj.mode == 'OBJECT'

    def execute(self, context):
        obj = get_active_mesh(context)
        cursor = context.scene.cursor

        if context.scene.pivot_align_match_rotation:
            old_world = obj.matrix_world.copy()
            scale = old_world.to_scale()
            cursor_rotation = cursor_rotation_quaternion(cursor)

            new_world = matrix_with_rotation_and_scale(
                cursor.location,
                cursor_rotation,
                scale,
            )

            made_single_user = set_origin_matrix_keep_geometry(obj, new_world)

        else:
            made_single_user = set_origin_location_keep_geometry(
                obj,
                cursor.location,
            )

        if made_single_user:
            self.report(
                {'INFO'},
                "Linked mesh data was made single-user so other objects were not changed."
            )

        return {'FINISHED'}


# ------------------------------------------------------------
# UI
# ------------------------------------------------------------

class VIEW3D_PT_pivot_align(bpy.types.Panel):
    bl_label = "Pivot Align"
    bl_idname = "VIEW3D_PT_pivot_align"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Pivot"

    def draw(self, context):
        layout = self.layout
        obj = context.active_object

        # Pivot Edit Mode --------------------------------------------------
        # Keep this at the top and available even with nothing selected so
        # Pivot Edit Mode can always be turned back off.
        box = layout.box()
        row = box.row(align=True)
        row.prop(
            context.scene,
            "pivot_align_edit_mode",
            text="Pivot Edit Mode",
            toggle=True,
            icon='ORIENTATION_LOCAL' if context.scene.pivot_align_edit_mode else 'ORIENTATION_GLOBAL',
        )

        if context.scene.pivot_align_edit_mode:
            box.label(text="Orientation: Local", icon='CHECKMARK')
            box.label(text="Affect Only Origins: On")
        else:
            box.label(text="Orientation: Global")
            box.label(text="Affect Only Origins: Off")

        if obj is None:
            layout.label(text="Select an object.", icon='INFO')
            return

        if obj.type != 'MESH':
            layout.label(text="Mesh object required for pivot edits.", icon='INFO')

            box = layout.box()
            box.label(text="3D Cursor")
            box.prop(
                context.scene,
                "pivot_align_match_rotation",
                text="Match Rotation",
            )
            box.operator(
                PIVOTALIGN_OT_cursor_from_origin.bl_idname,
                text="Cursor ← Pivot",
            )
            return

        if obj.mode != 'OBJECT':
            layout.label(text="Switch to Object Mode.", icon='INFO')

        # Position ---------------------------------------------------------
        box = layout.box()
        box.label(text="Pivot Position")

        row = box.row(align=True)
        op = row.operator(
            PIVOTALIGN_OT_set_origin.bl_idname,
            text="To Center",
        )
        op.mode = 'CENTER'

        op = row.operator(
            PIVOTALIGN_OT_set_origin.bl_idname,
            text="To World 0",
        )
        op.mode = 'WORLD'

        row = box.row(align=True)

        for axis in ('X', 'Y', 'Z'):
            col = row.column(align=True)
            col.label(text=axis)

            op = col.operator(
                PIVOTALIGN_OT_set_origin.bl_idname,
                text="Max",
            )
            op.mode = f"MAX_{axis}"

            op = col.operator(
                PIVOTALIGN_OT_set_origin.bl_idname,
                text="Min",
            )
            op.mode = f"MIN_{axis}"

        # Rotation ---------------------------------------------------------
        box = layout.box()
        box.label(text="Pivot Rotation")

        row = box.row(align=True)
        for axis in ('X', 'Y', 'Z'):
            op = row.operator(
                PIVOTALIGN_OT_rotate_origin.bl_idname,
                text=f"{axis} +90°",
            )
            op.axis = axis
            op.angle = 90.0

        row = box.row(align=True)
        for axis in ('X', 'Y', 'Z'):
            op = row.operator(
                PIVOTALIGN_OT_rotate_origin.bl_idname,
                text=f"{axis} -90°",
            )
            op.axis = axis
            op.angle = -90.0

        # Cursor -----------------------------------------------------------
        box = layout.box()
        box.label(text="3D Cursor")

        box.prop(
            context.scene,
            "pivot_align_match_rotation",
            text="Match Rotation",
        )

        row = box.row(align=True)
        row.operator(
            PIVOTALIGN_OT_cursor_from_origin.bl_idname,
            text="Cursor ← Pivot",
        )
        row.operator(
            PIVOTALIGN_OT_origin_from_cursor.bl_idname,
            text="Pivot ← Cursor",
        )


class VIEW3D_MT_pivot_align(bpy.types.Menu):
    bl_label = "Pivot Align"
    bl_idname = "VIEW3D_MT_pivot_align"

    def draw(self, context):
        layout = self.layout

        op = layout.operator(
            PIVOTALIGN_OT_set_origin.bl_idname,
            text="Pivot to Center",
        )
        op.mode = 'CENTER'

        op = layout.operator(
            PIVOTALIGN_OT_set_origin.bl_idname,
            text="Pivot to World 0",
        )
        op.mode = 'WORLD'

        layout.separator()

        layout.operator(
            PIVOTALIGN_OT_cursor_from_origin.bl_idname,
            text="Cursor from Pivot",
        )
        layout.operator(
            PIVOTALIGN_OT_origin_from_cursor.bl_idname,
            text="Pivot from Cursor",
        )


def draw_object_menu(self, context):
    self.layout.menu(VIEW3D_MT_pivot_align.bl_idname)


# ------------------------------------------------------------
# Registration
# ------------------------------------------------------------

classes = (
    PIVOTALIGN_OT_set_origin,
    PIVOTALIGN_OT_rotate_origin,
    PIVOTALIGN_OT_cursor_from_origin,
    PIVOTALIGN_OT_origin_from_cursor,
    VIEW3D_PT_pivot_align,
    VIEW3D_MT_pivot_align,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.pivot_align_edit_mode = BoolProperty(
        name="Pivot Edit Mode",
        description=(
            "Use Local transform orientation and Affect Only Origins while "
            "editing the pivot; disabling returns to Global orientation and "
            "normal object transforms"
        ),
        default=False,
        update=update_pivot_edit_mode,
    )

    bpy.types.Scene.pivot_align_match_rotation = BoolProperty(
        name="Match Rotation",
        description=(
            "When transferring between the Pivot and 3D Cursor, "
            "also copy orientation"
        ),
        default=False,
    )

    bpy.types.VIEW3D_MT_object.append(draw_object_menu)


def unregister():
    bpy.types.VIEW3D_MT_object.remove(draw_object_menu)

    # Never leave Blender in origin-only/local mode just because the add-on
    # was disabled or reloaded.
    for scene in bpy.data.scenes:
        apply_pivot_edit_mode(scene, False)

    del bpy.types.Scene.pivot_align_match_rotation
    del bpy.types.Scene.pivot_align_edit_mode

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
