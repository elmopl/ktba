import bpy
import subprocess
from multiprocessing import cpu_count
from bpy.props import IntProperty
from bpy.props import EnumProperty
from bpy.props import PointerProperty
from bpy import types

bl_info = {
    "name": "VSE parallel render",
    "category": "VSE"
}

class ParallelRender(types.Operator):
    """Object Cursor Array"""
    bl_idname = "render.parallel_render"
    bl_label = "Parallel Render"
    bl_options = {'REGISTER'}

    batch_type = EnumProperty(
        items = [
            # (identifier, name, description, icon, number)
            ('fixed', 'Fixed', 'Render in fixed size batches'), 
            ('parts', 'No. parts', 'Render in given number of batches (automatically splits it)'),
            ('auto', 'Auto', 'Render in automatically calculated sized batches.')
        ],
        name = "Render Batch Size"
    )

    fixed = IntProperty(
        name = "Number of frames per batch",
        min = 1,
        default = 10,
        max = 10000
    )

    parts = IntProperty(
        name = "Number of batches",
        min = 1,
        default = cpu_count()-1,
        max = 10000
    )

    def draw(self, context):
        layout = self.layout
        if bpy.data.is_dirty:
            layout.label("You have unsaved changes.", text_ctxt="Render will be done with last saved version", icon='ERROR')
        layout.prop(self, "batch_type", expand=True)
        sub_prop = str(self.batch_type)
        if hasattr(self, sub_prop):
            layout.prop(self, sub_prop)

    def check(self, context):
        return True

    def execute(self, context):
        cmd = (
            bpy.app.binary_path,
            "--background",
            bpy.data.filepath,
            "--version"
        )
        
        subprocess.check_call(cmd)
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
def render_panel(self, context):
    scn = context.scene
    print("asfdasdfasdf")
    self.layout.prop(types.RenderSettings, 'parallel_render') 

def register():
    bpy.utils.register_module(__name__)
    print("Can see no. cpus:", cpu_count())

def unregister():
    bpy.utils.unregister_module(__name__)
    types.RENDER_PT_render.remove(render_panel)
