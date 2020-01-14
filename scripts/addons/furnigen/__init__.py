import bpy
import logging

from math import radians
from mathutils import Matrix
from mathutils import Vector

bl_info = {
    "name": "FurniGen",
    "author": "Krzysztof Trzciński",
    "version": (1, 0),
    "blender": (2, 81, 0),
    #"location": "Properties > Parallel Render Panel or Render menu",
    "description": "Furniture generator",
    "warning": "",
    "wiki_url": "https://github.com/elmopl/ktba/wiki/Addons#furnigen",
    "tracker_url": "",
    "category": "3D View",
}

def _is_furnigen_enabled(context):
    ob = context.active_object
    res = ob and ob.get('furnigen', {}).get('enabled')
    return bool(res)

class FurniGenProperties(bpy.types.PropertyGroup):
    # name = StringProperty() # this is inherited from bpy.types.PropertyGroup
    enabled: bpy.props.BoolProperty('enabled')
    width: bpy.props.FloatProperty('width', min=0)
    height: bpy.props.FloatProperty('height', min=0)
    depth: bpy.props.FloatProperty('depth', min=0)
    sill_height: bpy.props.FloatProperty('sill height', min=0)
    frame_width: bpy.props.FloatProperty('frame_width', min=0)

class FurniGenGizmo(bpy.types.GizmoGroup):
    bl_idname = "OBJECT_GGT_furnigen_controls"
    bl_label = "FurniGen controls"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'PERSISTENT'}

    @classmethod
    def poll(cls, context):
        return _is_furnigen_enabled(context)

    def setup(self, context):
        # Arrow gizmo has one 'offset' property we can assign to the light energy.
        self.widgets = {}
        for prop, transform in (
            ('height', Matrix.Rotation(radians(0), 4, 'X')),
            ('width', Matrix.Rotation(radians(90), 4, 'Y')),
            ('depth', Matrix.Rotation(radians(-90), 4, 'X')),
            ('sill_height', Matrix.Rotation(radians(0), 4, 'X')),
            ('frame_width', Matrix.Rotation(radians(90), 4, 'Y')),
        ):
            mpr = self.gizmos.new("GIZMO_GT_arrow_3d")
            mpr.draw_style = 'NORMAL'

            mpr.color = 1.0, 0.5, 0.0
            mpr.alpha = 0.5
            mpr.length = 0

            mpr.color_highlight = 1.0, 0.5, 1.0
            mpr.alpha_highlight = 0.5

            self.widgets[prop] = (prop, mpr, transform)

    def refresh(self, context):
        ob = context.object

        dynamic_offsets = {
            'frame_width': Matrix.Translation(Vector((-ob.furnigen.height / 2, 0, 0))),
#            'sill_height': Matrix.Translation(Vector(0, 0, ob.furnigen.height / 2)),
        }

        for prop, widget, transform in self.widgets.values():
            widget.target_set_prop("offset", ob.furnigen, prop)
            extra_transform = dynamic_offsets.get(prop)
            if extra_transform is not None:
                transform = transform @ extra_transform
            widget.matrix_basis = ob.matrix_world.normalized() @ transform

class VIEW3D_OT_construct_furnigen_object(bpy.types.Operator):
    def execute(self, context):
        self.report({'INFO'}, f'Test {self}')
        collection = bpy.data.collections.new(name=self.BASE_NAME)

        obj = bpy.data.objects.new(
            name="Core",
            object_data=bpy.data.meshes.new(name=f"{self.BASE_NAME} mesh")
        )
        obj.display_type = 'WIRE'

        context.scene.collection.children.link(collection)
        collection.objects.link(obj)

        obj.furnigen.enabled = True
        obj.furnigen.width = 0.9
        obj.furnigen.depth = 0.075
        obj.furnigen.height = 2.140
        obj.furnigen.sill_height = 0.1
        obj.furnigen.frame_width = 0.044

        self.populate_mesh(obj)

        obj.select_set(True)
        context.view_layer.objects.active = obj

        return {'FINISHED'}

class VIEW3D_OT_construct_furnigen_object_door_30(VIEW3D_OT_construct_furnigen_object):
    bl_label = "Create 30s' door"
    bl_idname = "view3d.furnigen_create_door_30s"

    BASE_NAME = "30s Door"

    def create_corner(self):
        """
        This creates bottom left corner of the door.
        """

    def create_frame(self):
        """
        """
        struct = {
            'data': {
                'vertices': [(0,0,0),] * 8,
                'edges': [
                    (0, 1), (1, 2), (2, 3), (3, 0),
                    (4, 5), (5, 6), (6, 7), (7, 4),
                ],
                'faces': [],
            },
            'drivers': {
                'width': [((1, 2, 5, 6), 0)],
                'depth': [((0, 1, 4, 5), 1)],
                'height': [((0, 1, 2, 3), 2)],
            }
        }





    def populate_mesh(self, obj):
        mesh = obj.data

        struct = {
            'data': {
                'vertices': [(0,0,0),] * 8,
                'edges': [
                    (0, 1), (1, 2), (2, 3), (3, 0),
                    (4, 5), (5, 6), (6, 7), (7, 4),
                ],
                'faces': [],
            },
            'drivers': {
                'width': [((1, 2, 5, 6), 0)],
                'depth': [((0, 1, 4, 5), 1)],
                'height': [((0, 1, 2, 3), 2)],
            }
        }

        def _merge_struct(a, b):
            a_edge_count = len(a['data']['edges'])
            a['data']['faces'].extend(
                [x + a_edge_count for x in face]
                for face in b['data']['faces']
            )

            a_vertex_count = len(a['data']['vertices'])
            a['data']['edges'].extend(
                [x + a_vertex_count for x in edge]
                for edge in b['data']['edges']
            )
            
            a['data']['vertices'].extend(b['data']['vertices'])

            for name, group in b['data']['drivers']:
                a['data']['drivers'][name].append(group)

        mesh.from_pydata(**struct['data'])

        for prop, groups in struct['drivers'].items():
            for vertices, co_idx in groups:
                for vertex in vertices:
                    vertex = mesh.vertices[vertex]
                    driver = vertex.driver_add('co', co_idx).driver
                    var = driver.variables.new()
                    var.name = prop
                    var.type = 'SINGLE_PROP'
                    target = var.targets[0]
                    target.id = obj.id_data
                    target.data_path = f'furnigen.{prop}'
                    driver.expression = prop

class View3DPanel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Create"

    @classmethod
    def poll(cls, context):
        return True

OBJECT_CONSTRUCTORS = (
    VIEW3D_OT_construct_furnigen_object_door_30,
)

class FurniGenPanel(View3DPanel, bpy.types.Panel):
    bl_idname = "VIEW3D_PT_test_1"
    bl_label = "FurniGen"

    def draw(self, context):
        layout = self.layout
        for constructor_op in OBJECT_CONSTRUCTORS:
            layout.operator(constructor_op.bl_idname)

        if _is_furnigen_enabled(context):
            obj = context.object
            box = layout.box()
            box.row().label(text='Parameters')
            for name, prop in obj.furnigen.items():
                if name == 'enabled':
                    continue
                box.row().prop(obj.furnigen, name)


CLASSES = (
    FurniGenProperties,
    FurniGenPanel,
    FurniGenGizmo,
) + OBJECT_CONSTRUCTORS

def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)

    bpy.types.Object.furnigen = bpy.props.PointerProperty(type=FurniGenProperties)

def unregister():
    del bpy.types.Object.furnigen
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


