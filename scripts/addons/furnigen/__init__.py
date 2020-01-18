from . import doors30
from .parametrised import ParametrisedValue

# When bpy is already in local, we know this is not the initial import.
# This greatly helps with developement.
if "bpy" in locals():
    # ...so we need to reload our submodule(s) using importlib
    import importlib
    from . import parametrised
    importlib.reload(parametrised)
    importlib.reload(doors30)
    
import bpy



from functools import partial
from itertools import chain
import bpy
import logging

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

class FurniGenLength(bpy.types.PropertyGroup):
    value: bpy.props.FloatProperty(min=0)

class FurniGenCount(bpy.types.PropertyGroup):
    value: bpy.props.IntProperty(min=0)

class FurniGenProperties(bpy.types.PropertyGroup):
    # name = StringProperty() # this is inherited from bpy.types.PropertyGroup
    enabled: bpy.props.BoolProperty()
    index: bpy.props.IntProperty()
    geometry: bpy.props.StringProperty()
    lengths: bpy.props.CollectionProperty(type=FurniGenLength)
    counts: bpy.props.CollectionProperty(type=FurniGenCount)

GEOMETRIES = {
   '30s Door': doors30.DESCRIPTION,
}

def set_parameter_properties(furnigen):
    geometry = GEOMETRIES[furnigen.geometry]
    for category in ('lengths', 'counts'):
        for name, param in geometry['parameters'][category].items():
            item = getattr(furnigen, category).add()
            item.name = name
            item.value = param['default']

def build_geometry(obj):
    mesh = obj.data
    info = GEOMETRIES[obj.furnigen.geometry]
    geometries = info['geometries']
    param_name_to_idx = {
        name: pos
        for pos, name in enumerate(info['parameters']['lengths'])
    }

    all_faces = []

    def get_instances(geom):
        count = 1
        name = geom.get('instances')
        if name is not None:
            count = obj.furnigen.counts[name].value
        return count

    vertex_offset = 0
    for geometry in geometries:
        for _ in range(get_instances(geometry)):
            all_faces.extend(
                tuple(x + vertex_offset for x in face)
                for face in geometry['faces']
            )
            vertices = geometry['vertices']
            assert isinstance(vertices, (list, tuple)), (geometry['name'], type(vertices))
            vertex_offset += len(vertices)

    obj.data.from_pydata(
        vertices=((0, 0, 0),) * vertex_offset,
        edges=(),
        faces=all_faces
    )

    vertices = iter(mesh.vertices)
    for geometry in info['geometries']:
        instance_count = get_instances(geometry)
        for instance in range(instance_count):
            for pos, vertex in zip(geometry['vertices'], vertices):
                for co_idx, co in enumerate(map(ParametrisedValue, pos)):
                    if co.constant:
                        vertex.co[co_idx] = co.expr
                    else:
                        co = co.subst(instance=instance, instance_count=instance_count)
                        vertex.co[co_idx] = 1
                        driver = vertex.driver_add('co', co_idx).driver
                        print(co, co.parameters)
                        for name in co.parameters:
                            var = driver.variables.new()
                            var.name = name
                            var.type = 'SINGLE_PROP'
                            target = var.targets[0]
                            target.id = obj.id_data
                            pos = param_name_to_idx[name]
                            target.data_path = f'furnigen.lengths[{pos}].value'

                            driver.expression = str(co)

def _is_furnigen_enabled(context):
    ob = context.active_object
    res = ob and ob.get('furnigen', {}).get('enabled')
    return bool(res)

class FurniGenGizmo(bpy.types.GizmoGroup):
    bl_idname = "OBJECT_GGT_furnigen_controls"
    bl_label = "FurniGen controls"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'PERSISTENT'}

    @classmethod
    def poll(cls, context):
        return _is_furnigen_enabled(context)

    def _reconstruct(self, ob):
        self.gizmos.clear()
        geom = GEOMETRIES[ob.furnigen.geometry]
        self.arrows = {}
        for prop in ob.furnigen.lengths:
            name = prop.name
            mpr = self.gizmos.new("GIZMO_GT_arrow_3d")
            mpr.draw_style = 'NORMAL'

            mpr.color = 1.0, 0.5, 0.0
            mpr.alpha = 0.5
            mpr.length = 0

            mpr.target_set_prop("offset", prop, 'value')

            mpr.color_highlight = 1.0, 0.5, 1.0
            mpr.alpha_highlight = 0.5
            self.arrows[name] = (
                mpr,
                geom['parameters']['lengths'][name]['base_transform'],
            )

    def setup(self, context):
        self.obj = None

    def refresh(self, context):
        ob = context.object
        if self.obj != ob:
            self._reconstruct(ob)
            self.obj = ob

        parameters = {
            name: param.value
            for name, param in chain(
                ob.furnigen.lengths.items(),
                ob.furnigen.counts.items()
            )
        }

        for name, (arrow, transform) in self.arrows.items():
            transform = transform.calculate(parameters)
            arrow.matrix_basis = ob.matrix_world.normalized() @ transform

class VIEW3D_OT_construct_furnigen_object(bpy.types.Operator):
    def execute(self, context):
        collection = bpy.data.collections.new(name=self.GEOMETRY)

        obj = bpy.data.objects.new(
            name="Mesh",
            object_data=bpy.data.meshes.new(name=f"{self.GEOMETRY} mesh")
        )

        context.scene.collection.children.link(collection)
        collection.objects.link(obj)

        obj.furnigen.enabled = True
        obj.furnigen.geometry = self.GEOMETRY
        set_parameter_properties(obj.furnigen)
        build_geometry(obj)

        obj.select_set(True)
        context.view_layer.objects.active = obj

        return {'FINISHED'}

class VIEW3D_OT_construct_furnigen_object_door_30(VIEW3D_OT_construct_furnigen_object):
    bl_label = "Create 30s' door"
    bl_idname = "view3d.furnigen_create_door_30s"

    GEOMETRY = "30s Door"

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
class FURNIGEN_UL_parameter(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        layout.prop(item, "name", text="", emboss=False)
        layout.prop(item, "value", text="")

class FurniGenPanel(View3DPanel, bpy.types.Panel):
    bl_idname = "VIEW3D_PT_test_1"
    bl_label = "FurniGen"

    def draw(self, context):
        layout = self.layout
        for constructor_op in OBJECT_CONSTRUCTORS:
            layout.operator(constructor_op.bl_idname)

        if _is_furnigen_enabled(context):
            obj = context.object
            for name in ('Lengths', 'Counts'):
                box = layout.box()
                box.row().label(text=name)
                layout.template_list("FURNIGEN_UL_parameter", "", obj.furnigen, name.lower(), obj.furnigen, "index")

CLASSES = (
    FURNIGEN_UL_parameter,
    FurniGenLength,
    FurniGenCount,
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


