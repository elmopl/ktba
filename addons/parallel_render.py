"""
Small addon for blender to help with rendering in VSE.
It automates rendering with multiple instances of blender.

Copyright (c) 2017 Krzysztof Trzcinski
"""

from bpy import types
from bpy.props import EnumProperty
from bpy.props import IntProperty
from bpy.props import PointerProperty
from multiprocessing import cpu_count
from multiprocessing.dummy import Pool
from threading import Thread
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
            ('parts', 'No. parts', 'Render in given number of batches (automatically splits it)'),
            ('fixed', 'Fixed', 'Render in fixed size batches'), 
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
        default = cpu_count() * 2,
        max = 10000
    )

    max_parallel = IntProperty(
        name = "Maximum number of instances",
        min = 1,
        default = cpu_count() // 2,
        max = 10000
    )

    still_running = False
    thread = None 
    state = None

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

    def _run(self, scn):
        make_ranges = getattr(self, '_get_ranges_{0}'.format(str(self.batch_type)))
        ranges = tuple(make_ranges(scn))

        cmds = tuple(
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

        self.state = {'total': len(cmds), 'done': 0}

        def run(args):
            rng, cmd = args
            if self.keep_running:
                res = subprocess.call(cmd)
            else:
                res = None

            return rng, cmd, res

        self.keep_running = True
        self.report({'INFO'}, 'Starting 0/{0} [0.0%]'.format(
            len(cmds)
        ))
        with Pool(int(self.max_parallel)) as pool:
            pending = pool.imap_unordered(run, cmds)
            results = {}
            for num, (rng, cmd, res) in enumerate(pending, 1):
                self.state['done'] = num
                results[rng] = res
                self._report_progress()
       
            for res in results.items():
                print(res)

    def _report_progress(self):
        action = 'Done' if self.keep_running else 'Cancelling'
        rep_type = 'INFO' if self.keep_running else 'WARNING'
        self.report({rep_type}, '{0} {1}/{2} [{3:.1f}%]'.format(
            action,
            self.state['done'],
            self.state['total'],
            100.0 * self.state['done'] / self.state['total']
        ))
        
    def execute(self, context):
        scn = context.scene
        wm = context.window_manager
        self.timer = wm.event_timer_add(0.5, context.window)
        wm.modal_handler_add(self)
        wm.progress_begin(0., 100.)
        self.thread = Thread(target=self._run, args=(scn,))
        self.thread.start()
        return{'RUNNING_MODAL'}

    def modal(self, context, event):
        wm = context.window_manager

        # Stop the thread when ESCAPE is pressed.
        if event.type == 'ESC':
            self.keep_running = False
            self._report_progress()

        if event.type == 'TIMER':
            still_running = self.thread.is_alive() 
            percent = 100.0 * self.state['done'] / self.state['total']

            if still_running:
                wm.progress_update(percent)
                self._report_progress()
                return {'PASS_THROUGH'}

            self.thread.join()
            wm.event_timer_remove(self.timer)
            wm.progress_end()
            return {'FINISHED'}

        return {'PASS_THROUGH'}

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

