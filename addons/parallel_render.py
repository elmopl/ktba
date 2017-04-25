from bpy import types
from bpy.props import EnumProperty
from bpy.props import IntProperty
from bpy.props import PointerProperty
from multiprocessing import cpu_count
from multiprocessing.dummy import Pool
from queue import Queue
import bpy
import subprocess
import sys

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
        default = 300,
        max = 10000
    )

    parts = IntProperty(
        name = "Number of batches",
        min = 1,
        default = cpu_count() - 1,
        max = 10000
    )

    max_parallel = IntProperty(
        name = "Maximum number of instances",
        min = 1,
        default = cpu_count() // 2,
        max = 10000
    )


    def draw(self, context):
        layout = self.layout
        if bpy.data.is_dirty:
            layout.label("You have unsaved changes.", text_ctxt="Render will be done with last saved version", icon='ERROR')

        layout.prop(self, "max_parallel")

        layout.prop(self, "batch_type", expand=True)
        sub_prop = str(self.batch_type)
        if hasattr(self, sub_prop):
            layout.prop(self, sub_prop)

    def check(self, context):
        return True

    def _get_ranges_parts(self, scn):
        start = scn.frame_start - 1
        end = scn.frame_end
        length = end - start 
        parts = int(self.parts)

        if length <= parts:
            yield (start + 1, end)
            return

        for i in range(1, parts + 1):
            end = i * length // parts
            yield (start + 1, end)
            start = end

    def _get_ranges_fixed(self, scn):
        start = scn.frame_start
        end = scn.frame_end
        increment = int(self.fixed)
        while start <= end:
            yield (start, min(start + increment, end))
            start += increment + 1
        
    def execute(self, context):
        scn = context.scene

        make_ranges = getattr(self, '_get_ranges_{0}'.format(str(self.batch_type)))
        ranges = tuple(make_ranges(scn))

        cmds = (
            (
                (start, end),
                (
                    bpy.app.binary_path,
                    bpy.data.filepath,
                    '--background',
                    '--python',
                    __file__,
                    '--scene', str(scn.name),
                    '--start-frame', str(start),
                    '--end-frame', str(end),
                )
            )
            for start, end in ranges
        )

        with Pool(int(self.max_parallel)) as pool:
            wm = context.window_manager
            wm.progress_begin(0, len(ranges))

            run = lambda args: (args[0], args[1], subprocess.call(args[1]))
            pending = pool.imap_unordered(run, cmds)
            results = {}
            for num, (rng, cmd, res) in enumerate(pending):
                print(cmd, res)
                results[rng] = res
                wm.progress_update(num)
            wm.progress_end()
        
            print(results)
        #subprocess.check_call(cmd)
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
def render_panel(self, context):
    scn = context.scene
    self.layout.prop(types.RenderSettings, 'parallel_render') 

def register():
    bpy.utils.register_module(__name__)

def unregister():
    bpy.utils.unregister_module(__name__)
    types.RENDER_PT_render.remove(render_panel)

def render():
    start_pos = sys.argv.index(__file__)
    argv = iter(sys.argv[start_pos+1:])
    argv = dict(zip(argv, argv))

    scn_name = argv['--scene']
    scn = bpy.data.scenes[scn_name]
    scn.frame_start = int(argv['--start-frame'])
    scn.frame_end = int(argv['--end-frame'])

    bpy.ops.render.render(animation=True, scene = scn_name)

    sys.exit(0)

if __name__ == "__main__":
    render()

